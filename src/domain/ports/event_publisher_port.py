"""Event publisher port interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from ..models.feedback_result import FeedbackResult


class EventPublisherPort(ABC):
    """Interface for publishing domain events to message brokers.

    Abstracts event publishing (Kafka, RabbitMQ, SNS, etc.) following
    fire-and-forget pattern. Failures should be logged but not block business logic.
    """

    @abstractmethod
    async def publish_interview_attempted(
        self,
        candidate_id: UUID,
        interview_id: UUID,
        correlation_id: UUID,
        overall_score: float,
        theoretical_score_avg: float,
        speaking_score_avg: float,
    ) -> None:
        """Publish INTERVIEW_ATTEMPTED event to User Service.

        Args:
            candidate_id: Candidate UUID (maps to UserId in downstream services)
            interview_id: Interview UUID
            correlation_id: Request correlation ID for tracing
            overall_score: Weighted overall score (0-100)
            theoretical_score_avg: Theoretical score average (0-100)
            speaking_score_avg: Speaking score average (0-100)

        Note:
            This method should NOT raise exceptions (fire-and-forget).
            Errors should be logged and swallowed.
        """
        pass

    @abstractmethod
    async def publish_feedback_completed(
        self,
        request_id: UUID,
        entity_id: UUID,
        input_type: str,  # InputType enum value as string
        user_id: UUID | None,
        result: FeedbackResult,
        correlation_id: UUID,
    ) -> None:
        """Publish FEEDBACK_COMPLETED event to Kafka.

        Args:
            request_id: Feedback request UUID
            entity_id: Entity UUID that was analyzed
            input_type: Type of entity (INTERVIEW/CV/CODE)
            user_id: Optional user who requested analysis
            result: Typed feedback result
            correlation_id: Request correlation ID for tracing

        Note:
            This method should NOT raise exceptions (fire-and-forget).
            Errors should be logged and swallowed.
        """
        pass
