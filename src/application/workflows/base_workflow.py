"""Base workflow class for LangGraph workflows.

Provides common utilities and patterns for all workflows in the application.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any
from uuid import uuid4

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver


logger = logging.getLogger(__name__)


class BaseWorkflow(ABC):
    """Abstract base class for LangGraph workflows.

    Provides common functionality like thread ID generation,
    error formatting, and checkpoint management.
    """

    def __init__(self, checkpointer: AsyncPostgresSaver):
        """Initialize workflow with checkpointer.

        Args:
            checkpointer: AsyncPostgresSaver for state persistence
        """
        self.checkpointer = checkpointer

    @abstractmethod
    async def execute(self, *args, **kwargs) -> Any:
        """Execute the workflow.

        Subclasses must implement this method to define workflow logic.

        Returns:
            Workflow result (specific to each workflow)

        Raises:
            Exception: If workflow execution fails
        """
        pass

    def generate_thread_id(self, prefix: str = "") -> str:
        """Generate unique thread ID for workflow execution.

        Thread IDs are used to scope checkpoints and enable workflow resumption.

        Args:
            prefix: Optional prefix for the thread ID (e.g., "interview", "planning")

        Returns:
            Unique thread ID string

        Example:
            >>> thread_id = workflow.generate_thread_id("planning")
            >>> # thread_id: "planning_550e8400-e29b-41d4-a716-446655440000"
        """
        uuid_part = str(uuid4())
        if prefix:
            return f"{prefix}_{uuid_part}"
        return uuid_part

    def format_error(self, error: Exception, context: dict[str, Any] | None = None) -> str:
        """Format error message with context for logging/debugging.

        Args:
            error: Exception that occurred
            context: Optional context dict (e.g., state values, node name)

        Returns:
            Formatted error string

        Example:
            >>> error_msg = workflow.format_error(
            ...     ValueError("Invalid count"),
            ...     {"node": "calculate_count", "cv_id": "123"}
            ... )
        """
        error_type = type(error).__name__
        error_msg = str(error)

        if context:
            context_str = ", ".join([f"{k}={v}" for k, v in context.items()])
            return f"{error_type}: {error_msg} (Context: {context_str})"

        return f"{error_type}: {error_msg}"

    async def get_workflow_state(self, thread_id: str) -> dict[str, Any] | None:
        """Retrieve workflow state from checkpoint.

        Args:
            thread_id: Thread ID of the workflow execution

        Returns:
            Workflow state dict if checkpoint exists, None otherwise

        Example:
            >>> state = await workflow.get_workflow_state("planning_abc123")
            >>> if state:
            ...     print(f"Resuming from checkpoint: {state['checkpoint_id']}")
        """
        try:
            # Get latest checkpoint for thread
            checkpoint = await self.checkpointer.aget(thread_id)
            if checkpoint:
                return checkpoint.get("state")
            return None
        except Exception as e:
            logger.error(f"Failed to retrieve workflow state: {self.format_error(e)}")
            return None

    def should_retry(self, error: Exception, attempt: int, max_attempts: int = 3) -> bool:
        """Determine if operation should be retried based on error type.

        Args:
            error: Exception that occurred
            attempt: Current attempt number (1-indexed)
            max_attempts: Maximum retry attempts

        Returns:
            True if should retry, False otherwise

        Example:
            >>> if workflow.should_retry(rate_limit_error, attempt=2):
            ...     await asyncio.sleep(2 ** attempt)  # Exponential backoff
            ...     # Retry operation
        """
        if attempt >= max_attempts:
            return False

        # Retry on rate limits, timeouts, transient network errors
        retryable_errors = (
            "rate_limit",
            "timeout",
            "connection",
            "temporary",
            "503",  # Service unavailable
            "429",  # Too many requests
        )

        error_str = str(error).lower()
        return any(err in error_str for err in retryable_errors)

    def calculate_backoff_delay(self, attempt: int, base_delay: float = 1.0) -> float:
        """Calculate exponential backoff delay for retry attempts.

        Args:
            attempt: Current attempt number (1-indexed)
            base_delay: Base delay in seconds (default: 1.0)

        Returns:
            Delay in seconds

        Example:
            >>> delay = workflow.calculate_backoff_delay(attempt=3, base_delay=2.0)
            >>> # delay: 8.0 (2.0 * 2^3)
        """
        return base_delay * (2 ** attempt)
