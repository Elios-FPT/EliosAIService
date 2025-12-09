"""Evaluate answer use case.

Extracted from InterviewConversationWorkflow._evaluate_answer_unified (lines 362-632).
Includes helper methods for gap detection (lines 1235-1348).
"""

import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from ....domain.models.answer import Answer, AnswerEvaluation
from ....domain.models.evaluation import (
    ConceptGap,
    Evaluation,
    FollowUpEvaluationContext,
    GapSeverity,
)
from ....domain.models.interview import Interview, InterviewStatus
from ....domain.models.question import Question
from ....domain.ports.answer_repository_port import AnswerRepositoryPort
from ....domain.ports.evaluation_repository_port import EvaluationRepositoryPort
from ....domain.ports.interview_repository_port import InterviewRepositoryPort
from ....domain.ports.llm_port import LLMPort
from ....domain.ports.question_repository_port import QuestionRepositoryPort
from ...dto.interview.evaluate_answer_dto import EvaluateAnswerInput, EvaluateAnswerOutput

logger = logging.getLogger(__name__)


class EvaluateAnswerUseCase:
    """Evaluate candidate answer using unified comprehensive analysis.

    Uses comprehensive_answer_analysis prompt to consolidate 3 LLM calls into 1.
    Includes hybrid gap detection (keywords + LLM) for performance optimization.
    """

    # Scoring weights for combined evaluation
    THEORETICAL_WEIGHT = 0.7
    SPEAKING_WEIGHT = 0.3

    def __init__(
        self,
        interview_repo: InterviewRepositoryPort,
        question_repo: QuestionRepositoryPort,
        answer_repo: AnswerRepositoryPort,
        evaluation_repo: EvaluationRepositoryPort,
        llm: LLMPort,
    ):
        """Initialize with required ports.

        Args:
            interview_repo: Interview persistence port
            question_repo: Question persistence port
            answer_repo: Answer persistence port
            evaluation_repo: Evaluation persistence port
            llm: LLM port for comprehensive analysis
        """
        self.interview_repo = interview_repo
        self.question_repo = question_repo
        self.answer_repo = answer_repo
        self.evaluation_repo = evaluation_repo
        self.llm = llm

    def _combine_evaluations(
        self,
        theoretical_eval: AnswerEvaluation,
        voice_metrics: dict[str, float] | None = None,
    ) -> dict[str, Any]:
        """Combine theoretical and speaking evaluations.

        Args:
            theoretical_eval: Semantic evaluation from LLM
            voice_metrics: Voice quality metrics from STT (optional)

        Returns:
            Dict with:
            {
                "overall_score": float (0-100),
                "theoretical_score": float (0-100),
                "speaking_score": float | None (0-100),
            }
        """
        theoretical_score = theoretical_eval.score

        # Calculate speaking score if voice metrics available
        if voice_metrics:
            speaking_score = self._calculate_speaking_score(voice_metrics)
            overall_score = (
                theoretical_score * self.THEORETICAL_WEIGHT
                + speaking_score * self.SPEAKING_WEIGHT
            )
        else:
            # Text-only answer: use 100% theoretical weight
            speaking_score = None
            overall_score = theoretical_score

        speaking_display = f"{speaking_score:.1f}" if speaking_score is not None else "N/A"
        logger.info(
            f"Combined evaluation: theoretical={theoretical_score:.1f}, "
            f"speaking={speaking_display}, "
            f"overall={overall_score:.1f}"
        )

        return {
            "overall_score": round(overall_score, 2),
            "theoretical_score": round(theoretical_score, 2),
            "speaking_score": round(speaking_score, 2) if speaking_score else None,
        }

    def _calculate_speaking_score(self, voice_metrics: dict[str, float]) -> float:
        """Calculate speaking score from voice metrics.

        Args:
            voice_metrics: Dict with intonation_score, fluency_score, confidence_score

        Returns:
            Speaking score (0-100)
        """
        # Get metrics with defaults
        intonation = voice_metrics.get("intonation_score", 0.5)
        fluency = voice_metrics.get("fluency_score", 0.5)
        confidence = voice_metrics.get("confidence_score", 0.5)

        # Average and convert to 0-100 scale
        avg_score = (intonation + fluency + confidence) / 3.0
        return avg_score * 100.0

    async def execute(self, input_dto: EvaluateAnswerInput) -> EvaluateAnswerOutput:
        """Evaluate answer using unified comprehensive analysis.

        Args:
            input_dto: Contains question, answer, conversation context

        Returns:
            EvaluateAnswerOutput with saved answer, evaluation, and follow-up suggestion

        Raises:
            Exception: Re-raises exceptions after logging
        """
        try:
            # Step 1: Validate interview and transition status
            interview, cache_updates = await self._get_or_refresh_interview(
                interview_id=input_dto.interview_id,
                cached_interview=input_dto.cached_interview,
                force_refresh=False,
            )

            if not interview:
                logger.error(f"Interview {input_dto.interview_id} not found")
                raise ValueError(f"Interview {input_dto.interview_id} not found")

            # Batch status transitions
            if interview.status == InterviewStatus.QUESTIONING:
                interview.mark_evaluating()
                async with self._timing_context(
                    "db_update_interview_status", input_dto.interview_id
                ):
                    await self.interview_repo.update(interview)
                logger.info(
                    f"Interview {input_dto.interview_id} transitioned to EVALUATING status"
                )
                _, cache_updates = await self._get_or_refresh_interview(
                    interview_id=input_dto.interview_id,
                    cached_interview=None,
                    force_refresh=True,
                )

            if interview.status == InterviewStatus.FOLLOW_UP:
                interview.answer_followup()
                async with self._timing_context(
                    "db_update_interview_status", input_dto.interview_id
                ):
                    await self.interview_repo.update(interview)
                logger.info(
                    f"Interview {input_dto.interview_id} transitioned from FOLLOW_UP to EVALUATING"
                )
                _, cache_updates = await self._get_or_refresh_interview(
                    interview_id=input_dto.interview_id,
                    cached_interview=None,
                    force_refresh=True,
                )

            # Step 2: Detect if this is a follow-up question
            is_followup = input_dto.parent_question_id is not None
            parent_question_id = input_dto.parent_question_id

            # Step 3: Get question (main or follow-up parent)
            if is_followup:
                if parent_question_id is None:
                    raise ValueError("parent_question_id is None for follow-up")
                question = await self.question_repo.get_by_id(parent_question_id)
                if not question:
                    raise ValueError(f"Parent question {parent_question_id} not found")
                logger.debug(f"Loaded parent question {parent_question_id} for follow-up")
            else:
                question = Question(**input_dto.question)

            # Step 4: Build follow-up context if applicable
            followup_context = None
            if is_followup:
                followup_context = self._build_followup_context_from_input(input_dto)
                if followup_context:
                    logger.debug(
                        f"Follow-up context: attempt={followup_context.attempt_number}, "
                        f"prev_scores={followup_context.previous_scores}, "
                        f"gaps={len(followup_context.cumulative_gaps)}"
                    )

            # Step 5: Create answer entity
            if is_followup:
                if parent_question_id is None:
                    raise ValueError("parent_question_id is None when creating follow-up answer")

                current_followup_id_str = input_dto.question.get("id")
                if not current_followup_id_str:
                    raise ValueError("current_question_id missing from question dict")

                answer_question_id = parent_question_id
                follow_up_question_id = UUID(current_followup_id_str)

                logger.info(
                    f"Creating follow-up answer: parent={parent_question_id}, "
                    f"follow_up={follow_up_question_id}"
                )
            else:
                answer_question_id = UUID(input_dto.question["id"])
                follow_up_question_id = None
                logger.info(f"Creating main question answer: question={answer_question_id}")

            answer = Answer(
                interview_id=input_dto.interview_id,
                question_id=answer_question_id,
                follow_up_question_id=follow_up_question_id,
                text=input_dto.answer_text,
                is_voice=input_dto.is_voice,
                voice_metrics=input_dto.voice_metrics,
                created_at=datetime.utcnow(),
            )

            # Step 6: Single unified LLM call (Phase 2 optimization)
            conversation_history = [
                {"role": msg["type"], "content": msg["content"]}
                for msg in input_dto.conversation_history
            ]
            context: dict[str, Any] = {
                "interview_id": str(input_dto.interview_id),
                "candidate_id": str(input_dto.candidate_id),
                "conversation_history": conversation_history,
            }

            async with self._timing_context(
                "llm_comprehensive_analysis", input_dto.interview_id
            ):
                analysis = await self.llm.analyze_answer_comprehensive(
                    question=question,
                    answer_text=input_dto.answer_text,
                    context=context,
                    followup_context=followup_context,
                )

            # Step 7: Extract evaluation from analysis
            technical_accuracy = (
                analysis.evaluation.dimensions[0].score / 40.0
                if len(analysis.evaluation.dimensions) > 0
                else 0.0
            )
            depth_understanding = (
                analysis.evaluation.dimensions[1].score / 30.0
                if len(analysis.evaluation.dimensions) > 1
                else 0.0
            )
            semantic_similarity = max(
                0.0, min(1.0, analysis.evaluation.total_score / 100.0)
            )

            llm_eval = AnswerEvaluation(
                score=analysis.evaluation.total_score,
                completeness=technical_accuracy,
                relevance=depth_understanding,
                sentiment="neutral",
                reasoning=analysis.evaluation.reasoning,
                strengths=analysis.evaluation.strengths,
                weaknesses=analysis.evaluation.weaknesses,
                improvement_suggestions=analysis.evaluation.improvement_suggestions,
                semantic_similarity=semantic_similarity,
            )

            # Step 7.5: Combine theoretical and speaking scores
            combined_result = self._combine_evaluations(
                theoretical_eval=llm_eval,
                voice_metrics=input_dto.voice_metrics,
            )

            theoretical_score = combined_result["theoretical_score"]
            speaking_score = combined_result["speaking_score"]
            overall_score = combined_result["overall_score"]

            # Step 8: Extract gaps from analysis
            gap_concepts: list[str] = [gap.concept for gap in analysis.gaps]
            gaps_dict: dict[str, Any] = {
                "concepts": gap_concepts,
                "confirmed": len(analysis.gaps) > 0,
                "severity": analysis.gaps[0].severity if analysis.gaps else "minor",
            }

            # Step 9: Extract similarity score for Evaluation entity
            similarity_score = (
                semantic_similarity if question.has_ideal_answer() else None
            )

            # Step 10: Determine attempt number and parent evaluation
            attempt_number = followup_context.attempt_number if followup_context else 1
            parent_evaluation_id = (
                followup_context.previous_evaluations[0].id
                if followup_context and followup_context.previous_evaluations
                else None
            )

            # Step 11: Create Evaluation entity
            evaluation = Evaluation(
                answer_id=answer.id,
                raw_score=llm_eval.score,
                theoretical_score=theoretical_score,
                speaking_score=speaking_score,
                penalty=0.0,
                final_score=overall_score,  # Use combined score instead of llm_eval.score
                similarity_score=similarity_score,
                completeness=llm_eval.completeness,
                relevance=llm_eval.relevance,
                sentiment=llm_eval.sentiment,
                voice_metrics=input_dto.voice_metrics,  # Store raw voice metrics for future analysis
                reasoning=llm_eval.reasoning,
                strengths=llm_eval.strengths,
                weaknesses=llm_eval.weaknesses,
                improvement_suggestions=llm_eval.improvement_suggestions,
                attempt_number=attempt_number,
                parent_evaluation_id=parent_evaluation_id,
                gaps=[],
                evaluated_at=datetime.utcnow(),
            )

            evaluation.gaps = [
                ConceptGap(
                    evaluation_id=evaluation.id,
                    concept=concept,
                    severity=self._determine_gap_severity(concept, gaps_dict),
                    resolved=False,
                    created_at=datetime.utcnow(),
                )
                for concept in gap_concepts
            ]

            # Step 12: Apply penalty based on attempt number
            # Note: apply_penalty uses raw_score, but we need to apply penalty to combined score
            evaluation.apply_penalty(attempt_number)
            # Override final_score calculation: penalty applies to overall_score, not raw_score
            evaluation.final_score = max(0.0, min(100.0, overall_score + evaluation.penalty))
            speaking_display = f"{speaking_score:.1f}" if speaking_score is not None else "N/A"
            logger.info(
                f"Penalty applied: attempt={attempt_number}, penalty={evaluation.penalty}, "
                f"theoretical={theoretical_score:.1f}, speaking={speaking_display}, "
                f"overall={overall_score:.1f}, final_score={evaluation.final_score:.1f}"
            )

            # Step 13: Check if gaps should be resolved
            if evaluation.is_gap_resolved_by_criteria():
                evaluation.resolve_gaps()
                logger.info(
                    f"Gaps resolved by criteria: completeness={evaluation.completeness:.2f}, "
                    f"final_score={evaluation.final_score:.1f}, attempt={attempt_number}"
                )

            # TODO: save answer and evaluation at the same time
            # Step 14: Save answer first
            async with self._timing_context("db_save_answer", input_dto.interview_id):
                saved_answer = await self.answer_repo.save(answer)

            # Step 15: Update evaluation with correct answer_id and gap evaluation_ids
            evaluation.answer_id = saved_answer.id
            for gap in evaluation.gaps:
                gap.evaluation_id = evaluation.id

            # Step 16: Save evaluation
            async with self._timing_context("db_save_evaluation", input_dto.interview_id):
                saved_evaluation = await self.evaluation_repo.save(evaluation)

            similarity_display = f"{similarity_score:.2f}" if similarity_score is not None else "N/A"
            logger.info(
                f"Answer processed (unified): score={saved_evaluation.final_score:.1f}, "
                f"similarity={similarity_display}, "
                f"gaps={len(saved_evaluation.gaps)}"
            )

            # Step 18: Store follow-up suggestion
            followup_suggestion = None
            if analysis.follow_up and analysis.follow_up.question_text:
                followup_suggestion = {
                    "question_text": analysis.follow_up.question_text,
                    "reason": analysis.follow_up.reason,
                    "target_gaps": analysis.follow_up.target_gaps,
                }

            evaluation_payload = saved_evaluation.model_dump(mode="json")
            evaluation_payload["question_id"] = input_dto.question.get("id")
            # Alias final_score -> score for downstream clients
            evaluation_payload["score"] = saved_evaluation.final_score

            return EvaluateAnswerOutput(
                answer=saved_answer.model_dump(mode="json"),
                evaluation=evaluation_payload,
                followup_suggestion=followup_suggestion,
                cache_updates=cache_updates,
            )

        except Exception as exc:
            logger.error(f"Unified evaluation failed: {exc}", exc_info=True)
            raise

    def _build_followup_context_from_input(
        self, input_dto: EvaluateAnswerInput
    ) -> FollowUpEvaluationContext | None:
        """Build follow-up evaluation context from input DTO.

        Args:
            input_dto: Input containing evaluations and gaps

        Returns:
            FollowUpEvaluationContext if follow-up, None otherwise
        """
        if not input_dto.parent_question_id:
            return None

        current_q_id = input_dto.question.get("id")
        if not current_q_id:
            logger.warning("No question ID in input for follow-up context")
            return None

        followup_count = input_dto.followup_count
        attempt_number = followup_count

        # Extract previous evaluations
        previous_evaluations: list[Evaluation] = []
        for eval_dict in input_dto.evaluations:
            try:
                eval_q_id = eval_dict.get("question_id")
                if eval_q_id in [str(input_dto.parent_question_id), current_q_id]:
                    evaluation = Evaluation(**eval_dict)
                    previous_evaluations.append(evaluation)
            except Exception as exc:
                logger.warning(f"Failed to parse evaluation: {exc}")
                continue

        previous_evaluations.sort(key=lambda e: e.created_at)

        # Create ConceptGap objects from concepts
        cumulative_gaps: list[ConceptGap] = []
        for concept in input_dto.cumulative_gaps:
            eval_id = previous_evaluations[0].id if previous_evaluations else uuid4()
            gap = ConceptGap(
                evaluation_id=eval_id,
                concept=concept,
                severity=GapSeverity.MODERATE,
                resolved=False,
                created_at=datetime.utcnow(),
            )
            cumulative_gaps.append(gap)

        # Extract ideal_answer from question
        ideal_answer = input_dto.question.get("ideal_answer", "")
        if not ideal_answer:
            logger.warning("No ideal_answer in question for follow-up context")

        previous_scores = [e.final_score for e in previous_evaluations]

        try:
            context = FollowUpEvaluationContext(
                parent_question_id=input_dto.parent_question_id,
                follow_up_question_id=UUID(current_q_id),
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

        Args:
            concept: The missing concept
            gaps_dict: Gaps dictionary from LLM

        Returns:
            GapSeverity enum value
        """
        severity_str = gaps_dict.get("severity", "moderate")
        try:
            return GapSeverity(severity_str.lower())
        except ValueError:
            logger.warning(f"Invalid severity '{severity_str}', defaulting to MODERATE")
            return GapSeverity.MODERATE

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
