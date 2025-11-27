"""Mock event publisher adapter for testing."""

import logging
from uuid import UUID

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

