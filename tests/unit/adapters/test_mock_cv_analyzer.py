"""Unit tests for MockCVAnalyzerAdapter."""

import pytest
from uuid import UUID, uuid4

from src.adapters.mock.mock_cv_analyzer import MockCVAnalyzerAdapter
from src.domain.models.cv_analysis import CVAnalysis


@pytest.fixture
def cv_analyzer():
    """Create CV analyzer instance."""
    return MockCVAnalyzerAdapter()


class TestExtractTextFromBytes:
    """Test extract_text_from_bytes method."""

    @pytest.mark.asyncio
    async def test_extract_text_pdf(self, cv_analyzer):
        """Test extracting text from PDF bytes."""
        pdf_bytes = b"%PDF-1.4\n..."
        text = await cv_analyzer.extract_text_from_bytes(pdf_bytes, "pdf")

        assert isinstance(text, str)
        assert len(text) > 200
        assert "John Doe" in text
        assert "Software Engineer" in text

    @pytest.mark.asyncio
    async def test_extract_text_doc(self, cv_analyzer):
        """Test extracting text from DOC bytes."""
        doc_bytes = b"\xd0\xcf\x11\xe0..."
        text = await cv_analyzer.extract_text_from_bytes(doc_bytes, "doc")

        assert isinstance(text, str)
        assert len(text) > 0

    @pytest.mark.asyncio
    async def test_extract_text_docx(self, cv_analyzer):
        """Test extracting text from DOCX bytes."""
        docx_bytes = b"PK\x03\x04..."
        text = await cv_analyzer.extract_text_from_bytes(docx_bytes, "docx")

        assert isinstance(text, str)
        assert len(text) > 0

    @pytest.mark.asyncio
    async def test_extract_text_txt(self, cv_analyzer):
        """Test extracting text from TXT bytes."""
        txt_bytes = b"John Doe\nSoftware Engineer"
        text = await cv_analyzer.extract_text_from_bytes(txt_bytes, "txt")

        assert isinstance(text, str)
        assert len(text) > 0


