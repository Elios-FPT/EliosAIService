"""Payload DTO for INTERVIEW_ATTEMPTED event."""

from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel, Field, field_validator


class InterviewAttemptedPayload(BaseModel):
    """Payload for INTERVIEW_ATTEMPTED event sent to User Service.

    Attributes:
        user_id: User ID (mapped from candidate_id)
        interview_id: Interview UUID
        theoretical_score: Theoretical knowledge score (0-100, 2 decimals)
        speaking_score: Speaking/communication score (0-100, 2 decimals)
        overall_score: Weighted overall score (0-100, 2 decimals)
    """

    user_id: UUID = Field(
        alias="UserId",
        description="User ID (from candidate_id)"
    )
    interview_id: UUID = Field(
        alias="InterviewId",
        description="Interview UUID"
    )
    title: str | None = Field(
        alias="Title",
        default=None,
        description="Human-friendly interview title (optional)",
    )
    theoretical_score: str = Field(
        alias="TheoreticalScore",
        description="Theoretical score (2 decimal places)"
    )
    speaking_score: str = Field(
        alias="SpeakingScore",
        description="Speaking score (2 decimal places)"
    )
    overall_score: str = Field(
        alias="OverallScore",
        description="Overall score (2 decimal places)"
    )

    model_config = {
        "populate_by_name": True,
        "json_schema_extra": {
            "example": {
                "UserId": "ac9f879f-5121-45ab-bd47-641e68934105",
                "InterviewId": "b65eb3b4-7a9d-4672-8c7f-0535fbcea0a4",
                "TheoreticalScore": "80.50",
                "SpeakingScore": "60.20",
                "OverallScore": "75.00"
            }
        }
    }

    @field_validator("theoretical_score", "speaking_score", "overall_score")
    @classmethod
    def validate_score_format(cls, v: str) -> str:
        """Validate score has exactly 2 decimal places."""
        try:
            decimal_val = Decimal(v)
            # Check 2 decimal places
            if decimal_val.as_tuple().exponent != -2:
                raise ValueError("Score must have exactly 2 decimal places")
            # Check range 0-100
            if not (Decimal("0.00") <= decimal_val <= Decimal("100.00")):
                raise ValueError("Score must be between 0.00 and 100.00")
            return v
        except (ValueError, ArithmeticError) as e:
            raise ValueError(f"Invalid score format: {e}")

    @staticmethod
    def from_summary(
        candidate_id: UUID,
        interview_id: UUID,
        overall_score: float,
        theoretical_score_avg: float,
        speaking_score_avg: float,
        title: str | None = None,
    ) -> "InterviewAttemptedPayload":
        """Create payload from CompleteInterviewUseCase summary data.

        Args:
            candidate_id: Candidate UUID (maps to UserId)
            interview_id: Interview UUID
            overall_score: Overall score (weighted average)
            theoretical_score_avg: Theoretical score average
            speaking_score_avg: Speaking score average

        Returns:
            InterviewAttemptedPayload instance
        """
        return InterviewAttemptedPayload(
            user_id=candidate_id,
            interview_id=interview_id,
            title=title,
            theoretical_score=f"{theoretical_score_avg:.2f}",
            speaking_score=f"{speaking_score_avg:.2f}",
            overall_score=f"{overall_score:.2f}",
        )

