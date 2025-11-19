# Phase 3: Repository Layer

**Parent**: [Implementation Plan](./plan.md)
**Dependencies**: [Phase 1](./phase-01-database-schema.md), [Phase 2](./phase-02-domain-models.md)
**Created**: 2025-11-20
**Duration**: 4-5 days
**Priority**: Critical
**Status**: ⏳ Pending

---

## Overview

Implement repository port interface and PostgreSQL adapter for prompt version control. Includes 14 methods for version management, activation, retrieval, and analytics.

**Goals**:
- ✅ Repository port with 14 methods
- ✅ PostgreSQL adapter with transactions
- ✅ A/B testing weighted selection
- ✅ JSON diff calculation with DeepDiff
- ✅ Materialized view querying

---

## Repository Port

**File**: `src/domain/ports/prompt_repository_port.py`

**Methods** (14 total):

### Version Management (3)
- `create_initial_prompt(name, template_json, created_by, notes) -> PromptTemplate`
- `create_new_version(name, parent_version, template_json, change_summary, created_by, notes) -> PromptTemplate`
- `rollback_to_version(name, target_version, changed_by, reason) -> PromptTemplate`

### Activation & A/B Testing (2)
- `activate_version(prompt_id, changed_by, reason, traffic_percentage, ab_test_group) -> None`
- `adjust_ab_traffic(prompt_id, new_traffic_percentage, changed_by, reason) -> None`

### Retrieval (5)
- `get_active_prompt(name) -> PromptTemplate | None` (with A/B logic)
- `get_by_id(prompt_id) -> PromptTemplate | None`
- `get_version(name, version) -> PromptTemplate | None`
- `get_version_history(name) -> list[dict]` (with JSON diffs)
- `get_audit_trail(name) -> list[dict]`

### Analytics (2)
- `log_execution(prompt_template_id, execution_data) -> PromptExecution`
- `get_analytics_summary(name) -> dict`

### Internal (2)
- `_log_metadata_change(...) -> None` (internal, used by repository)

---

## PostgreSQL Adapter

**File**: `src/adapters/persistence/postgres_prompt_repository.py`

**Key Features**:
1. **Immutable versioning** - Append-only, never UPDATE
2. **Atomic activation** - Transaction to deactivate others
3. **Weighted A/B selection** - `random.choices()` based on `traffic_percentage`
4. **JSON diff** - DeepDiff for version comparison
5. **Materialized view querying** - Fast analytics

**Implementation Highlights**:

```python
class PostgreSQLPromptRepository(PromptRepositoryPort):
    """PostgreSQL implementation with immutable versioning."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def activate_version(
        self,
        prompt_id: UUID,
        changed_by: str,
        reason: str,
        traffic_percentage: int = 100,
        ab_test_group: str | None = None,
    ) -> None:
        """Activate version (atomic transaction)."""
        # Atomic transaction: deactivate all, activate target
        async with self.session.begin_nested():
            # 1. Deactivate all active versions
            active_prompts = await self.session.execute(...)
            for active_prompt in active_prompts:
                await self._log_metadata_change(...)
                active_prompt.is_active = False

            # 2. Activate target
            target.is_active = True
            await self._log_metadata_change(...)

        await self.session.commit()

    async def get_active_prompt(self, name: str) -> PromptTemplate | None:
        """Get active prompt with A/B testing logic."""
        active_prompts = await self.session.execute(...)

        if len(active_prompts) == 1:
            return PromptTemplateMapper.to_domain(active_prompts[0])

        # Weighted random selection
        return self._select_ab_variant(active_prompts)

    def _select_ab_variant(self, prompts: list) -> PromptTemplate:
        """Weighted random selection for A/B testing."""
        choices = prompts
        weights = [p.traffic_percentage for p in prompts]
        selected = random.choices(choices, weights=weights, k=1)[0]
        return PromptTemplateMapper.to_domain(selected)

    async def get_version_history(self, name: str) -> list[dict]:
        """Get version history with JSON diffs."""
        versions = await self.session.execute(...)

        history = []
        for version in versions:
            # Calculate diff with parent
            if version.parent_version_id:
                parent = await self.get_by_id(version.parent_version_id)
                diff = DeepDiff(parent.template_json, version.template_json)
                entry["diff"] = diff.to_dict()

            history.append(entry)

        return history
```

---

## Database Models & Mappers

**Add to**: `src/adapters/persistence/models.py`

```python
class PromptTemplateModel(Base):
    __tablename__ = "prompt_templates"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    version: Mapped[int] = mapped_column(Integer)
    parent_version_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("prompt_templates.id"))
    # ... 11 more fields

    executions: Mapped[list["PromptExecutionModel"]] = relationship(...)
    metadata_changes: Mapped[list["PromptMetadataChangeModel"]] = relationship(...)

class PromptMetadataChangeModel(Base):
    __tablename__ = "prompt_metadata_changes"
    # ... fields

class PromptExecutionModel(Base):
    __tablename__ = "prompt_executions"
    # ... fields

class PromptAnalyticsSummaryModel(Base):
    __tablename__ = "prompt_analytics_summary"
    # Materialized view (read-only)
```

**Add to**: `src/adapters/persistence/mappers.py`

