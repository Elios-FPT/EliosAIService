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
from uuid import UUID

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import StateSnapshot

from ...domain.models.answer import Answer
from ...domain.models.evaluation import Evaluation, ConceptGap
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
                "current_question": question.model_dump(mode="json"),
                "messages": [],  # Empty conversation
                "has_more_questions": has_more,
                "followup_count": 0,
                "cumulative_gaps": [],
                "answers": [],
                "evaluations": [],
                "errors": [],
                "retry_count": 0,
            }

        except Exception as exc:
            logger.error(f"start_session_node failed: {exc}", exc_info=True)
            return {
                "errors": state.get("errors", []) + [f"start_session: {str(exc)}"],
                "complete": True,
            }

    async def _evaluate_answer_node(self, state: ConversationState) -> dict[str, Any]:
        """Evaluate answer with conversation context.

        Uses LangChain adapter with conversation_history in context.

        Args:
            state: Current conversation state

        Returns:
            State updates: answers, evaluations
        """
        try:
            # Reconstruct domain objects
            current_question_dict = state.get("current_question")
            if not current_question_dict:
                logger.error("No current question in state")
                return {"errors": state.get("errors", []) + ["No current question"]}

            question = Question(**current_question_dict)
            answer_text = state.get("pending_answer_text")

            if not answer_text:
                logger.warning("No pending answer text in state")
                return {}

            # Build context with conversation history
            conversation_history = [
                {"role": msg["type"], "content": msg["content"]}
                for msg in state.get("messages", [])
            ]

            context: dict[str, Any] = {
                "interview_id": state["interview_id"],
                "candidate_id": state["candidate_id"],
                "conversation_history": conversation_history,
            }

            # Call LLM adapter (UNCHANGED API)
            evaluation_result = await self.llm.evaluate_answer(
                question=question,
                answer_text=answer_text,
                context=context,
            )

            # Create Answer entity
            answer = Answer(
                interview_id=UUID(state["interview_id"]),
                question_id=UUID(state["current_question_id"] or ""),
                text=answer_text,
                is_voice=state.get("is_voice_answer", False),
                voice_metrics=state.get("voice_metrics"),
            )
            await self.answer_repo.save(answer)

            # Create Evaluation entity with all required fields
            evaluation = Evaluation(
                answer_id=answer.id,
                question_id=UUID(state["current_question_id"] or ""),
                interview_id=UUID(state["interview_id"]),
                raw_score=evaluation_result.score,
                penalty=0.0,  # No penalty for now (workflow simplified)
                final_score=evaluation_result.score,
                similarity_score=evaluation_result.semantic_similarity,
                completeness=evaluation_result.completeness,
                relevance=evaluation_result.relevance,
                sentiment=evaluation_result.sentiment,
                reasoning=evaluation_result.reasoning,
                strengths=evaluation_result.strengths,
                weaknesses=evaluation_result.weaknesses,
                improvement_suggestions=evaluation_result.improvement_suggestions,
                attempt_number=1,  # Simplified for initial migration
                gaps=[],  # Gap detection can be added later
                evaluated_at=datetime.utcnow(),
            )
            await self.evaluation_repo.save(evaluation)

            logger.info(
                f"Answer evaluated: {answer.id}, score: {evaluation.final_score}",
                extra={
                    "answer_id": str(answer.id),
                    "score": evaluation.final_score,
                    "gaps_count": len(evaluation.gaps) if evaluation.gaps else 0,
                },
            )

            return {
                "answers": state.get("answers", []) + [answer.model_dump(mode="json")],
                "evaluations": state.get("evaluations", []) + [evaluation.model_dump(mode="json")],
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

        Break conditions (exit if ANY met):
        1. followup_count >= 3 (max reached)
        2. final_score >= 80.0 (quality sufficient)
        3. no unresolved gaps

        Args:
            state: Current conversation state

        Returns:
            State updates: needs_followup, cumulative_gaps, followup_reason
        """
        try:
            followup_count = state.get("followup_count", 0)
            latest_eval = state["evaluations"][-1]

            # Break condition 1: Max follow-ups
            if followup_count >= 3:
                logger.info(f"Max follow-ups reached ({followup_count})")
                return {"needs_followup": False, "followup_reason": "Max follow-ups reached"}

            # Break condition 2: High score
            if latest_eval["final_score"] >= 80.0:
                logger.info(f"Score sufficient: {latest_eval['final_score']}")
                return {"needs_followup": False, "followup_reason": "Score sufficient"}

            # Break condition 3: No gaps
            unresolved_gaps = [
                gap for gap in latest_eval.get("gaps", []) if not gap.get("resolved", False)
            ]
            if not unresolved_gaps:
                logger.info("No gaps detected")
                return {"needs_followup": False, "followup_reason": "No gaps detected"}

            # Accumulate gaps from all evaluations in this cycle
            cumulative = state.get("cumulative_gaps", [])
            for gap in unresolved_gaps:
                concept = gap.get("concept")
                if concept and concept not in cumulative:
                    cumulative.append(concept)

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

            return {
                "current_question_id": str(followup.id),
                "current_question": {
                    "id": str(followup.id),
                    "text": followup.text,
                    "question_type": "FOLLOW_UP",
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
                "current_question": question.model_dump(mode="json"),
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
                "has_more": result.get("has_more_questions"),
                "errors": result.get("errors", []),
            }

        except Exception as exc:
            logger.error(f"process_answer failed: {exc}", exc_info=True)
            raise

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
