"""Evaluate answer use case.

Extracted from InterviewConversationWorkflow._evaluate_answer_unified.
Handles unified comprehensive analysis (evaluation + gap detection + follow-up suggestion).
"""

import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from ...domain.models.answer import Answer, AnswerEvaluation
from ...domain.models.evaluation import ConceptGap, Evaluation, FollowUpEvaluationContext, GapSeverity
from ...domain.models.interview import Interview, InterviewStatus
from ...domain.models.question import Question
from ...domain.ports.answer_repository_port import AnswerRepositoryPort
from ...domain.ports.evaluation_repository_port import EvaluationRepositoryPort
from ...domain.ports.interview_repository_port import InterviewRepositoryPort
from ...domain.ports.llm_port import LLMPort
from ...domain.ports.question_repository_port import QuestionRepositoryPort
from ..dto.interview.evaluate_answer_dto import EvaluateAnswerInput, EvaluateAnswerOutput

logger = logging.getLogger(__name__)


class EvaluateAnswerUseCase:
    """Evaluate candidate answer using unified comprehensive analysis.

    Consolidates evaluation + gap detection + follow-up suggestion into single LLM call.
    Extracted from InterviewConversationWorkflow._evaluate_answer_unified.
    """

    def __init__(
        self,
        interview_repo: InterviewRepositoryPort,
        question_repo: QuestionRepositoryPort,
        answer_repo: AnswerRepositoryPort,
        evaluation_repo: EvaluationRepositoryPort,
        llm: LLMPort,
    ):
        """Initialize use case with required dependencies.

        Args:
            interview_repo: Interview repository port
            question_repo: Question repository port
            answer_repo: Answer repository port
            evaluation_repo: Evaluation repository port
            llm: LLM port for comprehensive analysis
        """
        self.interview_repo = interview_repo
        self.question_repo = question_repo
        self.answer_repo = answer_repo
        self.evaluation_repo = evaluation_repo
        self.llm = llm

    async def execute(self, input: EvaluateAnswerInput) -> EvaluateAnswerOutput:
        """Execute answer evaluation.

        Args:
            input: Evaluation input data

        Returns:
            EvaluateAnswerOutput with saved answer, evaluation, and followup suggestion

        Raises:
            ValueError: If interview or question not found
        """
        # Validate input
        if not input.question:
            raise ValueError("No current question in input")

        if not input.answer_text:
            logger.warning("No answer text in input")
            # Return empty output (no-op)
            return EvaluateAnswerOutput(
                answer={},
                evaluation={},
                followup_suggestion=None,
                cache_updates={},
            )

        interview_id = input.interview_id

        # Step 1: Get or refresh interview (use cache from input)
        interview, cache_updates = await self._get_or_refresh_interview(
            interview_id, input.cached_interview, force_refresh=False
        )
        if not interview:
            raise ValueError(f"Interview {interview_id} not found")

        # Step 2: Handle interview status transitions
        cache_updates = await self._handle_status_transitions(interview, cache_updates)

        # Step 3: Detect if this is a follow-up question
        is_followup = input.parent_question_id is not None
        parent_question_id = input.parent_question_id

        # Step 4: Get question (main or follow-up parent)
        if is_followup:
            if parent_question_id is None:
                raise ValueError("parent_question_id is None for follow-up")
            question = await self.question_repo.get_by_id(parent_question_id)
            if not question:
                raise ValueError(f"Parent question {parent_question_id} not found")
            logger.debug(f"Loaded parent question {parent_question_id} for follow-up evaluation")
        else:
            # Main question - reconstruct from input
            question = Question(**input.question)

        # Step 5: Build follow-up context if applicable
        followup_context = None
        if is_followup:
            followup_context = self._build_followup_context_from_input(input)
            if followup_context:
                logger.debug(
                    f"Follow-up context: attempt={followup_context.attempt_number}, "
                    f"prev_scores={followup_context.previous_scores}, "
                    f"gaps={len(followup_context.cumulative_gaps)}"
                )

        # Step 6: Create answer entity
        if is_followup:
            if parent_question_id is None:
                raise ValueError("parent_question_id is None when creating follow-up answer")

            # Get current question ID from input (should be follow-up ID)
            # Note: input.question contains the current question dict, but for follow-ups
            # we need the parent question ID for question_id and current_question_id for follow_up_question_id
            # Extract current_question_id from input.question if available, or use parent_question_id
            current_question_id_str = input.question.get("id") if isinstance(input.question, dict) else None
            if not current_question_id_str:
                raise ValueError("current_question_id missing from input when is_followup=True")

            answer_question_id = parent_question_id  # Parent context (analytics)
            follow_up_question_id = UUID(current_question_id_str)  # Direct link to follow-up

            logger.info(
                f"Creating follow-up answer: parent={parent_question_id}, "
                f"follow_up={follow_up_question_id}"
            )
        else:
            # Main question answer
            current_question_id_str = input.question.get("id") if isinstance(input.question, dict) else None
            if not current_question_id_str:
                raise ValueError("current_question_id missing from input")
            answer_question_id = UUID(current_question_id_str)
            follow_up_question_id = None

            logger.info(f"Creating main question answer: question={answer_question_id}")

        answer = Answer(
            interview_id=interview_id,
            question_id=answer_question_id,
            follow_up_question_id=follow_up_question_id,
            text=input.answer_text,
            is_voice=input.is_voice,
            voice_metrics=input.voice_metrics,
            created_at=datetime.utcnow(),
        )

        # Step 7: Single unified LLM call
        conversation_history = [
            {"role": msg.get("type", "human"), "content": msg.get("content", "")}
            for msg in input.conversation_history
        ]
        context: dict[str, Any] = {
            "interview_id": str(interview_id),
            "candidate_id": str(input.candidate_id),
            "conversation_history": conversation_history,
        }

        # Unified comprehensive analysis (consolidates 3→1 LLM call)
        async with self._timing_context("llm_comprehensive_analysis", interview_id):
            analysis = await self.llm.analyze_answer_comprehensive(
                question=question,
                answer_text=input.answer_text,
                context=context,
                followup_context=followup_context,
            )

        # Step 8: Extract evaluation from analysis
        # Map comprehensive analysis dimensions to AnswerEvaluation
        # Normalize dimension scores to 0-1 range
        technical_accuracy = (
            analysis.evaluation.dimensions[0].score / 40.0 if len(analysis.evaluation.dimensions) > 0 else 0.0
        )
        depth_understanding = (
            analysis.evaluation.dimensions[1].score / 30.0 if len(analysis.evaluation.dimensions) > 1 else 0.0
        )
        clarity = (
            analysis.evaluation.dimensions[2].score / 20.0 if len(analysis.evaluation.dimensions) > 2 else 0.0
        )
        practical = (
            analysis.evaluation.dimensions[3].score / 10.0 if len(analysis.evaluation.dimensions) > 3 else 0.0
        )

        # Compute semantic similarity: use score normalized to 0-1 as proxy
        semantic_similarity = max(0.0, min(1.0, analysis.evaluation.total_score / 100.0))

        llm_eval = AnswerEvaluation(
            score=analysis.evaluation.total_score,
            completeness=technical_accuracy,  # Use technical_accuracy as completeness proxy
            relevance=depth_understanding,  # Use depth as relevance proxy
            sentiment="neutral",  # Not in unified output
            reasoning=analysis.evaluation.reasoning,
            strengths=analysis.evaluation.strengths,
            weaknesses=analysis.evaluation.weaknesses,
            improvement_suggestions=analysis.evaluation.improvement_suggestions,
            semantic_similarity=semantic_similarity,  # Derived from total_score
        )

        # Step 9: Extract gaps from analysis
        gaps_dict = {
            "concepts": [gap.concept for gap in analysis.gaps],
            "confirmed": len(analysis.gaps) > 0,
            "severity": analysis.gaps[0].severity if analysis.gaps else "minor",
        }

        # Step 10: Extract similarity score for Evaluation entity (if ideal_answer exists)
        similarity_score = semantic_similarity if question.has_ideal_answer() else None

        # Step 11: Determine attempt number and parent evaluation
        attempt_number = followup_context.attempt_number if followup_context else 1
        parent_evaluation_id = (
            followup_context.previous_evaluations[0].id
            if followup_context and followup_context.previous_evaluations
            else None
        )

        # Get current question ID for evaluation
        current_question_id = UUID(input.question.get("id")) if isinstance(input.question, dict) and input.question.get("id") else answer_question_id

        # Step 12: Create Evaluation entity
        evaluation = Evaluation(
            answer_id=answer.id,  # Will link after saving answer
            question_id=current_question_id,  # Keep follow-up question ID
            interview_id=interview_id,
            raw_score=llm_eval.score,
            penalty=0.0,  # Will be set by apply_penalty()
            final_score=llm_eval.score,  # Will be recalculated by apply_penalty()
            similarity_score=similarity_score,
            completeness=llm_eval.completeness,
            relevance=llm_eval.relevance,
            sentiment=llm_eval.sentiment,
            reasoning=llm_eval.reasoning,
            strengths=llm_eval.strengths,
            weaknesses=llm_eval.weaknesses,
            improvement_suggestions=llm_eval.improvement_suggestions,
            attempt_number=attempt_number,
            parent_evaluation_id=parent_evaluation_id,
            gaps=[
                ConceptGap(
                    evaluation_id=answer.id,  # Temporary, will be updated
                    concept=concept,
                    severity=self._determine_gap_severity(concept, gaps_dict),
                    resolved=False,
                    created_at=datetime.utcnow(),
                )
                for concept in gaps_dict.get("concepts", [])
            ],
            evaluated_at=datetime.utcnow(),
        )

        # Step 13: Apply penalty based on attempt number
        evaluation.apply_penalty(attempt_number)
        logger.info(
            f"Penalty applied: attempt={attempt_number}, penalty={evaluation.penalty}, "
            f"raw_score={llm_eval.score:.1f}, final_score={evaluation.final_score:.1f}"
        )

        # Step 14: Check if gaps should be resolved
        if evaluation.is_gap_resolved_by_criteria():
            evaluation.resolve_gaps()
            logger.info(
                f"Gaps resolved by criteria: completeness={evaluation.completeness:.2f}, "
                f"final_score={evaluation.final_score:.1f}, attempt={attempt_number}"
            )

        # Step 15: Save answer first (to get ID)
        async with self._timing_context("db_save_answer", interview_id):
            saved_answer = await self.answer_repo.save(answer)

        # Step 16: Update evaluation with correct answer_id and gap evaluation_ids
        evaluation.answer_id = saved_answer.id
        for gap in evaluation.gaps:
            gap.evaluation_id = evaluation.id

        # Step 17: Save evaluation
        async with self._timing_context("db_save_evaluation", interview_id):
            saved_evaluation = await self.evaluation_repo.save(evaluation)

        # Step 18: Link answer to evaluation (bidirectional link)
        saved_answer.evaluation_id = saved_evaluation.id
        async with self._timing_context("db_update_answer", interview_id):
            saved_answer = await self.answer_repo.update(saved_answer)

        logger.info(
            f"Answer processed (unified): score={saved_evaluation.final_score:.1f}, "
            f"similarity={f'{similarity_score:.2f}' if similarity_score is not None else 'N/A'}, "
            f"gaps={len(saved_evaluation.gaps)}"
        )

        # Step 19: Store follow-up suggestion in output for later use
        followup_suggestion = None
        if analysis.follow_up and analysis.follow_up.question_text:
            followup_suggestion = {
                "question_text": analysis.follow_up.question_text,
                "reason": analysis.follow_up.reason,
                "target_gaps": analysis.follow_up.target_gaps,
            }

        return EvaluateAnswerOutput(
            answer=saved_answer.model_dump(mode="json"),
            evaluation=saved_evaluation.model_dump(mode="json"),
            followup_suggestion=followup_suggestion,
            cache_updates=cache_updates,
        )

    async def _get_or_refresh_interview(
        self,
        interview_id: UUID,
        cached_interview: dict[str, Any] | None,
        force_refresh: bool = False,
    ) -> tuple[Interview | None, dict[str, Any]]:
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

    async def _handle_status_transitions(
        self, interview: Interview, cache_updates: dict[str, Any]
    ) -> dict[str, Any]:
        """Handle interview status transitions.

        Transitions from QUESTIONING to EVALUATING, or from FOLLOW_UP to EVALUATING.

        Args:
            interview: Interview entity
            cache_updates: Current cache updates dict

        Returns:
            Updated cache_updates dict
        """
        interview_id = interview.id

        # Transition from QUESTIONING to EVALUATING if needed
        if interview.status == InterviewStatus.QUESTIONING:
            interview.mark_evaluating()
            async with self._timing_context("db_update_interview_status", interview_id):
                await self.interview_repo.update(interview)
            logger.info(f"Interview {interview_id} transitioned to EVALUATING status")
            # Refresh cache after update
            _, cache_updates = await self._get_or_refresh_interview(
                interview_id, None, force_refresh=True
            )

        # Transition from FOLLOW_UP to EVALUATING when processing follow-up answer
        if interview.status == InterviewStatus.FOLLOW_UP:
            interview.answer_followup()
            async with self._timing_context("db_update_interview_status", interview_id):
                await self.interview_repo.update(interview)
            logger.info(f"Interview {interview_id} transitioned from FOLLOW_UP to EVALUATING status")
            # Refresh cache after update
            _, cache_updates = await self._get_or_refresh_interview(
                interview_id, None, force_refresh=True
            )

        return cache_updates

    def _build_followup_context_from_input(
        self, input: EvaluateAnswerInput
    ) -> FollowUpEvaluationContext | None:
        """Build follow-up evaluation context from input DTO.

        Extracts previous evaluations, gaps, and scores from input
        (no database queries).

        Args:
            input: EvaluateAnswerInput DTO

        Returns:
            FollowUpEvaluationContext if follow-up question, None if main question
        """
        # Check if this is a follow-up question
        parent_question_id = input.parent_question_id
        if not parent_question_id:
            return None  # Main question, no context needed

        # Extract current question ID from input
        current_question_id_str = input.question.get("id") if isinstance(input.question, dict) else None
        if not current_question_id_str:
            logger.warning("No current_question_id in input for follow-up context")
            return None

        current_q_id = UUID(current_question_id_str)

        # Get follow-up count (attempt number)
        attempt_number = input.followup_count  # 2 or 3

        # Extract previous evaluations from input
        evaluations_dicts = input.evaluations
        previous_evaluations: list[Evaluation] = []

        for eval_dict in evaluations_dicts:
            try:
                # Filter evaluations for current question chain
                eval_q_id_str = eval_dict.get("question_id")
                if eval_q_id_str:
                    eval_q_id = UUID(eval_q_id_str) if isinstance(eval_q_id_str, str) else eval_q_id_str
                    if eval_q_id in [parent_question_id, current_q_id]:
                        evaluation = Evaluation(**eval_dict)
                        previous_evaluations.append(evaluation)
            except Exception as exc:
                logger.warning(f"Failed to parse evaluation from input: {exc}")
                continue

        # Sort by created_at
        previous_evaluations.sort(key=lambda e: e.created_at)

        # Extract cumulative gaps from input
        gap_concepts = input.cumulative_gaps
        cumulative_gaps: list[ConceptGap] = []

        # Create ConceptGap objects from concepts
        for concept in gap_concepts:
            # Use first evaluation ID as placeholder (will be updated)
            eval_id = previous_evaluations[0].id if previous_evaluations else uuid4()
            gap = ConceptGap(
                evaluation_id=eval_id,
                concept=concept,
                severity=GapSeverity.MODERATE,  # Default severity
                resolved=False,
                created_at=datetime.utcnow(),
            )
            cumulative_gaps.append(gap)

        # Extract ideal_answer from question in input
        question_dict = input.question
        ideal_answer = question_dict.get("ideal_answer", "") if isinstance(question_dict, dict) else ""

        if not ideal_answer:
            logger.warning("No ideal_answer in input for follow-up context")

        # Extract previous scores
        previous_scores = [e.final_score for e in previous_evaluations]

        # Build context
        try:
            context = FollowUpEvaluationContext(
                parent_question_id=parent_question_id,
                follow_up_question_id=current_q_id,
                attempt_number=attempt_number,
                previous_evaluations=previous_evaluations,
                cumulative_gaps=cumulative_gaps,
                previous_scores=previous_scores,
                parent_ideal_answer=ideal_answer,
            )

            logger.debug(
                f"Follow-up context built: attempt={attempt_number}, "
                f"prev_evals={len(previous_evaluations)}, gaps={len(cumulative_gaps)}"
            )

            return context

        except Exception as exc:
            logger.error(f"Failed to build follow-up context: {exc}", exc_info=True)
            return None

    def _determine_gap_severity(self, concept: str, gaps_dict: dict[str, Any]) -> GapSeverity:
        """Determine gap severity from LLM response.

        Maps LLM severity string to GapSeverity enum.
        Defaults to MODERATE if invalid/missing.

        Args:
            concept: The missing concept (unused, for signature compatibility)
            gaps_dict: Gaps dictionary from LLM
                Format: {"severity": "minor" | "moderate" | "major", ...}

        Returns:
            GapSeverity enum value
        """
        severity_str = gaps_dict.get("severity", "moderate")
        try:
            return GapSeverity(severity_str.lower())
        except ValueError:
            logger.warning(f"Invalid severity '{severity_str}', defaulting to MODERATE")
            return GapSeverity.MODERATE

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

