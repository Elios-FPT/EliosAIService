"""Unit tests for FeedbackCompletedPayload DTO."""

from datetime import datetime
from uuid import uuid4

from src.application.dto.event.feedback_completed_payload import FeedbackCompletedPayload
from src.domain.models.feedback_result import InterviewFeedbackResult


def test_feedback_completed_payload_from_feedback_serialization():
    """FeedbackCompletedPayload.from_feedback should produce expected JSON-safe dict."""
    request_id = uuid4()
    entity_id = uuid4()
    user_id = uuid4()

    result = InterviewFeedbackResult(
        interview_id=entity_id,
        overall_score=85.5,
        theoretical_score_avg=80.0,
        speaking_score_avg=60.0,
        total_questions=5,
        total_follow_ups=2,
        question_feedback=[],
        gap_progression={},
        strengths=[],
        weaknesses=[],
        study_recommendations=[],
        technique_tips=[],
        completion_time=datetime.utcnow().isoformat(),
    )

    payload = FeedbackCompletedPayload.from_feedback(
        request_id=request_id,
        entity_id=entity_id,
        input_type="INTERVIEW",
        user_id=user_id,
        result=result,
    )

    dumped = payload.model_dump(mode="json", by_alias=True)

    assert dumped["RequestId"] == str(request_id)
    assert dumped["EntityId"] == str(entity_id)
    assert dumped["InputType"] == "INTERVIEW"
    assert dumped["UserId"] == str(user_id)
    assert isinstance(dumped["Result"], dict)
    assert dumped["Result"]["interview_id"] == str(entity_id)
    assert dumped["Result"]["overall_score"] == 85.5
    assert "Timestamp" in dumped


