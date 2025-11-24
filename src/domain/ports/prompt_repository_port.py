"""Prompt repository port for version control."""

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Any
from uuid import UUID

from src.domain.models.prompt_execution import PromptExecution
from src.domain.models.prompt_template import PromptTemplate


class PromptRepositoryPort(ABC):
    """Abstract repository for prompt version control.

    Manages immutable prompt versions with A/B testing,
    activation lifecycle, and execution analytics.
    """

    # ========== Version Management ==========

    @abstractmethod
    async def create_initial_prompt(
        self,
        name: str,
        system_prompt: str,
        user_template: str,
        input_variables: list[str],
        partial_variables: dict[str, Any],
        output_parser_type: str,
        output_schema: dict[str, Any],
        temperature: Decimal,
        max_tokens: int,
        top_p: Decimal,
        frequency_penalty: Decimal,
        presence_penalty: Decimal,
        created_by: str,
    ) -> PromptTemplate:
        """Create initial prompt version (v1).

        Args:
            name: Unique prompt identifier
            system_prompt: System message (role/context)
            user_template: User message template with {variables}
            input_variables: Variables to interpolate
            partial_variables: Pre-filled variables
            output_parser_type: Parser type
            output_schema: Expected output schema
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum tokens to generate
            top_p: Nucleus sampling parameter
            frequency_penalty: Frequency penalty
            presence_penalty: Presence penalty
            created_by: User creating the prompt

        Returns:
            Created PromptTemplate (version=1, is_draft=True, is_active=False)

        Raises:
            ValueError: If prompt with this name already exists
        """
        pass

    @abstractmethod
    async def create_new_version(
        self,
        name: str,
        parent_version: int,
        system_prompt: str,
        user_template: str,
        input_variables: list[str],
        partial_variables: dict[str, Any],
        output_parser_type: str,
        output_schema: dict[str, Any],
        temperature: Decimal,
        max_tokens: int,
        top_p: Decimal,
        frequency_penalty: Decimal,
        presence_penalty: Decimal,
        change_summary: str,
        created_by: str,
    ) -> PromptTemplate:
        """Create new version forked from parent.

        Args:
            name: Prompt identifier
            parent_version: Version number to fork from
            system_prompt: System message (role/context)
            user_template: User message template with {variables}
            input_variables: Variables to interpolate
            partial_variables: Pre-filled variables
            output_parser_type: Parser type
            output_schema: Expected output schema
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum tokens to generate
            top_p: Nucleus sampling parameter
            frequency_penalty: Frequency penalty
            presence_penalty: Presence penalty
            change_summary: Human-readable change description
            created_by: User creating the version

        Returns:
            Created PromptTemplate (version=parent+1, is_draft=True, is_active=False)

        Raises:
            ValueError: If parent version not found
        """
        pass

    @abstractmethod
    async def rollback_to_version(
        self,
        name: str,
        target_version: int,
        changed_by: str,
        reason: str,
    ) -> PromptTemplate:
        """Rollback by creating new version from target version.

        Creates new version with content from target_version.
        Preserves immutability (no destructive rollback).

        Args:
            name: Prompt identifier
            target_version: Version to rollback to
            changed_by: User performing rollback
            reason: Reason for rollback

        Returns:
            New PromptTemplate with content from target version

        Raises:
            ValueError: If target version not found
        """
        pass

    # ========== Activation ==========

    @abstractmethod
    async def activate_version(
        self,
        prompt_id: UUID,
        changed_by: str,
        reason: str,
    ) -> None:
        """Activate version (always deactivates others).

        Atomic transaction:
        - Deactivate all other versions of the same prompt
        - Activate the specified version
        - Log metadata change

        Args:
            prompt_id: Prompt version to activate
            changed_by: User activating
            reason: Reason for activation

        Raises:
            ValueError: If prompt not found
        """
        pass

    # ========== Retrieval ==========

    @abstractmethod
    async def get_active_prompt(self, name: str) -> PromptTemplate | None:
        """Get active prompt version.

        Args:
            name: Prompt identifier

        Returns:
            Active PromptTemplate or None if no active version
        """
        pass

    @abstractmethod
    async def get_by_id(self, prompt_id: UUID) -> PromptTemplate | None:
        """Get prompt by ID.

        Args:
            prompt_id: Prompt version UUID

        Returns:
            PromptTemplate or None
        """
        pass

    @abstractmethod
    async def get_version(self, name: str, version: int) -> PromptTemplate | None:
        """Get specific version by name and version number.

        Args:
            name: Prompt identifier
            version: Version number

        Returns:
            PromptTemplate or None
        """
        pass

    @abstractmethod
    async def get_version_history(self, name: str) -> list[dict]:
        """Get version history with JSON diffs.

        Returns chronological list with diff from parent version.

        Args:
            name: Prompt identifier

        Returns:
            List of dicts with keys:
            - version: int
            - created_at: datetime
            - created_by: str
            - change_summary: str
            - is_active: bool
            - diff: dict (DeepDiff output, None for v1)
        """
        pass

    @abstractmethod
    async def get_audit_trail(self, name: str) -> list[dict]:
        """Get audit trail of metadata changes.

        Args:
            name: Prompt identifier

        Returns:
            List of dicts with keys:
            - field_name: str
            - old_value: str
            - new_value: str
            - changed_by: str
            - changed_at: datetime
        """
        pass

    # ========== Analytics ==========

    @abstractmethod
    async def log_execution(
        self,
        prompt_template_id: UUID,
        execution_data: dict,
    ) -> PromptExecution:
        """Log prompt execution for analytics.

        Args:
            prompt_template_id: Prompt version executed
            execution_data: Dict with keys:
                - interview_id (optional)
                - input_variables: dict
                - output_text: str
                - prompt_tokens: int
                - completion_tokens: int
                - latency_ms: int
                - model_name: str
                - success: bool
                - error_message: str (optional)

        Returns:
            Created PromptExecution
        """
        pass

    @abstractmethod
    async def get_analytics_summary(self, name: str) -> dict | None:
        """Get analytics summary from materialized view.

        Queries prompt_analytics_summary view for aggregated stats.

        Args:
            name: Prompt identifier

        Returns:
            Dict with keys:
            - total_executions: int
            - avg_prompt_tokens: float
            - avg_completion_tokens: float
            - avg_latency_ms: float
            - success_rate: float (0.0-1.0)
            - estimated_cost_usd: float
            - last_executed_at: datetime
            Or None if no executions
        """
        pass

    @abstractmethod
    async def list_prompts(
        self,
        limit: int,
        offset: int,
        is_active: bool | None = None,
        include_deleted: bool = False,
    ) -> tuple[list[PromptTemplate], int]:
        """List prompts with pagination and filters.

        Args:
            limit: Maximum number of prompts to return
            offset: Number of prompts to skip
            is_active: Filter by active status (None = no filter)
            include_deleted: Include soft-deleted prompts (default: False)

        Returns:
            Tuple of (list of PromptTemplate, total_count)
        """
        pass

    @abstractmethod
    async def update(self, prompt: PromptTemplate) -> PromptTemplate:
        """Update an existing prompt template.

        Args:
            prompt: PromptTemplate domain model with updated data

        Returns:
            Updated PromptTemplate

        Raises:
            ValueError: If prompt not found
        """
        pass