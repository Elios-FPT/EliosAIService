"""Integration tests for rule-based CV extraction."""

import pytest
import time
from src.infrastructure.adapters.cv_processing.rule_based_extractor import RuleBasedExtractor
from src.infrastructure.adapters.cv_processing.confidence_scorer import ConfidenceScorer


class TestRuleBasedCVExtraction:
    """Integration tests for full CV extraction workflow."""

    @pytest.fixture
    def extractor(self):
        """Create extractor instance."""
        return RuleBasedExtractor()

    @pytest.fixture
    def scorer(self):
        """Create scorer instance."""
        return ConfidenceScorer()

    def test_real_cv_english_extraction_and_scoring(self, extractor, scorer):
        """Test full extraction + scoring workflow on English CV."""
        # Load fixture
        with open("tests/fixtures/cv_samples/sample_cv_english.txt", "r", encoding="utf-8") as f:
            cv_text = f.read()

        # Extract fields
        extraction_result = extractor.extract(cv_text)

        # Validate extraction
        assert len(extraction_result["emails"]) >= 1
        assert "john.doe@example.com" in extraction_result["emails"]
        assert len(extraction_result["phones"]) >= 1
        assert len(extraction_result["dates"]) >= 5
        assert len(extraction_result["sections"]) >= 4
        assert len(extraction_result["urls"]) >= 2

        # Calculate confidence scores
        field_scores = {}

        # Score email
        email_valid = all(scorer.validate_email(email) for email in extraction_result["emails"])
        field_scores["email"] = scorer.score_field("email", extraction_result["emails"], email_valid)

        # Score phone
        phone_valid = all(scorer.validate_phone(phone) for phone in extraction_result["phones"])
        field_scores["phone"] = scorer.score_field("phone", extraction_result["phones"], phone_valid)

        # Score dates
        date_valid = all(scorer.validate_date(date) for date in extraction_result["dates"])
        field_scores["dates"] = scorer.score_field("dates", extraction_result["dates"], date_valid)

        # Score sections
        field_scores["sections"] = scorer.score_field("sections", extraction_result["sections"], True)

        # Score URLs
        field_scores["urls"] = scorer.score_field("urls", extraction_result["urls"], True)

        # Aggregate confidence
        overall_confidence = scorer.aggregate_confidence(field_scores)

        # Assertions
        assert overall_confidence > 0.85, f"Expected confidence > 0.85, got {overall_confidence}"
        assert field_scores["email"] >= 0.95
        assert field_scores["phone"] >= 0.95
        assert field_scores["sections"] >= 0.75

    def test_real_cv_vietnamese_extraction_and_scoring(self, extractor, scorer):
        """Test full extraction + scoring workflow on Vietnamese CV."""
        # Load fixture
        with open("tests/fixtures/cv_samples/sample_cv_vietnamese.txt", "r", encoding="utf-8") as f:
            cv_text = f.read()

        # Extract fields
        extraction_result = extractor.extract(cv_text)

        # Validate extraction
        assert len(extraction_result["emails"]) >= 1
        assert "nguyen.van.an@gmail.com" in extraction_result["emails"]
        assert len(extraction_result["phones"]) >= 1
        assert any("+84" in phone for phone in extraction_result["phones"])
        assert len(extraction_result["urls"]) >= 1

        # Calculate confidence scores
        field_scores = {}

        # Score email
        email_valid = all(scorer.validate_email(email) for email in extraction_result["emails"])
        field_scores["email"] = scorer.score_field("email", extraction_result["emails"], email_valid)

        # Score phone
        phone_valid = all(scorer.validate_phone(phone) for phone in extraction_result["phones"])
        field_scores["phone"] = scorer.score_field("phone", extraction_result["phones"], phone_valid)

        # Score sections
        field_scores["sections"] = scorer.score_field("sections", extraction_result["sections"], True)

        # Score URLs
        field_scores["urls"] = scorer.score_field("urls", extraction_result["urls"], True)

        # Aggregate confidence
        overall_confidence = scorer.aggregate_confidence(field_scores)

        # Assertions
        assert overall_confidence > 0.60, f"Expected confidence > 0.60, got {overall_confidence}"

    def test_extraction_performance(self, extractor):
        """Test that extraction completes within performance target (< 50ms)."""
        # Load fixture
        with open("tests/fixtures/cv_samples/sample_cv_english.txt", "r", encoding="utf-8") as f:
            cv_text = f.read()

        # Measure execution time
        start_time = time.perf_counter()
        extraction_result = extractor.extract(cv_text)
        end_time = time.perf_counter()

        execution_time_ms = (end_time - start_time) * 1000

        # Assert performance target
        assert execution_time_ms < 50.0, f"Extraction took {execution_time_ms:.2f}ms (target: < 50ms)"

        # Verify extraction actually worked
        assert len(extraction_result["emails"]) > 0

    def test_malformed_cv_graceful_degradation(self, extractor, scorer):
        """Test that extraction gracefully handles malformed CV content."""
        # Load malformed fixture
        with open("tests/fixtures/cv_samples/sample_cv_malformed.txt", "r", encoding="utf-8") as f:
            cv_text = f.read()

        # Extract fields (should not crash)
        extraction_result = extractor.extract(cv_text)

        # Calculate confidence (should be low)
        field_scores = {}

        email_valid = all(scorer.validate_email(email) for email in extraction_result["emails"])
        field_scores["email"] = scorer.score_field("email", extraction_result["emails"], email_valid)

        phone_valid = all(scorer.validate_phone(phone) for phone in extraction_result["phones"])
        field_scores["phone"] = scorer.score_field("phone", extraction_result["phones"], phone_valid)

        field_scores["sections"] = scorer.score_field("sections", extraction_result["sections"], True)

        overall_confidence = scorer.aggregate_confidence(field_scores)

        # Should have low confidence for malformed content
        assert overall_confidence < 0.50, f"Expected low confidence, got {overall_confidence}"

    def test_minimal_cv_extraction(self, extractor, scorer):
        """Test extraction on minimal CV (only name and email)."""
        # Load minimal fixture
        with open("tests/fixtures/cv_samples/sample_cv_minimal.txt", "r", encoding="utf-8") as f:
            cv_text = f.read()

        # Extract fields
        extraction_result = extractor.extract(cv_text)

        # Should extract email
        assert len(extraction_result["emails"]) >= 1
        assert "bob.johnson@email.com" in extraction_result["emails"]

        # Should have minimal or no other fields
        assert len(extraction_result["sections"]) == 0

        # Calculate confidence
        field_scores = {}
        email_valid = all(scorer.validate_email(email) for email in extraction_result["emails"])
        field_scores["email"] = scorer.score_field("email", extraction_result["emails"], email_valid)
        field_scores["sections"] = scorer.score_field("sections", extraction_result["sections"], True)

        overall_confidence = scorer.aggregate_confidence(field_scores)

        # Should have moderate confidence (email present but no structure)
        assert 0.30 < overall_confidence < 0.70
