"""DTOs for GenerateFollowupUseCase.

Maps state access from InterviewConversationWorkflow._generate_followup_node.
"""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class GenerateFollowupInput(BaseModel):
    """Input for GenerateFollowupUseCase.

    Contains all data needed to generate a follow-up question.
    """

    interview_id: UUID = Field(description="Interview UUID")
    current_question_id: str | None = Field(
        default=None, description="Current question ID"
    )
    parent_question_id: str | None = Field(
        default=None, description="Parent question ID"
    )
    parent_question: dict[str, Any] | None = Field(
        default=None, description="Parent question dict"
    )
    current_question: dict[str, Any] | None = Field(
        default=None, description="Current question dict (may be parent)"
    )
    followup_count: int = Field(default=0, description="Current follow-up count")
    cumulative_gaps: list[str] = Field(
        default_factory=list, description="Cumulative concept gaps"
    )
    latest_answer: dict[str, Any] | None = Field(
        default=None, description="Latest answer dict"
    )
    latest_evaluation: dict[str, Any] | None = Field(
        default=None, description="Latest evaluation dict"
    )
    followup_reason: str | None = Field(
        default=None, description="Reason for follow-up"
    )
    followup_suggestion: dict[str, Any] | None = Field(
        default=None, description="Cached follow-up from unified analysis"
    )
    cached_interview: dict[str, Any] | None = Field(
        default=None, description="Cached interview for performance"
    )

    model_config = {"extra": "forbid"}


class GenerateFollowupOutput(BaseModel):
    """Output from GenerateFollowupUseCase.

    Contains generated follow-up question and state updates.
    """

    current_question_id: str = Field(description="New follow-up question ID")
    current_question: dict[str, Any] = Field(
        description="Follow-up question with metadata"
    )
    parent_question_id: str = Field(description="Parent question ID")
    parent_question: dict[str, Any] = Field(description="Parent question dict")
    followup_count: int = Field(description="Updated follow-up count")
    needs_followup: bool = Field(
        default=False, description="Reset to false after generation"
    )
    cache_updates: dict[str, Any] = Field(
        default_factory=dict, description="Interview cache updates"
    )
    errors: list[str] = Field(default_factory=list, description="Any errors encountered")

    model_config = {"extra": "forbid"}
