"""DTOs for LoadNextQuestionUseCase.

Maps state access from InterviewConversationWorkflow._next_question_or_complete_node.
"""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class LoadNextQuestionInput(BaseModel):
    """Input for LoadNextQuestionUseCase.

    Contains interview ID and current question state.
    """

    interview_id: UUID = Field(description="Interview UUID")
    has_more_questions: bool = Field(
        default=False, description="Whether more questions exist"
    )
    cached_interview: dict[str, Any] | None = Field(
        default=None, description="Cached interview for performance"
    )

    model_config = {"extra": "forbid"}


class LoadNextQuestionOutput(BaseModel):
    """Output from LoadNextQuestionUseCase.

    Contains next question or completion flag.
    """

    complete: bool = Field(default=False, description="Whether interview is complete")
    current_question_id: str | None = Field(
        default=None, description="Next question ID"
    )
    current_question: dict[str, Any] | None = Field(
        default=None, description="Next question with metadata"
    )
    parent_question_id: None = Field(
        default=None, description="Reset to None for new main question"
    )
    parent_question: None = Field(
        default=None, description="Reset to None for new main question"
    )
    followup_count: int = Field(default=0, description="Reset to 0 for new question")
    cumulative_gaps: list[str] = Field(
        default_factory=list, description="Reset to empty for new question"
    )
    has_more_questions: bool = Field(
        default=False, description="Updated has_more flag"
    )
    cache_updates: dict[str, Any] = Field(
        default_factory=dict, description="Interview cache updates"
    )
    errors: list[str] = Field(default_factory=list, description="Any errors encountered")

    model_config = {"extra": "forbid"}
