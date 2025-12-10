"""Unit tests for ConfidenceScorer."""

import pytest
from src.infrastructure.adapters.cv_processing.confidence_scorer import ConfidenceScorer


class TestConfidenceScorer:
    """Test suite for ConfidenceScorer class."""

    @pytest.fixture
    def scorer(self):
        """Create scorer instance."""
        return ConfidenceScorer()

    def test_score_field_email_high_confidence(self, scorer):
        """Test scoring for valid email extraction."""
        emails = ["john.doe@example.com", "jane@company.org"]

        score = scorer.score_field("email", emails, validation_passed=True)

        assert score == 0.95  # High confidence for valid email

    def test_score_field_email_invalid(self, scorer):
        """Test scoring for invalid email (failed validation)."""
        emails = ["invalid@@example.com"]

        score = scorer.score_field("email", emails, validation_passed=False)

        assert score == 0.50  # Low confidence for failed validation

    def test_score_field_no_extraction(self, scorer):
        """Test scoring when no values extracted."""
        score = scorer.score_field("email", [], validation_passed=True)

        assert score == 0.0  # No confidence when nothing extracted

    def test_score_field_phone_high_confidence(self, scorer):
        """Test scoring for valid phone extraction."""
        phones = ["(202) 555-0123"]

        score = scorer.score_field("phone", phones, validation_passed=True)

        assert score == 0.95

    def test_score_field_dates_medium_confidence(self, scorer):
        """Test scoring for date extraction."""
        dates = ["Jan 2020", "Present", "2020-01-15"]

        score = scorer.score_field("dates", dates, validation_passed=True)

        assert score == 0.95 * 0.90  # Medium confidence with 0.90 multiplier

    def test_score_field_sections_good_structure(self, scorer):
        """Test scoring for well-structured CV (3+ sections)."""
        sections = {
            "EXPERIENCE": (10, "EXPERIENCE"),
            "EDUCATION": (20, "EDUCATION"),
            "SKILLS": (30, "SKILLS"),
            "SUMMARY": (5, "SUMMARY")
        }

        score = scorer.score_field("sections", sections, validation_passed=True)

        assert score == 0.90  # Good structure

    def test_score_field_sections_poor_structure(self, scorer):
        """Test scoring for poorly structured CV (< 2 sections)."""
        sections = {
            "EXPERIENCE": (10, "EXPERIENCE")
        }

        score = scorer.score_field("sections", sections, validation_passed=True)

        assert score == 0.50  # Poor structure

    def test_score_field_urls(self, scorer):
        """Test scoring for URL extraction."""
        urls = ["https://linkedin.com/in/johndoe", "https://github.com/johndoe"]

        score = scorer.score_field("urls", urls, validation_passed=True)

        assert score == 0.85  # Lower priority field

    def test_aggregate_confidence_all_fields(self, scorer):
        """Test aggregation with all fields present."""
        field_scores = {
            "email": 0.95,
            "phone": 0.95,
            "dates": 0.85,
            "sections": 0.90,
            "urls": 0.85
        }

        score = scorer.aggregate_confidence(field_scores)

        # Should be weighted average with no penalties
        assert 0.85 <= score <= 0.95
        assert score > 0.0

    def test_aggregate_confidence_missing_critical(self, scorer):
        """Test aggregation with missing critical fields."""
        field_scores = {
            "urls": 0.85  # Only non-critical field
        }

        score = scorer.aggregate_confidence(field_scores, critical_fields=["email", "phone"])

        # Should apply penalties for missing critical fields
        # 20% penalty per missing field: 0.80 * 0.80 = 0.64 penalty factor
        assert score < 0.60  # Significantly reduced due to penalties

    def test_aggregate_confidence_low_critical(self, scorer):
        """Test aggregation with low confidence in critical fields."""
        field_scores = {
            "email": 0.40,  # Low confidence in critical field
            "phone": 0.95,
            "sections": 0.90
        }

        score = scorer.aggregate_confidence(field_scores, critical_fields=["email"])

        # Should apply 10% penalty for low critical field confidence
        # Penalty factor: 0.90
        assert score > 0.0
        # Score should be reduced by penalty

    def test_aggregate_confidence_empty_scores(self, scorer):
        """Test aggregation with no field scores."""
        score = scorer.aggregate_confidence({})

        assert score == 0.0

    def test_validate_email_valid(self, scorer):
        """Test email validation for valid emails."""
        assert scorer.validate_email("john.doe@example.com") is True
        assert scorer.validate_email("user+tag@domain.co.uk") is True

    def test_validate_email_invalid(self, scorer):
        """Test email validation for invalid emails."""
        assert scorer.validate_email("invalid@@example.com") is False  # Double @
        assert scorer.validate_email("user@domain..com") is False  # Consecutive dots
        assert scorer.validate_email("a" * 65 + "@example.com") is False  # Local part too long
        assert scorer.validate_email("user@domain") is False  # No TLD

    def test_validate_phone_valid(self, scorer):
        """Test phone validation for valid phones."""
        assert scorer.validate_phone("(202) 555-0123") is True  # 10 digits
        assert scorer.validate_phone("+1-202-555-0123") is True  # 11 digits
        assert scorer.validate_phone("+84-9-1234-5678") is True  # 11 digits

    def test_validate_phone_invalid(self, scorer):
        """Test phone validation for invalid phones."""
        assert scorer.validate_phone("123") is False  # Too short
        assert scorer.validate_phone("1" * 20) is False  # Too long

    def test_validate_date_valid(self, scorer):
        """Test date validation for valid dates."""
        assert scorer.validate_date("Jan 2020") is True
        assert scorer.validate_date("2020-01-15") is True
        assert scorer.validate_date("Present") is True
        assert scorer.validate_date("Current") is True
        assert scorer.validate_date("01/15/2020") is True

    def test_validate_date_invalid(self, scorer):
        """Test date validation for invalid dates."""
        assert scorer.validate_date("random text") is False
        assert scorer.validate_date("123") is False
