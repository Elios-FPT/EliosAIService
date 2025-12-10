"""PostgreSQL implementation of QuestionRepositoryPort."""

from uuid import UUID

from async_lru import alru_cache
from sqlalchemy import select

from src.domain.models.question import DifficultyLevel, Question, QuestionType
from src.application.ports.question_repository_port import QuestionRepositoryPort
from .mappers import QuestionMapper
from .models import QuestionModel
from .session_provider import SessionProvider


class PostgreSQLQuestionRepository(QuestionRepositoryPort):
    """PostgreSQL implementation of question repository.

    This adapter implements the QuestionRepositoryPort interface
    using SQLAlchemy and PostgreSQL for persistence.
    """

    def __init__(self, session_provider: SessionProvider):
        """Initialize repository with session provider."""
        self._session_provider = session_provider

    async def save(self, question: Question) -> Question:
        """Save a new question to the database."""
        async with self._session_provider() as session:
            db_model = QuestionMapper.to_db_model(question)
            session.add(db_model)
            await session.commit()
            await session.refresh(db_model)
            return QuestionMapper.to_domain(db_model)

    async def save_batch(self, questions: list[Question]) -> list[Question]:
        """Save multiple questions in a single atomic transaction.

        All questions are saved in one transaction. If any question fails,
        the entire transaction is rolled back.

        Args:
            questions: List of questions to save

        Returns:
            List of saved questions with updated metadata

        Raises:
            Exception: If any question fails to save, entire transaction is rolled back
        """
        async with self._session_provider() as session:
            db_models = []
            for question in questions:
                db_model = QuestionMapper.to_db_model(question)
                session.add(db_model)
                db_models.append(db_model)

            # Commit all questions in one transaction
            await session.commit()

            # Refresh all models to get updated metadata
            for db_model in db_models:
                await session.refresh(db_model)

            return [QuestionMapper.to_domain(db_model) for db_model in db_models]

    @alru_cache(maxsize=128)  # Phase 3: Cache last 128 questions (LRU)
    async def get_by_id(self, question_id: UUID) -> Question | None:
        """Retrieve a question by ID (cached for performance).

        Phase 3 optimization: LRU cache reduces redundant DB queries for same question bank.
        Cache invalidated on update/delete operations.
        """
        async with self._session_provider() as session:
            result = await session.execute(
                select(QuestionModel).where(QuestionModel.id == question_id)
            )
            db_model = result.scalar_one_or_none()
            return QuestionMapper.to_domain(db_model) if db_model else None

    async def get_by_ids(self, question_ids: list[UUID]) -> list[Question]:
        """Retrieve multiple questions by IDs."""
        async with self._session_provider() as session:
            result = await session.execute(
                select(QuestionModel).where(QuestionModel.id.in_(question_ids))
            )
            db_models = result.scalars().all()
            return [QuestionMapper.to_domain(db_model) for db_model in db_models]

    async def find_by_skill(
        self,
        skill: str,
        difficulty: DifficultyLevel | None = None,
        limit: int = 10,
    ) -> list[Question]:
        """Find questions by skill with optional difficulty filter."""
        query = select(QuestionModel).where(
            QuestionModel.skills.contains([skill])  # PostgreSQL array contains
        )

        if difficulty:
            query = query.where(QuestionModel.difficulty == difficulty.value)

        query = query.limit(limit)

        async with self._session_provider() as session:
            result = await session.execute(query)
            db_models = result.scalars().all()
            return [QuestionMapper.to_domain(db_model) for db_model in db_models]

    async def find_by_type(
        self,
        question_type: QuestionType,
        difficulty: DifficultyLevel | None = None,
        limit: int = 10,
    ) -> list[Question]:
        """Find questions by type with optional difficulty filter."""
        query = select(QuestionModel).where(
            QuestionModel.question_type == question_type.value
        )

        if difficulty:
            query = query.where(QuestionModel.difficulty == difficulty.value)

        query = query.limit(limit)

        async with self._session_provider() as session:
            result = await session.execute(query)
            db_models = result.scalars().all()
            return [QuestionMapper.to_domain(db_model) for db_model in db_models]

    async def find_by_tags(
        self,
        tags: list[str],
        match_all: bool = False,
        limit: int = 10,
    ) -> list[Question]:
        """Find questions by tags.

        Args:
            tags: List of tags to search for
            match_all: If True, match all tags; if False, match any tag
            limit: Maximum number of results
        """
        if match_all:
            # Match all tags (array contains all elements)
            query = select(QuestionModel).where(
                QuestionModel.tags.contains(tags)  # PostgreSQL @> operator
            )
        else:
            # Match any tag (array overlap)
            query = select(QuestionModel).where(
                QuestionModel.tags.overlap(tags)  # PostgreSQL && operator
            )

        query = query.limit(limit)

        async with self._session_provider() as session:
            result = await session.execute(query)
            db_models = result.scalars().all()
            return [QuestionMapper.to_domain(db_model) for db_model in db_models]

    async def update(self, question: Question) -> Question:
        """Update an existing question and invalidate cache (Phase 3)."""
        async with self._session_provider() as session:
            result = await session.execute(
                select(QuestionModel).where(QuestionModel.id == question.id)
            )
            db_model = result.scalar_one_or_none()

            if not db_model:
                raise ValueError(f"Question with id {question.id} not found")

            QuestionMapper.update_db_model(db_model, question)
            await session.commit()
            await session.refresh(db_model)

            # Phase 3: Invalidate cache entry
            self.get_by_id.cache_invalidate(question.id)

            return QuestionMapper.to_domain(db_model)

    async def delete(self, question_id: UUID) -> bool:
        """Delete a question by ID and invalidate cache (Phase 3)."""
        async with self._session_provider() as session:
            result = await session.execute(
                select(QuestionModel).where(QuestionModel.id == question_id)
            )
            db_model = result.scalar_one_or_none()

            if not db_model:
                return False

            await session.delete(db_model)
            await session.commit()

            # Phase 3: Invalidate cache entry
            self.get_by_id.cache_invalidate(question_id)

            return True

    async def list_all(self, skip: int = 0, limit: int = 100) -> list[Question]:
        """List all questions with pagination."""
        async with self._session_provider() as session:
            result = await session.execute(
                select(QuestionModel)
                .order_by(QuestionModel.created_at.desc())
                .offset(skip)
                .limit(limit)
            )
            db_models = result.scalars().all()
            return [QuestionMapper.to_domain(db_model) for db_model in db_models]
