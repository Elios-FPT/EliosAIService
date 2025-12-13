"""Unit tests for LangChainAdapter.

Tests all 13 LLMPort methods with mocked LangChain model responses.
Validates proper mapping from LangChain structured outputs to domain models.
"""

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from langchain_core.language_models import BaseChatModel

from src.infrastructure.adapters.llm.langchain_adapter import LangChainAdapter
from src.domain.models.answer import AnswerEvaluation
from src.domain.models.evaluation import FollowUpEvaluationContext
from src.domain.models.question import DifficultyLevel, Question, QuestionType
from src.domain.models.prompt_template import PromptTemplate


@pytest.fixture
def mock_chat_model():
    """Create a mock LangChain chat model."""
    model = MagicMock(spec=BaseChatModel)
    return model


@pytest.fixture
def langchain_adapter(mock_chat_model):
    """Create LangChainAdapter instance with mock model."""
    adapter = LangChainAdapter(model=mock_chat_model)
    # Replace all chains with AsyncMocks for testing
    for chain_name in adapter._chains:
        adapter._chains[chain_name] = MagicMock()
        adapter._chains[chain_name].ainvoke = AsyncMock()
    adapter._log_execution = AsyncMock()
    return adapter


class TestInitialization:
    """Test adapter initialization and chain building."""

    def test_adapter_initialization(self, mock_chat_model):
        """Test that adapter initializes with model and builds chains."""
        adapter = LangChainAdapter(model=mock_chat_model)

        assert adapter.model == mock_chat_model
        assert adapter._chains is not None
        assert isinstance(adapter._chains, dict)

    def test_chains_built_for_all_methods(self, langchain_adapter):
        """Test that chains are built for all 13 LLMPort methods."""
        expected_chains = [
            "generate_question",
            "evaluate_answer",
            "generate_ideal_answer",
            "generate_rationale",
            "detect_concept_gaps",
            "generate_followup_question",
            "generate_feedback_report",
            "summarize_cv",
            "extract_skills_from_text",
            "generate_interview_recommendations",
            "generate_questions_batch",
            "generate_ideal_answers_batch",
            "generate_rationales_batch",
        ]

        for chain_name in expected_chains:
            assert chain_name in langchain_adapter._chains, \
                f"Chain '{chain_name}' not found in adapter chains"


class TestDynamicChainHelper:
    """Test dynamic chain helper behavior."""

    def test_get_or_build_chain_with_db_template_and_cache(self, mock_chat_model):
        adapter = LangChainAdapter(model=mock_chat_model)
        db_template = {
            "system": "System",
            "user_template": "User says {question_text}",
            "variables": ["question_text"],
        }

        chain = adapter._get_or_build_chain(
            "generate_ideal_answer",
            db_template_json=db_template,
            cache_key="ideal:v1",
        )

        cache_key = "generate_ideal_answer:ideal:v1"
        assert cache_key in adapter._db_chain_cache
        assert adapter._db_chain_cache[cache_key] is chain

        # Subsequent calls should reuse cache
        chain_again = adapter._get_or_build_chain(
            "generate_ideal_answer",
            db_template_json=db_template,
            cache_key="ideal:v1",
        )
        assert chain is chain_again

    def test_get_or_build_chain_invalid_template_falls_back(self, mock_chat_model):
        adapter = LangChainAdapter(model=mock_chat_model)
        fallback_chain = adapter._chains["generate_ideal_answer"]

        chain = adapter._get_or_build_chain(
            "generate_ideal_answer",
            db_template_json={"system": "sys"},  # missing user_template
        )

        assert chain is fallback_chain

    def test_get_or_build_chain_without_db_template_returns_fallback(self, mock_chat_model):
        adapter = LangChainAdapter(model=mock_chat_model)
        fallback_chain = adapter._chains["generate_ideal_answer"]

        chain = adapter._get_or_build_chain("generate_ideal_answer")

        assert chain is fallback_chain


