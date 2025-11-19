"""Unit tests for PromptExecution domain model."""

import pytest
from uuid import uuid4

from src.domain.models.prompt_execution import PromptExecution


def test_prompt_execution_creation():
    """Test creating a valid prompt execution."""
    prompt_id = uuid4()
    interview_id = uuid4()
    candidate_id = uuid4()

    execution = PromptExecution(
        prompt_template_id=prompt_id,
        interview_id=interview_id,
        candidate_id=candidate_id,
        input_variables={"skill": "Python", "difficulty": "medium"},
        output_text="Generated question text...",
        prompt_tokens=150,
        completion_tokens=300,
        latency_ms=1500,
        model_name="gpt-4",
        success=True,
    )

    assert execution.prompt_template_id == prompt_id
    assert execution.interview_id == interview_id
    assert execution.candidate_id == candidate_id
    assert execution.input_variables["skill"] == "Python"
    assert execution.output_text == "Generated question text..."
    assert execution.prompt_tokens == 150
    assert execution.completion_tokens == 300
    assert execution.latency_ms == 1500
    assert execution.model_name == "gpt-4"
    assert execution.success is True


def test_calculate_estimated_cost():
    """Test cost calculation with OpenAI pricing."""
    prompt_id = uuid4()

    execution = PromptExecution(
        prompt_template_id=prompt_id,
        input_variables={},
        latency_ms=1000,
        success=True,
        prompt_tokens=1000,  # 1k tokens
        completion_tokens=2000,  # 2k tokens
    )

    cost = execution.calculate_estimated_cost()

    # Expected: (1000 * 0.03 / 1000) + (2000 * 0.06 / 1000) = 0.03 + 0.12 = 0.15
    assert cost == pytest.approx(0.15)


def test_calculate_cost_with_no_tokens():
    """Test cost calculation when tokens are missing."""
    prompt_id = uuid4()

    execution = PromptExecution(
        prompt_template_id=prompt_id,
        input_variables={},
        latency_ms=1000,
        success=True,
    )

    cost = execution.calculate_estimated_cost()
    assert cost == 0.0


def test_calculate_cost_partial_tokens():
    """Test cost calculation with only prompt tokens."""
    prompt_id = uuid4()

    execution = PromptExecution(
        prompt_template_id=prompt_id,
        input_variables={},
        latency_ms=1000,
        success=True,
        prompt_tokens=1000,
        completion_tokens=None,
    )

    cost = execution.calculate_estimated_cost()
    assert cost == 0.0


def test_calculate_cost_realistic_example():
    """Test cost calculation with realistic values."""
    prompt_id = uuid4()

    execution = PromptExecution(
        prompt_template_id=prompt_id,
        input_variables={"skill": "Python"},
        latency_ms=2500,
        success=True,
        prompt_tokens=500,
        completion_tokens=150,
    )

    cost = execution.calculate_estimated_cost()

    # Expected: (500 * 0.03 / 1000) + (150 * 0.06 / 1000) = 0.015 + 0.009 = 0.024
    assert cost == pytest.approx(0.024)


def test_failed_execution():
    """Test creating a failed execution with error message."""
    prompt_id = uuid4()

    execution = PromptExecution(
        prompt_template_id=prompt_id,
        input_variables={"skill": "Python"},
        latency_ms=500,
        success=False,
        error_message="OpenAI API rate limit exceeded",
    )

    assert execution.success is False
    assert execution.error_message == "OpenAI API rate limit exceeded"
    assert execution.output_text is None


def test_tokens_used_field():
    """Test tokens_used field (fallback when prompt/completion missing)."""
    prompt_id = uuid4()

    execution = PromptExecution(
        prompt_template_id=prompt_id,
        input_variables={},
        latency_ms=1000,
        success=True,
        tokens_used=450,
    )

    assert execution.tokens_used == 450


def test_latency_validation():
    """Test latency_ms must be >= 0."""
    prompt_id = uuid4()

    # Valid latency
    execution = PromptExecution(
        prompt_template_id=prompt_id,
        input_variables={},
        latency_ms=0,
        success=True,
    )
    assert execution.latency_ms == 0

    # Invalid latency (< 0)
    with pytest.raises(ValueError):
        PromptExecution(
            prompt_template_id=prompt_id,
            input_variables={},
            latency_ms=-100,
            success=True,
        )


def test_executed_at_auto_set():
    """Test that executed_at is automatically set."""
    prompt_id = uuid4()

    execution = PromptExecution(
        prompt_template_id=prompt_id,
        input_variables={},
        latency_ms=1000,
        success=True,
    )

    assert execution.executed_at is not None


def test_id_auto_generated():
    """Test that ID is automatically generated."""
    prompt_id = uuid4()

    execution = PromptExecution(
        prompt_template_id=prompt_id,
        input_variables={},
        latency_ms=1000,
        success=True,
    )

    assert execution.id is not None
