"""Store questions use case.

Extracted from PlanningWorkflow._store_questions_node (lines 424-475).
"""

import logging

from ....domain.models.question import DifficultyLevel, Question, QuestionType
from ....application.ports.question_repository_port import QuestionRepositoryPort
from ...dto.planning.store_questions_dto import (
    StoreQuestionsInput,
    StoreQuestionsOutput,
)

logger = logging.getLogger(__name__)


class StoreQuestionsUseCase:
    """Store generated questions in database.

    Creates Question entities with ideal answers and rationales,
    then saves them in a single atomic transaction.
    """

    def __init__(self, question_repo: QuestionRepositoryPort):
        """Initialize with required port.

        Args:
            question_repo: Question repository port
        """
        self.question_repo = question_repo

    async def execute(self, input_dto: StoreQuestionsInput) -> StoreQuestionsOutput:
        """Store generated questions in database.

        Args:
            input_dto: Contains generated questions, answers, rationales, and specs

        Returns:
            StoreQuestionsOutput with stored question IDs
        """
        try:
            questions = input_dto.generated_questions
            answers = input_dto.generated_answers
            rationales = input_dto.generated_rationales
            specs = input_dto.question_specs

            if not questions:
                return StoreQuestionsOutput(
                    stored_question_ids=[],
                    errors=["No questions to store"]
                )

            # Create Question objects
            question_objects = []
            for q_text, ideal_answer, rationale, spec in zip(
                questions, answers, rationales, specs, strict=True
            ):
                question = Question(
                    text=q_text,
                    question_type=QuestionType.TECHNICAL,
                    difficulty=DifficultyLevel(spec["difficulty"]),
                    skills=[spec["skill"]],
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
                errors=[]
            )

        except Exception as e:
            logger.error(f"Failed to store questions: {e}", exc_info=True)
            return StoreQuestionsOutput(
                stored_question_ids=[],
                errors=[f"Failed to store questions: {str(e)}"]
            )
