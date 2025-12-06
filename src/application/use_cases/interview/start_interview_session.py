"""Start interview session use case.

Extracted from InterviewConversationWorkflow._start_session_node.
Initializes conversation and loads first question.
"""

import logging
from uuid import UUID

from ...domain.models.interview import Interview
from ...domain.ports.interview_repository_port import InterviewRepositoryPort
from ...domain.ports.question_repository_port import QuestionRepositoryPort
from ..dto.interview.start_session_dto import StartSessionInput, StartSessionOutput

logger = logging.getLogger(__name__)


class StartInterviewSessionUseCase:
    """Initialize conversation and load first question.

    Transitions interview to QUESTIONING state and loads first question.
    Extracted from InterviewConversationWorkflow._start_session_node.
    """

    def __init__(
        self,
        interview_repo: InterviewRepositoryPort,
        question_repo: QuestionRepositoryPort,
    ):
        """Initialize use case with required dependencies.

        Args:
            interview_repo: Interview repository port
            question_repo: Question repository port
        """
        self.interview_repo = interview_repo
        self.question_repo = question_repo

    async def execute(self, input: StartSessionInput) -> StartSessionOutput:
        """Execute session start.

        Args:
            input: Start session input data

        Returns:
            StartSessionOutput with first question and initial state

        Raises:
            ValueError: If interview or question not found
        """
        interview_id = input.interview_id

        # Load interview (use cache from input)
        interview, cache_updates = await self._get_or_refresh_interview(
            interview_id, input.cached_interview, force_refresh=False
        )
        if not interview:
            return StartSessionOutput(
                current_question_id="",
                current_question={},
                has_more_questions=False,
                cache_updates={},
                errors=[f"Interview {interview_id} not found"],
                complete=True,
            )

        # Transition to QUESTIONING
        interview.start()
        await self.interview_repo.update(interview)
        # Refresh cache after update (force refresh to get latest version)
        _, cache_updates = await self._get_or_refresh_interview(
            interview_id, None, force_refresh=True
        )

        # Get first question
        current_iq = await self.interview_repo.get_current_question(interview_id)
        if not current_iq:
            return StartSessionOutput(
                current_question_id="",
                current_question={},
                has_more_questions=False,
                cache_updates=cache_updates,
                errors=["No questions in interview"],
                complete=True,
            )

        question = await self.question_repo.get_by_id(current_iq.question_id)
        if not question:
            return StartSessionOutput(
                current_question_id="",
                current_question={},
                has_more_questions=False,
                cache_updates=cache_updates,
                errors=[f"Question {current_iq.question_id} not found"],
                complete=True,
            )

        # Check if more questions exist
        total_questions = await self.interview_repo.count_interview_questions(interview_id)
        has_more = interview.current_question_index < total_questions - 1

        logger.info(
            f"Session started for interview {interview_id}, first question: {question.id}",
            extra={"interview_id": str(interview_id), "question_id": str(question.id)},
        )

        return StartSessionOutput(
            current_question_id=str(question.id),
            current_question={
                **question.model_dump(mode="json"),
                "index": interview.current_question_index,  # WebSocket compatibility
                "total": total_questions,  # WebSocket compatibility
            },
            has_more_questions=has_more,
            cache_updates=cache_updates,
            errors=[],
            complete=False,
        )

    async def _get_or_refresh_interview(
        self,
        interview_id: UUID,
        cached_interview: dict | None,
        force_refresh: bool = False,
    ) -> tuple[Interview | None, dict]:
        """Get interview from cache or refresh from DB.

        Performance optimization: Caches interview entity to eliminate redundant DB queries.

        Args:
            interview_id: Interview UUID
            cached_interview: Cached interview dict from state (if available)
            force_refresh: If True, always fetch from DB

        Returns:
            Tuple of (Interview domain object, state updates dict)
            State updates include cached interview and version for checkpointing
        """
        # Check if cache is valid
        if not force_refresh and cached_interview:
            try:
                # Reconstruct Interview from cached dict
                interview = Interview(**cached_interview)
                return interview, {}
            except Exception as exc:
                logger.warning(f"Failed to reconstruct cached interview: {exc}, refreshing from DB")
                # Fall through to refresh

        # Fetch from DB
        interview = await self.interview_repo.get_by_id(interview_id)
        if not interview:
            return None, {}

        # Cache in state (will be checkpointed)
        state_updates = {
            "_cached_interview": interview.model_dump(mode="json"),
            "_interview_version": interview.updated_at.timestamp() if interview.updated_at else None,
        }

        return interview, state_updates

