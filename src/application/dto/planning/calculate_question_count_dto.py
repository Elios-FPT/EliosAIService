"""DTOs for CalculateQuestionCountUseCase.

Maps state access from PlanningWorkflow._calculate_count_node.
"""

from typing import Any

from pydantic import BaseModel, Field


class CalculateQuestionCountInput(BaseModel):
    """Input for CalculateQuestionCountUseCase.

    Contains CV analysis for calculating question count.
    """

    cv_analysis: dict[str, Any] | None = Field(
        default=None, description="CV analysis dict"
    )
    skills_count: int = Field(default=0, description="Number of unique skills")

    model_config = {"extra": "forbid"}


class CalculateQuestionCountOutput(BaseModel):
    """Output from CalculateQuestionCountUseCase.

    Contains calculated question count.
    """

    question_count: int = Field(
        description="Number of questions to generate (min 2, max 5)"
    )
    errors: list[str] = Field(default_factory=list, description="Any errors encountered")

    model_config = {"extra": "forbid"}
