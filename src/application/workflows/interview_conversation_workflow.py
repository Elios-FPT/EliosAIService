"""LangGraph workflow for interview conversation (QA phase).

Replaces session_orchestrator.py with stateful workflow for:
- Answer evaluation with conversation memory
- Adaptive follow-up generation
- Question progression
- Interview completion

Uses PostgreSQL checkpointing for state persistence across reconnects.
"""

import logging
from typing import Any, TypedDict
from uuid import UUID

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph.state import CompiledStateGraph

from ...domain.ports.llm_port import LLMPort
from ...domain.ports.answer_repository_port import AnswerRepositoryPort
from ...domain.ports.evaluation_repository_port import EvaluationRepositoryPort
from ...domain.ports.event_publisher_port import EventPublisherPort
from ...domain.ports.interview_repository_port import InterviewRepositoryPort
from ...domain.ports.question_repository_port import QuestionRepositoryPort
from ...domain.ports.follow_up_question_repository_port import FollowUpQuestionRepositoryPort
from ...domain.ports.vector_search_port import VectorSearchPort
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
    parent_question: dict[str, Any] | None  # Original main question for follow-ups
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

    # Performance optimization: Interview caching (Phase 1)
    _cached_interview: dict[str, Any] | None  # Interview.model_dump(mode="json")
    _interview_version: float | None  # interview.updated_at.timestamp() for cache invalidation

    # Performance optimization: Follow-up caching (Phase 2)
    _followup_suggestion: dict[str, Any] | None  # Cached follow-up from unified analysis


