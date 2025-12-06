"""DTOs for LoadCVAnalysisUseCase.

Maps state access from PlanningWorkflow._load_cv_node.
"""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class LoadCVAnalysisInput(BaseModel):
    """Input for LoadCVAnalysisUseCase.

    Contains CV analysis ID to load.
    """

    cv_analysis_id: UUID = Field(description="CV analysis UUID to load")

    model_config = {"extra": "forbid"}


class LoadCVAnalysisOutput(BaseModel):
    """Output from LoadCVAnalysisUseCase.

    Contains loaded CV analysis data.
    """

    cv_analysis: dict[str, Any] = Field(
        description="CV analysis (CVAnalysis.model_dump)"
    )
    skills: list[str] = Field(description="Extracted skill names")
    errors: list[str] = Field(default_factory=list, description="Any errors encountered")

    model_config = {"extra": "forbid"}
