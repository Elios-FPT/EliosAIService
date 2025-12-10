"""CV Analyzer port interface."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Literal

from src.domain.models.cv_analysis import CVAnalysis
from uuid import UUID

FileType = Literal["pdf", "docx", "doc", "txt"]


class CVAnalyzerPort(ABC):
    """Interface for CV analysis operations.

    This port abstracts CV parsing and analysis, allowing different
    implementations (spaCy, LangChain, etc.).
    """

    @abstractmethod
    async def analyze_cv(
        self,
        cv_content: bytes,
        file_type: FileType,
        candidate_id: str,
    ) -> CVAnalysis:
        """Analyze CV content and extract structured information.

        Args:
            cv_content: CV file content as bytes
            file_type: File type ("pdf", "docx", "doc", "txt")
            candidate_id: ID of the candidate

        Returns:
            CVAnalysis with extracted skills, experience, and metadata
        """
        pass

    @staticmethod
    def _detect_file_type(
        content_type: str | None = None,
        filename: str | None = None,
        content_bytes: bytes | None = None,
    ) -> FileType:
        """Detect file type from content-type, filename, or magic bytes.

        This is a helper method available to all CV analyzer implementations.

        Args:
            content_type: MIME type (e.g., "application/pdf")
            filename: File name with extension
            content_bytes: File content bytes (for magic number detection)

        Returns:
            File type: "pdf", "docx", "doc", or "txt"

        Raises:
            ValueError: If file type cannot be determined or is unsupported
        """
        # Priority 1: Content type
        if content_type:
            content_type_map = {
                "application/pdf": "pdf",
                "application/msword": "doc",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
                "text/plain": "txt",
            }
            if content_type in content_type_map:
                return content_type_map[content_type]

        # Priority 2: Filename extension
        if filename:
            ext = Path(filename).suffix.lower().lstrip(".")
            ext_map = {
                "pdf": "pdf",
                "doc": "doc",
                "docx": "docx",
                "txt": "txt",
            }
            if ext in ext_map:
                return ext_map[ext]

        # Priority 3: Magic bytes
        if content_bytes and len(content_bytes) >= 4:
            # PDF: %PDF
            if content_bytes[:4] == b"%PDF":
                return "pdf"
            # DOCX: PK\x03\x04 (ZIP signature)
            if content_bytes[:4] == b"PK\x03\x04":
                return "docx"
            # DOC: D0 CF 11 E0 (OLE2 signature)
            if content_bytes[:4] == b"\xd0\xcf\x11\xe0":
                return "doc"

        raise ValueError(
            f"Cannot determine file type. "
            f"Content-Type: {content_type}, Filename: {filename}"
        )

    # @abstractmethod
    # async def generate_cv_summary(
    #     self,
    #     extracted_data: dict,
    #     cv_text: str,
    # ) -> str:
    #     """Generate a concise summary of the CV for HR evaluation.

    #     Args:
    #         extracted_data: Extracted skills and experiences
    #         cv_text: Full text of the CV
    #     Returns:
    #         Summary text
    #     """
    #     pass

    # @abstractmethod
    # async def extract_skills_and_experience(
    #     self,
    #     cv_text: str,
    # ) -> CVAnalysis:
    #     """Extract skills and experience from CV text.

    #     Args:
    #         cv_text: Full text of the CV
    #     Returns:
    #         CVAnalysis with extracted skills, experiences, and language
    #     """
    #     pass

    # @abstractmethod
    # async def evaluate_cv_level_from_summary(
    #     self,
    #     cv_id: str,
    #     summary: str,
    # ) -> dict:
    #     """Evaluate CV level (e.g., Junior, Mid, Senior) based on summary.

    #     Args:
    #         cv_id: Unique CV identifier
    #         summary: CV summary text
    #     Returns:
    #         Dictionary with level, score, strengths, weaknesses, etc.
    #     """
    #     pass