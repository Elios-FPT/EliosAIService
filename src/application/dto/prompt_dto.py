"""Prompt template DTOs for REST API request/response."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from ...domain.models.prompt_template import PromptTemplate


# ========== Request DTOs ==========


class CreatePromptRequest(BaseModel):
    """Request to create initial prompt version (v1)."""

    prompt_name: str = Field(..., min_length=1, max_length=100, description="Unique prompt identifier")
    system_prompt: str = Field(..., description="System message (role/context)")
    user_template: str = Field(..., description="User message template with {variables}")
    input_variables: list[str] = Field(default_factory=list, description="Variables to interpolate")
    partial_variables: dict[str, Any] | None = Field(default=None, description="Pre-filled variables")
    output_parser_type: str = Field(default="json_output_parser", description="Parser type")
    output_schema: dict[str, Any] | None = Field(default=None, description="Expected output schema")
    temperature: float = Field(..., ge=0.0, le=2.0, description="Sampling temperature (0-2)")
    max_tokens: int = Field(..., ge=1, le=100000, description="Maximum tokens to generate")
    top_p: float = Field(..., ge=0.0, le=1.0, description="Nucleus sampling parameter")
    frequency_penalty: float = Field(..., ge=-2.0, le=2.0, description="Frequency penalty")
    presence_penalty: float = Field(..., ge=-2.0, le=2.0, description="Presence penalty")
    created_by: str = Field(..., description="User creating the prompt")


class CreateVersionRequest(BaseModel):
    """Request to create new version from parent."""

    parent_version: int | None = Field(
        default=None,
        ge=1,
        description="Parent version number to fork from (defaults to latest if omitted)",
    )
    system_prompt: str = Field(..., description="System message (role/context)")
    user_template: str = Field(..., description="User message template with {variables}")
    input_variables: list[str] = Field(default_factory=list, description="Variables to interpolate")
    partial_variables: dict[str, Any] | None = Field(default=None, description="Pre-filled variables")
    output_parser_type: str = Field(default="json_output_parser", description="Parser type")
    output_schema: dict[str, Any] | None = Field(default=None, description="Expected output schema")
    temperature: float = Field(..., ge=0.0, le=2.0, description="Sampling temperature (0-2)")
    max_tokens: int = Field(..., ge=1, le=100000, description="Maximum tokens to generate")
    top_p: float = Field(..., ge=0.0, le=1.0, description="Nucleus sampling parameter")
    frequency_penalty: float = Field(..., ge=-2.0, le=2.0, description="Frequency penalty")
    presence_penalty: float = Field(..., ge=-2.0, le=2.0, description="Presence penalty")
    change_summary: str = Field(..., description="Human-readable change description")
    created_by: str = Field(..., description="User creating the version")


class UpdateDraftPromptRequest(BaseModel):
    """Request to update an existing draft prompt version."""

    system_prompt: str = Field(..., description="System message (role/context)")
    user_template: str = Field(..., description="User message template with {variables}")
    input_variables: list[str] = Field(default_factory=list, description="Variables to interpolate")
    partial_variables: dict[str, Any] | None = Field(default=None, description="Pre-filled variables")
    output_parser_type: str = Field(default="json_output_parser", description="Parser type")
    output_schema: dict[str, Any] | None = Field(default=None, description="Expected output schema")
    temperature: float = Field(..., ge=0.0, le=2.0, description="Sampling temperature (0-2)")
    max_tokens: int = Field(..., ge=1, le=100000, description="Maximum tokens to generate")
    top_p: float = Field(..., ge=0.0, le=1.0, description="Nucleus sampling parameter")
    frequency_penalty: float = Field(..., ge=-2.0, le=2.0, description="Frequency penalty")
    presence_penalty: float = Field(..., ge=-2.0, le=2.0, description="Presence penalty")


class RollbackRequest(BaseModel):
    """Request to rollback to target version."""

    target_version: int = Field(..., ge=1, description="Version number to rollback to")
    changed_by: str = Field(..., description="User performing rollback")
    reason: str = Field(..., description="Reason for rollback")


class ActivatePromptRequest(BaseModel):
    """Request to activate prompt version."""

    changed_by: str = Field(..., description="User activating the version")
    reason: str = Field(..., description="Reason for activation")


# ========== Response DTOs ==========


class PromptTemplateResponse(BaseModel):
    """Response with full prompt template details."""

    id: UUID
    prompt_name: str
    version: int
    is_active: bool
    # Version control and lineage
    parent_version_id: UUID | None = None
    change_summary: str | None = None
    is_draft: bool
    created_by: str
    # Decomposed prompt structure
    system_prompt: str
    user_template: str
    input_variables: list[str]
    partial_variables: dict[str, Any]
    output_parser_type: str
    output_schema: dict[str, Any]
    # Model parameters
    temperature: float
    max_tokens: int
    top_p: float
    frequency_penalty: float
    presence_penalty: float
    # Denormalized JSON storage
    template_json: dict[str, Any] | None = None
    # Timestamps
    created_at: datetime
    deleted_at: datetime | None

    @staticmethod
    def from_domain(prompt: PromptTemplate) -> "PromptTemplateResponse":
        """Convert domain PromptTemplate to response DTO.

        Args:
            prompt: Domain PromptTemplate entity

        Returns:
            PromptTemplateResponse DTO
        """
        return PromptTemplateResponse(
            id=prompt.id,
            prompt_name=prompt.prompt_name,
            version=prompt.version,
            is_active=prompt.is_active,
            # Version control and lineage
            parent_version_id=prompt.parent_version_id,
            change_summary=prompt.change_summary,
            is_draft=prompt.is_draft,
            created_by=prompt.created_by,
            # Decomposed prompt structure
            system_prompt=prompt.system_prompt,
            user_template=prompt.user_template,
            input_variables=prompt.input_variables,
            partial_variables=prompt.partial_variables or {},
            output_parser_type=prompt.output_parser_type,
            output_schema=prompt.output_schema or {},
            # Model parameters
            temperature=float(prompt.temperature),
            max_tokens=prompt.max_tokens,
            top_p=float(prompt.top_p),
            frequency_penalty=float(prompt.frequency_penalty),
            presence_penalty=float(prompt.presence_penalty),
            # Denormalized JSON storage
            template_json=prompt.template_json,
            # Timestamps
            created_at=prompt.created_at,
            deleted_at=prompt.deleted_at,
        )


class VersionHistoryResponse(BaseModel):
    """Response with version history entry including diff."""

    id: UUID
    version: int
    created_at: datetime
    created_by: str | None = None
    change_summary: str | None = None
    is_active: bool
    is_draft: bool
    parent_version_id: UUID | None = None
    diff: dict[str, Any] | None


class AnalyticsSummaryResponse(BaseModel):
    """Response with analytics metrics summary."""

    prompt_name: str
    total_executions: int
    avg_prompt_tokens: float | None
    avg_completion_tokens: float | None
    avg_latency_ms: float | None
    success_rate: float
    estimated_cost_usd: float
    last_executed_at: datetime | None


class AuditTrailResponse(BaseModel):
    """Response with audit trail entry for metadata changes."""

    field_name: str
    old_value: str
    new_value: str
    changed_by: str
    changed_at: datetime


class PaginatedPromptsResponse(BaseModel):
    """Response with paginated list of prompts."""

    prompts: list[PromptTemplateResponse]
    total: int
    page: int
    page_size: int
    has_next: bool

