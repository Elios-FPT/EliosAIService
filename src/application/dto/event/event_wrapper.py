"""Generic event wrapper for Kafka messages."""

from uuid import UUID, uuid4
from pydantic import BaseModel, Field
from typing import Generic, TypeVar

PayloadType = TypeVar("PayloadType", bound=BaseModel)


class EventWrapper(BaseModel, Generic[PayloadType]):
    """Generic event envelope for Kafka messages.

    Follows domain event pattern with correlation tracking.
    Compatible with User Service event schema.

    Attributes:
        event_id: Unique event identifier (auto-generated)
        correlation_id: Request correlation ID for tracing
        event_type: Event type discriminator (e.g., INTERVIEW_ATTEMPTED)
        payload: Typed payload data
    """

    event_id: UUID = Field(
        default_factory=uuid4,
        alias="EventId",
        description="Unique event identifier"
    )
    correlation_id: UUID = Field(
        alias="CorrelationId",
        description="Correlation ID for request tracing"
    )
    event_type: str = Field(
        alias="EventType",
        description="Event type discriminator"
    )
    payload: PayloadType = Field(
        alias="Payload",
        description="Event payload data"
    )

    model_config = {
        "populate_by_name": True,  # Allow both snake_case and PascalCase
        "json_schema_extra": {
            "example": {
                "EventId": "7238f489-70a2-4ad6-8b43-ede743803c66",
                "CorrelationId": "17c186a6-2140-413e-b1fb-a24af8d12085",
                "EventType": "INTERVIEW_ATTEMPTED",
                "Payload": {}
            }
        }
    }

