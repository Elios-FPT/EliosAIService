"""Unit tests for CVAnalyzerPort interface."""

import pytest

from src.domain.ports.cv_analyzer_port import CVAnalyzerPort


class TestDetectFileType:
    """Test _detect_file_type static method."""

    def test_detect_pdf_from_content_type(self):
        """Test detecting PDF from content-type."""
        file_type = CVAnalyzerPort._detect_file_type(
            content_type="application/pdf"
        )
        assert file_type == "pdf"

    def test_detect_docx_from_content_type(self):
        """Test detecting DOCX from content-type."""
        file_type = CVAnalyzerPort._detect_file_type(
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        assert file_type == "docx"

    def test_detect_doc_from_content_type(self):
        """Test detecting DOC from content-type."""
        file_type = CVAnalyzerPort._detect_file_type(
            content_type="application/msword"
        )
        assert file_type == "doc"

    def test_detect_txt_from_content_type(self):
        """Test detecting TXT from content-type."""
        file_type = CVAnalyzerPort._detect_file_type(
            content_type="text/plain"
        )
        assert file_type == "txt"

    def test_detect_pdf_from_filename(self):
        """Test detecting PDF from filename extension."""
        file_type = CVAnalyzerPort._detect_file_type(
            filename="resume.pdf"
        )
        assert file_type == "pdf"

    def test_detect_docx_from_filename(self):
        """Test detecting DOCX from filename extension."""
        file_type = CVAnalyzerPort._detect_file_type(
            filename="cv.docx"
        )
        assert file_type == "docx"

    def test_detect_doc_from_filename(self):
        """Test detecting DOC from filename extension."""
        file_type = CVAnalyzerPort._detect_file_type(
            filename="resume.doc"
        )
        assert file_type == "doc"

    def test_detect_txt_from_filename(self):
        """Test detecting TXT from filename extension."""
        file_type = CVAnalyzerPort._detect_file_type(
            filename="cv.txt"
        )
        assert file_type == "txt"

    def test_detect_pdf_from_magic_bytes(self):
        """Test detecting PDF from magic bytes."""
        pdf_bytes = b"%PDF-1.4\n..."
        file_type = CVAnalyzerPort._detect_file_type(
            content_bytes=pdf_bytes
        )
        assert file_type == "pdf"

    def test_detect_docx_from_magic_bytes(self):
        """Test detecting DOCX from magic bytes (ZIP signature)."""
        docx_bytes = b"PK\x03\x04..."
        file_type = CVAnalyzerPort._detect_file_type(
            content_bytes=docx_bytes
        )
        assert file_type == "docx"

    def test_detect_doc_from_magic_bytes(self):
        """Test detecting DOC from magic bytes (OLE2 signature)."""
        doc_bytes = b"\xd0\xcf\x11\xe0..."
        file_type = CVAnalyzerPort._detect_file_type(
            content_bytes=doc_bytes
        )
        assert file_type == "doc"

    def test_priority_content_type_over_filename(self):
        """Test that content-type takes priority over filename."""
        file_type = CVAnalyzerPort._detect_file_type(
            content_type="application/pdf",
            filename="resume.docx"  # Wrong extension
        )
        assert file_type == "pdf"

    def test_priority_filename_over_magic_bytes(self):
        """Test that filename takes priority over magic bytes."""
        file_type = CVAnalyzerPort._detect_file_type(
            filename="resume.pdf",
            content_bytes=b"PK\x03\x04..."  # DOCX magic bytes
        )
        assert file_type == "pdf"

    def test_priority_magic_bytes_when_no_other_info(self):
        """Test that magic bytes are used when no content-type or filename."""
        file_type = CVAnalyzerPort._detect_file_type(
            content_bytes=b"%PDF-1.4\n..."
        )
        assert file_type == "pdf"

    def test_raises_value_error_when_cannot_detect(self):
        """Test that ValueError is raised when file type cannot be determined."""
        with pytest.raises(ValueError, match="Cannot determine file type"):
            CVAnalyzerPort._detect_file_type()

    def test_raises_value_error_for_unsupported_type(self):
        """Test that ValueError is raised for unsupported file types."""
        with pytest.raises(ValueError, match="Cannot determine file type"):
            CVAnalyzerPort._detect_file_type(
                content_type="image/jpeg",
                filename="photo.jpg"
            )

    def test_handles_none_values(self):
        """Test that None values are handled gracefully."""
        with pytest.raises(ValueError):
            CVAnalyzerPort._detect_file_type(
                content_type=None,
                filename=None,
                content_bytes=None
            )

    def test_handles_empty_bytes(self):
        """Test that empty bytes are handled."""
        with pytest.raises(ValueError):
            CVAnalyzerPort._detect_file_type(
                content_bytes=b""
            )

    def test_handles_short_bytes(self):
        """Test that bytes shorter than 4 bytes are handled."""
        with pytest.raises(ValueError):
            CVAnalyzerPort._detect_file_type(
                content_bytes=b"ABC"  # Only 3 bytes
            )

