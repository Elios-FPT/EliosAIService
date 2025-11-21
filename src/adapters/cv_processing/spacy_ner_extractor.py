"""Named Entity Recognition extractor using spaCy.

This module provides entity extraction from CV text using spaCy's pre-trained
NER models and custom skill matching.
"""

from __future__ import annotations

import re
from typing import Any

import spacy

from ...domain.models.cv_analysis import ExtractedSkill
from .confidence_scorer import ConfidenceScorer
from .skill_matcher import SkillMatcher


class SpacyNERExtractor:
    """Extract entities from CV text using spaCy NER.

    Supports English (en_core_web_sm) and Vietnamese (vi_core_news_sm) models
    with lazy loading. Uses PhraseMatcher for skill extraction (gazetteer-based).
    """

    SUPPORTED_LANGUAGES = ("en", "vi")

    def __init__(self) -> None:
        """Initialize extractor with lazy model loading."""
        self._nlp_en: spacy.Language | None = None
        self._nlp_vi: spacy.Language | None = None
        self.skill_matcher = SkillMatcher()
        self.confidence_scorer = ConfidenceScorer()

    @property
    def nlp_en(self) -> spacy.Language:
        """Lazy load English model (singleton)."""
        if self._nlp_en is None:
            self._nlp_en = self._load_model("en_core_web_sm")
        return self._nlp_en

    @property
    def nlp_vi(self) -> spacy.Language | None:
        """Lazy load Vietnamese model (singleton) if available."""
        if self._nlp_vi is None:
            try:
                self._nlp_vi = self._load_model("vi_core_news_sm")
            except RuntimeError:
                # Keep None so callers can gracefully fallback to English model
                self._nlp_vi = None
        return self._nlp_vi

    def _load_model(self, model_name: str) -> spacy.Language:
        """Load spaCy model with parser/lemmatizer disabled for speed."""
        try:
            return spacy.load(model_name, exclude=["parser", "lemmatizer"])
        except OSError:
            raise RuntimeError(
                f"spaCy model '{model_name}' not found. "
                f"Install via: python -m spacy download {model_name}"
            ) from None

    def extract(self, cv_text: str, language: str = "auto") -> dict[str, Any]:
        """Extract entities and skills from CV text.

        Args:
            cv_text: Full CV text content
            language: "en", "vi", or "auto" (auto-detect)

        Returns:
            {
                "name": str | None,
                "companies": list[str],
                "locations": list[str],
                "dates": list[str],  # Supplements Phase 1 regex
                "skills": list[ExtractedSkill],
                "experience_years": float | None,
                "confidence": dict[str, float]
            }
        """
        # Detect language if auto
        if language == "auto":
            language = self._detect_language(cv_text)

        language = language if language in self.SUPPORTED_LANGUAGES else "en"
        nlp = self._select_model(language)
        language_used = language if nlp is not None else "en"
        if nlp is None:
            # Fallback to English if requested model unavailable
            nlp = self.nlp_en

        # Process text
        doc = nlp(cv_text)

        # Extract entities
        entities = self._extract_entities(doc)

        # Extract skills (PhraseMatcher)
        skills = self._extract_skills(doc)

        # Calculate experience from dates
        experience_years = self._calculate_experience(entities["dates"])

        # Calculate confidence scores
        confidence_scores = {
            "name": self.confidence_scorer.score_field(
                "name", [entities["name"]], bool(entities["name"])
            ),
            "companies": self.confidence_scorer.score_field(
                "companies", entities["companies"], True
            ),
            "locations": self.confidence_scorer.score_field(
                "locations", entities["locations"], True
            ),
            "skills": self.confidence_scorer.score_field("skills", [s.skill for s in skills], True),
        }

        # Aggregate confidence
        overall_confidence = self.confidence_scorer.aggregate_confidence(
            confidence_scores, critical_fields=["name", "skills"]
        )

        return {
            "name": entities["name"],
            "companies": entities["companies"],
            "locations": entities["locations"],
            "dates": entities["dates"],
            "skills": skills,
            "experience_years": experience_years,
            "confidence": {
                "fields": confidence_scores,
                "overall": overall_confidence,
            },
            "language": language_used,
        }

    def _detect_language(self, text: str) -> str:
        """Auto-detect CV language (en or vi).

        Heuristic: Check for Vietnamese characters (Ă, Ơ, Ư, etc.)

        Args:
            text: CV text content

        Returns:
            "en" for English, "vi" for Vietnamese
        """
        # Vietnamese characters including all diacritics (lowercase)
        vietnamese_chars = "àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ"
        vietnamese_count = sum(1 for char in text.lower() if char in vietnamese_chars)

        # Threshold: > 5 Vietnamese chars → Vietnamese (more sensitive)
        return "vi" if vietnamese_count > 5 else "en"

    def _select_model(self, language: str) -> spacy.Language | None:
        """Return model matching requested language if available."""
        if language == "vi":
            return self.nlp_vi
        return self.nlp_en

    def _extract_entities(self, doc: spacy.tokens.Doc) -> dict[str, Any]:
        """Extract named entities from spaCy doc.

        Entity mapping:
        - PERSON → name (first occurrence)
        - ORG → companies
        - GPE, LOC → locations
        - DATE → dates

        Args:
            doc: Processed spaCy document

        Returns:
            Dictionary with extracted entities
        """
        name = None
        companies = []
        locations = []
        dates = []

        for ent in doc.ents:
            if ent.label_ == "PERSON" and name is None:
                name = ent.text
            elif ent.label_ == "ORG":
                companies.append(ent.text)
            elif ent.label_ in ["GPE", "LOC"]:
                locations.append(ent.text)
            elif ent.label_ == "DATE":
                dates.append(ent.text)

        return {
            "name": name,
            "companies": list(set(companies)),  # Deduplicate
            "locations": list(set(locations)),
            "dates": dates,
        }

    def _extract_skills(self, doc: spacy.tokens.Doc) -> list[ExtractedSkill]:
        """Extract skills using PhraseMatcher.

        Args:
            doc: Processed spaCy document

        Returns:
            List of ExtractedSkill objects
        """
        return self.skill_matcher.match_skills(doc, self.nlp_en)

    def _calculate_experience(self, dates: list[str]) -> float | None:
        """Calculate total work experience from extracted dates.

        Logic:
        - Find earliest and latest dates
        - Calculate difference in years
        - Fallback: None if insufficient data

        Args:
            dates: List of date strings extracted from CV

        Returns:
            Experience in years, or None if cannot calculate
        """
        if len(dates) < 2:
            return None

        # Parse dates (simplified - extract 4-digit years)
        years = []
        for date_str in dates:
            # Extract 4-digit year
            match = re.search(r"\b(19|20)\d{2}\b", date_str)
            if match:
                years.append(int(match.group()))

        if len(years) < 2:
            return None

        # Experience = latest year - earliest year
        return float(max(years) - min(years))
