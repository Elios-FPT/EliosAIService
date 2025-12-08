"""Unit tests for FeedbackMarkdownFormatter."""

import pytest
from uuid import uuid4

from src.domain.models.feedback_result import (
    ActionableRecommendations,
    BestPractices,
    CodeActionableRecommendation,
    CodeQuality,
    CodeReviewFeedbackResult,
    CVFeedbackResult,
    MarketCompetitiveness,
    OverallAssessment,
    Recommendation,
    SectionFeedback,
)
from src.domain.services.feedback_markdown_formatter import FeedbackMarkdownFormatter


class TestFeedbackMarkdownFormatter:
    """Test FeedbackMarkdownFormatter service."""

    @pytest.fixture
    def formatter(self):
        """Create formatter instance."""
        return FeedbackMarkdownFormatter()

    def test_format_cv_result(self, formatter):
        """Test CV feedback markdown generation."""
        result = CVFeedbackResult(
            cv_analysis_id=uuid4(),
            overall_assessment=OverallAssessment(
                overall_score=85.0, summary="Strong CV with good structure."
            ),
            professional_summary=SectionFeedback(
                score=12.0, feedback="Good summary", suggestions=["Add more keywords"]
            ),
            work_experience=SectionFeedback(
                score=22.0, feedback="Excellent experience", suggestions=[]
            ),
            projects=SectionFeedback(
                score=20.0, feedback="Good projects", suggestions=["Add GitHub links"]
            ),
            skills=SectionFeedback(
                score=16.0, feedback="Comprehensive skills", suggestions=[]
            ),
            actionable_recommendations=ActionableRecommendations(
                high_priority=[
                    Recommendation(
                        recommendation="Add quantifiable achievements",
                        impact="High",
                        effort="low",
                    )
                ],
                medium_priority=[],
                low_priority=[],
            ),
            market_competitiveness=MarketCompetitiveness(
                assessment="Competitive for mid-level roles",
                target_roles=["Backend Developer", "Python Developer"],
                improvement_areas=["Leadership experience"],
            ),
        )

        markdown = formatter.format(result)

        # Verify structure
        assert "# CV Feedback Analysis" in markdown
        assert "## Overall Assessment" in markdown
        assert "## Professional Summary" in markdown
        assert "## Work Experience" in markdown
        assert "## Projects" in markdown
        assert "## Skills" in markdown
        assert "## Actionable Recommendations" in markdown
        assert "## Market Competitiveness" in markdown

        # Verify content
        assert "85.0/100" in markdown
        assert "Strong CV with good structure." in markdown
        assert "12.0/15" in markdown
        assert "Good summary" in markdown
        assert "Add more keywords" in markdown
        assert "Add quantifiable achievements" in markdown
        assert "Competitive for mid-level roles" in markdown
        assert "Backend Developer" in markdown
        assert "Leadership experience" in markdown

    def test_format_code_result(self, formatter):
        """Test CODE feedback markdown generation."""
        result = CodeReviewFeedbackResult(
            submission_id="sub-123",
            language="python",
            overall_assessment=OverallAssessment(
                overall_score=78.0, summary="Good code with room for improvement."
            ),
            code_quality=CodeQuality(
                score=20.0,
                feedback="Readable and well-structured",
                suggestions=["Add type hints"],
            ),
            best_practices=BestPractices(
                score=15.0,
                feedback="Generally follows conventions",
                principles_followed=["PEP 8"],
                principles_violated=["Single Responsibility"],
                suggestions=["Refactor large functions"],
            ),
            actionable_recommendations=CodeActionableRecommendation(
                recommendation="Refactor process_data() function",
                impact="Improves maintainability",
                effort="medium",
                line_reference="Lines 45-78",
            ),
        )

        markdown = formatter.format(result)

        # Verify structure
        assert "# Code Review Feedback" in markdown
        assert "## Overall Assessment" in markdown
        assert "## Code Quality" in markdown
        assert "## Best Practices" in markdown
        assert "## Top Recommendation" in markdown

        # Verify content
        assert "78.0/100" in markdown
        assert "Good code with room for improvement." in markdown
        assert "20.0/25" in markdown
        assert "Readable and well-structured" in markdown
        assert "Add type hints" in markdown
        assert "15.0/20" in markdown
        assert "PEP 8" in markdown
        assert "Single Responsibility" in markdown
        assert "Refactor process_data() function" in markdown
        assert "Lines 45-78" in markdown

    def test_format_unsupported_type(self, formatter):
        """Test that unsupported types raise ValueError."""
        from src.domain.models.feedback_result import InterviewFeedbackResult

        result = InterviewFeedbackResult(
            interview_id=uuid4(),
            overall_score=85.0,
            theoretical_score_avg=80.0,
            speaking_score_avg=60.0,
            total_questions=5,
            total_follow_ups=3,
            question_feedback=[],
            gap_progression={},
            strengths=[],
            weaknesses=[],
            study_recommendations=[],
            technique_tips=[],
            completion_time="2025-01-01T00:00:00Z",
        )

        with pytest.raises(ValueError, match="Unsupported result type"):
            formatter.format(result)

    def test_format_cv_result_empty_suggestions(self, formatter):
        """Test CV result with empty suggestions."""
        result = CVFeedbackResult(
            cv_analysis_id=uuid4(),
            overall_assessment=OverallAssessment(
                overall_score=90.0, summary="Excellent CV"
            ),
            professional_summary=SectionFeedback(
                score=15.0, feedback="Perfect", suggestions=[]
            ),
            work_experience=SectionFeedback(
                score=25.0, feedback="Excellent", suggestions=[]
            ),
            projects=SectionFeedback(score=25.0, feedback="Great", suggestions=[]),
            skills=SectionFeedback(score=20.0, feedback="Complete", suggestions=[]),
            actionable_recommendations=ActionableRecommendations(),
            market_competitiveness=MarketCompetitiveness(
                assessment="Highly competitive", target_roles=[], improvement_areas=[]
            ),
        )

        markdown = formatter.format(result)

        # Verify no empty suggestion lists appear
        assert "**Suggestions**:" not in markdown or markdown.count("**Suggestions**:") == 0
        assert "90.0/100" in markdown
        assert "Excellent CV" in markdown

    def test_format_code_result_empty_principles(self, formatter):
        """Test CODE result with empty principles."""
        result = CodeReviewFeedbackResult(
            submission_id="sub-456",
            language="java",
            overall_assessment=OverallAssessment(
                overall_score=80.0, summary="Solid code"
            ),
            code_quality=CodeQuality(
                score=22.0, feedback="Good quality", suggestions=[]
            ),
            best_practices=BestPractices(
                score=18.0,
                feedback="Follows best practices",
                principles_followed=[],
                principles_violated=[],
                suggestions=[],
            ),
            actionable_recommendations=CodeActionableRecommendation(
                recommendation="Continue current approach",
                impact="Maintains quality",
                effort="low",
                line_reference=None,
            ),
        )

        markdown = formatter.format(result)

        # Verify structure still correct
        assert "# Code Review Feedback" in markdown
        assert "80.0/100" in markdown
        assert "Continue current approach" in markdown
        # Line reference should not appear if None
        assert "**Line Reference**:" not in markdown

    def test_format_recommendations_all_priorities(self, formatter):
        """Test recommendations with all priority levels."""
        result = CVFeedbackResult(
            cv_analysis_id=uuid4(),
            overall_assessment=OverallAssessment(
                overall_score=75.0, summary="Good CV"
            ),
            professional_summary=SectionFeedback(
                score=10.0, feedback="OK", suggestions=[]
            ),
            work_experience=SectionFeedback(
                score=20.0, feedback="Good", suggestions=[]
            ),
            projects=SectionFeedback(score=18.0, feedback="Fine", suggestions=[]),
            skills=SectionFeedback(score=15.0, feedback="Adequate", suggestions=[]),
            actionable_recommendations=ActionableRecommendations(
                high_priority=[
                    Recommendation(
                        recommendation="High priority item", impact="Critical", effort="low"
                    )
                ],
                medium_priority=[
                    Recommendation(
                        recommendation="Medium priority item",
                        impact="Important",
                        effort="medium",
                    )
                ],
                low_priority=[
                    Recommendation(
                        recommendation="Low priority item", impact="Nice to have", effort="high"
                    )
                ],
            ),
            market_competitiveness=MarketCompetitiveness(
                assessment="Average", target_roles=[], improvement_areas=[]
            ),
        )

        markdown = formatter.format(result)

        assert "### High Priority" in markdown
        assert "### Medium Priority" in markdown
        assert "### Low Priority" in markdown
        assert "High priority item" in markdown
        assert "Medium priority item" in markdown
        assert "Low priority item" in markdown

    def test_format_recommendations_empty(self, formatter):
        """Test recommendations with no items."""
        result = CVFeedbackResult(
            cv_analysis_id=uuid4(),
            overall_assessment=OverallAssessment(
                overall_score=100.0, summary="Perfect CV"
            ),
            professional_summary=SectionFeedback(
                score=15.0, feedback="Perfect", suggestions=[]
            ),
            work_experience=SectionFeedback(
                score=25.0, feedback="Perfect", suggestions=[]
            ),
            projects=SectionFeedback(score=25.0, feedback="Perfect", suggestions=[]),
            skills=SectionFeedback(score=20.0, feedback="Perfect", suggestions=[]),
            actionable_recommendations=ActionableRecommendations(),
            market_competitiveness=MarketCompetitiveness(
                assessment="Excellent", target_roles=[], improvement_areas=[]
            ),
        )

        markdown = formatter.format(result)

        assert "## Actionable Recommendations" in markdown
        assert "*No recommendations provided.*" in markdown

