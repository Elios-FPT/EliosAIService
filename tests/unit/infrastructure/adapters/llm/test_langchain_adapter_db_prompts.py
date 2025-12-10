"""Unit tests for LangChainAdapter DB prompt loading.

Tests all 9 refactored methods to verify DB prompt loading, fallback behavior,
and execution logging.
"""

from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from langchain_core.language_models import BaseChatModel

from src.infrastructure.adapters.llm.langchain_adapter import LangChainAdapter
from src.domain.models.evaluation import FollowUpEvaluationContext
from src.domain.models.prompt_template import PromptTemplate
from src.domain.models.question import DifficultyLevel, Question, QuestionType


@pytest.fixture
def mock_chat_model():
    """Create a mock LangChain chat model."""
    model = MagicMock(spec=BaseChatModel)
    model.model_name = "gpt-4"
    model.ainvoke = AsyncMock()
    return model


@pytest.fixture
def mock_prompt_repo():
    """Create a mock PromptRepositoryPort."""
    repo = AsyncMock()
    return repo


@pytest.fixture
def sample_prompt_template():
    """Create a sample PromptTemplate for testing."""
    return PromptTemplate(
        id=uuid4(),
        name="test_prompt",
        version=2,
        template_json={
            "system": "You are an expert evaluator.",
            "user_template": "Question: {question_text}\nAnswer: {answer_text}",
            "variables": ["question_text", "answer_text"],
        },
        is_active=True,
        is_draft=False,
        created_by="test",
    )


def create_method_specific_prompt_template(prompt_name: str, variables: list[str]) -> PromptTemplate:
    """Create a prompt template with method-specific variables."""
    return PromptTemplate(
        id=uuid4(),
        name=prompt_name,
        version=1,
        template_json={
            "system": "You are a helpful assistant.",
            "user_template": " ".join([f"{{{v}}}" for v in variables]),
            "variables": variables,
        },
        is_active=True,
        is_draft=False,
        created_by="test",
    )


def mock_chain_ainvoke(adapter: LangChainAdapter, return_value: dict):
    """Helper to mock chain's ainvoke method."""
    mock_chain = AsyncMock()
    mock_chain.ainvoke = AsyncMock(return_value=return_value)
    original_get_chain = adapter._get_or_build_chain

    def patched_get_chain(*args, **kwargs):
        return mock_chain

    adapter._get_or_build_chain = patched_get_chain
    return mock_chain


@pytest.fixture
def sample_question():
    """Create a sample Question for testing."""
    return Question(
        id=uuid4(),
        text="What is Python?",
        question_type=QuestionType.TECHNICAL,
        difficulty=DifficultyLevel.MEDIUM,
        skills=["Python"],
    )


