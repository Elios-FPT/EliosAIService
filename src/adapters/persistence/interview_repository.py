"""PostgreSQL implementation of InterviewRepositoryPort."""

from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.orm import selectinload

from ...domain.models.interview import Interview, InterviewStatus
from ...domain.models.interview_question import InterviewQuestion
from ...domain.ports.interview_repository_port import InterviewRepositoryPort
from .mappers import InterviewMapper, InterviewQuestionMapper
from .models import InterviewModel, InterviewQuestionModel
from .session_provider import SessionProvider


class PostgreSQLInterviewRepository(InterviewRepositoryPort):
    """PostgreSQL implementation of interview repository.

    This adapter implements the InterviewRepositoryPort interface
    using SQLAlchemy and PostgreSQL for persistence.
    """

    def __init__(self, session_provider: SessionProvider):
        """Initialize repository with session provider."""
        self._session_provider = session_provider

    async def save(self, interview: Interview) -> Interview:
        """Save a new interview to the database."""
        async with self._session_provider() as session:
            db_model = InterviewMapper.to_db_model(interview)
            session.add(db_model)
            await session.commit()
            await session.refresh(db_model)
            return InterviewMapper.to_domain(db_model)

    async def get_by_id(self, interview_id: UUID) -> Interview | None:
        """Retrieve an interview by ID."""
        async with self._session_provider() as session:
            result = await session.execute(
                select(InterviewModel)
                .where(InterviewModel.id == interview_id)
                .where(InterviewModel.deleted_at.is_(None))
            )
            db_model = result.scalar_one_or_none()
            return InterviewMapper.to_domain(db_model) if db_model else None

    async def get_by_candidate_id(
        self,
        candidate_id: UUID,
        status: InterviewStatus | None = None,
    ) -> list[Interview]:
        """Retrieve interviews for a candidate with optional status filter."""
        query = select(InterviewModel).where(InterviewModel.candidate_id == candidate_id)

        if status:
            query = query.where(InterviewModel.status == status.value)

        query = query.where(InterviewModel.deleted_at.is_(None)).order_by(
            InterviewModel.created_at.desc()
        )

        async with self._session_provider() as session:
            result = await session.execute(query)
            db_models = result.scalars().all()
            return [InterviewMapper.to_domain(db_model) for db_model in db_models]

    async def get_active_by_candidate(self, candidate_id: UUID) -> Interview | None:
        """Retrieve the most recent active interview for a candidate.

        Active interviews are those that are not in terminal states (COMPLETE, CANCELLED).
        This includes: PLANNING, IDLE, QUESTIONING, EVALUATING, FOLLOW_UP.

        Args:
            candidate_id: Candidate identifier

        Returns:
            Most recent active interview if found, None otherwise
        """
        async with self._session_provider() as session:
            result = await session.execute(
                select(InterviewModel)
                .where(InterviewModel.candidate_id == candidate_id)
                .where(InterviewModel.deleted_at.is_(None))
                .where(
                    InterviewModel.status.notin_(
                        [InterviewStatus.COMPLETE.value, InterviewStatus.CANCELLED.value]
                    )
                )
                .order_by(InterviewModel.created_at.desc())
                .limit(1)
            )
            db_model = result.scalar_one_or_none()
            return InterviewMapper.to_domain(db_model) if db_model else None

    async def get_by_status(
        self,
        status: InterviewStatus,
        limit: int = 100,
    ) -> list[Interview]:
        """Retrieve interviews by status."""
        async with self._session_provider() as session:
            result = await session.execute(
                select(InterviewModel)
                .where(InterviewModel.status == status.value)
                .where(InterviewModel.deleted_at.is_(None))
                .order_by(InterviewModel.created_at.desc())
                .limit(limit)
            )
            db_models = result.scalars().all()
            return [InterviewMapper.to_domain(db_model) for db_model in db_models]

    async def update(self, interview: Interview) -> Interview:
        """Update an existing interview."""
        async with self._session_provider() as session:
            result = await session.execute(
                select(InterviewModel).where(InterviewModel.id == interview.id)
            )
            db_model = result.scalar_one_or_none()

            if not db_model:
                raise ValueError(f"Interview with id {interview.id} not found")

            InterviewMapper.update_db_model(db_model, interview)
            await session.commit()
            await session.refresh(db_model)
            return InterviewMapper.to_domain(db_model)

    async def delete(self, interview_id: UUID) -> bool:
        """Delete an interview by ID."""
        async with self._session_provider() as session:
            result = await session.execute(
                select(InterviewModel).where(InterviewModel.id == interview_id)
            )
            db_model = result.scalar_one_or_none()

            if not db_model:
                return False

            await session.delete(db_model)
            await session.commit()
            return True

    async def list_all(self, skip: int = 0, limit: int = 100) -> list[Interview]:
        """List all interviews with pagination."""
        async with self._session_provider() as session:
            result = await session.execute(
                select(InterviewModel)
                .where(InterviewModel.deleted_at.is_(None))
                .order_by(InterviewModel.created_at.desc())
                .offset(skip)
                .limit(limit)
            )
            db_models = result.scalars().all()
            return [InterviewMapper.to_domain(db_model) for db_model in db_models]

    # New methods for interview_questions junction table management

    async def get_interview_questions(self, interview_id: UUID) -> list[InterviewQuestion]:
        """Get all questions for an interview, ordered by sequence.

        Phase 2 Optimization: Uses selectinload() to prevent N+1 queries.
        Before: 1 parent query + N lazy loads (1+N queries total)
        After: 1 parent query + 1 eager load with IN clause (2 queries total)

        Args:
            interview_id: UUID of the interview

        Returns:
            List of InterviewQuestion domain models ordered by sequence_order
        """
        async with self._session_provider() as session:
            result = await session.execute(
                select(InterviewQuestionModel)
                .options(selectinload(InterviewQuestionModel.question))  # Phase 2: Eager load
                .where(InterviewQuestionModel.interview_id == interview_id)
                .order_by(InterviewQuestionModel.sequence_order)
            )
            db_models = result.scalars().all()
            return [InterviewQuestionMapper.to_domain(db_model) for db_model in db_models]

    async def add_question(
        self,
        interview_id: UUID,
        question_id: UUID,
        sequence_order: int,
    ) -> InterviewQuestion:
        """Add a question to an interview with specified sequence order.

        Args:
            interview_id: UUID of the interview
            question_id: UUID of the question to add
            sequence_order: 0-based order in the interview sequence

        Returns:
            Created InterviewQuestion domain model
        """
        from uuid import uuid4

        interview_question = InterviewQuestion(
            id=uuid4(),
            interview_id=interview_id,
            question_id=question_id,
            sequence_order=sequence_order,
            asked_at=None,
            skipped=False,
            skip_reason=None,
            created_at=datetime.utcnow(),
        )

        async with self._session_provider() as session:
            db_model = InterviewQuestionMapper.to_db_model(interview_question)
            session.add(db_model)
            await session.commit()
            await session.refresh(db_model)
            return InterviewQuestionMapper.to_domain(db_model)

    async def get_current_question(self, interview_id: UUID) -> InterviewQuestion | None:
        """Get the current question for an interview based on current_question_index.

        Phase 2 Optimization: Uses selectinload() to prevent N+1 queries.

        Args:
            interview_id: UUID of the interview

        Returns:
            Current InterviewQuestion or None if interview complete or not found
        """
        # First get interview to find current_question_index
        async with self._session_provider() as session:
            interview_result = await session.execute(
                select(InterviewModel).where(InterviewModel.id == interview_id)
            )
            interview_model = interview_result.scalar_one_or_none()

            if not interview_model:
                return None

            result = await session.execute(
                select(InterviewQuestionModel)
                .options(selectinload(InterviewQuestionModel.question))  # Phase 2: Eager load
                .where(InterviewQuestionModel.interview_id == interview_id)
                .where(
                    InterviewQuestionModel.sequence_order
                    == interview_model.current_question_index
                )
            )
            db_model = result.scalar_one_or_none()
            return InterviewQuestionMapper.to_domain(db_model) if db_model else None

    async def mark_question_asked(
        self,
        interview_question_id: UUID,
        asked_at: datetime | None = None,
    ) -> InterviewQuestion:
        """Mark a question as asked with timestamp.

        Args:
            interview_question_id: UUID of the InterviewQuestion record
            asked_at: Timestamp when question was asked (defaults to now)

        Returns:
            Updated InterviewQuestion domain model

        Raises:
            ValueError: If InterviewQuestion not found
        """
        async with self._session_provider() as session:
            result = await session.execute(
                select(InterviewQuestionModel).where(
                    InterviewQuestionModel.id == interview_question_id
                )
            )
            db_model = result.scalar_one_or_none()

            if not db_model:
                raise ValueError(
                    f"InterviewQuestion with id {interview_question_id} not found"
                )

            db_model.asked_at = asked_at or datetime.utcnow()
            await session.commit()
            await session.refresh(db_model)
            return InterviewQuestionMapper.to_domain(db_model)

    async def count_interview_questions(self, interview_id: UUID) -> int:
        """Count total questions for an interview.

        Args:
            interview_id: UUID of the interview

        Returns:
            Total number of questions in the interview
        """
        from sqlalchemy import func

        async with self._session_provider() as session:
            result = await session.execute(
                select(func.count(InterviewQuestionModel.id)).where(
                    InterviewQuestionModel.interview_id == interview_id
                )
            )
            return result.scalar_one()

    async def soft_delete_by_candidate_id(self, candidate_id: UUID) -> int:
        """Soft delete all interviews for a candidate that are not already deleted."""
        async with self._session_provider() as session:
            stmt = (
                update(InterviewModel)
                .where(InterviewModel.candidate_id == candidate_id)
                .where(InterviewModel.deleted_at.is_(None))
                .values(deleted_at=datetime.utcnow())
            )
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount or 0

    async def hard_delete_old_soft_deleted(self, days: int = 30) -> int:
        """Hard delete interviews soft-deleted more than N days ago."""
        async with self._session_provider() as session:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            stmt = delete(InterviewModel).where(
                InterviewModel.deleted_at.is_not(None),
                InterviewModel.deleted_at < cutoff_date,
            )
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount or 0
