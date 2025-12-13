"""Mock LLM adapter for testing without API calls."""

from typing import TYPE_CHECKING, Any
from uuid import UUID

from src.domain.models.evaluation import FollowUpEvaluationContext
from src.domain.models.feedback_result import (
    CVFeedbackResult,
    CodeReviewFeedbackResult,
    FeedbackResult,
    InputType,
)
from src.domain.models.question import Question
from src.application.ports.llm_port import LLMPort

if TYPE_CHECKING:
    from ...adapters.llm.comprehensive_models import ComprehensiveAnalysis


class MockLLMAdapter(LLMPort):
    """Mock LLM adapter implementing LLMPort interface.

    Provides stub implementations for all LLMPort methods.
    Used in tests and development mode when USE_MOCK_ADAPTERS=true.
    """

    async def analyze_feedback(
        self,
        input_type: InputType,
        feedback_input: str,
        context: dict[str, Any] | None = None,
    ) -> FeedbackResult:
        """Mock feedback analysis."""
        from src.domain.models.feedback_result import (
            OverallAssessment,
            SectionFeedback,
            ActionableRecommendations,
            Recommendation,
            MarketCompetitiveness,
            CodeQuality,
            BestPractices,
            CodeActionableRecommendation,
        )

        if input_type == InputType.CV:
            return CVFeedbackResult(
                cv_analysis_id=UUID(),
                overall_assessment=OverallAssessment(
                    overall_score=75.0,
                    summary="Mock CV feedback - overall assessment",
                ),
                professional_summary=SectionFeedback(
                    score=12.0,
                    feedback="Mock professional summary feedback",
                    suggestions=["Improve job title clarity"],
                ),
                work_experience=SectionFeedback(
                    score=20.0,
                    feedback="Mock work experience feedback",
                    suggestions=["Quantify achievements"],
                ),
                projects=SectionFeedback(
                    score=18.0,
                    feedback="Mock projects feedback",
                    suggestions=["Add project links"],
                ),
                skills=SectionFeedback(
                    score=15.0,
                    feedback="Mock skills feedback",
                    suggestions=["Organize by proficiency"],
                ),
                actionable_recommendations=ActionableRecommendations(
                    high_priority=[
                        Recommendation(
                            recommendation="Add quantifiable metrics",
                            impact="High impact on recruiter attention",
                            effort="low",
                        )
                    ],
                    medium_priority=[],
                    low_priority=[],
                ),
                market_competitiveness=MarketCompetitiveness(
                    assessment="Mock market competitiveness assessment",
                    target_roles=["Backend Developer", "Software Engineer"],
                    improvement_areas=["System design", "Cloud experience"],
                ),
            )
        else:  # CODE
            return CodeReviewFeedbackResult(
                submission_id="mock",
                language="python",
                overall_assessment=OverallAssessment(
                    overall_score=80.0,
                    summary="Mock code review - overall assessment",
                ),
                code_quality=CodeQuality(
                    score=20.0,
                    feedback="Mock code quality feedback",
                    suggestions=["Improve variable naming"],
                ),
                best_practices=BestPractices(
                    score=16.0,
                    feedback="Mock best practices feedback",
                    principles_violated=["DRY"],
                    principles_followed=["SOLID"],
                    suggestions=["Extract common logic"],
                ),
                actionable_recommendations=CodeActionableRecommendation(
                    recommendation="Refactor duplicate code",
                    impact="Improves maintainability",
                    effort="medium",
                    line_reference="lines 45-60",
                ),
            )

    # Stub implementations for other LLMPort methods
    # These should be implemented if MockLLMAdapter is used elsewhere
    async def generate_followup_question(
        self,
        parent_question: str,
        answer_text: str,
        missing_concepts: list[str],
        severity: str,
        order: int,
        cumulative_gaps: list[str] | None = None,
        previous_follow_ups: list[dict[str, Any]] | None = None,
        context: dict[str, Any] | None = None,
    ) -> str:
        """Stub - not implemented."""
        raise NotImplementedError("MockLLMAdapter.generate_followup_question not implemented")

    async def generate_interview_recommendations(
        self,
        context: dict[str, Any],
    ) -> dict[str, list[str]]:
        """Stub - not implemented."""
        raise NotImplementedError("MockLLMAdapter.generate_interview_recommendations not implemented")

    async def generate_questions_with_answers_and_rationales_batch(
        self,
        question_specs: list[dict[str, Any]],
        context: dict[str, Any],
    ) -> list[tuple[str, str, str]]:
        """Stub - not implemented."""
        raise NotImplementedError("MockLLMAdapter.generate_questions_with_answers_and_rationales_batch not implemented")

    async def analyze_answer_comprehensive(
        self,
        question: Question,
        answer_text: str,
        context: dict[str, Any],
        followup_context: FollowUpEvaluationContext | None = None,
    ) -> "ComprehensiveAnalysis":
        """Stub - not implemented."""
        raise NotImplementedError("MockLLMAdapter.analyze_answer_comprehensive not implemented")

