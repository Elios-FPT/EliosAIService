"""Mock LLM adapter for testing without API calls."""

from typing import TYPE_CHECKING, Any
from uuid import UUID

from ...domain.models.evaluation import FollowUpEvaluationContext
from ...domain.models.feedback_result import (
    CVFeedbackResult,
    CodeReviewFeedbackResult,
    FeedbackResult,
    InputType,
)
from ...domain.models.question import Question
from ...domain.ports.llm_port import LLMPort

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
        if input_type == InputType.CV:
            return CVFeedbackResult(
                cv_analysis_id=UUID(),
                skills_identified=[],
                primary_skills=[],
                secondary_skills=[],
                total_experience_years=0.0,
                work_experience_summary="Mock CV feedback",
                education_level="Unknown",
                education_details=[],
                skill_gaps=[],
                improvement_areas=[],
                suggested_certifications=[],
                language="en",
            )
        else:  # CODE
            return CodeReviewFeedbackResult(
                submission_id="mock",
                code_quality_score=75.0,
                maintainability_score=80.0,
                readability_score=70.0,
                bugs_detected=[],
                security_issues=[],
                code_smells=[],
                best_practices_violations=[],
                refactoring_suggestions=[],
                performance_tips=[],
                language="python",
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

