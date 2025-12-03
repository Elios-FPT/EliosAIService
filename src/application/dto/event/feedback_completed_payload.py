"""Payload DTO for FEEDBACK_COMPLETED event."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from ....domain.models.feedback_result import FeedbackResult


class FeedbackCompletedPayload(BaseModel):
    """Payload for FEEDBACK_COMPLETED event sent to downstream services.

    Attributes:
        request_id: Feedback request UUID
        entity_id: Entity UUID (interview_id, cv_analysis_id, etc.)
        input_type: Type of entity analyzed (INTERVIEW/CODE/CV)
        user_id: User UUID (nullable for external requests)
        result: Type-safe feedback result (polymorphic)
        timestamp: ISO timestamp of completion
    """

    request_id: UUID = Field(
        alias="RequestId",
        description="Feedback request UUID",
    )
    entity_id: UUID = Field(
        alias="EntityId",
        description="Entity UUID (interview_id, cv_analysis_id, etc.)",
    )
    input_type: str = Field(
        alias="InputType",
        description="Type of entity: INTERVIEW, CV, or CODE",
    )
    user_id: UUID | None = Field(
        default=None,
        alias="UserId",
        description="User UUID (nullable for external requests)",
    )
    result: dict = Field(
        alias="Result",
        description="Type-safe feedback result (polymorphic based on input_type)",
    )
    timestamp: str = Field(
        alias="Timestamp",
        description="ISO timestamp of completion",
    )

    model_config = {
        "populate_by_name": True,
        "json_schema_extra": {
            "example": {
                "RequestId": "330e8400-e29b-41d4-a716-446655440000",
                "EntityId": "110e8400-e29b-41d4-a716-446655440000",
                "InputType": "INTERVIEW",
                "UserId": "220e8400-e29b-41d4-a716-446655440000",
                "Result": {
                    "interview_id": "110e8400-e29b-41d4-a716-446655440000",
                    "overall_score": 85.5,
                    "theoretical_score_avg": 80.0,
                    "speaking_score_avg": 60.0,
                },
                "Timestamp": "2025-12-03T10:30:00Z",
            }
        },
    }

    @staticmethod
    def from_feedback(
        request_id: UUID,
        entity_id: UUID,
        input_type: str,
        user_id: UUID | None,
        result: FeedbackResult,
        timestamp: datetime | None = None,
    ) -> "FeedbackCompletedPayload":
        """Create payload from feedback analysis result.

        Args:
            request_id: Feedback request UUID
            entity_id: Entity UUID
            input_type: Type of entity (INTERVIEW/CV/CODE)
            user_id: User UUID (nullable)
            result: Typed feedback result
            timestamp: Optional timestamp (defaults to now)

        Returns:
            FeedbackCompletedPayload instance
        """
        if timestamp is None:
            timestamp = datetime.utcnow()

        return FeedbackCompletedPayload(
            request_id=request_id,
            entity_id=entity_id,
            input_type=input_type,
            user_id=user_id,
            result=result.model_dump(mode="json"),
            timestamp=timestamp.isoformat(),
        )

