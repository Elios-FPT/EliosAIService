"""LLM-based CV analyzer using LangChain structured output."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import pdfplumber
from docx import Document

from src.domain.models.cv_analysis import CVAnalysis
from src.domain.models.cv_skill import CVSkill, ProficiencyLevel
from src.application.ports.cv_analyzer_port import CVAnalyzerPort, FileType
from src.application.ports.llm_port import LLMPort
from src.infrastructure.adapters.llm.cv_skill_extraction_models import CVSkillExtractionOutput

logger = logging.getLogger(__name__)


class LLMCVAnalyzerAdapter(CVAnalyzerPort):
    """LLM-based CV analyzer using structured output extraction.

    Fail-fast: Raises exception on LLM failure (no fallback).
    """

    def __init__(self, llm_port: LLMPort) -> None:
        """Initialize adapter with LLM port (required).

        Args:
            llm_port: LLM port for skill extraction (must implement analyze_cv_for_skills)

        Raises:
            ValueError: If llm_port is None
        """
        if llm_port is None:
            raise ValueError("llm_port is required for LLMCVAnalyzerAdapter")
        self.llm_port = llm_port

    async def analyze_cv(
        self,
        cv_content: bytes,
        file_type: FileType,
        candidate_id: str,
    ) -> CVAnalysis:
        """Analyze CV using LLM skill extraction.

        Args:
            cv_content: CV file bytes (PDF/DOCX/TXT)
            file_type: File type for parsing
            candidate_id: Candidate UUID string

        Returns:
            CVAnalysis with extracted skills and summary

        Raises:
            RuntimeError: If LLM extraction fails
            ValueError: If file parsing fails
        """
        cv_text = self._read_cv_text_from_bytes(cv_content, file_type)

        # LLM skill extraction (fail-fast, no fallback)
        extraction = await self.llm_port.analyze_cv_for_skills(  # type: ignore[attr-defined]
            cv_text=cv_text,
            context={"candidate_id": candidate_id},
        )

        return self._map_extraction_to_cv_analysis(
            extraction, cv_text, UUID(candidate_id)
        )

    def _map_extraction_to_cv_analysis(
        self,
        extraction: CVSkillExtractionOutput,
        cv_text: str,
        candidate_id: UUID,
    ) -> CVAnalysis:
        """Map LLM extraction to CVAnalysis domain model."""
        cv_analysis_id = uuid4()

        skills = [
            CVSkill(
                id=uuid4(),
                cv_analysis_id=cv_analysis_id,
                skill_name=skill.skill_name,
                proficiency_level=ProficiencyLevel(skill.proficiency_level.value),
                years_of_experience=skill.years_of_experience,
                is_primary=skill.is_primary,
                created_at=datetime.now(),
            )
            for skill in extraction.skills
        ]

        return CVAnalysis(
            id=cv_analysis_id,
            candidate_id=candidate_id,
            skills=skills,
            summary=extraction.summary,
            created_at=datetime.now(),
        )

    # === File Parsing (Keep from original) ===

    def _read_cv_text_from_bytes(self, cv_bytes: bytes, file_type: FileType) -> str:
        """Parse CV bytes to text based on file type."""
        if file_type == "pdf":
            return self._read_pdf_from_bytes(cv_bytes)
        elif file_type in ("docx", "doc"):
            return self._read_docx_from_bytes(cv_bytes)
        else:
            return self._read_text_from_bytes(cv_bytes)

    def _read_pdf_from_bytes(self, pdf_bytes: bytes) -> str:
        """Extract text from PDF bytes."""
        from io import BytesIO
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages).strip()

    def _read_docx_from_bytes(self, docx_bytes: bytes) -> str:
        """Extract text from DOCX bytes (uses tempfile)."""
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
        """Decode plain text bytes."""
        return text_bytes.decode('utf-8', errors='ignore').strip()
