"""Generate follow-up question use case.

Extracted from InterviewConversationWorkflow._generate_followup_node (lines 827-976).
"""

import logging
import time
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID

from ....domain.models.follow_up_question import FollowUpQuestion
from ....domain.models.interview import Interview
from ....domain.models.question import Question
from ....application.ports.follow_up_question_repository_port import FollowUpQuestionRepositoryPort
from ....application.ports.interview_repository_port import InterviewRepositoryPort
from ....application.ports.llm_port import LLMPort
from ...dto.interview.generate_followup_dto import GenerateFollowupInput, GenerateFollowupOutput

logger = logging.getLogger(__name__)


class GenerateFollowupUseCase:
    """Generate follow-up question and transition state.

    Creates FollowUpQuestion entity and updates interview state.
    """

    def __init__(
        self,
        interview_repo: InterviewRepositoryPort,
        followup_repo: FollowUpQuestionRepositoryPort,
        llm: LLMPort,
    ):
        """Initialize with required ports.

        Args:
            interview_repo: Interview persistence port
            followup_repo: Follow-up question persistence port
            llm: LLM port for follow-up generation
        """
        self.interview_repo = interview_repo
        self.followup_repo = followup_repo
        self.llm = llm

    async def execute(self, input_dto: GenerateFollowupInput) -> GenerateFollowupOutput:
        """Generate follow-up question and update interview state.

        Args:
            input_dto: Contains parent_question, latest_answer, cumulative_gaps, etc.

        Returns:
            GenerateFollowupOutput with generated follow-up question and metadata
        """
        try:
            # Validate inputs
            current_q_id = input_dto.current_question_id
            parent_question_id_str = input_dto.parent_question_id or current_q_id
            if not parent_question_id_str:
                logger.error("No parent_question_id/current_question_id for follow-up generation")
                return GenerateFollowupOutput(
                    current_question_id="",
                    current_question={},
                    parent_question_id="",
                    parent_question={},
                    followup_count=input_dto.followup_count,
                    errors=["No parent question available"],
                )

            parent_question_id = UUID(parent_question_id_str)
            followup_count = input_dto.followup_count

            # Get parent question
            parent_question_dict = input_dto.parent_question or input_dto.current_question
            if not parent_question_dict:
                logger.error("No parent/current question in input")
                return GenerateFollowupOutput(
                    current_question_id="",
                    current_question={},
                    parent_question_id="",
                    parent_question={},
                    followup_count=followup_count,
                    errors=["No parent question"],
                )

            parent_question = Question(**parent_question_dict)

            if not input_dto.latest_answer:
                logger.error("No latest answer in input")
                return GenerateFollowupOutput(
                    current_question_id="",
                    current_question={},
                    parent_question_id="",
                    parent_question={},
                    followup_count=followup_count,
                    errors=["No answers"],
                )

            latest_answer = input_dto.latest_answer

            # Determine severity from latest evaluation
            severity = "moderate"
            if input_dto.latest_evaluation and input_dto.latest_evaluation.get("gaps"):
                severity_order = {"major": 3, "moderate": 2, "minor": 1}
                unresolved = [
                    g
                    for g in input_dto.latest_evaluation["gaps"]
                    if not g.get("resolved")
                ]
                if unresolved:
                    highest = max(
                        unresolved,
                        key=lambda g: severity_order.get(g.get("severity", "moderate"), 0),
                    )
                    severity = highest.get("severity", "moderate")

            # Check for cached follow-up from unified analysis (Phase 2 optimization)
            followup_suggestion = input_dto.followup_suggestion
            if followup_suggestion and followup_suggestion.get("question_text"):
                async with self._timing_context("followup_cached", input_dto.interview_id):
                    followup_text = followup_suggestion["question_text"]
                    logger.info(
                        f"Using cached follow-up from unified analysis "
                        f"(reason: {followup_suggestion.get('reason', 'N/A')})"
                    )
            else:
                # Fallback: Generate follow-up via separate LLM call
                logger.warning("No cached follow-up found, generating via separate LLM call")
                async with self._timing_context("followup_llm_call", input_dto.interview_id):
                    followup_text = await self.llm.generate_followup_question(
                        parent_question=parent_question.text,
                        answer_text=latest_answer["text"],
                        missing_concepts=input_dto.cumulative_gaps,
                        severity=severity,
                        order=followup_count + 1,
                        cumulative_gaps=input_dto.cumulative_gaps,
                    )

            # Create FollowUpQuestion entity
            followup_reason = input_dto.followup_reason or "Gap detected"
            followup = FollowUpQuestion(
                parent_question_id=parent_question_id,
                interview_id=input_dto.interview_id,
                text=followup_text,
                generated_reason=followup_reason,
                order_in_sequence=followup_count + 1,
            )
            async with self._timing_context("db_save_followup", input_dto.interview_id):
                await self.followup_repo.save(followup)

            # Update interview state (FOLLOW_UP transition)
            interview, cache_updates = await self._get_or_refresh_interview(
                interview_id=input_dto.interview_id,
                cached_interview=input_dto.cached_interview,
                force_refresh=False,
            )

            if not interview:
                logger.error(
                    f"Interview {input_dto.interview_id} not found during follow-up generation"
                )
                return GenerateFollowupOutput(
                    current_question_id="",
                    current_question={},
                    parent_question_id="",
                    parent_question={},
                    followup_count=followup_count,
                    errors=[f"Interview {input_dto.interview_id} not found"],
                )

            # Use domain method ask_followup()
            interview.ask_followup(
                followup_id=followup.id,
                parent_question_id=parent_question_id,
            )
            async with self._timing_context(
                "db_update_interview_followup", input_dto.interview_id
            ):
                await self.interview_repo.update(interview)

            # Refresh cache after update
            _, cache_updates = await self._get_or_refresh_interview(
                interview_id=input_dto.interview_id,
                cached_interview=None,
                force_refresh=True,
            )

            logger.info(
                f"Follow-up generated: {followup.id} (order {followup.order_in_sequence})",
                extra={
                    "followup_id": str(followup.id),
                    "parent_id": str(parent_question_id),
                    "severity": severity,
                },
            )

            # Extract ideal_answer from parent question
            ideal_answer = parent_question_dict.get("ideal_answer") or ""
            if not ideal_answer:
                logger.warning(
                    f"No ideal_answer in parent question {parent_question_id}, "
                    f"gap detection will be skipped for follow-up"
                )

            return GenerateFollowupOutput(
                current_question_id=str(followup.id),
                current_question={
                    "id": str(followup.id),
                    "text": followup.text,
                    "question_type": parent_question.question_type.value,
                    "difficulty": parent_question.difficulty.value,
                    "ideal_answer": ideal_answer,
                    "parent_question_id": str(parent_question_id),
                    "generated_reason": followup.generated_reason,
                    "order_in_sequence": followup.order_in_sequence,
                },
                parent_question_id=str(parent_question_id),
                parent_question=parent_question.model_dump(mode="json"),
                followup_count=followup_count + 1,
                needs_followup=False,
                cache_updates=cache_updates,
            )

        except Exception as exc:
            logger.error(f"generate_followup failed: {exc}", exc_info=True)
            return GenerateFollowupOutput(
                current_question_id="",
                current_question={},
                parent_question_id="",
                parent_question={},
                followup_count=input_dto.followup_count,
                errors=[f"generate_followup: {str(exc)}"],
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
