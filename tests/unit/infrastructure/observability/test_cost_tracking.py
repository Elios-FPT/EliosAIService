"""Unit tests for cost tracking utilities."""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from uuid import UUID

from src.infrastructure.observability.cost_tracking import (
    calculate_cost_from_tokens,
    _normalize_model_name,
    get_interview_cost,
    get_daily_cost_summary,
    TOKEN_PRICING,
)


class TestCalculateCostFromTokens:
    """Test token cost calculation."""

    def test_gpt4_cost_calculation(self):
        """Test GPT-4 cost calculation."""
        # GPT-4: $0.03/1K input, $0.06/1K output
        cost = calculate_cost_from_tokens(
            model_name="gpt-4",
            input_tokens=1000,
            output_tokens=500,
        )

        # (1000/1000 * 0.03) + (500/1000 * 0.06) = 0.03 + 0.03 = 0.06
        assert cost == 0.06

    def test_gpt4_turbo_cost_calculation(self):
        """Test GPT-4 Turbo cost calculation."""
        # GPT-4 Turbo: $0.01/1K input, $0.03/1K output
        cost = calculate_cost_from_tokens(
            model_name="gpt-4-turbo",
            input_tokens=2000,
            output_tokens=1000,
        )

        # (2000/1000 * 0.01) + (1000/1000 * 0.03) = 0.02 + 0.03 = 0.05
        assert cost == 0.05

    def test_gpt35_turbo_cost_calculation(self):
        """Test GPT-3.5 Turbo cost calculation."""
        # GPT-3.5 Turbo: $0.0005/1K input, $0.0015/1K output
        cost = calculate_cost_from_tokens(
            model_name="gpt-3.5-turbo",
            input_tokens=10000,
            output_tokens=5000,
        )

        # (10000/1000 * 0.0005) + (5000/1000 * 0.0015) = 0.005 + 0.0075 = 0.0125
        assert cost == 0.0125

    def test_claude_opus_cost_calculation(self):
        """Test Claude Opus cost calculation."""
        # Claude Opus: $0.015/1K input, $0.075/1K output
        cost = calculate_cost_from_tokens(
            model_name="claude-3-opus",
            input_tokens=1000,
            output_tokens=1000,
        )

        # (1000/1000 * 0.015) + (1000/1000 * 0.075) = 0.015 + 0.075 = 0.09
        assert cost == 0.09

    def test_claude_sonnet_cost_calculation(self):
        """Test Claude Sonnet cost calculation."""
        # Claude Sonnet: $0.003/1K input, $0.015/1K output
        cost = calculate_cost_from_tokens(
            model_name="claude-3-sonnet",
            input_tokens=5000,
            output_tokens=2000,
        )

        # (5000/1000 * 0.003) + (2000/1000 * 0.015) = 0.015 + 0.03 = 0.045
        assert cost == 0.045

    def test_unknown_model_defaults_to_gpt4(self):
        """Test unknown model defaults to GPT-4 pricing."""
        cost = calculate_cost_from_tokens(
            model_name="unknown-model-xyz",
            input_tokens=1000,
            output_tokens=500,
        )

        # Should use GPT-4 pricing
        expected = calculate_cost_from_tokens("gpt-4", 1000, 500)
        assert cost == expected

    def test_total_tokens_fallback(self):
        """Test fallback to total_tokens when input/output not provided."""
        cost = calculate_cost_from_tokens(
            model_name="gpt-4",
            total_tokens=1000,
        )

        # Should assume 70% input, 30% output
        # (700/1000 * 0.03) + (300/1000 * 0.06) = 0.021 + 0.018 = 0.039
        assert cost == 0.039

    def test_zero_tokens(self):
        """Test zero token cost."""
        cost = calculate_cost_from_tokens(
            model_name="gpt-4",
            input_tokens=0,
            output_tokens=0,
        )

        assert cost == 0.0

    def test_large_token_count(self):
        """Test large token counts."""
        cost = calculate_cost_from_tokens(
            model_name="gpt-4",
            input_tokens=100000,
            output_tokens=50000,
        )

        # (100000/1000 * 0.03) + (50000/1000 * 0.06) = 3.0 + 3.0 = 6.0
        assert cost == 6.0

    def test_fractional_tokens(self):
        """Test fractional token counts."""
        cost = calculate_cost_from_tokens(
            model_name="gpt-3.5-turbo",
            input_tokens=150,
            output_tokens=75,
        )

        # (150/1000 * 0.0005) + (75/1000 * 0.0015) = 0.000075 + 0.0001125 = 0.0001875
        # Rounded to 4 decimal places = 0.0002
        assert cost == 0.0002


