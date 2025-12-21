"""Type-safe feedback result models using Pydantic simple inheritance."""

from datetime import datetime
from enum import Enum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


# ============================================
# Enums
# ============================================
class InputType(str, Enum):
    """Input type enumeration (matches DB enum).

    Values match PostgreSQL input_type_enum.
    """

    CODE = "CODE"
    CV = "CV"
    INTERVIEW = "INTERVIEW"


class FeedbackStatus(str, Enum):
    """Feedback status enumeration (matches DB enum).

    Status Transitions:
    - PENDING → PROCESSING (analysis started)
    - PROCESSING → SUCCESS (completed)
    - PROCESSING → RETRYING (transient failure)
    - PROCESSING → FAILED (permanent failure after retries)
    - RETRYING → PROCESSING (retry attempt)
    """

    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    RETRYING = "RETRYING"


# ============================================
# Nested Models for CV Feedback
# ============================================
class OverallAssessment(BaseModel):
    """Overall assessment section (shared by CV and Code feedback)."""

    overall_score: float = Field(ge=0.0, le=100.0, description="Overall score 0-100")
    summary: str = Field(description="2-3 sentence overall assessment")


class SectionFeedback(BaseModel):
    """Reusable section feedback model (for professional_summary, work_experience, projects, skills).

    Score ranges vary by section:
    - professional_summary: 0-15
    - work_experience: 0-25
    - projects: 0-25
    - skills: 0-20
    """

    score: float = Field(ge=0.0, description="Section score (range varies by section)")
    feedback: str = Field(description="Feedback text")
    suggestions: list[str] = Field(
        default_factory=list, description="List of improvement suggestions"
    )


class Recommendation(BaseModel):
    """Single recommendation with priority metadata."""

    recommendation: str = Field(description="Specific recommendation")
    impact: str = Field(description="Expected impact of this recommendation")
    effort: str = Field(
        description="Effort required: 'low', 'medium', or 'high'"
    )


class ActionableRecommendations(BaseModel):
    """Actionable recommendations grouped by priority."""

    high_priority: list[Recommendation] = Field(
        default_factory=list, description="High priority recommendations"
    )
    medium_priority: list[Recommendation] = Field(
        default_factory=list, description="Medium priority recommendations"
    )
    low_priority: list[Recommendation] = Field(
        default_factory=list, description="Low priority recommendations"
    )


class MarketCompetitiveness(BaseModel):
    """Market competitiveness assessment."""

    assessment: str = Field(
        description="Assessment of how competitive this CV is in the current market"
    )
    target_roles: list[str] = Field(
        default_factory=list, description="Suggested target roles"
    )
    improvement_areas: list[str] = Field(
        default_factory=list, description="Areas needing improvement"
    )


# ============================================
# Nested Models for Code Feedback
# ============================================
class CodeQuality(BaseModel):
    """Code quality feedback section."""

    score: float = Field(ge=0.0, le=25.0, description="Code quality score 0-25")
    feedback: str = Field(description="Feedback on code readability, structure, and organization")
    suggestions: list[str] = Field(
        default_factory=list, description="List of improvement suggestions"
    )


class BestPractices(BaseModel):
    """Best practices feedback section."""

    score: float = Field(ge=0.0, le=20.0, description="Best practices score 0-20")
    feedback: str = Field(
        description="Feedback on adherence to best practices and design principles"
    )
    principles_violated: list[str] = Field(
        default_factory=list, description="List of violated principles"
    )
    principles_followed: list[str] = Field(
        default_factory=list, description="List of followed principles"
    )
    suggestions: list[str] = Field(
        default_factory=list, description="List of improvement suggestions"
    )


class CodeActionableRecommendation(BaseModel):
    """Single code recommendation with line reference."""

    recommendation: str = Field(
        description="Most important recommendation to improve the code"
    )
    impact: str = Field(description="Expected impact of this recommendation")
    effort: str = Field(
        description="Effort required: 'low', 'medium', or 'high'"
    )
    line_reference: str | None = Field(
        default=None, description="Line number or section reference if applicable"
    )