class TestEvaluateAnswerDB:
    """Test evaluate_answer with DB prompt loading."""

    @pytest.mark.asyncio
    async def test_evaluate_answer_with_db_prompt(
        self, mock_prompt_repo, mock_chat_model, sample_question
    ):
        """Test evaluate_answer loads DB prompt and logs execution."""
        # Setup prompt template with correct variables
        prompt_template = create_method_specific_prompt_template(
            "answer_evaluation",
            ["question_text", "difficulty", "skill", "answer_text", "followup_context"],
        )
        mock_prompt_repo.get_active_prompt.return_value = prompt_template
        mock_prompt_repo.log_execution.return_value = None

        adapter = LangChainAdapter(
            model=mock_chat_model, prompt_repository=mock_prompt_repo
        )

        # Mock the chain's ainvoke to return parsed JSON
        mock_chain = AsyncMock()
        mock_chain.ainvoke = AsyncMock(
            return_value={
                "score": 85.0,
                "feedback": "Good answer",
                "strengths": ["Clear explanation"],
                "weaknesses": ["Missing examples"],
                "missing_concepts": ["Error handling"],
            }
        )

        # Patch _get_or_build_chain to return our mock chain
        original_get_chain = adapter._get_or_build_chain
        adapter._get_or_build_chain = lambda *args, **kwargs: mock_chain

        # Execute
        result = await adapter.evaluate_answer(
            question=sample_question,
            answer_text="Python is a programming language...",
            context={"interview_id": "test-123"},
        )

        # Assertions
        assert result.score == 85.0
        assert result.reasoning == "Good answer"
        assert "Clear explanation" in result.strengths

        # Verify DB prompt loaded
        mock_prompt_repo.get_active_prompt.assert_called_once_with("answer_evaluation")

        # Verify execution logged
        mock_prompt_repo.log_execution.assert_called_once()
        log_call = mock_prompt_repo.log_execution.call_args
        assert log_call[1]["prompt_template_id"] == prompt_template.id
        assert log_call[1]["execution_data"]["success"] is True

    @pytest.mark.asyncio
    async def test_evaluate_answer_fallback_to_registry(
        self, mock_prompt_repo, mock_chat_model, sample_question
    ):
        """Test evaluate_answer falls back to PROMPT_REGISTRY when DB fails."""
        # Simulate DB failure
        mock_prompt_repo.get_active_prompt.return_value = None

        mock_chat_model.ainvoke.return_value = {
            "score": 85.0,
            "feedback": "Good answer",
            "strengths": [],
            "weaknesses": [],
            "missing_concepts": [],
        }

        # Setup adapter
        adapter = LangChainAdapter(
            model=mock_chat_model, prompt_repository=mock_prompt_repo
        )

        # Execute (should still work with PROMPT_REGISTRY)
        result = await adapter.evaluate_answer(
            question=sample_question,
            answer_text="Python is a programming language...",
            context={},
        )

        # Should still work
        assert result.score == 85.0

        # No execution logging (no DB prompt)
        mock_prompt_repo.log_execution.assert_not_called()

    @pytest.mark.asyncio
    async def test_evaluate_answer_db_exception_fallback(
        self, mock_prompt_repo, mock_chat_model, sample_question
    ):
        """Test evaluate_answer handles DB exception gracefully."""
        # Simulate DB exception
        mock_prompt_repo.get_active_prompt.side_effect = Exception("DB connection lost")

        mock_chat_model.ainvoke.return_value = {
            "score": 85.0,
            "feedback": "Good answer",
            "strengths": [],
            "weaknesses": [],
            "missing_concepts": [],
        }

        # Setup adapter
        adapter = LangChainAdapter(
            model=mock_chat_model, prompt_repository=mock_prompt_repo
        )

        # Execute (should fall back gracefully)
        result = await adapter.evaluate_answer(
            question=sample_question,
            answer_text="Python is a programming language...",
            context={},
        )

        # Should still work with PROMPT_REGISTRY
        assert result.score == 85.0

    @pytest.mark.asyncio
    async def test_evaluate_answer_execution_failure_logged(
        self, mock_prompt_repo, mock_chat_model, sample_prompt_template, sample_question
    ):
        """Test evaluate_answer logs execution failure."""
        # Simulate chain execution failure
        mock_prompt_repo.get_active_prompt.return_value = sample_prompt_template
        mock_chat_model.ainvoke.side_effect = Exception("LLM timeout")

        # Setup adapter
        adapter = LangChainAdapter(
            model=mock_chat_model, prompt_repository=mock_prompt_repo
        )

        # Execute (should raise exception)
        with pytest.raises(Exception, match="LLM timeout"):
            await adapter.evaluate_answer(
                question=sample_question,
                answer_text="Python is...",
                context={"interview_id": "test-123"},
            )

        # Verify failure logged
        mock_prompt_repo.log_execution.assert_called_once()
        log_call = mock_prompt_repo.log_execution.call_args
        assert log_call[1]["execution_data"]["success"] is False
        assert "LLM timeout" in log_call[1]["execution_data"]["error_message"]


