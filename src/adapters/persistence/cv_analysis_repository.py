"""PostgreSQL implementation of CVAnalysisRepositoryPort."""

from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.orm import selectinload

from ...domain.models.cv_analysis import CVAnalysis
from ...domain.ports.cv_analysis_repository_port import CVAnalysisRepositoryPort
from .mappers import CVAnalysisMapper, CVSkillMapper
from .models import CVAnalysisModel
from .session_provider import SessionProvider


class PostgreSQLCVAnalysisRepository(CVAnalysisRepositoryPort):
    """PostgreSQL implementation of CV analysis repository.

    This adapter implements the CVAnalysisRepositoryPort interface
    using SQLAlchemy and PostgreSQL for persistence.
    """

    def __init__(self, session_provider: SessionProvider):
        """Initialize repository with session provider."""
        self._session_provider = session_provider

    async def save(self, cv_analysis: CVAnalysis) -> CVAnalysis:
        """Save a new CV analysis to the database.

        Skills are saved as separate entities with relationship to CV analysis.
        """
        async with self._session_provider() as session:
            db_model = CVAnalysisMapper.to_db_model(cv_analysis)
            session.add(db_model)

            for skill in cv_analysis.skills:
                skill_model = CVSkillMapper.to_db_model(skill)
                session.add(skill_model)

            await session.commit()
            await session.refresh(db_model, attribute_names=["skills"])
            return CVAnalysisMapper.to_domain(db_model)

    async def get_by_id(self, cv_analysis_id: UUID) -> CVAnalysis | None:
        """Retrieve a CV analysis by ID with skills loaded."""
        async with self._session_provider() as session:
            result = await session.execute(
                select(CVAnalysisModel)
                .where(CVAnalysisModel.id == cv_analysis_id)
                .where(CVAnalysisModel.deleted_at.is_(None))
                .options(selectinload(CVAnalysisModel.skills))
            )
            db_model = result.scalar_one_or_none()
            return CVAnalysisMapper.to_domain(db_model) if db_model else None

    async def get_by_candidate_id(self, candidate_id: UUID) -> list[CVAnalysis]:
        """Retrieve all CV analyses for a candidate with skills loaded."""
        async with self._session_provider() as session:
            result = await session.execute(
                select(CVAnalysisModel)
                .where(CVAnalysisModel.candidate_id == candidate_id)
                .where(CVAnalysisModel.deleted_at.is_(None))
                .options(selectinload(CVAnalysisModel.skills))
                .order_by(CVAnalysisModel.created_at.desc())
            )
            db_models = result.scalars().all()
            return [CVAnalysisMapper.to_domain(db_model) for db_model in db_models]

    async def get_latest_by_candidate_id(
        self,
        candidate_id: UUID,
    ) -> CVAnalysis | None:
        """Retrieve the most recent CV analysis for a candidate with skills loaded."""
        async with self._session_provider() as session:
            result = await session.execute(
                select(CVAnalysisModel)
                .where(CVAnalysisModel.candidate_id == candidate_id)
                .where(CVAnalysisModel.deleted_at.is_(None))
                .options(selectinload(CVAnalysisModel.skills))
                .order_by(CVAnalysisModel.created_at.desc())
                .limit(1)
            )
            db_model = result.scalar_one_or_none()
            return CVAnalysisMapper.to_domain(db_model) if db_model else None

    async def update(self, cv_analysis: CVAnalysis) -> CVAnalysis:
        """Update an existing CV analysis and its skills.

        Skills are managed by deleting old and adding new to ensure consistency.
        """
        async with self._session_provider() as session:
            result = await session.execute(
                select(CVAnalysisModel)
                .where(CVAnalysisModel.id == cv_analysis.id)
                .options(selectinload(CVAnalysisModel.skills))
            )
            db_model = result.scalar_one_or_none()

            if not db_model:
                raise ValueError(f"CV Analysis with id {cv_analysis.id} not found")

            CVAnalysisMapper.update_db_model(db_model, cv_analysis)

            for skill_model in db_model.skills:
                await session.delete(skill_model)

            for skill in cv_analysis.skills:
                skill_model = CVSkillMapper.to_db_model(skill)
                session.add(skill_model)

            await session.commit()
            await session.refresh(db_model, attribute_names=["skills"])
            return CVAnalysisMapper.to_domain(db_model)

    async def delete(self, cv_analysis_id: UUID) -> bool:
        """Delete a CV analysis by ID."""
        async with self._session_provider() as session:
            result = await session.execute(
                select(CVAnalysisModel).where(CVAnalysisModel.id == cv_analysis_id)
            )
            db_model = result.scalar_one_or_none()

            if not db_model:
                return False

            await session.delete(db_model)
            await session.commit()
            return True

    async def soft_delete_by_candidate_id(self, candidate_id: UUID) -> int:
        """Soft delete all CV analyses for a candidate that are not already deleted."""
        async with self._session_provider() as session:
            stmt = (
                update(CVAnalysisModel)
                .where(CVAnalysisModel.candidate_id == candidate_id)
                .where(CVAnalysisModel.deleted_at.is_(None))
                .values(deleted_at=datetime.utcnow())
            )
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount or 0

    async def hard_delete_old_soft_deleted(self, days: int = 30) -> int:
        """Hard delete CV analyses soft-deleted more than N days ago."""
        async with self._session_provider() as session:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            stmt = delete(CVAnalysisModel).where(
                CVAnalysisModel.deleted_at.is_not(None),
                CVAnalysisModel.deleted_at < cutoff_date,
            )
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount or 0
