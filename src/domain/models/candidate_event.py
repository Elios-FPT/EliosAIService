"""Candidate lifecycle event models."""

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel


class EventType(str, Enum):
    """Candidate event types."""

    CREATED = "CREATED"
    UPDATED = "UPDATED"
    DELETED = "DELETED"


class CandidateEventPayload(BaseModel):
    """Payload for candidate lifecycle events."""

    UserId: UUID
    DeletedAt: datetime


class CandidateEvent(BaseModel):
    """Candidate lifecycle event from Kafka."""

    EventId: UUID
    CorrelationId: UUID
    EventType: EventType
    Payload: CandidateEventPayload


