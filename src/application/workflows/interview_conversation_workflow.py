"""LangGraph workflow for interview conversation (QA phase).

Replaces session_orchestrator.py with stateful workflow for:
- Answer evaluation with conversation memory
- Adaptive follow-up generation
- Question progression
- Interview completion

Uses PostgreSQL checkpointing for state persistence across reconnects.
"""

import logging
from datetime import datetime
from typing import Any, TypedDict
from uuid import UUID, uuid4

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import StateSnapshot

from ...domain.models.answer import Answer
from ...domain.models.evaluation import Evaluation, ConceptGap, GapSeverity, FollowUpEvaluationContext
from ...domain.models.interview import InterviewStatus
from ...domain.models.question import Question
from ...domain.models.follow_up_question import FollowUpQuestion
from ...domain.ports.llm_port import LLMPort
from ...domain.ports.answer_repository_port import AnswerRepositoryPort
from ...domain.ports.evaluation_repository_port import EvaluationRepositoryPort
from ...domain.ports.interview_repository_port import InterviewRepositoryPort
from ...domain.ports.question_repository_port import QuestionRepositoryPort
from ...domain.ports.follow_up_question_repository_port import FollowUpQuestionRepositoryPort
from .base_workflow import BaseWorkflow


logger = logging.getLogger(__name__)


class ConversationState(TypedDict):
    """State for interview conversation workflow.

    Checkpointed after each node execution to PostgreSQL.
    All UUIDs serialized as strings for JSON compatibility.
    """
    # Input (initial)
    interview_id: str  # UUID as str
    candidate_id: str  # UUID as str

    # Conversation memory (LangChain BaseMessage serialized)
    messages: list[dict[str, Any]]  # Serialized BaseMessage.dict()

    # Current context
    current_question_id: str | None
    current_question: dict[str, Any] | None  # Question.model_dump()
    parent_question_id: str | None  # For follow-ups
    pending_answer_text: str | None  # From WebSocket input
    is_voice_answer: bool
    voice_metrics: dict[str, Any] | None

    # Accumulated results
    answers: list[dict[str, Any]]  # Answer.model_dump()
    evaluations: list[dict[str, Any]]  # Evaluation.model_dump()
    followup_count: int
    cumulative_gaps: list[str]

    # Control flow
    has_more_questions: bool
    needs_followup: bool
    complete: bool
    followup_reason: str | None

    # Completion data (from _complete_interview_node)
    summary: dict[str, Any] | None  # DetailedInterviewFeedback.model_dump()
    final_status: str | None  # InterviewStatus.value

    # Error handling
    errors: list[str]
    retry_count: int

    # Checkpointing metadata
    checkpoint_thread_id: str
    last_checkpoint_time: float | None


