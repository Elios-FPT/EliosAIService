"""CV Analysis domain model."""

from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from .cv_skill import CVSkill, ProficiencyLevel


class CVAnalysis(BaseModel):
    """Represents the analysis results of a candidate's CV.

    This is an entity in the interview domain.
    """

    id: UUID = Field(default_factory=uuid4)
    candidate_id: UUID
    extracted_text: str
    skills: List[CVSkill] = Field(default_factory=list)
    work_experience_years: float | None = None
    education_level: str | None = None  # e.g., "Bachelor's", "Master's"
    suggested_topics: list[str] = Field(default_factory=list)  # Topics to cover
    suggested_difficulty: str = "medium"  # Overall difficulty level
    embedding: Optional[List[float]] = None  # Vector embedding of CV
    summary: Optional[str] = None  # AI-generated summary
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


    class Config:
        """Pydantic configuration."""
        frozen = False

    def add_skill(
        self,
        skill_name: str,
        proficiency_level: Optional[ProficiencyLevel] = None,
        years_of_experience: Optional[float] = None,
        is_primary: bool = False
    ) -> CVSkill:
        """
        Add a skill to this CV analysis.

        Args:
            skill_name: Name of the skill (e.g., "Python", "Leadership")
            proficiency_level: Skill proficiency (default: INTERMEDIATE)
            years_of_experience: Years of experience with skill
            is_primary: Whether this is a primary/core skill

        Returns:
            The created CVSkill instance
        """
        skill = CVSkill(
            cv_analysis_id=self.id,
            skill_name=skill_name,
            proficiency_level=proficiency_level or ProficiencyLevel.INTERMEDIATE,
            years_of_experience=years_of_experience,
            is_primary=is_primary
        )
        self.skills.append(skill)
        return skill

    def get_primary_skills(self) -> List[CVSkill]:
        """Get all primary skills."""
        return [skill for skill in self.skills if skill.is_primary]

    def get_skills_by_proficiency(self, level: ProficiencyLevel) -> List[CVSkill]:
        """Get skills filtered by proficiency level."""
        return [skill for skill in self.skills if skill.proficiency_level == level]

    def has_skill(self, skill_name: str) -> bool:
        """Check if a specific skill was found in CV.

        Args:
            skill_name: Name of skill to check

        Returns:
            True if skill exists, False otherwise
        """
        return any(
            skill.skill_name.lower() == skill_name.lower()
            for skill in self.skills
        )

    def get_skill_by_name(self, skill_name: str) -> CVSkill | None:
        """Get a skill by name.

        Args:
            skill_name: Name of skill to find

        Returns:
            CVSkill if found, None otherwise
        """
        for skill in self.skills:
            if skill.skill_name.lower() == skill_name.lower():
                return skill
        return None

    def get_top_skills(self, limit: int = 5) -> List[CVSkill]:
        """Get top skills (primary first, then by name).

        Args:
            limit: Maximum number of skills to return

        Returns:
            List of top skills
        """
        sorted_skills = sorted(
            self.skills,
            key=lambda s: (not s.is_primary, s.skill_name)
        )
        return sorted_skills[:limit]

    def is_experienced(self, min_years: float = 3.0) -> bool:
        """Check if candidate is experienced.

        Args:
            min_years: Minimum years of experience

        Returns:
            True if experienced, False otherwise
        """
        return (
            self.work_experience_years is not None
            and self.work_experience_years >= min_years
        )
