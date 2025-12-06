"""Prepare question specs use case.

Extracted from PlanningWorkflow._prepare_specs_node.
Prepares question specifications with exemplar search.
"""

import logging
from typing import Any

from ...domain.models.cv_analysis import CVAnalysis
from ...domain.ports.vector_search_port import VectorSearchPort
from ..dto.planning.prepare_question_specs_dto import (
    PrepareQuestionSpecsInput,
    PrepareQuestionSpecsOutput,
    QuestionSpec,
)

logger = logging.getLogger(__name__)


class PrepareQuestionSpecsUseCase:
    """Prepare question specifications with exemplar search.

    Extracted from PlanningWorkflow._prepare_specs_node.
    """

    def __init__(self, vector_search: VectorSearchPort):
        """Initialize use case with required dependencies.

        Args:
            vector_search: Vector search port for exemplar retrieval
        """
        self.vector_search = vector_search

    async def execute(
        self, input: PrepareQuestionSpecsInput
    ) -> PrepareQuestionSpecsOutput:
        """Prepare question specifications.

        Args:
            input: Contains CV analysis and question count

        Returns:
            PrepareQuestionSpecsOutput with question specifications
        """
        if not input.cv_analysis or input.question_count == 0:
            return PrepareQuestionSpecsOutput(
                question_specs=[],
                errors=["Missing CV analysis or question count"],
            )

        try:
            # Reconstruct CVAnalysis from dict if needed
            if isinstance(input.cv_analysis, dict):
                cv_analysis = CVAnalysis(**input.cv_analysis)
            else:
                cv_analysis = input.cv_analysis

            # Build question specs
            specs = []
            skills = cv_analysis.skills

            if not skills:
                return PrepareQuestionSpecsOutput(
                    question_specs=[],
                    errors=["No skills found in CV analysis"],
                )

            for i in range(input.question_count):
                # Rotate through skills
                skill_obj = skills[i % len(skills)]
                skill_name = skill_obj.skill_name  # CVSkill uses 'skill_name'

                # Determine difficulty based on proficiency
                difficulty_map = {
                    "beginner": "easy",
                    "intermediate": "medium",
                    "advanced": "hard",
                    "expert": "hard",
                }
                proficiency_value = (
                    skill_obj.proficiency_level.value
                    if skill_obj.proficiency_level
                    else "intermediate"
                )
                difficulty = difficulty_map.get(proficiency_value, "medium")

                # Search for exemplar questions (if vector search available)
                exemplars = []
                try:
                    # Vector search for similar questions
                    search_results = await self.vector_search.search(
                        query_text=f"{skill_name} technical interview question",
                        top_k=3,
                        filter_metadata={"skill": skill_name},
                    )
                    exemplars = [
                        {"text": r.get("text"), "difficulty": r.get("difficulty")}
                        for r in search_results
                    ]
                except Exception as ve:
                    logger.warning(f"Exemplar search failed for {skill_name}: {ve}")
                    # Continue without exemplars

                specs.append(
                    QuestionSpec(
                        skill=skill_name,
                        difficulty=difficulty,
                        exemplars=exemplars,
                    )
                )

            logger.info(f"Prepared {len(specs)} question specs")
            return PrepareQuestionSpecsOutput(
                question_specs=specs,
                errors=[],
            )

        except Exception as exc:
            logger.error(f"Failed to prepare question specs: {exc}", exc_info=True)
            return PrepareQuestionSpecsOutput(
                question_specs=[],
                errors=[f"prepare_specs: {str(exc)}"],
            )

