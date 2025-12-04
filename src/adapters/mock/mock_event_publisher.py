"""Mock event publisher adapter for testing."""

import logging
from uuid import UUID

from ...domain.models.feedback_result import FeedbackResult
from ...domain.ports.event_publisher_port import EventPublisherPort

logger = logging.getLogger(__name__)


class MockEventPublisher(EventPublisherPort):
    """Mock event publisher for development and testing.

    Logs events instead of publishing to real message broker.
    Stores published events in memory for test assertions.
    """

    def __init__(self):
        """Initialize mock publisher with empty event store."""
        self.published_events: list[dict] = []
        logger.info("MockEventPublisher initialized")

    async def publish_interview_attempted(
        self,
        candidate_id: UUID,
        interview_id: UUID,
        correlation_id: UUID,
        overall_score: float,
        theoretical_score_avg: float,
        speaking_score_avg: float,
    ) -> None:
        """Log event and store in memory (no actual publish).

        Args:
            candidate_id: Candidate UUID
            interview_id: Interview UUID
            correlation_id: Correlation ID
            overall_score: Overall score
            theoretical_score_avg: Theoretical score
            speaking_score_avg: Speaking score
        """
        event_data = {
            "event_type": "INTERVIEW_ATTEMPTED",
            "candidate_id": str(candidate_id),
            "interview_id": str(interview_id),
            "correlation_id": str(correlation_id),
            "overall_score": round(overall_score, 2),
            "theoretical_score_avg": round(theoretical_score_avg, 2),
            "speaking_score_avg": round(speaking_score_avg, 2),
        }

        self.published_events.append(event_data)

        logger.info(
            "MockEventPublisher: INTERVIEW_ATTEMPTED event",
            extra={
                "interview_id": str(interview_id),
                "candidate_id": str(candidate_id),
                "overall_score": event_data["overall_score"],
            }
        )

    def clear_events(self) -> None:
        """Clear stored events (for test cleanup)."""
        self.published_events.clear()

    def get_events(self, event_type: str | None = None) -> list[dict]:
        """Get published events, optionally filtered by type.

        Args:
            event_type: Optional event type filter

        Returns:
            List of published event dictionaries
        """
        if event_type is None:
            return self.published_events.copy()
        return [e for e in self.published_events if e["event_type"] == event_type]

    async def publish_feedback_completed(
        self,
        request_id: UUID,
        entity_id: UUID,
        input_type: str,
        user_id: UUID | None,
        result: FeedbackResult,
        correlation_id: UUID,
    ) -> None:
        """Log event and store in memory (no actual publish).

        Args:
            request_id: Feedback request UUID
            entity_id: Entity UUID
            input_type: Type of entity (INTERVIEW/CV/CODE)
            user_id: User UUID (nullable)
            result: Feedback result model
            correlation_id: Correlation ID

        Note:
            Mock implementation - no actual Kafka publishing.
        """
        event_data = {
            "event_type": "FEEDBACK_COMPLETED",
            "request_id": str(request_id),
            "entity_id": str(entity_id),
            "input_type": input_type,
            "user_id": str(user_id) if user_id else None,
            "correlation_id": str(correlation_id),
            "result": result.model_dump(mode="json"),
        }

        self.published_events.append(event_data)

        logger.info(
            "MockEventPublisher: FEEDBACK_COMPLETED event",
            extra={
                "request_id": str(request_id),
                "entity_id": str(entity_id),
                "input_type": input_type,
                "user_id": str(user_id) if user_id else None,
                "correlation_id": str(correlation_id),
            },
        )

    async def publish_token_delta(
        self,
        user_id: UUID,
        tokens: int,
        correlation_id: UUID,
    ) -> None:
        """Log token delta event and store in memory."""
        event_data = {
            "event_type": "TOKEN_DELTA",
            "user_id": str(user_id),
            "tokens": tokens,
            "correlation_id": str(correlation_id),
        }

        self.published_events.append(event_data)

        logger.info(
            "MockEventPublisher: TOKEN_DELTA event",
            extra={
                "user_id": str(user_id),
                "tokens": tokens,
                "correlation_id": str(correlation_id),
            },
        )

