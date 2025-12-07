"""Prepare question specifications use case.

Extracted from PlanningWorkflow._prepare_specs_node (lines 302-369).
"""

import logging
from typing import Any

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
                exemplars = await self._search_exemplars(skill_name)

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
        proficiency_value = proficiency if proficiency else "intermediate"
        return difficulty_map.get(proficiency_value, "medium")

    async def _search_exemplars(self, skill_name: str) -> list[dict[str, Any]]:
        """Search for exemplar questions via vector search.

        Args:
            skill_name: Skill to search for

        Returns:
            List of exemplar question dictionaries
        """
        try:
            # Generate embedding for the query
            query_text = f"{skill_name} technical interview question"
            query_embedding = await self.vector_search.get_embedding(query_text)

            # Search for similar questions
            search_results = await self.vector_search.find_similar_questions(
                query_embedding=query_embedding,
                top_k=3,
                filters={"skill": skill_name}
            )

            exemplars = [
                {"text": r.get("text"), "difficulty": r.get("difficulty")}
                for r in search_results
            ]
            return exemplars

        except Exception as ve:
            logger.warning(f"Exemplar search failed for {skill_name}: {ve}")
            # Continue without exemplars
            return []