class TestGenerateQuestion:
    """Test generate_question method."""

    @pytest.mark.asyncio
    async def test_generate_question_basic(self, langchain_adapter):
        """Test basic question generation."""
        # Mock chain response
        mock_response = {"question_text": "What is polymorphism in OOP?", "reasoning": "Tests OOP knowledge"}
        langchain_adapter._chains["generate_question"].ainvoke.return_value = mock_response

        context = {"cv_summary": "Python developer", "covered_topics": [], "stage": "early"}
        result = await langchain_adapter.generate_question(
            context=context,
            skill="Python",
            difficulty="medium"
        )

        assert result == "What is polymorphism in OOP?"
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_generate_question_with_exemplars(self, langchain_adapter):
        """Test question generation with exemplar questions."""
        mock_response = {"question_text": "Explain Python decorators"}
        langchain_adapter._chains["generate_question"].ainvoke.return_value = mock_response

        context = {"cv_summary": "Python developer", "covered_topics": ["classes"], "stage": "mid"}
        exemplars = [
            {"text": "What are Python generators?", "difficulty": "MEDIUM"},
            {"text": "Explain list comprehensions", "difficulty": "EASY"}
        ]

        result = await langchain_adapter.generate_question(
            context=context,
            skill="Python",
            difficulty="medium",
            exemplars=exemplars
        )

        assert result == "Explain Python decorators"
        # Verify ainvoke was called with exemplar section
        call_args = langchain_adapter._chains["generate_question"].ainvoke.call_args[0][0]
        assert "exemplar_section" in call_args
        assert "What are Python generators?" in call_args["exemplar_section"]

    @pytest.mark.asyncio
    async def test_generate_question_no_exemplars(self, langchain_adapter):
        """Test question generation without exemplars."""
        mock_response = {"question_text": "What is REST API?"}
        langchain_adapter._chains["generate_question"].ainvoke.return_value = mock_response

        context = {"cv_summary": "Backend developer"}
        result = await langchain_adapter.generate_question(
            context=context,
            skill="API Design",
            difficulty="easy"
        )

        assert result == "What is REST API?"
        # Verify exemplar section is empty
        call_args = langchain_adapter._chains["generate_question"].ainvoke.call_args[0][0]
        assert call_args["exemplar_section"] == ""


class TestEvaluateAnswer:
    """Test evaluate_answer method."""

    @pytest.fixture
    def sample_question(self):
        """Create sample question for testing."""
        return Question(
            text="What is recursion?",
            question_type=QuestionType.TECHNICAL,
            difficulty=DifficultyLevel.MEDIUM,
            skills=["Python", "Algorithms"],
        )

    @pytest.mark.asyncio
    async def test_evaluate_answer_basic(self, langchain_adapter, sample_question):
        """Test basic answer evaluation."""
        mock_response = {
            "score": 85.5,
            "feedback": "Good understanding of recursion",
            "strengths": ["Clear explanation", "Good examples"],
            "weaknesses": ["Missing base case details"],
            "missing_concepts": ["stack overflow handling"]
        }
        langchain_adapter._chains["evaluate_answer"].ainvoke.return_value = mock_response

        context = {}
        result = await langchain_adapter.evaluate_answer(
            question=sample_question,
            answer_text="Recursion is when a function calls itself",
            context=context
        )

        assert isinstance(result, AnswerEvaluation)
        assert result.score == 85.5
        assert result.reasoning == "Good understanding of recursion"
        assert len(result.strengths) == 2
        assert len(result.weaknesses) == 1
        # missing_concepts mapped to improvement_suggestions
        assert len(result.improvement_suggestions) == 1

    @pytest.mark.asyncio
    async def test_evaluate_answer_without_followup(self, langchain_adapter, sample_question):
        """Test answer evaluation without follow-up context."""
        mock_response = {
            "score": 70.0,
            "feedback": "Good answer with room for improvement",
            "strengths": ["Clear explanation"],
            "weaknesses": ["Could be more detailed"],
            "missing_concepts": []
        }
        langchain_adapter._chains["evaluate_answer"].ainvoke.return_value = mock_response

        result = await langchain_adapter.evaluate_answer(
            question=sample_question,
            answer_text="A function that calls itself with a stop condition",
            context={},
            followup_context=None
        )

        assert result.score == 70.0
        assert result.reasoning == "Good answer with room for improvement"
        # Verify no follow-up context in call
        call_args = langchain_adapter._chains["evaluate_answer"].ainvoke.call_args[0][0]
        assert call_args["followup_context"] == ""


