"""Prompt template domain model."""

from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator, model_validator


class PromptTemplate(BaseModel):
    """Immutable prompt version with metadata.

    Represents a single version of a prompt template.
    Each version is immutable (append-only).
    """

    id: UUID = Field(default_factory=uuid4)
    name: str = Field(..., max_length=100, description="Prompt identifier")
    version: int = Field(..., ge=1, description="Version number (auto-increment)")
    parent_version_id: UUID | None = Field(
        default=None,
        description="Parent version for lineage tracking"
    )
    change_summary: str | None = Field(
        default=None,
        description="Human-readable change description"
    )
    template_json: dict = Field(
        ...,
        description="Full prompt content (immutable)"
    )
    is_active: bool = Field(default=False, description="Currently deployed")
    is_draft: bool = Field(default=True, description="Draft vs production")
    ab_test_group: str | None = Field(
        default=None,
        max_length=50,
        description="A/B test group identifier"
    )
    traffic_percentage: int = Field(
        default=0,
        ge=0,
        le=100,
        description="% of traffic for this version"
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None)

    class Config:
        """Pydantic config."""
        from_attributes = True
        json_schema_extra = {
            "example": {
                "name": "question_generation",
                "version": 1,
                "template_json": {
                    "system": "You are an expert interviewer.",
                    "user_template": "Generate question for {skill}",
                    "variables": ["skill"],
                    "constraints": "VERBAL ONLY"
                },
                "is_active": True,
                "is_draft": False,
                "created_by": "system"
            }
        }

    @field_validator("template_json")
    @classmethod
    def validate_template_json(cls, v: dict) -> dict:
        """Validate template_json structure."""
        required_keys = ["system", "user_template", "variables"]
        if not all(key in v for key in required_keys):
            raise ValueError(f"template_json must contain: {required_keys}")

        # Validate types
        if not isinstance(v["system"], str):
            raise ValueError("template_json['system'] must be a string")
        if not isinstance(v["user_template"], str):
            raise ValueError("template_json['user_template'] must be a string")
        if not isinstance(v["variables"], list):
            raise ValueError("template_json['variables'] must be a list")

        return v

    @model_validator(mode='after')
    def validate_active_not_draft(self) -> 'PromptTemplate':
        """Ensure active versions are not drafts."""
        if self.is_active and self.is_draft:
            raise ValueError("Active versions cannot be drafts")
        return self

    def get_prompt_text(self, **variables) -> str:
        """Render prompt with variables.

        Args:
            **variables: Variable values for interpolation

        Returns:
            Rendered prompt text

        Raises:
            ValueError: If required variables missing
        """
        required_vars = set(self.template_json["variables"])
        provided_vars = set(variables.keys())

        if missing := required_vars - provided_vars:
            raise ValueError(f"Missing variables: {missing}")

        user_prompt = self.template_json["user_template"].format(**variables)
        return f"{self.template_json['system']}\n\n{user_prompt}"
