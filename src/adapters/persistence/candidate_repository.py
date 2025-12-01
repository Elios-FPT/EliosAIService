"""PostgreSQL implementation of CandidateRepositoryPort."""

from uuid import UUID

from sqlalchemy import select

from ...domain.models.candidate import Candidate
from ...domain.ports.candidate_repository_port import CandidateRepositoryPort
from .mappers import CandidateMapper
from .models import CandidateModel
from .session_provider import SessionProvider


class PostgreSQLCandidateRepository(CandidateRepositoryPort):
    """PostgreSQL implementation of candidate repository.

    This adapter implements the CandidateRepositoryPort interface
    using SQLAlchemy and PostgreSQL for persistence.
    """

    def __init__(self, session_provider: SessionProvider):
        """Initialize repository with session provider."""
        self._session_provider = session_provider

    async def save(self, candidate: Candidate) -> Candidate:
        """Save a new candidate to the database."""
        async with self._session_provider() as session:
            db_model = CandidateMapper.to_db_model(candidate)
            session.add(db_model)
            await session.commit()
            await session.refresh(db_model)
            return CandidateMapper.to_domain(db_model)

    async def get_by_id(self, candidate_id: UUID) -> Candidate | None:
        """Retrieve a candidate by ID."""
        async with self._session_provider() as session:
            result = await session.execute(
                select(CandidateModel).where(CandidateModel.id == candidate_id)
            )
            db_model = result.scalar_one_or_none()
            return CandidateMapper.to_domain(db_model) if db_model else None

    async def get_by_email(self, email: str) -> Candidate | None:
        """Retrieve a candidate by email address."""
        async with self._session_provider() as session:
            result = await session.execute(
                select(CandidateModel).where(CandidateModel.email == email)
            )
            db_model = result.scalar_one_or_none()
            return CandidateMapper.to_domain(db_model) if db_model else None

    async def update(self, candidate: Candidate) -> Candidate:
        """Update an existing candidate."""
        async with self._session_provider() as session:
            result = await session.execute(
                select(CandidateModel).where(CandidateModel.id == candidate.id)
            )
            db_model = result.scalar_one_or_none()

            if not db_model:
                raise ValueError(f"Candidate with id {candidate.id} not found")

            CandidateMapper.update_db_model(db_model, candidate)
            await session.commit()
            await session.refresh(db_model)
            return CandidateMapper.to_domain(db_model)

    async def delete(self, candidate_id: UUID) -> bool:
        """Delete a candidate by ID."""
        async with self._session_provider() as session:
            result = await session.execute(
                select(CandidateModel).where(CandidateModel.id == candidate_id)
            )
            db_model = result.scalar_one_or_none()

            if not db_model:
                return False

            await session.delete(db_model)
            await session.commit()
            return True

    async def list_all(self, skip: int = 0, limit: int = 100) -> list[Candidate]:
        """List all candidates with pagination."""
        async with self._session_provider() as session:
            result = await session.execute(
                select(CandidateModel)
                .order_by(CandidateModel.created_at.desc())
                .offset(skip)
                .limit(limit)
            )
            db_models = result.scalars().all()
            return [CandidateMapper.to_domain(db_model) for db_model in db_models]
