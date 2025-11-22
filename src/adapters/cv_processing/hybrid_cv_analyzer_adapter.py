"""Hybrid CV analyzer orchestrator coordinating rules, NER, and LLM fallback."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import pdfplumber
from docx import Document

from ...domain.models.candidate import Candidate
from ...domain.models.cv_analysis import CVAnalysis
from ...domain.models.cv_skill import CVSkill, ProficiencyLevel
from ...domain.ports.cv_analyzer_port import CVAnalyzerPort
from .confidence_scorer import ConfidenceScorer
from .llm_fallback_extractor import (
    LLMFallbackExtractor,
    LLMFallbackExtractorProtocol,
    NoOpLLMFallbackExtractor,
)
from .rule_based_extractor import RuleBasedExtractor
from .spacy_ner_extractor import SpacyNERExtractor


class HybridCVAnalyzerAdapter(CVAnalyzerPort):
    """Hybrid analyzer implementing CVAnalyzerPort with multi-layer extraction."""

    def __init__(
        self,
        *,
        confidence_threshold: float = 0.7,
        use_llm_fallback: bool = True,
        rule_extractor: RuleBasedExtractor | None = None,
        ner_extractor: SpacyNERExtractor | None = None,
        confidence_scorer: ConfidenceScorer | None = None,
        llm_fallback: LLMFallbackExtractorProtocol | None = None,
    ) -> None:
        self.rule_extractor = rule_extractor or RuleBasedExtractor()
        self.ner_extractor = ner_extractor or SpacyNERExtractor()
        self.confidence_scorer = confidence_scorer or ConfidenceScorer()
        # Default to real LLM fallback if not provided (Phase 4)
        if llm_fallback is None:
            try:
                self.llm_fallback = LLMFallbackExtractor()
            except Exception:
                # Fallback to no-op if LLM initialization fails
                self.llm_fallback = NoOpLLMFallbackExtractor()
        else:
            self.llm_fallback = llm_fallback
        self.confidence_threshold = confidence_threshold
        self.use_llm_fallback = use_llm_fallback

    async def analyze_cv(
        self,
        cv_file_path: str,
        candidate_id: UUID,
    ) -> CVAnalysis:
        """Analyze CV contents using rules → NER → optional LLM fallback."""

        cv_text = self._read_cv_text(cv_file_path)

        rule_results = self.rule_extractor.extract(cv_text)
        ner_results = self.ner_extractor.extract(cv_text)
        merged_results = self._merge_results(rule_results, ner_results)

        confidence = self.confidence_scorer.aggregate_confidence(
            merged_results["field_confidences"],
        )
        if (
            confidence < self.confidence_threshold
            and self.use_llm_fallback
            and self.llm_fallback
        ):
            merged_results = await self.llm_fallback.fill_gaps(merged_results, cv_text)

        return self._map_to_cv_analysis(
            merged_results,
            cv_text,
            cv_file_path,
            candidate_id,
        )

    async def generate_candidate_from_summary(
        self,
        summary_info: str,
        cv_file_path: str,
        candidate_id: UUID,
    ) -> Candidate:
        """Generate lightweight Candidate from summary text."""

        ner_results = self.ner_extractor.extract(summary_info)
        rule_results = self.rule_extractor.extract(summary_info)

        overall_conf = ner_results.get("confidence", {}).get("overall", 0.0)
        name = ner_results.get("name")
        if not name or overall_conf < 0.5:
            name = "Unknown Candidate"
        emails = rule_results.get("emails", [])
        email = emails[0] if emails else "no-email@example.com"

        return Candidate(
            id=candidate_id,
            name=name,
            email=email,
            cv_file_path=cv_file_path,
        )

    def _read_cv_text(self, file_path: str) -> str:
        """Read CV text supporting PDF, DOCX, and plaintext formats."""

        path = Path(file_path)
        suffix = path.suffix.lower()

        if suffix == ".pdf":
            return self._read_pdf(path)
        if suffix == ".docx":
            return self._read_docx(path)

        return self._read_text(path)

    def _read_pdf(self, path: Path) -> str:
        with pdfplumber.open(path) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages).strip()

    def _read_docx(self, path: Path) -> str:
        document = Document(path)
        return "\n".join(p.text.strip() for p in document.paragraphs if p.text).strip()

    def _read_text(self, path: Path) -> str:
        return path.read_text(encoding="utf-8", errors="ignore").strip()

    def _merge_results(
        self,
        rule_results: dict[str, Any],
        ner_results: dict[str, Any],
    ) -> dict[str, Any]:
        """Merge rule-based + NER outputs with conflict resolution."""

        merged = {
            "emails": rule_results.get("emails", []),
            "phones": rule_results.get("phones", []),
            "urls": rule_results.get("urls", []),
            "sections": rule_results.get("sections", {}),
            "dates": self._merge_dates(rule_results, ner_results),
            "name": ner_results.get("name"),
            "companies": ner_results.get("companies", []),
            "locations": ner_results.get("locations", []),
            "skills": ner_results.get("skills", []),
            "experience_years": ner_results.get("experience_years"),
            "language": ner_results.get("language", "en"),
        }

        merged["field_confidences"] = self._build_field_confidences(merged, ner_results)
        return merged

    def _merge_dates(
        self,
        rule_results: dict[str, Any],
        ner_results: dict[str, Any],
    ) -> list[str]:
        rule_dates = rule_results.get("dates", [])
        ner_dates = ner_results.get("dates", [])
        return list(dict.fromkeys(rule_dates + ner_dates))

    def _build_field_confidences(
        self,
        merged_results: dict[str, Any],
        ner_results: dict[str, Any],
    ) -> dict[str, float]:
        emails = merged_results["emails"]
        phones = merged_results["phones"]
        sections = merged_results["sections"]
        skills = merged_results["skills"]

        email_valid = all(self.confidence_scorer.validate_email(email) for email in emails)
        phone_valid = all(self.confidence_scorer.validate_phone(phone) for phone in phones)
        ner_confidence = ner_results.get("confidence", {}).get("fields", {})

        field_confidences = {
            "email": self.confidence_scorer.score_field("email", emails, email_valid),
            "phone": self.confidence_scorer.score_field("phone", phones, phone_valid),
            "sections": self.confidence_scorer.score_field(
                "sections",
                sections,
                bool(sections),
            ),
            "name": ner_confidence.get("name", 0.0),
            "companies": ner_confidence.get("companies", 0.0),
            "skills": ner_confidence.get("skills", 0.0),
        }
        return field_confidences

    def _map_to_cv_analysis(
        self,
        merged_results: dict[str, Any],
        cv_text: str,
        cv_file_path: str,
        candidate_id: UUID,
    ) -> CVAnalysis:
        from uuid import uuid4

        # Create CV analysis ID first
        cv_analysis_id = uuid4()

        # Create CVSkill entities with the analysis ID
        experience_years = merged_results.get("experience_years", 0.0) or 0.0
        skills = self._ensure_skill_objects(
            merged_results.get("skills", []),
            cv_analysis_id,
            experience_years,
        )

        return CVAnalysis(
            id=cv_analysis_id,
            candidate_id=candidate_id,
            extracted_text=cv_text,
            skills=skills,
            work_experience_years=experience_years,
            education_level=merged_results.get("education_level"),
            suggested_topics=merged_results.get("topics", []),
            suggested_difficulty=self._calculate_difficulty(experience_years),
            embedding=None,
            summary=merged_results.get("summary"),
            created_at=datetime.now().isoformat(),
        )

    def _ensure_skill_objects(
        self,
        skills: list[CVSkill] | list[Any],
        cv_analysis_id: UUID,
        experience_years: float,
    ) -> list[CVSkill]:
        from uuid import uuid4

        if not skills:
            return []

        # If already CVSkill objects, return them
        if isinstance(skills[0], CVSkill):
            return skills

        # Infer proficiency level from experience years
        def infer_proficiency(exp_years: float) -> ProficiencyLevel:
            if exp_years >= 7:
                return ProficiencyLevel.EXPERT
            elif exp_years >= 4:
                return ProficiencyLevel.ADVANCED
            elif exp_years >= 2:
                return ProficiencyLevel.INTERMEDIATE
            else:
                return ProficiencyLevel.BEGINNER

        # Convert to CVSkill entities
        return [
            CVSkill(
                id=uuid4(),
                cv_analysis_id=cv_analysis_id,
                skill_name=skill.get("skill") if isinstance(skill, dict) else str(skill),
                proficiency_level=infer_proficiency(experience_years),
                years_of_experience=experience_years,
                is_primary=(idx < 3),  # First 3 skills are primary
                created_at=datetime.now(),
            )
            for idx, skill in enumerate(skills)
        ]

    def _calculate_difficulty(self, experience_years: float | None) -> str:
        if experience_years is None:
            return "medium"
        if experience_years >= 10:
            return "expert"
        if experience_years >= 5:
            return "advanced"
        if experience_years >= 2:
            return "medium"
        return "beginner"

