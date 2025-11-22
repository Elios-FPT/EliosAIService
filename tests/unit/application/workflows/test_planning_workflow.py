"""Unit tests for PlanningWorkflow class."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4, UUID

from src.application.workflows.planning_workflow import PlanningWorkflow, PlanningState
from src.domain.models.cv_analysis import CVAnalysis, ExtractedSkill
from src.domain.models.interview import Interview, InterviewStatus
from src.domain.models.question import Question, QuestionType, DifficultyLevel


@pytest.fixture
def mock_checkpointer():
    """Create mock AsyncPostgresSaver."""
    checkpointer = MagicMock()
    checkpointer.aget = AsyncMock()
    checkpointer.aput = AsyncMock()
    return checkpointer


@pytest.fixture
def mock_llm():
    """Create mock LLM port."""
    llm = MagicMock()
    llm.generate_questions_batch = AsyncMock()
    llm.generate_ideal_answers_batch = AsyncMock()
    llm.generate_rationales_batch = AsyncMock()
    llm.generate_questions_with_answers_and_rationales_batch = AsyncMock()
    return llm


@pytest.fixture
def mock_cv_repo():
    """Create mock CV analysis repository."""
    repo = MagicMock()
    repo.get_by_id = AsyncMock()
    return repo


@pytest.fixture
def mock_question_repo():
    """Create mock question repository."""
    repo = MagicMock()
    repo.create = AsyncMock()
    return repo


@pytest.fixture
def mock_interview_repo():
    """Create mock interview repository."""
    repo = MagicMock()
    repo.get_active_by_candidate = AsyncMock()
    repo.create = AsyncMock()
    repo.update = AsyncMock()
    return repo


@pytest.fixture
def mock_vector_search():
    """Create mock vector search port."""
    search = MagicMock()
    search.search = AsyncMock()
    return search


@pytest.fixture
def workflow(
    mock_checkpointer,
    mock_llm,
    mock_cv_repo,
    mock_question_repo,
    mock_interview_repo,
    mock_vector_search,
):
    """Create PlanningWorkflow instance with all mocked dependencies."""
    return PlanningWorkflow(
        checkpointer=mock_checkpointer,
        llm_port=mock_llm,
        cv_repo=mock_cv_repo,
        question_repo=mock_question_repo,
        interview_repo=mock_interview_repo,
        vector_search=mock_vector_search,
    )


@pytest.fixture
def sample_cv_analysis():
    """Create sample CV analysis for testing."""
    return CVAnalysis(
        id=uuid4(),
        candidate_id=uuid4(),
        cv_file_path="/tmp/test_cv.pdf",
        extracted_text="Senior Python developer with 5 years experience...",
        summary="Senior Python developer with 5 years experience",
        skills=[
            ExtractedSkill(skill="Python", proficiency="expert", years=5),
            ExtractedSkill(skill="FastAPI", proficiency="intermediate", years=2),
            ExtractedSkill(skill="PostgreSQL", proficiency="intermediate", years=3),
            ExtractedSkill(skill="Docker", proficiency="beginner", years=1),
        ],
        work_experience_years=5,
    )


@pytest.fixture
def initial_state(sample_cv_analysis):
    """Create initial planning state."""
    cv_id = sample_cv_analysis.id
    candidate_id = sample_cv_analysis.candidate_id

    return {
        "cv_analysis_id": cv_id,
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
        "checkpoint_thread_id": "test_thread_123",
    }


class TestPlanningWorkflow:
    """Test suite for PlanningWorkflow class."""

    def test_initialization(self, workflow, mock_checkpointer):
        """Test workflow initializes with all dependencies."""
        assert workflow.checkpointer == mock_checkpointer
        assert workflow.llm is not None
        assert workflow.cv_repo is not None
        assert workflow.question_repo is not None
        assert workflow.interview_repo is not None
        assert workflow.vector_search is not None
        assert workflow.app is not None

    async def test_load_cv_node_success(self, workflow, mock_cv_repo, sample_cv_analysis):
        """Test load_cv_node successfully loads CV analysis."""
        # Setup
        mock_cv_repo.get_by_id.return_value = sample_cv_analysis
        state = {
            "cv_analysis_id": sample_cv_analysis.id,
            "candidate_id": sample_cv_analysis.candidate_id,
        }

        # Execute
        result = await workflow._load_cv_node(state)

        # Verify
        assert "cv_analysis" in result
        assert result["cv_analysis"] == sample_cv_analysis
        assert "errors" not in result or not result["errors"]
        mock_cv_repo.get_by_id.assert_called_once_with(sample_cv_analysis.id)

    async def test_load_cv_node_not_found(self, workflow, mock_cv_repo):
        """Test load_cv_node handles missing CV analysis."""
        # Setup
        cv_id = uuid4()
        mock_cv_repo.get_by_id.return_value = None
        state = {"cv_analysis_id": cv_id, "candidate_id": uuid4()}

        # Execute
        result = await workflow._load_cv_node(state)

        # Verify
        assert "errors" in result
        assert len(result["errors"]) > 0
        assert str(cv_id) in result["errors"][0]

    async def test_load_cv_node_error(self, workflow, mock_cv_repo):
        """Test load_cv_node handles repository errors."""
        # Setup
        mock_cv_repo.get_by_id.side_effect = Exception("Database connection failed")
        state = {"cv_analysis_id": uuid4(), "candidate_id": uuid4()}

        # Execute
        result = await workflow._load_cv_node(state)

        # Verify
        assert "errors" in result
        assert len(result["errors"]) > 0
        assert "Database connection failed" in result["errors"][0]

    async def test_calculate_count_node_success(self, workflow, sample_cv_analysis):
        """Test calculate_count_node calculates question count."""
        # Setup
        state = {"cv_analysis": sample_cv_analysis}

        # Execute
        result = await workflow._calculate_count_node(state)

        # Verify
        assert "question_count" in result
        assert result["question_count"] >= 2
        assert result["question_count"] <= 5
        assert "errors" not in result or not result["errors"]

    async def test_calculate_count_node_missing_cv(self, workflow):
        """Test calculate_count_node handles missing CV analysis."""
        # Setup
        state = {"cv_analysis": None}

        # Execute
        result = await workflow._calculate_count_node(state)

        # Verify
        assert "errors" in result
        assert "CV analysis missing" in result["errors"][0]

    async def test_prepare_specs_node_success(self, workflow, sample_cv_analysis, mock_vector_search):
        """Test prepare_specs_node creates question specifications."""
        # Setup
        mock_vector_search.search.return_value = [
            {"text": "Example Python question", "difficulty": "medium"},
            {"text": "Another Python question", "difficulty": "easy"},
        ]
        state = {
            "cv_analysis": sample_cv_analysis,
            "question_count": 3,
        }

        # Execute
        result = await workflow._prepare_specs_node(state)

        # Verify
        assert "question_specs" in result
        assert len(result["question_specs"]) == 3

        # Check spec structure
        for spec in result["question_specs"]:
            assert "skill" in spec
            assert "difficulty" in spec
            assert "exemplars" in spec

    async def test_prepare_specs_node_vector_search_failure(
        self, workflow, sample_cv_analysis, mock_vector_search
    ):
        """Test prepare_specs_node continues when vector search fails."""
        # Setup
        mock_vector_search.search.side_effect = Exception("Vector DB unavailable")
        state = {
            "cv_analysis": sample_cv_analysis,
            "question_count": 2,
        }

        # Execute
        result = await workflow._prepare_specs_node(state)

        # Verify - should continue with empty exemplars
        assert "question_specs" in result
        assert len(result["question_specs"]) == 2
        # Exemplars should be empty lists due to search failure
        for spec in result["question_specs"]:
            assert spec["exemplars"] == []

    async def test_generate_batch_node_success(
        self, workflow, sample_cv_analysis, mock_llm
    ):
        """Test generate_batch_node generates complete question sets using unified method."""
        # Setup - unified method returns list of tuples (question, ideal_answer, rationale)
        mock_llm.generate_questions_with_answers_and_rationales_batch.return_value = [
            (
                "What is Python GIL?",
                "GIL is Global Interpreter Lock...",
                "This tests understanding of Python internals",
            ),
            (
                "Explain async/await in Python",
                "Async/await enables asynchronous programming...",
                "This assesses async programming knowledge",
            ),
        ]

        state = {
            "cv_analysis": sample_cv_analysis,
            "question_specs": [
                {"skill": "Python", "difficulty": "medium", "exemplars": []},
                {"skill": "FastAPI", "difficulty": "easy", "exemplars": []},
            ],
        }

        # Execute
        result = await workflow._generate_batch_node(state)

        # Verify
        assert "generated_questions" in result
        assert "generated_answers" in result
        assert "generated_rationales" in result
        assert len(result["generated_questions"]) == 2
        assert len(result["generated_answers"]) == 2
        assert len(result["generated_rationales"]) == 2
        assert result["generated_questions"][0] == "What is Python GIL?"
        assert result["generated_answers"][0] == "GIL is Global Interpreter Lock..."
        assert result["generated_rationales"][0] == "This tests understanding of Python internals"

        # Verify unified LLM method called correctly
        mock_llm.generate_questions_with_answers_and_rationales_batch.assert_called_once()

    async def test_generate_batch_node_missing_specs(self, workflow):
        """Test generate_batch_node handles missing specs."""
        # Setup
        state = {
            "cv_analysis": None,
            "question_specs": [],
        }

        # Execute
        result = await workflow._generate_batch_node(state)

        # Verify
        assert "errors" in result
        assert "Missing question specs" in result["errors"][0]

    async def test_generate_batch_node_llm_error(
        self, workflow, sample_cv_analysis, mock_llm
    ):
        """Test generate_batch_node handles LLM errors."""
        # Setup
        mock_llm.generate_questions_with_answers_and_rationales_batch.side_effect = Exception("LLM API timeout")
        state = {
            "cv_analysis": sample_cv_analysis,
            "question_specs": [
                {"skill": "Python", "difficulty": "medium", "exemplars": []}
            ],
        }

        # Execute
        result = await workflow._generate_batch_node(state)

        # Verify
        assert "errors" in result
        assert "LLM API timeout" in result["errors"][0]

    async def test_store_questions_node_success(
        self, workflow, mock_question_repo
    ):
        """Test store_questions_node saves questions to database."""
        # Setup
        question_id_1 = uuid4()
        question_id_2 = uuid4()

        mock_question_repo.create.side_effect = [
            Question(
                id=question_id_1,
                text="What is Python GIL?",
                question_type=QuestionType.TECHNICAL,
                difficulty=DifficultyLevel.MEDIUM,
                skills=["Python"],
                ideal_answer="GIL is...",
                rationale="Tests understanding",
            ),
            Question(
                id=question_id_2,
                text="Explain async/await",
                question_type=QuestionType.TECHNICAL,
                difficulty=DifficultyLevel.EASY,
                skills=["FastAPI"],
                ideal_answer="Async/await...",
                rationale="Tests async knowledge",
            ),
        ]

        state = {
            "generated_questions": ["What is Python GIL?", "Explain async/await"],
            "generated_answers": ["GIL is...", "Async/await..."],
            "generated_rationales": ["Tests understanding", "Tests async knowledge"],
            "question_specs": [
                {"skill": "Python", "difficulty": "medium"},
                {"skill": "FastAPI", "difficulty": "easy"},
            ],
        }

        # Execute
        result = await workflow._store_questions_node(state)

        # Verify
        assert "stored_question_ids" in result
        assert len(result["stored_question_ids"]) == 2
        assert question_id_1 in result["stored_question_ids"]
        assert question_id_2 in result["stored_question_ids"]
        assert mock_question_repo.create.call_count == 2

    async def test_store_questions_node_no_questions(self, workflow):
        """Test store_questions_node handles empty question list."""
        # Setup
        state = {
            "generated_questions": [],
            "generated_answers": [],
            "generated_rationales": [],
            "question_specs": [],
        }

        # Execute
        result = await workflow._store_questions_node(state)

        # Verify
        assert "errors" in result
        assert "No questions to store" in result["errors"][0]

    async def test_update_interview_node_success(
        self, workflow, mock_interview_repo
    ):
        """Test update_interview_node creates and updates interview."""
        # Setup
        candidate_id = uuid4()
        cv_analysis_id = uuid4()
        question_ids = [uuid4(), uuid4()]

        # Mock no existing interview
        mock_interview_repo.get_active_by_candidate.return_value = None

        # Mock interview creation and update
        created_interview = Interview(
            id=uuid4(),
            candidate_id=candidate_id,
            status=InterviewStatus.IDLE,
            cv_analysis_id=cv_analysis_id,
        )
        mock_interview_repo.create.return_value = created_interview
        mock_interview_repo.update.return_value = created_interview

        state = {
            "candidate_id": candidate_id,
            "cv_analysis_id": cv_analysis_id,
            "stored_question_ids": question_ids,
        }

        # Execute
        result = await workflow._update_interview_node(state)

        # Verify
        assert "interview" in result
        assert result["interview"] is not None
        mock_interview_repo.create.assert_called_once()
        mock_interview_repo.update.assert_called_once()

    async def test_update_interview_node_no_question_ids(self, workflow):
        """Test update_interview_node handles missing question IDs."""
        # Setup
        state = {
            "candidate_id": uuid4(),
            "cv_analysis_id": uuid4(),
            "stored_question_ids": [],
        }

        # Execute
        result = await workflow._update_interview_node(state)

        # Verify
        assert "errors" in result
        assert "No question IDs" in result["errors"][0]

    async def test_handle_error_node_retry(self, workflow):
        """Test handle_error_node allows retry within max attempts."""
        # Setup
        state = {
            "errors": ["LLM timeout"],
            "retry_count": 1,
        }

        # Execute
        result = await workflow._handle_error_node(state)

        # Verify
        assert "retry_count" in result
        assert result["retry_count"] == 2
        assert "errors" in result
        assert result["errors"] == []  # Errors cleared for retry

    async def test_handle_error_node_max_retries(self, workflow):
        """Test handle_error_node stops after max retries."""
        # Setup
        state = {
            "errors": ["LLM timeout"],
            "retry_count": 3,
        }

        # Execute
        result = await workflow._handle_error_node(state)

        # Verify
        assert "errors" in result
        assert len(result["errors"]) > 0
        assert "Max retry attempts exceeded" in result["errors"][-1]

    def test_check_for_errors_with_errors(self, workflow):
        """Test _check_for_errors returns 'error' when errors exist."""
        # Setup
        state = {"errors": ["Some error"]}

        # Execute
        result = workflow._check_for_errors(state)

        # Verify
        assert result == "error"

    def test_check_for_errors_no_errors(self, workflow):
        """Test _check_for_errors returns 'continue' when no errors."""
        # Setup
        state = {"errors": []}

        # Execute
        result = workflow._check_for_errors(state)

        # Verify
        assert result == "continue"

    async def test_execute_success_flow(
        self,
        workflow,
        mock_cv_repo,
        mock_llm,
        mock_question_repo,
        mock_interview_repo,
        sample_cv_analysis,
    ):
        """Test complete execute workflow with successful flow."""
        # Setup all mocks for full workflow
        cv_id = sample_cv_analysis.id
        candidate_id = sample_cv_analysis.candidate_id

        mock_cv_repo.get_by_id.return_value = sample_cv_analysis

        mock_llm.generate_questions_with_answers_and_rationales_batch.return_value = [
            ("Question 1", "Answer 1", "Rationale 1"),
            ("Question 2", "Answer 2", "Rationale 2"),
        ]

        question_1 = Question(
            id=uuid4(),
            text="Question 1",
            question_type=QuestionType.TECHNICAL,
            difficulty=DifficultyLevel.MEDIUM,
            skills=["Python"],
            ideal_answer="Answer 1",
            rationale="Rationale 1",
        )
        question_2 = Question(
            id=uuid4(),
            text="Question 2",
            question_type=QuestionType.TECHNICAL,
            difficulty=DifficultyLevel.EASY,
            skills=["FastAPI"],
            ideal_answer="Answer 2",
            rationale="Rationale 2",
        )
        mock_question_repo.create.side_effect = [question_1, question_2]

        interview = Interview(
            id=uuid4(),
            candidate_id=candidate_id,
            status=InterviewStatus.QUESTIONING,
            cv_analysis_id=cv_id,
        )
        mock_interview_repo.get_active_by_candidate.return_value = None
        mock_interview_repo.create.return_value = interview
        mock_interview_repo.update.return_value = interview

        # Mock the compiled app
        workflow.app = AsyncMock()
        workflow.app.ainvoke = AsyncMock(return_value={
            "stored_question_ids": [question_1.id, question_2.id],
            "interview": interview,
            "errors": [],
        })

        # Execute
        result = await workflow.execute(
            cv_analysis_id=cv_id,
            candidate_id=candidate_id,
        )

        # Verify
        assert "question_ids" in result
        assert "interview" in result
        assert "thread_id" in result
        assert len(result["question_ids"]) == 2
        assert result["interview"] == interview

    async def test_execute_with_errors(
        self,
        workflow,
        mock_cv_repo,
    ):
        """Test execute workflow handles errors."""
        # Setup
        cv_id = uuid4()
        candidate_id = uuid4()

        # Mock the compiled app to return errors
        workflow.app = AsyncMock()
        workflow.app.ainvoke = AsyncMock(return_value={
            "errors": ["CV analysis not found"],
            "stored_question_ids": [],
            "interview": None,
        })

        # Execute and verify exception
        with pytest.raises(Exception) as exc_info:
            await workflow.execute(
                cv_analysis_id=cv_id,
                candidate_id=candidate_id,
            )

        assert "Workflow failed" in str(exc_info.value)

    async def test_execute_with_custom_thread_id(self, workflow):
        """Test execute workflow with custom thread ID."""
        # Setup
        custom_thread_id = "custom_thread_456"

        workflow.app = AsyncMock()
        workflow.app.ainvoke = AsyncMock(return_value={
            "stored_question_ids": [uuid4()],
            "interview": MagicMock(),
            "errors": [],
        })

        # Execute
        result = await workflow.execute(
            cv_analysis_id=uuid4(),
            candidate_id=uuid4(),
            thread_id=custom_thread_id,
        )

        # Verify custom thread ID used
        assert result["thread_id"] == custom_thread_id
