"""Unit tests for event DTOs."""

import pytest
from uuid import UUID, uuid4
from decimal import Decimal

from src.application.dto.event import EventWrapper, InterviewAttemptedPayload


def test_event_wrapper_serialization():
    """Test EventWrapper serializes to PascalCase."""
    from pydantic import BaseModel

    class TestPayload(BaseModel):
        test: str

    payload = TestPayload(test="data")
    correlation_id = uuid4()

    event = EventWrapper[TestPayload](
        correlation_id=correlation_id,
        event_type="TEST_EVENT",
        payload=payload,
    )

    # Serialize with alias (PascalCase)
    event_dict = event.model_dump(by_alias=True)

    assert "EventId" in event_dict
    assert "CorrelationId" in event_dict
    assert "EventType" in event_dict
    assert "Payload" in event_dict
    assert event_dict["EventType"] == "TEST_EVENT"
    # UUID may be serialized as UUID object or string depending on Pydantic version
    assert str(event_dict["CorrelationId"]) == str(correlation_id)


def test_interview_attempted_payload_validation():
    """Test InterviewAttemptedPayload validates score format."""
    valid_payload = InterviewAttemptedPayload(
        user_id=uuid4(),
        interview_id=uuid4(),
        theoretical_score="80.50",
        speaking_score="60.20",
        overall_score="75.00",
    )

    assert valid_payload.theoretical_score == "80.50"
    assert valid_payload.speaking_score == "60.20"
    assert valid_payload.overall_score == "75.00"


def test_interview_attempted_payload_invalid_decimals():
    """Test payload rejects scores without 2 decimals."""
    with pytest.raises(ValueError, match="exactly 2 decimal places"):
        InterviewAttemptedPayload(
            user_id=uuid4(),
            interview_id=uuid4(),
            theoretical_score="80.5",  # Only 1 decimal
            speaking_score="60.20",
            overall_score="75.00",
        )


def test_interview_attempted_payload_out_of_range():
    """Test payload rejects scores outside 0-100."""
    with pytest.raises(ValueError, match="between 0.00 and 100.00"):
        InterviewAttemptedPayload(
            user_id=uuid4(),
            interview_id=uuid4(),
            theoretical_score="150.00",  # > 100
            speaking_score="60.20",
            overall_score="75.00",
        )


def test_interview_attempted_payload_from_summary():
    """Test from_summary factory method."""
    candidate_id = uuid4()
    interview_id = uuid4()

    payload = InterviewAttemptedPayload.from_summary(
        candidate_id=candidate_id,
        interview_id=interview_id,
        overall_score=75.456,  # Rounds to 75.46
        theoretical_score_avg=80.123,  # Rounds to 80.12
        speaking_score_avg=60.789,  # Rounds to 60.79
    )

    assert payload.user_id == candidate_id
    assert payload.interview_id == interview_id
    assert payload.overall_score == "75.46"
    assert payload.theoretical_score == "80.12"
    assert payload.speaking_score == "60.79"

