"""Index interview questions to vector database use case."""

import logging
from dataclasses import dataclass
from uuid import UUID

from ....domain.ports.interview_repository_port import InterviewRepositoryPort
from ....domain.ports.question_repository_port import QuestionRepositoryPort
from ....domain.ports.vector_search_port import VectorSearchPort

logger = logging.getLogger(__name__)


@dataclass
class IndexQuestionsInput:
    """Input for indexing questions."""

    interview_id: UUID


@dataclass
class IndexQuestionsOutput:
    """Output from indexing questions."""

    indexed_count: int
    errors: list[str]


class IndexQuestionsToVectorUseCase:
    """Index interview questions to vector database."""

    def __init__(
        self,
        vector_search: VectorSearchPort,
        interview_repo: InterviewRepositoryPort,
        question_repo: QuestionRepositoryPort,
    ):
        self.vector_search = vector_search
        self.interview_repo = interview_repo
        self.question_repo = question_repo

    async def execute(self, input_dto: IndexQuestionsInput) -> IndexQuestionsOutput:
        """Index asked questions from a completed interview."""
        errors: list[str] = []
        indexed_count = 0

        try:
            interview_questions = await self.interview_repo.get_interview_questions(
                input_dto.interview_id
            )
            asked_questions = [iq for iq in interview_questions if not iq.skipped]

            for iq in asked_questions:
                try:
                    question = await self.question_repo.get_by_id(iq.question_id)
                    if not question:
                        logger.warning("Question %s not found", iq.question_id)
                        continue

                    await self.vector_search.insert_question(
                        question_id=question.id,
                        text=question.text,
                        question_type=question.question_type,
                        difficulty=question.difficulty,
                        skills=question.skills,
                    )
                    indexed_count += 1
                except Exception as exc:
                    error_msg = f"Failed to index question {iq.question_id}: {exc}"
                    logger.error(error_msg)
                    errors.append(error_msg)

            return IndexQuestionsOutput(indexed_count=indexed_count, errors=errors)

        except Exception as exc:
            error_msg = f"Failed to index questions: {exc}"
            logger.error(error_msg, exc_info=True)
            return IndexQuestionsOutput(indexed_count=indexed_count, errors=[error_msg] + errors)