class TestGenerateRationaleDB:
    """Test generate_rationale with DB prompt loading."""

    @pytest.mark.asyncio
    async def test_generate_rationale_with_db_prompt(
        self, mock_prompt_repo, mock_chat_model, sample_prompt_template
    ):
        """Test generate_rationale loads DB prompt and logs execution."""
        mock_prompt_repo.get_active_prompt.return_value = sample_prompt_template
        mock_prompt_repo.log_execution.return_value = None

        mock_chat_model.ainvoke.return_value = {"rationale_text": "This is the rationale"}

        adapter = LangChainAdapter(
            model=mock_chat_model, prompt_repository=mock_prompt_repo
        )

        result = await adapter.generate_rationale(
            question_text="What is Python?",
            ideal_answer="Python is...",
            context={"interview_id": "test-123"},
        )

        assert result == "This is the rationale"
        mock_prompt_repo.get_active_prompt.assert_called_once_with("rationale_generation")
        mock_prompt_repo.log_execution.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_rationale_fallback_to_registry(
        self, mock_prompt_repo, mock_chat_model
    ):
        """Test generate_rationale falls back to PROMPT_REGISTRY."""
        mock_prompt_repo.get_active_prompt.return_value = None
        mock_chat_model.ainvoke.return_value = {"rationale_text": "Fallback rationale"}

        adapter = LangChainAdapter(
            model=mock_chat_model, prompt_repository=mock_prompt_repo
        )

        result = await adapter.generate_rationale(
            question_text="What is Python?", ideal_answer="Python is...", context={}
        )

        assert result == "Fallback rationale"
        mock_prompt_repo.log_execution.assert_not_called()

    @pytest.mark.asyncio
    async def test_generate_rationale_db_exception_fallback(
        self, mock_prompt_repo, mock_chat_model
    ):
        """Test generate_rationale handles DB exception gracefully."""
        mock_prompt_repo.get_active_prompt.side_effect = Exception("DB error")
        mock_chat_model.ainvoke.return_value = {"rationale_text": "Exception fallback"}

        adapter = LangChainAdapter(
            model=mock_chat_model, prompt_repository=mock_prompt_repo
        )

        result = await adapter.generate_rationale(
            question_text="What is Python?", ideal_answer="Python is...", context={}
        )

        assert result == "Exception fallback"

    @pytest.mark.asyncio
    async def test_generate_rationale_execution_failure_logged(
        self, mock_prompt_repo, mock_chat_model, sample_prompt_template
    ):
        """Test generate_rationale logs execution failure."""
        mock_prompt_repo.get_active_prompt.return_value = sample_prompt_template
        mock_chat_model.ainvoke.side_effect = Exception("LLM error")

        adapter = LangChainAdapter(
            model=mock_chat_model, prompt_repository=mock_prompt_repo
        )

        with pytest.raises(Exception, match="LLM error"):
            await adapter.generate_rationale(
                question_text="What is Python?",
                ideal_answer="Python is...",
                context={"interview_id": "test-123"},
            )

        log_call = mock_prompt_repo.log_execution.call_args
        assert log_call[1]["execution_data"]["success"] is False


