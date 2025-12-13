"""PostgreSQL implementation of PromptRepositoryPort."""

import json
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from deepdiff import DeepDiff
from deepdiff.helper import SetOrdered
from sqlalchemy import func, select

from src.domain.models.prompt_execution import PromptExecution
from src.domain.models.prompt_metadata_change import PromptMetadataChange
from src.domain.models.prompt_template import PromptTemplate
from src.application.ports.prompt_repository_port import PromptRepositoryPort

from .mappers import (
    PromptExecutionMapper,
    PromptMetadataChangeMapper,
    PromptTemplateMapper,
)
from .models import (
    PromptAnalyticsSummaryModel,
    PromptMetadataChangeModel,
    PromptTemplateModel,
)
from .session_provider import SessionProvider


def _make_diff_serializable(diff_dict: dict) -> dict:
    """Convert DeepDiff result to fully JSON-serializable format.

    DeepDiff.to_dict() can contain non-serializable types like SetOrdered.
    This function recursively converts them to plain Python types.

    Args:
        diff_dict: Dictionary from DeepDiff.to_dict()

    Returns:
        Fully serializable dictionary
    """
    if not diff_dict:
        return {}

    def convert_value(value: Any) -> Any:
        """Recursively convert non-serializable types to plain Python types."""
        # Explicitly handle SetOrdered first (before other iterable checks)
        if isinstance(value, SetOrdered):
            return [convert_value(item) for item in value]
        # Handle dict
        elif isinstance(value, dict):
            return {k: convert_value(v) for k, v in value.items()}
        # Handle list, tuple, set
        elif isinstance(value, (list, tuple, set)):
            return [convert_value(item) for item in value]
        elif hasattr(value, '__iter__') and not isinstance(value, (str, bytes)):
            # Handle other iterable types (but not strings/bytes)
            try:
                return [convert_value(item) for item in value]
            except (TypeError, ValueError):
                return str(value)
        else:
            # For primitive types, try to serialize
            try:
                # Test if it's JSON serializable
                json.dumps(value)
                return value
            except (TypeError, ValueError):
                # Convert to string as last resort
                return str(value)

    return convert_value(diff_dict)