```python
class PromptTemplateMapper:
    @staticmethod
    def to_domain(db_model: PromptTemplateModel) -> PromptTemplate:
        return PromptTemplate(
            id=db_model.id,
            name=db_model.name,
            # ... map all fields
        )

    @staticmethod
    def to_db_model(domain_model: PromptTemplate) -> PromptTemplateModel:
        return PromptTemplateModel(
            id=domain_model.id,
            name=domain_model.name,
            # ... map all fields
        )

class PromptMetadataChangeMapper:
    # ... similar pattern

class PromptExecutionMapper:
    # ... similar pattern
```

---

## Implementation Steps

### Step 1: Create Repository Port (1 day)
- [ ] Create `src/domain/ports/prompt_repository_port.py`
- [ ] Define all 14 abstract methods with docstrings
- [ ] Add type hints
- [ ] Document expected behavior

### Step 2: Add DB Models & Mappers (1 day)
- [ ] Add 4 models to `models.py`
- [ ] Add 3 mappers to `mappers.py`
- [ ] Add relationships
- [ ] Test model creation

### Step 3: Implement PostgreSQL Adapter (2-3 days)
- [ ] Create `postgres_prompt_repository.py`
- [ ] Implement version management methods
- [ ] Implement activation methods (with transactions)
- [ ] Implement retrieval methods (with A/B logic)
- [ ] Implement analytics methods
- [ ] Implement `_select_ab_variant()` helper
- [ ] Implement `_log_metadata_change()` helper

### Step 4: Integration Testing (1 day)
- [ ] Write integration tests for all methods
- [ ] Test transactions (activation)
- [ ] Test A/B selection distribution
- [ ] Test version history with diffs
- [ ] Test audit trail logging

---

## Testing

### Integration Tests

**File**: `tests/integration/test_prompt_repository.py`

**Test Cases**:
1. `test_create_initial_prompt` - Create v1
2. `test_create_new_version` - Fork from parent
3. `test_activate_version_deactivates_others` - Atomic transaction
4. `test_rollback_creates_new_version` - Rollback preserves history
5. `test_get_active_prompt_ab_testing` - Weighted selection (50/50 → ~50% each)
6. `test_get_version_history_with_diffs` - DeepDiff calculation
7. `test_get_audit_trail` - All metadata changes logged
8. `test_log_execution` - Analytics tracking
9. `test_get_analytics_summary` - Materialized view query

**Example Test**:

```python
async def test_activate_version_deactivates_others(db_session):
    """Test activation deactivates previous versions."""
    repo = PostgreSQLPromptRepository(db_session)

    # Create 2 versions
    v1 = await repo.create_initial_prompt("test", {}, "admin")
    v2 = await repo.create_new_version("test", 1, {}, "Update", "admin")

    # Activate v1
    await repo.activate_version(v1.id, "admin", "Test", traffic_percentage=100)

    # Activate v2 → should deactivate v1
    await repo.activate_version(v2.id, "admin", "Test", traffic_percentage=100)

    # Check: v1 inactive, v2 active
    v1_refreshed = await repo.get_by_id(v1.id)
    v2_refreshed = await repo.get_by_id(v2.id)

    assert not v1_refreshed.is_active
    assert v2_refreshed.is_active

async def test_ab_testing_distribution(db_session):
    """Test A/B selection distributes traffic correctly."""
    repo = PostgreSQLPromptRepository(db_session)

    # Create 2 active versions (50/50 split)
    v1 = await repo.create_initial_prompt("test", {...}, "admin")
    v2 = await repo.create_new_version("test", 1, {...}, "Variant", "admin")

    await repo.activate_version(v1.id, "admin", "Control", traffic_percentage=50, ab_test_group="control")
    await repo.activate_version(v2.id, "admin", "Variant", traffic_percentage=50, ab_test_group="variant_a")

    # Sample 1000 selections
    selections = {"v1": 0, "v2": 0}
    for _ in range(1000):
        selected = await repo.get_active_prompt("test")
        if selected.version == 1:
            selections["v1"] += 1
        else:
            selections["v2"] += 1

    # Verify ~50/50 distribution (±5% tolerance)
    assert 450 <= selections["v1"] <= 550
    assert 450 <= selections["v2"] <= 550
```

---

## Success Criteria

- ✅ All 14 port methods implemented
- ✅ DB models and mappers working
- ✅ Atomic activation transaction works
- ✅ A/B testing distributes traffic correctly (±5%)
- ✅ Version history includes JSON diffs
- ✅ Audit trail logs all metadata changes
- ✅ Integration tests passing (>85% coverage)
- ✅ Performance: `get_active_prompt()` <10ms

---

## Related Files

**New Files**:
- `src/domain/ports/prompt_repository_port.py`
- `src/adapters/persistence/postgres_prompt_repository.py`
- `tests/integration/test_prompt_repository.py`
- `tests/integration/test_prompt_version_workflow.py`
- `tests/integration/test_ab_testing_flow.py`

**Modified Files**:
- `src/adapters/persistence/models.py` (add 4 models)
- `src/adapters/persistence/mappers.py` (add 3 mappers)

---

## Next Phase

→ [Phase 4: Helper Utilities](./phase-04-helper-utilities.md)

**Blockers**: Phase 1 and 2 must be complete

---

## Notes

- Use `begin_nested()` for nested transactions (activation)
- A/B selection uses `random.choices()` for weighted random
- DeepDiff library handles JSON comparison
- Materialized view queried directly (no aggregation in Python)

---

**Phase Status**: Ready to implement
**Last Updated**: 2025-11-20