class TestDetectConceptGapsDB:
    """Test detect_concept_gaps with DB prompt loading."""

    @pytest.mark.asyncio
    async def test_detect_concept_gaps_with_db_prompt(
        self, mock_prompt_repo, mock_chat_model, sample_prompt_template
    ):
        """Test detect_concept_gaps loads DB prompt and logs execution."""
        mock_prompt_repo.get_active_prompt.return_value = sample_prompt_template
        mock_prompt_repo.log_execution.return_value = None

        mock_chat_model.ainvoke.return_value = {
            "concepts": ["OOP", "Inheritance"],
            "keywords": ["class", "method"],
            "confirmed": True,
            "severity": "major",
        }

        adapter = LangChainAdapter(
            model=mock_chat_model, prompt_repository=mock_prompt_repo
        )

        result = await adapter.detect_concept_gaps(
            answer_text="Python is a language",
            ideal_answer="Python supports OOP with classes",
            question_text="What is Python?",
            keyword_gaps=["OOP"],
            context={"interview_id": "test-123"},
        )

        assert result["concepts"] == ["OOP", "Inheritance"]
        assert result["confirmed"] is True
        mock_prompt_repo.get_active_prompt.assert_called_once_with("gap_detection")
        mock_prompt_repo.log_execution.assert_called_once()

    @pytest.mark.asyncio
    async def test_detect_concept_gaps_fallback_to_registry(
        self, mock_prompt_repo, mock_chat_model
    ):
        """Test detect_concept_gaps falls back to PROMPT_REGISTRY."""
        mock_prompt_repo.get_active_prompt.return_value = None
        mock_chat_model.ainvoke.return_value = {
            "concepts": [],
            "keywords": [],
            "confirmed": False,
            "severity": "minor",
        }

        adapter = LangChainAdapter(
            model=mock_chat_model, prompt_repository=mock_prompt_repo
        )

        result = await adapter.detect_concept_gaps(
            answer_text="Answer",
            ideal_answer="Ideal",
            question_text="Question",
            keyword_gaps=[],
            context={},
        )

        assert result["confirmed"] is False
        mock_prompt_repo.log_execution.assert_not_called()

    @pytest.mark.asyncio
    async def test_detect_concept_gaps_db_exception_fallback(
        self, mock_prompt_repo, mock_chat_model
    ):
        """Test detect_concept_gaps handles DB exception gracefully."""
        mock_prompt_repo.get_active_prompt.side_effect = Exception("DB error")
        mock_chat_model.ainvoke.return_value = {
            "concepts": [],
            "keywords": [],
            "confirmed": False,
            "severity": "minor",
        }

        adapter = LangChainAdapter(
            model=mock_chat_model, prompt_repository=mock_prompt_repo
        )

        result = await adapter.detect_concept_gaps(
            answer_text="Answer",
            ideal_answer="Ideal",
            question_text="Question",
            keyword_gaps=[],
            context={},
        )

        assert result is not None

    @pytest.mark.asyncio
    async def test_detect_concept_gaps_execution_failure_logged(
        self, mock_prompt_repo, mock_chat_model, sample_prompt_template
    ):
        """Test detect_concept_gaps logs execution failure."""
        mock_prompt_repo.get_active_prompt.return_value = sample_prompt_template
        mock_chat_model.ainvoke.side_effect = Exception("LLM error")

        adapter = LangChainAdapter(
            model=mock_chat_model, prompt_repository=mock_prompt_repo
        )

        with pytest.raises(Exception, match="LLM error"):
            await adapter.detect_concept_gaps(
                answer_text="Answer",
                ideal_answer="Ideal",
                question_text="Question",
                keyword_gaps=[],
                context={"interview_id": "test-123"},
            )

        log_call = mock_prompt_repo.log_execution.call_args
        assert log_call[1]["execution_data"]["success"] is False


