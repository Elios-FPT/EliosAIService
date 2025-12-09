"""DTOs for PrepareQuestionSpecsUseCase.

Maps state access from PlanningWorkflow._prepare_specs_node.
"""

from typing import Any

from pydantic import BaseModel, Field


class QuestionSpec(BaseModel):
    """Specification for a single question to generate."""

    skill: str = Field(description="Target skill for the question")
    difficulty: str = Field(description="Difficulty level (easy, medium, hard)")
    exemplars: list[dict[str, Any]] = Field(
        default_factory=list, description="Similar example questions from vector search"
    )

    model_config = {"extra": "forbid"}


class PrepareQuestionSpecsInput(BaseModel):
    """Input for PrepareQuestionSpecsUseCase.

    Contains CV analysis and question count for spec preparation.
    """

    cv_analysis: dict[str, Any] | None = Field(
        default=None, description="CV analysis dict"
    )
    question_count: int = Field(default=0, description="Number of questions to prepare")

    model_config = {"extra": "forbid"}


class PrepareQuestionSpecsOutput(BaseModel):
    """Output from PrepareQuestionSpecsUseCase.

    Contains prepared question specifications.
    """

    question_specs: list[QuestionSpec] = Field(
        default_factory=list, description="Question specifications"
    )
    errors: list[str] = Field(default_factory=list, description="Any errors encountered")

    model_config = {"extra": "forbid"}
