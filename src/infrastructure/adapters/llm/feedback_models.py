"""Pydantic models for feedback analysis LLM output."""

from pydantic import BaseModel, Field
from typing import Any


class OverallAssessment(BaseModel):
    """Overall assessment section."""
    overall_score: float = Field(ge=0.0, le=100.0)
    summary: str


class ProfessionalSummary(BaseModel):
    """Professional summary feedback."""
    score: float = Field(ge=0.0, le=15.0)
    feedback: str
    suggestions: list[str] = Field(default_factory=list)


class WorkExperience(BaseModel):
    """Work experience feedback."""
    score: float = Field(ge=0.0, le=25.0)
    feedback: str
    suggestions: list[str] = Field(default_factory=list)


class Projects(BaseModel):
    """Projects feedback."""
    score: float = Field(ge=0.0, le=25.0)
    feedback: str
    suggestions: list[str] = Field(default_factory=list)


class Skills(BaseModel):
    """Skills feedback."""
    score: float = Field(ge=0.0, le=20.0)
    feedback: str
    suggestions: list[str] = Field(default_factory=list)


class Recommendation(BaseModel):
    """Single recommendation."""
    recommendation: str
    impact: str
    effort: str  # "low" | "medium" | "high"


class ActionableRecommendations(BaseModel):
    """Actionable recommendations grouped by priority."""
    high_priority: list[Recommendation] = Field(default_factory=list)
    medium_priority: list[Recommendation] = Field(default_factory=list)
    low_priority: list[Recommendation] = Field(default_factory=list)


class MarketCompetitiveness(BaseModel):
    """Market competitiveness assessment."""
    assessment: str
    target_roles: list[str] = Field(default_factory=list)
    improvement_areas: list[str] = Field(default_factory=list)


class CVFeedbackAnalysis(BaseModel):
    """CV feedback analysis output from LLM."""
    overall_assessment: OverallAssessment
    professional_summary: ProfessionalSummary
    work_experience: WorkExperience
    projects: Projects
    skills: Skills
    actionable_recommendations: ActionableRecommendations
    market_competitiveness: MarketCompetitiveness


class CodeQuality(BaseModel):
    """Code quality feedback."""
    score: float = Field(ge=0.0, le=25.0)
    feedback: str
    suggestions: list[str] = Field(default_factory=list)


class BestPractices(BaseModel):
    """Best practices feedback."""
    score: float = Field(ge=0.0, le=20.0)
    feedback: str
    principles_violated: list[str] = Field(default_factory=list)
    principles_followed: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)


class CodeActionableRecommendation(BaseModel):
    """Single code recommendation."""
    recommendation: str
    impact: str
    effort: str  # "low" | "medium" | "high"
    line_reference: str | None = None


class CodeFeedbackAnalysis(BaseModel):
    """Code feedback analysis output from LLM."""
    overall_assessment: OverallAssessment
    code_quality: CodeQuality
    best_practices: BestPractices
    actionable_recommendations: CodeActionableRecommendation