class TestGenerateFollowupQuestionDB:
    """Test generate_followup_question with DB prompt loading."""

    @pytest.mark.asyncio
    async def test_generate_followup_question_with_db_prompt(
        self, mock_prompt_repo, mock_chat_model, sample_prompt_template
    ):
        """Test generate_followup_question loads DB prompt and logs execution."""
        mock_prompt_repo.get_active_prompt.return_value = sample_prompt_template
        mock_prompt_repo.log_execution.return_value = None

        mock_chat_model.ainvoke.return_value = {"question_text": "Can you explain OOP?"}

        adapter = LangChainAdapter(
            model=mock_chat_model, prompt_repository=mock_prompt_repo
        )

        result = await adapter.generate_followup_question(
            parent_question="What is Python?",
            answer_text="Python is a language",
            missing_concepts=["OOP"],
            severity="major",
            order=1,
            context={"interview_id": "test-123"},
        )

        assert result == "Can you explain OOP?"
        mock_prompt_repo.get_active_prompt.assert_called_once_with("follow_up_generation")
        mock_prompt_repo.log_execution.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_followup_question_fallback_to_registry(
        self, mock_prompt_repo, mock_chat_model
    ):
        """Test generate_followup_question falls back to PROMPT_REGISTRY."""
        mock_prompt_repo.get_active_prompt.return_value = None
        mock_chat_model.ainvoke.return_value = {"question_text": "Fallback question"}

        adapter = LangChainAdapter(
            model=mock_chat_model, prompt_repository=mock_prompt_repo
        )

        result = await adapter.generate_followup_question(
            parent_question="Question",
            answer_text="Answer",
            missing_concepts=[],
            severity="minor",
            order=1,
            context={},
        )

        assert result == "Fallback question"
        mock_prompt_repo.log_execution.assert_not_called()

    @pytest.mark.asyncio
    async def test_generate_followup_question_db_exception_fallback(
        self, mock_prompt_repo, mock_chat_model
    ):
        """Test generate_followup_question handles DB exception gracefully."""
        mock_prompt_repo.get_active_prompt.side_effect = Exception("DB error")
        mock_chat_model.ainvoke.return_value = {"question_text": "Exception fallback"}

        adapter = LangChainAdapter(
            model=mock_chat_model, prompt_repository=mock_prompt_repo
        )

        result = await adapter.generate_followup_question(
            parent_question="Question",
            answer_text="Answer",
            missing_concepts=[],
            severity="minor",
            order=1,
            context={},
        )

        assert result == "Exception fallback"

    @pytest.mark.asyncio
    async def test_generate_followup_question_execution_failure_logged(
        self, mock_prompt_repo, mock_chat_model, sample_prompt_template
    ):
        """Test generate_followup_question logs execution failure."""
        mock_prompt_repo.get_active_prompt.return_value = sample_prompt_template
        mock_chat_model.ainvoke.side_effect = Exception("LLM error")

        adapter = LangChainAdapter(
            model=mock_chat_model, prompt_repository=mock_prompt_repo
        )

        with pytest.raises(Exception, match="LLM error"):
            await adapter.generate_followup_question(
                parent_question="Question",
                answer_text="Answer",
                missing_concepts=[],
                severity="minor",
                order=1,
                context={"interview_id": "test-123"},
            )

        log_call = mock_prompt_repo.log_execution.call_args
        assert log_call[1]["execution_data"]["success"] is False


class TestGenerateFeedbackReportDB:
    """Test generate_feedback_report with DB prompt loading."""

    @pytest.mark.asyncio
    async def test_generate_feedback_report_with_db_prompt(
        self, mock_prompt_repo, mock_chat_model, sample_prompt_template, sample_question
    ):
        """Test generate_feedback_report loads DB prompt and logs execution."""
        mock_prompt_repo.get_active_prompt.return_value = sample_prompt_template
        mock_prompt_repo.log_execution.return_value = None

        mock_chat_model.ainvoke.return_value = {"report_text": "Feedback report content"}

        adapter = LangChainAdapter(
            model=mock_chat_model, prompt_repository=mock_prompt_repo
        )

        result = await adapter.generate_feedback_report(
            interview_id=uuid4(),
            questions=[sample_question],
            answers=[{"answer": "Answer text"}],
        )

        assert result == "Feedback report content"
        mock_prompt_repo.get_active_prompt.assert_called_once_with("feedback_report")
        mock_prompt_repo.log_execution.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_feedback_report_fallback_to_registry(
        self, mock_prompt_repo, mock_chat_model, sample_question
    ):
        """Test generate_feedback_report falls back to PROMPT_REGISTRY."""
        mock_prompt_repo.get_active_prompt.return_value = None
        mock_chat_model.ainvoke.return_value = {"report_text": "Fallback report"}

        adapter = LangChainAdapter(
            model=mock_chat_model, prompt_repository=mock_prompt_repo
        )

        result = await adapter.generate_feedback_report(
            interview_id=uuid4(), questions=[sample_question], answers=[]
        )

        assert result == "Fallback report"
        mock_prompt_repo.log_execution.assert_not_called()

    @pytest.mark.asyncio
    async def test_generate_feedback_report_db_exception_fallback(
        self, mock_prompt_repo, mock_chat_model, sample_question
    ):
        """Test generate_feedback_report handles DB exception gracefully."""
        mock_prompt_repo.get_active_prompt.side_effect = Exception("DB error")
        mock_chat_model.ainvoke.return_value = {"report_text": "Exception fallback"}

        adapter = LangChainAdapter(
            model=mock_chat_model, prompt_repository=mock_prompt_repo
        )

        result = await adapter.generate_feedback_report(
            interview_id=uuid4(), questions=[sample_question], answers=[]
        )

        assert result == "Exception fallback"

    @pytest.mark.asyncio
    async def test_generate_feedback_report_execution_failure_logged(
        self, mock_prompt_repo, mock_chat_model, sample_prompt_template, sample_question
    ):
        """Test generate_feedback_report logs execution failure."""
        mock_prompt_repo.get_active_prompt.return_value = sample_prompt_template
        mock_chat_model.ainvoke.side_effect = Exception("LLM error")

        adapter = LangChainAdapter(
            model=mock_chat_model, prompt_repository=mock_prompt_repo
        )

        with pytest.raises(Exception, match="LLM error"):
            await adapter.generate_feedback_report(
                interview_id=uuid4(),
                questions=[sample_question],
                answers=[{"answer": "Answer"}],
            )

        log_call = mock_prompt_repo.log_execution.call_args
        assert log_call[1]["execution_data"]["success"] is False


