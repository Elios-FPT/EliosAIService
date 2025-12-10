"""Start interview session use case.

Extracted from InterviewConversationWorkflow._start_session_node (lines 276-347).
"""

import logging
from typing import Any
from uuid import UUID

from ....domain.models.interview import Interview
from ....application.ports.interview_repository_port import InterviewRepositoryPort
from ....application.ports.question_repository_port import QuestionRepositoryPort
from ...dto.interview.start_session_dto import StartSessionInput, StartSessionOutput

logger = logging.getLogger(__name__)


class StartInterviewSessionUseCase:
    """Initialize interview conversation and load first question.

    Transitions interview to QUESTIONING state and loads first question.
    Follows CompleteInterviewUseCase pattern with constructor injection.
    """

    def __init__(
        self,
        interview_repo: InterviewRepositoryPort,
        question_repo: QuestionRepositoryPort,
    ):
        """Initialize with required ports.

        Args:
            interview_repo: Interview persistence port
            question_repo: Question persistence port
        """
        self.interview_repo = interview_repo
        self.question_repo = question_repo

    async def execute(self, input_dto: StartSessionInput) -> StartSessionOutput:
        """Start interview session and load first question.

        Args:
            input_dto: Contains interview_id, candidate_id, and optional cached_interview

        Returns:
            StartSessionOutput with first question and metadata

        Raises:
            ValueError: If interview not found or no questions available
        """
        try:
            # Load interview (use cache if provided)
            interview, cache_updates = await self._get_or_refresh_interview(
                interview_id=input_dto.interview_id,
                cached_interview=input_dto.cached_interview,
                force_refresh=False,
            )

            if not interview:
                logger.error(f"Interview {input_dto.interview_id} not found")
                return StartSessionOutput(
                    current_question_id="",
                    current_question={},
                    has_more_questions=False,
                    errors=[f"Interview {input_dto.interview_id} not found"],
                    complete=True,
                )

            # Transition to QUESTIONING
            interview.start()
            await self.interview_repo.update(interview)

            # Refresh cache after update
            _, cache_updates = await self._get_or_refresh_interview(
                interview_id=input_dto.interview_id,
                cached_interview=None,
                force_refresh=True,
            )

            # Get first question
            current_iq = await self.interview_repo.get_current_question(input_dto.interview_id)
            if not current_iq:
                logger.error(f"No questions in interview {input_dto.interview_id}")
                return StartSessionOutput(
                    current_question_id="",
                    current_question={},
                    has_more_questions=False,
                    errors=["No questions in interview"],
                    complete=True,
                )

            question = await self.question_repo.get_by_id(current_iq.question_id)
            if not question:
                logger.error(f"Question {current_iq.question_id} not found")
                return StartSessionOutput(
                    current_question_id="",
                    current_question={},
                    has_more_questions=False,
                    errors=[f"Question {current_iq.question_id} not found"],
                    complete=True,
                )

            # Check if more questions exist
            total_questions = await self.interview_repo.count_interview_questions(
                input_dto.interview_id
            )
            has_more = interview.current_question_index < total_questions - 1

            logger.info(
                f"Session started for interview {input_dto.interview_id}, "
                f"first question: {question.id}",
                extra={
                    "interview_id": str(input_dto.interview_id),
                    "question_id": str(question.id),
                },
            )

            return StartSessionOutput(
                current_question_id=str(question.id),
                current_question={
                    **question.model_dump(mode="json"),
                    "index": interview.current_question_index,
                    "total": total_questions,
                },
                has_more_questions=has_more,
                cache_updates=cache_updates,
            )

        except Exception as exc:
            logger.error(f"start_interview_session failed: {exc}", exc_info=True)
            return StartSessionOutput(
                current_question_id="",
                current_question={},
                has_more_questions=False,
                errors=[f"start_session: {str(exc)}"],
                complete=True,
            )

    async def _get_or_refresh_interview(
        self,
        interview_id: UUID,
        cached_interview: dict[str, Any] | None,
        force_refresh: bool = False,
    ) -> tuple[Interview | None, dict[str, Any]]:
        """Get interview from cache or refresh from DB.

        Args:
            interview_id: Interview UUID
            cached_interview: Optional cached interview dict
            force_refresh: If True, always fetch from DB

        Returns:
            Tuple of (Interview entity, cache_updates dict)
        """
        # Check if cache is valid
        if not force_refresh and cached_interview:
            try:
                interview = Interview(**cached_interview)
                return interview, {}
            except Exception as exc:
                logger.warning(f"Failed to reconstruct cached interview: {exc}")

        # Fetch from DB
        interview = await self.interview_repo.get_by_id(interview_id)
        if not interview:
            return None, {}

        # Cache in state
        cache_updates = {
            "_cached_interview": interview.model_dump(mode="json"),
            "_interview_version": (
                interview.updated_at.timestamp() if interview.updated_at else None
            ),
        }

        return interview, cache_updates
