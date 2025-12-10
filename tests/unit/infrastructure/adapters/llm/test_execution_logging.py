"""Unit tests for execution logging enhancements.

Tests token extraction, cost estimation, input sanitization, and retry logic.
"""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.infrastructure.adapters.llm.langchain_adapter import LangChainAdapter
from src.domain.models.prompt_template import PromptTemplate


@pytest.fixture
def mock_chat_model():
    """Create a mock LangChain chat model."""
    model = MagicMock()
    model.model_name = "gpt-4"
    return model


@pytest.fixture
def mock_prompt_repo():
    """Create a mock PromptRepositoryPort."""
    repo = AsyncMock()
    return repo


@pytest.fixture
def sample_prompt_template():
    """Create a sample PromptTemplate for testing."""
    return PromptTemplate(
        id=uuid4(),
        name="test_prompt",
        version=1,
        template_json={
            "system": "You are a helpful assistant.",
            "user_template": "Answer: {question}",
            "variables": ["question"],
        },
        is_active=True,
        is_draft=False,
        created_by="test",
    )


class TestExtractTokenUsage:
    """Test _extract_token_usage() method."""

    def test_extract_token_usage_openai(self, mock_chat_model):
        """Test token extraction from OpenAI response."""
        adapter = LangChainAdapter(model=mock_chat_model)

        metadata = {
            "usage": {
                "total_tokens": 150,
                "prompt_tokens": 100,
                "completion_tokens": 50,
            }
        }

        total, prompt, completion = adapter._extract_token_usage(metadata, "gpt-4")

        assert total == 150
        assert prompt == 100
        assert completion == 50

    def test_extract_token_usage_anthropic(self, mock_chat_model):
        """Test token extraction from Anthropic response."""
        adapter = LangChainAdapter(model=mock_chat_model)

        metadata = {
            "usage": {
                "input_tokens": 100,
                "output_tokens": 50,
            }
        }

        total, prompt, completion = adapter._extract_token_usage(metadata, "claude-3-opus")

        assert total == 150
        assert prompt == 100
        assert completion == 50

    def test_extract_token_usage_generic(self, mock_chat_model):
        """Test token extraction from generic format."""
        adapter = LangChainAdapter(model=mock_chat_model)

        metadata = {
            "token_usage": {
                "total": 200,
                "prompt": 150,
                "completion": 50,
            }
        }

        total, prompt, completion = adapter._extract_token_usage(metadata, "unknown")

        assert total == 200
        assert prompt == 150
        assert completion == 50

    def test_extract_token_usage_none(self, mock_chat_model):
        """Test token extraction when metadata is None."""
        adapter = LangChainAdapter(model=mock_chat_model)

        total, prompt, completion = adapter._extract_token_usage(None, "gpt-4")

        assert total is None
        assert prompt is None
        assert completion is None

    def test_extract_token_usage_no_usage_key(self, mock_chat_model):
        """Test token extraction when usage key is missing."""
        adapter = LangChainAdapter(model=mock_chat_model)

        metadata = {"model": "gpt-4", "other": "data"}

        total, prompt, completion = adapter._extract_token_usage(metadata, "gpt-4")

        assert total is None
        assert prompt is None
        assert completion is None


class TestEstimateCost:
    """Test _estimate_cost() method."""

    def test_estimate_cost_gpt4(self, mock_chat_model):
        """Test cost estimation for GPT-4."""
        adapter = LangChainAdapter(model=mock_chat_model)

        # 1000 prompt tokens + 500 completion tokens
        # Expected: (1000/1000 * 0.03) + (500/1000 * 0.06) = 0.03 + 0.03 = 0.06
        cost = adapter._estimate_cost("gpt-4", 1000, 500)

        assert cost == pytest.approx(0.06, rel=0.01)

    def test_estimate_cost_gpt35(self, mock_chat_model):
        """Test cost estimation for GPT-3.5."""
        adapter = LangChainAdapter(model=mock_chat_model)

        # 1000 prompt tokens + 500 completion tokens
        # Expected: (1000/1000 * 0.0005) + (500/1000 * 0.0015) = 0.0005 + 0.00075 = 0.00125
        cost = adapter._estimate_cost("gpt-3.5-turbo", 1000, 500)

        assert cost == pytest.approx(0.00125, rel=0.01)

    def test_estimate_cost_claude_opus(self, mock_chat_model):
        """Test cost estimation for Claude 3 Opus."""
        adapter = LangChainAdapter(model=mock_chat_model)

        # 1000 prompt tokens + 500 completion tokens
        # Expected: (1000/1000 * 0.015) + (500/1000 * 0.075) = 0.015 + 0.0375 = 0.0525
        cost = adapter._estimate_cost("claude-3-opus", 1000, 500)

        assert cost == pytest.approx(0.0525, rel=0.01)

    def test_estimate_cost_unknown_model(self, mock_chat_model):
        """Test cost estimation for unknown model."""
        adapter = LangChainAdapter(model=mock_chat_model)

        cost = adapter._estimate_cost("unknown-model", 1000, 500)

        assert cost is None

    def test_estimate_cost_no_tokens(self, mock_chat_model):
        """Test cost estimation when tokens are None."""
        adapter = LangChainAdapter(model=mock_chat_model)

        cost = adapter._estimate_cost("gpt-4", None, 500)
        assert cost is None

        cost = adapter._estimate_cost("gpt-4", 1000, None)
        assert cost is None


