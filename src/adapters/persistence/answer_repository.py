"""PostgreSQL implementation of AnswerRepositoryPort."""

from uuid import UUID

from sqlalchemy import select

from ...domain.models.answer import Answer
from ...application.ports.answer_repository_port import AnswerRepositoryPort
from .mappers import AnswerMapper
from .models import AnswerModel
from .session_provider import SessionProvider


class PostgreSQLAnswerRepository(AnswerRepositoryPort):
    """PostgreSQL implementation of answer repository.

    This adapter implements the AnswerRepositoryPort interface
    using SQLAlchemy and PostgreSQL for persistence.
    """

    def __init__(self, session_provider: SessionProvider):
        """Initialize repository with session provider."""
        self._session_provider = session_provider

    async def save(self, answer: Answer) -> Answer:
        """Save a new answer to the database."""
        async with self._session_provider() as session:
            db_model = AnswerMapper.to_db_model(answer)
            session.add(db_model)
            await session.commit()
            await session.refresh(db_model)
            return AnswerMapper.to_domain(db_model)

    async def get_by_id(self, answer_id: UUID) -> Answer | None:
        """Retrieve an answer by ID."""
        async with self._session_provider() as session:
            result = await session.execute(
                select(AnswerModel).where(AnswerModel.id == answer_id)
            )
            db_model = result.scalar_one_or_none()
            return AnswerMapper.to_domain(db_model) if db_model else None

    async def get_by_ids(self, answer_ids: list[UUID]) -> list[Answer]:
        """Retrieve multiple answers by IDs."""
        async with self._session_provider() as session:
            result = await session.execute(
                select(AnswerModel).where(AnswerModel.id.in_(answer_ids))
            )
            db_models = result.scalars().all()
            return [AnswerMapper.to_domain(db_model) for db_model in db_models]

    async def get_by_interview_id(self, interview_id: UUID) -> list[Answer]:
        """Retrieve all answers for an interview."""
        async with self._session_provider() as session:
            result = await session.execute(
                select(AnswerModel)
                .where(AnswerModel.interview_id == interview_id)
                .order_by(AnswerModel.created_at.asc())
            )
            db_models = result.scalars().all()
            return [AnswerMapper.to_domain(db_model) for db_model in db_models]

    async def get_by_question_id(self, question_id: UUID) -> list[Answer]:
        """Retrieve all answers for a question."""
        result = await self.session.execute(
            select(AnswerModel)
            .where(AnswerModel.question_id == question_id)
            .order_by(AnswerModel.created_at.desc())
        )
        db_models = result.scalars().all()
        return [AnswerMapper.to_domain(db_model) for db_model in db_models]

    async def get_by_candidate_id(self, candidate_id: UUID) -> list[Answer]:
        """Retrieve all answers by a candidate via interview relationship.

        Note: candidate_id removed from answers table. Query via interviews JOIN.
        """
        from .models import InterviewModel

        async with self._session_provider() as session:
            result = await session.execute(
                select(AnswerModel)
                .join(InterviewModel, AnswerModel.interview_id == InterviewModel.id)
                .where(InterviewModel.candidate_id == candidate_id)
                .order_by(AnswerModel.created_at.desc())
            )
            db_models = result.scalars().all()
            return [AnswerMapper.to_domain(db_model) for db_model in db_models]

    async def update(self, answer: Answer) -> Answer:
        """Update an existing answer."""
        async with self._session_provider() as session:
            result = await session.execute(
                select(AnswerModel).where(AnswerModel.id == answer.id)
            )
            db_model = result.scalar_one_or_none()

            if not db_model:
                raise ValueError(f"Answer with id {answer.id} not found")

            AnswerMapper.update_db_model(db_model, answer)
            await session.commit()
            await session.refresh(db_model)
            return AnswerMapper.to_domain(db_model)

    async def delete(self, answer_id: UUID) -> bool:
        """Delete an answer by ID."""
        async with self._session_provider() as session:
            result = await session.execute(
                select(AnswerModel).where(AnswerModel.id == answer_id)
            )
            db_model = result.scalar_one_or_none()

            if not db_model:
                return False

            await session.delete(db_model)
            await session.commit()
            return True
