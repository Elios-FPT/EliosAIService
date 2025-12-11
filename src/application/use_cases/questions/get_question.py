"""Use case for retrieving a question by id."""

from uuid import UUID

from src.application.ports.question_repository_port import QuestionRepositoryPort
from src.domain.models.question import Question


class GetQuestionUseCase:
    """Fetch question by identifier."""

    def __init__(self, question_repo: QuestionRepositoryPort):
        self._question_repo = question_repo

    async def execute(self, question_id: UUID) -> Question | None:
        return await self._question_repo.get_by_id(question_id)