class PostgreSQLPromptRepository(PromptRepositoryPort):
    """PostgreSQL implementation with immutable versioning."""

    def __init__(self, session_provider: SessionProvider):
        """Initialize repository."""
        self._session_provider = session_provider

    # ========== Version Management ==========

    async def create_initial_prompt(
        self,
        name: str,
        system_prompt: str,
        user_template: str,
        input_variables: list[str],
        partial_variables: dict[str, Any],
        output_schema: dict[str, Any],
        temperature: Decimal,
        max_tokens: int,
        top_p: Decimal,
        frequency_penalty: Decimal,
        presence_penalty: Decimal,
        created_by: str,
    ) -> PromptTemplate:
        """Create initial prompt version (v1)."""
        async with self._session_provider() as session:
            result = await session.execute(
                select(PromptTemplateModel)
                .where(PromptTemplateModel.prompt_name == name)
                .limit(1)
            )
            existing = result.scalar_one_or_none()
            if existing:
                raise ValueError(f"Prompt '{name}' already exists")

            prompt = PromptTemplate(
                prompt_name=name,
                version=1,
                is_active=False,
                parent_version_id=None,
                change_summary=None,
                is_draft=True,
                created_by=created_by,
                system_prompt=system_prompt,
                user_template=user_template,
                input_variables=input_variables,
                partial_variables=partial_variables,
                output_schema=output_schema,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
                frequency_penalty=frequency_penalty,
                presence_penalty=presence_penalty,
                deleted_at=None,
                created_at=datetime.utcnow(),
            )

            db_model = PromptTemplateMapper.to_db_model(prompt)
            session.add(db_model)
            await session.commit()
            await session.refresh(db_model)
            return PromptTemplateMapper.to_domain(db_model)

    async def create_new_version(
        self,
        name: str,
        parent_version: int | None,
        system_prompt: str,
        user_template: str,
        input_variables: list[str],
        partial_variables: dict[str, Any],
        output_schema: dict[str, Any],
        temperature: Decimal,
        max_tokens: int,
        top_p: Decimal,
        frequency_penalty: Decimal,
        presence_penalty: Decimal,
        change_summary: str,
        created_by: str,
    ) -> PromptTemplate:
        """Create new version optionally forked from parent."""
        async with self._session_provider() as session:
            parent = None
            if parent_version is not None:
                parent = await self.get_version(name, parent_version)
                if not parent:
                    raise ValueError(f"Parent version {name} v{parent_version} not found")

            result = await session.execute(
                select(func.max(PromptTemplateModel.version))
                .where(PromptTemplateModel.prompt_name == name)
            )
            max_version = result.scalar() or 0

            new_prompt = PromptTemplate(
                prompt_name=name,
                version=max_version + 1,
                is_active=False,
                parent_version_id=parent.id if parent else None,
                change_summary=change_summary,
                is_draft=True,
                created_by=created_by,
                system_prompt=system_prompt,
                user_template=user_template,
                input_variables=input_variables,
                partial_variables=partial_variables,
                output_schema=output_schema,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
                frequency_penalty=frequency_penalty,
                presence_penalty=presence_penalty,
                deleted_at=None,
                created_at=datetime.utcnow(),
            )

            db_model = PromptTemplateMapper.to_db_model(new_prompt)
            session.add(db_model)
            await session.commit()
            await session.refresh(db_model)
            return PromptTemplateMapper.to_domain(db_model)

    async def rollback_to_version(
        self,
        name: str,
        target_version: int,
        changed_by: str,
        reason: str,
    ) -> PromptTemplate:
        """Rollback by creating new version from target version."""
        # Get target version
        target = await self.get_version(name, target_version)
        if not target:
            raise ValueError(f"Target version {name} v{target_version} not found")

        # Create new version with target's decomposed fields directly
        return await self.create_new_version(
            name=name,
            parent_version=target_version,
            system_prompt=target.system_prompt,
            user_template=target.user_template,
            input_variables=target.input_variables,
            partial_variables=target.partial_variables,
            output_schema=target.output_schema,
            temperature=target.temperature,
            max_tokens=target.max_tokens,
            top_p=target.top_p,
            frequency_penalty=target.frequency_penalty,
            presence_penalty=target.presence_penalty,
            change_summary=f"Rollback to v{target_version}: {reason}",
            created_by=changed_by,
        )

    # ========== Activation ==========

    async def activate_version(
        self,
        prompt_id: UUID,
        changed_by: str,
        reason: str,
    ) -> None:
        """Activate version (always deactivates others)."""
        # Get target prompt
        async with self._session_provider() as session:
            result = await session.execute(
                select(PromptTemplateModel).where(PromptTemplateModel.id == prompt_id)
            )
            target = result.scalar_one_or_none()
            if not target:
                raise ValueError(f"Prompt {prompt_id} not found")

            async with session.begin_nested():
                result = await session.execute(
                    select(PromptTemplateModel)
                    .where(PromptTemplateModel.prompt_name == target.prompt_name)
                    .where(PromptTemplateModel.is_active)
                    .where(PromptTemplateModel.id != prompt_id)
                )
                active_prompts = result.scalars().all()

                for active_prompt in active_prompts:
                    await self._log_metadata_change(
                        prompt_template_id=active_prompt.id,
                        field_name="is_active",
                        old_value=True,
                        new_value=False,
                        changed_by=changed_by,
                        session=session,
                    )
                    active_prompt.is_active = False

                await self._log_metadata_change(
                    prompt_template_id=target.id,
                    field_name="is_active",
                    old_value=target.is_active,
                    new_value=True,
                    changed_by=changed_by,
                    session=session,
                )
                target.is_active = True

            await session.commit()

    # ========== Retrieval ==========

    async def get_active_prompt(self, name: str) -> PromptTemplate | None:
        """Get active prompt (only one active at a time)."""
        async with self._session_provider() as session:
            result = await session.execute(
                select(PromptTemplateModel)
                .where(PromptTemplateModel.prompt_name == name)
                .where(PromptTemplateModel.is_active)
                .limit(1)
            )
            db_model = result.scalar_one_or_none()
            return PromptTemplateMapper.to_domain(db_model) if db_model else None

    async def get_by_id(self, prompt_id: UUID) -> PromptTemplate | None:
        """Get prompt by ID."""
        async with self._session_provider() as session:
            result = await session.execute(
                select(PromptTemplateModel).where(PromptTemplateModel.id == prompt_id)
            )
            db_model = result.scalar_one_or_none()
            return PromptTemplateMapper.to_domain(db_model) if db_model else None

    async def update_draft_prompt(self, prompt_id: UUID, updates: dict) -> PromptTemplate:
        """Update mutable fields on draft prompt."""
        async with self._session_provider() as session:
            result = await session.execute(
                select(PromptTemplateModel).where(PromptTemplateModel.id == prompt_id)
            )
            draft = result.scalar_one_or_none()

            if not draft:
                raise LookupError(f"Prompt {prompt_id} not found")
            if not draft.is_draft:
                raise ValueError("Only draft prompts can be updated")

            mutable_fields = [
                "system_prompt",
                "user_template",
                "input_variables",
                "partial_variables",
                "output_schema",
                "temperature",
                "max_tokens",
                "top_p",
                "frequency_penalty",
                "presence_penalty",
            ]

            for field in mutable_fields:
                if field in updates:
                    setattr(draft, field, updates[field])

            await session.commit()
            await session.refresh(draft)
            return PromptTemplateMapper.to_domain(draft)

    async def get_version(self, name: str, version: int) -> PromptTemplate | None:
        """Get specific version by name and version number."""
        async with self._session_provider() as session:
            result = await session.execute(
                select(PromptTemplateModel)
                .where(PromptTemplateModel.prompt_name == name)
                .where(PromptTemplateModel.version == version)
            )
            db_model = result.scalar_one_or_none()
            return PromptTemplateMapper.to_domain(db_model) if db_model else None

    async def get_version_history(self, name: str) -> list[dict]:
        """Get version history with JSON diffs."""
        async with self._session_provider() as session:
            result = await session.execute(
                select(PromptTemplateModel)
                .where(PromptTemplateModel.prompt_name == name)
                .where(PromptTemplateModel.deleted_at.is_(None))
                .order_by(PromptTemplateModel.version)
            )
            versions = result.scalars().all()

            history = []
            prev_version = None
            for version in versions:
                entry = {
                    "id": version.id,
                    "version": version.version,
                    "created_at": version.created_at,
                    "created_by": version.created_by,
                    "change_summary": version.change_summary,
                    "is_active": version.is_active,
                    "is_draft": version.is_draft,
                    "parent_version_id": version.parent_version_id,
                    "diff": None,
                }

                # template_json removed; keep diff empty for now

                history.append(entry)
                prev_version = version

            return history

    async def get_audit_trail(self, name: str) -> list[dict]:
        """Get audit trail of metadata changes."""
        async with self._session_provider() as session:
            result = await session.execute(
                select(PromptTemplateModel.id).where(PromptTemplateModel.prompt_name == name)
            )
            prompt_ids = [row[0] for row in result.all()]

            if not prompt_ids:
                return []

            result = await session.execute(
                select(PromptMetadataChangeModel)
                .where(PromptMetadataChangeModel.prompt_template_id.in_(prompt_ids))
                .order_by(PromptMetadataChangeModel.changed_at.desc())
            )
            changes = result.scalars().all()

            return [
                {
                    "field_name": change.field_name,
                    "old_value": change.old_value,
                    "new_value": change.new_value,
                    "changed_by": change.changed_by,
                    "changed_at": change.changed_at,
                }
                for change in changes
            ]

    # ========== Analytics ==========

    async def log_execution(
        self,
        prompt_template_id: UUID,
        execution_data: dict,
    ) -> PromptExecution:
        """Log prompt execution for analytics."""
        execution = PromptExecution(
            prompt_template_id=prompt_template_id,
            interview_id=execution_data.get("interview_id"),
            input_variables=execution_data["input_variables"],
            output_text=execution_data.get("output_text"),
            prompt_tokens=execution_data.get("prompt_tokens"),
            completion_tokens=execution_data.get("completion_tokens"),
            latency_ms=execution_data["latency_ms"],
            model_name=execution_data.get("model_name"),
            success=execution_data["success"],
            error_message=execution_data.get("error_message"),
            executed_at=datetime.utcnow(),
        )

        async with self._session_provider() as session:
            db_model = PromptExecutionMapper.to_db_model(execution)
            session.add(db_model)
            await session.commit()
            await session.refresh(db_model)
            return PromptExecutionMapper.to_domain(db_model)

    async def get_analytics_summary(self, name: str) -> dict | None:
        """Get analytics summary from materialized view."""
        # Get prompt template ID
        async with self._session_provider() as session:
            result = await session.execute(
                select(PromptTemplateModel)
                .where(PromptTemplateModel.prompt_name == name)
                .where(PromptTemplateModel.is_active)
                .limit(1)
            )
            prompt = result.scalar_one_or_none()
            if not prompt:
                return None

            result = await session.execute(
                select(PromptAnalyticsSummaryModel)
                .where(PromptAnalyticsSummaryModel.prompt_template_id == prompt.id)
            )
            summary = result.scalar_one_or_none()

            if not summary:
                return None

            return {
                "total_executions": summary.total_executions,
                "avg_prompt_tokens": summary.avg_prompt_tokens,
                "avg_completion_tokens": summary.avg_completion_tokens,
                "avg_latency_ms": summary.avg_latency_ms,
                "success_rate": summary.success_rate,
                "estimated_cost_usd": summary.estimated_cost_usd,
                "last_executed_at": summary.last_executed_at,
            }

    async def list_prompts(
        self,
        limit: int,
        offset: int,
        is_active: bool | None = None,
        include_deleted: bool = False,
    ) -> tuple[list[PromptTemplate], int]:
        """List prompts with pagination and filters."""
        # Build base query
        query = select(PromptTemplateModel)
        count_query = select(func.count(PromptTemplateModel.id))

        # Apply filters
        if not include_deleted:
            query = query.where(PromptTemplateModel.deleted_at.is_(None))
            count_query = count_query.where(PromptTemplateModel.deleted_at.is_(None))

        if is_active is not None:
            query = query.where(PromptTemplateModel.is_active == is_active)
            count_query = count_query.where(PromptTemplateModel.is_active == is_active)

        async with self._session_provider() as session:
            count_result = await session.execute(count_query)
            total_count = count_result.scalar() or 0

            query = (
                query.order_by(PromptTemplateModel.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            result = await session.execute(query)
            db_models = result.scalars().all()
            prompts = [PromptTemplateMapper.to_domain(model) for model in db_models]
            return prompts, total_count

    async def update(self, prompt: PromptTemplate) -> PromptTemplate:
        """Update an existing prompt template."""
        async with self._session_provider() as session:
            result = await session.execute(
                select(PromptTemplateModel).where(PromptTemplateModel.id == prompt.id)
            )
            db_model = result.scalar_one_or_none()

            if not db_model:
                raise ValueError(f"Prompt with id {prompt.id} not found")

            PromptTemplateMapper.update_db_model(db_model, prompt)
            await session.commit()
            await session.refresh(db_model)
            return PromptTemplateMapper.to_domain(db_model)

    # ========== Internal Helpers ==========

    async def _log_metadata_change(
        self,
        prompt_template_id: UUID,
        field_name: str,
        old_value: any,
        new_value: any,
        changed_by: str,
        session,
    ) -> None:
        """Log metadata change (internal helper)."""
        change = PromptMetadataChange.create_change(
            prompt_template_id=prompt_template_id,
            field_name=field_name,
            old_value=old_value,
            new_value=new_value,
            changed_by=changed_by,
        )

        db_model = PromptMetadataChangeMapper.to_db_model(change)
        session.add(db_model)
        # Don't commit - let caller handle transaction
