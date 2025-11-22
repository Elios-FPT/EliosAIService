"""Domain model for CV skill."""
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4
from datetime import datetime
from pydantic import BaseModel, Field, field_validator


class ProficiencyLevel(str, Enum):
    """Skill proficiency levels matching DB ENUM."""
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


class CVSkill(BaseModel):
    """
    Represents a skill extracted from a CV.

    Normalized from cv_analyses.skills JSONB to dedicated table.
    """

    id: UUID = Field(default_factory=uuid4)
    cv_analysis_id: UUID
    skill_name: str = Field(min_length=1, max_length=100)
    proficiency_level: Optional[ProficiencyLevel] = ProficiencyLevel.INTERMEDIATE
    years_of_experience: Optional[float] = Field(default=None, ge=0, le=50)
    is_primary: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)

    @field_validator('skill_name')
    @classmethod
    def validate_skill_name(cls, v: str) -> str:
        """Normalize skill name (strip whitespace, title case)."""
        normalized = v.strip()
        if not normalized:
            raise ValueError("skill_name cannot be empty")
        return normalized

    def __str__(self) -> str:
        """String representation for logging."""
        prof = self.proficiency_level.value if self.proficiency_level else "unknown"
        return f"CVSkill({self.skill_name}, {prof})"

    def __repr__(self) -> str:
        """Developer-friendly representation."""
        prof = self.proficiency_level.value if self.proficiency_level else None
        return (
            f"CVSkill(id={self.id}, skill_name='{self.skill_name}', "
            f"proficiency={prof}, "
            f"years={self.years_of_experience}, is_primary={self.is_primary})"
        )

    class Config:
        """Pydantic configuration."""

        pass