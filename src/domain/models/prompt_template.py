"""Prompt template domain model."""

from datetime import datetime
from typing import List, Dict, Optional, Any
from decimal import Decimal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class PromptTemplate(BaseModel):
    """
    LLM prompt template with version control.

    Decomposed from template_json for UI editing.
    """

    id: UUID = Field(default_factory=uuid4)
    prompt_name: str = Field(min_length=1, max_length=100)
    version: int = Field(default=1, ge=1)
    is_active: bool = False
    traffic_percentage: int = Field(default=0, ge=0, le=100)

    # Decomposed prompt structure
    system_prompt: str = Field(description="System message (role/context)")
    user_template: str = Field(description="User message template with {variables}")
    input_variables: List[str] = Field(
        default_factory=list,
        description="Variables to interpolate (e.g., ['question', 'answer'])"
    )
    partial_variables: Dict[str, Any] = Field(
        default_factory=dict,
        description="Pre-filled variables (e.g., {'format': 'JSON'})"
    )

    # Output parsing config
    output_parser_type: str = Field(
        default="json_output_parser",
        description="Parser type (json_output_parser, structured_output_parser, etc.)"
    )
    output_schema: Dict[str, Any] = Field(
        default_factory=dict,
        description="Expected output schema (JSON Schema format)"
    )

    # Model parameters
    temperature: Decimal = Field(
        default=Decimal("0.3"),
        ge=Decimal("0"),
        le=Decimal("2"),
        description="Sampling temperature (0-2)"
    )
    max_tokens: int = Field(default=2000, ge=1, le=100000)
    top_p: Decimal = Field(
        default=Decimal("0.95"),
        ge=Decimal("0"),
        le=Decimal("1"),
        description="Nucleus sampling parameter"
    )
    frequency_penalty: Decimal = Field(
        default=Decimal("0"),
        ge=Decimal("-2"),
        le=Decimal("2")
    )
    presence_penalty: Decimal = Field(
        default=Decimal("0"),
        ge=Decimal("-2"),
        le=Decimal("2")
    )

    # Soft delete
    deleted_at: Optional[datetime] = None

    # Legacy JSONB (backup, not used in domain logic)
    template_json_legacy: Optional[Dict[str, Any]] = None

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        """Pydantic configuration."""
        from_attributes = True

    def soft_delete(self) -> None:
        """Soft delete this template."""
        self.deleted_at = datetime.utcnow()
        self.is_active = False

    def is_deleted(self) -> bool:
        """Check if template is soft-deleted."""
        return self.deleted_at is not None

    def to_langchain_config(self) -> Dict[str, Any]:
        """
        Convert to LangChain-compatible config.

        Returns:
            Dict matching structure expected by LangChainAdapter
        """
        return {
            "template_type": "chat",
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": self.user_template}
            ],
            "input_variables": self.input_variables,
            "partial_variables": self.partial_variables,
            "output_parser": {
                "type": self.output_parser_type,
                "schema": self.output_schema
            },
            "model_params": {
                "temperature": float(self.temperature),
                "max_tokens": self.max_tokens,
                "top_p": float(self.top_p),
                "frequency_penalty": float(self.frequency_penalty),
                "presence_penalty": float(self.presence_penalty)
            }
        }
