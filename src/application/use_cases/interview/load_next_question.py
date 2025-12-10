"""Load next question use case.

Extracted from InterviewConversationWorkflow._next_question_or_complete_node (lines 978-1048).
"""

import logging
import time
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID

from ....domain.models.interview import Interview
from ....application.ports.interview_repository_port import InterviewRepositoryPort
from ....application.ports.question_repository_port import QuestionRepositoryPort
from ...dto.interview.load_next_question_dto import LoadNextQuestionInput, LoadNextQuestionOutput

logger = logging.getLogger(__name__)


class LoadNextQuestionUseCase:
    """Load next question or mark for completion.

    Transitions interview state and loads next main question if available.
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

    async def execute(self, input_dto: LoadNextQuestionInput) -> LoadNextQuestionOutput:
        """Load next question or mark interview complete.

        Args:
            input_dto: Contains interview_id, has_more_questions, cached_interview

        Returns:
            LoadNextQuestionOutput with next question or completion flag
        """
        try:
            # Check if more questions exist
            if not input_dto.has_more_questions:
                logger.info(f"No more questions, completing interview {input_dto.interview_id}")
                return LoadNextQuestionOutput(complete=True)

            # Transition interview state (QUESTIONING)
            interview, cache_updates = await self._get_or_refresh_interview(
                interview_id=input_dto.interview_id,
                cached_interview=input_dto.cached_interview,
                force_refresh=False,
            )

            if not interview:
                logger.error(f"Interview {input_dto.interview_id} not found")
                return LoadNextQuestionOutput(
                    complete=True,
                    errors=[f"Interview {input_dto.interview_id} not found"],
                )

            interview.proceed_to_next_question()
            await self.interview_repo.update(interview)

            # Refresh cache after update
            _, cache_updates = await self._get_or_refresh_interview(
                interview_id=input_dto.interview_id,
                cached_interview=None,
                force_refresh=True,
            )

            # Get next question
            current_iq = await self.interview_repo.get_current_question(input_dto.interview_id)
            if not current_iq:
                logger.info("No more questions (after proceed), completing interview")
                return LoadNextQuestionOutput(complete=True)

            question = await self.question_repo.get_by_id(current_iq.question_id)
            if not question:
                logger.error(f"Question {current_iq.question_id} not found")
                return LoadNextQuestionOutput(
                    complete=True,
                    errors=[f"Question {current_iq.question_id} not found"],
                )

            # Update has_more_questions
            total = await self.interview_repo.count_interview_questions(input_dto.interview_id)
            has_more = interview.current_question_index < total - 1

            logger.info(
                f"Next question loaded: {question.id} (index {interview.current_question_index})",
                extra={"question_id": str(question.id), "has_more": has_more},
            )

            return LoadNextQuestionOutput(
                complete=False,
                current_question_id=str(question.id),
                current_question={
                    **question.model_dump(mode="json"),
                    "index": interview.current_question_index,
                    "total": total,
                },
                parent_question_id=None,
                parent_question=None,
                followup_count=0,
                cumulative_gaps=[],
                has_more_questions=has_more,
                cache_updates=cache_updates,
            )

        except Exception as exc:
            logger.error(f"load_next_question failed: {exc}", exc_info=True)
            return LoadNextQuestionOutput(
                complete=True,
                errors=[f"next_question: {str(exc)}"],
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
        if not force_refresh and cached_interview:
            try:
                interview = Interview(**cached_interview)
                return interview, {}
            except Exception as exc:
                logger.warning(f"Failed to reconstruct cached interview: {exc}")

        interview = await self.interview_repo.get_by_id(interview_id)
        if not interview:
            return None, {}

        cache_updates = {
            "_cached_interview": interview.model_dump(mode="json"),
            "_interview_version": (
                interview.updated_at.timestamp() if interview.updated_at else None
            ),
        }

        return interview, cache_updates

    @asynccontextmanager
    async def _timing_context(self, phase_name: str, interview_id: UUID | None = None):  # type: ignore[misc]
        """Context manager for timing operations.

        Args:
            phase_name: Name of the phase being timed
            interview_id: Optional interview ID for context
        """
        start = time.perf_counter()
        try:
            yield
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            logger.info(
                f"[TIMING] {phase_name}: {duration_ms:.2f}ms",
                extra={
                    "phase": phase_name,
                    "duration_ms": duration_ms,
                    "interview_id": str(interview_id) if interview_id else None,
                },
            )
