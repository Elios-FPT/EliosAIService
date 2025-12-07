"""FeedbackRequest domain entity."""

from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from .feedback_result import FeedbackStatus, InputType


class FeedbackRequest(BaseModel):
    """Represents a feedback analysis request.

    Minimal design: Only stores request metadata + error state.
    Cost/performance tracking done via prompt_executions table.

    Lifecycle:
    1. Created with status=PENDING
    2. Processing starts: status=PROCESSING
    3. If transient error: status=RETRYING (retry with backoff)
    4. If success: status=SUCCESS (response created)
    5. If permanent error: status=FAILED (error_message set)
    """

    # Identity
    id: UUID = Field(default_factory=uuid4)

    # Polymorphic entity reference
    entity_id: UUID = Field(description="ID of entity being analyzed (interview/cv/code)")
    input_type: InputType = Field(description="Type of entity (discriminator)")

    # Optional user context
    user_id: UUID | None = Field(default=None, description="User who requested analysis")

    # Status tracking
    status: FeedbackStatus = Field(default=FeedbackStatus.PENDING)

    # Failure tracking (ONLY this field added per requirements)
    error_message: str | None = Field(
        default=None,
        description="Human-readable error when status=FAILED",
    )

    # Content to be analyzed (for audit trail and direct submission)
    feedback_input: str = Field(
        description="Content to be analyzed (JSON string for INTERVIEW/CV, text for CODE)"
    )

    # Audit timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        """Pydantic configuration."""

        frozen = False  # Allow status updates

    def is_terminal_state(self) -> bool:
        """Check if request reached terminal state (SUCCESS or FAILED)."""
        return self.status in (FeedbackStatus.SUCCESS, FeedbackStatus.FAILED)

    def can_retry(self) -> bool:
        """Check if request can be retried (transient failure)."""
        return self.status == FeedbackStatus.RETRYING

