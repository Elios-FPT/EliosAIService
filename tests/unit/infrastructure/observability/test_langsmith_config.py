"""Unit tests for LangSmith configuration and PII filtering."""

import pytest
from unittest.mock import Mock, patch
from uuid import UUID

from src.infrastructure.observability.langsmith_config import (
    PIIFilteringTracer,
    setup_langsmith_tracing,
    create_pii_filtering_callback,
    create_metadata_for_tracing,
)


class TestPIIFilteringTracer:
    """Test PII filtering tracer."""

    def test_filter_email(self):
        """Test email redaction."""
        tracer = PIIFilteringTracer()

        text = "My email is john.doe@example.com and you can reach me there."
        filtered = tracer._filter_pii(text)

        assert "john.doe@example.com" not in filtered
        assert "[EMAIL_REDACTED]" in filtered

    def test_filter_phone(self):
        """Test phone number redaction."""
        tracer = PIIFilteringTracer()

        test_cases = [
            "Call me at 555-123-4567",
            "Phone: 555.123.4567",
            "Contact: 5551234567",
        ]

        for text in test_cases:
            filtered = tracer._filter_pii(text)
            assert "[PHONE_REDACTED]" in filtered
            assert "555" not in filtered or "[PHONE_REDACTED]" in filtered

    def test_filter_ssn(self):
        """Test SSN redaction."""
        tracer = PIIFilteringTracer()

        text = "My SSN is 123-45-6789 for verification."
        filtered = tracer._filter_pii(text)

        assert "123-45-6789" not in filtered
        assert "[SSN_REDACTED]" in filtered

    def test_filter_credit_card(self):
        """Test credit card redaction."""
        tracer = PIIFilteringTracer()

        test_cases = [
            "Card: 1234-5678-9012-3456",
            "Number: 1234 5678 9012 3456",
            "CC: 1234567890123456",
        ]

        for text in test_cases:
            filtered = tracer._filter_pii(text)
            assert "[CC_REDACTED]" in filtered

    def test_filter_name_context(self):
        """Test name redaction in specific contexts."""
        tracer = PIIFilteringTracer()

        text = "My name is John Smith and I work at Google."
        filtered = tracer._filter_pii(text)

        assert "John Smith" not in filtered
        assert "[NAME_REDACTED]" in filtered

    def test_truncate_answer_text(self):
        """Test answer text truncation."""
        tracer = PIIFilteringTracer(max_answer_length=50)

        long_answer = "A" * 200
        filtered = tracer._filter_pii(long_answer, field_name="answer_text")

        # Should truncate to 50 chars + "... [TRUNCATED]" (15 chars) = 65 total
        assert filtered.endswith("... [TRUNCATED]")
        assert len(filtered) == 50 + len("... [TRUNCATED]")
        assert filtered.startswith("A" * 50)

    def test_truncate_cv_text(self):
        """Test CV text truncation."""
        tracer = PIIFilteringTracer(max_cv_length=100)

        long_cv = "B" * 500
        filtered = tracer._filter_pii(long_cv, field_name="cv_text")

        assert len(filtered) <= 120  # 100 + "... [CV_REDACTED]"
        assert "[CV_REDACTED]" in filtered

    def test_filter_dict_recursive(self):
        """Test recursive dictionary filtering."""
        tracer = PIIFilteringTracer()

        data = {
            "question": "What is your email?",
            "answer": "My email is john@example.com",
            "metadata": {
                "candidate_email": "candidate@test.com",
                "phone": "555-1234",
            },
        }

        filtered = tracer._filter_dict(data)

        # Check all emails redacted
        assert "john@example.com" not in str(filtered)
        assert "candidate@test.com" not in str(filtered)
        assert filtered["answer"] == "My email is [EMAIL_REDACTED]"
        assert filtered["metadata"]["candidate_email"] == "[EMAIL_REDACTED]"

    def test_filter_preserves_safe_data(self):
        """Test that UUIDs and numbers are preserved."""
        tracer = PIIFilteringTracer()

        data = {
            "interview_id": "123e4567-e89b-12d3-a456-426614174000",
            "score": 85.5,
            "difficulty": "medium",
        }

        filtered = tracer._filter_dict(data)

        assert filtered["interview_id"] == "123e4567-e89b-12d3-a456-426614174000"
        assert filtered["score"] == 85.5
        assert filtered["difficulty"] == "medium"

    def test_multiple_pii_patterns(self):
        """Test filtering multiple PII patterns in one text."""
        tracer = PIIFilteringTracer()

        text = """
        My name is Jane Doe.
        Email: jane.doe@company.com
        Phone: 555-987-6543
        SSN: 987-65-4321
        """

        filtered = tracer._filter_pii(text)

        assert "Jane Doe" not in filtered
        assert "jane.doe@company.com" not in filtered
        assert "555-987-6543" not in filtered
        assert "987-65-4321" not in filtered
        assert "[NAME_REDACTED]" in filtered
        assert "[EMAIL_REDACTED]" in filtered
        assert "[PHONE_REDACTED]" in filtered
        assert "[SSN_REDACTED]" in filtered


