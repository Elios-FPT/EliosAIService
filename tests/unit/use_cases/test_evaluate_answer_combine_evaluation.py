"""Tests for EvaluateAnswerUseCase combine evaluation methods."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.use_cases.interview.evaluate_answer import EvaluateAnswerUseCase
from src.domain.models.answer import AnswerEvaluation


class TestCombineEvaluations:
    """Test _combine_evaluations method."""

    @pytest.fixture
    def use_case(self) -> EvaluateAnswerUseCase:
        """Create EvaluateAnswerUseCase instance with mocked dependencies."""
        return EvaluateAnswerUseCase(
            interview_repo=AsyncMock(),
            question_repo=AsyncMock(),
            answer_repo=AsyncMock(),
            evaluation_repo=AsyncMock(),
            llm=AsyncMock(),
        )

    def test_combine_with_voice_metrics(self, use_case: EvaluateAnswerUseCase):
        """Test combining theoretical and speaking scores."""
        theoretical_eval = AnswerEvaluation(
            score=80.0,
            completeness=0.8,
            relevance=0.8,
            sentiment="confident",
            reasoning="Good answer",
            strengths=["Clear explanation"],
            weaknesses=[],
            improvement_suggestions=[],
            semantic_similarity=0.8,
        )

        voice_metrics = {
            "intonation_score": 0.8,
            "fluency_score": 0.7,
            "confidence_score": 0.9,
        }

        result = use_case._combine_evaluations(theoretical_eval, voice_metrics)

        assert result["theoretical_score"] == 80.0
        assert result["speaking_score"] == 80.0  # (0.8 + 0.7 + 0.9) / 3 * 100
        # overall = 80 * 0.7 + 80 * 0.3 = 80.0
        assert result["overall_score"] == 80.0

    def test_combine_text_only_no_voice_metrics(self, use_case: EvaluateAnswerUseCase):
        """Test text-only answer (no voice metrics)."""
        theoretical_eval = AnswerEvaluation(
            score=75.0,
            completeness=0.75,
            relevance=0.75,
            sentiment="neutral",
            reasoning="Adequate answer",
            strengths=[],
            weaknesses=["Could be more detailed"],
            improvement_suggestions=["Add examples"],
            semantic_similarity=0.75,
        )

        result = use_case._combine_evaluations(theoretical_eval, voice_metrics=None)

        assert result["theoretical_score"] == 75.0
        assert result["speaking_score"] is None
        # Text-only: overall = theoretical (100% weight)
        assert result["overall_score"] == 75.0

    def test_combine_different_scores(self, use_case: EvaluateAnswerUseCase):
        """Test combining different theoretical and speaking scores."""
        theoretical_eval = AnswerEvaluation(
            score=90.0,
            completeness=0.9,
            relevance=0.9,
            sentiment="confident",
            reasoning="Excellent answer",
            strengths=["Comprehensive"],
            weaknesses=[],
            improvement_suggestions=[],
            semantic_similarity=0.9,
        )

        voice_metrics = {
            "intonation_score": 0.6,
            "fluency_score": 0.5,
            "confidence_score": 0.7,
        }

        result = use_case._combine_evaluations(theoretical_eval, voice_metrics)

        assert result["theoretical_score"] == 90.0
        # speaking = (0.6 + 0.5 + 0.7) / 3 * 100 = 60.0
        assert result["speaking_score"] == 60.0
        # overall = 90 * 0.7 + 60 * 0.3 = 63 + 18 = 81.0
        assert result["overall_score"] == 81.0


class TestCalculateSpeakingScore:
    """Test _calculate_speaking_score method."""

    @pytest.fixture
    def use_case(self) -> EvaluateAnswerUseCase:
        """Create EvaluateAnswerUseCase instance with mocked dependencies."""
        return EvaluateAnswerUseCase(
            interview_repo=AsyncMock(),
            question_repo=AsyncMock(),
            answer_repo=AsyncMock(),
            evaluation_repo=AsyncMock(),
            llm=AsyncMock(),
        )

    def test_calculate_speaking_score_all_metrics(self, use_case: EvaluateAnswerUseCase):
        """Test calculation with all metrics present."""
        voice_metrics = {
            "intonation_score": 0.8,
            "fluency_score": 0.7,
            "confidence_score": 0.9,
        }

        score = use_case._calculate_speaking_score(voice_metrics)
        # (0.8 + 0.7 + 0.9) / 3 * 100 = 80.0
        assert score == 80.0

    def test_calculate_speaking_score_missing_metrics(self, use_case: EvaluateAnswerUseCase):
        """Test calculation with missing metrics (uses defaults)."""
        voice_metrics = {
            "intonation_score": 0.8,
            # fluency_score missing -> defaults to 0.5
            "confidence_score": 0.9,
        }

        score = use_case._calculate_speaking_score(voice_metrics)
        # (0.8 + 0.5 + 0.9) / 3 * 100 = 73.33...
        assert abs(score - 73.33) < 0.1

    def test_calculate_speaking_score_all_defaults(self, use_case: EvaluateAnswerUseCase):
        """Test calculation with all metrics missing (all defaults to 0.5)."""
        voice_metrics = {}

        score = use_case._calculate_speaking_score(voice_metrics)
        # (0.5 + 0.5 + 0.5) / 3 * 100 = 50.0
        assert score == 50.0

    def test_calculate_speaking_score_edge_values(self, use_case: EvaluateAnswerUseCase):
        """Test calculation with edge values (0.0 and 1.0)."""
        voice_metrics = {
            "intonation_score": 0.0,
            "fluency_score": 1.0,
            "confidence_score": 0.5,
        }

        score = use_case._calculate_speaking_score(voice_metrics)
        # (0.0 + 1.0 + 0.5) / 3 * 100 = 50.0
        assert score == 50.0


class TestVoiceMetricsStorage:
    """Test that voice_metrics pattern is correct for Evaluation entity."""

    def test_voice_metrics_passed_to_evaluation_constructor(self):
        """Test that voice_metrics can be passed to Evaluation constructor.
        
        This verifies the pattern used in EvaluateAnswerUseCase.execute()
        where input_dto.voice_metrics is passed to Evaluation constructor.
        """
        from src.domain.models.evaluation import Evaluation
        from uuid import uuid4

        voice_metrics = {
            "intonation_score": 0.85,
            "fluency_score": 0.92,
            "confidence_score": 0.88,
            "speaking_rate_wpm": 145,
        }

        # Simulate what EvaluateAnswerUseCase does:
        # evaluation = Evaluation(..., voice_metrics=input_dto.voice_metrics, ...)
        evaluation = Evaluation(
            answer_id=uuid4(),
            raw_score=80.0,
            theoretical_score=85.0,
            speaking_score=75.0,
            final_score=82.0,
            completeness=0.9,
            relevance=0.8,
            voice_metrics=voice_metrics,  # Pattern: input_dto.voice_metrics
        )

        # Verify voice_metrics stored correctly
        assert evaluation.voice_metrics == voice_metrics
        assert evaluation.voice_metrics["intonation_score"] == 0.85
        assert evaluation.voice_metrics["speaking_rate_wpm"] == 145

    def test_voice_metrics_none_for_text_answer(self):
        """Test that voice_metrics=None works for text-only answers."""
        from src.domain.models.evaluation import Evaluation
        from uuid import uuid4

        # Simulate text-only answer (no voice_metrics)
        evaluation = Evaluation(
            answer_id=uuid4(),
            raw_score=80.0,
            theoretical_score=80.0,
            speaking_score=None,
            final_score=80.0,
            completeness=0.9,
            relevance=0.8,
            voice_metrics=None,  # Text-only: no voice metrics
        )

        assert evaluation.voice_metrics is None