class TestSummarizeCVDB:
    """Test summarize_cv with DB prompt loading."""

    @pytest.mark.asyncio
    async def test_summarize_cv_with_db_prompt(
        self, mock_prompt_repo, mock_chat_model, sample_prompt_template
    ):
        """Test summarize_cv loads DB prompt and logs execution."""
        mock_prompt_repo.get_active_prompt.return_value = sample_prompt_template
        mock_prompt_repo.log_execution.return_value = None

        mock_chat_model.ainvoke.return_value = {
            "summary_text": "5 years Python developer",
            "years_experience": 5,
        }

        adapter = LangChainAdapter(
            model=mock_chat_model, prompt_repository=mock_prompt_repo
        )

        result = await adapter.summarize_cv(
            cv_text="John Doe, Python developer...",
            context={"candidate_id": "test-123"},
        )

        assert result == "5 years Python developer"
        mock_prompt_repo.get_active_prompt.assert_called_once_with("cv_summary")
        mock_prompt_repo.log_execution.assert_called_once()

    @pytest.mark.asyncio
    async def test_summarize_cv_fallback_to_registry(
        self, mock_prompt_repo, mock_chat_model
    ):
        """Test summarize_cv falls back to PROMPT_REGISTRY."""
        mock_prompt_repo.get_active_prompt.return_value = None
        mock_chat_model.ainvoke.return_value = {
            "summary_text": "Fallback summary",
            "years_experience": 3,
        }

        adapter = LangChainAdapter(
            model=mock_chat_model, prompt_repository=mock_prompt_repo
        )

        result = await adapter.summarize_cv(cv_text="CV text", context={})

        assert result == "Fallback summary"
        mock_prompt_repo.log_execution.assert_not_called()

    @pytest.mark.asyncio
    async def test_summarize_cv_db_exception_fallback(
        self, mock_prompt_repo, mock_chat_model
    ):
        """Test summarize_cv handles DB exception gracefully."""
        mock_prompt_repo.get_active_prompt.side_effect = Exception("DB error")
        mock_chat_model.ainvoke.return_value = {
            "summary_text": "Exception fallback",
            "years_experience": 2,
        }

        adapter = LangChainAdapter(
            model=mock_chat_model, prompt_repository=mock_prompt_repo
        )

        result = await adapter.summarize_cv(cv_text="CV text", context={})

        assert result == "Exception fallback"

    @pytest.mark.asyncio
    async def test_summarize_cv_execution_failure_logged(
        self, mock_prompt_repo, mock_chat_model, sample_prompt_template
    ):
        """Test summarize_cv logs execution failure."""
        mock_prompt_repo.get_active_prompt.return_value = sample_prompt_template
        mock_chat_model.ainvoke.side_effect = Exception("LLM error")

        adapter = LangChainAdapter(
            model=mock_chat_model, prompt_repository=mock_prompt_repo
        )

        with pytest.raises(Exception, match="LLM error"):
            await adapter.summarize_cv(
                cv_text="CV text", context={"candidate_id": "test-123"}
            )

        log_call = mock_prompt_repo.log_execution.call_args
        assert log_call[1]["execution_data"]["success"] is False


