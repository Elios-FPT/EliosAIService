"""DTOs for GenerateQuestionsBatchUseCase.

Maps state access from PlanningWorkflow._generate_batch_node.
"""

from typing import Any

from pydantic import BaseModel, Field


class GenerateQuestionsBatchInput(BaseModel):
    """Input for GenerateQuestionsBatchUseCase.

    Contains question specs and CV context for batch generation.
    """

    question_specs: list[dict[str, Any]] = Field(
        default_factory=list, description="Question specifications"
    )
    cv_analysis: dict[str, Any] | None = Field(
        default=None, description="CV analysis for context"
    )

    model_config = {"extra": "forbid"}


class GenerateQuestionsBatchOutput(BaseModel):
    """Output from GenerateQuestionsBatchUseCase.

    Contains generated questions, ideal answers, and rationales.
    """

    generated_questions: list[str] = Field(
        default_factory=list, description="Generated question texts"
    )
    generated_answers: list[str] = Field(
        default_factory=list, description="Generated ideal answers"
    )
    generated_rationales: list[str] = Field(
        default_factory=list, description="Generated rationales"
    )
    errors: list[str] = Field(default_factory=list, description="Any errors encountered")

    model_config = {"extra": "forbid"}
