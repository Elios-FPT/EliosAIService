"""Unit tests for feedback mappers."""

import pytest
from datetime import datetime
from uuid import uuid4

from src.adapters.persistence.mappers import (
    FeedbackRequestMapper,
    FeedbackResponseMapper,
)
from src.adapters.persistence.models import (
    FeedbackRequestModel,
    FeedbackResponseModel,
)
from src.domain.models.feedback_request import FeedbackRequest
from src.domain.models.feedback_response import FeedbackResponse
from src.domain.models.feedback_result import (
    CVFeedbackResult,
    CodeReviewFeedbackResult,
    FeedbackStatus,
    InputType,
    InterviewFeedbackResult,
)


class TestFeedbackRequestMapper:
    """Test FeedbackRequestMapper."""

    def test_to_domain(self):
        """Test converting DB model to domain model."""
        db_model = FeedbackRequestModel(
            id=uuid4(),
            entity_id=uuid4(),
            input_type="INTERVIEW",
            user_id=uuid4(),
            status="PENDING",
            error_message=None,
            feedback_input='{"questions": []}',
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        domain_model = FeedbackRequestMapper.to_domain(db_model)

        assert domain_model.id == db_model.id
        assert domain_model.entity_id == db_model.entity_id
        assert domain_model.input_type == InputType.INTERVIEW
        assert domain_model.status == FeedbackStatus.PENDING
        assert domain_model.user_id == db_model.user_id
        assert domain_model.feedback_input == '{"questions": []}'

    def test_to_db_model(self):
        """Test converting domain model to DB model."""
        domain_model = FeedbackRequest(
            id=uuid4(),
            entity_id=uuid4(),
            input_type=InputType.CV,
            user_id=uuid4(),
            status=FeedbackStatus.PROCESSING,
            error_message=None,
            feedback_input='{"summary": "test"}',
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        db_model = FeedbackRequestMapper.to_db_model(domain_model)

        assert db_model.id == domain_model.id
        assert db_model.entity_id == domain_model.entity_id
        assert db_model.input_type == "CV"
        assert db_model.status == "PROCESSING"
        assert db_model.feedback_input == '{"summary": "test"}'

    def test_update_db_model(self):
        """Test updating DB model from domain model."""
        db_model = FeedbackRequestModel(
            id=uuid4(),
            entity_id=uuid4(),
            input_type="INTERVIEW",
            status="PENDING",
            feedback_input='{"questions": []}',
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        domain_model = FeedbackRequest(
            id=db_model.id,
            entity_id=db_model.entity_id,
            input_type=InputType.INTERVIEW,
            status=FeedbackStatus.SUCCESS,
            error_message="Test error",
            feedback_input='{"questions": [{"id": 1}]}',
            created_at=db_model.created_at,
            updated_at=datetime.utcnow(),
        )

        FeedbackRequestMapper.update_db_model(db_model, domain_model)

        assert db_model.status == "SUCCESS"
        assert db_model.error_message == "Test error"
        assert db_model.feedback_input == '{"questions": [{"id": 1}]}'


class TestFeedbackResponseMapper:
    """Test FeedbackResponseMapper."""

    def test_to_domain_interview_result(self):
        """Test converting DB model to domain with InterviewFeedbackResult."""
        interview_id = uuid4()
        db_model = FeedbackResponseModel(
            id=uuid4(),
            feedback_request_id=uuid4(),
            result_json={
                "interview_id": str(interview_id),
                "overall_score": 85.5,
                "theoretical_score_avg": 80.0,
                "speaking_score_avg": 60.0,
                "total_questions": 5,
                "total_follow_ups": 3,
                "completion_time": "2025-12-03T10:30:00Z",
            },
            created_at=datetime.utcnow(),
        )

        domain_model = FeedbackResponseMapper.to_domain(db_model, InputType.INTERVIEW)

        assert isinstance(domain_model.result, InterviewFeedbackResult)
        assert domain_model.result.interview_id == interview_id
        assert domain_model.result.overall_score == 85.5

    def test_to_domain_cv_result(self):
        """Test converting DB model to domain with CVFeedbackResult."""
        cv_analysis_id = uuid4()
        db_model = FeedbackResponseModel(
            id=uuid4(),
            feedback_request_id=uuid4(),
            result_json={
                "cv_analysis_id": str(cv_analysis_id),
                "overall_assessment": {
                    "overall_score": 75.0,
                    "summary": "Good CV",
                },
                "professional_summary": {
                    "score": 12.0,
                    "feedback": "Good summary",
                    "suggestions": [],
                },
                "work_experience": {
                    "score": 20.0,
                    "feedback": "5 years experience",
                    "suggestions": [],
                },
                "projects": {
                    "score": 18.0,
                    "feedback": "Good projects",
                    "suggestions": [],
                },
                "skills": {
                    "score": 15.0,
                    "feedback": "Relevant skills",
                    "suggestions": [],
                },
                "actionable_recommendations": {
                    "high_priority": [],
                    "medium_priority": [],
                    "low_priority": [],
                },
                "market_competitiveness": {
                    "assessment": "Competitive",
                    "target_roles": [],
                    "improvement_areas": [],
                },
            },
            created_at=datetime.utcnow(),
        )

        domain_model = FeedbackResponseMapper.to_domain(db_model, InputType.CV)

        assert isinstance(domain_model.result, CVFeedbackResult)
        assert domain_model.result.cv_analysis_id == cv_analysis_id
        assert domain_model.result.overall_assessment.overall_score == 75.0
        assert domain_model.result.work_experience.feedback == "5 years experience"

    def test_to_domain_code_result(self):
        """Test converting DB model to domain with CodeReviewFeedbackResult."""
        db_model = FeedbackResponseModel(
            id=uuid4(),
            feedback_request_id=uuid4(),
            result_json={
                "submission_id": "sub_123",
                "language": "python",
                "overall_assessment": {
                    "overall_score": 85.0,
                    "summary": "Good code quality",
                },
                "code_quality": {
                    "score": 20.0,
                    "feedback": "Clean code",
                    "suggestions": [],
                },
                "best_practices": {
                    "score": 16.0,
                    "feedback": "Follows best practices",
                    "principles_violated": [],
                    "principles_followed": ["SOLID"],
                    "suggestions": [],
                },
                "actionable_recommendations": {
                    "recommendation": "Add error handling",
                    "impact": "High",
                    "effort": "medium",
                    "line_reference": None,
                },
            },
            created_at=datetime.utcnow(),
        )

        domain_model = FeedbackResponseMapper.to_domain(db_model, InputType.CODE)

        assert isinstance(domain_model.result, CodeReviewFeedbackResult)
        assert domain_model.result.submission_id == "sub_123"
        assert domain_model.result.code_quality.score == 20.0
        assert domain_model.result.overall_assessment.overall_score == 85.0

    def test_to_domain_unknown_input_type(self):
        """Test that unknown input_type raises ValueError."""
        db_model = FeedbackResponseModel(
            id=uuid4(),
            feedback_request_id=uuid4(),
            result_json={},
            created_at=datetime.utcnow(),
        )

        with pytest.raises(ValueError, match="Unknown input_type"):
            FeedbackResponseMapper.to_domain(db_model, "UNKNOWN")  # type: ignore

    def test_to_db_model(self):
        """Test converting domain model to DB model."""
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

        domain_model = FeedbackResponse(
            id=uuid4(),
            request_id=uuid4(),
            result=result,
            created_at=datetime.utcnow(),
        )

        db_model = FeedbackResponseMapper.to_db_model(domain_model)

        assert db_model.id == domain_model.id
        assert db_model.feedback_request_id == domain_model.request_id
        assert db_model.result_json["interview_id"] == str(interview_id)
        assert db_model.result_json["overall_score"] == 75.0