class TestNormalizeModelName:
    """Test model name normalization."""

    def test_normalize_gpt4_variants(self):
        """Test GPT-4 variant normalization."""
        assert _normalize_model_name("gpt-4") == "gpt-4"
        assert _normalize_model_name("gpt-4-0613") == "gpt-4"
        assert _normalize_model_name("GPT-4-0314") == "gpt-4"

    def test_normalize_gpt4_turbo_variants(self):
        """Test GPT-4 Turbo variant normalization."""
        assert _normalize_model_name("gpt-4-turbo") == "gpt-4-turbo"
        assert _normalize_model_name("gpt-4-1106-preview") == "gpt-4-turbo"
        assert _normalize_model_name("GPT-4-TURBO-preview") == "gpt-4-turbo"

    def test_normalize_gpt35_variants(self):
        """Test GPT-3.5 variant normalization."""
        assert _normalize_model_name("gpt-3.5-turbo") == "gpt-3.5-turbo"
        assert _normalize_model_name("gpt-3.5-turbo-16k") == "gpt-3.5-turbo"

    def test_normalize_claude_variants(self):
        """Test Claude variant normalization."""
        assert _normalize_model_name("claude-3-opus-20240229") == "claude-3-opus"
        assert _normalize_model_name("claude-3-sonnet-20240229") == "claude-3-sonnet"
        assert _normalize_model_name("claude-3-haiku-20240307") == "claude-3-haiku"

    def test_normalize_llama_variants(self):
        """Test Llama variant normalization."""
        assert _normalize_model_name("llama-3-70b-instruct") == "llama-3-70b"
        assert _normalize_model_name("meta-llama-3-70b") == "llama-3-70b"

    def test_normalize_unknown_defaults_to_gpt4(self):
        """Test unknown model defaults to gpt-4."""
        assert _normalize_model_name("completely-unknown-model") == "gpt-4"


@pytest.mark.asyncio
class TestGetInterviewCost:
    """Test get_interview_cost function."""

    @patch("langsmith.Client")
    async def test_get_interview_cost_success(self, mock_client_class):
        """Test successful interview cost retrieval."""
        # Mock LangSmith client
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        # Mock run data
        mock_run = Mock()
        mock_run.total_tokens = 1000
        mock_run.prompt_tokens = 700
        mock_run.completion_tokens = 300
        mock_run.extra = {"invocation_params": {"model_name": "gpt-4"}}

        mock_client.list_runs.return_value = [mock_run]

        # Call function
        interview_id = UUID("123e4567-e89b-12d3-a456-426614174000")
        result = await get_interview_cost(
            interview_id=interview_id,
            langsmith_api_key="test-key",
            project_name="test-project",
        )

        # Verify result
        assert result["total_tokens"] == 1000
        assert result["input_tokens"] == 700
        assert result["output_tokens"] == 300
        assert result["trace_count"] == 1
        assert result["total_cost_usd"] > 0
        assert "gpt-4" in result["model_breakdown"]

    @patch("langsmith.Client")
    async def test_get_interview_cost_no_traces(self, mock_client_class):
        """Test interview cost with no traces found."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client.list_runs.return_value = []

        interview_id = UUID("123e4567-e89b-12d3-a456-426614174000")
        result = await get_interview_cost(
            interview_id=interview_id,
            langsmith_api_key="test-key",
        )

        assert result["total_tokens"] == 0
        assert result["total_cost_usd"] == 0.0
        assert result["trace_count"] == 0

    @patch("langsmith.Client")
    async def test_get_interview_cost_multiple_models(self, mock_client_class):
        """Test interview cost with multiple models."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        # Create runs with different models
        run1 = Mock()
        run1.total_tokens = 1000
        run1.prompt_tokens = 700
        run1.completion_tokens = 300
        run1.extra = {"invocation_params": {"model_name": "gpt-4"}}

        run2 = Mock()
        run2.total_tokens = 2000
        run2.prompt_tokens = 1400
        run2.completion_tokens = 600
        run2.extra = {"invocation_params": {"model_name": "claude-3-sonnet"}}

        mock_client.list_runs.return_value = [run1, run2]

        interview_id = UUID("123e4567-e89b-12d3-a456-426614174000")
        result = await get_interview_cost(
            interview_id=interview_id,
            langsmith_api_key="test-key",
        )

        assert result["total_tokens"] == 3000
        assert result["trace_count"] == 2
        assert "gpt-4" in result["model_breakdown"]
        assert "claude-3-sonnet" in result["model_breakdown"]

    async def test_get_interview_cost_langsmith_not_installed(self):
        """Test error when langsmith package not installed."""
        with patch("langsmith.Client", side_effect=ImportError):
            interview_id = UUID("123e4567-e89b-12d3-a456-426614174000")
            result = await get_interview_cost(
                interview_id=interview_id,
                langsmith_api_key="test-key",
            )

            assert "error" in result
            assert "langsmith package not installed" in result["error"]


