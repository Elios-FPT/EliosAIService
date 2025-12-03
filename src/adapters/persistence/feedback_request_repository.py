"""PostgreSQL implementation of FeedbackRequestRepositoryPort."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import select

from ...domain.models.feedback_request import FeedbackRequest
from ...domain.models.feedback_result import FeedbackStatus, InputType
from ...domain.ports.feedback_repository_port import FeedbackRequestRepositoryPort
from .mappers import FeedbackRequestMapper
from .models import FeedbackRequestModel
from .session_provider import SessionProvider


class PostgresFeedbackRequestRepository(FeedbackRequestRepositoryPort):
    """PostgreSQL implementation of feedback request repository."""

    def __init__(self, session_provider: SessionProvider):
        """Initialize repository with session provider.

        Args:
            session_provider: Async context manager for database sessions
        """
        self._session_provider = session_provider

    async def create(
        self,
        entity_id: UUID,
        input_type: InputType,
        user_id: UUID | None = None,
    ) -> FeedbackRequest:
        """Create new feedback request with status=PENDING.

        Args:
            entity_id: UUID of entity to analyze
            input_type: Type of entity (INTERVIEW/CV/CODE)
            user_id: Optional user who requested analysis

        Returns:
            Created FeedbackRequest

        Raises:
            ValueError: If creation fails
        """
        from uuid import uuid4

        request = FeedbackRequest(
            id=uuid4(),
            entity_id=entity_id,
            input_type=input_type,
            user_id=user_id,
            status=FeedbackStatus.PENDING,
            error_message=None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        async with self._session_provider() as session:
            db_model = FeedbackRequestMapper.to_db_model(request)
            session.add(db_model)
            await session.commit()
            await session.refresh(db_model)
            return FeedbackRequestMapper.to_domain(db_model)

    async def get_by_id(self, request_id: UUID) -> FeedbackRequest | None:
        """Get request by ID.

        Args:
            request_id: Request UUID

        Returns:
            FeedbackRequest if found, None otherwise
        """
        async with self._session_provider() as session:
            result = await session.execute(
                select(FeedbackRequestModel).where(FeedbackRequestModel.id == request_id)
            )
            db_model = result.scalar_one_or_none()
            return (
                FeedbackRequestMapper.to_domain(db_model) if db_model else None
            )

    async def update_status(
        self,
        request_id: UUID,
        status: FeedbackStatus,
        error_message: str | None = None,
    ) -> FeedbackRequest:
        """Update request status and optional error message.

        Args:
            request_id: Request UUID
            status: New status
            error_message: Error message if status=FAILED

        Returns:
            Updated FeedbackRequest

        Raises:
            ValueError: If request not found
        """
        async with self._session_provider() as session:
            result = await session.execute(
                select(FeedbackRequestModel).where(
                    FeedbackRequestModel.id == request_id
                )
            )
            db_model = result.scalar_one_or_none()

            if not db_model:
                raise ValueError(f"FeedbackRequest {request_id} not found")

            db_model.status = status.value
            db_model.error_message = error_message
            db_model.updated_at = datetime.utcnow()

            await session.commit()
            await session.refresh(db_model)
            return FeedbackRequestMapper.to_domain(db_model)

    async def list_by_user(
        self,
        user_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[FeedbackRequest]:
        """List requests for user (for frontend dashboard).

        Args:
            user_id: User UUID
            limit: Max results (default 50, max 100)
            offset: Pagination offset

        Returns:
            List of FeedbackRequest ordered by created_at DESC
        """
        # Enforce max limit
        if limit > 100:
            limit = 100

        async with self._session_provider() as session:
            result = await session.execute(
                select(FeedbackRequestModel)
                .where(FeedbackRequestModel.user_id == user_id)
                .order_by(FeedbackRequestModel.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            db_models = result.scalars().all()
            return [FeedbackRequestMapper.to_domain(m) for m in db_models]

