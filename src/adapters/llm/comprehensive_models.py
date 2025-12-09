"""Pydantic models for comprehensive answer analysis (Phase 2).

Unified output schema consolidating evaluation, gap detection, and follow-up
generation into a single LLM call.
"""

from pydantic import BaseModel, Field
from typing import List, Literal


class EvaluationDimension(BaseModel):
    """Single evaluation dimension (e.g., technical_accuracy)."""

    dimension_name: str
    score: float = Field(ge=0.0, le=40.0, description="Score for this dimension (max varies by dimension)")
    reasoning: str = Field(description="Explanation for this dimension's score")


class EvaluationOutput(BaseModel):
    """Part 1: Answer evaluation with multi-dimensional scoring."""

    dimensions: List[EvaluationDimension] = Field(
        min_items=4,
        max_items=4,
        description="Four evaluation dimensions: technical_accuracy, depth_of_understanding, clarity_of_communication, practical_application",
    )
    total_score: float = Field(ge=0.0, le=100.0, description="Total score (0-100)")
    strengths: List[str] = Field(description="List of answer strengths")
    weaknesses: List[str] = Field(description="List of answer weaknesses")
    improvement_suggestions: List[str] = Field(description="Suggestions for improvement")
    reasoning: str = Field(description="Overall evaluation reasoning")


class ConceptGapOutput(BaseModel):
    """Part 2: Gap detection result for a single concept."""

    concept: str = Field(description="Missing or incomplete concept")
    severity: Literal["minor", "moderate", "major"] = Field(description="Gap severity level")
    explanation: str = Field(description="Explanation of why this is a gap")


class FollowUpOutput(BaseModel):
    """Part 3: Follow-up question suggestion (optional)."""

    question_text: str | None = Field(
        default=None, description="Follow-up question text (null if no follow-up needed)"
    )
    reason: str | None = Field(default=None, description="Reason for generating this follow-up")
    target_gaps: List[str] = Field(
        default_factory=list, description="List of gap concepts this follow-up targets"
    )


class ComprehensiveAnalysis(BaseModel):
    """Unified output from comprehensive_answer_analysis prompt.

    Consolidates evaluation, gap detection, and follow-up generation
    into a single structured response.
    """

    evaluation: EvaluationOutput = Field(description="Answer evaluation with multi-dimensional scoring")
    gaps: List[ConceptGapOutput] = Field(
        default_factory=list, description="List of detected concept gaps"
    )
    follow_up: FollowUpOutput | None = Field(
        default=None, description="Optional follow-up question suggestion"
    )
    confidence: float = Field(
        ge=0.0, le=1.0, default=0.8, description="Confidence in the analysis (0.0-1.0)"
    )