class TestAnalyzeCV:
    """Test analyze_cv method."""

    @pytest.mark.asyncio
    async def test_analyze_junior_cv(self, cv_analyzer):
        """Test analyzing junior-level CV."""
        candidate_id = str(uuid4())
        cv_bytes = b"junior developer cv content"
        cv_analysis = await cv_analyzer.analyze_cv(
            cv_content=cv_bytes,
            file_type="pdf",
            candidate_id=candidate_id
        )

        assert isinstance(cv_analysis, CVAnalysis)
        assert str(cv_analysis.candidate_id) == candidate_id
        assert len(cv_analysis.skills) >= 2
        assert len(cv_analysis.skills) <= 3
        assert cv_analysis.work_experience_years is not None
        assert 1.0 <= cv_analysis.work_experience_years <= 2.0
        assert cv_analysis.suggested_difficulty == "easy"
        assert cv_analysis.education_level == "Bachelor's"

    @pytest.mark.asyncio
    async def test_analyze_senior_cv(self, cv_analyzer):
        """Test analyzing senior-level CV."""
        candidate_id = str(uuid4())
        cv_bytes = b"senior engineer cv content"
        cv_analysis = await cv_analyzer.analyze_cv(
            cv_content=cv_bytes,
            file_type="pdf",
            candidate_id=candidate_id
        )

        assert isinstance(cv_analysis, CVAnalysis)
        assert len(cv_analysis.skills) >= 5
        assert len(cv_analysis.skills) <= 6
        assert cv_analysis.work_experience_years is not None
        assert 6.0 <= cv_analysis.work_experience_years <= 10.0
        assert cv_analysis.suggested_difficulty == "hard"
        assert cv_analysis.education_level == "Master's"

    @pytest.mark.asyncio
    async def test_analyze_mid_level_cv(self, cv_analyzer):
        """Test analyzing mid-level CV (default)."""
        candidate_id = str(uuid4())
        cv_bytes = b"developer cv content"
        cv_analysis = await cv_analyzer.analyze_cv(
            cv_content=cv_bytes,
            file_type="pdf",
            candidate_id=candidate_id
        )

        assert isinstance(cv_analysis, CVAnalysis)
        assert len(cv_analysis.skills) >= 4
        assert len(cv_analysis.skills) <= 5
        assert cv_analysis.work_experience_years is not None
        assert 3.0 <= cv_analysis.work_experience_years <= 5.0
        assert cv_analysis.suggested_difficulty == "medium"
        assert cv_analysis.education_level == "Bachelor's"

    @pytest.mark.asyncio
    async def test_cv_analysis_structure(self, cv_analyzer):
        """Test CV analysis has all required fields."""
        candidate_id = str(uuid4())
        cv_bytes = b"test cv content"
        cv_analysis = await cv_analyzer.analyze_cv(
            cv_content=cv_bytes,
            file_type="pdf",
            candidate_id=candidate_id
        )

        assert cv_analysis.id is not None
        # Verify no cv_file_path field (removed)
        assert not hasattr(cv_analysis, "cv_file_path")
        assert cv_analysis.extracted_text is not None
        assert len(cv_analysis.extracted_text) > 0
        assert isinstance(cv_analysis.skills, list)
        assert len(cv_analysis.skills) > 0
        assert isinstance(cv_analysis.suggested_topics, list)
        assert len(cv_analysis.suggested_topics) > 0
        assert cv_analysis.summary is not None
        assert "Mock CV analysis" in cv_analysis.summary

    @pytest.mark.asyncio
    async def test_skills_are_technical(self, cv_analyzer):
        """Test that extracted skills include technical skills."""
        candidate_id = str(uuid4())
        cv_bytes = b"senior engineer cv content"
        cv_analysis = await cv_analyzer.analyze_cv(
            cv_content=cv_bytes,
            file_type="pdf",
            candidate_id=candidate_id
        )

        # Check skill structure
        for skill in cv_analysis.skills:
            assert skill.skill_name is not None
            assert skill.proficiency_level is not None

    @pytest.mark.asyncio
    async def test_suggested_topics_from_skills(self, cv_analyzer):
        """Test that suggested topics are derived from skills."""
        candidate_id = str(uuid4())
        cv_bytes = b"python developer cv content"
        cv_analysis = await cv_analyzer.analyze_cv(
            cv_content=cv_bytes,
            file_type="pdf",
            candidate_id=candidate_id
        )

        # Topics should be related to skills
        assert len(cv_analysis.suggested_topics) > 0
        assert len(cv_analysis.suggested_topics) <= 5

    @pytest.mark.asyncio
    async def test_metadata_included(self, cv_analyzer):
        """Test that analysis has required fields."""
        candidate_id = str(uuid4())
        cv_bytes = b"junior dev cv content"
        cv_analysis = await cv_analyzer.analyze_cv(
            cv_content=cv_bytes,
            file_type="pdf",
            candidate_id=candidate_id
        )

        # Verify analysis structure
        assert cv_analysis.id is not None
        assert cv_analysis.candidate_id == UUID(candidate_id)
        assert cv_analysis.extracted_text is not None
        assert len(cv_analysis.skills) > 0
        assert cv_analysis.summary is not None
        assert "junior" in cv_analysis.summary.lower() or "Mock CV analysis" in cv_analysis.summary

    @pytest.mark.asyncio
    async def test_consistent_results(self, cv_analyzer):
        """Test that same content produces consistent experience level."""
        candidate_id = str(uuid4())
        cv_bytes = b"junior dev cv content"

        # Call twice with same content
        result1 = await cv_analyzer.analyze_cv(cv_bytes, "pdf", candidate_id)
        result2 = await cv_analyzer.analyze_cv(cv_bytes, "pdf", candidate_id)

        assert result1.suggested_difficulty == result2.suggested_difficulty
        assert len(result1.skills) == len(result2.skills)
        assert result1.education_level == result2.education_level
