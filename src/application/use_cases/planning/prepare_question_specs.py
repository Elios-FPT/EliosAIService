"""Prepare question specifications use case.

Extracted from PlanningWorkflow._prepare_specs_node (lines 302-369).
"""

import logging
from typing import Any

from ....domain.models.exemplar_models import ExemplarFilters
from ....domain.models.question import Difficulty
from ....domain.ports.vector_search_port import VectorSearchPort
from ...dto.planning.prepare_question_specs_dto import (
    PrepareQuestionSpecsInput,
    PrepareQuestionSpecsOutput,
    QuestionSpec,
)

logger = logging.getLogger(__name__)


class PrepareQuestionSpecsUseCase:
    """Prepare question specifications with exemplar search.

    Rotates through CV skills and searches for exemplar questions via vector search.
    Maps proficiency levels to difficulty (beginner→easy, expert→hard, etc.).
    """

    def __init__(self, vector_search: VectorSearchPort):
        """Initialize with required port.

        Args:
            vector_search: Vector search port for exemplar retrieval
        """
        self.vector_search = vector_search

    async def execute(
        self, input_dto: PrepareQuestionSpecsInput
    ) -> PrepareQuestionSpecsOutput:
        """Prepare question specifications with exemplar search.

        Args:
            input_dto: Contains CV analysis and question count

        Returns:
            PrepareQuestionSpecsOutput with prepared specs
        """
        try:
            cv_analysis = input_dto.cv_analysis
            question_count = input_dto.question_count

            if not cv_analysis or question_count == 0:
                return PrepareQuestionSpecsOutput(
                    question_specs=[],
                    errors=["Missing CV analysis or question count"]
                )

            # Extract skills from CV analysis
            skills_data = cv_analysis.get("skills", [])
            if not skills_data:
                return PrepareQuestionSpecsOutput(
                    question_specs=[],
                    errors=["No skills found in CV analysis"]
                )

            # Use CV summary as search query
            cv_summary = cv_analysis.get("summary", "")
            if not cv_summary:
                cv_summary = "software developer technical interview"

            # Build question specs
            specs = []
            for i in range(question_count):
                # Rotate through skills
                skill_dict = skills_data[i % len(skills_data)]
                skill_name = skill_dict.get("skill_name", "")

                # Determine difficulty based on proficiency
                difficulty = self._map_proficiency_to_difficulty(
                    skill_dict.get("proficiency_level")
                )

                # Search for exemplar questions
                exemplars = await self._search_exemplars(
                    cv_summary=cv_summary,
                    skill_name=skill_name,
                    difficulty=difficulty,
                )

                specs.append(
                    QuestionSpec(
                        skill=skill_name,
                        difficulty=difficulty,
                        exemplars=exemplars
                    )
                )

            logger.info(f"Prepared {len(specs)} question specs")
            return PrepareQuestionSpecsOutput(
                question_specs=specs,
                errors=[]
            )

        except Exception as e:
            logger.error(f"Failed to prepare question specs: {e}", exc_info=True)
            return PrepareQuestionSpecsOutput(
                question_specs=[],
                errors=[f"Failed to prepare question specs: {str(e)}"]
            )

    def _map_proficiency_to_difficulty(self, proficiency: str | None) -> str:
        """Map proficiency level to difficulty.

        Args:
            proficiency: Proficiency level string

        Returns:
            Difficulty string (easy, medium, hard)
        """
        difficulty_map = {
            "beginner": "easy",
            "intermediate": "medium",
            "advanced": "hard",
            "expert": "hard",
        }
        proficiency_value = proficiency.lower() if proficiency else "intermediate"
        return difficulty_map.get(proficiency_value, "medium")

    async def _search_exemplars(
        self,
        cv_summary: str,
        skill_name: str,
        difficulty: str,
    ) -> list[dict[str, Any]]:
        """Search for exemplar questions via vector search."""
        try:
            filters = ExemplarFilters(
                difficulty=Difficulty(difficulty) if difficulty else None,
                skills=[skill_name] if skill_name else None,
            )

            results = await self.vector_search.search_exemplars(
                cv_summary=cv_summary,
                filters=filters,
                top_k=3,
            )

            return [
                {
                    "text": r.text,
                    "difficulty": r.difficulty.value,
                    "similarity_score": r.similarity_score,
                }
                for r in results
            ]

        except Exception as ve:
            logger.warning(f"Exemplar search failed for {skill_name}: {ve}")
            return []
