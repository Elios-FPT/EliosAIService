"""LangGraph workflow for adaptive answer evaluation (no interrupts).

Phase 3A: Simplified adaptive workflow for single answer evaluation with
follow-up decision. Generates follow-up questions but doesn't execute loop
(requires user input). Phase 3B will add WebSocket interrupts for full loop.

This workflow handles:
- Answer evaluation with adaptive scoring
- Follow-up decision logic (break conditions)
- Follow-up question generation (conditional)

NOTE: In Phase 3A, we evaluate ONE answer and decide if follow-up needed.
The actual multi-iteration loop happens in Phase 3B with interrupts.
"""

import logging
from datetime import datetime
from typing import Any, TypedDict
from uuid import UUID, uuid4

from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from ...domain.models.answer import Answer
from ...domain.models.evaluation import Evaluation, ConceptGap, GapSeverity, FollowUpEvaluationContext
from ...domain.models.follow_up_question import FollowUpQuestion
from ...domain.models.interview import Interview
from ...domain.models.question import Question
from ...domain.ports.answer_repository_port import AnswerRepositoryPort
from ...domain.ports.evaluation_repository_port import EvaluationRepositoryPort
from ...domain.ports.follow_up_question_repository_port import FollowUpQuestionRepositoryPort
from ...domain.ports.interview_repository_port import InterviewRepositoryPort
from ...domain.ports.llm_port import LLMPort
from ...domain.ports.question_repository_port import QuestionRepositoryPort
from .base_workflow import BaseWorkflow


logger = logging.getLogger(__name__)


class AdaptiveEvalSimpleState(TypedDict):
    """State for adaptive evaluation workflow (no interrupts).

    Passed between nodes and checkpointed at each step.
    """
    # Input (initial)
    interview_id: UUID
    question_id: UUID
    answer_text: str
    audio_file_path: str | None
    voice_metrics: dict[str, float] | None

    # Context (loaded in first node)
    interview: Interview | None
    question: Question | None
    parent_question_id: UUID | None
    is_followup: bool

    # Loop tracking
    iteration: int  # Current iteration (0 = main, 1-3 = follow-ups)
    answers: list[Answer]  # All answers in this evaluation cycle
    evaluations: list[Evaluation]  # All evaluations in this cycle
    cumulative_gaps: list[str]  # Accumulated concept gaps

    # Follow-up questions generated (for Phase 3B)
    followup_questions_generated: list[FollowUpQuestion]

    # Output
    combined_evaluation: Evaluation | None
    final_answer: Answer | None
    has_more_questions: bool
    complete: bool

    # Error handling
    errors: list[str]
    retry_count: int


