"""Generate questions batch use case.

Extracted from PlanningWorkflow._generate_batch_node (lines 371-422).
"""

import logging
from typing import Any

from ....domain.ports.llm_port import LLMPort
from ...dto.planning.generate_questions_batch_dto import (
    GenerateQuestionsBatchInput,
    GenerateQuestionsBatchOutput,
)

logger = logging.getLogger(__name__)


class GenerateQuestionsBatchUseCase:
    """Generate questions with ideal answers and rationales in parallel.

    Uses unified LLM method to ensure question, ideal_answer, and rationale
    are generated together in one call per spec for consistency.
    Maintains parallel generation capability via batch method.
    """

    def __init__(self, llm: LLMPort):
        """Initialize with required port.

        Args:
            llm: LLM port for question generation
        """
        self.llm = llm

    async def execute(
        self, input_dto: GenerateQuestionsBatchInput
    ) -> GenerateQuestionsBatchOutput:
        """Generate complete question sets (question, answer, rationale) in parallel.

        Args:
            input_dto: Contains question specs and CV context

        Returns:
            GenerateQuestionsBatchOutput with generated content
        """
        try:
            specs = input_dto.question_specs
            cv_analysis = input_dto.cv_analysis

            if not specs or not cv_analysis:
                return GenerateQuestionsBatchOutput(
                    generated_questions=[],
                    generated_answers=[],
                    generated_rationales=[],
                    errors=["Missing question specs or CV analysis"]
                )

            # Prepare context for LLM
            context = self._build_context(cv_analysis)

            # Generate complete question sets in parallel
            logger.info(
                f"Generating {len(specs)} complete question sets "
                f"(question, answer, rationale) in parallel..."
            )

            question_sets = await self.llm.generate_questions_with_answers_and_rationales_batch(
                specs, context
            )

            # Unpack tuples into separate lists
            questions = []
            answers = []
            rationales = []
            for question_text, ideal_answer, rationale in question_sets:
                questions.append(question_text)
                answers.append(ideal_answer)
                rationales.append(rationale)

            logger.info(f"Successfully generated {len(questions)} complete question sets")

            return GenerateQuestionsBatchOutput(
                generated_questions=questions,
                generated_answers=answers,
                generated_rationales=rationales,
                errors=[]
            )

        except Exception as e:
            logger.error(f"Failed to generate questions batch: {e}", exc_info=True)
            return GenerateQuestionsBatchOutput(
                generated_questions=[],
                generated_answers=[],
                generated_rationales=[],
                errors=[f"Failed to generate questions batch: {str(e)}"]
            )

    def _build_context(self, cv_analysis: dict[str, Any]) -> dict[str, Any]:
        """Build LLM context from CV analysis.

        Args:
            cv_analysis: CV analysis dictionary

        Returns:
            Context dictionary for LLM
        """
        return {
            "cv_summary": cv_analysis.get("summary", ""),
            "covered_topics": [],
            "stage": "planning"
        }