class TestGenerateFeedbackReport:
    """Test generate_feedback_report method."""

    @pytest.fixture
    def sample_questions(self):
        """Create sample questions list."""
        return [
            Question(
                text="What is REST?",
                question_type=QuestionType.TECHNICAL,
                difficulty=DifficultyLevel.EASY,
                skills=["API Design"],
            ),
            Question(
                text="Explain microservices",
                question_type=QuestionType.TECHNICAL,
                difficulty=DifficultyLevel.HARD,
                skills=["Architecture"],
            ),
        ]

    @pytest.fixture
    def sample_answers(self):
        """Create sample answers list."""
        return [
            {"answer_text": "REST is an API design pattern", "score": 80.0, "feedback": "Good"},
            {"answer_text": "Microservices are distributed systems", "score": 70.0, "feedback": "Needs detail"},
        ]

    @pytest.mark.asyncio
    async def test_generate_feedback_report(self, langchain_adapter, sample_questions, sample_answers):
        """Test feedback report generation."""
        mock_response = {
            "report_text": "Overall performance: Good. Strengths: API knowledge. Weaknesses: Architecture depth.",
            "overall_score": 75.0
        }
        langchain_adapter._chains["generate_feedback_report"].ainvoke.return_value = mock_response

        interview_id = uuid4()
        result = await langchain_adapter.generate_feedback_report(
            interview_id=interview_id,
            questions=sample_questions,
            answers=sample_answers
        )

        assert isinstance(result, str)
        assert "Overall performance: Good" in result


class TestSummarizeCV:
    """Test summarize_cv method."""

    @pytest.mark.asyncio
    async def test_summarize_cv(self, langchain_adapter):
        """Test CV summarization."""
        mock_response = {
            "summary_text": "Experienced Python developer with 5 years in backend development",
            "years_experience": 5
        }
        langchain_adapter._chains["summarize_cv"].ainvoke.return_value = mock_response

        cv_text = "John Doe - Python Developer with extensive FastAPI experience..."
        result = await langchain_adapter.summarize_cv(cv_text=cv_text)

        assert isinstance(result, str)
        assert result == "Experienced Python developer with 5 years in backend development"


class TestExtractSkills:
    """Test extract_skills_from_text method."""

    @pytest.mark.asyncio
    async def test_extract_skills_basic(self, langchain_adapter):
        """Test skill extraction."""
        mock_response = {
            "skills": [
                {"name": "Python", "category": "programming", "proficiency": "expert"},
                {"name": "FastAPI", "category": "framework", "proficiency": "intermediate"},
                {"name": "PostgreSQL", "category": "database", "proficiency": "intermediate"}
            ]
        }
        langchain_adapter._chains["extract_skills_from_text"].ainvoke.return_value = mock_response

        text = "Proficient in Python, FastAPI, and PostgreSQL"
        result = await langchain_adapter.extract_skills_from_text(text=text)

        assert isinstance(result, list)
        assert len(result) == 3
        # Check structure mapping
        assert result[0]["skill"] == "Python"
        assert result[0]["category"] == "programming"
        assert result[0]["proficiency"] == "expert"

    @pytest.mark.asyncio
    async def test_extract_skills_empty(self, langchain_adapter):
        """Test skill extraction with no skills found."""
        mock_response = {"skills": []}
        langchain_adapter._chains["extract_skills_from_text"].ainvoke.return_value = mock_response

        text = "Generic work experience"
        result = await langchain_adapter.extract_skills_from_text(text=text)

        assert result == []


