"""Calculate question count use case.

Extracted from PlanningWorkflow._calculate_count_node.
Calculates number of questions based on skill diversity.
"""

import logging
from typing import Any

from ...domain.models.cv_analysis import CVAnalysis
from ..dto.planning.calculate_question_count_dto import (
    CalculateQuestionCountInput,
    CalculateQuestionCountOutput,
)

logger = logging.getLogger(__name__)


class CalculateQuestionCountUseCase:
    """Calculate number of questions based on skill diversity.

    Formula: n = min(5, max(2, unique_skills // 3))
    Extracted from PlanningWorkflow._calculate_count_node.
    """

    async def execute(
        self, input: CalculateQuestionCountInput
    ) -> CalculateQuestionCountOutput:
        """Calculate question count.

        Args:
            input: Contains CV analysis or skills count

        Returns:
            CalculateQuestionCountOutput with calculated question count
        """
        if not input.cv_analysis:
            return CalculateQuestionCountOutput(
                question_count=0,
                errors=["CV analysis missing in input"],
            )

        # Reconstruct CVAnalysis from dict if needed
        try:
            if isinstance(input.cv_analysis, dict):
                cv_analysis = CVAnalysis(**input.cv_analysis)
            else:
                cv_analysis = input.cv_analysis

            # Calculate based on skill diversity
            # CVAnalysis.skills is a list of CVSkill objects
            unique_skills = 0
            if hasattr(cv_analysis, "skills") and cv_analysis.skills:
                if isinstance(cv_analysis.skills, list):
                    # Count unique skill names
                    skill_names = set()
                    for skill in cv_analysis.skills:
                        if hasattr(skill, "skill_name"):
                            skill_names.add(skill.skill_name)
                        elif isinstance(skill, str):
                            skill_names.add(skill)
                    unique_skills = len(skill_names)
                else:
                    unique_skills = input.skills_count if input.skills_count > 0 else 0
            else:
                # Fallback to skills_count from input
                unique_skills = input.skills_count

            # Formula: n = min(5, max(2, unique_skills // 3))
            question_count = min(5, max(2, unique_skills // 3))

            logger.info(
                f"Calculated question count: {question_count} (from {unique_skills} skills)"
            )
            return CalculateQuestionCountOutput(
                question_count=question_count,
                errors=[],
            )

        except Exception as exc:
            logger.error(f"Failed to calculate question count: {exc}", exc_info=True)
            return CalculateQuestionCountOutput(
                question_count=0,
                errors=[f"calculate_count: {str(exc)}"],
            )

