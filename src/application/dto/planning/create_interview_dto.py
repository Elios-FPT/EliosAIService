"""DTOs for CreateInterviewUseCase.

Maps state access from PlanningWorkflow._update_interview_node.
"""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class CreateInterviewInput(BaseModel):
    """Input for CreateInterviewUseCase.

    Contains data needed to create an interview with questions.
    """

    candidate_id: UUID = Field(description="Candidate UUID")
    cv_analysis_id: UUID = Field(description="CV analysis UUID")
    stored_question_ids: list[UUID] = Field(
        default_factory=list, description="Question UUIDs to attach"
    )
    question_specs: list[dict[str, Any]] = Field(
        default_factory=list, description="Question specs for title generation"
    )

    model_config = {"extra": "forbid"}


class CreateInterviewOutput(BaseModel):
    """Output from CreateInterviewUseCase.

    Contains created interview entity.
    """

    interview: dict[str, Any] = Field(
        description="Created interview (Interview.model_dump)"
    )
    errors: list[str] = Field(default_factory=list, description="Any errors encountered")

    model_config = {"extra": "forbid"}