class TestGenerateIdealAnswer:
    """Test generate_ideal_answer method."""

    @pytest.mark.asyncio
    async def test_generate_ideal_answer(self, langchain_adapter):
        """Test ideal answer generation."""
        mock_response = {
            "answer_text": "Recursion is a technique where a function calls itself. Key elements: base case, recursive case, call stack management."
        }
        langchain_adapter._chains["generate_ideal_answer"].ainvoke.return_value = mock_response

        context = {"cv_summary": "Python developer", "skill_level": "intermediate"}
        result = await langchain_adapter.generate_ideal_answer(
            question_text="What is recursion?",
            context=context
        )

        assert isinstance(result, str)
        assert "base case" in result.lower()
        assert "recursive case" in result.lower()

    @pytest.mark.asyncio
    async def test_generate_ideal_answer_with_db_prompt_uses_chain(self, mock_chat_model):
        prompt_repo = MagicMock()
        prompt_repo.get_active_prompt = AsyncMock(return_value=PromptTemplate(
            name="ideal_answer_generation",
            version=2,
            template_json={
                "system": "system",
                "user_template": "{question_text} :: {summary} :: {skills} :: {experience}",
                "variables": ["question_text", "summary", "skills", "experience"],
            },
            is_active=True,
            is_draft=False,
        ))

        adapter = LangChainAdapter(model=mock_chat_model, prompt_repository=prompt_repo)
        adapter._log_execution = AsyncMock()
        mock_chain = MagicMock()
        mock_chain.ainvoke = AsyncMock(return_value={"answer_text": "Ideal answer"})
        adapter._get_or_build_chain = MagicMock(return_value=mock_chain)

        context = {
            "summary": "Seasoned dev",
            "skills": ["python", "fastapi"],
            "experience": "10",
            "cv_summary": "Seasoned dev resume",
            "skill_level": "advanced",
        }

        result = await adapter.generate_ideal_answer(
            question_text="Explain recursion",
            context=context,
        )

        assert result == "Ideal answer"
        adapter._get_or_build_chain.assert_called_once()
        mock_chain.ainvoke.assert_awaited_once()
        variables = mock_chain.ainvoke.call_args[0][0]
        assert variables["summary"] == "Seasoned dev"
        assert "python" in variables["skills"]
        adapter._log_execution.assert_awaited()

    @pytest.mark.asyncio
    async def test_generate_ideal_answer_logs_failure_on_exception(self, mock_chat_model):
        prompt_repo = MagicMock()
        prompt_repo.get_active_prompt = AsyncMock(return_value=PromptTemplate(
            name="ideal_answer_generation",
            version=3,
            template_json={
                "system": "system",
                "user_template": "{question_text}",
                "variables": ["question_text"],
            },
            is_active=True,
            is_draft=False,
        ))

        adapter = LangChainAdapter(model=mock_chat_model, prompt_repository=prompt_repo)
        adapter._log_execution = AsyncMock()
        failing_chain = MagicMock()
        failing_chain.ainvoke = AsyncMock(side_effect=RuntimeError("chain failure"))
        adapter._get_or_build_chain = MagicMock(return_value=failing_chain)

        context = {}

        with pytest.raises(RuntimeError):
            await adapter.generate_ideal_answer("Explain recursion", context)

        adapter._log_execution.assert_awaited_once()


class TestGenerateRationale:
    """Test generate_rationale method."""

    @pytest.mark.asyncio
    async def test_generate_rationale(self, langchain_adapter):
        """Test rationale generation."""
        mock_response = {
            "rationale_text": "This answer is ideal because it covers all key concepts systematically and provides concrete examples."
        }
        langchain_adapter._chains["generate_rationale"].ainvoke.return_value = mock_response

        result = await langchain_adapter.generate_rationale(
            question_text="What is recursion?",
            ideal_answer="Recursion is a technique..."
        )

        assert isinstance(result, str)
        assert "ideal" in result.lower()
        assert "key concepts" in result.lower()


class TestDetectConceptGaps:
    """Test detect_concept_gaps method."""

    @pytest.mark.asyncio
    async def test_detect_concept_gaps(self, langchain_adapter):
        """Test concept gap detection."""
        mock_response = {
            "concepts": ["base case", "call stack"],
            "keywords": ["base", "stack"],
            "confirmed": True,
            "severity": "moderate"
        }
        langchain_adapter._chains["detect_concept_gaps"].ainvoke.return_value = mock_response

        result = await langchain_adapter.detect_concept_gaps(
            answer_text="Recursion is a function calling itself",
            ideal_answer="Recursion requires base case, recursive case, and stack management",
            question_text="What is recursion?",
            keyword_gaps=["base", "stack", "case"]
        )

        assert isinstance(result, dict)
        assert result["concepts"] == ["base case", "call stack"]
        assert result["confirmed"] is True
        assert result["severity"] == "moderate"


