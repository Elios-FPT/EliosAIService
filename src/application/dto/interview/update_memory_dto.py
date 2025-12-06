"""DTOs for UpdateConversationMemoryUseCase.

Maps state access from InterviewConversationWorkflow._update_memory_node.
"""

from typing import Any

from pydantic import BaseModel, Field


class UpdateMemoryInput(BaseModel):
    """Input for UpdateConversationMemoryUseCase.

    Contains current messages and latest Q&A to append.
    """

    messages: list[dict[str, Any]] = Field(
        default_factory=list, description="Current conversation messages"
    )
    current_question_id: str | None = Field(
        default=None, description="Current question ID"
    )
    current_question: dict[str, Any] | None = Field(
        default=None, description="Current question dict"
    )
    latest_answer: dict[str, Any] | None = Field(
        default=None, description="Latest answer dict"
    )
    latest_evaluation: dict[str, Any] | None = Field(
        default=None, description="Latest evaluation dict"
    )

    model_config = {"extra": "forbid"}


class UpdateMemoryOutput(BaseModel):
    """Output from UpdateConversationMemoryUseCase.

    Contains updated (truncated) messages list.
    """

    messages: list[dict[str, Any]] = Field(
        description="Updated conversation messages (truncated to max 10)"
    )
    truncated: bool = Field(
        default=False, description="Whether messages were truncated"
    )
    errors: list[str] = Field(default_factory=list, description="Any errors encountered")

    model_config = {"extra": "forbid"}
