"""Unit tests for SkillMatcher."""

import pytest
import spacy
from src.adapters.cv_processing.skill_matcher import SkillMatcher


class TestSkillMatcher:
    """Test suite for SkillMatcher class."""

    @pytest.fixture(scope="class")
    def nlp(self):
        """Load spaCy English model once for all tests."""
        try:
            return spacy.load("en_core_web_sm", exclude=["parser", "lemmatizer"])
        except OSError:
            pytest.skip("spaCy English model not installed")

    @pytest.fixture
    def matcher(self):
        """Create matcher instance."""
        return SkillMatcher()

    def test_load_patterns_success(self, matcher):
        """Test that skill patterns load successfully."""
        patterns = matcher.skill_patterns

        assert isinstance(patterns, dict)
        assert len(patterns) > 0
        assert "programming_languages" in patterns
        assert "frameworks" in patterns
        assert "databases" in patterns
        assert "tools" in patterns

    def test_match_skills_programming_languages(self, matcher, nlp):
        """Test matching programming language skills."""
        text = "I have experience with Python, Java, and JavaScript."
        doc = nlp(text)

        skills = matcher.match_skills(doc, nlp)

        assert len(skills) >= 3
        skill_names = [s.skill for s in skills]
        assert any("Python" in name for name in skill_names)
        assert any("Java" in name for name in skill_names)
        assert any("JavaScript" in name for name in skill_names)

    def test_match_skills_frameworks(self, matcher, nlp):
        """Test matching framework skills."""
        text = "Proficient in React, FastAPI, and Django frameworks."
        doc = nlp(text)

        skills = matcher.match_skills(doc, nlp)

        assert len(skills) >= 3
        skill_names = [s.skill for s in skills]
        assert any("React" in name for name in skill_names)
        assert any("FastAPI" in name for name in skill_names)
        assert any("Django" in name for name in skill_names)

    def test_match_skills_databases(self, matcher, nlp):
        """Test matching database skills."""
        text = "Experience with PostgreSQL, MongoDB, and Redis databases."
        doc = nlp(text)

        skills = matcher.match_skills(doc, nlp)

        assert len(skills) >= 3
        skill_names = [s.skill for s in skills]
        assert any("PostgreSQL" in name for name in skill_names)
        assert any("MongoDB" in name for name in skill_names)
        assert any("Redis" in name for name in skill_names)

    def test_categorize_skill_programming_language(self, matcher, nlp):
        """Test that Python is categorized as programming_languages."""
        text = "I know Python programming."
        doc = nlp(text)

        skills = matcher.match_skills(doc, nlp)

        python_skill = next((s for s in skills if "Python" in s.skill), None)
        assert python_skill is not None
        assert python_skill.category == "programming_languages"

    def test_categorize_skill_framework(self, matcher, nlp):
        """Test that React is categorized as frameworks."""
        text = "I use React for frontend development."
        doc = nlp(text)

        skills = matcher.match_skills(doc, nlp)

        react_skill = next((s for s in skills if "React" in s.skill), None)
        assert react_skill is not None
        assert react_skill.category == "frameworks"

    def test_match_skills_deduplication(self, matcher, nlp):
        """Test that duplicate skills are deduplicated."""
        text = "Python Python Python Python"
        doc = nlp(text)

        skills = matcher.match_skills(doc, nlp)

        # Should only match Python once despite multiple occurrences
        python_skills = [s for s in skills if "Python" in s.skill]
        assert len(python_skills) == 1

    def test_match_skills_case_insensitive(self, matcher, nlp):
        """Test that matching is case-insensitive."""
        text = "I know python, PYTHON, and PyThOn."
        doc = nlp(text)

        skills = matcher.match_skills(doc, nlp)

        # Should match Python regardless of case, but deduplicate
        python_skills = [s for s in skills if "python" in s.skill.lower()]
        assert len(python_skills) == 1

    def test_match_skills_empty_text(self, matcher, nlp):
        """Test matching on empty text."""
        text = ""
        doc = nlp(text)

        skills = matcher.match_skills(doc, nlp)

        assert skills == []

    def test_match_skills_no_skills(self, matcher, nlp):
        """Test text with no recognizable skills."""
        text = "I like to read books and watch movies in my free time."
        doc = nlp(text)

        skills = matcher.match_skills(doc, nlp)

        # Should return empty list or minimal matches
        assert len(skills) == 0

    def test_match_skills_multiple_categories(self, matcher, nlp):
        """Test matching skills from multiple categories."""
        text = """
        Skills: Python, JavaScript, React, Django, PostgreSQL, Docker, AWS,
        Agile, Scrum, Leadership, Communication, Problem Solving
        """
        doc = nlp(text)

        skills = matcher.match_skills(doc, nlp)

        # Should have skills from different categories
        categories = {s.category for s in skills}
        assert len(categories) >= 4  # programming_languages, frameworks, databases, tools, soft_skills

    def test_extracted_skill_attributes(self, matcher, nlp):
        """Test that ExtractedSkill objects have correct attributes."""
        text = "I know Python programming."
        doc = nlp(text)

        skills = matcher.match_skills(doc, nlp)

        assert len(skills) > 0
        skill = skills[0]
        assert hasattr(skill, "skill")
        assert hasattr(skill, "category")
        assert hasattr(skill, "proficiency")
        assert hasattr(skill, "years")
        assert skill.proficiency is None  # Not implemented in Phase 2
        assert skill.years is None  # Not implemented in Phase 2
