"""Unit tests for FeedbackResponse domain entity."""

import pytest
from uuid import uuid4

from src.domain.models.feedback_response import FeedbackResponse
from src.domain.models.feedback_result import (
    CVFeedbackResult,
    InterviewFeedbackResult,
    OverallAssessment,
    SectionFeedback,
    ActionableRecommendations,
    MarketCompetitiveness,
)


class TestFeedbackResponseCreation:
    """Test FeedbackResponse creation."""

    def test_create_feedback_response_with_interview_result(self):
        """Test creating FeedbackResponse with InterviewFeedbackResult."""
        request_id = uuid4()
        interview_id = uuid4()

        result = InterviewFeedbackResult(
            interview_id=interview_id,
            overall_score=85.0,
            theoretical_score_avg=80.0,
            speaking_score_avg=60.0,
            total_questions=5,
            total_follow_ups=3,
            completion_time="2025-12-03T10:30:00Z",
        )

        response = FeedbackResponse(
            request_id=request_id,
            result=result,
        )

        assert response.request_id == request_id
        assert isinstance(response.result, InterviewFeedbackResult)
        assert response.result.interview_id == interview_id
        assert response.id is not None
        assert response.created_at is not None

    def test_create_feedback_response_with_cv_result(self):
        """Test creating FeedbackResponse with CVFeedbackResult."""
        request_id = uuid4()
        cv_analysis_id = uuid4()

        result = CVFeedbackResult(
            cv_analysis_id=cv_analysis_id,
            overall_assessment=OverallAssessment(
                overall_score=75.0,
                summary="Good CV with relevant experience",
            ),
            professional_summary=SectionFeedback(
                score=12.0,
                feedback="Good professional summary",
                suggestions=[],
            ),
            work_experience=SectionFeedback(
                score=20.0,
                feedback="5 years experience",
                suggestions=[],
            ),
            projects=SectionFeedback(
                score=18.0,
                feedback="Good projects",
                suggestions=[],
            ),
            skills=SectionFeedback(
                score=15.0,
                feedback="Relevant skills",
                suggestions=[],
            ),
            actionable_recommendations=ActionableRecommendations(),
            market_competitiveness=MarketCompetitiveness(
                assessment="Competitive",
                target_roles=[],
                improvement_areas=[],
            ),
        )

        response = FeedbackResponse(
            request_id=request_id,
            result=result,
        )

        assert response.request_id == request_id
        assert isinstance(response.result, CVFeedbackResult)
        assert response.result.cv_analysis_id == cv_analysis_id

    def test_get_result_type(self):
        """Test get_result_type method."""
        request_id = uuid4()
        interview_id = uuid4()

        result = InterviewFeedbackResult(
            interview_id=interview_id,
            overall_score=75.0,
            theoretical_score_avg=70.0,
            speaking_score_avg=50.0,
            total_questions=3,
            total_follow_ups=2,
            completion_time="2025-12-03T10:30:00Z",
        )

        response = FeedbackResponse(
            request_id=request_id,
            result=result,
        )

        assert response.get_result_type() == "InterviewFeedbackResult"


class TestFeedbackResponseImmutability:
    """Test FeedbackResponse immutability (should be frozen)."""

    def test_feedback_response_is_immutable(self):
        """Test that FeedbackResponse is immutable (frozen=True)."""
        request_id = uuid4()
        interview_id = uuid4()

        result = InterviewFeedbackResult(
            interview_id=interview_id,
            overall_score=75.0,
            theoretical_score_avg=70.0,
            speaking_score_avg=50.0,
            total_questions=3,
            total_follow_ups=2,
            completion_time="2025-12-03T10:30:00Z",
        )

        response = FeedbackResponse(
            request_id=request_id,
            result=result,
        )

        # Should raise ValidationError when trying to modify
        with pytest.raises(Exception):  # Pydantic raises ValidationError for frozen models
            response.request_id = uuid4()