class TestSanitizeVariables:
    """Test _sanitize_variables() method."""

    def test_sanitize_variables_email(self, mock_chat_model):
        """Test email redaction in input variables."""
        adapter = LangChainAdapter(model=mock_chat_model)

        sanitized = adapter._sanitize_variables(
            {
                "cv_text": "Contact: john.doe@example.com for more info",
                "question": "What is Python?",
            }
        )

        assert "[EMAIL_REDACTED]" in sanitized["cv_text"]
        assert "john.doe@example.com" not in sanitized["cv_text"]
        assert sanitized["question"] == "What is Python?"

    def test_sanitize_variables_phone(self, mock_chat_model):
        """Test phone number redaction."""
        adapter = LangChainAdapter(model=mock_chat_model)

        sanitized = adapter._sanitize_variables(
            {
                "cv_text": "Call me at 555-123-4567",
                "contact": "Phone: 555.123.4567",
            }
        )

        assert "[PHONE_REDACTED]" in sanitized["cv_text"]
        assert "555-123-4567" not in sanitized["cv_text"]
        assert "[PHONE_REDACTED]" in sanitized["contact"]

    def test_sanitize_variables_truncate(self, mock_chat_model):
        """Test long text truncation."""
        adapter = LangChainAdapter(model=mock_chat_model)

        long_text = "A" * 1000
        sanitized = adapter._sanitize_variables({"cv_text": long_text})

        assert len(sanitized["cv_text"]) < len(long_text)
        assert "[TRUNCATED" in sanitized["cv_text"]
        assert sanitized["cv_text"].endswith(" chars]")

    def test_sanitize_variables_none(self, mock_chat_model):
        """Test sanitization with None values."""
        adapter = LangChainAdapter(model=mock_chat_model)

        sanitized = adapter._sanitize_variables({"key1": None, "key2": "value"})

        assert sanitized["key1"] is None
        assert sanitized["key2"] == "value"


class TestLogExecutionWithRetry:
    """Test _log_execution_with_retry() method."""

    @pytest.mark.asyncio
    async def test_log_execution_retry_success(
        self, mock_chat_model, mock_prompt_repo, sample_prompt_template
    ):
        """Test retry logic succeeds on second attempt."""
        # Fail first, succeed second
        mock_prompt_repo.log_execution.side_effect = [
            Exception("Connection lost"),
            None,  # Success
        ]

        adapter = LangChainAdapter(model=mock_chat_model, prompt_repository=mock_prompt_repo)

        execution_data = {
            "interview_id": "test-123",
            "tokens_used": 100,
            "success": True,
        }

        await adapter._log_execution_with_retry(sample_prompt_template, execution_data)

        assert mock_prompt_repo.log_execution.call_count == 2

    @pytest.mark.asyncio
    async def test_log_execution_retry_all_fail(
        self, mock_chat_model, mock_prompt_repo, sample_prompt_template
    ):
        """Test retry logic fails after all attempts."""
        mock_prompt_repo.log_execution.side_effect = Exception("Connection lost")

        adapter = LangChainAdapter(model=mock_chat_model, prompt_repository=mock_prompt_repo)

        execution_data = {"tokens_used": 100, "success": True}

        with pytest.raises(Exception, match="Connection lost"):
            await adapter._log_execution_with_retry(
                sample_prompt_template, execution_data, max_retries=3
            )

        assert mock_prompt_repo.log_execution.call_count == 3

    @pytest.mark.asyncio
    async def test_log_execution_retry_success_first_attempt(
        self, mock_chat_model, mock_prompt_repo, sample_prompt_template
    ):
        """Test retry logic succeeds on first attempt."""
        mock_prompt_repo.log_execution.return_value = None

        adapter = LangChainAdapter(model=mock_chat_model, prompt_repository=mock_prompt_repo)

        execution_data = {"tokens_used": 100, "success": True}

        await adapter._log_execution_with_retry(sample_prompt_template, execution_data)

        assert mock_prompt_repo.log_execution.call_count == 1
