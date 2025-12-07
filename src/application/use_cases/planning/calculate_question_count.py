"""Calculate question count use case.

Extracted from PlanningWorkflow._calculate_count_node (lines 274-300).
"""

import logging

from ...dto.planning.calculate_question_count_dto import (
    CalculateQuestionCountInput,
    CalculateQuestionCountOutput,
)

logger = logging.getLogger(__name__)


class CalculateQuestionCountUseCase:
    """Calculate number of questions based on skill diversity.

    Formula: n = min(5, max(2, unique_skills // 3))
    Ensures at least 2 questions and at most 5 questions.
    """

    async def execute(
        self, input_dto: CalculateQuestionCountInput
    ) -> CalculateQuestionCountOutput:
        """Calculate question count from skill diversity.

        Args:
            input_dto: Contains skill count or CV analysis

        Returns:
            CalculateQuestionCountOutput with calculated count
        """
        try:
            # Use skills_count if provided, otherwise extract from cv_analysis
            if input_dto.skills_count > 0:
                unique_skills = input_dto.skills_count
            elif input_dto.cv_analysis:
                skills = input_dto.cv_analysis.get("skills", [])
                unique_skills = len(skills)
            else:
                return CalculateQuestionCountOutput(
                    question_count=0,
                    errors=["CV analysis missing or no skills count provided"]
                )

            # Apply formula: min(5, max(2, unique_skills // 3))
            question_count = min(5, max(2, unique_skills // 3))

            logger.info(
                f"Calculated question count: {question_count} "
                f"(from {unique_skills} skills)"
            )

            return CalculateQuestionCountOutput(
                question_count=question_count,
                errors=[]
            )

        except Exception as e:
            logger.error(f"Failed to calculate question count: {e}", exc_info=True)
            return CalculateQuestionCountOutput(
                question_count=0,
                errors=[f"Failed to calculate question count: {str(e)}"]
            )
