"""Load next question use case.

Extracted from InterviewConversationWorkflow._next_question_or_complete_node.
Loads next question or marks interview for completion.
"""

import logging
from uuid import UUID

from ...domain.models.interview import Interview
from ...domain.ports.interview_repository_port import InterviewRepositoryPort
from ...domain.ports.question_repository_port import QuestionRepositoryPort
from ..dto.interview.load_next_question_dto import LoadNextQuestionInput, LoadNextQuestionOutput

logger = logging.getLogger(__name__)


class LoadNextQuestionUseCase:
    """Load next question or mark for completion.

    Transitions interview state and loads next main question if available.
    Extracted from InterviewConversationWorkflow._next_question_or_complete_node.
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

    async def execute(self, input: LoadNextQuestionInput) -> LoadNextQuestionOutput:
        """Execute next question loading.

        Args:
            input: Load next question input data

        Returns:
            LoadNextQuestionOutput with next question or completion flag
        """
        interview_id = input.interview_id

        # Check if more questions exist
        if not input.has_more_questions:
            logger.info(f"No more questions, completing interview {interview_id}")
            return LoadNextQuestionOutput(
                complete=True,
                current_question_id=None,
                current_question=None,
                parent_question_id=None,
                parent_question=None,
                followup_count=0,
                cumulative_gaps=[],
                has_more_questions=False,
                cache_updates={},
                errors=[],
            )

        # Transition interview state (QUESTIONING) - use cache
        interview, cache_updates = await self._get_or_refresh_interview(
            interview_id, input.cached_interview, force_refresh=False
        )
        if not interview:
            return LoadNextQuestionOutput(
                complete=True,
                current_question_id=None,
                current_question=None,
                parent_question_id=None,
                parent_question=None,
                followup_count=0,
                cumulative_gaps=[],
                has_more_questions=False,
                cache_updates={},
                errors=[f"Interview {interview_id} not found"],
            )

        interview.proceed_to_next_question()
        await self.interview_repo.update(interview)
        # Refresh cache after update
        _, cache_updates = await self._get_or_refresh_interview(
            interview_id, None, force_refresh=True
        )

        # Get next question
        current_iq = await self.interview_repo.get_current_question(interview_id)
        if not current_iq:
            logger.info(f"No more questions (after proceed), completing interview")
            return LoadNextQuestionOutput(
                complete=True,
                current_question_id=None,
                current_question=None,
                parent_question_id=None,
                parent_question=None,
                followup_count=0,
                cumulative_gaps=[],
                has_more_questions=False,
                cache_updates=cache_updates,
                errors=[],
            )

        question = await self.question_repo.get_by_id(current_iq.question_id)
        if not question:
            return LoadNextQuestionOutput(
                complete=True,
                current_question_id=None,
                current_question=None,
                parent_question_id=None,
                parent_question=None,
                followup_count=0,
                cumulative_gaps=[],
                has_more_questions=False,
                cache_updates=cache_updates,
                errors=[f"Question {current_iq.question_id} not found"],
            )

        # Update has_more_questions
        total = await self.interview_repo.count_interview_questions(interview_id)
        has_more = interview.current_question_index < total - 1

        logger.info(
            f"Next question loaded: {question.id} (index {interview.current_question_index})",
            extra={"question_id": str(question.id), "has_more": has_more},
        )

        return LoadNextQuestionOutput(
            complete=False,
            current_question_id=str(question.id),
            current_question={
                **question.model_dump(mode="json"),  # All question fields
                "index": interview.current_question_index,  # WebSocket compatibility
                "total": total,  # WebSocket compatibility
            },
            parent_question_id=None,  # Reset (new main question)
            parent_question=None,
            followup_count=0,  # Reset counter
            cumulative_gaps=[],  # Reset gaps
            has_more_questions=has_more,
            cache_updates=cache_updates,
            errors=[],
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

