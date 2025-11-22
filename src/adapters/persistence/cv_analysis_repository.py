"""PostgreSQL implementation of CVAnalysisRepositoryPort."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ...domain.models.cv_analysis import CVAnalysis
from ...domain.ports.cv_analysis_repository_port import CVAnalysisRepositoryPort
from .mappers import CVAnalysisMapper, CVSkillMapper
from .models import CVAnalysisModel, CVSkillModel


class PostgreSQLCVAnalysisRepository(CVAnalysisRepositoryPort):
    """PostgreSQL implementation of CV analysis repository.

    This adapter implements the CVAnalysisRepositoryPort interface
    using SQLAlchemy and PostgreSQL for persistence.
    """

    def __init__(self, session: AsyncSession):
        """Initialize repository with database session.

        Args:
            session: Async SQLAlchemy session
        """
        self.session = session

    async def save(self, cv_analysis: CVAnalysis) -> CVAnalysis:
        """Save a new CV analysis to the database.

        Skills are saved as separate entities with relationship to CV analysis.
        """
        # Create CV analysis without skills
        db_model = CVAnalysisMapper.to_db_model(cv_analysis)
        self.session.add(db_model)

        # Save skills separately to maintain relationship
        for skill in cv_analysis.skills:
            skill_model = CVSkillMapper.to_db_model(skill)
            self.session.add(skill_model)

        await self.session.commit()
        await self.session.refresh(db_model, attribute_names=["skills"])
        return CVAnalysisMapper.to_domain(db_model)

    async def get_by_id(self, cv_analysis_id: UUID) -> CVAnalysis | None:
        """Retrieve a CV analysis by ID with skills loaded."""
        result = await self.session.execute(
            select(CVAnalysisModel)
            .where(CVAnalysisModel.id == cv_analysis_id)
            .options(selectinload(CVAnalysisModel.skills))
        )
        db_model = result.scalar_one_or_none()
        return CVAnalysisMapper.to_domain(db_model) if db_model else None

    async def get_by_candidate_id(self, candidate_id: UUID) -> list[CVAnalysis]:
        """Retrieve all CV analyses for a candidate with skills loaded."""
        result = await self.session.execute(
            select(CVAnalysisModel)
            .where(CVAnalysisModel.candidate_id == candidate_id)
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
        result = await self.session.execute(
            select(CVAnalysisModel)
            .where(CVAnalysisModel.candidate_id == candidate_id)
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
        result = await self.session.execute(
            select(CVAnalysisModel)
            .where(CVAnalysisModel.id == cv_analysis.id)
            .options(selectinload(CVAnalysisModel.skills))
        )
        db_model = result.scalar_one_or_none()

        if not db_model:
            raise ValueError(f"CV Analysis with id {cv_analysis.id} not found")

        # Update CV analysis fields
        CVAnalysisMapper.update_db_model(db_model, cv_analysis)

        # Replace skills: delete old, add new (CASCADE handles deletion)
        # Clear existing skills
        for skill_model in db_model.skills:
            await self.session.delete(skill_model)

        # Add new skills from domain model
        for skill in cv_analysis.skills:
            skill_model = CVSkillMapper.to_db_model(skill)
            self.session.add(skill_model)

        await self.session.commit()
        await self.session.refresh(db_model, attribute_names=["skills"])
        return CVAnalysisMapper.to_domain(db_model)

    async def delete(self, cv_analysis_id: UUID) -> bool:
        """Delete a CV analysis by ID."""
        result = await self.session.execute(
            select(CVAnalysisModel).where(CVAnalysisModel.id == cv_analysis_id)
        )
        db_model = result.scalar_one_or_none()

        if not db_model:
            return False

        await self.session.delete(db_model)
        await self.session.commit()
        return True
