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
            ...     print(f"Resuming from checkpoint: {state.get('checkpoint_thread_id')}")
        """
        try:
            # Use config dict format (required by LangGraph checkpointer API)
            config: dict[str, Any] = {"configurable": {"thread_id": thread_id}}

            # Get latest checkpoint for thread
            # checkpointer.aget() returns a StateSnapshot or None
            checkpoint = await self.checkpointer.aget(config)

            if checkpoint is None:
                logger.debug(f"No checkpoint found for thread {thread_id}")
                return None

            # Handle StateSnapshot object or dict
            # StateSnapshot from LangGraph has the state accessible via .values property
            # Note: If checkpoint.values() returns dict_values, the checkpoint itself might be dict-like
            # Try multiple ways to access the state
            state = None

            # Method 1: Check if checkpoint has a direct 'state' attribute
            if hasattr(checkpoint, "state"):
                state_attr = getattr(checkpoint, "state")
                if isinstance(state_attr, dict):
                    return state_attr

            # Method 2: Try accessing .values as a property (not calling it)
            if hasattr(checkpoint, "values"):
                values_attr = getattr(checkpoint, "values")
                # Check if it's a property (not callable) or if calling it gives us what we need
                if not callable(values_attr):
                    # It's a property - use it directly
                    if isinstance(values_attr, dict):
                        return values_attr
                else:
                    # It's callable - try calling it, but handle dict_values return
                    try:
                        if hasattr(values_attr, "__await__"):
                            state_result = await values_attr()
                        else:
                            state_result = values_attr()

                        # If it returns dict_values, the checkpoint itself might be the state dict
                        if isinstance(state_result, dict):
                            return state_result
                        # If it's dict_values, try accessing checkpoint as dict
                        elif type(state_result).__name__ == "dict_values":
                            # The checkpoint might be dict-like - try to access it as dict
                            if isinstance(checkpoint, dict):
                                return checkpoint
                            # Or try to get state from checkpoint attributes
                            if hasattr(checkpoint, "state"):
                                state_attr = getattr(checkpoint, "state")
                                if isinstance(state_attr, dict):
                                    return state_attr
                    except Exception as e:
                        logger.debug(f"Error calling checkpoint.values(): {e}")

            # Method 3: If checkpoint is itself a dict, return it
            if isinstance(checkpoint, dict):
                # Check if it has a 'state' key
                if "state" in checkpoint:
                    return checkpoint["state"]
                # Otherwise, the checkpoint itself might be the state
                return checkpoint

            # Method 4: Try to convert StateSnapshot to dict if it's dict-like
            if hasattr(checkpoint, "__dict__"):
                checkpoint_dict = checkpoint.__dict__
                if "state" in checkpoint_dict and isinstance(checkpoint_dict["state"], dict):
                    return checkpoint_dict["state"]
                # Check if the checkpoint dict itself looks like state
                if isinstance(checkpoint_dict, dict) and "interview_id" in checkpoint_dict:
                    return checkpoint_dict

            # If we get here, we couldn't extract the state
            logger.warning(
                f"Could not extract state from checkpoint. "
                f"Type: {type(checkpoint)}, "
                f"Has values: {hasattr(checkpoint, 'values')}, "
                f"Has state: {hasattr(checkpoint, 'state')}, "
                f"Is dict: {isinstance(checkpoint, dict)}"
            )
            return None

        except Exception as e:
            logger.error(
                f"Failed to retrieve workflow state for thread {thread_id}: {self.format_error(e)}",
                exc_info=True
            )
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
