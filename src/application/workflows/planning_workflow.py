"""LangGraph workflow for parallel interview question planning.

This workflow replaces sequential question generation with a parallelized,
checkpointed workflow that can resume after crashes.
"""

import logging
import uuid
from typing import Any, TypedDict
from uuid import UUID

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph.state import CompiledStateGraph

from ...domain.models.cv_analysis import CVAnalysis
from ...domain.models.interview import Interview
from ...domain.models.question import Question, QuestionType, DifficultyLevel
from ...domain.ports.llm_port import LLMPort
from ...domain.ports.cv_analysis_repository_port import CVAnalysisRepositoryPort
from ...domain.ports.question_repository_port import QuestionRepositoryPort
from ...domain.ports.interview_repository_port import InterviewRepositoryPort
from ...domain.ports.vector_search_port import VectorSearchPort
from .base_workflow import BaseWorkflow


logger = logging.getLogger(__name__)


class PlanningState(TypedDict):
    """State for planning workflow.

    Passed between nodes and checkpointed at each step.
    """
    # Input
    cv_analysis_id: UUID
    candidate_id: UUID

    # Loaded data
    cv_analysis: CVAnalysis | None

    # Planning
    question_count: int
    question_specs: list[dict[str, Any]]  # skill, difficulty, exemplars

    # Generated content
    generated_questions: list[str]
    generated_answers: list[str]
    generated_rationales: list[str]

    # Persisted results
    stored_question_ids: list[UUID]
    interview: Interview | None

    # Error handling
    errors: list[str]
    retry_count: int

    # Thread management
    checkpoint_thread_id: str


