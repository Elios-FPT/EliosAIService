"""Get next question use case."""

from uuid import UUID

from ...domain.models.question import Question
from ...domain.ports.interview_repository_port import InterviewRepositoryPort
from ...domain.ports.question_repository_port import QuestionRepositoryPort


class GetNextQuestionUseCase:
    """Get next question in interview sequence."""

    def __init__(
        self,
        interview_repository: InterviewRepositoryPort,
        question_repository: QuestionRepositoryPort,
    ):
        self.interview_repo = interview_repository
        self.question_repo = question_repository

    async def execute(self, interview_id: UUID) -> Question | None:
        """Get next unanswered question using junction table.

        Args:
            interview_id: The interview UUID

        Returns:
            Next question or None if interview complete

        Raises:
            ValueError: If interview not found
        """
        # Get interview
        interview = await self.interview_repo.get_by_id(interview_id)
        if not interview:
            raise ValueError(f"Interview {interview_id} not found")

        # Get current question from junction table using new repository method
        interview_question = await self.interview_repo.get_current_question(interview_id)
        if not interview_question:
            # No more questions or interview complete
            return None

        # Get the actual Question entity
        question = await self.question_repo.get_by_id(interview_question.question_id)

        # Mark question as asked if not already marked
        if not interview_question.asked_at:
            from datetime import datetime
            await self.interview_repo.mark_question_asked(
                interview_question_id=interview_question.id,
                asked_at=datetime.utcnow(),
            )

        return question
