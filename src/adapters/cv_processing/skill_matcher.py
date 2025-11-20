"""Skill matching using spaCy PhraseMatcher and skill gazetteer.

This module provides skill extraction using a categorized skill gazetteer
loaded from skill_patterns.json.
"""

import json
import os
from typing import TYPE_CHECKING

import spacy
from spacy.matcher import PhraseMatcher

from ...domain.models.cv_analysis import ExtractedSkill

if TYPE_CHECKING:
    from spacy.language import Language
    from spacy.tokens import Doc


class SkillMatcher:
    """Match skills using spaCy PhraseMatcher and skill gazetteer.

    Uses skill_patterns.json with categorized skills:
    - programming_languages
    - frameworks
    - databases
    - tools
    - soft_skills
    - cloud_platforms
    - data_science
    - methodologies
    - security
    - mobile
    - testing
    - web_technologies
    - version_control
    - vietnamese
    """

    def __init__(self) -> None:
        """Initialize matcher with skill patterns."""
        self.skill_patterns = self._load_patterns()
        self.phrase_matcher: PhraseMatcher | None = None  # Lazy init per language
        self._category_lookup: dict[str, str] = {}  # skill_lower -> category
        self._nlp: "Language | None" = None  # Store nlp reference for pattern creation

    def _load_patterns(self) -> dict[str, list[str]]:
        """Load skill patterns from JSON file.

        Returns:
            Dictionary mapping category names to skill lists
        """
        pattern_file = os.path.join(os.path.dirname(__file__), "skill_patterns.json")
        with open(pattern_file, encoding="utf-8") as f:
            return json.load(f)

    def initialize_matcher(self, nlp: "Language") -> None:
        """Initialize PhraseMatcher with nlp model.

        Args:
            nlp: spaCy language model
        """
        if self.phrase_matcher is None:
            self._nlp = nlp
            self.phrase_matcher = self._build_phrase_matcher(nlp)

    def match_skills(
        self, doc: "Doc", nlp: "Language | None" = None
    ) -> list[ExtractedSkill]:
        """Match skills in spaCy doc using PhraseMatcher.

        Args:
            doc: spaCy processed document
            nlp: Optional spaCy language model (required for first call)

        Returns:
            List of ExtractedSkill objects with categories
        """
        # Lazy init PhraseMatcher
        if self.phrase_matcher is None:
            if nlp is None:
                raise ValueError("nlp parameter required for first call to match_skills")
            self.initialize_matcher(nlp)

        # Find matches
        matches = self.phrase_matcher(doc)

        # Convert to ExtractedSkill objects
        skills = []
        seen_skills = set()  # Deduplicate

        for _match_id, start, end in matches:
            skill_text = doc[start:end].text
            skill_lower = skill_text.lower()

            if skill_lower not in seen_skills:
                seen_skills.add(skill_lower)
                category = self._categorize_skill(skill_lower)
                skills.append(
                    ExtractedSkill(
                        skill=skill_text,
                        category=category,
                        proficiency=None,  # TODO: Infer from context in Phase 3
                        years=None,
                    )
                )

        return skills

    def _build_phrase_matcher(self, nlp: spacy.Language) -> PhraseMatcher:
        """Build PhraseMatcher with all skill patterns.

        Args:
            nlp: spaCy language model for creating docs

        Returns:
            Configured PhraseMatcher instance
        """
        matcher = PhraseMatcher(nlp.vocab, attr="LOWER")  # Case-insensitive

        # Add all skills from all categories
        all_skills = []
        for category, skills in self.skill_patterns.items():
            for skill in skills:
                skill_lower = skill.lower()
                # Build category lookup
                self._category_lookup[skill_lower] = category
                all_skills.append(skill)

        # Convert to spaCy patterns using nlp
        patterns = [nlp.make_doc(skill) for skill in all_skills]
        matcher.add("SKILL", patterns)

        return matcher

    def _categorize_skill(self, skill: str) -> str:
        """Categorize skill based on patterns.

        Args:
            skill: Skill name (lowercase)

        Returns:
            Category name, or "technical" if not found
        """
        return self._category_lookup.get(skill.lower(), "technical")