class AdaptiveEvalSimpleWorkflow(BaseWorkflow):
    """LangGraph workflow for adaptive answer evaluation (Phase 3A).

    Evaluates ONE answer and decides if follow-up needed. Generates follow-up
    question but does NOT execute the loop (requires user input between iterations).

    Phase 3A Flow:
    1. load_context - Fetch interview, question, detect follow-up status
    2. evaluate_answer - LLM evaluation with follow-up context if applicable
    3. store_answer - Save Answer + Evaluation to DB
    4. check_followup - Break condition check (conditional edge)
    5a. generate_followup - Generate follow-up question (END, return to client)
    5b. finalize - No follow-up needed (END)

    Phase 3B will add:
    - WebSocket streaming of workflow state
    - Loop-back: generate_followup → interrupt → wait for answer → evaluate_answer
    - Full 0-3 iteration loop execution with interrupts
    """

    def __init__(
        self,
        checkpointer: AsyncPostgresSaver,
        answer_repo: AnswerRepositoryPort,
        evaluation_repo: EvaluationRepositoryPort,
        interview_repo: InterviewRepositoryPort,
        question_repo: QuestionRepositoryPort,
        follow_up_repo: FollowUpQuestionRepositoryPort,
        llm: LLMPort,
    ):
        """Initialize adaptive evaluation workflow.

        Args:
            checkpointer: AsyncPostgresSaver for state persistence
            answer_repo: Answer repository
            evaluation_repo: Evaluation repository
            interview_repo: Interview repository
            question_repo: Question repository
            follow_up_repo: Follow-up question repository
            llm: LLM port for evaluation and follow-up generation
        """
        super().__init__(checkpointer)
        self.answer_repo = answer_repo
        self.evaluation_repo = evaluation_repo
        self.interview_repo = interview_repo
        self.question_repo = question_repo
        self.follow_up_repo = follow_up_repo
        self.llm = llm
        self.app: Any = self._build_graph()  # CompiledStateGraph type

    def _build_graph(self) -> CompiledStateGraph:
        """Build LangGraph StateGraph with all nodes and edges.

        Returns:
            Compiled StateGraph ready for execution
        """
        # Create graph
        graph = StateGraph(AdaptiveEvalSimpleState)

        # Add nodes
        graph.add_node("load_context", self._load_context_node)
        graph.add_node("evaluate_answer", self._evaluate_answer_node)
        graph.add_node("store_answer", self._store_answer_node)
        graph.add_node("check_followup", self._check_followup_node)
        graph.add_node("generate_followup", self._generate_followup_node)
        graph.add_node("finalize", self._finalize_node)
        graph.add_node("handle_error", self._handle_error_node)

        # Add edges
        graph.set_entry_point("load_context")
        graph.add_edge("load_context", "evaluate_answer")
        graph.add_edge("evaluate_answer", "store_answer")
        graph.add_edge("store_answer", "check_followup")

        # Conditional edge: check_followup → generate_followup OR finalize
        graph.add_conditional_edges(
            "check_followup",
            self._should_generate_followup,
            {
                "generate_followup": "generate_followup",
                "finalize": "finalize",
            }
        )

        # Terminal nodes (Phase 3A - no loop back)
        graph.add_edge("generate_followup", END)
        graph.add_edge("finalize", END)

        # Compile with checkpointer
        return graph.compile(checkpointer=self.checkpointer)

    async def execute(
        self,
        interview_id: UUID,
        question_id: UUID,
        answer_text: str,
        audio_file_path: str | None = None,
        voice_metrics: dict[str, float] | None = None,
        thread_id: str | None = None,
    ) -> dict[str, Any]:
        """Execute adaptive evaluation workflow.

        Args:
            interview_id: Interview UUID
            question_id: Question UUID (main or follow-up)
            answer_text: Candidate's answer text
            audio_file_path: Optional audio file path
            voice_metrics: Optional voice metrics
            thread_id: Optional thread ID for resuming

        Returns:
            Result dict with:
                - evaluation: Latest Evaluation
                - answer: Latest Answer
                - has_more_questions: bool
                - followup_question: FollowUpQuestion | None (if generated)
                - needs_followup: bool

        Raises:
            Exception: If workflow fails after retries
        """
        # Generate thread ID if not provided
        if thread_id is None:
            thread_id = self.generate_thread_id("adaptive_eval")

        # Initial state
        initial_state: AdaptiveEvalSimpleState = {
            "interview_id": interview_id,
            "question_id": question_id,
            "answer_text": answer_text,
            "audio_file_path": audio_file_path,
            "voice_metrics": voice_metrics,
            "interview": None,
            "question": None,
            "parent_question_id": None,
            "is_followup": False,
            "iteration": 0,
            "answers": [],
            "evaluations": [],
            "cumulative_gaps": [],
            "followup_questions_generated": [],
            "combined_evaluation": None,
            "final_answer": None,
            "has_more_questions": False,
            "complete": False,
            "errors": [],
            "retry_count": 0,
        }

        # Execute workflow
        try:
            final_state = await self.app.ainvoke(
                initial_state,
                {"configurable": {"thread_id": thread_id}}
            )

            # Check for errors
            if final_state.get("errors"):
                raise Exception(f"Adaptive evaluation workflow failed: {final_state['errors']}")

            # Extract results
            evaluation = final_state["evaluations"][-1] if final_state["evaluations"] else None
            answer = final_state["answers"][-1] if final_state["answers"] else None
            followup_question = final_state["followup_questions_generated"][-1] if final_state["followup_questions_generated"] else None

            return {
                "evaluation": evaluation,
                "answer": answer,
                "has_more_questions": final_state["has_more_questions"],
                "followup_question": followup_question,
                "needs_followup": followup_question is not None,
                "thread_id": thread_id,
            }

        except Exception as e:
            logger.error(f"Adaptive evaluation workflow failed: {self.format_error(e)}")
            raise

    # Node implementations

    async def _load_context_node(self, state: AdaptiveEvalSimpleState) -> dict[str, Any]:
        """Load interview, question, and detect follow-up status.

        Args:
            state: Current workflow state

        Returns:
            State updates with context
        """
        try:
            interview_id = state["interview_id"]
            question_id = state["question_id"]

            # Load interview
            interview = await self.interview_repo.get_by_id(interview_id)
            if not interview:
                return {"errors": [f"Interview {interview_id} not found"]}

            # Detect if follow-up question
            is_followup, parent_question_id = await self._is_followup_question(question_id)

            # Load question (parent if follow-up, else main)
            if is_followup:
                question = await self._get_follow_up_parent_question(question_id)
            else:
                question = await self._get_question(question_id)
                parent_question_id = question_id  # Main question is its own parent

            logger.info(
                f"Loaded context: interview={interview.id}, question={question.id}, "
                f"is_followup={is_followup}, parent={parent_question_id}"
            )

            return {
                "interview": interview,
                "question": question,
                "parent_question_id": parent_question_id,
                "is_followup": is_followup,
            }

        except Exception as e:
            error_msg = self.format_error(e, {"node": "load_context"})
            logger.error(error_msg)
            return {"errors": [error_msg]}

    async def _evaluate_answer_node(self, state: AdaptiveEvalSimpleState) -> dict[str, Any]:
        """Evaluate answer using LLM with follow-up context.

        Args:
            state: Current workflow state

        Returns:
            State updates with new answer and evaluation
        """
        try:
            interview = state["interview"]
            question = state["question"]
            answer_text = state["answer_text"]
            iteration = state["iteration"]

            if not interview or not question:
                return {"errors": ["Missing interview or question in state"]}

            # Build follow-up context if iteration > 0
            followup_context = None
            if iteration > 0:
                followup_context = await self._build_followup_context(state)

            # Create answer entity
            answer_question_id = state["parent_question_id"] if state["is_followup"] else state["question_id"]
            if not answer_question_id:
                return {"errors": ["Missing question ID for answer"]}

            answer = Answer(
                interview_id=interview.id,
                question_id=answer_question_id,
                candidate_id=interview.candidate_id,
                text=answer_text,
                is_voice=bool(state.get("audio_file_path")),
                audio_file_path=state.get("audio_file_path"),
                voice_metrics=state.get("voice_metrics"),
                created_at=datetime.utcnow(),
            )

            # Evaluate with LLM
            llm_eval = await self.llm.evaluate_answer(
                question=question,
                answer_text=answer_text,
                context={
                    "interview_id": str(interview.id),
                    "candidate_id": str(interview.candidate_id),
                },
                followup_context=followup_context,
            )

            # Extract similarity score
            similarity_score = None
            if question.has_ideal_answer() and llm_eval.semantic_similarity is not None:
                similarity_score = max(0.01, llm_eval.semantic_similarity)

            # Detect gaps
            gaps_dict = await self._detect_gaps_hybrid(
                answer_text=answer_text,
                ideal_answer=question.ideal_answer or "",
                question_text=question.text,
                interview_id=interview.id,
            )

            # Determine attempt number
            attempt_number = iteration + 1  # 1-based
            parent_evaluation_id = state["evaluations"][-1].id if state["evaluations"] else None

            # Create Evaluation entity
            evaluation = Evaluation(
                answer_id=answer.id,  # Will link after saving
                question_id=state["question_id"],
                interview_id=interview.id,
                raw_score=llm_eval.score,
                penalty=0.0,
                final_score=llm_eval.score,
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
                        evaluation_id=answer.id,  # Temporary
                        concept=concept,
                        severity=self._determine_gap_severity(concept, gaps_dict),
                        resolved=False,
                        created_at=datetime.utcnow(),
                    )
                    for concept in gaps_dict.get("concepts", [])
                ],
                evaluated_at=datetime.utcnow(),
            )

            # Apply penalty
            evaluation.apply_penalty(attempt_number)

            # Check gap resolution
            if evaluation.is_gap_resolved_by_criteria():
                evaluation.resolve_gaps()
                logger.info(
                    f"Gaps resolved: completeness={evaluation.completeness:.2f}, "
                    f"score={evaluation.final_score:.1f}, attempt={attempt_number}"
                )

            logger.info(
                f"Evaluated answer (iteration {iteration}): score={evaluation.final_score:.1f}, "
                f"similarity={f'{similarity_score:.2f}' if similarity_score else 'N/A'}, "
                f"gaps={len(evaluation.gaps)}"
            )

            return {
                "answers": state["answers"] + [answer],
                "evaluations": state["evaluations"] + [evaluation],
            }

        except Exception as e:
            error_msg = self.format_error(e, {"node": "evaluate_answer", "iteration": state.get("iteration", 0)})
            logger.error(error_msg)
            return {"errors": [error_msg]}

    async def _store_answer_node(self, state: AdaptiveEvalSimpleState) -> dict[str, Any]:
        """Save answer and evaluation to database.

        Args:
            state: Current workflow state

        Returns:
            State updates with saved entities
        """
        try:
            # Get latest answer and evaluation
            answer = state["answers"][-1]
            evaluation = state["evaluations"][-1]
            interview = state["interview"]

            if not interview:
                return {"errors": ["Missing interview in state"]}

            # Save answer first
            saved_answer = await self.answer_repo.save(answer)

            # Update evaluation with answer_id
            evaluation.answer_id = saved_answer.id
            for gap in evaluation.gaps:
                gap.evaluation_id = evaluation.id

            # Save evaluation
            saved_evaluation = await self.evaluation_repo.save(evaluation)

            # Link answer to evaluation
            saved_answer.evaluation_id = saved_evaluation.id
            saved_answer = await self.answer_repo.update(saved_answer)

            # Update interview
            interview.add_answer(saved_answer.id)
            updated_interview = await self.interview_repo.update(interview)

            # Update state lists with saved entities
            answers = state["answers"][:-1] + [saved_answer]
            evaluations = state["evaluations"][:-1] + [saved_evaluation]

            logger.info(
                f"Stored answer {saved_answer.id} and evaluation {saved_evaluation.id}"
            )

            return {
                "answers": answers,
                "evaluations": evaluations,
                "interview": updated_interview,
                "final_answer": saved_answer,  # Track latest
            }

        except Exception as e:
            error_msg = self.format_error(e, {"node": "store_answer"})
            logger.error(error_msg)
            return {"errors": [error_msg]}

    async def _check_followup_node(self, state: AdaptiveEvalSimpleState) -> dict[str, Any]:
        """Check break conditions and update iteration counter.

        This node only updates state - the conditional edge makes the decision.

        Args:
            state: Current workflow state

        Returns:
            State updates (iteration increment)
        """
        try:
            latest_evaluation = state["evaluations"][-1]
            cumulative_gaps = []

            # Collect unresolved gaps
            for evaluation in state["evaluations"]:
                for gap in evaluation.gaps:
                    if not gap.resolved and gap.concept not in cumulative_gaps:
                        cumulative_gaps.append(gap.concept)

            logger.info(
                f"Checked follow-up need: iteration={state['iteration']}, "
                f"gaps={len(cumulative_gaps)}, "
                f"similarity={latest_evaluation.similarity_score:.2f if latest_evaluation.similarity_score else 'N/A'}"
            )

            return {
                "cumulative_gaps": cumulative_gaps,
            }

        except Exception as e:
            error_msg = self.format_error(e, {"node": "check_followup"})
            logger.error(error_msg)
            return {"errors": [error_msg]}

    async def _generate_followup_node(self, state: AdaptiveEvalSimpleState) -> dict[str, Any]:
        """Generate follow-up question (Phase 3A - no loop execution).

        Args:
            state: Current workflow state

        Returns:
            State updates with new follow-up question
        """
        try:
            question = state["question"]
            cumulative_gaps = state["cumulative_gaps"]
            iteration = state["iteration"]
            interview = state["interview"]
            parent_question_id = state["parent_question_id"]

            if not question or not interview or not parent_question_id:
                return {"errors": ["Missing required state for follow-up generation"]}

            # Get latest evaluation for severity
            latest_eval = state["evaluations"][-1] if state["evaluations"] else None
            severity = "moderate"  # Default
            if latest_eval and latest_eval.gaps:
                # Use first gap severity as representative
                severity = latest_eval.gaps[0].severity.value if latest_eval.gaps else "moderate"

            # Generate follow-up question using LLM
            followup_text = await self.llm.generate_followup_question(
                parent_question=question.text,
                answer_text=state["answer_text"],
                missing_concepts=cumulative_gaps,
                severity=severity,
                order=iteration + 1,
                cumulative_gaps=cumulative_gaps,
                context={"interview_id": str(interview.id)},
            )

            # Create follow-up question entity
            followup_question = FollowUpQuestion(
                parent_question_id=parent_question_id,
                interview_id=interview.id,
                text=followup_text,
                generated_reason=f"Missing concepts: {', '.join(cumulative_gaps[:3])}",
                order_in_sequence=iteration + 1,  # 1-based
            )

            # Save follow-up question
            saved_followup = await self.follow_up_repo.save(followup_question)

            # Check if more main questions available using junction table
            total_questions = await self.interview_repo.count_interview_questions(interview.id)
            has_more = interview.current_question_index < (total_questions - 1)

            logger.info(
                f"Generated follow-up question {saved_followup.id} (iteration {iteration + 1}), "
                f"has_more_main_questions={has_more}"
            )

            # Phase 3A: Return follow-up question for manual handling
            # Phase 3B will add loop-back logic here
            return {
                "followup_questions_generated": state["followup_questions_generated"] + [saved_followup],
                "has_more_questions": has_more,
                "complete": True,
            }

        except Exception as e:
            error_msg = self.format_error(e, {"node": "generate_followup", "iteration": state.get("iteration", 0)})
            logger.error(error_msg)
            return {"errors": [error_msg]}

    async def _finalize_node(self, state: AdaptiveEvalSimpleState) -> dict[str, Any]:
        """Finalize workflow when no follow-up needed.

        Args:
            state: Current workflow state

        Returns:
            State updates marking completion
        """
        try:
            interview = state["interview"]
            evaluation = state["evaluations"][-1] if state["evaluations"] else None

            if not interview:
                return {"errors": ["Missing interview in finalize"]}

            # Check if more main questions available using junction table
            total_questions = await self.interview_repo.count_interview_questions(interview.id)
            has_more = interview.current_question_index < (total_questions - 1)

            score_str = f"{evaluation.final_score:.1f}" if evaluation else "N/A"
            logger.info(
                f"Finalized evaluation (no follow-up): score={score_str}, "
                f"has_more={has_more}"
            )

            return {
                "has_more_questions": has_more,
                "complete": True,
            }

        except Exception as e:
            error_msg = self.format_error(e, {"node": "finalize"})
            logger.error(error_msg)
            return {"errors": [error_msg]}

    async def _handle_error_node(self, state: AdaptiveEvalSimpleState) -> dict[str, Any]:
        """Handle workflow errors with retry logic.

        Args:
            state: Current workflow state

        Returns:
            State updates
        """
        errors = state.get("errors", [])
        retry_count = state.get("retry_count", 0)

        logger.error(f"Workflow error (attempt {retry_count + 1}): {errors}")

        if retry_count < 3:
            return {
                "retry_count": retry_count + 1,
                "errors": []
            }
        else:
            logger.error(f"Max retries exceeded. Final errors: {errors}")
            return {
                "errors": errors + ["Max retry attempts exceeded"]
            }

    # Helper methods (conditional edge)

    def _should_generate_followup(self, state: AdaptiveEvalSimpleState) -> str:
        """Decide: generate_followup OR finalize.

        Break conditions (finalize):
        1. Max iterations (3) reached
        2. High similarity score (>= 0.8)
        3. No gaps detected

        Args:
            state: Current workflow state

        Returns:
            "generate_followup" or "finalize"
        """
        iteration = state["iteration"]
        latest_evaluation = state["evaluations"][-1] if state["evaluations"] else None
        cumulative_gaps = state["cumulative_gaps"]

        if not latest_evaluation:
            logger.warning("No evaluation found, cannot determine follow-up need")
            return "finalize"

        # Break condition 1: Max iterations
        if iteration >= 3:
            logger.info(f"Break condition: Max iterations ({iteration}) reached")
            return "finalize"

        # Break condition 2: High similarity
        if latest_evaluation.similarity_score and latest_evaluation.similarity_score >= 0.8:
            logger.info(
                f"Break condition: High similarity ({latest_evaluation.similarity_score:.2f} >= 0.8)"
            )
            return "finalize"

        # Break condition 3: No gaps
        if not cumulative_gaps:
            logger.info("Break condition: No concept gaps detected")
            return "finalize"

        # Need follow-up
        sim_str = f"{latest_evaluation.similarity_score:.2f}" if latest_evaluation.similarity_score else "N/A"
        logger.info(
            f"Follow-up needed: iteration={iteration}, gaps={len(cumulative_gaps)}, "
            f"similarity={sim_str}"
        )
        return "generate_followup"

    # Helper methods

    async def _is_followup_question(self, question_id: UUID) -> tuple[bool, UUID | None]:
        """Check if question_id is a follow-up question.

        Args:
            question_id: Question UUID

        Returns:
            Tuple of (is_followup, parent_question_id)
        """
        follow_up = await self.follow_up_repo.get_by_id(question_id)
        if follow_up:
            return True, follow_up.parent_question_id
        return False, None

    async def _get_question(self, question_id: UUID) -> Question:
        """Get main question.

        Args:
            question_id: Question UUID

        Returns:
            Question entity

        Raises:
            ValueError: If question not found
        """
        question = await self.question_repo.get_by_id(question_id)
        if not question:
            raise ValueError(f"Question {question_id} not found")
        return question

    async def _get_follow_up_parent_question(self, question_id: UUID) -> Question:
        """Get parent question for a follow-up.

        Args:
            question_id: Follow-up question UUID

        Returns:
            Parent Question entity

        Raises:
            ValueError: If follow-up or parent not found
        """
        follow_up = await self.follow_up_repo.get_by_id(question_id)
        if not follow_up:
            raise ValueError(f"Follow-up question {question_id} not found")

        parent = await self.question_repo.get_by_id(follow_up.parent_question_id)
        if not parent:
            raise ValueError(f"Parent question {follow_up.parent_question_id} not found")

        return parent

    async def _build_followup_context(
        self,
        state: AdaptiveEvalSimpleState,
    ) -> FollowUpEvaluationContext | None:
        """Build follow-up evaluation context from state.

        Args:
            state: Current workflow state

        Returns:
            FollowUpEvaluationContext or None if missing required state
        """
        previous_evaluations = state["evaluations"]
        parent_question_id = state["parent_question_id"]
        question = state["question"]

        if not parent_question_id or not question:
            return None

        cumulative_gaps_list = []

        # Convert cumulative_gaps (list[str]) to ConceptGap objects
        # Use a placeholder evaluation_id (will be updated when evaluation is saved)
        placeholder_eval_id = previous_evaluations[-1].id if previous_evaluations else uuid4()
        for concept in state["cumulative_gaps"]:
            cumulative_gaps_list.append(
                ConceptGap(
                    evaluation_id=placeholder_eval_id,
                    concept=concept,
                    severity=GapSeverity.MODERATE,
                    resolved=False,
                    created_at=datetime.utcnow(),
                )
            )

        return FollowUpEvaluationContext(
            parent_question_id=parent_question_id,
            follow_up_question_id=state["question_id"],
            attempt_number=state["iteration"] + 1,
            previous_evaluations=previous_evaluations,
            cumulative_gaps=cumulative_gaps_list,
            previous_scores=[e.final_score for e in previous_evaluations],
            parent_ideal_answer=question.ideal_answer or "",
        )

    async def _detect_gaps_hybrid(
        self,
        answer_text: str,
        ideal_answer: str,
        question_text: str,
        interview_id: UUID,
    ) -> dict[str, Any]:
        """Detect concept gaps using hybrid approach (keywords + LLM).

        Args:
            answer_text: Candidate's answer
            ideal_answer: Reference ideal answer
            question_text: The question asked
            interview_id: Interview UUID for logging context

        Returns:
            Gaps dict with detected concepts
        """
        # Keyword-based gap detection
        keyword_gaps = self._detect_keyword_gaps(answer_text, ideal_answer)

        # If keywords detected gaps, confirm with LLM
        if keyword_gaps:
            llm_gaps = await self.llm.detect_concept_gaps(
                answer_text=answer_text,
                ideal_answer=ideal_answer,
                question_text=question_text,
                keyword_gaps=keyword_gaps,
                context={"interview_id": str(interview_id)},
            )
            return llm_gaps
        else:
            return {"concepts": [], "confirmed": False, "severity": "minor"}

    def _detect_keyword_gaps(self, answer_text: str, ideal_answer: str) -> list[str]:
        """Fast keyword-based gap detection."""
        stop_words = {
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
            "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
            "being", "have", "has", "had", "do", "does", "did", "will", "would",
            "should", "could", "may", "might", "must", "can", "this", "that",
            "these", "those",
        }

        ideal_words = {
            word.lower().strip('.,!?;:"\'-')
            for word in ideal_answer.split()
            if len(word.strip('.,!?;:"\'-')) > 3
            and word.lower().strip('.,!?;:"\'-') not in stop_words
        }

        answer_words = {
            word.lower().strip('.,!?;:"\'-')
            for word in answer_text.split()
            if len(word.strip('.,!?;:"\'-')) > 3
            and word.lower().strip('.,!?;:"\'-') not in stop_words
        }

        missing = list(ideal_words - answer_words)
        return missing if len(missing) > 3 else []

    def _determine_gap_severity(
        self,
        concept: str,
        gaps_dict: dict[str, Any]
    ) -> GapSeverity:
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
            return GapSeverity.MODERATE
