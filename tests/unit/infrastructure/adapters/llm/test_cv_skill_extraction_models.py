"""Unit tests for CV skill extraction models."""

import pytest
from pydantic import ValidationError

from src.infrastructure.adapters.llm.cv_skill_extraction_models import (
    CVSkillExtractionOutput,
    SkillOutput,
    ProficiencyLevelOutput,
)


class TestSkillOutput:
    """Tests for SkillOutput model."""

    def test_valid_skill(self):
        skill = SkillOutput(
            skill_name="Python",
            proficiency_level=ProficiencyLevelOutput.ADVANCED,
            years_of_experience=5.0,
            is_primary=True,
        )
        assert skill.skill_name == "Python"
        assert skill.proficiency_level == ProficiencyLevelOutput.ADVANCED
        assert skill.years_of_experience == 5.0
        assert skill.is_primary is True

    def test_default_values(self):
        skill = SkillOutput(skill_name="FastAPI")
        assert skill.proficiency_level == ProficiencyLevelOutput.INTERMEDIATE
        assert skill.years_of_experience is None
        assert skill.is_primary is False

    def test_skill_name_max_length(self):
        with pytest.raises(ValidationError):
            SkillOutput(skill_name="x" * 101)  # Exceeds 100 chars

    def test_years_of_experience_range(self):
        # Valid range
        skill = SkillOutput(skill_name="Python", years_of_experience=0)
        assert skill.years_of_experience == 0

        skill = SkillOutput(skill_name="Python", years_of_experience=50)
        assert skill.years_of_experience == 50

        # Invalid: negative
        with pytest.raises(ValidationError):
            SkillOutput(skill_name="Python", years_of_experience=-1)

        # Invalid: >50
        with pytest.raises(ValidationError):
            SkillOutput(skill_name="Python", years_of_experience=51)


class TestCVSkillExtractionOutput:
    """Tests for CVSkillExtractionOutput model."""

    def test_valid_output(self):
        output = CVSkillExtractionOutput(
            skills=[
                SkillOutput(skill_name="Python", is_primary=True),
                SkillOutput(skill_name="FastAPI", is_primary=True),
            ],
            summary="Backend developer with Python expertise.",
        )
        assert len(output.skills) == 2
        assert output.summary == "Backend developer with Python expertise."

    def test_empty_skills_allowed(self):
        output = CVSkillExtractionOutput(
            skills=[],
            summary="No technical skills identified.",
        )
        assert len(output.skills) == 0

    def test_max_skills_limit(self):
        # 30 skills is OK
        skills = [SkillOutput(skill_name=f"Skill{i}") for i in range(30)]
        output = CVSkillExtractionOutput(skills=skills, summary="Many skills.")
        assert len(output.skills) == 30

        # 31 skills should fail
        skills = [SkillOutput(skill_name=f"Skill{i}") for i in range(31)]
        with pytest.raises(ValidationError):
            CVSkillExtractionOutput(skills=skills, summary="Too many skills.")

    def test_summary_length_constraints(self):
        # Too short
        with pytest.raises(ValidationError):
            CVSkillExtractionOutput(skills=[], summary="short")

        # Valid length
        output = CVSkillExtractionOutput(
            skills=[],
            summary="This is a valid summary with enough characters.",
        )
        assert len(output.summary) >= 10
