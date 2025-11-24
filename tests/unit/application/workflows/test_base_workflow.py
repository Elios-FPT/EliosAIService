"""Unit tests for BaseWorkflow class."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

from src.application.workflows.base_workflow import BaseWorkflow


class ConcreteWorkflow(BaseWorkflow):
    """Concrete implementation of BaseWorkflow for testing."""

    async def execute(self, *args, **kwargs):
        """Concrete implementation of abstract execute method."""
        return {"result": "test"}


@pytest.fixture
def mock_checkpointer():
    """Create mock AsyncPostgresSaver."""
    checkpointer = MagicMock()
    checkpointer.aget = AsyncMock()
    checkpointer.aput = AsyncMock()
    return checkpointer


@pytest.fixture
def workflow(mock_checkpointer):
    """Create ConcreteWorkflow instance with mock checkpointer."""
    return ConcreteWorkflow(checkpointer=mock_checkpointer)


class TestBaseWorkflow:
    """Test suite for BaseWorkflow class."""

    def test_initialization(self, mock_checkpointer):
        """Test workflow initializes with checkpointer."""
        workflow = ConcreteWorkflow(checkpointer=mock_checkpointer)
        assert workflow.checkpointer == mock_checkpointer

    async def test_execute_is_abstract(self, mock_checkpointer):
        """Test that execute method must be implemented."""
        # ConcreteWorkflow implements execute, so it should work
        workflow = ConcreteWorkflow(checkpointer=mock_checkpointer)
        result = await workflow.execute()
        assert result == {"result": "test"}

    def test_generate_thread_id_no_prefix(self, workflow):
        """Test thread ID generation without prefix."""
        thread_id = workflow.generate_thread_id()

        # Should be a valid UUID string
        assert isinstance(thread_id, str)
        assert len(thread_id) == 36  # UUID format: 8-4-4-4-12

        # Verify it's a valid UUID
        try:
            UUID(thread_id)
        except ValueError:
            pytest.fail("Generated thread_id is not a valid UUID")

    def test_generate_thread_id_with_prefix(self, workflow):
        """Test thread ID generation with prefix."""
        thread_id = workflow.generate_thread_id(prefix="planning")

        # Should start with prefix
        assert thread_id.startswith("planning_")

        # Should have UUID after prefix
        uuid_part = thread_id.split("_", 1)[1]
        assert len(uuid_part) == 36

        # Verify UUID part is valid
        try:
            UUID(uuid_part)
        except ValueError:
            pytest.fail("Generated UUID part is not valid")

    def test_generate_thread_id_uniqueness(self, workflow):
        """Test that generated thread IDs are unique."""
        thread_ids = [workflow.generate_thread_id("test") for _ in range(100)]

        # All IDs should be unique
        assert len(thread_ids) == len(set(thread_ids))

    def test_format_error_without_context(self, workflow):
        """Test error formatting without context."""
        error = ValueError("Invalid count")
        formatted = workflow.format_error(error)

        assert formatted == "ValueError: Invalid count"

    def test_format_error_with_context(self, workflow):
        """Test error formatting with context."""
        error = ValueError("Invalid count")
        context = {"node": "calculate_count", "cv_id": "123"}
        formatted = workflow.format_error(error, context)

        assert "ValueError: Invalid count" in formatted
        assert "node=calculate_count" in formatted
        assert "cv_id=123" in formatted

    def test_format_error_with_empty_context(self, workflow):
        """Test error formatting with empty context dict."""
        error = RuntimeError("Test error")
        formatted = workflow.format_error(error, {})

        assert formatted == "RuntimeError: Test error"

    async def test_get_workflow_state_exists(self, workflow, mock_checkpointer):
        """Test retrieving existing workflow state."""
        # Mock checkpoint retrieval
        mock_checkpointer.aget.return_value = {
            "state": {"cv_analysis_id": "test-id", "question_count": 5}
        }

        state = await workflow.get_workflow_state("thread_123")

        assert state == {"cv_analysis_id": "test-id", "question_count": 5}
        mock_checkpointer.aget.assert_called_once_with("thread_123")

    async def test_get_workflow_state_not_exists(self, workflow, mock_checkpointer):
        """Test retrieving non-existent workflow state."""
        mock_checkpointer.aget.return_value = None

        state = await workflow.get_workflow_state("thread_456")

        assert state is None
        mock_checkpointer.aget.assert_called_once_with("thread_456")

    async def test_get_workflow_state_error(self, workflow, mock_checkpointer):
        """Test error handling when retrieving workflow state."""
        mock_checkpointer.aget.side_effect = Exception("Database error")

        state = await workflow.get_workflow_state("thread_789")

        # Should return None on error
        assert state is None

    def test_should_retry_within_max_attempts(self, workflow):
        """Test retry decision within max attempts."""
        # Retryable errors (matching the patterns in base_workflow.py)
        rate_limit_error = Exception("rate_limit exceeded")
        timeout_error = Exception("connection timeout")
        temp_error = Exception("temporary failure")
        http_503_error = Exception("HTTP 503 Service Unavailable")
        http_429_error = Exception("HTTP 429 Too Many Requests")

        assert workflow.should_retry(rate_limit_error, attempt=1) is True
        assert workflow.should_retry(timeout_error, attempt=2) is True
        assert workflow.should_retry(temp_error, attempt=1) is True
        assert workflow.should_retry(http_503_error, attempt=2) is True
        assert workflow.should_retry(http_429_error, attempt=1) is True

    def test_should_retry_max_attempts_exceeded(self, workflow):
        """Test retry decision when max attempts exceeded."""
        error = Exception("Rate limit exceeded")

        # Should not retry when attempt >= max_attempts
        assert workflow.should_retry(error, attempt=3, max_attempts=3) is False
        assert workflow.should_retry(error, attempt=4, max_attempts=3) is False

    def test_should_retry_non_retryable_error(self, workflow):
        """Test retry decision for non-retryable errors."""
        validation_error = Exception("Invalid input data")
        not_found_error = Exception("Resource not found")

        assert workflow.should_retry(validation_error, attempt=1) is False
        assert workflow.should_retry(not_found_error, attempt=1) is False

    def test_should_retry_case_insensitive(self, workflow):
        """Test that error matching is case-insensitive."""
        error_upper = Exception("RATE_LIMIT EXCEEDED")
        error_mixed = Exception("Connection TIMEOUT")

        assert workflow.should_retry(error_upper, attempt=1) is True
        assert workflow.should_retry(error_mixed, attempt=1) is True

    def test_calculate_backoff_delay_default(self, workflow):
        """Test exponential backoff calculation with default base."""
        # Default base_delay = 1.0
        assert workflow.calculate_backoff_delay(attempt=1) == 2.0  # 1.0 * 2^1
        assert workflow.calculate_backoff_delay(attempt=2) == 4.0  # 1.0 * 2^2
        assert workflow.calculate_backoff_delay(attempt=3) == 8.0  # 1.0 * 2^3
        assert workflow.calculate_backoff_delay(attempt=4) == 16.0  # 1.0 * 2^4

    def test_calculate_backoff_delay_custom_base(self, workflow):
        """Test exponential backoff calculation with custom base."""
        base_delay = 2.0

        assert workflow.calculate_backoff_delay(attempt=1, base_delay=base_delay) == 4.0
        assert workflow.calculate_backoff_delay(attempt=2, base_delay=base_delay) == 8.0
        assert workflow.calculate_backoff_delay(attempt=3, base_delay=base_delay) == 16.0

    def test_calculate_backoff_delay_zero_attempt(self, workflow):
        """Test exponential backoff with attempt=0."""
        # 2^0 = 1, so delay should equal base_delay
        assert workflow.calculate_backoff_delay(attempt=0, base_delay=5.0) == 5.0
