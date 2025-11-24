"""Prompt metadata change domain model."""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class PromptMetadataChange(BaseModel):
    """Audit log entry for metadata changes.

    Tracks all non-version changes to prompt templates
    (activation, traffic adjustments, A/B test group changes).
    """

    id: UUID = Field(default_factory=uuid4)
    prompt_template_id: UUID = Field(..., description="Foreign key to prompt_templates")
    field_name: str = Field(..., max_length=50, description="Changed field name")
    old_value: str | None = Field(default=None, description="Previous value (serialized)")
    new_value: str | None = Field(default=None, description="New value (serialized)")
    changed_by: str = Field(..., max_length=100, description="User identifier")
    changed_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        """Pydantic config."""
        from_attributes = True
        json_schema_extra = {
            "example": {
                "prompt_template_id": "123e4567-e89b-12d3-a456-426614174000",
                "field_name": "is_active",
                "old_value": "false",
                "new_value": "true",
                "changed_by": "admin"
            }
        }

    @classmethod
    def create_change(
        cls,
        prompt_template_id: UUID,
        field_name: str,
        old_value: Any,
        new_value: Any,
        changed_by: str,
    ) -> "PromptMetadataChange":
        """Factory method to create change entry.

        Args:
            prompt_template_id: ID of changed prompt
            field_name: Name of changed field
            old_value: Previous value (any type, will be serialized)
            new_value: New value (any type, will be serialized)
            changed_by: User identifier

        Returns:
            PromptMetadataChange instance
        """
        return cls(
            prompt_template_id=prompt_template_id,
            field_name=field_name,
            old_value=str(old_value) if old_value is not None else None,
            new_value=str(new_value) if new_value is not None else None,
            changed_by=changed_by,
        )
