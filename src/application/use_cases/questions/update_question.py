"""Use case for updating questions (full or partial)."""

from datetime import datetime
from uuid import UUID

from src.application.dto.question_dto import UpdateQuestionRequest
from src.application.ports.question_repository_port import QuestionRepositoryPort
from src.domain.models.question import Question


class UpdateQuestionUseCase:
    """Update existing questions."""

    def __init__(self, question_repo: QuestionRepositoryPort):
        self._question_repo = question_repo

    async def execute(
        self,
        question_id: UUID,
        request: UpdateQuestionRequest,
    ) -> Question | None:
        existing = await self._question_repo.get_by_id(question_id)
        if not existing:
            return None

        updated = existing.copy()

        if request.text is not None:
            updated.text = request.text
        if request.question_type is not None:
            updated.question_type = request.question_type
        if request.difficulty is not None:
            updated.difficulty = request.difficulty
        if request.skills is not None:
            updated.skills = request.skills
        if request.ideal_answer is not None:
            updated.ideal_answer = request.ideal_answer
        if request.rationale is not None:
            updated.rationale = request.rationale

        updated.updated_at = datetime.utcnow()
        return await self._question_repo.update(updated)

