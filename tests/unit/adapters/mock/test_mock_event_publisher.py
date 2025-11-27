"""Unit tests for MockEventPublisher."""

import pytest
from uuid import uuid4

from src.adapters.mock.mock_event_publisher import MockEventPublisher


@pytest.mark.asyncio
async def test_mock_publishes_and_stores_event():
    """Test mock publisher stores events in memory."""
    publisher = MockEventPublisher()
    candidate_id = uuid4()
    interview_id = uuid4()
    correlation_id = uuid4()

    await publisher.publish_interview_attempted(
        candidate_id=candidate_id,
        interview_id=interview_id,
        correlation_id=correlation_id,
        overall_score=75.5,
        theoretical_score_avg=80.0,
        speaking_score_avg=60.0,
    )

    events = publisher.get_events("INTERVIEW_ATTEMPTED")
    assert len(events) == 1
    assert events[0]["event_type"] == "INTERVIEW_ATTEMPTED"
    assert events[0]["interview_id"] == str(interview_id)
    assert events[0]["candidate_id"] == str(candidate_id)
    assert events[0]["overall_score"] == 75.5


@pytest.mark.asyncio
async def test_mock_clear_events():
    """Test clear_events removes stored events."""
    publisher = MockEventPublisher()

    await publisher.publish_interview_attempted(
        candidate_id=uuid4(),
        interview_id=uuid4(),
        correlation_id=uuid4(),
        overall_score=75.0,
        theoretical_score_avg=80.0,
        speaking_score_avg=60.0,
    )

    assert len(publisher.published_events) == 1

    publisher.clear_events()
    assert len(publisher.published_events) == 0

