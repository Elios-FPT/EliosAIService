"""DTOs for feedback API."""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from ...domain.models.feedback_result import FeedbackResult, FeedbackStatus


class AnalyzeFeedbackRequest(BaseModel):
    """Request to analyze entity (CODE/CV/INTERVIEW)."""

    entity_id: UUID = Field(description="UUID of entity to analyze")
    input_type: str = Field(description="Type of entity: INTERVIEW, CV, or CODE")
    user_id: UUID | None = Field(
        default=None, description="User requesting analysis"
    )
    feedback_input: str | None = Field(
        default=None,
        description="Optional direct content to analyze (for direct submission)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "entity_id": "110e8400-e29b-41d4-a716-446655440000",
                "input_type": "INTERVIEW",
                "user_id": "220e8400-e29b-41d4-a716-446655440000",
                "feedback_input": '{"questions": [...]}'  # Optional
            }
        }


class AnalyzeFeedbackResponse(BaseModel):
    """Response containing feedback analysis."""

    request_id: UUID
    status: str = Field(description="FeedbackStatus as string")
    result: dict[str, Any] | None = Field(
        default=None,
        description="Typed result serialized as dict (InterviewFeedbackResult/CodeReviewFeedbackResult/CVFeedbackResult)",
    )
    error_message: str | None = None

    class Config:
        json_schema_extra = {
            "example": {
                "request_id": "330e8400-e29b-41d4-a716-446655440000",
                "status": "SUCCESS",
                "result": {
                    "interview_id": "110e8400-e29b-41d4-a716-446655440000",
                    "overall_score": 85.5,
                    "theoretical_score_avg": 80.0,
                    "speaking_score_avg": 60.0,
                    "total_questions": 5,
                    "total_follow_ups": 3,
                },
                "error_message": None,
            }
        }


class FeedbackHistoryResponse(BaseModel):
    """Response for feedback history list."""

    request_id: UUID
    entity_id: UUID
    input_type: str
    status: str
    created_at: str
    result: dict[str, Any] | None = None
    error_message: str | None = None

