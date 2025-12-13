"""Use case for deleting questions."""

from uuid import UUID

from src.application.ports.question_repository_port import QuestionRepositoryPort


class DeleteQuestionUseCase:
    """Hard delete a question."""

    def __init__(self, question_repo: QuestionRepositoryPort):
        self._question_repo = question_repo

    async def execute(self, question_id: UUID) -> bool:
        return await self._question_repo.delete(question_id)

