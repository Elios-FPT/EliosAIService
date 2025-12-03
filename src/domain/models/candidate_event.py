"""Candidate lifecycle event models."""

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel

from ...application.dto.event import EventWrapper


class EventType(str, Enum):
    """Candidate event types."""

    CREATED = "CREATED"
    UPDATED = "UPDATED"
    DELETED = "DELETED"


class CandidateEventPayload(BaseModel):
    """Payload for candidate lifecycle events."""

    UserId: UUID
    DeletedAt: datetime


class CandidateEvent(EventWrapper[CandidateEventPayload]):
    """Candidate lifecycle event from Kafka.

    Reuses the generic EventWrapper envelope to stay consistent with
    other Kafka events while keeping the same JSON shape:
    - EventId
    - CorrelationId
    - EventType
    - Payload
    """

