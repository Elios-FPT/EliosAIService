"""Load CV analysis use case.

Extracted from PlanningWorkflow._load_cv_node.
Loads CV analysis from repository.
"""

import logging
from uuid import UUID

from ...domain.ports.cv_analysis_repository_port import CVAnalysisRepositoryPort
from ..dto.planning.load_cv_analysis_dto import LoadCVAnalysisInput, LoadCVAnalysisOutput

logger = logging.getLogger(__name__)


class LoadCVAnalysisUseCase:
    """Load CV analysis from repository.

    Extracted from PlanningWorkflow._load_cv_node.
    """

    def __init__(self, cv_analysis_repo: CVAnalysisRepositoryPort):
        """Initialize use case with required dependencies.

        Args:
            cv_analysis_repo: CV analysis repository port
        """
        self.cv_analysis_repo = cv_analysis_repo

    async def execute(self, input: LoadCVAnalysisInput) -> LoadCVAnalysisOutput:
        """Load CV analysis by ID.

        Args:
            input: Contains cv_analysis_id

        Returns:
            LoadCVAnalysisOutput with CV analysis data

        Raises:
            ValueError: If CV analysis not found
        """
        cv_analysis = await self.cv_analysis_repo.get_by_id(input.cv_analysis_id)

        if not cv_analysis:
            return LoadCVAnalysisOutput(
                cv_analysis={},
                skills=[],
                errors=[f"CV analysis not found: {input.cv_analysis_id}"],
            )

        # Get skills from CV analysis
        # Note: CVAnalysis.skills is a list of CVSkill objects
        skills = []
        if cv_analysis.skills:
            # Extract skill names from CVSkill objects
            skills = [skill.skill_name for skill in cv_analysis.skills]
        else:
            # Fallback: try to get skills from repository if not in model
            try:
                skill_objects = await self.cv_analysis_repo.get_skills(cv_analysis.id)
                skills = [s.skill_name for s in skill_objects]
            except Exception as exc:
                logger.warning(f"Failed to load skills from repository: {exc}")
                skills = []

        logger.info(f"Loaded CV analysis: {cv_analysis.id} with {len(skills)} skills")
        return LoadCVAnalysisOutput(
            cv_analysis=cv_analysis.model_dump(mode="json"),
            skills=skills,
            errors=[],
        )

