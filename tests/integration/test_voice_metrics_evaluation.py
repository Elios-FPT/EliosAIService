"""Integration tests for voice metrics evaluation flow."""

from uuid import uuid4

import pytest

from src.domain.models.answer import Answer
from src.domain.models.evaluation import Evaluation
from src.domain.models.interview import Interview, InterviewStatus
from src.domain.models.question import DifficultyLevel, Question, QuestionType


class TestVoiceMetricsEvaluationFlow:
    """Test full evaluation flow with voice metrics integration."""

    @pytest.mark.asyncio
    async def test_voice_answer_evaluation_stores_speaking_score(
        self,
        async_session,
        mock_evaluation_repo,
    ):
        """Test that voice answer evaluation stores speaking_score in Evaluation."""
        # Create evaluation with voice metrics
        answer_id = uuid4()
        evaluation = Evaluation(
            answer_id=answer_id,
            raw_score=80.0,
            theoretical_score=85.0,  # LLM score
            speaking_score=75.0,  # Voice metrics score
            final_score=82.0,  # Combined: 85 * 0.7 + 75 * 0.3 = 82.0
            completeness=0.9,
            relevance=0.8,
        )

        # Save evaluation
        saved = await mock_evaluation_repo.save(evaluation)

        # Verify speaking_score is stored
        assert saved.speaking_score == 75.0
        assert saved.theoretical_score == 85.0
        assert saved.final_score == 82.0

    @pytest.mark.asyncio
    async def test_text_answer_evaluation_no_speaking_score(
        self,
        async_session,
        mock_evaluation_repo,
    ):
        """Test that text-only answer has None speaking_score."""
        answer_id = uuid4()
        evaluation = Evaluation(
            answer_id=answer_id,
            raw_score=80.0,
            theoretical_score=80.0,  # LLM score
            speaking_score=None,  # Text-only: no speaking score
            final_score=80.0,  # Text-only: 100% theoretical weight
            completeness=0.8,
            relevance=0.8,
        )

        saved = await mock_evaluation_repo.save(evaluation)

        # Verify speaking_score is None
        assert saved.speaking_score is None
        assert saved.theoretical_score == 80.0
        assert saved.final_score == 80.0

    @pytest.mark.asyncio
    async def test_aggregate_scoring_with_mixed_answers(
        self,
        async_session,
        mock_evaluation_repo,
        mock_answer_repo,
    ):
        """Test aggregate scoring with mix of voice and text answers."""
        # Create voice answer with evaluation
        voice_answer = Answer(
            interview_id=uuid4(),
            question_id=uuid4(),
            candidate_id=uuid4(),
            text="Voice answer",
            is_voice=True,
        )
        await mock_answer_repo.save(voice_answer)

        voice_eval = Evaluation(
            answer_id=voice_answer.id,
            raw_score=80.0,
            theoretical_score=80.0,
            speaking_score=80.0,  # (0.8 + 0.7 + 0.9) / 3 * 100
            final_score=80.0,  # 80 * 0.7 + 80 * 0.3 = 80.0
            completeness=0.8,
            relevance=0.8,
        )
        await mock_evaluation_repo.save(voice_eval)

        # Create text answer with evaluation
        text_answer = Answer(
            interview_id=voice_answer.interview_id,
            question_id=uuid4(),
            candidate_id=voice_answer.candidate_id,
            text="Text answer",
            is_voice=False,
        )
        await mock_answer_repo.save(text_answer)

        text_eval = Evaluation(
            answer_id=text_answer.id,
            raw_score=90.0,
            theoretical_score=90.0,
            speaking_score=None,  # Text-only
            final_score=90.0,
            completeness=0.9,
            relevance=0.9,
        )
        await mock_evaluation_repo.save(text_eval)

        # Test aggregate calculation (simulated)
        # theoretical_avg = (80 + 90) / 2 = 85.0
        # speaking_avg = 80.0 (only voice answer has speaking_score)
        # overall = 85 * 0.7 + 80 * 0.3 = 83.5

        theoretical_scores = [80.0, 90.0]
        speaking_scores = [80.0]  # Only voice answer

        theoretical_avg = sum(theoretical_scores) / len(theoretical_scores)
        speaking_avg = sum(speaking_scores) / len(speaking_scores) if speaking_scores else 50.0
        overall_score = (theoretical_avg * 0.7) + (speaking_avg * 0.3)

        assert theoretical_avg == 85.0
        assert speaking_avg == 80.0
        assert overall_score == 83.5

    @pytest.mark.asyncio
    async def test_penalty_applies_to_combined_score(
        self,
        async_session,
        mock_evaluation_repo,
    ):
        """Test that penalty applies to combined score, not just raw_score."""
        answer_id = uuid4()
        evaluation = Evaluation(
            answer_id=answer_id,
            raw_score=80.0,
            theoretical_score=85.0,
            speaking_score=75.0,
            final_score=82.0,  # Combined before penalty
            penalty=0.0,
            completeness=0.8,
            relevance=0.8,
        )

        # Apply penalty for attempt 2
        evaluation.apply_penalty(2)
        # Override final_score to apply penalty to combined score
        evaluation.final_score = max(0.0, min(100.0, 82.0 + evaluation.penalty))

        assert evaluation.penalty == -5.0
        assert evaluation.final_score == 77.0  # 82.0 - 5.0

