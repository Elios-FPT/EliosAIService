"""Use case for creating questions."""

from datetime import datetime
from uuid import UUID

from src.application.dto.question_dto import CreateQuestionRequest
from src.application.ports.question_repository_port import QuestionRepositoryPort
from src.domain.models.question import Question


class CreateQuestionUseCase:
    """Create a new question."""

    def __init__(self, question_repo: QuestionRepositoryPort):
        self._question_repo = question_repo

    async def execute(self, request: CreateQuestionRequest) -> Question:
        """Create and persist a question."""
        now = datetime.utcnow()
        question = Question(
            text=request.text,
            question_type=request.question_type,
            difficulty=request.difficulty,
            skills=request.skills,
            ideal_answer=request.ideal_answer,
            rationale=request.rationale,
            created_at=now,
            updated_at=now,
        )
        return await self._question_repo.save(question)

