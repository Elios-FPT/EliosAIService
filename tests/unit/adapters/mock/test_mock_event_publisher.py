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


@pytest.mark.asyncio
async def test_mock_publishes_feedback_completed_serialized_result():
    """Test mock publisher stores FEEDBACK_COMPLETED with serialized result."""
    from datetime import datetime
    from src.domain.models.feedback_result import InterviewFeedbackResult

    publisher = MockEventPublisher()
    request_id = uuid4()
    entity_id = uuid4()
    user_id = uuid4()

    feedback_result = InterviewFeedbackResult(
        interview_id=entity_id,
        overall_score=90.0,
        theoretical_score_avg=88.0,
        speaking_score_avg=70.0,
        total_questions=4,
        total_follow_ups=1,
        question_feedback=[],
        gap_progression={},
        strengths=["strong fundamentals"],
        weaknesses=[],
        study_recommendations=[],
        technique_tips=[],
        completion_time=datetime.utcnow().isoformat(),
    )

    await publisher.publish_feedback_completed(
        request_id=request_id,
        entity_id=entity_id,
        input_type="INTERVIEW",
        user_id=user_id,
        result=feedback_result,
        correlation_id=uuid4(),
    )

    events = publisher.get_events("FEEDBACK_COMPLETED")
    assert len(events) == 1
    event = events[0]
    assert event["event_type"] == "FEEDBACK_COMPLETED"
    assert event["request_id"] == str(request_id)
    assert event["entity_id"] == str(entity_id)
    assert event["input_type"] == "INTERVIEW"
    assert event["user_id"] == str(user_id)
    assert isinstance(event["result"], dict)
    assert event["result"]["interview_id"] == str(entity_id)
