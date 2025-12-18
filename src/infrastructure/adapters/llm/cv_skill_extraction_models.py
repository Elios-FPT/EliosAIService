"""Pydantic models for CV skill extraction LLM output.

Used with LangChain's with_structured_output() for type-safe extraction.
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ProficiencyLevelOutput(str, Enum):
    """Proficiency level for structured output.

    Must match src.domain.models.cv_skill.ProficiencyLevel values.
    """
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


class SkillOutput(BaseModel):
    """Single skill extracted from CV.

    Attributes:
        skill_name: Technical skill name (e.g., "Python", "FastAPI")
        proficiency_level: Inferred proficiency based on CV context
        years_of_experience: Estimated years from job durations/complexity
        is_primary: True for top 3-5 core skills
    """
    skill_name: str = Field(
        max_length=100,
        description="Technical skill name (language, framework, tool, methodology)"
    )
    proficiency_level: ProficiencyLevelOutput = Field(
        default=ProficiencyLevelOutput.INTERMEDIATE,
        description="Inferred proficiency: beginner/intermediate/advanced/expert"
    )
    years_of_experience: Optional[float] = Field(
        default=None,
        ge=0,
        le=50,
        description="Estimated years of experience with this skill"
    )
    is_primary: bool = Field(
        default=False,
        description="True if this is a core/primary skill (mark top 3-5)"
    )


class CVSkillExtractionOutput(BaseModel):
    """CV skill extraction output from LLM.

    Used as structured_output_model in LangChainAdapter.analyze_cv_for_skills().

    Attributes:
        skills: List of extracted technical skills (max 30 to prevent hallucination)
        summary: 2-3 sentence skill-focused summary (no personal info)
    """
    skills: list[SkillOutput] = Field(
        default_factory=list,
        max_length=30,
        description="Extracted technical skills (max 30)"
    )
    summary: str = Field(
        min_length=10,
        max_length=500,
        description="2-3 sentence skill-focused summary (no personal info like name, email, location)"
    )
