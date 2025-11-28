"""Interview REST API endpoints."""

import os
import uuid
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from ....application.dto.interview_dto import (
    InterviewResponse,
    InterviewSummaryResponse,
    PlanInterviewRequest,
    PlanningStatusResponse,
    QuestionResponse,
)
from ....application.use_cases.analyze_cv import AnalyzeCVUseCase
from ....application.use_cases.get_next_question import GetNextQuestionUseCase
from ....domain.models.interview import InterviewStatus
from ....infrastructure.config.settings import get_settings
from ....infrastructure.database.session import get_async_session
from ....infrastructure.dependency_injection.container import get_container

router = APIRouter(prefix="/interviews", tags=["Interviews"])


@router.post("/cv/upload", summary="Upload CV for further analyze")
async def upload_cv(
    file: UploadFile = File(..., description="PDF CV file"),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Upload a CV file to the server.

    This endpoint accepts a PDF file and saves it to the server.
    Returns the file path where the CV is stored.
    """
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File must be a PDF")

    try:
        # Generate a unique filename
        setting = get_settings()
        UPLOAD_DIR = setting.upload_dir
        file_extension = os.path.splitext(file.filename)[1]
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        file_path = os.path.join(UPLOAD_DIR, unique_filename)

        # Save the uploaded file
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)

        # TODO: replace with data from User Service
        candidate_id = uuid.UUID("102ea1b3-f664-4617-8f43-fdde557f12b6")
        container = get_container()
        cv_analyzer = container.cv_analyzer_port()

        cv_analysis_use_case = AnalyzeCVUseCase(
            cv_analyzer=cv_analyzer,
            vector_search=container.vector_search_port(),
            candidate_repository_port=container.candidate_repository_port(session=session),
            cv_analysis_repository_port=container.cv_analysis_repository_port(session=session),
        )
        cv_analysis = await cv_analysis_use_case.execute(file_path, candidate_id)
        return cv_analysis

    except Exception as e:
        # Clean up the file if there was an error
        if "file_path" in locals() and os.path.exists(file_path):
            os.remove(file_path)

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error uploading file: {str(e)}",
        ) from e


@router.get(
    "/{interview_id}",
    response_model=InterviewResponse,
    summary="Get interview details",
)
async def get_interview(
    interview_id: UUID,
    session: AsyncSession = Depends(get_async_session),
):
    """Get interview by ID.

    Args:
        interview_id: Interview UUID
        session: Database session

    Returns:
        Interview details

    Raises:
        HTTPException: If interview not found
    """
    container = get_container()
    settings = get_settings()

    interview_repo = container.interview_repository_port(session=session)
    interview = await interview_repo.get_by_id(interview_id)

    if not interview:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Interview {interview_id} not found",
        )

    # Get total questions from junction table
    question_count = await interview_repo.count_interview_questions(interview_id)

    base_url = settings.ws_base_url
    return InterviewResponse.from_domain(interview, base_url, question_count)


@router.put(
    "/{interview_id}/start",
    response_model=InterviewResponse,
    summary="Start interview (move to IN_PROGRESS)",
)
async def start_interview(
    interview_id: UUID,
    session: AsyncSession = Depends(get_async_session),
):
    """Start interview session.

    Args:
        interview_id: Interview UUID
        session: Database session

    Returns:
        Updated interview details

    Raises:
        HTTPException: If interview not found or invalid state
    """
    container = get_container()
    settings = get_settings()

    interview_repo = container.interview_repository_port(session=session)
    interview = await interview_repo.get_by_id(interview_id)

    if not interview:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Interview {interview_id} not found",
        )

    try:
        interview.start()
        updated = await interview_repo.update(interview)

        # Get total questions from junction table
        question_count = await interview_repo.count_interview_questions(interview_id)

        base_url = settings.ws_base_url
        return InterviewResponse.from_domain(updated, base_url, question_count)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.get(
    "/{interview_id}/questions/current",
    response_model=QuestionResponse,
    summary="Get current question",
)
async def get_current_question(
    interview_id: UUID,
    session: AsyncSession = Depends(get_async_session),
):
    """Get current unanswered question.

    Args:
        interview_id: Interview UUID
        session: Database session

    Returns:
        Current question details

    Raises:
        HTTPException: If interview not found or no more questions
    """
    container = get_container()

    use_case = GetNextQuestionUseCase(
        interview_repository=container.interview_repository_port(session=session),
        question_repository=container.question_repository_port(session=session),
    )

    try:
        question = await use_case.execute(interview_id)
        if not question:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No more questions available",
            )

        # Get interview for context
        interview_repo = container.interview_repository_port(session=session)
        interview = await interview_repo.get_by_id(interview_id)

        if not interview:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Interview {interview_id} not found",
            )

        # Get total questions from junction table
        total_questions = await interview_repo.count_interview_questions(interview_id)

        return QuestionResponse(
            id=question.id,
            text=question.text,
            question_type=question.question_type.value,
            difficulty=question.difficulty.value,
            index=interview.current_question_index,
            total=total_questions,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


# NEW: Adaptive Planning Endpoints
@router.post(
    "/plan",
    response_model=PlanningStatusResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Plan interview with adaptive questions",
)
async def plan_interview(
    request: PlanInterviewRequest,
    session: AsyncSession = Depends(get_async_session),
):
    """Plan interview using LangGraph workflow.

    This endpoint triggers the pre-planning phase:
    1. Calculates n based on skill diversity (max 5)
    2. Generates n questions with ideal_answer + rationale (parallel execution)
    3. Returns interview with status=IDLE
    4. Uses PostgreSQL checkpointing for crash recovery

    Args:
        request: Planning request with cv_analysis_id and candidate_id
        session: Database session

    Returns:
        Planning status with interview_id

    Raises:
        HTTPException: If CV analysis not found or workflow fails
    """
    try:
        container = get_container()

        # Validate CV analysis exists
        cv_analysis_repo = container.cv_analysis_repository_port(session=session)
        cv_analysis = await cv_analysis_repo.get_by_id(request.cv_analysis_id)
        if not cv_analysis:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"CV analysis {request.cv_analysis_id} not found",
            )

        # Get settings for WebSocket URL
        settings = get_settings()

        # Use LangGraph workflow for interview planning
        from ....application.workflows.planning_workflow import PlanningWorkflow

        # Get checkpointer (async)
        checkpointer = await container.get_checkpointer()

        # Create workflow with dependencies from container
        workflow = PlanningWorkflow(
            checkpointer=checkpointer,
            llm_port=container.llm_port(session=session),
            cv_repo=cv_analysis_repo,
            question_repo=container.question_repository_port(session=session),
            interview_repo=container.interview_repository_port(session=session),
            vector_search=container.vector_search_port(),
        )

        # Execute workflow
        result = await workflow.execute(
            cv_analysis_id=request.cv_analysis_id,
            candidate_id=request.candidate_id,
        )
        interview = result.get("interview")

        # Check if workflow failed (interview is None)
        if interview is None:
            errors = result.get("errors", ["Unknown error occurred during interview planning"])
            raise HTTPException(status_code=500, detail=f"Failed to plan interview: {errors}")

        # Construct WebSocket URL for interview session
        ws_url = f"{settings.ws_base_url}/ws/interviews/{interview.id}"

        return PlanningStatusResponse(
            interview_id=interview.id,
            status=interview.status.value,
            planned_question_count=interview.planned_question_count,
            plan_metadata=interview.plan_metadata,
            message=f"Interview planned with {interview.planned_question_count} questions",
            ws_url=ws_url,  # WebSocket URL for real-time interview session
        )

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.get(
    "/{interview_id}/plan",
    response_model=PlanningStatusResponse,
    summary="Get interview planning status",
)
async def get_planning_status(
    interview_id: UUID,
    session: AsyncSession = Depends(get_async_session),
):
    """Get interview planning status.

    Args:
        interview_id: Interview UUID
        session: Database session

    Returns:
        Planning status details

    Raises:
        HTTPException: If interview not found
    """
    container = get_container()
    interview_repo = container.interview_repository_port(session=session)
    interview = await interview_repo.get_by_id(interview_id)

    if not interview:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Interview {interview_id} not found",
        )

    # Determine message based on status
    if interview.status == InterviewStatus.IDLE:
        message = f"Interview ready with {interview.planned_question_count} questions"
    elif (
        interview.status == InterviewStatus.QUESTIONING
        or interview.status == InterviewStatus.EVALUATING
    ):
        message = "Interview started"
    elif interview.status == InterviewStatus.COMPLETE:
        message = "Interview completed"
    else:
        message = f"Interview status: {interview.status.value}"

    # Construct WebSocket URL for interview session
    settings = get_settings()
    ws_url = f"{settings.ws_base_url}/ws/interviews/{interview.id}"

    return PlanningStatusResponse(
        interview_id=interview.id,
        status=interview.status.value,
        planned_question_count=interview.planned_question_count,
        plan_metadata=interview.plan_metadata,
        message=message,
        ws_url=ws_url,  # WebSocket URL for real-time interview session
    )


@router.get(
    "/{interview_id}/summary",
    response_model=InterviewSummaryResponse,
    summary="Get interview completion summary",
)
async def get_interview_summary(
    interview_id: UUID,
    session: AsyncSession = Depends(get_async_session),
):
    """Get comprehensive interview summary.

    This endpoint retrieves the cached summary generated during interview completion.
    Use case: Client reconnects after WebSocket disconnect and needs to retrieve summary.

    Args:
        interview_id: Interview UUID
        session: Database session

    Returns:
        Interview summary with all metrics, recommendations, and analysis

    Raises:
        HTTPException:
            - 404: Interview not found
            - 400: Interview not completed
            - 404: Summary not generated
    """
    container = get_container()
    interview_repo = container.interview_repository_port(session=session)
    interview = await interview_repo.get_by_id(interview_id)

    if not interview:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Interview {interview_id} not found",
        )

    if interview.status != InterviewStatus.COMPLETE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Interview not completed (status: {interview.status.value})",
        )

    # Extract summary from metadata
    summary = interview.plan_metadata.get("completion_summary") if interview.plan_metadata else None

    if not summary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Summary not found (interview completed without summary generation)",
        )

    return InterviewSummaryResponse(**summary)
