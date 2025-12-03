"""Unit tests for feedback result models and ENUMs."""

import pytest
from pydantic import ValidationError
from uuid import uuid4

from src.domain.models.feedback_result import (
    CVFeedbackResult,
    CodeReviewFeedbackResult,
    FeedbackResult,
    FeedbackStatus,
    InputType,
    InterviewFeedbackResult,
)


class TestInputTypeEnum:
    """Test InputType ENUM values."""

    def test_input_type_enum_values(self):
        """Test InputType enum has correct values."""
        assert InputType.CODE.value == "CODE"
        assert InputType.CV.value == "CV"
        assert InputType.INTERVIEW.value == "INTERVIEW"

    def test_input_type_enum_string_inheritance(self):
        """Test InputType inherits from str."""
        assert isinstance(InputType.CODE, str)
        assert str(InputType.CV) == "CV"


class TestFeedbackStatusEnum:
    """Test FeedbackStatus ENUM values."""

    def test_feedback_status_enum_values(self):
        """Test FeedbackStatus enum has all required values."""
        assert FeedbackStatus.PENDING.value == "PENDING"
        assert FeedbackStatus.PROCESSING.value == "PROCESSING"
        assert FeedbackStatus.SUCCESS.value == "SUCCESS"
        assert FeedbackStatus.FAILED.value == "FAILED"
        assert FeedbackStatus.RETRYING.value == "RETRYING"

    def test_feedback_status_enum_string_inheritance(self):
        """Test FeedbackStatus inherits from str."""
        assert isinstance(FeedbackStatus.PENDING, str)
        assert str(FeedbackStatus.SUCCESS) == "SUCCESS"


class TestFeedbackResultBase:
    """Test FeedbackResult base class."""

    def test_feedback_result_base_class(self):
        """Test FeedbackResult is a valid Pydantic model."""
        result = FeedbackResult()
        assert isinstance(result, FeedbackResult)
        assert isinstance(result, FeedbackResult)


class TestInterviewFeedbackResult:
    """Test InterviewFeedbackResult model."""

    def test_interview_feedback_result_creation(self):
        """Test creating valid InterviewFeedbackResult."""
        result = InterviewFeedbackResult(
            interview_id=uuid4(),
            overall_score=85.5,
            theoretical_score_avg=80.0,
            speaking_score_avg=60.0,
            total_questions=5,
            total_follow_ups=3,
            question_feedback=[{"question_id": str(uuid4()), "score": 75.0}],
            gap_progression={"concepts_covered": 10, "gaps_closed": 7},
            strengths=["Strong algorithmic thinking"],
            weaknesses=["Limited system design experience"],
            study_recommendations=["Review microservices patterns"],
            technique_tips=["Practice STAR method"],
            completion_time="2025-12-03T10:30:00Z",
        )

        assert result.overall_score == 85.5
        assert result.theoretical_score_avg == 80.0
        assert result.speaking_score_avg == 60.0
        assert result.total_questions == 5
        assert result.total_follow_ups == 3
        assert isinstance(result, FeedbackResult)  # Inheritance check

    def test_interview_feedback_result_score_bounds(self):
        """Test score validation (must be 0-100)."""
        with pytest.raises(ValidationError):
            InterviewFeedbackResult(
                interview_id=uuid4(),
                overall_score=101.0,  # Invalid
                theoretical_score_avg=80.0,
                speaking_score_avg=60.0,
                total_questions=5,
                total_follow_ups=3,
                completion_time="2025-12-03T10:30:00Z",
            )

        with pytest.raises(ValidationError):
            InterviewFeedbackResult(
                interview_id=uuid4(),
                overall_score=-1.0,  # Invalid
                theoretical_score_avg=80.0,
                speaking_score_avg=60.0,
                total_questions=5,
                total_follow_ups=3,
                completion_time="2025-12-03T10:30:00Z",
            )

    def test_interview_feedback_result_default_fields(self):
        """Test default field values."""
        result = InterviewFeedbackResult(
            interview_id=uuid4(),
            overall_score=75.0,
            theoretical_score_avg=70.0,
            speaking_score_avg=50.0,
            total_questions=3,
            total_follow_ups=2,
            completion_time="2025-12-03T10:30:00Z",
        )

        assert result.question_feedback == []
        assert result.gap_progression == {}
        assert result.strengths == []
        assert result.weaknesses == []
        assert result.study_recommendations == []
        assert result.technique_tips == []

    def test_interview_feedback_result_negative_counts(self):
        """Test that counts cannot be negative."""
        with pytest.raises(ValidationError):
            InterviewFeedbackResult(
                interview_id=uuid4(),
                overall_score=75.0,
                theoretical_score_avg=70.0,
                speaking_score_avg=50.0,
                total_questions=-1,  # Invalid
                total_follow_ups=2,
                completion_time="2025-12-03T10:30:00Z",
            )


class TestCodeReviewFeedbackResult:
    """Test CodeReviewFeedbackResult model (stub)."""

    def test_code_review_feedback_result_creation(self):
        """Test creating valid CodeReviewFeedbackResult."""
        result = CodeReviewFeedbackResult(
            submission_id="sub_123",
            code_quality_score=85.0,
            maintainability_score=80.0,
            readability_score=75.0,
            language="python",
        )

        assert result.submission_id == "sub_123"
        assert result.code_quality_score == 85.0
        assert isinstance(result, FeedbackResult)  # Inheritance check

    def test_code_review_feedback_result_score_bounds(self):
        """Test score validation (must be 0-100)."""
        with pytest.raises(ValidationError):
            CodeReviewFeedbackResult(
                submission_id="sub_123",
                code_quality_score=150.0,  # Invalid
                maintainability_score=80.0,
                readability_score=75.0,
                language="python",
            )

    def test_code_review_feedback_result_default_fields(self):
        """Test default field values."""
        result = CodeReviewFeedbackResult(
            submission_id="sub_123",
            code_quality_score=75.0,
            maintainability_score=70.0,
            readability_score=65.0,
            language="java",
        )

        assert result.bugs_detected == []
        assert result.security_issues == []
        assert result.code_smells == []
        assert result.best_practices_violations == []
        assert result.refactoring_suggestions == []
        assert result.performance_tips == []


class TestCVFeedbackResult:
    """Test CVFeedbackResult model."""

    def test_cv_feedback_result_creation(self):
        """Test creating valid CVFeedbackResult."""
        result = CVFeedbackResult(
            cv_analysis_id=uuid4(),
            total_experience_years=5.5,
            work_experience_summary="5 years as backend developer",
            education_level="Bachelor's Degree",
            language="en",
        )

        assert result.total_experience_years == 5.5
        assert result.work_experience_summary == "5 years as backend developer"
        assert isinstance(result, FeedbackResult)  # Inheritance check

    def test_cv_feedback_result_negative_experience(self):
        """Test that experience years cannot be negative."""
        with pytest.raises(ValidationError):
            CVFeedbackResult(
                cv_analysis_id=uuid4(),
                total_experience_years=-1.0,  # Invalid
                work_experience_summary="Summary",
                education_level="Bachelor's",
                language="en",
            )

    def test_cv_feedback_result_default_fields(self):
        """Test default field values."""
        result = CVFeedbackResult(
            cv_analysis_id=uuid4(),
            total_experience_years=3.0,
            work_experience_summary="Summary",
            education_level="Bachelor's",
            language="en",
        )

        assert result.skills_identified == []
        assert result.primary_skills == []
        assert result.secondary_skills == []
        assert result.education_details == []
        assert result.skill_gaps == []
        assert result.improvement_areas == []
        assert result.suggested_certifications == []

