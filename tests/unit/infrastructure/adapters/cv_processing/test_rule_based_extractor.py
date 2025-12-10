"""Unit tests for RuleBasedExtractor."""

import pytest
from src.infrastructure.adapters.cv_processing.rule_based_extractor import RuleBasedExtractor


class TestRuleBasedExtractor:
    """Test suite for RuleBasedExtractor class."""

    @pytest.fixture
    def extractor(self):
        """Create extractor instance."""
        return RuleBasedExtractor()

    @pytest.fixture
    def sample_cv_english(self):
        """Load English CV fixture."""
        with open("tests/fixtures/cv_samples/sample_cv_english.txt", "r", encoding="utf-8") as f:
            return f.read()

    @pytest.fixture
    def sample_cv_vietnamese(self):
        """Load Vietnamese CV fixture."""
        with open("tests/fixtures/cv_samples/sample_cv_vietnamese.txt", "r", encoding="utf-8") as f:
            return f.read()

    def test_extract_emails_valid_formats(self, extractor):
        """Test extraction of various valid email formats."""
        text = """
        Contact: john.doe@example.com
        Email: jane+tag@domain.co.uk
        Reach me: user_name@company-name.org
        """
        result = extractor._extract_emails(text)

        assert len(result) == 3
        assert "john.doe@example.com" in result
        assert "jane+tag@domain.co.uk" in result
        assert "user_name@company-name.org" in result

    def test_extract_emails_deduplication(self, extractor):
        """Test email deduplication (case-insensitive)."""
        text = """
        Email: John.Doe@Example.com
        Contact: john.doe@example.com
        Backup: JOHN.DOE@EXAMPLE.COM
        """
        result = extractor._extract_emails(text)

        # Should return only 1 unique email (case-insensitive dedup)
        assert len(result) == 1

    def test_extract_phones_us_format(self, extractor):
        """Test extraction of US phone formats."""
        text = """
        Phone: (202) 555-0123
        Mobile: 202-555-0124
        Cell: 202.555.0125
        """
        result = extractor._extract_phones(text)

        assert len(result) == 3
        # Check that some form of 202-555-0123 is captured
        assert any("202" in phone and "555" in phone and "0123" in phone for phone in result)

    def test_extract_phones_international(self, extractor):
        """Test extraction of international phone formats."""
        text = """
        Phone: +1-202-555-0123
        Vietnam: +84-9-1234-5678
        UK: +44-20-7123-4567
        """
        result = extractor._extract_phones(text)

        assert len(result) == 3
        assert any("+84" in phone for phone in result)

    def test_extract_dates_multiple_formats(self, extractor):
        """Test extraction of various date formats."""
        text = """
        Start: Jan 2020
        End: December 2021
        Contract: 2020-01-15 to 2021-12-31
        Project: 01/15/2020 - 12/31/2021
        Current: Jan 2022 - Present
        """
        result = extractor._extract_dates(text)

        # Should extract multiple date formats
        assert len(result) >= 6
        assert "Present" in result or "present" in result
        assert any("2020" in date for date in result)

    def test_extract_sections_case_insensitive(self, extractor):
        """Test section extraction is case-insensitive."""
        text = """

EXPERIENCE
Senior Developer at Tech Corp

experience
Junior Developer at StartupXYZ

Experience
Mid-level Developer at AgencyX"""
        result = extractor._extract_sections(text)

        # Should extract only unique sections (normalized)
        # Only first occurrence is kept (last one wins due to dict update)
        assert "EXPERIENCE" in result

    def test_extract_sections_normalization(self, extractor):
        """Test section header normalization."""
        text = """
WORK EXPERIENCE
Senior Developer

TECHNICAL SKILLS
Python, Java

ACADEMIC BACKGROUND
B.S. Computer Science
        """
        result = extractor._extract_sections(text)

        # Normalized section names
        assert "EXPERIENCE" in result  # WORK EXPERIENCE → EXPERIENCE
        assert "SKILLS" in result      # TECHNICAL SKILLS → SKILLS
        assert "EDUCATION" in result   # ACADEMIC BACKGROUND → EDUCATION

    def test_extract_urls_linkedin_github(self, extractor):
        """Test extraction of LinkedIn and GitHub URLs."""
        text = """
        LinkedIn: https://linkedin.com/in/johndoe
        GitHub: https://github.com/johndoe
        Portfolio: https://www.johndoe.com
        Blog: http://blog.johndoe.com
        """
        result = extractor._extract_urls(text)

        assert len(result) == 4
        assert any("linkedin.com" in url for url in result)
        assert any("github.com" in url for url in result)

    def test_extract_full_english_cv(self, extractor, sample_cv_english):
        """Test extraction on full English CV fixture."""
        result = extractor.extract(sample_cv_english)

        # Verify emails extracted
        assert len(result["emails"]) >= 1
        assert "john.doe@example.com" in result["emails"]

        # Verify phones extracted
        assert len(result["phones"]) >= 1
        assert any("202" in phone for phone in result["phones"])

        # Verify dates extracted
        assert len(result["dates"]) >= 5

        # Verify sections extracted
        assert len(result["sections"]) >= 4
        assert "EXPERIENCE" in result["sections"]
        assert "EDUCATION" in result["sections"]
        assert "SKILLS" in result["sections"]

        # Verify URLs extracted
        assert len(result["urls"]) >= 2
        assert any("linkedin.com" in url for url in result["urls"])

    def test_extract_full_vietnamese_cv(self, extractor, sample_cv_vietnamese):
        """Test extraction on Vietnamese CV fixture."""
        result = extractor.extract(sample_cv_vietnamese)

        # Verify emails extracted
        assert len(result["emails"]) >= 1
        assert "nguyen.van.an@gmail.com" in result["emails"]

        # Verify phones extracted (Vietnamese format)
        assert len(result["phones"]) >= 1
        assert any("+84" in phone for phone in result["phones"])

        # Verify URLs extracted
        assert len(result["urls"]) >= 1

        # Note: Vietnamese section headers may not match English patterns
        # This is expected and will be handled by spaCy NER in Phase 2

    def test_extract_empty_text(self, extractor):
        """Test extraction on empty text."""
        result = extractor.extract("")

        assert result["emails"] == []
        assert result["phones"] == []
        assert result["dates"] == []
        assert result["sections"] == {}
        assert result["urls"] == []

    def test_extract_malformed_content(self, extractor):
        """Test extraction on malformed CV content."""
        with open("tests/fixtures/cv_samples/sample_cv_malformed.txt", "r", encoding="utf-8") as f:
            text = f.read()

        result = extractor.extract(text)

        # Should not crash, but may extract limited data
        assert isinstance(result, dict)
        assert "emails" in result
        assert "phones" in result
        # Malformed email should not be extracted
        assert len(result["emails"]) == 0
