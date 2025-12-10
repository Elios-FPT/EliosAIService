"""Hybrid CV analyzer orchestrator coordinating rules, NER, and LLM fallback."""

from __future__ import annotations

from datetime import datetime, timezone

def debug_print(msg: str):
    """Helper function to print debug messages with timestamps."""
    print(f"DEBUG [{datetime.now().strftime('%H:%M:%S.%f')[:-3]}]: {msg}", flush=True)

debug_print("hybrid_cv_analyzer_adapter.py: Starting imports...")

from pathlib import Path
from typing import Any
from uuid import UUID

import pdfplumber
from docx import Document

from ...domain.models.cv_analysis import CVAnalysis
from ...domain.models.cv_skill import CVSkill, ProficiencyLevel
from ...application.ports.cv_analyzer_port import CVAnalyzerPort, FileType

debug_print("hybrid_cv_analyzer_adapter.py: About to import sub-modules...")
from .confidence_scorer import ConfidenceScorer
debug_print("hybrid_cv_analyzer_adapter.py: confidence_scorer imported")
from .llm_fallback_extractor import (
    LLMFallbackExtractor,
    LLMFallbackExtractorProtocol,
    NoOpLLMFallbackExtractor,
)
debug_print("hybrid_cv_analyzer_adapter.py: llm_fallback_extractor imported")
from .rule_based_extractor import RuleBasedExtractor
debug_print("hybrid_cv_analyzer_adapter.py: rule_based_extractor imported")
from .spacy_ner_extractor import SpacyNERExtractor
debug_print("hybrid_cv_analyzer_adapter.py: spacy_ner_extractor imported")
debug_print("hybrid_cv_analyzer_adapter.py: All imports completed")


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
        cv_content: bytes,
        file_type: FileType,
        candidate_id: str,
    ) -> CVAnalysis:
        """Analyze CV contents from bytes using rules → NER → optional LLM fallback."""

        cv_text = self._read_cv_text_from_bytes(cv_content, file_type)

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
            UUID(candidate_id),
        )

    def _read_cv_text_from_bytes(self, cv_bytes: bytes, file_type: FileType) -> str:
        """Read CV text from bytes."""
        if file_type == "pdf":
            return self._read_pdf_from_bytes(cv_bytes)
        elif file_type in ("docx", "doc"):
            return self._read_docx_from_bytes(cv_bytes)
        else:
            return self._read_text_from_bytes(cv_bytes)

    def _read_pdf_from_bytes(self, pdf_bytes: bytes) -> str:
        """Read PDF from bytes."""
        from io import BytesIO
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages).strip()

    def _read_docx_from_bytes(self, docx_bytes: bytes) -> str:
        """Read DOCX from bytes (uses tempfile due to library limitation)."""
        from tempfile import NamedTemporaryFile
        import os

        with NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
            tmp.write(docx_bytes)
            tmp_path = tmp.name

        try:
            document = Document(tmp_path)
            return "\n".join(p.text.strip() for p in document.paragraphs if p.text).strip()
        finally:
            os.unlink(tmp_path)

    def _read_text_from_bytes(self, text_bytes: bytes) -> str:
        """Read plain text from bytes."""
        return text_bytes.decode('utf-8', errors='ignore').strip()

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
            skills=skills,
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

