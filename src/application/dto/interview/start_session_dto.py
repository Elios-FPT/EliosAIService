"""DTOs for StartInterviewSessionUseCase.

Maps state access from InterviewConversationWorkflow._start_session_node.
"""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class StartSessionInput(BaseModel):
    """Input for StartInterviewSessionUseCase.

    Contains interview and candidate IDs to start a session.
    """

    interview_id: UUID = Field(description="Interview UUID")
    candidate_id: UUID = Field(description="Candidate UUID")
    cached_interview: dict[str, Any] | None = Field(
        default=None, description="Cached interview for performance"
    )

    model_config = {"extra": "forbid"}


class StartSessionOutput(BaseModel):
    """Output from StartInterviewSessionUseCase.

    Contains first question and initial conversation state.
    """

    current_question_id: str = Field(description="First question ID as string")
    current_question: dict[str, Any] = Field(
        description="First question with index/total metadata"
    )
    has_more_questions: bool = Field(description="Whether more questions exist")
    cache_updates: dict[str, Any] = Field(
        default_factory=dict, description="Interview cache updates to merge into state"
    )
    errors: list[str] = Field(default_factory=list, description="Any errors encountered")
    complete: bool = Field(default=False, description="Whether interview is complete")

    model_config = {"extra": "forbid"}
