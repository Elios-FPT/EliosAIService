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

        Args:
            state: Current workflow state

        Returns:
            State updates
        """
        try:
            cv_analysis = await self.cv_repo.get_by_id(state["cv_analysis_id"])

            if not cv_analysis:
                return {
                    "errors": [f"CV analysis not found: {state['cv_analysis_id']}"]
                }

            logger.info(f"Loaded CV analysis: {cv_analysis.id}")
            return {"cv_analysis": cv_analysis}

        except Exception as e:
            error_msg = self.format_error(e, {"node": "load_cv"})
            logger.error(error_msg)
            return {"errors": [error_msg]}

    async def _calculate_count_node(self, state: PlanningState) -> dict[str, Any]:
        """Calculate number of questions based on skill diversity.

        Formula: n = min(5, max(2, unique_skills // 3))

        Args:
            state: Current workflow state

        Returns:
            State updates
        """
        try:
            cv_analysis = state["cv_analysis"]
            if not cv_analysis:
                return {"errors": ["CV analysis missing in state"]}

            # Calculate based on skill diversity
            unique_skills = len(cv_analysis.skills)
            question_count = min(5, max(2, unique_skills // 3))

            logger.info(f"Calculated question count: {question_count} (from {unique_skills} skills)")
            return {"question_count": question_count}

        except Exception as e:
            error_msg = self.format_error(e, {"node": "calculate_count"})
            logger.error(error_msg)
            return {"errors": [error_msg]}

    async def _prepare_specs_node(self, state: PlanningState) -> dict[str, Any]:
        """Prepare question specifications with exemplar search.

        Args:
            state: Current workflow state

        Returns:
            State updates
        """
        try:
            cv_analysis = state["cv_analysis"]
            question_count = state["question_count"]

            if not cv_analysis or question_count == 0:
                return {"errors": ["Missing CV analysis or question count"]}

            # Build question specs
            specs = []
            skills = cv_analysis.skills

            if not skills:
                return {"errors": ["No skills found in CV analysis"]}

            for i in range(question_count):
                # Rotate through skills
                skill_obj = skills[i % len(skills)]
                skill_name = skill_obj.skill_name  # CVSkill uses 'skill_name'

                # Determine difficulty based on proficiency
                difficulty_map = {
                    "beginner": "easy",
                    "intermediate": "medium",
                    "advanced": "hard",
                    "expert": "hard",
                }
                proficiency_value = skill_obj.proficiency_level.value if skill_obj.proficiency_level else "intermediate"
                difficulty = difficulty_map.get(proficiency_value, "medium")

                # Search for exemplar questions (if vector search available)
                exemplars = []
                try:
                    # Vector search for similar questions
                    search_results = await self.vector_search.search(
                        query_text=f"{skill_name} technical interview question",
                        top_k=3,
                        filter_metadata={"skill": skill_name}
                    )
                    exemplars = [
                        {"text": r.get("text"), "difficulty": r.get("difficulty")}
                        for r in search_results
                    ]
                except Exception as ve:
                    logger.warning(f"Exemplar search failed for {skill_name}: {ve}")
                    # Continue without exemplars

                specs.append({
                    "skill": skill_name,
                    "difficulty": difficulty,
                    "exemplars": exemplars
                })

            logger.info(f"Prepared {len(specs)} question specs")
            return {"question_specs": specs}

        except Exception as e:
            error_msg = self.format_error(e, {"node": "prepare_specs"})
            logger.error(error_msg)
            return {"errors": [error_msg]}

    async def _generate_batch_node(self, state: PlanningState) -> dict[str, Any]:
        """Generate questions with ideal answers and rationales in a single LLM call per spec.

        Uses unified LLM method to ensure question, ideal_answer, and rationale are generated
        together in one call for consistency.

        Args:
            state: Current workflow state

        Returns:
            State updates
        """
        try:
            specs = state["question_specs"]
            cv_analysis = state["cv_analysis"]

            if not specs or not cv_analysis:
                return {"errors": ["Missing question specs or CV analysis"]}

            # Prepare context
            context = {
                "cv_summary": cv_analysis.summary,
                "covered_topics": [],
                "stage": "planning"
            }

            # Generate complete question sets (question, ideal_answer, rationale) in parallel
            # Each spec generates all three components in a single LLM call
            logger.info(f"Generating {len(specs)} complete question sets (question, answer, rationale) in parallel...")
            question_sets = await self.llm.generate_questions_with_answers_and_rationales_batch(specs, context)

            # Unpack tuples into separate lists
            questions = []
            answers = []
            rationales = []
            for question_text, ideal_answer, rationale in question_sets:
                questions.append(question_text)
                answers.append(ideal_answer)
                rationales.append(rationale)

            logger.info(f"Successfully generated {len(questions)} complete question sets")

            return {
                "generated_questions": questions,
                "generated_answers": answers,
                "generated_rationales": rationales,
            }

        except Exception as e:
            error_msg = self.format_error(e, {"node": "generate_batch"})
            logger.error(error_msg)
            return {"errors": [error_msg]}

    async def _store_questions_node(self, state: PlanningState) -> dict[str, Any]:
        """Store generated questions in database.

        Args:
            state: Current workflow state

        Returns:
            State updates
        """
        # Early check for existing errors
        if state.get("errors"):
            logger.warning("Skipping store_questions node due to existing errors in state")
            return {}  # Return empty update to preserve existing errors

        try:
            questions = state["generated_questions"]
            answers = state["generated_answers"]
            rationales = state["generated_rationales"]
            specs = state["question_specs"]

            if not questions:
                # Check if questions were supposed to be generated
                if not state.get("generated_questions") and state.get("question_specs"):
                    return {"errors": ["No questions generated in previous step (generate_batch). Question generation may have failed."]}
                return {"errors": ["No questions to store"]}

            # Create Question objects
            question_objects = []
            for i, (q_text, ideal_answer, rationale, spec) in enumerate(
                zip(questions, answers, rationales, specs)
            ):
                question = Question(
                    text=q_text,
                    question_type=QuestionType.TECHNICAL,
                    difficulty=DifficultyLevel(spec["difficulty"]),
                    skills=[spec["skill"]],
                    ideal_answer=ideal_answer,
                    rationale=rationale,
                )
                question_objects.append(question)

            # Save all questions in one atomic transaction
            saved_questions = await self.question_repo.save_batch(question_objects)
            question_ids = [q.id for q in saved_questions]

            logger.info(f"Stored {len(question_ids)} questions in single transaction")
            return {"stored_question_ids": question_ids}

        except Exception as e:
            error_msg = self.format_error(e, {"node": "store_questions"})
            logger.error(error_msg)
            return {"errors": [error_msg]}

    async def _update_interview_node(self, state: PlanningState) -> dict[str, Any]:
        """Update interview with generated question IDs and mark as QUESTIONING.

        Args:
            state: Current workflow state

        Returns:
            State updates
        """
        # Early check for existing errors
        if state.get("errors"):
            logger.warning("Skipping update_interview node due to existing errors in state")
            return {}  # Return empty update to preserve existing errors

        try:
            candidate_id = state["candidate_id"]
            question_ids = state["stored_question_ids"]
            cv_analysis_id = state["cv_analysis_id"]
            question_specs = state.get("question_specs") or []

            if not question_ids:
                # Provide context about why question IDs are missing
                if not state.get("stored_question_ids") and state.get("generated_questions"):
                    return {"errors": ["No question IDs to attach to interview. Questions were generated but failed to be stored in previous step (store_questions)."]}
                elif not state.get("generated_questions"):
                    return {"errors": ["No question IDs to attach to interview. No questions were generated in the workflow."]}
                return {"errors": ["No question IDs to attach to interview"]}

            from ...domain.models.interview import Interview, InterviewStatus
            # Build a human-friendly, non-date-based title using skills from planned questions.
            title = self._build_interview_title(question_specs)
            interview = Interview(
                id=uuid.uuid4(),
                candidate_id=candidate_id,
                title=title,
                status=InterviewStatus.IDLE,
                cv_analysis_id=cv_analysis_id,
            )
            interview = await self.interview_repo.save(interview)

            # Add questions to interview via junction table
            for idx, question_id in enumerate(question_ids):
                await self.interview_repo.add_question(
                    interview_id=interview.id,
                    question_id=question_id,
                    sequence_order=idx,
                )

            logger.info(f"Updated interview {interview.id} with {len(question_ids)} questions")
            return {"interview": interview}

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