# ============================================
# Simple Inheritance Results
# ============================================
class FeedbackResult(BaseModel):
    """Base class for all feedback results.

    Subclasses represent specific analysis types.
    Use Pydantic simple inheritance (no discriminator field).
    Deserialization logic in repository layer uses input_type.
    """

    pass


class InterviewFeedbackResult(FeedbackResult):
    """Interview feedback result (reuses DetailedInterviewFeedback structure).

    This structure matches existing CompleteInterviewUseCase output format
    for seamless integration.
    """

    interview_id: UUID
    overall_score: float = Field(
        ge=0.0, le=100.0, description="Overall interview score 0-100"
    )
    theoretical_score_avg: float = Field(
        ge=0.0, le=100.0, description="Average theoretical knowledge score"
    )
    speaking_score_avg: float | None = Field(
        default=None,
        ge=0.0,
        le=100.0,
        description="Average speaking/communication score (null if no voice data)",
    )

    total_questions: int = Field(ge=0, description="Total questions asked (main + follow-ups)")
    total_follow_ups: int = Field(ge=0, description="Total follow-up questions generated")

    # Detailed feedback per question
    question_feedback: list[dict] = Field(
        default_factory=list,
        description="List of QuestionDetailedFeedback serialized as dicts",
    )

    # Gap analysis
    gap_progression: dict[str, int | float] = Field(
        default_factory=dict,
        description="Gap progression metrics (concepts covered, gaps closed)",
    )

    # Recommendations
    strengths: list[str] = Field(
        default_factory=list, description="Candidate strengths (2-5 points)"
    )
    weaknesses: list[str] = Field(
        default_factory=list, description="Areas needing improvement"
    )
    study_recommendations: list[str] = Field(
        default_factory=list, description="Specific topics to study"
    )
    technique_tips: list[str] = Field(
        default_factory=list, description="Interview technique improvements"
    )

    # Metadata
    completion_time: str = Field(description="ISO timestamp when interview completed")


class CodeReviewFeedbackResult(FeedbackResult):
    """Code review feedback result.

    Matches code_solution_feedback prompt template output_schema.
    Analyzes code for quality, best practices, and actionable improvements.
    """

    submission_id: str = Field(description="External code submission ID (metadata)")
    language: str = Field(
        description="Programming language ('python', 'java', etc.) (metadata)"
    )

    # Matches prompt template output_schema
    overall_assessment: OverallAssessment = Field(
        description="Overall assessment with score and summary"
    )
    code_quality: CodeQuality = Field(
        description="Code quality feedback (score 0-25)"
    )
    best_practices: BestPractices = Field(
        description="Best practices feedback (score 0-20)"
    )
    actionable_recommendations: CodeActionableRecommendation = Field(
        description="Single most important actionable recommendation"
    )


class CVFeedbackResult(FeedbackResult):
    """CV analysis feedback result.

    Matches cv_feedback prompt template output_schema.
    Analyzes CV for structure, content, and market competitiveness.
    """

    cv_analysis_id: UUID = Field(description="CV analysis ID (metadata)")

    # Matches prompt template output_schema
    overall_assessment: OverallAssessment = Field(
        description="Overall assessment with score and summary"
    )
    professional_summary: SectionFeedback = Field(
        description="Professional summary/title feedback (score 0-15)"
    )
    work_experience: SectionFeedback = Field(
        description="Work experience section feedback (score 0-25)"
    )
    projects: SectionFeedback = Field(
        description="Projects section feedback (score 0-25)"
    )
    skills: SectionFeedback = Field(
        description="Skills section feedback (score 0-20)"
    )
    actionable_recommendations: ActionableRecommendations = Field(
        description="Prioritized actionable recommendations"
    )
    market_competitiveness: MarketCompetitiveness = Field(
        description="Market competitiveness assessment"
    )

