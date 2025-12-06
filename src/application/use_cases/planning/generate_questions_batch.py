"""Generate questions batch use case.

Extracted from PlanningWorkflow._generate_batch_node.
Generates questions with ideal answers and rationales in parallel.
"""

import logging
from typing import Any

from ...domain.models.cv_analysis import CVAnalysis
from ...domain.ports.llm_port import LLMPort
from ..dto.planning.generate_questions_batch_dto import (
    GenerateQuestionsBatchInput,
    GenerateQuestionsBatchOutput,
)

logger = logging.getLogger(__name__)


class GenerateQuestionsBatchUseCase:
    """Generate questions with ideal answers and rationales in a single LLM call per spec.

    Uses unified LLM method to ensure question, ideal_answer, and rationale are generated
    together in one call for consistency.
    Extracted from PlanningWorkflow._generate_batch_node.
    """

    def __init__(self, llm: LLMPort):
        """Initialize use case with required dependencies.

        Args:
            llm: LLM port for question generation
        """
        self.llm = llm

    async def execute(
        self, input: GenerateQuestionsBatchInput
    ) -> GenerateQuestionsBatchOutput:
        """Generate questions batch.

        Args:
            input: Contains question specs and CV analysis

        Returns:
            GenerateQuestionsBatchOutput with generated questions, answers, and rationales
        """
        if not input.question_specs or not input.cv_analysis:
            return GenerateQuestionsBatchOutput(
                generated_questions=[],
                generated_answers=[],
                generated_rationales=[],
                errors=["Missing question specs or CV analysis"],
            )

        try:
            # Reconstruct CVAnalysis from dict if needed
            if isinstance(input.cv_analysis, dict):
                cv_analysis = CVAnalysis(**input.cv_analysis)
            else:
                cv_analysis = input.cv_analysis

            # Prepare context
            context = {
                "cv_summary": cv_analysis.summary,
                "covered_topics": [],
                "stage": "planning",
            }

            # Convert QuestionSpec DTOs to dicts for LLM call
            specs_dicts = []
            for spec in input.question_specs:
                if isinstance(spec, dict):
                    specs_dicts.append(spec)
                else:
                    # Convert QuestionSpec DTO to dict
                    specs_dicts.append(spec.model_dump())

            # Generate complete question sets (question, ideal_answer, rationale) in parallel
            # Each spec generates all three components in a single LLM call
            logger.info(
                f"Generating {len(specs_dicts)} complete question sets (question, answer, rationale) in parallel..."
            )
            question_sets = await self.llm.generate_questions_with_answers_and_rationales_batch(
                specs_dicts, context
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
                errors=[],
            )

        except Exception as exc:
            logger.error(f"Failed to generate questions batch: {exc}", exc_info=True)
            return GenerateQuestionsBatchOutput(
                generated_questions=[],
                generated_answers=[],
                generated_rationales=[],
                errors=[f"generate_batch: {str(exc)}"],
            )

