"""REST API endpoints for feedback analysis."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ....application.dto.feedback_dto import (
    AnalyzeFeedbackRequest,
    AnalyzeFeedbackResponse,
    FeedbackHistoryResponse,
)
from ....application.use_cases.analyze_feedback import (
    AnalyzeFeedbackUseCase,
    LLMMaxRetriesError,
)
from ....domain.models.feedback_result import FeedbackStatus, InputType
from ....infrastructure.database.session import get_async_session
from ....infrastructure.dependency_injection.container import get_container

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/feedback", tags=["Feedback"])


def get_analyze_feedback_use_case(
    session: AsyncSession = Depends(get_async_session),
) -> AnalyzeFeedbackUseCase:
    """Dependency injection for use case.

    Args:
        session: Database session

    Returns:
        Configured AnalyzeFeedbackUseCase
    """
    container = get_container()
    return container.analyze_feedback_use_case(session=session)


@router.post("/analyze", response_model=AnalyzeFeedbackResponse, status_code=status.HTTP_200_OK)
async def analyze_feedback(
    request: AnalyzeFeedbackRequest,
    use_case: AnalyzeFeedbackUseCase = Depends(get_analyze_feedback_use_case),
) -> AnalyzeFeedbackResponse:
    """Analyze entity and return feedback (synchronous).

    **Processing Time:**
    - INTERVIEW: 5-10s (LLM analysis)
    - CODE: 3-8s (code review) - Not yet implemented
    - CV: 2-5s (skill extraction)

    **Note:** Frontend should show loading spinner during wait.

    **Error Handling:**
    - 400: Invalid entity_id or input_type
    - 404: Entity not found
    - 500: LLM failure after retries
    - 503: Service temporarily unavailable

    Args:
        request: Analysis request DTO
        use_case: Injected use case

    Returns:
        AnalyzeFeedbackResponse with typed result

    Raises:
        HTTPException: On various error conditions
    """
    try:
        # Validate input_type
        try:
            input_type = InputType(request.input_type.upper())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid input_type: {request.input_type}. Must be INTERVIEW, CV, or CODE",
            )

        feedback_request, result = await use_case.execute(
            entity_id=request.entity_id,
            input_type=input_type,
            user_id=request.user_id,
        )

        return AnalyzeFeedbackResponse(
            request_id=feedback_request.id,
            status=feedback_request.status.value,
            result=result,
            error_message=feedback_request.error_message,
        )

    except ValueError as e:
        # Entity not found or validation error
        error_msg = str(e)
        if "not found" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=error_msg
            ) from e
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg
        ) from e
    except NotImplementedError as e:
        # CODE analysis not implemented
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(e)
        ) from e
    except LLMMaxRetriesError as e:
        # LLM failed after retries
        logger.error(f"LLM max retries exceeded: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Analysis service temporarily unavailable. Please try again later.",
        ) from e
    except Exception as e:
        # Unexpected error
        logger.error(f"Unexpected error in analyze_feedback: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Analysis failed: {str(e)}",
        ) from e


@router.get(
    "/history/{user_id}",
    response_model=list[FeedbackHistoryResponse],
    status_code=status.HTTP_200_OK,
)
async def get_feedback_history(
    user_id: UUID,
    limit: int = 50,
    offset: int = 0,
    session: AsyncSession = Depends(get_async_session),
    use_case: AnalyzeFeedbackUseCase = Depends(get_analyze_feedback_use_case),
) -> list[FeedbackHistoryResponse]:
    """Get feedback history for user (frontend dashboard).

    **Query Parameters:**
    - limit: Max results (default 50, max 100)
    - offset: Pagination offset

    **Response:** List of feedback requests with results (sorted by created_at DESC)

    Args:
        user_id: User UUID
        limit: Max results
        offset: Pagination offset
        use_case: Injected use case

    Returns:
        List of FeedbackHistoryResponse
    """
    # Enforce max limit
    if limit > 100:
        limit = 100

    requests = await use_case.list_user_feedback(user_id, limit, offset)

    # Map to response DTOs
    # Fetch responses for all SUCCESS requests
    container = get_container()
    response_repo = container.feedback_response_repository_port(session=session)
    responses = []
    for req in requests:
        # Fetch response if status=SUCCESS
        result = None
        if req.status == FeedbackStatus.SUCCESS:
            response = await response_repo.get_by_request_id(req.id)
            if response:
                result = response.result

        responses.append(
            FeedbackHistoryResponse(
                request_id=req.id,
                entity_id=req.entity_id,
                input_type=req.input_type.value,
                status=req.status.value,
                created_at=req.created_at.isoformat(),
                result=result,
                error_message=req.error_message,
            )
        )

    return responses


@router.get(
    "/{request_id}",
    response_model=AnalyzeFeedbackResponse,
    status_code=status.HTTP_200_OK,
)
async def get_feedback_by_id(
    request_id: UUID,
    session: AsyncSession = Depends(get_async_session),
) -> AnalyzeFeedbackResponse:
    """Get feedback by request ID.

    Args:
        request_id: Feedback request UUID
        session: Database session

    Returns:
        AnalyzeFeedbackResponse

    Raises:
        HTTPException: If request not found
    """
    container = get_container()
    request_repo = container.feedback_request_repository_port(session=session)
    response_repo = container.feedback_response_repository_port(session=session)

    feedback_request = await request_repo.get_by_id(request_id)
    if not feedback_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Feedback request {request_id} not found",
        )

    # Fetch response if status=SUCCESS
    result = None
    if feedback_request.status == FeedbackStatus.SUCCESS:
        response = await response_repo.get_by_request_id(request_id)
        if response:
            result = response.result

    return AnalyzeFeedbackResponse(
        request_id=feedback_request.id,
        status=feedback_request.status.value,
        result=result,
        error_message=feedback_request.error_message,
    )