class TestGenerateFollowupQuestion:
    """Test generate_followup_question method."""

    @pytest.mark.asyncio
    async def test_generate_followup_basic(self, langchain_adapter):
        """Test basic follow-up question generation."""
        mock_response = {
            "question_text": "Can you explain what a base case is in recursion?",
            "focus": "base case"
        }
        langchain_adapter._chains["generate_followup_question"].ainvoke.return_value = mock_response

        result = await langchain_adapter.generate_followup_question(
            parent_question="What is recursion?",
            answer_text="A function calling itself",
            missing_concepts=["base case", "call stack"],
            severity="major",
            order=1
        )

        assert isinstance(result, str)
        assert "base case" in result.lower()


class TestGenerateRecommendations:
    """Test generate_interview_recommendations method."""

    @pytest.mark.asyncio
    async def test_generate_recommendations(self, langchain_adapter):
        """Test interview recommendations generation."""
        mock_response = {
            "strengths": ["Good problem-solving", "Clear communication"],
            "weaknesses": ["Lacks depth in algorithms", "Limited system design knowledge"],
            "study_topics": ["Advanced algorithms", "System design patterns"],
            "technique_tips": ["Slow down when answering", "Ask clarifying questions"]
        }
        langchain_adapter._chains["generate_interview_recommendations"].ainvoke.return_value = mock_response

        context = {
            "interview_id": str(uuid4()),
            "total_answers": 5,
            "gap_progression": {"attempt_1": 3, "attempt_2": 1},
            "evaluations": [{"score": 75.0}, {"score": 80.0}]
        }

        result = await langchain_adapter.generate_interview_recommendations(context=context)

        assert isinstance(result, dict)
        assert "strengths" in result
        assert "weaknesses" in result
        assert "study_topics" in result
        assert "technique_tips" in result
        assert len(result["strengths"]) == 2
        assert len(result["study_topics"]) == 2


class TestBatchOperations:
    """Test batch generation methods."""

    @pytest.mark.asyncio
    async def test_generate_questions_batch(self, langchain_adapter):
        """Test parallel question generation."""
        # Mock RunnableParallel execution
        mock_results = {
            "q_0": {"question_text": "What is REST?"},
            "q_1": {"question_text": "Explain microservices?"},
            "q_2": {"question_text": "What is GraphQL?"}
        }

        with patch("src.infrastructure.adapters.llm.langchain_adapter.RunnableParallel") as mock_parallel:
            mock_parallel_instance = MagicMock()
            mock_parallel_instance.ainvoke = AsyncMock(return_value=mock_results)
            mock_parallel.return_value = mock_parallel_instance

            question_specs = [
                {"skill": "API Design", "difficulty": "easy"},
                {"skill": "Architecture", "difficulty": "hard"},
                {"skill": "API Design", "difficulty": "medium"}
            ]
            context = {"cv_summary": "Backend developer"}

            result = await langchain_adapter.generate_questions_batch(
                question_specs=question_specs,
                context=context
            )

            assert len(result) == 3
            assert result[0] == "What is REST?"
            assert result[1] == "Explain microservices?"
            assert result[2] == "What is GraphQL?"

    @pytest.mark.asyncio
    async def test_generate_ideal_answers_batch(self, langchain_adapter):
        """Test parallel ideal answer generation."""
        mock_results = {
            "a_0": {"answer_text": "REST is an architectural style..."},
            "a_1": {"answer_text": "Microservices are independently deployable..."}
        }

        with patch("src.infrastructure.adapters.llm.langchain_adapter.RunnableParallel") as mock_parallel:
            mock_parallel_instance = MagicMock()
            mock_parallel_instance.ainvoke = AsyncMock(return_value=mock_results)
            mock_parallel.return_value = mock_parallel_instance

            question_texts = ["What is REST?", "Explain microservices"]
            context = {"cv_summary": "Developer", "skill_level": "intermediate"}

            result = await langchain_adapter.generate_ideal_answers_batch(
                question_texts=question_texts,
                context=context
            )

            assert len(result) == 2
            assert "REST is an architectural style" in result[0]
            assert "Microservices are independently" in result[1]

    @pytest.mark.asyncio
    async def test_generate_rationales_batch(self, langchain_adapter):
        """Test parallel rationale generation."""
        mock_results = {
            "r_0": {"rationale_text": "This answer covers key REST principles..."},
            "r_1": {"rationale_text": "This answer explains microservices benefits..."}
        }

        with patch("src.infrastructure.adapters.llm.langchain_adapter.RunnableParallel") as mock_parallel:
            mock_parallel_instance = MagicMock()
            mock_parallel_instance.ainvoke = AsyncMock(return_value=mock_results)
            mock_parallel.return_value = mock_parallel_instance

            question_ideal_pairs = [
                ("What is REST?", "REST is an API design pattern"),
                ("Explain microservices", "Microservices are distributed systems")
            ]

            result = await langchain_adapter.generate_rationales_batch(
                question_ideal_pairs=question_ideal_pairs
            )

            assert len(result) == 2
            assert "REST principles" in result[0]
            assert "microservices benefits" in result[1]

    @pytest.mark.asyncio
    async def test_generate_questions_with_answers_and_rationales_batch(self, langchain_adapter):
        """Test unified method that generates question, ideal_answer, and rationale together."""
        # Mock chain responses - each call returns a dict with all three components
        mock_result_0 = {
            "question_text": "What is REST?",
            "ideal_answer": "REST is an architectural style for designing web services...",
            "rationale": "This answer covers key REST principles and demonstrates understanding."
        }
        mock_result_1 = {
            "question_text": "Explain microservices?",
            "ideal_answer": "Microservices are independently deployable services...",
            "rationale": "This answer explains microservices benefits and architecture."
        }

        # Mock the chain's ainvoke to return different results for each call
        mock_chain = MagicMock()
        mock_chain.ainvoke = AsyncMock(side_effect=[mock_result_0, mock_result_1])
        langchain_adapter._chains["generate_questions_with_answers_and_rationales_batch"] = mock_chain

        question_specs = [
            {"skill": "API Design", "difficulty": "easy", "exemplars": []},
            {"skill": "Architecture", "difficulty": "hard", "exemplars": []}
        ]
        context = {"cv_summary": "Backend developer", "covered_topics": [], "stage": "planning"}

        result = await langchain_adapter.generate_questions_with_answers_and_rationales_batch(
            question_specs=question_specs,
            context=context
        )

        assert len(result) == 2
        assert isinstance(result[0], tuple)
        assert len(result[0]) == 3
        assert result[0][0] == "What is REST?"
        assert "REST is an architectural style" in result[0][1]
        assert "key REST principles" in result[0][2]
        assert result[1][0] == "Explain microservices?"
        assert "Microservices are independently" in result[1][1]
        assert "microservices benefits" in result[1][2]


