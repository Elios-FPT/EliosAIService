"""Generate follow-up use case.

Extracted from InterviewConversationWorkflow._generate_followup_node.
Generates follow-up question and transitions interview state.
"""

import logging
import time
from contextlib import asynccontextmanager
from uuid import UUID

from ...domain.models.follow_up_question import FollowUpQuestion
from ...domain.models.interview import Interview
from ...domain.models.question import Question
from ...domain.ports.follow_up_question_repository_port import FollowUpQuestionRepositoryPort
from ...domain.ports.interview_repository_port import InterviewRepositoryPort
from ...domain.ports.llm_port import LLMPort
from ..dto.interview.generate_followup_dto import GenerateFollowupInput, GenerateFollowupOutput

logger = logging.getLogger(__name__)


class GenerateFollowupUseCase:
    """Generate follow-up question and transition state.

    Creates FollowUpQuestion entity and updates interview state.
    Extracted from InterviewConversationWorkflow._generate_followup_node.
    """

    def __init__(
        self,
        interview_repo: InterviewRepositoryPort,
        followup_repo: FollowUpQuestionRepositoryPort,
        llm: LLMPort,
    ):
        """Initialize use case with required dependencies.

        Args:
            interview_repo: Interview repository port
            followup_repo: Follow-up question repository port
            llm: LLM port for generating follow-up questions
        """
        self.interview_repo = interview_repo
        self.followup_repo = followup_repo
        self.llm = llm

    async def execute(self, input: GenerateFollowupInput) -> GenerateFollowupOutput:
        """Execute follow-up generation.

        Args:
            input: Generate follow-up input data

        Returns:
            GenerateFollowupOutput with generated follow-up question and state updates

        Raises:
            ValueError: If interview, question, or answer not found
        """
        interview_id = input.interview_id
        current_q_id = input.current_question_id
        parent_question_id_str = input.parent_question_id or current_q_id
        if not parent_question_id_str:
            return GenerateFollowupOutput(
                current_question_id="",
                current_question={},
                parent_question_id="",
                parent_question={},
                followup_count=input.followup_count,
                needs_followup=False,
                cache_updates={},
                errors=["No parent question available"],
            )

        parent_question_id = UUID(parent_question_id_str)
        followup_count = input.followup_count

        # Get parent question
        parent_question_dict = input.parent_question or input.current_question
        if not parent_question_dict:
            return GenerateFollowupOutput(
                current_question_id="",
                current_question={},
                parent_question_id="",
                parent_question={},
                followup_count=input.followup_count,
                needs_followup=False,
                cache_updates={},
                errors=["No parent question"],
            )

        parent_question = Question(**parent_question_dict)

        # Get latest answer
        latest_answer = input.latest_answer
        if not latest_answer:
            return GenerateFollowupOutput(
                current_question_id="",
                current_question={},
                parent_question_id="",
                parent_question={},
                followup_count=input.followup_count,
                needs_followup=False,
                cache_updates={},
                errors=["No answers"],
            )

        # Determine severity from latest evaluation
        latest_eval = input.latest_evaluation or {}
        severity = "moderate"  # Default
        if latest_eval.get("gaps"):
            # Find highest severity
            severity_order = {"major": 3, "moderate": 2, "minor": 1}
            unresolved = [g for g in latest_eval["gaps"] if not g.get("resolved")]
            if unresolved:
                highest = max(
                    unresolved, key=lambda g: severity_order.get(g.get("severity", "moderate"), 0)
                )
                severity = highest.get("severity", "moderate")

        # Check for cached follow-up from unified analysis (Phase 2 optimization)
        followup_suggestion = input.followup_suggestion
        if followup_suggestion and followup_suggestion.get("question_text"):
            async with self._timing_context("followup_cached", interview_id):
                followup_text = followup_suggestion["question_text"]
                logger.info(
                    f"Using cached follow-up from unified analysis (reason: {followup_suggestion.get('reason', 'N/A')})"
                )
        else:
            # Fallback: Generate follow-up via separate LLM call (legacy path)
            logger.warning("No cached follow-up found, generating via separate LLM call")
            async with self._timing_context("followup_llm_call", interview_id):
                followup_text = await self.llm.generate_followup_question(
                    parent_question=parent_question.text,
                    answer_text=latest_answer.get("text", ""),
                    missing_concepts=input.cumulative_gaps,
                    severity=severity,
                    order=followup_count + 1,
                    cumulative_gaps=input.cumulative_gaps,
                    context={"interview_id": str(interview_id)},
                )

        # Create FollowUpQuestion entity
        followup_reason = input.followup_reason or "Gap detected"
        followup = FollowUpQuestion(
            parent_question_id=parent_question_id,
            interview_id=interview_id,
            text=followup_text,
            generated_reason=followup_reason,
            order_in_sequence=followup_count + 1,
        )
        async with self._timing_context("db_save_followup", interview_id):
            await self.followup_repo.save(followup)

        # Update interview state (FOLLOW_UP transition) - use cache
        interview, cache_updates = await self._get_or_refresh_interview(
            interview_id, input.cached_interview, force_refresh=False
        )
        if not interview:
            return GenerateFollowupOutput(
                current_question_id="",
                current_question={},
                parent_question_id="",
                parent_question={},
                followup_count=input.followup_count,
                needs_followup=False,
                cache_updates={},
                errors=[f"Interview {interview_id} not found"],
            )

        # Use domain method ask_followup() which handles business logic
        # and calls transition_to() internally for status change
        interview.ask_followup(
            followup_id=followup.id,
            parent_question_id=parent_question_id,
        )
        async with self._timing_context("db_update_interview_followup", interview_id):
            await self.interview_repo.update(interview)
        # Refresh cache after update
        _, cache_updates = await self._get_or_refresh_interview(
            interview_id, None, force_refresh=True
        )

        logger.info(
            f"Follow-up generated: {followup.id} (order {followup.order_in_sequence})",
            extra={
                "followup_id": str(followup.id),
                "parent_id": str(parent_question_id),
                "severity": severity,
            },
        )

        # Extract ideal_answer from parent question for gap detection
        parent_question_dict = input.parent_question or parent_question.model_dump(mode="json")
        ideal_answer = parent_question_dict.get("ideal_answer", "") if isinstance(parent_question_dict, dict) else ""

        if not ideal_answer:
            logger.warning(
                f"No ideal_answer in input for parent question {parent_question_id}, "
                f"gap detection will be skipped for follow-up"
            )
        else:
            logger.debug(f"Extracted ideal_answer from input for follow-up generation")

        return GenerateFollowupOutput(
            current_question_id=str(followup.id),
            current_question={
                "id": str(followup.id),
                "text": followup.text,
                # Follow-ups inherit parent's metadata to keep Question model valid
                "question_type": parent_question.question_type.value,
                "difficulty": parent_question.difficulty.value,
                "ideal_answer": ideal_answer,  # Pass parent's ideal_answer
                "parent_question_id": str(parent_question_id),  # WebSocket compatibility
                "generated_reason": followup.generated_reason,  # WebSocket compatibility
                "order_in_sequence": followup.order_in_sequence,  # WebSocket compatibility
            },
            parent_question_id=str(parent_question_id),
            parent_question=parent_question.model_dump(mode="json"),
            followup_count=followup_count + 1,
            needs_followup=False,  # Reset for next cycle
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

    @asynccontextmanager
    async def _timing_context(self, phase_name: str, interview_id: UUID | None = None):
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

