"""Tests for Evaluation domain model with voice metrics support."""

from datetime import datetime
from uuid import uuid4

import pytest

from src.domain.models.evaluation import Evaluation, ConceptGap, GapSeverity


class TestEvaluationVoiceMetricsFields:
    """Test Evaluation model with theoretical_score and speaking_score fields."""

    def test_evaluation_with_voice_metrics(self):
        """Test evaluation with both theoretical and speaking scores."""
        evaluation = Evaluation(
            answer_id=uuid4(),
            raw_score=80.0,
            theoretical_score=85.0,
            speaking_score=75.0,
            final_score=82.0,  # (85 * 0.7) + (75 * 0.3) = 82.0
            completeness=0.9,
            relevance=0.8,
        )

        assert evaluation.theoretical_score == 85.0
        assert evaluation.speaking_score == 75.0
        assert evaluation.final_score == 82.0

    def test_evaluation_text_only_no_speaking_score(self):
        """Test evaluation for text-only answer (no speaking score)."""
        evaluation = Evaluation(
            answer_id=uuid4(),
            raw_score=80.0,
            theoretical_score=80.0,
            speaking_score=None,  # Text-only answer
            final_score=80.0,
            completeness=0.9,
            relevance=0.8,
        )

        assert evaluation.theoretical_score == 80.0
        assert evaluation.speaking_score is None
        assert evaluation.final_score == 80.0

    def test_evaluation_fields_optional(self):
        """Test that theoretical_score and speaking_score are optional."""
        evaluation = Evaluation(
            answer_id=uuid4(),
            raw_score=70.0,
            theoretical_score=None,
            speaking_score=None,
            final_score=70.0,
            completeness=0.7,
            relevance=0.7,
        )

        assert evaluation.theoretical_score is None
        assert evaluation.speaking_score is None
        # Should still work with None values
        assert evaluation.final_score == 70.0

    def test_evaluation_score_bounds_validation(self):
        """Test that score fields respect bounds (0-100)."""
        # Valid scores
        evaluation = Evaluation(
            answer_id=uuid4(),
            raw_score=50.0,
            theoretical_score=75.0,
            speaking_score=60.0,
            final_score=70.5,
            completeness=0.5,
            relevance=0.5,
        )
        assert evaluation.theoretical_score == 75.0
        assert evaluation.speaking_score == 60.0

        # Test bounds validation
        with pytest.raises(Exception):  # Pydantic validation error
            Evaluation(
                answer_id=uuid4(),
                raw_score=50.0,
                theoretical_score=150.0,  # > 100
                speaking_score=60.0,
                final_score=70.0,
                completeness=0.5,
                relevance=0.5,
            )

        with pytest.raises(Exception):  # Pydantic validation error
            Evaluation(
                answer_id=uuid4(),
                raw_score=50.0,
                theoretical_score=75.0,
                speaking_score=-10.0,  # < 0
                final_score=70.0,
                completeness=0.5,
                relevance=0.5,
            )

    def test_evaluation_penalty_with_combined_scores(self):
        """Test penalty application with combined scores."""
        evaluation = Evaluation(
            answer_id=uuid4(),
            raw_score=80.0,
            theoretical_score=85.0,
            speaking_score=75.0,
            final_score=82.0,
            completeness=0.9,
            relevance=0.8,
        )

        # Apply penalty for attempt 2
        evaluation.apply_penalty(2)
        # Note: apply_penalty currently uses raw_score, but final_score should reflect combined
        assert evaluation.penalty == -5.0
        # The final_score calculation in apply_penalty uses raw_score, not combined
        # This is expected behavior for now (will be updated in Phase 02)

    def test_evaluation_with_voice_metrics_dict(self):
        """Test evaluation with voice_metrics dict field."""
        voice_metrics = {
            "intonation_score": 0.85,
            "fluency_score": 0.92,
            "confidence_score": 0.88,
            "speaking_rate_wpm": 145,
        }
        evaluation = Evaluation(
            answer_id=uuid4(),
            raw_score=80.0,
            theoretical_score=85.0,
            speaking_score=75.0,
            final_score=82.0,
            completeness=0.9,
            relevance=0.8,
            voice_metrics=voice_metrics,
        )

        assert evaluation.voice_metrics is not None
        assert evaluation.voice_metrics["intonation_score"] == 0.85
        assert evaluation.voice_metrics["fluency_score"] == 0.92
        assert evaluation.voice_metrics["confidence_score"] == 0.88
        assert evaluation.voice_metrics["speaking_rate_wpm"] == 145

    def test_evaluation_without_voice_metrics_none(self):
        """Test evaluation without voice_metrics (text answer)."""
        evaluation = Evaluation(
            answer_id=uuid4(),
            raw_score=80.0,
            theoretical_score=80.0,
            speaking_score=None,
            final_score=80.0,
            completeness=0.9,
            relevance=0.8,
            voice_metrics=None,  # Text-only answer
        )

        assert evaluation.voice_metrics is None

    def test_evaluation_voice_metrics_empty_dict(self):
        """Test evaluation with empty voice_metrics dict."""
        evaluation = Evaluation(
            answer_id=uuid4(),
            raw_score=80.0,
            theoretical_score=80.0,
            speaking_score=None,
            final_score=80.0,
            completeness=0.9,
            relevance=0.8,
            voice_metrics={},  # Empty dict
        )

        assert evaluation.voice_metrics == {}

    def test_evaluation_voice_metrics_invalid_type_rejected(self):
        """Test that Pydantic rejects invalid voice_metrics types."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            Evaluation(
                answer_id=uuid4(),
                raw_score=80.0,
                theoretical_score=80.0,
                speaking_score=None,
                final_score=80.0,
                completeness=0.9,
                relevance=0.8,
                voice_metrics="invalid_string",  # Should be dict or None
            )

    def test_evaluation_voice_metrics_partial_structure(self):
        """Test evaluation with partial voice_metrics structure."""
        evaluation = Evaluation(
            answer_id=uuid4(),
            raw_score=80.0,
            theoretical_score=80.0,
            speaking_score=None,
            final_score=80.0,
            completeness=0.9,
            relevance=0.8,
            voice_metrics={
                "intonation_score": 0.85,
                # Missing other fields - should still work
            },
        )

        assert evaluation.voice_metrics is not None
        assert evaluation.voice_metrics["intonation_score"] == 0.85