class InterviewConversationWorkflow(BaseWorkflow):
    """LangGraph workflow for interview conversation (QA phase).

    Manages stateful interview flow with:
    - 8 nodes (start session, evaluate answer, memory update, follow-up decision,
      follow-up generation, next question, complete interview, index questions)
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
        vector_search: VectorSearchPort,
        llm: LLMPort,
        event_publisher: EventPublisherPort,
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
            event_publisher: Event publisher for domain events
        """
        super().__init__(checkpointer)
        self.interview_repo = interview_repo
        self.question_repo = question_repo
        self.answer_repo = answer_repo
        self.evaluation_repo = evaluation_repo
        self.followup_repo = followup_repo
        self.vector_search = vector_search
        self.llm = llm
        self.event_publisher = event_publisher
        self.app = self._build_graph()

    def _build_graph(self) -> CompiledStateGraph[ConversationState]:
        """Build LangGraph StateGraph with all nodes and edges.

        Workflow structure:
        START → route_entry → [new session?] → start_session → END (wait for answer)
                    ↓
              [has answer?] → evaluate_answer → [follow-up?] → validate_gaps → update_memory
                                                      ↓                    ↓
                                              [main question] ─────────────┘
                                                                           ↓
                                                                  decide_followup
                                                                           ↓
                                                                   [needs_followup?]
                                                                           ↓
                                                                   generate_followup → END
                                                                           ↓
                                                                   next_or_complete → [complete?] → complete → index_questions → END
                                                                           ↓
                                                                   [has_more?] → END

        Returns:
            Compiled StateGraph ready for execution
        """
        # Create graph
        graph = StateGraph(ConversationState)

        # Add nodes
        graph.add_node("route_entry", self._route_entry_node)
        graph.add_node("start_session", self._start_session_node)
        graph.add_node("evaluate_answer", self._evaluate_answer_node)
        graph.add_node("validate_gaps", self._validate_gaps_node)  # Phase 3: Gap validation
        graph.add_node("update_memory", self._update_memory_node)
        graph.add_node("decide_followup", self._decide_followup_node)
        graph.add_node("generate_followup", self._generate_followup_node)
        graph.add_node("next_or_complete", self._next_question_or_complete_node)
        graph.add_node("complete", self._complete_interview_node)
        graph.add_node("index_questions", self._index_questions_node)

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

        # Phase 3: Conditional gap validation (only for follow-ups)
        graph.add_conditional_edges(
            "evaluate_answer",
            lambda state: "validate_gaps" if state.get("parent_question_id") else "update_memory",
            {
                "validate_gaps": "validate_gaps",
                "update_memory": "update_memory",
            },
        )

        # Validation → Memory update
        graph.add_edge("validate_gaps", "update_memory")

        # Memory → Decide
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

        graph.add_edge("complete", "index_questions")
        graph.add_edge("index_questions", END)

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

        Args:
            state: Current conversation state

        Returns:
            State updates: current_question, messages, has_more_questions
        """
        from ...application.use_cases.interview.start_interview_session import StartInterviewSessionUseCase
        from ...application.dto.interview.start_session_dto import StartSessionInput

        try:
            use_case = StartInterviewSessionUseCase(
                interview_repo=self.interview_repo,
                question_repo=self.question_repo,
            )

            input_dto = StartSessionInput(
                interview_id=UUID(state["interview_id"]),
                candidate_id=UUID(state["candidate_id"]),
                cached_interview=state.get("_cached_interview"),
            )

            output = await use_case.execute(input_dto)

            if output.errors:
                return {
                    "errors": output.errors,
                    "complete": output.complete,
                }

            return {
                **output.cache_updates,
                "current_question_id": output.current_question_id,
                "current_question": output.current_question,
                "messages": [],
                "has_more_questions": output.has_more_questions,
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
        """Evaluate answer using unified comprehensive analysis.

        Args:
            state: Current conversation state

        Returns:
            State updates: answers, evaluations, _followup_suggestion
        """
        from ...application.use_cases.interview.evaluate_answer import EvaluateAnswerUseCase
        from ...application.dto.interview.evaluate_answer_dto import EvaluateAnswerInput

        try:
            current_question_dict = state.get("current_question")
            if not current_question_dict:
                logger.error("No current question in state")
                return {"errors": state.get("errors", []) + ["No current question"]}

            answer_text = state.get("pending_answer_text")
            if not answer_text:
                logger.warning("No pending answer text in state")
                return {}

            use_case = EvaluateAnswerUseCase(
                interview_repo=self.interview_repo,
                question_repo=self.question_repo,
                answer_repo=self.answer_repo,
                evaluation_repo=self.evaluation_repo,
                llm=self.llm,
            )

            input_dto = EvaluateAnswerInput(
                interview_id=UUID(state["interview_id"]),
                candidate_id=UUID(state["candidate_id"]),
                question=current_question_dict,
                answer_text=answer_text,
                parent_question_id=UUID(state["parent_question_id"]) if state.get("parent_question_id") else None,
                is_voice=state.get("is_voice_answer", False),
                voice_metrics=state.get("voice_metrics"),
                conversation_history=state.get("messages", []),
                followup_count=state.get("followup_count", 0),
                cumulative_gaps=state.get("cumulative_gaps", []),
                evaluations=state.get("evaluations", []),
                cached_interview=state.get("_cached_interview"),
            )

            output = await use_case.execute(input_dto)

            return {
                **output.cache_updates,
                "answers": state.get("answers", []) + [output.answer],
                "evaluations": state.get("evaluations", []) + [output.evaluation],
                "pending_answer_text": None,
                "_followup_suggestion": output.followup_suggestion,
            }

        except Exception as exc:
            logger.error(f"Unified evaluation failed: {exc}", exc_info=True)
            raise

    async def _validate_gaps_node(self, state: ConversationState) -> dict[str, Any]:
        """Validate cumulative gaps against DB (resume safety check).

        Args:
            state: Current conversation state

        Returns:
            State updates: cumulative_gaps (validated/merged from DB)
        """
        from ...application.use_cases.interview.validate_gaps import ValidateGapsUseCase
        from ...application.dto.interview.validate_gaps_dto import ValidateGapsInput

        try:
            use_case = ValidateGapsUseCase()

            input_dto = ValidateGapsInput(
                interview_id=UUID(state["interview_id"]),
                parent_question_id=UUID(state["parent_question_id"]) if state.get("parent_question_id") else None,
                cumulative_gaps=state.get("cumulative_gaps", []),
                answers=state.get("answers", []),
                evaluations=state.get("evaluations", []),
            )

            output = await use_case.execute(input_dto)

            if output.cumulative_gaps is not None:
                return {"cumulative_gaps": output.cumulative_gaps}

            return {}

        except Exception as exc:
            logger.error(f"Gap validation failed: {exc}", exc_info=True)
            return {}

    async def _update_memory_node(self, state: ConversationState) -> dict[str, Any]:
        """Append Q&A to conversation memory with truncation.

        Args:
            state: Current conversation state

        Returns:
            State updates: messages (truncated)
        """
        from ...application.use_cases.interview.update_conversation_memory import UpdateConversationMemoryUseCase
        from ...application.dto.interview.update_memory_dto import UpdateMemoryInput

        try:
            use_case = UpdateConversationMemoryUseCase()

            input_dto = UpdateMemoryInput(
                messages=state.get("messages", []),
                current_question_id=state.get("current_question_id"),
                current_question=state.get("current_question"),
                latest_answer=state["answers"][-1] if state.get("answers") else None,
                latest_evaluation=state["evaluations"][-1] if state.get("evaluations") else None,
            )

            output = await use_case.execute(input_dto)

            if output.errors:
                return {"errors": state.get("errors", []) + output.errors}

            return {"messages": output.messages}

        except Exception as exc:
            logger.error(f"update_memory_node failed: {exc}", exc_info=True)
            return {"errors": state.get("errors", []) + [f"update_memory: {str(exc)}"]}

    async def _decide_followup_node(self, state: ConversationState) -> dict[str, Any]:
        """Decide if follow-up question needed.

        Args:
            state: Current conversation state

        Returns:
            State updates: needs_followup, cumulative_gaps, followup_reason
        """
        from ...application.use_cases.interview.decide_followup import DecideFollowupUseCase
        from ...application.dto.interview.decide_followup_dto import DecideFollowupInput

        try:
            use_case = DecideFollowupUseCase()

            input_dto = DecideFollowupInput(
                followup_count=state.get("followup_count", 0),
                latest_evaluation=state["evaluations"][-1],
                cumulative_gaps=state.get("cumulative_gaps", []),
            )

            output = await use_case.execute(input_dto)

            result = {
                "needs_followup": output.needs_followup,
                "followup_reason": output.followup_reason,
                "cumulative_gaps": output.cumulative_gaps,
            }

            if output.errors:
                result["errors"] = state.get("errors", []) + output.errors

            return result

        except Exception as exc:
            logger.error(f"decide_followup_node failed: {exc}", exc_info=True)
            return {
                "errors": state.get("errors", []) + [f"decide_followup: {str(exc)}"],
                "needs_followup": False,
            }

    async def _generate_followup_node(self, state: ConversationState) -> dict[str, Any]:
        """Generate follow-up question and transition state.

        Args:
            state: Current conversation state

        Returns:
            State updates: current_question, followup_count, needs_followup
        """
        from ...application.use_cases.interview.generate_followup import GenerateFollowupUseCase
        from ...application.dto.interview.generate_followup_dto import GenerateFollowupInput

        try:
            use_case = GenerateFollowupUseCase(
                interview_repo=self.interview_repo,
                followup_repo=self.followup_repo,
                llm=self.llm,
            )

            input_dto = GenerateFollowupInput(
                interview_id=UUID(state["interview_id"]),
                current_question_id=state.get("current_question_id"),
                parent_question_id=state.get("parent_question_id"),
                current_question=state.get("current_question"),
                parent_question=state.get("parent_question"),
                latest_answer=state["answers"][-1] if state.get("answers") else None,
                latest_evaluation=state["evaluations"][-1] if state.get("evaluations") else None,
                followup_count=state.get("followup_count", 0),
                cumulative_gaps=state.get("cumulative_gaps", []),
                followup_reason=state.get("followup_reason"),
                followup_suggestion=state.get("_followup_suggestion"),
                cached_interview=state.get("_cached_interview"),
            )

            output = await use_case.execute(input_dto)

            if output.errors:
                return {
                    "errors": state.get("errors", []) + output.errors,
                    "needs_followup": False,
                }

            return {
                **output.cache_updates,
                "current_question_id": output.current_question_id,
                "current_question": output.current_question,
                "parent_question_id": output.parent_question_id,
                "parent_question": output.parent_question,
                "followup_count": output.followup_count,
                "needs_followup": output.needs_followup,
            }

        except Exception as exc:
            logger.error(f"generate_followup_node failed: {exc}", exc_info=True)
            return {
                "errors": state.get("errors", []) + [f"generate_followup: {str(exc)}"],
                "needs_followup": False,
            }

    async def _next_question_or_complete_node(self, state: ConversationState) -> dict[str, Any]:
        """Load next question or mark for completion.

        Args:
            state: Current conversation state

        Returns:
            State updates: current_question, has_more_questions, complete
        """
        from ...application.use_cases.interview.load_next_question import LoadNextQuestionUseCase
        from ...application.dto.interview.load_next_question_dto import LoadNextQuestionInput

        try:
            use_case = LoadNextQuestionUseCase(
                interview_repo=self.interview_repo,
                question_repo=self.question_repo,
            )

            input_dto = LoadNextQuestionInput(
                interview_id=UUID(state["interview_id"]),
                has_more_questions=state.get("has_more_questions", False),
                cached_interview=state.get("_cached_interview"),
            )

            output = await use_case.execute(input_dto)

            if output.complete:
                result: dict[str, Any] = {"complete": True}
                if output.errors:
                    result["errors"] = state.get("errors", []) + output.errors
                return result

            return {
                **output.cache_updates,
                "current_question_id": output.current_question_id,
                "current_question": output.current_question,
                "parent_question_id": output.parent_question_id,
                "parent_question": output.parent_question,
                "followup_count": output.followup_count,
                "cumulative_gaps": output.cumulative_gaps,
                "has_more_questions": output.has_more_questions,
            }

        except Exception as exc:
            logger.error(f"next_question_or_complete_node failed: {exc}", exc_info=True)
            return {
                "errors": state.get("errors", []) + [f"next_question: {str(exc)}"],
                "complete": True,
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
                event_publisher=self.event_publisher,
            )

            result = await complete_uc.execute(interview_id)

            # Cleanup checkpoints (no retention in dev mode)
            thread_id = state.get("checkpoint_thread_id")
            if thread_id:
                try:
                    # TODO: Note: AsyncPostgresSaver doesn't have delete_thread method
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

    async def _index_questions_node(self, state: ConversationState) -> dict[str, Any]:
        """Index asked questions to vector database.

        Called after interview completion to add generated questions
        to vector DB for future exemplar search.

        Args:
            state: Current conversation state

        Returns:
            Empty dict (no state updates, non-blocking)
        """
        try:
            from ..use_cases.planning.index_questions_to_vector import (
                IndexQuestionsInput,
                IndexQuestionsToVectorUseCase,
            )

            interview_id = UUID(state["interview_id"])

            index_uc = IndexQuestionsToVectorUseCase(
                vector_search=self.vector_search,
                interview_repo=self.interview_repo,
                question_repo=self.question_repo,
            )

            index_result = await index_uc.execute(IndexQuestionsInput(interview_id=interview_id))

            if index_result.errors:
                logger.warning(
                    "Question indexing completed with errors for %s: %s",
                    interview_id,
                    index_result.errors,
                )
            else:
                logger.info(
                    "Indexed %s questions for interview %s",
                    index_result.indexed_count,
                    interview_id,
                )

            # Return empty dict - indexing is non-blocking
            return {}

        except Exception as exc:
            # Log but don't fail workflow - indexing is optional
            logger.warning(
                "Question indexing skipped for %s: %s",
                state.get("interview_id"),
                exc,
                exc_info=True,
            )
            return {}

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
            # Deterministic thread ID per interview
            thread_id = self.build_thread_id(interview_id)

            # Initialize state
            initial_state: ConversationState = {
                "interview_id": str(interview_id),
                "candidate_id": str(candidate_id),
                "messages": [],
                "current_question_id": None,
                "current_question": None,
                "parent_question": None,
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

    @staticmethod
    def build_thread_id(interview_id: UUID) -> str:
        """Derive deterministic thread ID for interview workflow."""
        return f"interview_{interview_id}"

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
