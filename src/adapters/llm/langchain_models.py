"""Pydantic models for LangChain structured outputs.

These models define the expected structure of LLM responses.
They are internal to the adapter layer and get mapped to domain models.
"""

from pydantic import BaseModel, Field


class QuestionOutput(BaseModel):
    """Structured output for question generation."""

    question_text: str = Field(
        description="The generated interview question text"
    )
    reasoning: str | None = Field(
        default=None,
        description="Brief reasoning for why this question is relevant (optional)"
    )


class EvaluationOutput(BaseModel):
    """Structured output for answer evaluation."""

    score: float = Field(
        ge=0.0, le=100.0,
        description="Evaluation score from 0-100"
    )
    feedback: str = Field(
        description="Detailed feedback explaining the score"
    )
    strengths: list[str] = Field(
        default_factory=list,
        description="List of answer strengths (2-5 points)"
    )
    weaknesses: list[str] = Field(
        default_factory=list,
        description="List of answer weaknesses (2-5 points)"
    )
    missing_concepts: list[str] = Field(
        default_factory=list,
        description="Key concepts missing from the answer"
    )


class IdealAnswerOutput(BaseModel):
    """Structured output for ideal answer generation."""

    answer_text: str = Field(
        description="The ideal answer (150-300 words)"
    )


class RationaleOutput(BaseModel):
    """Structured output for rationale generation."""

    rationale_text: str = Field(
        description="Explanation of why the answer is ideal (50-100 words)"
    )


class GapDetectionOutput(BaseModel):
    """Structured output for concept gap detection."""

    concepts: list[str] = Field(
        description="Missing key concepts from the answer"
    )
    keywords: list[str] = Field(
        description="Confirmed missing keywords subset"
    )
    confirmed: bool = Field(
        description="Whether gaps are confirmed by LLM analysis"
    )
    severity: str = Field(
        description="Gap severity: 'minor', 'moderate', or 'major'"
    )


class FollowUpOutput(BaseModel):
    """Structured output for follow-up question generation."""

    question_text: str = Field(
        description="The targeted follow-up question"
    )
    focus: str | None = Field(
        default=None,
        description="The specific concept this follow-up targets (optional)"
    )


class RecommendationsOutput(BaseModel):
    """Structured output for interview recommendations."""

    strengths: list[str] = Field(
        description="Top 3-5 candidate strengths"
    )
    weaknesses: list[str] = Field(
        description="Top 3-5 areas for improvement"
    )
    study_topics: list[str] = Field(
        description="Specific topics to study"
    )
    technique_tips: list[str] = Field(
        description="Interview technique tips (voice, pacing, structure)"
    )


class CVSummaryOutput(BaseModel):
    """Structured output for CV summarization."""

    summary_text: str = Field(
        description="Concise CV summary (100-200 words)"
    )
    years_experience: int | None = Field(
        default=None,
        description="Estimated years of professional experience (optional)"
    )


class SkillExtractionOutput(BaseModel):
    """Structured output for skill extraction."""

    class SkillItem(BaseModel):
        """Individual skill with metadata."""
        name: str = Field(description="Skill name")
        category: str | None = Field(
            default=None,
            description="Skill category (e.g., 'programming', 'framework', 'database')"
        )
        proficiency: str | None = Field(
            default=None,
            description="Estimated proficiency if mentioned (e.g., 'beginner', 'intermediate', 'expert')"
        )

    skills: list[SkillItem] = Field(
        description="List of extracted skills with metadata"
    )


class FeedbackReportOutput(BaseModel):
    """Structured output for comprehensive feedback report."""

    report_text: str = Field(
        description="Complete formatted feedback report"
    )
    overall_score: float | None = Field(
        default=None,
        ge=0.0, le=100.0,
        description="Overall interview score if calculated (optional)"
    )