class PlanningWorkflow(BaseWorkflow):
    """LangGraph workflow for parallel question planning.

    Generates interview questions in parallel using RunnableParallel,
    with PostgreSQL checkpointing for crash recovery.
    """

    def __init__(
        self,
        checkpointer: AsyncPostgresSaver,
        llm_port: LLMPort,
        cv_repo: CVAnalysisRepositoryPort,
        question_repo: QuestionRepositoryPort,
        interview_repo: InterviewRepositoryPort,
        vector_search: VectorSearchPort,
    ):
        """Initialize planning workflow.

        Args:
            checkpointer: AsyncPostgresSaver for state persistence
            llm_port: LLM adapter for question generation
            cv_repo: CV analysis repository
            question_repo: Question repository
            interview_repo: Interview repository
            vector_search: Vector search for exemplar retrieval
        """
        super().__init__(checkpointer)
        self.llm = llm_port
        self.cv_repo = cv_repo
        self.question_repo = question_repo
        self.interview_repo = interview_repo
        self.vector_search = vector_search
        self.app = self._build_graph()

    def _build_graph(self) -> CompiledStateGraph:
        """Build LangGraph StateGraph with all nodes and edges.

        Returns:
            Compiled StateGraph ready for execution
        """
        # Create graph
        graph = StateGraph(PlanningState)

        # Add nodes
        graph.add_node("load_cv", self._load_cv_node)
        graph.add_node("calculate_count", self._calculate_count_node)
        graph.add_node("prepare_specs", self._prepare_specs_node)
        graph.add_node("generate_batch", self._generate_batch_node)
        graph.add_node("store_questions", self._store_questions_node)
        graph.add_node("update_interview", self._update_interview_node)
        graph.add_node("handle_error", self._handle_error_node)

        # Add edges
        graph.set_entry_point("load_cv")

        # Conditional edges for error handling - all nodes check for errors
        graph.add_conditional_edges(
            "load_cv",
            self._check_for_errors,
            {
                "continue": "calculate_count",
                "error": "handle_error"
            }
        )

        graph.add_conditional_edges(
            "calculate_count",
            self._check_for_errors,
            {
                "continue": "prepare_specs",
                "error": "handle_error"
            }
        )

        graph.add_conditional_edges(
            "prepare_specs",
            self._check_for_errors,
            {
                "continue": "generate_batch",
                "error": "handle_error"
            }
        )

        graph.add_conditional_edges(
            "generate_batch",
            self._check_for_errors,
            {
                "continue": "store_questions",
                "error": "handle_error"
            }
        )

        graph.add_conditional_edges(
            "store_questions",
            self._check_for_errors,
            {
                "continue": "update_interview",
                "error": "handle_error"
            }
        )

        graph.add_conditional_edges(
            "update_interview",
            self._check_for_errors,
            {
                "continue": END,
                "error": "handle_error"
            }
        )

        # Error handler routes to END (after max retries) or back to workflow start
        graph.add_conditional_edges(
            "handle_error",
            self._should_retry,
            {
                "retry": "load_cv",  # Retry from beginning
                "end": END  # Max retries exceeded
            }
        )

        # Compile with checkpointer
        return graph.compile(checkpointer=self.checkpointer)

    async def execute(
        self,
        cv_analysis_id: UUID,
        candidate_id: UUID,
        thread_id: str | None = None
    ) -> dict[str, Any]:
        """Execute planning workflow.

        Args:
            cv_analysis_id: ID of CV analysis
            candidate_id: ID of candidate
            thread_id: Optional thread ID for resuming (generates new if None)

        Returns:
            Result dict with question_ids and interview

        Raises:
            Exception: If workflow fails after retries
        """
        # Generate thread ID if not provided
        if thread_id is None:
            thread_id = self.generate_thread_id("planning")

        # Initial state
        initial_state: PlanningState = {
            "cv_analysis_id": cv_analysis_id,
            "candidate_id": candidate_id,
            "cv_analysis": None,
            "question_count": 0,
            "question_specs": [],
            "generated_questions": [],
            "generated_answers": [],
            "generated_rationales": [],
            "stored_question_ids": [],
            "interview": None,
            "errors": [],
            "retry_count": 0,
            "checkpoint_thread_id": thread_id,
        }

        # Execute workflow
        try:
            final_state = await self.app.ainvoke(
                initial_state,
                {"configurable": {"thread_id": thread_id}}
            )

            # Check for errors
            if final_state.get("errors"):
                raise Exception(f"Workflow failed: {final_state['errors']}")

            return {
                "question_ids": final_state["stored_question_ids"],
                "interview": final_state["interview"],
                "thread_id": thread_id,
            }

        except Exception as e:
            logger.error(f"Planning workflow failed: {self.format_error(e)}")
            raise

    # Node implementations

    async def _load_cv_node(self, state: PlanningState) -> dict[str, Any]:
        """Load CV analysis from repository.

        Delegates to LoadCVAnalysisUseCase.

        Args:
            state: Current workflow state

        Returns:
            State updates
        """
        from ..use_cases.planning.load_cv_analysis import LoadCVAnalysisUseCase
        from ..dto.planning.load_cv_analysis_dto import LoadCVAnalysisInput

        try:
            # Construct use case on-demand
            load_uc = LoadCVAnalysisUseCase(cv_analysis_repo=self.cv_repo)

            # Hydrate DTO from state
            input_dto = LoadCVAnalysisInput(cv_analysis_id=state["cv_analysis_id"])

            # Execute use case
            output = await load_uc.execute(input_dto)

            # Return state updates
            if output.errors:
                return {"errors": output.errors}
            return {"cv_analysis": output.cv_analysis}

        except Exception as e:
            error_msg = self.format_error(e, {"node": "load_cv"})
            logger.error(error_msg)
            return {"errors": [error_msg]}

    async def _calculate_count_node(self, state: PlanningState) -> dict[str, Any]:
        """Calculate number of questions based on skill diversity.

        Delegates to CalculateQuestionCountUseCase.

        Args:
            state: Current workflow state

        Returns:
            State updates
        """
        from ..use_cases.planning.calculate_question_count import CalculateQuestionCountUseCase
        from ..dto.planning.calculate_question_count_dto import CalculateQuestionCountInput

        try:
            # Construct use case on-demand
            calculate_uc = CalculateQuestionCountUseCase()

            # Hydrate DTO from state
            input_dto = CalculateQuestionCountInput(cv_analysis=state.get("cv_analysis"))

            # Execute use case
            output = await calculate_uc.execute(input_dto)

            # Return state updates
            if output.errors:
                return {"errors": output.errors}
            return {"question_count": output.question_count}

        except Exception as e:
            error_msg = self.format_error(e, {"node": "calculate_count"})
            logger.error(error_msg)
            return {"errors": [error_msg]}

    async def _prepare_specs_node(self, state: PlanningState) -> dict[str, Any]:
        """Prepare question specifications with exemplar search.

        Delegates to PrepareQuestionSpecsUseCase.

        Args:
            state: Current workflow state

        Returns:
            State updates
        """
        from ..use_cases.planning.prepare_question_specs import PrepareQuestionSpecsUseCase
        from ..dto.planning.prepare_question_specs_dto import PrepareQuestionSpecsInput

        try:
            # Construct use case on-demand
            prepare_uc = PrepareQuestionSpecsUseCase(vector_search=self.vector_search)

            # Hydrate DTO from state
            input_dto = PrepareQuestionSpecsInput(
                cv_analysis=state.get("cv_analysis"),
                question_count=state.get("question_count", 0),
            )

            # Execute use case
            output = await prepare_uc.execute(input_dto)

            # Return state updates
            if output.errors:
                return {"errors": output.errors}
            return {"question_specs": [spec.model_dump() for spec in output.question_specs]}

        except Exception as e:
            error_msg = self.format_error(e, {"node": "prepare_specs"})
            logger.error(error_msg)
            return {"errors": [error_msg]}

    async def _generate_batch_node(self, state: PlanningState) -> dict[str, Any]:
        """Generate questions with ideal answers and rationales in a single LLM call per spec.

        Delegates to GenerateQuestionsBatchUseCase.

        Args:
            state: Current workflow state

        Returns:
            State updates
        """
        from ..use_cases.planning.generate_questions_batch import GenerateQuestionsBatchUseCase
        from ..dto.planning.generate_questions_batch_dto import GenerateQuestionsBatchInput
        from ..dto.planning.prepare_question_specs_dto import QuestionSpec

        try:
            # Construct use case on-demand
            generate_uc = GenerateQuestionsBatchUseCase(llm=self.llm)

            # Hydrate DTO from state
            # Convert dict specs back to QuestionSpec objects
            specs_dict = state.get("question_specs", [])
            question_specs = [QuestionSpec(**spec) for spec in specs_dict]

            input_dto = GenerateQuestionsBatchInput(
                question_specs=question_specs,
                cv_summary=state.get("cv_analysis").summary if state.get("cv_analysis") else None,
            )

            # Execute use case
            output = await generate_uc.execute(input_dto)

            # Return state updates
            if output.errors:
                return {"errors": output.errors}
            return {
                "generated_questions": output.generated_questions,
                "generated_answers": output.generated_answers,
                "generated_rationales": output.generated_rationales,
            }

        except Exception as e:
            error_msg = self.format_error(e, {"node": "generate_batch"})
            logger.error(error_msg)
            return {"errors": [error_msg]}

    async def _store_questions_node(self, state: PlanningState) -> dict[str, Any]:
        """Store generated questions in database.

        Delegates to StoreQuestionsUseCase.

        Args:
            state: Current workflow state

        Returns:
            State updates
        """
        from ..use_cases.planning.store_questions import StoreQuestionsUseCase
        from ..dto.planning.store_questions_dto import StoreQuestionsInput
        from ..dto.planning.prepare_question_specs_dto import QuestionSpec

        # Early check for existing errors
        if state.get("errors"):
            logger.warning("Skipping store_questions node due to existing errors in state")
            return {}

        try:
            # Construct use case on-demand
            store_uc = StoreQuestionsUseCase(question_repo=self.question_repo)

            # Hydrate DTO from state
            specs_dict = state.get("question_specs", [])
            question_specs = [QuestionSpec(**spec) for spec in specs_dict]

            input_dto = StoreQuestionsInput(
                generated_questions=state.get("generated_questions", []),
                generated_answers=state.get("generated_answers", []),
                generated_rationales=state.get("generated_rationales", []),
                question_specs=question_specs,
            )

            # Execute use case
            output = await store_uc.execute(input_dto)

            # Return state updates
            if output.errors:
                return {"errors": output.errors}
            return {"stored_question_ids": [str(qid) for qid in output.stored_question_ids]}

        except Exception as e:
            error_msg = self.format_error(e, {"node": "store_questions"})
            logger.error(error_msg)
            return {"errors": [error_msg]}

    async def _update_interview_node(self, state: PlanningState) -> dict[str, Any]:
        """Update interview with generated question IDs and mark as QUESTIONING.

        Delegates to CreateInterviewUseCase.

        Args:
            state: Current workflow state

        Returns:
            State updates
        """
        from ..use_cases.planning.create_interview import CreateInterviewUseCase
        from ..dto.planning.create_interview_dto import CreateInterviewInput

        # Early check for existing errors
        if state.get("errors"):
            logger.warning("Skipping update_interview node due to existing errors in state")
            return {}

        try:
            # Construct use case on-demand
            create_uc = CreateInterviewUseCase(
                interview_repo=self.interview_repo,
            )

            # Hydrate DTO from state
            question_ids = [UUID(qid) if isinstance(qid, str) else qid for qid in state.get("stored_question_ids", [])]
            question_specs = state.get("question_specs") or []

            input_dto = CreateInterviewInput(
                candidate_id=state["candidate_id"],
                cv_analysis_id=state["cv_analysis_id"],
                question_ids=question_ids,
                question_specs=question_specs,
            )

            # Execute use case
            output = await create_uc.execute(input_dto)

            # Return state updates
            if output.errors:
                return {"errors": output.errors}
            return {"interview": output.interview}

        except Exception as e:
            error_msg = self.format_error(e, {"node": "update_interview"})
            logger.error(error_msg)
            return {"errors": [error_msg]}

    async def _handle_error_node(self, state: PlanningState) -> dict[str, Any]:
        """Handle workflow errors with retry logic.

        Args:
            state: Current workflow state

        Returns:
            State updates
        """
        errors = state.get("errors", [])
        retry_count = state.get("retry_count", 0)

        logger.error(f"Workflow error (attempt {retry_count + 1}): {errors}")

        # Check if should retry
        if retry_count < 3:
            logger.info(f"Retrying workflow (attempt {retry_count + 1}/3)")
            return {
                "retry_count": retry_count + 1,
                "errors": []  # Clear errors for retry
            }
        else:
            # Max retries exceeded - keep errors for final state
            logger.error(f"Max retries exceeded. Final errors: {errors}")
            return {
                "errors": errors + ["Max retry attempts exceeded"]
            }

    # Helper methods

    def _check_for_errors(self, state: PlanningState) -> str:
        """Check if state has errors.

        Args:
            state: Current workflow state

        Returns:
            "error" if errors exist, "continue" otherwise
        """
        if state.get("errors"):
            return "error"
        return "continue"

    def _should_retry(self, state: PlanningState) -> str:
        """Determine if workflow should retry or end.

        Args:
            state: Current workflow state

        Returns:
            "retry" if retries available, "end" if max retries exceeded
        """
        retry_count = state.get("retry_count", 0)
        if retry_count < 3:
            return "retry"
        return "end"

    def _build_interview_title(self, question_specs: list[dict[str, Any]] | None) -> str:
        """Build a simple, human-friendly interview title from planned question skills.

        Prefer the most common or first skill from question specs; otherwise fall back
        to a generic label. Avoids including dates to keep titles stable and clean.
        """
        if not question_specs:
            return "General Interview"

        # Extract ordered, unique skill names from specs
        skills = [spec.get("skill") for spec in question_specs if spec.get("skill")]
        if not skills:
            return "General Interview"

        # Deduplicate while preserving order
        seen = set()
        ordered_skills = []
        for skill in skills:
            if skill not in seen:
                seen.add(skill)
                ordered_skills.append(skill)

        skills_str = ", ".join(ordered_skills)
        return f"Interview – {skills_str}"
