"""PostgreSQL implementation of FollowUpQuestionRepositoryPort."""

from uuid import UUID

from sqlalchemy import select

from ...domain.models.follow_up_question import FollowUpQuestion
from ...application.ports.follow_up_question_repository_port import (
    FollowUpQuestionRepositoryPort,
)
from .mappers import FollowUpQuestionMapper
from .models import FollowUpQuestionModel
from .session_provider import SessionProvider


class PostgreSQLFollowUpQuestionRepository(FollowUpQuestionRepositoryPort):
    """PostgreSQL implementation of follow-up question repository.

    This adapter implements the FollowUpQuestionRepositoryPort interface
    using SQLAlchemy and PostgreSQL for persistence.
    """

    def __init__(self, session_provider: SessionProvider):
        """Initialize repository with session provider."""
        self._session_provider = session_provider

    async def save(self, follow_up_question: FollowUpQuestion) -> FollowUpQuestion:
        """Save a new follow-up question to the database.

        Args:
            follow_up_question: FollowUpQuestion to save

        Returns:
            Saved follow-up question
        """
        async with self._session_provider() as session:
            db_model = FollowUpQuestionMapper.to_db_model(follow_up_question)
            session.add(db_model)
            await session.commit()
            await session.refresh(db_model)
            return FollowUpQuestionMapper.to_domain(db_model)

    async def get_by_id(self, question_id: UUID) -> FollowUpQuestion | None:
        """Retrieve a follow-up question by ID.

        Args:
            question_id: Follow-up question identifier

        Returns:
            FollowUpQuestion if found, None otherwise
        """
        async with self._session_provider() as session:
            result = await session.execute(
                select(FollowUpQuestionModel).where(
                    FollowUpQuestionModel.id == question_id
                )
            )
            db_model = result.scalar_one_or_none()
            return FollowUpQuestionMapper.to_domain(db_model) if db_model else None

    async def get_by_parent_question_id(
        self, parent_question_id: UUID
    ) -> list[FollowUpQuestion]:
        """Retrieve all follow-up questions for a parent question.

        Args:
            parent_question_id: Parent question identifier

        Returns:
            List of follow-up questions ordered by order_in_sequence
        """
        async with self._session_provider() as session:
            result = await session.execute(
                select(FollowUpQuestionModel)
                .where(FollowUpQuestionModel.parent_question_id == parent_question_id)
                .order_by(FollowUpQuestionModel.order_in_sequence)
            )
            db_models = result.scalars().all()
            return [FollowUpQuestionMapper.to_domain(db_model) for db_model in db_models]

    async def get_by_interview_id(self, interview_id: UUID) -> list[FollowUpQuestion]:
        """Retrieve all follow-up questions for an interview.

        Args:
            interview_id: Interview identifier

        Returns:
            List of follow-up questions ordered by created_at
        """
        async with self._session_provider() as session:
            result = await session.execute(
                select(FollowUpQuestionModel)
                .where(FollowUpQuestionModel.interview_id == interview_id)
                .order_by(FollowUpQuestionModel.created_at)
            )
            db_models = result.scalars().all()
            return [FollowUpQuestionMapper.to_domain(db_model) for db_model in db_models]

    async def count_by_parent_question_id(self, parent_question_id: UUID) -> int:
        """Count follow-up questions for a parent question.

        Args:
            parent_question_id: Parent question identifier

        Returns:
            Count of follow-up questions
        """
        async with self._session_provider() as session:
            result = await session.execute(
                select(FollowUpQuestionModel).where(
                    FollowUpQuestionModel.parent_question_id == parent_question_id
                )
            )
            db_models = result.scalars().all()
            return len(db_models)

    async def delete(self, question_id: UUID) -> bool:
        """Delete a follow-up question.

        Args:
            question_id: Follow-up question identifier

        Returns:
            True if deleted, False if not found
        """
        async with self._session_provider() as session:
            result = await session.execute(
                select(FollowUpQuestionModel).where(
                    FollowUpQuestionModel.id == question_id
                )
            )
            db_model = result.scalar_one_or_none()

            if db_model:
                await session.delete(db_model)
                await session.commit()
                return True
            return False
