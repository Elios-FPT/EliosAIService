"""DTOs for DecideFollowupUseCase.

Maps state access from InterviewConversationWorkflow._decide_followup_node.
"""

from typing import Any

from pydantic import BaseModel, Field


class DecideFollowupInput(BaseModel):
    """Input for DecideFollowupUseCase.

    Contains evaluation and follow-up count to decide if follow-up needed.
    """

    followup_count: int = Field(default=0, description="Current follow-up count")
    latest_evaluation: dict[str, Any] = Field(
        description="Latest evaluation (Evaluation.model_dump)"
    )
    cumulative_gaps: list[str] = Field(
        default_factory=list, description="Current cumulative gaps"
    )

    model_config = {"extra": "forbid"}


class DecideFollowupOutput(BaseModel):
    """Output from DecideFollowupUseCase.

    Contains follow-up decision and updated gaps.
    """

    needs_followup: bool = Field(description="Whether follow-up is needed")
    followup_reason: str | None = Field(
        default=None, description="Reason for follow-up decision"
    )
    cumulative_gaps: list[str] = Field(
        default_factory=list, description="Updated cumulative gaps"
    )
    errors: list[str] = Field(default_factory=list, description="Any errors encountered")

    model_config = {"extra": "forbid"}
