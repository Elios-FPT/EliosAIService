"""Tests for Evaluation repository mappers with voice metrics fields."""

from datetime import datetime
from typing import AsyncGenerator
from uuid import uuid4

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.adapters.persistence.evaluation_repository import PostgreSQLEvaluationRepository
from src.adapters.persistence.models import EvaluationModel
from src.adapters.persistence.session_provider import SessionProvider
from src.domain.models.evaluation import Evaluation


class TestEvaluationRepositoryMappers:
    """Test mapper functions handle theoretical_score and speaking_score."""

    @pytest.fixture
    def mock_session_provider(self) -> SessionProvider:
        """Create mock session provider."""
        mock_session = AsyncMock()
        mock_provider = MagicMock()
        mock_provider.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_provider.return_value.__aexit__ = AsyncMock(return_value=None)
        return mock_provider

    def test_to_domain_with_voice_metrics(self, mock_session_provider):
        """Test _to_domain maps new fields correctly."""
        repo = PostgreSQLEvaluationRepository(mock_session_provider)

        # Create mock database model with new fields
        db_model = EvaluationModel(
            id=uuid4(),
            answer_id=uuid4(),
            raw_score=80.0,
            penalty=0.0,
            theoretical_score=85.0,
            speaking_score=75.0,
            final_score=82.0,
            similarity_score=0.8,
            completeness=0.9,
            relevance=0.8,
            sentiment="confident",
            reasoning="Good answer",
            strengths=["Clear explanation"],
            weaknesses=[],
            improvement_suggestions=[],
            attempt_number=1,
            parent_evaluation_id=None,
            gaps=[],
            created_at=datetime.utcnow(),
            evaluated_at=datetime.utcnow(),
        )

        domain_model = repo._to_domain(db_model)

        assert domain_model.theoretical_score == 85.0
        assert domain_model.speaking_score == 75.0
        assert domain_model.final_score == 82.0

    def test_to_domain_without_voice_metrics(self, mock_session_provider):
        """Test _to_domain handles None values for text-only answers."""
        repo = PostgreSQLEvaluationRepository(mock_session_provider)

        db_model = EvaluationModel(
            id=uuid4(),
            answer_id=uuid4(),
            raw_score=80.0,
            penalty=0.0,
            theoretical_score=None,
            speaking_score=None,
            final_score=80.0,
            similarity_score=0.8,
            completeness=0.9,
            relevance=0.8,
            sentiment=None,
            reasoning="Good answer",
            strengths=[],
            weaknesses=[],
            improvement_suggestions=[],
            attempt_number=1,
            parent_evaluation_id=None,
            gaps=[],
            created_at=datetime.utcnow(),
            evaluated_at=datetime.utcnow(),
        )

        domain_model = repo._to_domain(db_model)

        assert domain_model.theoretical_score is None
        assert domain_model.speaking_score is None
        assert domain_model.final_score == 80.0

    def test_to_db_model_with_voice_metrics(self, mock_session_provider):
        """Test _to_db_model maps new fields correctly."""
        repo = PostgreSQLEvaluationRepository(mock_session_provider)

        domain_model = Evaluation(
            id=uuid4(),
            answer_id=uuid4(),
            raw_score=80.0,
            penalty=0.0,
            theoretical_score=85.0,
            speaking_score=75.0,
            final_score=82.0,
            similarity_score=0.8,
            completeness=0.9,
            relevance=0.8,
            sentiment="confident",
            reasoning="Good answer",
            strengths=["Clear explanation"],
            weaknesses=[],
            improvement_suggestions=[],
            attempt_number=1,
            parent_evaluation_id=None,
            gaps=[],
            created_at=datetime.utcnow(),
            evaluated_at=datetime.utcnow(),
        )

        db_model = repo._to_db_model(domain_model)

        assert db_model.theoretical_score == 85.0
        assert db_model.speaking_score == 75.0
        assert db_model.final_score == 82.0

    def test_to_db_model_without_voice_metrics(self, mock_session_provider):
        """Test _to_db_model handles None values."""
        repo = PostgreSQLEvaluationRepository(mock_session_provider)

        domain_model = Evaluation(
            id=uuid4(),
            answer_id=uuid4(),
            raw_score=80.0,
            penalty=0.0,
            theoretical_score=None,
            speaking_score=None,
            final_score=80.0,
            similarity_score=0.8,
            completeness=0.9,
            relevance=0.8,
            sentiment=None,
            reasoning="Good answer",
            strengths=[],
            weaknesses=[],
            improvement_suggestions=[],
            attempt_number=1,
            parent_evaluation_id=None,
            gaps=[],
            created_at=datetime.utcnow(),
            evaluated_at=datetime.utcnow(),
        )

        db_model = repo._to_db_model(domain_model)

        assert db_model.theoretical_score is None
        assert db_model.speaking_score is None
        assert db_model.final_score == 80.0

    def test_round_trip_mapping(self, mock_session_provider):
        """Test round-trip: domain -> db -> domain preserves new fields."""
        repo = PostgreSQLEvaluationRepository(mock_session_provider)

        original = Evaluation(
            id=uuid4(),
            answer_id=uuid4(),
            raw_score=80.0,
            penalty=0.0,
            theoretical_score=85.0,
            speaking_score=75.0,
            final_score=82.0,
            similarity_score=0.8,
            completeness=0.9,
            relevance=0.8,
            sentiment="confident",
            reasoning="Good answer",
            strengths=["Clear"],
            weaknesses=[],
            improvement_suggestions=[],
            attempt_number=1,
            parent_evaluation_id=None,
            gaps=[],
            created_at=datetime.utcnow(),
            evaluated_at=datetime.utcnow(),
        )

        db_model = repo._to_db_model(original)
        restored = repo._to_domain(db_model)

        assert restored.theoretical_score == original.theoretical_score
        assert restored.speaking_score == original.speaking_score
        assert restored.final_score == original.final_score

    def test_to_domain_with_voice_metrics_jsonb(self, mock_session_provider):
        """Test _to_domain maps voice_metrics JSONB correctly."""
        repo = PostgreSQLEvaluationRepository(mock_session_provider)

        voice_metrics = {
            "intonation_score": 0.85,
            "fluency_score": 0.92,
            "confidence_score": 0.88,
            "speaking_rate_wpm": 145,
        }

        db_model = EvaluationModel(
            id=uuid4(),
            answer_id=uuid4(),
            raw_score=80.0,
            penalty=0.0,
            theoretical_score=85.0,
            speaking_score=75.0,
            final_score=82.0,
            similarity_score=0.8,
            completeness=0.9,
            relevance=0.8,
            sentiment="confident",
            voice_metrics=voice_metrics,
            reasoning="Good answer",
            strengths=[],
            weaknesses=[],
            improvement_suggestions=[],
            attempt_number=1,
            parent_evaluation_id=None,
            gaps=[],
            created_at=datetime.utcnow(),
            evaluated_at=datetime.utcnow(),
        )

        domain_model = repo._to_domain(db_model)

        assert domain_model.voice_metrics is not None
        assert domain_model.voice_metrics["intonation_score"] == 0.85
        assert domain_model.voice_metrics["fluency_score"] == 0.92
        assert domain_model.voice_metrics["confidence_score"] == 0.88
        assert domain_model.voice_metrics["speaking_rate_wpm"] == 145

    def test_to_domain_without_voice_metrics_jsonb(self, mock_session_provider):
        """Test _to_domain handles None voice_metrics (text answer)."""
        repo = PostgreSQLEvaluationRepository(mock_session_provider)

        db_model = EvaluationModel(
            id=uuid4(),
            answer_id=uuid4(),
            raw_score=80.0,
            penalty=0.0,
            theoretical_score=80.0,
            speaking_score=None,
            final_score=80.0,
            similarity_score=0.8,
            completeness=0.9,
            relevance=0.8,
            sentiment=None,
            voice_metrics=None,  # Text-only answer
            reasoning="Good answer",
            strengths=[],
            weaknesses=[],
            improvement_suggestions=[],
            attempt_number=1,
            parent_evaluation_id=None,
            gaps=[],
            created_at=datetime.utcnow(),
            evaluated_at=datetime.utcnow(),
        )

        domain_model = repo._to_domain(db_model)

        assert domain_model.voice_metrics is None

    def test_to_db_model_with_voice_metrics_jsonb(self, mock_session_provider):
        """Test _to_db_model maps voice_metrics dict to JSONB correctly."""
        repo = PostgreSQLEvaluationRepository(mock_session_provider)

        voice_metrics = {
            "intonation_score": 0.85,
            "fluency_score": 0.92,
            "confidence_score": 0.88,
            "speaking_rate_wpm": 145,
        }

        domain_model = Evaluation(
            id=uuid4(),
            answer_id=uuid4(),
            raw_score=80.0,
            penalty=0.0,
            theoretical_score=85.0,
            speaking_score=75.0,
            final_score=82.0,
            similarity_score=0.8,
            completeness=0.9,
            relevance=0.8,
            sentiment="confident",
            voice_metrics=voice_metrics,
            reasoning="Good answer",
            strengths=[],
            weaknesses=[],
            improvement_suggestions=[],
            attempt_number=1,
            parent_evaluation_id=None,
            gaps=[],
            created_at=datetime.utcnow(),
            evaluated_at=datetime.utcnow(),
        )

        db_model = repo._to_db_model(domain_model)

        assert db_model.voice_metrics is not None
        assert db_model.voice_metrics["intonation_score"] == 0.85
        assert db_model.voice_metrics["fluency_score"] == 0.92
        assert db_model.voice_metrics["confidence_score"] == 0.88
        assert db_model.voice_metrics["speaking_rate_wpm"] == 145

    def test_to_db_model_without_voice_metrics_jsonb(self, mock_session_provider):
        """Test _to_db_model handles None voice_metrics."""
        repo = PostgreSQLEvaluationRepository(mock_session_provider)

        domain_model = Evaluation(
            id=uuid4(),
            answer_id=uuid4(),
            raw_score=80.0,
            penalty=0.0,
            theoretical_score=80.0,
            speaking_score=None,
            final_score=80.0,
            similarity_score=0.8,
            completeness=0.9,
            relevance=0.8,
            sentiment=None,
            voice_metrics=None,  # Text-only answer
            reasoning="Good answer",
            strengths=[],
            weaknesses=[],
            improvement_suggestions=[],
            attempt_number=1,
            parent_evaluation_id=None,
            gaps=[],
            created_at=datetime.utcnow(),
            evaluated_at=datetime.utcnow(),
        )

        db_model = repo._to_db_model(domain_model)

        assert db_model.voice_metrics is None

    def test_round_trip_voice_metrics_jsonb(self, mock_session_provider):
        """Test round-trip: domain -> db -> domain preserves voice_metrics JSONB."""
        repo = PostgreSQLEvaluationRepository(mock_session_provider)

        voice_metrics = {
            "intonation_score": 0.85,
            "fluency_score": 0.92,
            "confidence_score": 0.88,
            "speaking_rate_wpm": 145,
        }

        original = Evaluation(
            id=uuid4(),
            answer_id=uuid4(),
            raw_score=80.0,
            penalty=0.0,
            theoretical_score=85.0,
            speaking_score=75.0,
            final_score=82.0,
            similarity_score=0.8,
            completeness=0.9,
            relevance=0.8,
            sentiment="confident",
            voice_metrics=voice_metrics,
            reasoning="Good answer",
            strengths=[],
            weaknesses=[],
            improvement_suggestions=[],
            attempt_number=1,
            parent_evaluation_id=None,
            gaps=[],
            created_at=datetime.utcnow(),
            evaluated_at=datetime.utcnow(),
        )

        db_model = repo._to_db_model(original)
        restored = repo._to_domain(db_model)

        assert restored.voice_metrics is not None
        assert restored.voice_metrics == original.voice_metrics
        assert restored.voice_metrics["intonation_score"] == 0.85
        assert restored.voice_metrics["speaking_rate_wpm"] == 145