class TestHelperMethods:
    """Test internal helper methods."""

    def test_format_previous_evaluations(self, langchain_adapter):
        """Test formatting of previous evaluations."""
        eval1 = AnswerEvaluation(
            score=60.0,
            semantic_similarity=0.5,
            completeness=0.4,
            relevance=0.8,
            reasoning="Needs improvement",
            improvement_suggestions=["base case", "recursive case", "stack"]
        )
        eval2 = AnswerEvaluation(
            score=70.0,
            semantic_similarity=0.6,
            completeness=0.6,
            relevance=0.9,
            reasoning="Better",
            improvement_suggestions=["stack management"]
        )

        result = langchain_adapter._format_previous_evaluations([eval1, eval2])

        assert "Attempt 1: Score 60.0/100" in result
        assert "Attempt 2: Score 70.0/100" in result

    def test_format_previous_evaluations_empty(self, langchain_adapter):
        """Test formatting with no previous evaluations."""
        result = langchain_adapter._format_previous_evaluations([])
        assert result == "None"

    def test_format_questions_answers(self, langchain_adapter):
        """Test formatting of questions and answers for report."""
        questions = [
            Question(
                text="What is REST?",
                question_type=QuestionType.TECHNICAL,
                difficulty=DifficultyLevel.EASY,
                skills=["API"],
            )
        ]
        answers = [
            {"answer_text": "REST is an API design pattern for web services", "score": 85.0, "feedback": "Good answer"}
        ]

        result = langchain_adapter._format_questions_answers(questions, answers)

        assert "Question 1" in result
        assert "Q: What is REST?" in result
        assert "Skill: API" in result
        assert "Difficulty: easy" in result
        assert "Score: 85.0/100" in result
        assert "A: REST is an API design pattern" in result
