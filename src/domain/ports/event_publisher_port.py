"""Event publisher port interface."""

from abc import ABC, abstractmethod
from uuid import UUID


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
            candidate_id: Candidate UUID (maps to UserId)
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

