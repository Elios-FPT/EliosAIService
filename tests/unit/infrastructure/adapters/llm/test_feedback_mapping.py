"""Unit tests for feedback analysis mapping functions."""

import pytest
from uuid import uuid4

from src.infrastructure.adapters.llm.feedback_models import (
    ActionableRecommendations,
    BestPractices,
    CodeActionableRecommendation,
    CodeFeedbackAnalysis,
    CodeQuality,
    CVFeedbackAnalysis,
    MarketCompetitiveness,
    OverallAssessment,
    ProfessionalSummary,
    Projects,
    Recommendation,
    Skills,
    WorkExperience,
)
from src.infrastructure.adapters.llm.langchain_adapter import LangChainAdapter
from src.domain.models.feedback_result import CVFeedbackResult, CodeReviewFeedbackResult


class TestCVFeedbackMapping:
    """Test CV feedback analysis mapping."""

    def test_map_cv_analysis_to_result(self):
        """Test mapping CVFeedbackAnalysis to CVFeedbackResult."""
        entity_id = uuid4()
        adapter = LangChainAdapter(model=None)  # type: ignore

        analysis = CVFeedbackAnalysis(
            overall_assessment=OverallAssessment(
                overall_score=85.0,
                summary="Strong CV with good technical skills",
            ),
            professional_summary=ProfessionalSummary(
                score=12.0,
                feedback="Good professional summary",
                suggestions=["Add more keywords"],
            ),
            work_experience=WorkExperience(
                score=20.0,
                feedback="Strong work experience",
                suggestions=["Quantify achievements"],
            ),
            projects=Projects(
                score=22.0,
                feedback="Good project descriptions",
                suggestions=[],
            ),
            skills=Skills(
                score=18.0,
                feedback="Well-organized skills",
                suggestions=[],
            ),
            actionable_recommendations=ActionableRecommendations(
                high_priority=[
                    Recommendation(
                        recommendation="Add more keywords",
                        impact="High",
                        effort="low",
                    ),
                    Recommendation(
                        recommendation="Get AWS certification",
                        impact="Medium",
                        effort="medium",
                    ),
                ],
                medium_priority=[
                    Recommendation(
                        recommendation="Consider Python certification",
                        impact="Medium",
                        effort="high",
                    ),
                ],
                low_priority=[],
            ),
            market_competitiveness=MarketCompetitiveness(
                assessment="Competitive in mid-level roles",
                target_roles=["Backend Developer", "Full Stack Developer"],
                improvement_areas=["Cloud experience", "System design"],
            ),
        )

        result = adapter._map_cv_analysis_to_result(analysis, entity_id)

        assert isinstance(result, CVFeedbackResult)
        assert result.cv_analysis_id == entity_id
        assert result.work_experience.feedback == "Strong work experience"
        assert result.work_experience.score == 20.0
        assert result.market_competitiveness.improvement_areas == ["Cloud experience", "System design"]
        assert len(result.actionable_recommendations.high_priority) == 2
        assert result.actionable_recommendations.high_priority[0].recommendation == "Add more keywords"
        assert len(result.actionable_recommendations.medium_priority) == 1

    def test_map_cv_analysis_empty_recommendations(self):
        """Test mapping with empty recommendations."""
        adapter = LangChainAdapter(model=None)  # type: ignore

        analysis = CVFeedbackAnalysis(
            overall_assessment=OverallAssessment(overall_score=70.0, summary="Average CV"),
            professional_summary=ProfessionalSummary(score=10.0, feedback="OK", suggestions=[]),
            work_experience=WorkExperience(score=15.0, feedback="Decent", suggestions=[]),
            projects=Projects(score=15.0, feedback="OK", suggestions=[]),
            skills=Skills(score=12.0, feedback="Basic", suggestions=[]),
            actionable_recommendations=ActionableRecommendations(),
            market_competitiveness=MarketCompetitiveness(
                assessment="Needs improvement",
                target_roles=[],
                improvement_areas=[],
            ),
        )

        result = adapter._map_cv_analysis_to_result(analysis, None)

        assert isinstance(result, CVFeedbackResult)
        assert len(result.actionable_recommendations.high_priority) == 0
        assert len(result.actionable_recommendations.medium_priority) == 0
        assert len(result.market_competitiveness.improvement_areas) == 0


class TestCodeFeedbackMapping:
    """Test code feedback analysis mapping."""

    def test_map_code_analysis_to_result(self):
        """Test mapping CodeFeedbackAnalysis to CodeReviewFeedbackResult."""
        entity_id = uuid4()
        adapter = LangChainAdapter(model=None)  # type: ignore

        analysis = CodeFeedbackAnalysis(
            overall_assessment=OverallAssessment(
                overall_score=80.0,
                summary="Good code quality with minor improvements needed",
            ),
            code_quality=CodeQuality(
                score=20.0,
                feedback="Clean and readable code",
                suggestions=["Add comments"],
            ),
            best_practices=BestPractices(
                score=16.0,
                feedback="Follows most best practices",
                principles_violated=["DRY"],
                principles_followed=["SOLID", "KISS"],
                suggestions=["Refactor duplicate code"],
            ),
            actionable_recommendations=CodeActionableRecommendation(
                recommendation="Extract common logic into helper function",
                impact="High",
                effort="medium",
                line_reference="Lines 45-50",
            ),
        )

        result = adapter._map_code_analysis_to_result(analysis, entity_id, "python")

        assert isinstance(result, CodeReviewFeedbackResult)
        assert result.submission_id == str(entity_id)
        assert result.code_quality.score == 20.0
        assert result.code_quality.feedback == "Clean and readable code"
        assert result.best_practices.score == 16.0
        assert result.best_practices.principles_violated == ["DRY"]
        assert result.best_practices.principles_followed == ["SOLID", "KISS"]
        assert result.actionable_recommendations.recommendation == "Extract common logic into helper function"
        assert result.actionable_recommendations.line_reference == "Lines 45-50"
        assert result.language == "python"

    def test_map_code_analysis_empty_violations(self):
        """Test mapping with no violations."""
        adapter = LangChainAdapter(model=None)  # type: ignore

        analysis = CodeFeedbackAnalysis(
            overall_assessment=OverallAssessment(overall_score=95.0, summary="Excellent code"),
            code_quality=CodeQuality(score=25.0, feedback="Perfect", suggestions=[]),
            best_practices=BestPractices(
                score=20.0,
                feedback="Follows all best practices",
                principles_violated=[],
                principles_followed=["SOLID", "DRY", "KISS"],
                suggestions=[],
            ),
            actionable_recommendations=CodeActionableRecommendation(
                recommendation="",
                impact="",
                effort="low",
            ),
        )

        result = adapter._map_code_analysis_to_result(analysis, None, "javascript")

        assert isinstance(result, CodeReviewFeedbackResult)
        assert result.best_practices.principles_violated == []
        assert result.code_quality.score == 25.0
        assert result.best_practices.score == 20.0
        assert result.language == "javascript"

