"""DTOs for StoreQuestionsUseCase.

Maps state access from PlanningWorkflow._store_questions_node.
"""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class StoreQuestionsInput(BaseModel):
    """Input for StoreQuestionsUseCase.

    Contains generated content for storing as Question entities.
    """

    generated_questions: list[str] = Field(
        default_factory=list, description="Question texts"
    )
    generated_answers: list[str] = Field(
        default_factory=list, description="Ideal answer texts"
    )
    generated_rationales: list[str] = Field(
        default_factory=list, description="Rationale texts"
    )
    question_specs: list[dict[str, Any]] = Field(
        default_factory=list, description="Question specifications with skill/difficulty"
    )

    model_config = {"extra": "forbid"}


class StoreQuestionsOutput(BaseModel):
    """Output from StoreQuestionsUseCase.

    Contains IDs of stored questions.
    """

    stored_question_ids: list[UUID] = Field(
        default_factory=list, description="UUIDs of stored questions"
    )
    errors: list[str] = Field(default_factory=list, description="Any errors encountered")

    model_config = {"extra": "forbid"}