class TestExtractSkillsDB:
    """Test extract_skills_from_text with DB prompt loading."""

    @pytest.mark.asyncio
    async def test_extract_skills_with_db_prompt(
        self, mock_prompt_repo, mock_chat_model, sample_prompt_template
    ):
        """Test extract_skills_from_text loads DB prompt and logs execution."""
        mock_prompt_repo.get_active_prompt.return_value = sample_prompt_template
        mock_prompt_repo.log_execution.return_value = None

        mock_chat_model.ainvoke.return_value = {
            "skills": [
                {"name": "Python", "category": "programming", "proficiency": "expert"},
                {"name": "FastAPI", "category": "framework", "proficiency": "intermediate"},
            ]
        }

        adapter = LangChainAdapter(
            model=mock_chat_model, prompt_repository=mock_prompt_repo
        )

        result = await adapter.extract_skills_from_text(
            text="Python developer with FastAPI experience",
            context={"candidate_id": "test-123"},
        )

        assert len(result) == 2
        assert result[0]["skill"] == "Python"
        mock_prompt_repo.get_active_prompt.assert_called_once_with("skill_extraction")
        mock_prompt_repo.log_execution.assert_called_once()

    @pytest.mark.asyncio
    async def test_extract_skills_fallback_to_registry(
        self, mock_prompt_repo, mock_chat_model
    ):
        """Test extract_skills_from_text falls back to PROMPT_REGISTRY."""
        mock_prompt_repo.get_active_prompt.return_value = None
        mock_chat_model.ainvoke.return_value = {"skills": []}

        adapter = LangChainAdapter(
            model=mock_chat_model, prompt_repository=mock_prompt_repo
        )

        result = await adapter.extract_skills_from_text(text="Text", context={})

        assert len(result) == 0
        mock_prompt_repo.log_execution.assert_not_called()

    @pytest.mark.asyncio
    async def test_extract_skills_db_exception_fallback(
        self, mock_prompt_repo, mock_chat_model
    ):
        """Test extract_skills_from_text handles DB exception gracefully."""
        mock_prompt_repo.get_active_prompt.side_effect = Exception("DB error")
        mock_chat_model.ainvoke.return_value = {"skills": []}

        adapter = LangChainAdapter(
            model=mock_chat_model, prompt_repository=mock_prompt_repo
        )

        result = await adapter.extract_skills_from_text(text="Text", context={})

        assert result is not None

    @pytest.mark.asyncio
    async def test_extract_skills_execution_failure_logged(
        self, mock_prompt_repo, mock_chat_model, sample_prompt_template
    ):
        """Test extract_skills_from_text logs execution failure."""
        mock_prompt_repo.get_active_prompt.return_value = sample_prompt_template
        mock_chat_model.ainvoke.side_effect = Exception("LLM error")

        adapter = LangChainAdapter(
            model=mock_chat_model, prompt_repository=mock_prompt_repo
        )

        with pytest.raises(Exception, match="LLM error"):
            await adapter.extract_skills_from_text(
                text="Text", context={"candidate_id": "test-123"}
            )

        log_call = mock_prompt_repo.log_execution.call_args
        assert log_call[1]["execution_data"]["success"] is False