class InterviewConversationWorkflow(BaseWorkflow):
    """LangGraph workflow for interview conversation (QA phase).

    Manages stateful interview flow with:
    - 7 nodes (start session, evaluate answer, memory update, follow-up decision,
      follow-up generation, next question, complete interview)
    - Conversation memory (truncated to 10 messages)
    - PostgreSQL checkpointing for state persistence
    - Conditional routing based on follow-up needs and question availability
    """

    def __init__(
        self,
        checkpointer: AsyncPostgresSaver,
        interview_repo: InterviewRepositoryPort,
        question_repo: QuestionRepositoryPort,
        answer_repo: AnswerRepositoryPort,
        evaluation_repo: EvaluationRepositoryPort,
        followup_repo: FollowUpQuestionRepositoryPort,
        llm: LLMPort,
    ):
        """Initialize conversation workflow.

        Args:
            checkpointer: AsyncPostgresSaver for state persistence
            interview_repo: Interview repository
            question_repo: Question repository
            answer_repo: Answer repository
            evaluation_repo: Evaluation repository
            followup_repo: Follow-up question repository
            llm: LLM adapter for evaluation and follow-up generation
        """
        super().__init__(checkpointer)
        self.interview_repo = interview_repo
        self.question_repo = question_repo
        self.answer_repo = answer_repo
        self.evaluation_repo = evaluation_repo
        self.followup_repo = followup_repo
        self.llm = llm
        self.app = self._build_graph()

    def _build_graph(self) -> CompiledStateGraph[ConversationState]:
        """Build LangGraph StateGraph with all nodes and edges.

        Workflow structure:
        START → route_entry → [new session?] → start_session → END (wait for answer)
                    ↓
              [has answer?] → evaluate_answer → update_memory → decide_followup
                                                      ↓
                                              [needs_followup?]
                                                      ↓
                                              generate_followup → END (wait for answer)
                                                      ↓
                                              next_or_complete → [complete?] → complete → END
                                                      ↓
                                              [has_more?] → END (wait for answer)

        Returns:
            Compiled StateGraph ready for execution
        """
        # Create graph
        graph = StateGraph(ConversationState)

        # Add nodes
        graph.add_node("route_entry", self._route_entry_node)
        graph.add_node("start_session", self._start_session_node)
        graph.add_node("evaluate_answer", self._evaluate_answer_node)
        graph.add_node("update_memory", self._update_memory_node)
        graph.add_node("decide_followup", self._decide_followup_node)
        graph.add_node("generate_followup", self._generate_followup_node)
        graph.add_node("next_or_complete", self._next_question_or_complete_node)
        graph.add_node("complete", self._complete_interview_node)

        # Add edges
        graph.set_entry_point("route_entry")

        # Route entry: new session or answer processing
        graph.add_conditional_edges(
            "route_entry",
            self._route_entry_point,
            {
                "start_session": "start_session",
                "evaluate_answer": "evaluate_answer",
            },
        )

        # Start session, then wait for first answer
        graph.add_edge("start_session", END)

        # Linear flow: evaluate → memory → decide
        graph.add_edge("evaluate_answer", "update_memory")
        graph.add_edge("update_memory", "decide_followup")

        # Conditional: decide_followup → generate_followup OR next_or_complete
        graph.add_conditional_edges(
            "decide_followup",
            self._should_generate_followup,
            {
                "generate_followup": "generate_followup",
                "next_or_complete": "next_or_complete",
            },
        )

        # Follow-up generated → back to evaluate_answer (wait for answer)
        # Note: WebSocket handler will call process_answer() which continues from checkpoint
        graph.add_edge("generate_followup", END)

        # Conditional: next_or_complete → complete OR back to evaluate
        graph.add_conditional_edges(
            "next_or_complete",
            self._should_complete,
            {
                "complete": "complete",
                "wait_for_answer": END,  # Wait for next answer from WebSocket
            },
        )

        graph.add_edge("complete", END)

        # Compile with checkpointer
        return graph.compile(checkpointer=self.checkpointer)  # type: ignore[return-value]

    # ========== WORKFLOW NODES ==========

    async def _route_entry_node(self, state: ConversationState) -> dict[str, Any]:
        """Entry point router (pass-through node).

        No-op node that just passes state through to conditional edge.

        Args:
            state: Current conversation state

        Returns:
            Empty dict (no state updates)
        """
        return {}

    async def _start_session_node(self, state: ConversationState) -> dict[str, Any]:
        """Initialize conversation and load first question.

        Transitions interview to QUESTIONING state and loads first question.

        Args:
            state: Current conversation state

        Returns:
            State updates: current_question, messages, has_more_questions
        """
        try:
            interview_id = UUID(state["interview_id"])

            # Load interview
            interview = await self.interview_repo.get_by_id(interview_id)
            if not interview:
                logger.error(f"Interview {interview_id} not found")
                return {"errors": [f"Interview {interview_id} not found"], "complete": True}

            # Transition to QUESTIONING
            interview.start()
            await self.interview_repo.update(interview)

            # Get first question
            current_iq = await self.interview_repo.get_current_question(interview_id)
            if not current_iq:
                logger.error(f"No questions in interview {interview_id}")
                return {"errors": ["No questions in interview"], "complete": True}

            question = await self.question_repo.get_by_id(current_iq.question_id)
            if not question:
                logger.error(f"Question {current_iq.question_id} not found")
                return {"errors": [f"Question {current_iq.question_id} not found"], "complete": True}

            # Check if more questions exist
            total_questions = await self.interview_repo.count_interview_questions(interview_id)
            has_more = interview.current_question_index < total_questions - 1

            logger.info(
                f"Session started for interview {interview_id}, first question: {question.id}",
                extra={"interview_id": str(interview_id), "question_id": str(question.id)},
            )

            return {
                "current_question_id": str(question.id),
                "current_question": {
                    **question.model_dump(mode="json"),
                    "index": interview.current_question_index,  # WebSocket compatibility (Phase 2)
                    "total": total_questions,  # WebSocket compatibility (Phase 2)
                },
                "messages": [],  # Empty conversation
                "has_more_questions": has_more,
                "followup_count": 0,
                "cumulative_gaps": [],
                "answers": [],
                "evaluations": [],
                "errors": [],
                "retry_count": 0,
                "summary": None,
                "final_status": None,
            }

        except Exception as exc:
            logger.error(f"start_session_node failed: {exc}", exc_info=True)
            return {
                "errors": state.get("errors", []) + [f"start_session: {str(exc)}"],
                "complete": True,
            }

    async def _evaluate_answer_node(self, state: ConversationState) -> dict[str, Any]:
        """Evaluate answer with adaptive evaluation (Phase 2).

        Mirrors ProcessAnswerAdaptiveUseCase.execute() logic:
        - For main questions (attempt 1): Standard evaluation, no penalty
        - For follow-up questions (attempts 2-3): Context-aware evaluation with penalties

        Args:
            state: Current conversation state

        Returns:
            State updates: answers, evaluations
        """
        try:
            # Validate input
            current_question_dict = state.get("current_question")
            if not current_question_dict:
                logger.error("No current question in state")
                return {"errors": state.get("errors", []) + ["No current question"]}

            answer_text = state.get("pending_answer_text")
            if not answer_text:
                logger.warning("No pending answer text in state")
                return {}

            # Step 1: Validate interview
            interview_id = UUID(state["interview_id"])
            interview = await self.interview_repo.get_by_id(interview_id)
            if not interview:
                logger.error(f"Interview {interview_id} not found")
                return {"errors": state.get("errors", []) + [f"Interview {interview_id} not found"]}

            # Transition from QUESTIONING to EVALUATING if needed
            if interview.status == InterviewStatus.QUESTIONING:
                interview.mark_evaluating()
                await self.interview_repo.update(interview)
                logger.info(f"Interview {interview_id} transitioned to EVALUATING status")

            # Step 2: Detect if this is a follow-up question
            parent_question_id_str = state.get("parent_question_id")
            is_followup = parent_question_id_str is not None
            parent_question_id = UUID(parent_question_id_str) if is_followup else None

            # Step 3: Get question (main or follow-up parent)
            if is_followup:
                if parent_question_id is None:
                    logger.error("parent_question_id is None for follow-up")
                    return {"errors": state.get("errors", []) + ["parent_question_id is None"]}
                question = await self.question_repo.get_by_id(parent_question_id)
                if not question:
                    logger.error(f"Parent question {parent_question_id} not found")
                    return {"errors": state.get("errors", []) + [f"Parent question {parent_question_id} not found"]}
                logger.debug(f"Loaded parent question {parent_question_id} for follow-up evaluation")
            else:
                # Main question - reconstruct from state
                question = Question(**current_question_dict)

            # Step 4: Build follow-up context if applicable
            followup_context = None
            if is_followup:
                followup_context = self._build_followup_context_from_state(state)
                if followup_context:
                    logger.debug(
                        f"Follow-up context: attempt={followup_context.attempt_number}, "
                        f"prev_scores={followup_context.previous_scores}, "
                        f"gaps={len(followup_context.cumulative_gaps)}"
                    )

            # Step 5: Create answer entity (simplified - no embedded evaluation)
            # For follow-up questions, use parent_question_id to satisfy FK constraint
            if is_followup:
                if parent_question_id is None:
                    logger.error("parent_question_id is None when creating answer")
                    return {"errors": state.get("errors", []) + ["parent_question_id is None"]}
                answer_question_id = parent_question_id
            else:
                answer_question_id = UUID(state["current_question_id"])

            answer = Answer(
                interview_id=interview_id,
                question_id=answer_question_id,  # Use parent question ID for follow-ups
                text=answer_text,
                is_voice=state.get("is_voice_answer", False),
                voice_metrics=state.get("voice_metrics"),
                created_at=datetime.utcnow(),
            )

            # Step 6: Evaluate answer using LLM (with follow-up context if applicable)
            conversation_history = [
                {"role": msg["type"], "content": msg["content"]}
                for msg in state.get("messages", [])
            ]
            context: dict[str, Any] = {
                "interview_id": state["interview_id"],
                "candidate_id": state["candidate_id"],
                "conversation_history": conversation_history,
            }

            llm_eval = await self.llm.evaluate_answer(
                question=question,
                answer_text=answer_text,
                context=context,
                followup_context=followup_context,
            )

            # Step 7: Extract similarity score (if ideal_answer exists)
            similarity_score = None
            if question.has_ideal_answer() and llm_eval.semantic_similarity is not None:
                similarity_score = max(0.01, llm_eval.semantic_similarity)  # Avoid zero
                logger.info(f"Similarity score: {similarity_score:.2f}")

            # Step 8: Detect gaps
            ideal_answer = question.ideal_answer or ""
            gaps_dict = await self._detect_gaps_hybrid(
                answer_text=answer_text,
                ideal_answer=ideal_answer,
                question_text=question.text,
            )

            # Step 9: Determine attempt number and parent evaluation
            attempt_number = followup_context.attempt_number if followup_context else 1
            parent_evaluation_id = (
                followup_context.previous_evaluations[0].id
                if followup_context and followup_context.previous_evaluations
                else None
            )

            # Step 10: Create Evaluation entity
            evaluation = Evaluation(
                answer_id=answer.id,  # Will link after saving answer
                question_id=UUID(state["current_question_id"] or ""),  # Keep follow-up question ID
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

            # Step 11: Apply penalty based on attempt number
            evaluation.apply_penalty(attempt_number)
            logger.info(
                f"Penalty applied: attempt={attempt_number}, penalty={evaluation.penalty}, "
                f"raw_score={llm_eval.score:.1f}, final_score={evaluation.final_score:.1f}"
            )

            # Step 12: Check if gaps should be resolved
            if evaluation.is_gap_resolved_by_criteria():
                evaluation.resolve_gaps()
                logger.info(
                    f"Gaps resolved by criteria: completeness={evaluation.completeness:.2f}, "
                    f"final_score={evaluation.final_score:.1f}, attempt={attempt_number}"
                )

            # Step 13: Save answer first (to get ID)
            saved_answer = await self.answer_repo.save(answer)

            # Step 14: Update evaluation with correct answer_id and gap evaluation_ids
            evaluation.answer_id = saved_answer.id
            for gap in evaluation.gaps:
                gap.evaluation_id = evaluation.id

            # Step 15: Save evaluation
            saved_evaluation = await self.evaluation_repo.save(evaluation)

            logger.info(
                f"Answer processed: score={saved_evaluation.final_score:.1f}, "
                f"similarity={f'{similarity_score:.2f}' if similarity_score is not None else 'N/A'}, "
                f"gaps={len(saved_evaluation.gaps)}"
            )

            return {
                "answers": state.get("answers", []) + [saved_answer.model_dump(mode="json")],
                "evaluations": state.get("evaluations", []) + [saved_evaluation.model_dump(mode="json")],
                "pending_answer_text": None,  # Clear pending answer
            }

        except Exception as exc:
            logger.error(f"evaluate_answer_node failed: {exc}", exc_info=True)
            return {
                "errors": state.get("errors", []) + [f"evaluate_answer: {str(exc)}"],
                "retry_count": state.get("retry_count", 0) + 1,
            }

    async def _update_memory_node(self, state: ConversationState) -> dict[str, Any]:
        """Append Q&A to conversation memory with truncation.

        Adds question and answer to conversation history, truncates to last 10 messages.

        Args:
            state: Current conversation state

        Returns:
            State updates: messages (truncated)
        """
        try:
            messages = state.get("messages", [])

            # Add question (AI message)
            current_question_dict = state.get("current_question")
            if not current_question_dict:
                logger.warning("No current question in state for memory update")
                return {}

            messages.append(
                {
                    "type": "ai",
                    "content": current_question_dict["text"],
                    "additional_kwargs": {
                        "question_id": state["current_question_id"],
                        "question_type": current_question_dict.get("question_type"),
                    },
                }
            )

            # Add answer (Human message)
            latest_answer = state["answers"][-1]
            messages.append(
                {
                    "type": "human",
                    "content": latest_answer["text"],
                    "additional_kwargs": {
                        "answer_id": latest_answer["id"],
                        "score": state["evaluations"][-1]["final_score"],
                    },
                }
            )

            # Truncate to last N messages (from Phase 0 benchmark)
            max_messages = 10  # 5 Q&A pairs
            if len(messages) > max_messages:
                logger.info(f"Truncating conversation memory from {len(messages)} to {max_messages}")
                messages = messages[-max_messages:]

            return {"messages": messages}

        except Exception as exc:
            logger.error(f"update_memory_node failed: {exc}", exc_info=True)
            return {
                "errors": state.get("errors", []) + [f"update_memory: {str(exc)}"],
            }

    async def _decide_followup_node(self, state: ConversationState) -> dict[str, Any]:
        """Decide if follow-up question needed.

        Break conditions (aligned with FollowUpDecisionUseCase):
        1. followup_count >= 3 (max reached)
        2. evaluation.is_adaptive_complete() (similarity >= 0.8 OR no gaps)

        Uses domain method for consistency with legacy path.

        Args:
            state: Current conversation state

        Returns:
            State updates: needs_followup, cumulative_gaps, followup_reason
        """
        try:
            followup_count = state.get("followup_count", 0)
            latest_eval_dict = state["evaluations"][-1]

            # Break condition 1: Max follow-ups
            if followup_count >= 3:
                logger.info(f"Max follow-ups reached ({followup_count})")
                return {"needs_followup": False, "followup_reason": "Max follow-ups reached"}

            # Reconstruct Evaluation entity to call domain method
            evaluation = Evaluation(**latest_eval_dict)

            # Break condition 2: Adaptive completion criteria (domain method)
            if evaluation.is_adaptive_complete():
                reason = (
                    f"Answer meets completion criteria: "
                    f"similarity={evaluation.similarity_score:.2f}"
                    if evaluation.similarity_score is not None and evaluation.similarity_score >= 0.8
                    else "No unresolved gaps"
                )
                logger.info(reason)
                return {"needs_followup": False, "followup_reason": reason}

            # Accumulate gaps from unresolved
            unresolved_gaps = [
                gap for gap in evaluation.gaps if not gap.resolved
            ]

            cumulative = state.get("cumulative_gaps", [])
            for gap in unresolved_gaps:
                if gap.concept and gap.concept not in cumulative:
                    cumulative.append(gap.concept)

            logger.info(
                f"Follow-up needed: {len(unresolved_gaps)} gaps detected",
                extra={"gaps": cumulative},
            )

            return {
                "needs_followup": True,
                "cumulative_gaps": cumulative,
                "followup_reason": f"Detected {len(unresolved_gaps)} gaps",
            }

        except Exception as exc:
            logger.error(f"decide_followup_node failed: {exc}", exc_info=True)
            return {
                "errors": state.get("errors", []) + [f"decide_followup: {str(exc)}"],
                "needs_followup": False,
            }

    async def _generate_followup_node(self, state: ConversationState) -> dict[str, Any]:
        """Generate follow-up question and transition state.

        Creates FollowUpQuestion entity and updates interview state.

        Args:
            state: Current conversation state

        Returns:
            State updates: current_question, followup_count, needs_followup
        """
        try:
            interview_id = UUID(state["interview_id"])
            current_q_id = state.get("current_question_id")
            if not current_q_id:
                logger.error("No current_question_id for follow-up generation")
                return {"errors": state.get("errors", []) + ["No current_question_id"], "needs_followup": False}

            parent_question_id = UUID(current_q_id)
            followup_count = state.get("followup_count", 0)

            # Get parent question
            current_question_dict = state.get("current_question")
            if not current_question_dict:
                logger.error("No current question in state")
                return {"errors": state.get("errors", []) + ["No current question"], "needs_followup": False}

            parent_question = Question(**current_question_dict)
            answers_list = state.get("answers", [])
            if not answers_list:
                logger.error("No answers in state")
                return {"errors": state.get("errors", []) + ["No answers"], "needs_followup": False}

            latest_answer = answers_list[-1]

            # Determine severity from latest evaluation
            latest_eval = state["evaluations"][-1]
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

            # Generate follow-up text
            followup_text = await self.llm.generate_followup_question(
                parent_question=parent_question.text,
                answer_text=latest_answer["text"],
                missing_concepts=state["cumulative_gaps"],
                severity=severity,
                order=followup_count + 1,
                cumulative_gaps=state["cumulative_gaps"],
            )

            # Create FollowUpQuestion entity
            followup_reason = state.get("followup_reason") or "Gap detected"
            followup = FollowUpQuestion(
                parent_question_id=parent_question_id,
                interview_id=interview_id,
                text=followup_text,
                generated_reason=followup_reason,
                order_in_sequence=followup_count + 1,
            )
            await self.followup_repo.save(followup)

            # Update interview state (FOLLOW_UP transition)
            interview = await self.interview_repo.get_by_id(interview_id)
            if not interview:
                logger.error(f"Interview {interview_id} not found during follow-up generation")
                return {"errors": state.get("errors", []) + [f"Interview {interview_id} not found"], "needs_followup": False}

            interview.ask_followup(followup.id, parent_question_id)
            await self.interview_repo.update(interview)

            logger.info(
                f"Follow-up generated: {followup.id} (order {followup.order_in_sequence})",
                extra={
                    "followup_id": str(followup.id),
                    "parent_id": str(parent_question_id),
                    "severity": severity,
                },
            )

            # Extract ideal_answer from parent question (in state) for gap detection
            parent_question_dict = state.get("current_question") or {}
            ideal_answer = parent_question_dict.get("ideal_answer") or ""

            if not ideal_answer:
                logger.warning(
                    f"No ideal_answer in state for parent question {parent_question_id}, "
                    f"gap detection will be skipped for follow-up"
                )
            else:
                logger.debug(f"Extracted ideal_answer from state for follow-up generation")

            return {
                "current_question_id": str(followup.id),
                "current_question": {
                    "id": str(followup.id),
                    "text": followup.text,
                    "question_type": "FOLLOW_UP",
                    "ideal_answer": ideal_answer,  # NEW: Pass parent's ideal_answer
                    "parent_question_id": str(parent_question_id),  # WebSocket compatibility (Phase 2)
                    "generated_reason": followup.generated_reason,  # WebSocket compatibility
                    "order_in_sequence": followup.order_in_sequence,  # WebSocket compatibility
                },
                "parent_question_id": str(parent_question_id),
                "followup_count": followup_count + 1,
                "needs_followup": False,  # Reset for next cycle
            }

        except Exception as exc:
            logger.error(f"generate_followup_node failed: {exc}", exc_info=True)
            return {
                "errors": state.get("errors", []) + [f"generate_followup: {str(exc)}"],
                "needs_followup": False,  # Skip follow-up on error
            }

    async def _next_question_or_complete_node(self, state: ConversationState) -> dict[str, Any]:
        """Load next question or mark for completion.

        Transitions interview state and loads next main question if available.

        Args:
            state: Current conversation state

        Returns:
            State updates: current_question, has_more_questions, complete
        """
        try:
            interview_id = UUID(state["interview_id"])

            # Check if more questions exist
            if not state.get("has_more_questions"):
                logger.info(f"No more questions, completing interview {interview_id}")
                return {"complete": True}

            # Transition interview state (QUESTIONING)
            interview = await self.interview_repo.get_by_id(interview_id)
            if not interview:
                logger.error(f"Interview {interview_id} not found")
                return {"errors": state.get("errors", []) + [f"Interview {interview_id} not found"], "complete": True}

            interview.proceed_to_next_question()
            await self.interview_repo.update(interview)

            # Get next question
            current_iq = await self.interview_repo.get_current_question(interview_id)
            if not current_iq:
                logger.info(f"No more questions (after proceed), completing interview")
                return {"complete": True}

            question = await self.question_repo.get_by_id(current_iq.question_id)
            if not question:
                logger.error(f"Question {current_iq.question_id} not found")
                return {"errors": state.get("errors", []) + [f"Question {current_iq.question_id} not found"], "complete": True}

            # Update has_more_questions
            total = await self.interview_repo.count_interview_questions(interview_id)
            has_more = interview.current_question_index < total - 1

            logger.info(
                f"Next question loaded: {question.id} (index {interview.current_question_index})",
                extra={"question_id": str(question.id), "has_more": has_more},
            )

            return {
                "current_question_id": str(question.id),
                "current_question": {
                    **question.model_dump(mode="json"),  # All question fields
                    "index": interview.current_question_index,  # WebSocket compatibility (Phase 2)
                    "total": total,  # WebSocket compatibility (Phase 2)
                },
                "parent_question_id": None,  # Reset (new main question)
                "followup_count": 0,  # Reset counter
                "cumulative_gaps": [],  # Reset gaps
                "has_more_questions": has_more,
            }

        except Exception as exc:
            logger.error(f"next_question_or_complete_node failed: {exc}", exc_info=True)
            return {
                "errors": state.get("errors", []) + [f"next_question: {str(exc)}"],
                "complete": True,  # Force completion on error
            }

    async def _complete_interview_node(self, state: ConversationState) -> dict[str, Any]:
        """Generate summary and finalize interview.

        Delegates to CompleteInterviewUseCase (REUSED from current implementation).

        Args:
            state: Current conversation state

        Returns:
            State updates: complete, summary, final_status
        """
        try:
            from ...application.use_cases.complete_interview import CompleteInterviewUseCase

            interview_id = UUID(state["interview_id"])

            # Call existing use case
            complete_uc = CompleteInterviewUseCase(
                interview_repository=self.interview_repo,
                answer_repository=self.answer_repo,
                question_repository=self.question_repo,
                follow_up_question_repository=self.followup_repo,
                evaluation_repository=self.evaluation_repo,
                llm=self.llm,
            )

            result = await complete_uc.execute(interview_id)

            # Cleanup checkpoints (no retention in dev mode)
            thread_id = state.get("checkpoint_thread_id")
            if thread_id:
                try:
                    # Note: AsyncPostgresSaver doesn't have delete_thread method
                    # Checkpoints will be cleaned up by retention policy or manual cleanup
                    logger.info(f"Interview completed, checkpoint thread: {thread_id}")
                except Exception as cleanup_exc:
                    logger.warning(f"Checkpoint cleanup failed: {cleanup_exc}")

            logger.info(
                f"Interview completed: {interview_id}, status: {result.interview.status.value}",
                extra={"interview_id": str(interview_id), "status": result.interview.status.value},
            )

            return {
                "complete": True,
                "summary": result.summary.model_dump(mode="json"),
                "final_status": result.interview.status.value,
            }

        except Exception as exc:
            logger.error(f"complete_interview_node failed: {exc}", exc_info=True)
            return {
                "errors": state.get("errors", []) + [f"complete_interview: {str(exc)}"],
                "complete": True,  # Mark as complete even on error
            }

    # ========== HELPER METHODS FOR GAP DETECTION ==========

    async def _detect_gaps_hybrid(
        self,
        answer_text: str,
        ideal_answer: str,
        question_text: str,
    ) -> dict[str, Any]:
        """Detect concept gaps using hybrid approach (keywords + LLM).

        Step 1: Fast keyword-based detection
        Step 2: If keywords found gaps, confirm with LLM

        Args:
            answer_text: Candidate's answer
            ideal_answer: Reference ideal answer
            question_text: The question asked

        Returns:
            Gaps dict with detected concepts and severity
            Format: {"concepts": [...], "confirmed": bool, "severity": str}
        """
        # Step 1: Keyword-based gap detection
        keyword_gaps = self._detect_keyword_gaps(answer_text, ideal_answer)

        logger.debug(f"Gap detection: keyword_gaps={len(keyword_gaps)}")

        # Step 2: If keywords detected gaps, confirm with LLM
        if keyword_gaps:
            llm_gaps = await self.llm.detect_concept_gaps(
                answer_text=answer_text,
                ideal_answer=ideal_answer,
                question_text=question_text,
                keyword_gaps=keyword_gaps,
            )
            if llm_gaps.get("confirmed"):
                logger.info(f"Gaps confirmed by LLM: {llm_gaps['concepts']}")
            return llm_gaps
        else:
            return {"concepts": [], "confirmed": False, "severity": "minor"}

    def _detect_keyword_gaps(self, answer_text: str, ideal_answer: str) -> list[str]:
        """Fast keyword-based gap detection.

        Extracts words from ideal_answer that are missing in answer_text.
        Filters:
        - Word length > 3 chars
        - Not in stop words list
        - Case-insensitive

        Args:
            answer_text: Candidate's answer
            ideal_answer: Reference ideal answer

        Returns:
            List of missing words (empty if < 4 missing words)
        """
        stop_words = {
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
            "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
            "being", "have", "has", "had", "do", "does", "did", "will", "would",
            "should", "could", "may", "might", "must", "can", "this", "that",
            "these", "those",
        }

        # Extract words from ideal answer (>3 chars, not stop words)
        ideal_words = {
            word.lower().strip('.,!?;:"\'-')
            for word in ideal_answer.split()
            if len(word.strip('.,!?;:"\'-')) > 3
            and word.lower().strip('.,!?;:"\'-') not in stop_words
        }

        # Extract words from answer
        answer_words = {
            word.lower().strip('.,!?;:"\'-')
            for word in answer_text.split()
            if len(word.strip('.,!?;:"\'-')) > 3
            and word.lower().strip('.,!?;:"\'-') not in stop_words
        }

        # Find missing words
        missing = list(ideal_words - answer_words)

        # Return only if significant gaps (> 3 missing words)
        return missing if len(missing) > 3 else []

    def _determine_gap_severity(
        self,
        concept: str,
        gaps_dict: dict[str, Any],
    ) -> GapSeverity:
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

    def _build_followup_context_from_state(
        self,
        state: ConversationState,
    ) -> FollowUpEvaluationContext | None:
        """Build follow-up evaluation context from workflow state.

        Extracts previous evaluations, gaps, and scores from state
        (no database queries).

        Args:
            state: Current conversation state

        Returns:
            FollowUpEvaluationContext if follow-up question, None if main question
        """
        # Check if this is a follow-up question
        parent_question_id = state.get("parent_question_id")
        if not parent_question_id:
            return None  # Main question, no context needed

        # Extract IDs
        current_q_id = state.get("current_question_id")
        if not current_q_id:
            logger.warning("No current_question_id in state for follow-up context")
            return None

        # Get follow-up count (attempt number)
        followup_count = state.get("followup_count", 0)
        attempt_number = followup_count  # 2 or 3

        # Extract previous evaluations from state
        evaluations_dicts = state.get("evaluations", [])
        previous_evaluations: list[Evaluation] = []

        for eval_dict in evaluations_dicts:
            try:
                # Filter evaluations for current question chain
                eval_q_id = eval_dict.get("question_id")
                if eval_q_id in [parent_question_id, current_q_id]:
                    evaluation = Evaluation(**eval_dict)
                    previous_evaluations.append(evaluation)
            except Exception as exc:
                logger.warning(f"Failed to parse evaluation from state: {exc}")
                continue

        # Sort by created_at
        previous_evaluations.sort(key=lambda e: e.created_at)

        # Extract cumulative gaps from state
        gap_concepts = state.get("cumulative_gaps", [])
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

        # Extract ideal_answer from current_question in state
        current_question = state.get("current_question")
        ideal_answer = current_question.get("ideal_answer", "") if current_question else ""

        if not ideal_answer:
            logger.warning("No ideal_answer in state for follow-up context")

        # Extract previous scores
        previous_scores = [e.final_score for e in previous_evaluations]

        # Build context
        try:
            context = FollowUpEvaluationContext(
                parent_question_id=UUID(parent_question_id),
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

    # ========== CONDITIONAL EDGE FUNCTIONS ==========

    def _route_entry_point(self, state: ConversationState) -> str:
        """Route based on whether this is new session or answer processing.

        Args:
            state: Current conversation state

        Returns:
            "start_session" if no pending answer (new session)
            "evaluate_answer" if pending answer exists (continuing workflow)
        """
        has_pending_answer = bool(state.get("pending_answer_text"))
        return "evaluate_answer" if has_pending_answer else "start_session"

    def _should_generate_followup(self, state: ConversationState) -> str:
        """Route after decide_followup_node.

        Args:
            state: Current conversation state

        Returns:
            "generate_followup" if needs_followup, else "next_or_complete"
        """
        return "generate_followup" if state.get("needs_followup") else "next_or_complete"

    def _should_complete(self, state: ConversationState) -> str:
        """Route after next_question_or_complete_node.

        Args:
            state: Current conversation state

        Returns:
            "complete" if complete flag set, else "wait_for_answer"
        """
        return "complete" if state.get("complete") else "wait_for_answer"

    # ========== PUBLIC API ==========

    async def get_workflow_state(self, thread_id: str) -> dict[str, Any] | None:
        """Retrieve workflow state from checkpoint using compiled app.

        Overrides base class method to use app.aget_state() which is the
        recommended way to retrieve state from LangGraph checkpoints.

        Args:
            thread_id: Thread ID of the workflow execution

        Returns:
            Workflow state dict if checkpoint exists, None otherwise
        """
        try:
            config: dict[str, Any] = {"configurable": {"thread_id": thread_id}}

            # Use compiled app's aget_state() method (recommended approach)
            state_snapshot = await self.app.aget_state(config)  # type: ignore[arg-type]

            if state_snapshot is None:
                logger.debug(f"No checkpoint found for thread {thread_id}")
                return None

            # StateSnapshot has .values that contains the state dict
            # It might be a property or a method
            if hasattr(state_snapshot, "values"):
                values_attr = getattr(state_snapshot, "values")

                # Try as property first
                if not callable(values_attr):
                    state = values_attr
                else:
                    # It's a method - call it (might be async or sync)
                    try:
                        if hasattr(values_attr, "__await__"):
                            state = await values_attr()
                        else:
                            state = values_attr()
                    except Exception as e:
                        logger.warning(
                            f"Error calling state_snapshot.values(): {e}, "
                            f"trying as property"
                        )
                        # Fallback: try accessing as property
                        state = state_snapshot.values

                # Validate and return
                if isinstance(state, dict):
                    return state
                else:
                    logger.warning(
                        f"StateSnapshot.values is not a dict: {type(state)}. "
                        f"Trying to access state directly from snapshot."
                    )
                    # Last resort: check if snapshot itself is dict-like
                    if isinstance(state_snapshot, dict):
                        return state_snapshot
                    return None
            else:
                # Try accessing state directly if snapshot is dict-like
                if isinstance(state_snapshot, dict):
                    return state_snapshot

                logger.warning(
                    f"StateSnapshot does not have 'values' attribute: {type(state_snapshot)}. "
                    f"Available attributes: {[attr for attr in dir(state_snapshot) if not attr.startswith('_')][:10]}"
                )
                return None

        except Exception as e:
            logger.error(
                f"Failed to retrieve workflow state for thread {thread_id}: {self.format_error(e)}",
                exc_info=True
            )
            return None

    async def start_session(self, interview_id: UUID, candidate_id: UUID) -> dict[str, Any]:
        """Start conversation workflow and send first question.

        Args:
            interview_id: Interview UUID
            candidate_id: Candidate UUID

        Returns:
            Dict with question, thread_id, and workflow state
        """
        try:
            # Generate thread ID
            thread_id = self.generate_thread_id(f"interview_{interview_id}")

            # Initialize state
            initial_state: ConversationState = {
                "interview_id": str(interview_id),
                "candidate_id": str(candidate_id),
                "messages": [],
                "current_question_id": None,
                "current_question": None,
                "parent_question_id": None,
                "pending_answer_text": None,
                "is_voice_answer": False,
                "voice_metrics": None,
                "answers": [],
                "evaluations": [],
                "followup_count": 0,
                "cumulative_gaps": [],
                "has_more_questions": False,
                "needs_followup": False,
                "complete": False,
                "followup_reason": None,
                "summary": None,
                "final_status": None,
                "errors": [],
                "retry_count": 0,
                "checkpoint_thread_id": thread_id,
                "last_checkpoint_time": None,
            }

            # Execute workflow (only start_session node)
            config: dict[str, Any] = {"configurable": {"thread_id": thread_id}}
            result = await self.app.ainvoke(initial_state, config)  # type: ignore[arg-type]

            logger.info(
                f"Session started for interview {interview_id}, thread: {thread_id}",
                extra={"interview_id": str(interview_id), "thread_id": thread_id},
            )

            return {
                "thread_id": thread_id,
                "question": result.get("current_question"),
                "question_id": result.get("current_question_id"),
                "has_more": result.get("has_more_questions"),
                "errors": result.get("errors", []),
            }

        except Exception as exc:
            logger.error(f"start_session failed: {exc}", exc_info=True)
            raise

    async def process_answer(
        self,
        thread_id: str,
        answer_text: str,
        is_voice: bool = False,
        voice_metrics: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Process answer and continue workflow.

        Resumes from checkpoint, evaluates answer, and progresses through workflow.

        Args:
            thread_id: Thread ID from start_session
            answer_text: Answer text from candidate
            is_voice: Whether answer was voice input
            voice_metrics: Voice metrics (if applicable)

        Returns:
            Dict with next question (if follow-up), completion status, or summary
        """
        try:
            # Update state with pending answer
            config: dict[str, Any] = {"configurable": {"thread_id": thread_id}}

            # Get current state
            current_state = await self.get_workflow_state(thread_id)
            if not current_state:
                raise ValueError(f"No workflow state found for thread {thread_id}")

            # Inject answer into state
            current_state["pending_answer_text"] = answer_text
            current_state["is_voice_answer"] = is_voice
            current_state["voice_metrics"] = voice_metrics

            # Continue workflow from checkpoint
            result = await self.app.ainvoke(current_state, config)  # type: ignore[arg-type]

            logger.info(
                f"Answer processed, thread: {thread_id}, complete: {result.get('complete')}",
                extra={
                    "thread_id": thread_id,
                    "complete": result.get("complete"),
                    "needs_followup": result.get("needs_followup"),
                },
            )

            return {
                "complete": result.get("complete", False),
                "question": result.get("current_question"),
                "question_id": result.get("current_question_id"),
                "summary": result.get("summary"),
                "final_status": result.get("final_status"),
                "has_more": result.get("has_more_questions"),
                "errors": result.get("errors", []),
                # NEW: Add evaluation data for client display
                "evaluation": self._extract_latest_evaluation(result),
            }

        except Exception as exc:
            logger.error(f"process_answer failed: {exc}", exc_info=True)
            raise

    def _extract_latest_evaluation(self, result: dict[str, Any]) -> dict[str, Any] | None:
        """Extract latest evaluation from workflow state.

        Args:
            result: Workflow execution result containing state

        Returns:
            Evaluation dict with score, feedback, strengths, weaknesses, gaps
            None if no evaluations in state
        """
        evaluations = result.get("evaluations", [])
        if not evaluations:
            return None

        latest_eval = evaluations[-1]  # Last evaluation in list

        return {
            "answer_id": latest_eval.get("answer_id"),
            "score": latest_eval.get("final_score"),
            "feedback": latest_eval.get("reasoning"),
            "strengths": latest_eval.get("strengths", []),
            "weaknesses": latest_eval.get("weaknesses", []),
            "gaps": latest_eval.get("gaps", []),
        }

    def visualize_graph(self, output_format: str = "mermaid") -> str | bytes:
        """Visualize the workflow graph.

        Args:
            output_format: "mermaid" (text), "mermaid_png" (PNG bytes), or "ascii" (text)

        Returns:
            Mermaid diagram text, PNG bytes, or ASCII diagram

        Example:
            >>> workflow = InterviewConversationWorkflow(...)
            >>> mermaid_text = workflow.visualize_graph("mermaid")
            >>> with open("workflow.mmd", "w") as f:
            ...     f.write(mermaid_text)
            >>>
            >>> # Or export PNG
            >>> png_bytes = workflow.visualize_graph("mermaid_png")
            >>> with open("workflow.png", "wb") as f:
            ...     f.write(png_bytes)
        """
        graph = self.app.get_graph()

        if output_format == "mermaid":
            return graph.draw_mermaid()
        elif output_format == "mermaid_png":
            return graph.draw_mermaid_png()
        elif output_format == "ascii":
            return graph.draw_ascii()
        else:
            raise ValueError(f"Unknown format: {output_format}. Use 'mermaid', 'mermaid_png', or 'ascii'")

    async def execute(self, *args: Any, **kwargs: Any) -> Any:
        """Execute workflow (required by BaseWorkflow).

        Use start_session() and process_answer() instead for conversation workflow.
        """
        raise NotImplementedError("Use start_session() and process_answer() for conversation workflow")
