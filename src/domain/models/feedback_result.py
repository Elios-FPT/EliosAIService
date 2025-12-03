"""Type-safe feedback result models using Pydantic simple inheritance."""

from datetime import datetime
from enum import Enum
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
    speaking_score_avg: float = Field(
        ge=0.0, le=100.0, description="Average speaking/communication score"
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
    """Code review feedback result (STUB - not implemented in Phase 04).

    Future implementation will analyze code for:
    - Code quality (maintainability, readability)
    - Bugs and security issues
    - Code smells and best practices
    """

    submission_id: str = Field(description="External code submission ID")

    # Quality scores
    code_quality_score: float = Field(
        ge=0.0, le=100.0, description="Overall code quality score"
    )
    maintainability_score: float = Field(
        ge=0.0, le=100.0, description="Maintainability score"
    )
    readability_score: float = Field(
        ge=0.0, le=100.0, description="Readability score"
    )

    # Detailed analysis
    bugs_detected: list[dict] = Field(
        default_factory=list,
        description="List of bugs: {severity, line, description}",
    )
    security_issues: list[dict] = Field(
        default_factory=list,
        description="Security issues: {severity, type, recommendation}",
    )
    code_smells: list[dict] = Field(
        default_factory=list,
        description="Code smells: {type, location, suggestion}",
    )
    best_practices_violations: list[str] = Field(
        default_factory=list, description="Best practice violations"
    )

    # Recommendations
    refactoring_suggestions: list[str] = Field(default_factory=list)
    performance_tips: list[str] = Field(default_factory=list)

    # Metadata
    language: str = Field(description="Programming language ('python', 'java', etc.)")


class CVFeedbackResult(FeedbackResult):
    """CV analysis feedback result.

    Analyzes CV for skills, experience, education, and provides
    career improvement recommendations.
    """

    cv_analysis_id: UUID

    # Skills analysis
    skills_identified: list[dict] = Field(
        default_factory=list,
        description="Skills: {name, proficiency, years}",
    )
    primary_skills: list[str] = Field(
        default_factory=list, description="Top skills for interview focus"
    )
    secondary_skills: list[str] = Field(
        default_factory=list, description="Additional skills"
    )

    # Experience
    total_experience_years: float = Field(ge=0.0, description="Total work experience")
    work_experience_summary: str = Field(description="Work experience summary")

    # Education
    education_level: str = Field(description="Highest education level")
    education_details: list[dict] = Field(
        default_factory=list,
        description="Education entries: {degree, institution, year}",
    )

    # Recommendations
    skill_gaps: list[str] = Field(
        default_factory=list, description="Identified skill gaps for target role"
    )
    improvement_areas: list[str] = Field(
        default_factory=list, description="Areas needing development"
    )
    suggested_certifications: list[str] = Field(
        default_factory=list, description="Recommended certifications"
    )

    # Metadata
    language: str = Field(description="CV language ('en', 'vi', etc.)")

