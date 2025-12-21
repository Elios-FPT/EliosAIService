"""Payload DTOs for token confirmation responses from User Service."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class TokenResponsePayload(BaseModel):
    """Payload for successful token operations.

    Maps User Service response payload structure.
    """

    processed_at: datetime = Field(alias="processedAt")
    success: bool
    new_balance: Decimal = Field(alias="newBalance")
    user_id: UUID = Field(alias="userId")

    model_config = {"populate_by_name": True}


class TokenResponseEnvelope(BaseModel):
    """Complete token response message envelope.

    Matches User Service Kafka message format.
    """

    event_id: UUID = Field(alias="EventId")
    correlation_id: UUID = Field(alias="CorrelationId")
    event_type: str = Field(alias="EventType")
    payload: TokenResponsePayload | None = Field(alias="Payload", default=None)
    success: bool = Field(alias="Success")
    error_message: str | None = Field(alias="ErrorMessage", default=None)

    model_config = {"populate_by_name": True}

    def is_success(self) -> bool:
        """Check if token operation succeeded."""
        return self.success and self.payload is not None

    def get_error_detail(self) -> str:
        """Get error message for failed operations."""
        if self.error_message:
            return self.error_message
        return "Token operation failed (unknown error)"
