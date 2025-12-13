"""Use case for listing questions with filters."""

from src.application.dto.question_dto import QuestionListResponse, QuestionResponse
from src.application.ports.question_repository_port import QuestionRepositoryPort
from src.domain.models.question import Difficulty, QuestionType


class ListQuestionsUseCase:
    """List questions with pagination and filters."""

    def __init__(self, question_repo: QuestionRepositoryPort):
        self._question_repo = question_repo

    async def execute(
        self,
        question_type: QuestionType | None,
        difficulty: Difficulty | None,
        skill: str | None,
        limit: int,
        offset: int,
    ) -> QuestionListResponse:
        items = await self._question_repo.list_filtered(
            question_type=question_type,
            difficulty=difficulty,
            skill=skill,
            limit=limit,
            offset=offset,
        )
        total = await self._question_repo.count_filtered(
            question_type=question_type,
            difficulty=difficulty,
            skill=skill,
        )
        return QuestionListResponse(
            items=[QuestionResponse.from_domain(q) for q in items],
            total=total,
            limit=limit,
            offset=offset,
        )

