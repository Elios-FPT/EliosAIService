"""Payload DTO for token balance updates."""

from uuid import UUID

from pydantic import BaseModel, Field


class TokenDeltaPayload(BaseModel):
    """Payload describing a token delta for a user."""

    user_id: UUID = Field(alias="UserId", description="User identifier (UUID)")
    tokens: int = Field(alias="Tokens", description="Token delta (negative for deduction)")

    model_config = {
        "populate_by_name": True,
        "json_schema_extra": {
            "example": {
                "UserId": "102ea1b3-f664-4617-8f43-fdde557f12b6",
                "Tokens": -10,
            }
        },
    }


