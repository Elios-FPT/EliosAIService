"""FeedbackResponse domain entity."""

from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from .feedback_result import FeedbackResult


class FeedbackResponse(BaseModel):
    """Represents a feedback analysis response.

    Minimal design: Only stores typed result.
    NO cost/performance/version fields (reuse prompt_executions).

    1:1 relationship with FeedbackRequest.
    """

    # Identity
    id: UUID = Field(default_factory=uuid4)
    request_id: UUID = Field(description="Foreign key to feedback_request")

    # Type-safe result (deserialized via input_type from request)
    result: FeedbackResult = Field(description="Typed feedback result")

    # Audit
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        """Pydantic configuration."""

        frozen = True  # Immutable after creation

    def get_result_type(self) -> str:
        """Get result type name for debugging."""
        return type(self.result).__name__

