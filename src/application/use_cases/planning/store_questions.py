"""Store questions use case.

Extracted from PlanningWorkflow._store_questions_node.
Stores generated questions in database.
"""

import logging
from typing import Any
from uuid import UUID

from ...domain.models.question import DifficultyLevel, Question, QuestionType
from ...domain.ports.question_repository_port import QuestionRepositoryPort
from ..dto.planning.store_questions_dto import StoreQuestionsInput, StoreQuestionsOutput

logger = logging.getLogger(__name__)


class StoreQuestionsUseCase:
    """Store generated questions in database.

    Extracted from PlanningWorkflow._store_questions_node.
    """

    def __init__(self, question_repo: QuestionRepositoryPort):
        """Initialize use case with required dependencies.

        Args:
            question_repo: Question repository port
        """
        self.question_repo = question_repo

    async def execute(self, input: StoreQuestionsInput) -> StoreQuestionsOutput:
        """Store questions.

        Args:
            input: Contains generated questions, answers, rationales, and specs

        Returns:
            StoreQuestionsOutput with stored question IDs
        """
        if not input.generated_questions:
            # Check if questions were supposed to be generated
            if input.question_specs:
                return StoreQuestionsOutput(
                    stored_question_ids=[],
                    errors=[
                        "No questions generated. Question generation may have failed."
                    ],
                )
            return StoreQuestionsOutput(
                stored_question_ids=[],
                errors=["No questions to store"],
            )

        try:
            # Create Question objects
            question_objects = []
            for i, (q_text, ideal_answer, rationale, spec) in enumerate(
                zip(
                    input.generated_questions,
                    input.generated_answers,
                    input.generated_rationales,
                    input.question_specs,
                )
            ):
                question = Question(
                    text=q_text,
                    question_type=QuestionType.TECHNICAL,
                    difficulty=DifficultyLevel(spec.get("difficulty", "medium")),
                    skills=[spec.get("skill", "")],
                    ideal_answer=ideal_answer,
                    rationale=rationale,
                )
                question_objects.append(question)

            # Save all questions in one atomic transaction
            saved_questions = await self.question_repo.save_batch(question_objects)
            question_ids = [q.id for q in saved_questions]

            logger.info(f"Stored {len(question_ids)} questions in single transaction")
            return StoreQuestionsOutput(
                stored_question_ids=question_ids,
                errors=[],
            )

        except Exception as exc:
            logger.error(f"Failed to store questions: {exc}", exc_info=True)
            return StoreQuestionsOutput(
                stored_question_ids=[],
                errors=[f"store_questions: {str(exc)}"],
            )

