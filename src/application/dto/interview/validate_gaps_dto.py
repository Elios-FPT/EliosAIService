"""DTOs for ValidateGapsUseCase.

Maps state access from InterviewConversationWorkflow._validate_gaps_node.
"""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ValidateGapsInput(BaseModel):
    """Input for ValidateGapsUseCase.

    Contains data needed to validate cumulative gaps against DB.
    """

    interview_id: UUID = Field(description="Interview UUID")
    parent_question_id: UUID | None = Field(
        default=None, description="Parent question ID if follow-up"
    )
    cumulative_gaps: list[str] = Field(
        default_factory=list, description="Gaps from workflow state"
    )
    evaluations: list[dict[str, Any]] = Field(
        default_factory=list, description="Evaluations from state"
    )
    answers: list[dict[str, Any]] = Field(
        default_factory=list, description="Answers from state"
    )

    model_config = {"extra": "forbid"}


class ValidateGapsOutput(BaseModel):
    """Output from ValidateGapsUseCase.

    Contains validated/merged gaps list.
    """

    cumulative_gaps: list[str] = Field(
        default_factory=list, description="Validated cumulative gaps"
    )
    gaps_mismatch_count: int = Field(
        default=0, description="Number of gaps missing from state"
    )

    model_config = {"extra": "forbid"}
