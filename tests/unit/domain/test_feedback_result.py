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
    """Test CodeReviewFeedbackResult model."""

    def test_code_review_feedback_result_creation(self):
        """Test creating valid CodeReviewFeedbackResult."""
        from src.domain.models.feedback_result import (
            OverallAssessment,
            CodeQuality,
            BestPractices,
            CodeActionableRecommendation,
        )

        result = CodeReviewFeedbackResult(
            submission_id="sub_123",
            language="python",
            overall_assessment=OverallAssessment(
                overall_score=85.0,
                summary="Good code quality overall",
            ),
            code_quality=CodeQuality(
                score=20.0,
                feedback="Code is readable and well-structured",
                suggestions=["Add more comments"],
            ),
            best_practices=BestPractices(
                score=18.0,
                feedback="Follows most best practices",
                principles_violated=[],
                principles_followed=["SOLID", "DRY"],
                suggestions=["Consider design patterns"],
            ),
            actionable_recommendations=CodeActionableRecommendation(
                recommendation="Extract magic numbers to constants",
                impact="Improves maintainability",
                effort="low",
                line_reference="line 42",
            ),
        )

        assert result.submission_id == "sub_123"
        assert result.overall_assessment.overall_score == 85.0
        assert result.code_quality.score == 20.0
        assert isinstance(result, FeedbackResult)  # Inheritance check

    def test_code_review_feedback_result_score_bounds(self):
        """Test score validation (overall 0-100, code_quality 0-25, best_practices 0-20)."""
        from src.domain.models.feedback_result import (
            OverallAssessment,
            CodeQuality,
            BestPractices,
            CodeActionableRecommendation,
        )

        with pytest.raises(ValidationError):
            CodeReviewFeedbackResult(
                submission_id="sub_123",
                language="python",
                overall_assessment=OverallAssessment(
                    overall_score=150.0,  # Invalid
                    summary="Test",
                ),
                code_quality=CodeQuality(score=20.0, feedback="Test"),
                best_practices=BestPractices(score=18.0, feedback="Test"),
                actionable_recommendations=CodeActionableRecommendation(
                    recommendation="Test", impact="Test", effort="low"
                ),
            )

        with pytest.raises(ValidationError):
            CodeReviewFeedbackResult(
                submission_id="sub_123",
                language="python",
                overall_assessment=OverallAssessment(overall_score=75.0, summary="Test"),
                code_quality=CodeQuality(score=30.0, feedback="Test"),  # Invalid (>25)
                best_practices=BestPractices(score=18.0, feedback="Test"),
                actionable_recommendations=CodeActionableRecommendation(
                    recommendation="Test", impact="Test", effort="low"
                ),
            )


class TestCVFeedbackResult:
    """Test CVFeedbackResult model."""

    def test_cv_feedback_result_creation(self):
        """Test creating valid CVFeedbackResult."""
        from src.domain.models.feedback_result import (
            OverallAssessment,
            SectionFeedback,
            ActionableRecommendations,
            MarketCompetitiveness,
        )

        result = CVFeedbackResult(
            cv_analysis_id=uuid4(),
            overall_assessment=OverallAssessment(
                overall_score=80.0,
                summary="Strong CV with good technical background",
            ),
            professional_summary=SectionFeedback(
                score=12.0,
                feedback="Clear professional positioning",
                suggestions=["Add more keywords"],
            ),
            work_experience=SectionFeedback(
                score=20.0,
                feedback="Well-structured work experience",
                suggestions=["Quantify achievements"],
            ),
            projects=SectionFeedback(
                score=18.0,
                feedback="Good project descriptions",
                suggestions=["Add project links"],
            ),
            skills=SectionFeedback(
                score=15.0,
                feedback="Relevant skills listed",
                suggestions=["Organize by proficiency"],
            ),
            actionable_recommendations=ActionableRecommendations(
                high_priority=[],
                medium_priority=[],
                low_priority=[],
            ),
            market_competitiveness=MarketCompetitiveness(
                assessment="Competitive for mid-level positions",
                target_roles=["Backend Developer"],
                improvement_areas=["System design"],
            ),
        )

        assert result.overall_assessment.overall_score == 80.0
        assert result.work_experience.score == 20.0
        assert isinstance(result, FeedbackResult)  # Inheritance check

    def test_cv_feedback_result_score_bounds(self):
        """Test score validation (overall 0-100, sections have varying ranges)."""
        from src.domain.models.feedback_result import (
            OverallAssessment,
            SectionFeedback,
            ActionableRecommendations,
            MarketCompetitiveness,
        )

        with pytest.raises(ValidationError):
            CVFeedbackResult(
                cv_analysis_id=uuid4(),
                overall_assessment=OverallAssessment(
                    overall_score=150.0,  # Invalid
                    summary="Test",
                ),
                professional_summary=SectionFeedback(score=12.0, feedback="Test"),
                work_experience=SectionFeedback(score=20.0, feedback="Test"),
                projects=SectionFeedback(score=18.0, feedback="Test"),
                skills=SectionFeedback(score=15.0, feedback="Test"),
                actionable_recommendations=ActionableRecommendations(),
                market_competitiveness=MarketCompetitiveness(
                    assessment="Test", target_roles=[], improvement_areas=[]
                ),
            )

    def test_cv_feedback_result_default_fields(self):
        """Test default field values."""
        from src.domain.models.feedback_result import (
            OverallAssessment,
            SectionFeedback,
            ActionableRecommendations,
            MarketCompetitiveness,
        )

        result = CVFeedbackResult(
            cv_analysis_id=uuid4(),
            overall_assessment=OverallAssessment(overall_score=75.0, summary="Test"),
            professional_summary=SectionFeedback(score=10.0, feedback="Test"),
            work_experience=SectionFeedback(score=18.0, feedback="Test"),
            projects=SectionFeedback(score=15.0, feedback="Test"),
            skills=SectionFeedback(score=12.0, feedback="Test"),
            actionable_recommendations=ActionableRecommendations(),
            market_competitiveness=MarketCompetitiveness(
                assessment="Test", target_roles=[], improvement_areas=[]
            ),
        )

        assert result.actionable_recommendations.high_priority == []
        assert result.actionable_recommendations.medium_priority == []
        assert result.actionable_recommendations.low_priority == []
        assert result.market_competitiveness.target_roles == []
        assert result.market_competitiveness.improvement_areas == []