class TestGenerateRecommendationsDB:
    """Test generate_interview_recommendations with DB prompt loading."""

    @pytest.mark.asyncio
    async def test_generate_recommendations_with_db_prompt(
        self, mock_prompt_repo, mock_chat_model, sample_prompt_template
    ):
        """Test generate_interview_recommendations loads DB prompt and logs execution."""
        mock_prompt_repo.get_active_prompt.return_value = sample_prompt_template
        mock_prompt_repo.log_execution.return_value = None

        mock_chat_model.ainvoke.return_value = {
            "strengths": ["Good communication"],
            "weaknesses": ["Needs more practice"],
            "study_topics": ["Python OOP"],
            "technique_tips": ["Speak clearly"],
        }

        adapter = LangChainAdapter(
            model=mock_chat_model, prompt_repository=mock_prompt_repo
        )

        result = await adapter.generate_interview_recommendations(
            context={
                "interview_id": "test-123",
                "total_answers": 5,
                "gap_progression": {},
                "evaluations": [],
            }
        )

        assert "strengths" in result
        assert "weaknesses" in result
        mock_prompt_repo.get_active_prompt.assert_called_once_with(
            "interview_recommendations"
        )
        mock_prompt_repo.log_execution.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_recommendations_fallback_to_registry(
        self, mock_prompt_repo, mock_chat_model
    ):
        """Test generate_interview_recommendations falls back to PROMPT_REGISTRY."""
        mock_prompt_repo.get_active_prompt.return_value = None
        mock_chat_model.ainvoke.return_value = {
            "strengths": [],
            "weaknesses": [],
            "study_topics": [],
            "technique_tips": [],
        }

        adapter = LangChainAdapter(
            model=mock_chat_model, prompt_repository=mock_prompt_repo
        )

        result = await adapter.generate_interview_recommendations(context={})

        assert "strengths" in result
        mock_prompt_repo.log_execution.assert_not_called()

    @pytest.mark.asyncio
    async def test_generate_recommendations_db_exception_fallback(
        self, mock_prompt_repo, mock_chat_model
    ):
        """Test generate_interview_recommendations handles DB exception gracefully."""
        mock_prompt_repo.get_active_prompt.side_effect = Exception("DB error")
        mock_chat_model.ainvoke.return_value = {
            "strengths": [],
            "weaknesses": [],
            "study_topics": [],
            "technique_tips": [],
        }

        adapter = LangChainAdapter(
            model=mock_chat_model, prompt_repository=mock_prompt_repo
        )

        result = await adapter.generate_interview_recommendations(context={})

        assert result is not None

    @pytest.mark.asyncio
    async def test_generate_recommendations_execution_failure_logged(
        self, mock_prompt_repo, mock_chat_model, sample_prompt_template
    ):
        """Test generate_interview_recommendations logs execution failure."""
        mock_prompt_repo.get_active_prompt.return_value = sample_prompt_template
        mock_chat_model.ainvoke.side_effect = Exception("LLM error")

        adapter = LangChainAdapter(
            model=mock_chat_model, prompt_repository=mock_prompt_repo
        )

        with pytest.raises(Exception, match="LLM error"):
            await adapter.generate_interview_recommendations(
                context={"interview_id": "test-123"}
            )

        log_call = mock_prompt_repo.log_execution.call_args
        assert log_call[1]["execution_data"]["success"] is False


class TestGenerateIdealAnswerDB:
    """Test generate_ideal_answer with DB prompt loading (logging enhancement only)."""

    @pytest.mark.asyncio
    async def test_generate_ideal_answer_with_db_prompt(
        self, mock_prompt_repo, mock_chat_model, sample_prompt_template
    ):
        """Test generate_ideal_answer loads DB prompt and logs execution."""
        mock_prompt_repo.get_active_prompt.return_value = sample_prompt_template
        mock_prompt_repo.log_execution.return_value = None

        mock_chat_model.ainvoke.return_value = {"ideal_answer": "Ideal answer text"}

        adapter = LangChainAdapter(
            model=mock_chat_model, prompt_repository=mock_prompt_repo
        )

        result = await adapter.generate_ideal_answer(
            question_text="What is Python?",
            context={"interview_id": "test-123"},
        )

        assert result == "Ideal answer text"
        mock_prompt_repo.get_active_prompt.assert_called_once_with("ideal_answer")
        mock_prompt_repo.log_execution.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_ideal_answer_execution_failure_logged(
        self, mock_prompt_repo, mock_chat_model, sample_prompt_template
    ):
        """Test generate_ideal_answer logs execution failure."""
        mock_prompt_repo.get_active_prompt.return_value = sample_prompt_template
        mock_chat_model.ainvoke.side_effect = Exception("LLM error")

        adapter = LangChainAdapter(
            model=mock_chat_model, prompt_repository=mock_prompt_repo
        )

        with pytest.raises(Exception, match="LLM error"):
            await adapter.generate_ideal_answer(
                question_text="What is Python?",
                context={"interview_id": "test-123"},
            )

        log_call = mock_prompt_repo.log_execution.call_args
        assert log_call[1]["execution_data"]["success"] is False

