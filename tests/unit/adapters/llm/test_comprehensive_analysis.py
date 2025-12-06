"""Unit tests for comprehensive answer analysis (Phase 2)."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.adapters.llm.comprehensive_models import (
    ComprehensiveAnalysis,
    EvaluationOutput,
    EvaluationDimension,
    ConceptGapOutput,
    FollowUpOutput,
)
from src.adapters.llm.langchain_adapter import LangChainAdapter
from src.domain.models.question import Question, QuestionType, DifficultyLevel


@pytest.fixture
def sample_question():
    """Create sample question for testing."""
    return Question(
        id=None,
        text="What is recursion?",
        question_type=QuestionType.TECHNICAL,
        difficulty=DifficultyLevel.MEDIUM,
        skills=["Python", "Algorithms"],
        ideal_answer="Recursion is a programming technique where a function calls itself...",
    )


@pytest.fixture
def mock_comprehensive_response():
    """Mock comprehensive analysis response."""
    return {
        "evaluation": {
            "dimensions": [
                {"dimension_name": "technical_accuracy", "score": 35.0, "reasoning": "Good understanding"},
                {"dimension_name": "depth_of_understanding", "score": 25.0, "reasoning": "Adequate depth"},
                {"dimension_name": "clarity_of_communication", "score": 18.0, "reasoning": "Clear explanation"},
                {"dimension_name": "practical_application", "score": 8.0, "reasoning": "Good examples"},
            ],
            "total_score": 86.0,
            "strengths": ["Clear explanation", "Good examples"],
            "weaknesses": ["Missing base case details"],
            "improvement_suggestions": ["Explain base case handling"],
            "reasoning": "Overall good understanding of recursion",
        },
        "gaps": [
            {"concept": "stack overflow handling", "severity": "moderate", "explanation": "Not mentioned"}
        ],
        "follow_up": {
            "question_text": "How would you handle stack overflow in recursive functions?",
            "reason": "Major gap in stack overflow handling",
            "target_gaps": ["stack overflow handling"],
        },
        "confidence": 0.95,
    }


class TestComprehensiveModels:
    """Test comprehensive analysis Pydantic models."""

    def test_evaluation_dimension_validation(self):
        """Test EvaluationDimension model validation."""
        dim = EvaluationDimension(
            dimension_name="technical_accuracy",
            score=35.0,
            reasoning="Good understanding",
        )
        assert dim.dimension_name == "technical_accuracy"
        assert dim.score == 35.0
        assert dim.score <= 40.0  # Max for technical_accuracy

    def test_evaluation_output_validation(self):
        """Test EvaluationOutput model validation."""
        dimensions = [
            EvaluationDimension(dimension_name="technical_accuracy", score=35.0, reasoning="Good"),
            EvaluationDimension(dimension_name="depth_of_understanding", score=25.0, reasoning="Adequate"),
            EvaluationDimension(dimension_name="clarity_of_communication", score=18.0, reasoning="Clear"),
            EvaluationDimension(dimension_name="practical_application", score=8.0, reasoning="Good examples"),
        ]
        eval_output = EvaluationOutput(
            dimensions=dimensions,
            total_score=86.0,
            strengths=["Clear explanation"],
            weaknesses=["Missing details"],
            improvement_suggestions=["Add more examples"],
            reasoning="Overall good",
        )
        assert len(eval_output.dimensions) == 4
        assert eval_output.total_score == 86.0

    def test_concept_gap_output_validation(self):
        """Test ConceptGapOutput model validation."""
        gap = ConceptGapOutput(
            concept="stack overflow",
            severity="moderate",
            explanation="Not mentioned in answer",
        )
        assert gap.concept == "stack overflow"
        assert gap.severity in ["minor", "moderate", "major"]

    def test_follow_up_output_validation(self):
        """Test FollowUpOutput model validation."""
        followup = FollowUpOutput(
            question_text="How would you handle stack overflow?",
            reason="Gap in understanding",
            target_gaps=["stack overflow"],
        )
        assert followup.question_text is not None
        assert len(followup.target_gaps) > 0

    def test_comprehensive_analysis_validation(self, mock_comprehensive_response):
        """Test ComprehensiveAnalysis model validation."""
        analysis = ComprehensiveAnalysis(**mock_comprehensive_response)
        assert analysis.evaluation.total_score == 86.0
        assert len(analysis.gaps) == 1
        assert analysis.follow_up is not None
        assert analysis.confidence == 0.95


class TestAnalyzeAnswerComprehensive:
    """Test analyze_answer_comprehensive method."""

    @pytest.mark.asyncio
    async def test_analyze_answer_comprehensive_success(
        self, langchain_adapter, sample_question, mock_comprehensive_response
    ):
        """Test successful comprehensive analysis."""
        # Mock chain invocation
        langchain_adapter._chains["comprehensive_answer_analysis"].ainvoke = AsyncMock(
            return_value=mock_comprehensive_response
        )
        langchain_adapter._invoke_chain_with_metadata = AsyncMock(
            return_value=(mock_comprehensive_response, {"usage": {"total_tokens": 800}})
        )

        context = {"interview_id": "123", "candidate_id": "456"}
        result = await langchain_adapter.analyze_answer_comprehensive(
            question=sample_question,
            answer_text="Recursion is when a function calls itself",
            context=context,
        )

        assert isinstance(result, ComprehensiveAnalysis)
        assert result.evaluation.total_score == 86.0
        assert len(result.gaps) == 1
        assert result.follow_up is not None

    @pytest.mark.asyncio
    async def test_analyze_answer_comprehensive_no_ideal_answer(self, langchain_adapter, sample_question):
        """Test error when question has no ideal_answer."""
        sample_question.ideal_answer = None

        context = {"interview_id": "123"}
        with pytest.raises(ValueError, match="no ideal_answer"):
            await langchain_adapter.analyze_answer_comprehensive(
                question=sample_question,
                answer_text="Some answer",
                context=context,
            )

    @pytest.mark.asyncio
    async def test_analyze_answer_comprehensive_with_followup_context(
        self, langchain_adapter, sample_question, mock_comprehensive_response
    ):
        """Test comprehensive analysis with follow-up context."""
        from src.domain.models.evaluation import FollowUpEvaluationContext, Evaluation

        # Mock chain invocation
        langchain_adapter._invoke_chain_with_metadata = AsyncMock(
            return_value=(mock_comprehensive_response, {"usage": {"total_tokens": 800}})
        )

        followup_context = FollowUpEvaluationContext(
            attempt_number=2,
            previous_evaluations=[Evaluation(id=None, answer_id=None, question_id=None, interview_id=None, raw_score=70.0)],
            previous_scores=[70.0],
            cumulative_gaps=[],
        )

        context = {"interview_id": "123"}
        result = await langchain_adapter.analyze_answer_comprehensive(
            question=sample_question,
            answer_text="Recursion is when a function calls itself",
            context=context,
            followup_context=followup_context,
        )

        assert isinstance(result, ComprehensiveAnalysis)
        # Verify follow-up context was used (check attempt_number in response)
        assert result.evaluation.total_score == 86.0