class TestLangSmithSetup:
    """Test LangSmith setup functions."""

    def test_create_metadata_for_tracing(self):
        """Test metadata creation for tracing."""
        interview_id = UUID("123e4567-e89b-12d3-a456-426614174000")
        candidate_id = UUID("987e6543-e21c-34d5-b678-901234567890")

        metadata = create_metadata_for_tracing(
            interview_id=interview_id,
            candidate_id=candidate_id,
            question_type="technical",
            difficulty="hard",
            skill="Python",
            custom_field="custom_value",
        )

        assert metadata["interview_id"] == str(interview_id)
        assert metadata["candidate_id"] == str(candidate_id)
        assert metadata["question_type"] == "technical"
        assert metadata["difficulty"] == "hard"
        assert metadata["skill"] == "Python"
        assert metadata["custom_field"] == "custom_value"

    def test_create_metadata_with_none_values(self):
        """Test metadata creation with None values."""
        metadata = create_metadata_for_tracing(
            interview_id=None,
            candidate_id=None,
            question_type="behavioral",
        )

        assert "interview_id" not in metadata
        assert "candidate_id" not in metadata
        assert metadata["question_type"] == "behavioral"

    @patch.dict("os.environ", {}, clear=True)
    def test_setup_langsmith_disabled(self):
        """Test LangSmith setup when disabled."""
        settings = Mock()
        settings.enable_langsmith = False

        tracer = setup_langsmith_tracing(settings)

        assert tracer is None

    @patch.dict("os.environ", {}, clear=True)
    def test_setup_langsmith_enabled_with_pii_filtering(self):
        """Test LangSmith setup with PII filtering enabled."""
        settings = Mock()
        settings.enable_langsmith = True
        settings.langsmith_api_key = "test-api-key"
        settings.langchain_tracing_v2 = True
        settings.langchain_project = "test-project"
        settings.langchain_endpoint = "https://api.smith.langchain.com"
        settings.langsmith_filter_pii = True
        settings.langsmith_sample_rate = 1.0

        tracer = setup_langsmith_tracing(settings)

        assert tracer is not None
        assert isinstance(tracer, PIIFilteringTracer)
        assert tracer.max_answer_length == 200
        assert tracer.max_cv_length == 100

    @patch.dict("os.environ", {}, clear=True)
    def test_setup_langsmith_enabled_without_pii_filtering(self):
        """Test LangSmith setup without PII filtering."""
        settings = Mock()
        settings.enable_langsmith = True
        settings.langsmith_api_key = "test-api-key"
        settings.langchain_tracing_v2 = True
        settings.langchain_project = "test-project"
        settings.langchain_endpoint = "https://api.smith.langchain.com"
        settings.langsmith_filter_pii = False
        settings.langsmith_sample_rate = 0.5

        tracer = setup_langsmith_tracing(settings)

        assert tracer is None  # No tracer returned when PII filtering disabled

    def test_create_pii_filtering_callback_enabled(self):
        """Test callback creation when enabled."""
        settings = Mock()
        settings.enable_langsmith = True
        settings.langsmith_api_key = "test-api-key"
        settings.langchain_tracing_v2 = True
        settings.langchain_project = "test-project"
        settings.langchain_endpoint = "https://api.smith.langchain.com"
        settings.langsmith_filter_pii = True
        settings.langsmith_sample_rate = 1.0

        callbacks = create_pii_filtering_callback(settings)

        assert isinstance(callbacks, list)
        assert len(callbacks) == 1
        assert isinstance(callbacks[0], PIIFilteringTracer)

    def test_create_pii_filtering_callback_disabled(self):
        """Test callback creation when disabled."""
        settings = Mock()
        settings.enable_langsmith = False

        callbacks = create_pii_filtering_callback(settings)

        assert isinstance(callbacks, list)
        assert len(callbacks) == 0


class TestEdgeCases:
    """Test edge cases and special scenarios."""

    def test_empty_string_filtering(self):
        """Test filtering empty strings."""
        tracer = PIIFilteringTracer()

        assert tracer._filter_pii("") == ""
        assert tracer._filter_pii(None) is None

    def test_filter_dict_with_nested_lists(self):
        """Test filtering dictionaries with nested lists."""
        tracer = PIIFilteringTracer()

        data = {
            "questions": [
                {"text": "What is your email?"},
                {"text": "Contact: john@example.com"},
            ],
            "answers": ["My email is jane@test.com", "Call me at 555-1234"],
        }

        filtered = tracer._filter_dict(data)

        assert "john@example.com" not in str(filtered)
        assert "jane@test.com" not in str(filtered)
        assert "[EMAIL_REDACTED]" in filtered["questions"][1]["text"]

    def test_no_pii_in_text(self):
        """Test text without PII remains unchanged (except structure)."""
        tracer = PIIFilteringTracer()

        text = "The sky is blue and Python is great."
        filtered = tracer._filter_pii(text)

        assert filtered == text
