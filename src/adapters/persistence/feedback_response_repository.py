"""PostgreSQL implementation of FeedbackResponseRepositoryPort."""

from uuid import UUID

from sqlalchemy import select

from ...domain.models.feedback_response import FeedbackResponse
from ...domain.models.feedback_result import FeedbackResult, InputType
from ...application.ports.feedback_repository_port import FeedbackResponseRepositoryPort
from .mappers import FeedbackResponseMapper
from .models import FeedbackRequestModel, FeedbackResponseModel
from .session_provider import SessionProvider


class PostgresFeedbackResponseRepository(FeedbackResponseRepositoryPort):
    """PostgreSQL implementation of feedback response repository."""

    def __init__(self, session_provider: SessionProvider):
        """Initialize repository with session provider.

        Args:
            session_provider: Async context manager for database sessions
        """
        self._session_provider = session_provider

    async def create(
        self,
        request_id: UUID,
        result: FeedbackResult,
        prompt_execution_id: UUID | None = None,
    ) -> FeedbackResponse:
        """Create feedback response with type-safe result.

        Args:
            request_id: Foreign key to feedback_request
            result: Typed feedback result (Interview/Code/CV)
            prompt_execution_id: Optional link to prompt_executions for cost tracking

        Returns:
            Created FeedbackResponse

        Raises:
            ValueError: If creation fails
        """
        from datetime import datetime
        from uuid import uuid4

        response = FeedbackResponse(
            id=uuid4(),
            request_id=request_id,
            result=result,
            created_at=datetime.utcnow(),
        )

        async with self._session_provider() as session:
            db_model = FeedbackResponseMapper.to_db_model(response)
            # Set prompt_execution_id if provided
            if prompt_execution_id:
                db_model.prompt_execution_id = prompt_execution_id

            session.add(db_model)
            await session.commit()
            await session.refresh(db_model)

            # Fetch input_type from request for deserialization
            request_result = await session.execute(
                select(FeedbackRequestModel).where(
                    FeedbackRequestModel.id == request_id
                )
            )
            request_model = request_result.scalar_one_or_none()
            if not request_model:
                raise ValueError(f"FeedbackRequest {request_id} not found")

            input_type = InputType(request_model.input_type)
            return FeedbackResponseMapper.to_domain(db_model, input_type)

    async def get_by_request_id(self, request_id: UUID) -> FeedbackResponse | None:
        """Get response for request with type-safe deserialization.

        Args:
            request_id: Request UUID

        Returns:
            FeedbackResponse with deserialized result, or None

        Note:
            Fetches request.input_type to determine result class for deserialization.
        """
        async with self._session_provider() as session:
            # Fetch response
            response_result = await session.execute(
                select(FeedbackResponseModel).where(
                    FeedbackResponseModel.feedback_request_id == request_id
                )
            )
            db_model = response_result.scalar_one_or_none()
            if not db_model:
                return None

            # Fetch request to get input_type
            request_result = await session.execute(
                select(FeedbackRequestModel).where(
                    FeedbackRequestModel.id == request_id
                )
            )
            request_model = request_result.scalar_one_or_none()
            if not request_model:
                return None

            input_type = InputType(request_model.input_type)
            return FeedbackResponseMapper.to_domain(db_model, input_type)

