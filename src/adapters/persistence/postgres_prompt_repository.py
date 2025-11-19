"""PostgreSQL implementation of PromptRepositoryPort."""

import random
from datetime import datetime
from uuid import UUID

from deepdiff import DeepDiff
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.domain.models.prompt_execution import PromptExecution
from src.domain.models.prompt_metadata_change import PromptMetadataChange
from src.domain.models.prompt_template import PromptTemplate
from src.domain.ports.prompt_repository_port import PromptRepositoryPort
from .mappers import (
    PromptExecutionMapper,
    PromptMetadataChangeMapper,
    PromptTemplateMapper,
)
from .models import (
    PromptAnalyticsSummaryModel,
    PromptExecutionModel,
    PromptMetadataChangeModel,
    PromptTemplateModel,
)


class PostgreSQLPromptRepository(PromptRepositoryPort):
    """PostgreSQL implementation with immutable versioning."""

    def __init__(self, session: AsyncSession):
        """Initialize repository.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session

    # ========== Version Management ==========

    async def create_initial_prompt(
        self,
        name: str,
        template_json: dict,
        created_by: str,
        notes: str | None = None,
    ) -> PromptTemplate:
        """Create initial prompt version (v1)."""
        # Check if prompt already exists
        result = await self.session.execute(
            select(PromptTemplateModel).where(PromptTemplateModel.name == name).limit(1)
        )
        existing = result.scalar_one_or_none()
        if existing:
            raise ValueError(f"Prompt '{name}' already exists")

        # Create domain model
        prompt = PromptTemplate(
            name=name,
            version=1,
            template_json=template_json,
            created_by=created_by,
            notes=notes,
            created_at=datetime.utcnow(),
            is_draft=True,
            is_active=False,
        )

        # Convert to DB model and save
        db_model = PromptTemplateMapper.to_db_model(prompt)
        self.session.add(db_model)
        await self.session.commit()
        await self.session.refresh(db_model)

        return PromptTemplateMapper.to_domain(db_model)

    async def create_new_version(
        self,
        name: str,
        parent_version: int,
        template_json: dict,
        change_summary: str,
        created_by: str,
        notes: str | None = None,
    ) -> PromptTemplate:
        """Create new version forked from parent."""
        # Get parent version
        parent = await self.get_version(name, parent_version)
        if not parent:
            raise ValueError(f"Parent version {name} v{parent_version} not found")

        # Get max version for this prompt
        result = await self.session.execute(
            select(func.max(PromptTemplateModel.version))
            .where(PromptTemplateModel.name == name)
        )
        max_version = result.scalar() or 0

        # Create new version
        new_prompt = PromptTemplate(
            name=name,
            version=max_version + 1,
            parent_version_id=parent.id,
            template_json=template_json,
            change_summary=change_summary,
            created_by=created_by,
            notes=notes,
            created_at=datetime.utcnow(),
            is_draft=True,
            is_active=False,
        )

        # Save
        db_model = PromptTemplateMapper.to_db_model(new_prompt)
        self.session.add(db_model)
        await self.session.commit()
        await self.session.refresh(db_model)

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

        # Create new version with target's content
        return await self.create_new_version(
            name=name,
            parent_version=target_version,
            template_json=target.template_json,
            change_summary=f"Rollback to v{target_version}: {reason}",
            created_by=changed_by,
            notes=f"Rolled back from v{target_version}",
        )

    # ========== Activation & A/B Testing ==========

    async def activate_version(
        self,
        prompt_id: UUID,
        changed_by: str,
        reason: str,
        traffic_percentage: int = 100,
        ab_test_group: str | None = None,
    ) -> None:
        """Activate version (atomic transaction)."""
        if not 0 <= traffic_percentage <= 100:
            raise ValueError("traffic_percentage must be between 0 and 100")

        # Get target prompt
        result = await self.session.execute(
            select(PromptTemplateModel).where(PromptTemplateModel.id == prompt_id)
        )
        target = result.scalar_one_or_none()
        if not target:
            raise ValueError(f"Prompt {prompt_id} not found")

        async with self.session.begin_nested():
            # If traffic=100, deactivate all other active versions
            if traffic_percentage == 100:
                result = await self.session.execute(
                    select(PromptTemplateModel)
                    .where(PromptTemplateModel.name == target.name)
                    .where(PromptTemplateModel.is_active == True)
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
                        reason=f"Deactivated by activating v{target.version}",
                    )
                    active_prompt.is_active = False

            # Activate target
            await self._log_metadata_change(
                prompt_template_id=target.id,
                field_name="is_active",
                old_value=target.is_active,
                new_value=True,
                changed_by=changed_by,
                reason=reason,
            )
            target.is_active = True
            target.is_draft = False
            target.traffic_percentage = traffic_percentage
            target.ab_test_group = ab_test_group

        await self.session.commit()

    async def adjust_ab_traffic(
        self,
        prompt_id: UUID,
        new_traffic_percentage: int,
        changed_by: str,
        reason: str,
    ) -> None:
        """Adjust traffic percentage for A/B testing."""
        if not 0 <= new_traffic_percentage <= 100:
            raise ValueError("traffic_percentage must be between 0 and 100")

        # Get prompt
        result = await self.session.execute(
            select(PromptTemplateModel).where(PromptTemplateModel.id == prompt_id)
        )
        prompt = result.scalar_one_or_none()
        if not prompt:
            raise ValueError(f"Prompt {prompt_id} not found")
        if not prompt.is_active:
            raise ValueError("Can only adjust traffic for active prompts")

        # Log change and update
        await self._log_metadata_change(
            prompt_template_id=prompt.id,
            field_name="traffic_percentage",
            old_value=prompt.traffic_percentage,
            new_value=new_traffic_percentage,
            changed_by=changed_by,
            reason=reason,
        )
        prompt.traffic_percentage = new_traffic_percentage
        await self.session.commit()

    # ========== Retrieval ==========

    async def get_active_prompt(self, name: str) -> PromptTemplate | None:
        """Get active prompt with A/B testing logic."""
        result = await self.session.execute(
            select(PromptTemplateModel)
            .where(PromptTemplateModel.name == name)
            .where(PromptTemplateModel.is_active == True)
        )
        active_prompts = list(result.scalars().all())

        if not active_prompts:
            return None

        if len(active_prompts) == 1:
            return PromptTemplateMapper.to_domain(active_prompts[0])

        # Weighted random selection for A/B testing
        return self._select_ab_variant(active_prompts)

    async def get_by_id(self, prompt_id: UUID) -> PromptTemplate | None:
        """Get prompt by ID."""
        result = await self.session.execute(
            select(PromptTemplateModel).where(PromptTemplateModel.id == prompt_id)
        )
        db_model = result.scalar_one_or_none()
        return PromptTemplateMapper.to_domain(db_model) if db_model else None

    async def get_version(self, name: str, version: int) -> PromptTemplate | None:
        """Get specific version by name and version number."""
        result = await self.session.execute(
            select(PromptTemplateModel)
            .where(PromptTemplateModel.name == name)
            .where(PromptTemplateModel.version == version)
        )
        db_model = result.scalar_one_or_none()
        return PromptTemplateMapper.to_domain(db_model) if db_model else None

    async def get_version_history(self, name: str) -> list[dict]:
        """Get version history with JSON diffs."""
        result = await self.session.execute(
            select(PromptTemplateModel)
            .where(PromptTemplateModel.name == name)
            .order_by(PromptTemplateModel.version)
        )
        versions = result.scalars().all()

        history = []
        for version in versions:
            entry = {
                "version": version.version,
                "created_at": version.created_at,
                "created_by": version.created_by,
                "change_summary": version.change_summary,
                "is_active": version.is_active,
                "is_draft": version.is_draft,
                "diff": None,
            }

            # Calculate diff with parent
            if version.parent_version_id:
                parent = await self.get_by_id(version.parent_version_id)
                if parent:
                    diff = DeepDiff(
                        parent.template_json,
                        version.template_json,
                        ignore_order=True,
                    )
                    entry["diff"] = diff.to_dict() if diff else {}

            history.append(entry)

        return history

    async def get_audit_trail(self, name: str) -> list[dict]:
        """Get audit trail of metadata changes."""
        # Get all prompt IDs for this name
        result = await self.session.execute(
            select(PromptTemplateModel.id)
            .where(PromptTemplateModel.name == name)
        )
        prompt_ids = [row[0] for row in result.all()]

        if not prompt_ids:
            return []

        # Get all metadata changes
        result = await self.session.execute(
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
                "reason": change.reason,
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
        # Create execution
        execution = PromptExecution(
            prompt_template_id=prompt_template_id,
            interview_id=execution_data.get("interview_id"),
            candidate_id=execution_data.get("candidate_id"),
            input_variables=execution_data["input_variables"],
            output_text=execution_data.get("output_text"),
            prompt_tokens=execution_data.get("prompt_tokens"),
            completion_tokens=execution_data.get("completion_tokens"),
            tokens_used=execution_data.get("tokens_used"),
            latency_ms=execution_data["latency_ms"],
            model_name=execution_data.get("model_name"),
            success=execution_data["success"],
            error_message=execution_data.get("error_message"),
            executed_at=datetime.utcnow(),
        )

        # Save
        db_model = PromptExecutionMapper.to_db_model(execution)
        self.session.add(db_model)
        await self.session.commit()
        await self.session.refresh(db_model)

        return PromptExecutionMapper.to_domain(db_model)

    async def get_analytics_summary(self, name: str) -> dict | None:
        """Get analytics summary from materialized view."""
        # Get prompt template ID
        result = await self.session.execute(
            select(PromptTemplateModel)
            .where(PromptTemplateModel.name == name)
            .where(PromptTemplateModel.is_active == True)
            .limit(1)
        )
        prompt = result.scalar_one_or_none()
        if not prompt:
            return None

        # Query materialized view
        result = await self.session.execute(
            select(PromptAnalyticsSummaryModel)
            .where(PromptAnalyticsSummaryModel.prompt_template_id == prompt.id)
        )
        summary = result.scalar_one_or_none()

        if not summary:
            return None

        return {
            "total_executions": summary.total_executions,
            "avg_tokens_used": summary.avg_tokens_used,
            "avg_latency_ms": summary.avg_latency_ms,
            "success_rate": summary.success_rate,
            "estimated_cost_usd": summary.estimated_cost_usd,
            "last_executed_at": summary.last_executed_at,
        }

    # ========== Internal Helpers ==========

    def _select_ab_variant(self, prompts: list[PromptTemplateModel]) -> PromptTemplate:
        """Weighted random selection for A/B testing."""
        weights = [p.traffic_percentage for p in prompts]
        selected = random.choices(prompts, weights=weights, k=1)[0]
        return PromptTemplateMapper.to_domain(selected)

    async def _log_metadata_change(
        self,
        prompt_template_id: UUID,
        field_name: str,
        old_value: any,
        new_value: any,
        changed_by: str,
        reason: str | None = None,
    ) -> None:
        """Log metadata change (internal helper)."""
        change = PromptMetadataChange.create_change(
            prompt_template_id=prompt_template_id,
            field_name=field_name,
            old_value=old_value,
            new_value=new_value,
            changed_by=changed_by,
            reason=reason,
        )

        db_model = PromptMetadataChangeMapper.to_db_model(change)
        self.session.add(db_model)
        # Don't commit - let caller handle transaction
