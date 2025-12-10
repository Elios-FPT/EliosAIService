"""Load CV analysis use case.

Extracted from PlanningWorkflow._load_cv_node (lines 249-272).
"""

import logging

from ....application.ports.cv_analysis_repository_port import CVAnalysisRepositoryPort
from ...dto.planning.load_cv_analysis_dto import LoadCVAnalysisInput, LoadCVAnalysisOutput

logger = logging.getLogger(__name__)


class LoadCVAnalysisUseCase:
    """Load CV analysis from repository.

    Retrieves CV analysis entity and extracts skill names for downstream processing.
    """

    def __init__(self, cv_repo: CVAnalysisRepositoryPort):
        """Initialize with required port.

        Args:
            cv_repo: CV analysis repository port
        """
        self.cv_repo = cv_repo

    async def execute(self, input_dto: LoadCVAnalysisInput) -> LoadCVAnalysisOutput:
        """Load CV analysis from repository.

        Args:
            input_dto: Contains CV analysis ID to load

        Returns:
            LoadCVAnalysisOutput with CV analysis data and extracted skills
        """
        try:
            cv_analysis = await self.cv_repo.get_by_id(input_dto.cv_analysis_id)

            if not cv_analysis:
                return LoadCVAnalysisOutput(
                    cv_analysis={},
                    skills=[],
                    errors=[f"CV analysis not found: {input_dto.cv_analysis_id}"]
                )

            logger.info(f"Loaded CV analysis: {cv_analysis.id}")

            # Extract skill names from CVSkill objects
            skills = [skill.skill_name for skill in cv_analysis.skills]

            return LoadCVAnalysisOutput(
                cv_analysis=cv_analysis.model_dump(mode="json"),
                skills=skills,
                errors=[]
            )

        except Exception as e:
            logger.error(f"Failed to load CV analysis: {e}", exc_info=True)
            return LoadCVAnalysisOutput(
                cv_analysis={},
                skills=[],
                errors=[f"Failed to load CV analysis: {str(e)}"]
            )