@pytest.mark.asyncio
class TestGetDailyCostSummary:
    """Test get_daily_cost_summary function."""

    @patch("langsmith.Client")
    async def test_get_daily_cost_summary_success(self, mock_client_class):
        """Test successful daily cost summary."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        # Mock multiple runs with interview metadata
        runs = []
        for i in range(5):
            run = Mock()
            run.total_tokens = 1000
            run.prompt_tokens = 700
            run.completion_tokens = 300
            run.metadata = {"interview_id": f"interview-{i % 2}"}  # 2 unique interviews
            run.extra = {"invocation_params": {"model_name": "gpt-4"}}
            runs.append(run)

        mock_client.list_runs.return_value = runs

        result = await get_daily_cost_summary(
            langsmith_api_key="test-key",
            project_name="test-project",
            days=1,
        )

        assert result["total_tokens"] == 5000
        assert result["total_traces"] == 5
        assert result["interviews_count"] == 2  # 2 unique interview IDs
        assert result["total_cost_usd"] > 0
        assert result["avg_cost_per_interview"] > 0

    @patch("langsmith.Client")
    async def test_get_daily_cost_summary_no_data(self, mock_client_class):
        """Test daily cost summary with no data."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client.list_runs.return_value = []

        result = await get_daily_cost_summary(
            langsmith_api_key="test-key",
            days=7,
        )

        assert result["total_tokens"] == 0
        assert result["total_cost_usd"] == 0.0
        assert result["interviews_count"] == 0
        assert result["avg_cost_per_interview"] == 0.0

    async def test_get_daily_cost_summary_error_handling(self):
        """Test error handling in daily cost summary."""
        with patch("langsmith.Client", side_effect=Exception("API Error")):
            result = await get_daily_cost_summary(
                langsmith_api_key="test-key",
            )

            assert "error" in result


class TestTokenPricingData:
    """Test TOKEN_PRICING data structure."""

    def test_all_models_have_input_output_pricing(self):
        """Verify all models have input and output pricing."""
        for model, pricing in TOKEN_PRICING.items():
            assert "input" in pricing, f"Model {model} missing input pricing"
            assert "output" in pricing, f"Model {model} missing output pricing"
            assert pricing["input"] > 0, f"Model {model} input pricing must be positive"
            assert pricing["output"] > 0, f"Model {model} output pricing must be positive"

    def test_output_pricing_higher_than_input(self):
        """Verify output pricing is typically higher than input (except llama)."""
        for model, pricing in TOKEN_PRICING.items():
            if "llama" not in model:  # Llama has equal pricing
                assert pricing["output"] >= pricing["input"], f"Model {model} output should be >= input"
