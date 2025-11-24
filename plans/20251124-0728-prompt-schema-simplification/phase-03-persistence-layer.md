# Phase 3: Persistence Layer

**Parent**: [Implementation Plan](./plan.md)
**Created**: 2025-11-24
**Duration**: 3-4 hours
**Priority**: High
**Status**: ⏳ Pending

---

## Context Links

- [Parent Plan](./plan.md)
- [Phase 2: Domain Models](./phase-02-domain-models.md)
- [Current Models](../../src/adapters/persistence/models.py)
- [Current Repository](../../src/adapters/persistence/postgres_prompt_repository.py)

---

## Overview

Update SQLAlchemy models, mappers, and repository implementation. Remove A/B testing logic. Simplify activation workflow.

**Goals**:
- Update database models to match schema
- Update mappers for field removal
- Simplify repository activation logic
- Update analytics summary model

---

## Key Insights

- SQLAlchemy models must match database schema exactly
- Mappers need field removal
- Activation logic simplified (no traffic percentage)
- Analytics model needs new fields

---

## Requirements

### Functional Requirements
- Remove fields from SQLAlchemy models
- Update mappers to exclude deleted fields
- Simplify `activate_version()` (always deactivate others)
- Remove `adjust_ab_traffic()` method
- Update `get_active_prompt()` (no A/B selection)
- Update `log_execution()` (remove candidate_id, tokens_used)
- Update analytics summary model

### Non-Functional Requirements
- Maintain query performance
- Keep transaction integrity
- Update all indexes appropriately

---

## Architecture

### Model Updates

```
PromptTemplateModel:
  - Remove: template_json_legacy, ab_test_group, traffic_percentage, notes

PromptMetadataChangeModel:
  - Remove: reason

PromptExecutionModel:
  - Remove: candidate_id, tokens_used

PromptAnalyticsSummaryModel:
  - Remove: ab_test_group, avg_tokens_used
  - Add: avg_prompt_tokens, avg_completion_tokens
```

### Repository Logic Changes

```
activate_version():
  - Remove traffic_percentage parameter
  - Always deactivate all other active versions
  - No A/B test group assignment

get_active_prompt():
  - Remove weighted random selection
  - Return single active version (or None)

log_execution():
  - Remove candidate_id parameter
  - Remove tokens_used (use prompt_tokens + completion_tokens)
```

---

## Related Code Files

**Modified Files**:
- `src/adapters/persistence/models.py`
- `src/adapters/persistence/mappers.py`
- `src/adapters/persistence/postgres_prompt_repository.py`

---

## Implementation Steps

### Step 1: Update SQLAlchemy Models

```python
# models.py
class PromptTemplateModel(Base):
    # Remove fields
    # template_json_legacy: REMOVED
    # ab_test_group: REMOVED
    # traffic_percentage: REMOVED
    # notes: REMOVED

class PromptMetadataChangeModel(Base):
    # reason: REMOVED

class PromptExecutionModel(Base):
    # candidate_id: REMOVED
    # tokens_used: REMOVED

class PromptAnalyticsSummaryModel(Base):
    # ab_test_group: REMOVED
    # avg_tokens_used: REMOVED
    # ADD: avg_prompt_tokens
    # ADD: avg_completion_tokens
```

### Step 2: Update Mappers

```python
# mappers.py
# Remove field mappings for deleted columns
# Update PromptAnalyticsSummaryMapper for new view structure
```

### Step 3: Update Repository - activate_version()

```python
async def activate_version(
    self,
    prompt_id: UUID,
    changed_by: str,
    reason: str,
) -> None:
    """Activate version (always deactivates others)."""
    target = await self.get_by_id(prompt_id)
    if not target:
        raise ValueError(f"Prompt {prompt_id} not found")

    async with self.session.begin_nested():
        # Always deactivate all other active versions
        result = await self.session.execute(
            select(PromptTemplateModel)
            .where(PromptTemplateModel.prompt_name == target.prompt_name)
            .where(PromptTemplateModel.is_active == True)
            .where(PromptTemplateModel.id != prompt_id)
        )
        for active_prompt in result.scalars().all():
            await self._log_metadata_change(...)
            active_prompt.is_active = False

        # Activate target
        target.is_active = True
        await self._log_metadata_change(...)

    await self.session.commit()
```

### Step 4: Remove adjust_ab_traffic()

```python
# DELETE entire method
```

### Step 5: Simplify get_active_prompt()

```python
async def get_active_prompt(self, name: str) -> PromptTemplate | None:
    """Get active prompt (only one active at a time)."""
    result = await self.session.execute(
        select(PromptTemplateModel)
        .where(PromptTemplateModel.prompt_name == name)
        .where(PromptTemplateModel.is_active == True)
        .limit(1)
    )
    db_model = result.scalar_one_or_none()
    return PromptTemplateMapper.to_domain(db_model) if db_model else None
```

### Step 6: Update log_execution()

```python
async def log_execution(
    self,
    prompt_template_id: UUID,
    execution_data: dict,
) -> PromptExecution:
    execution = PromptExecution(
        prompt_template_id=prompt_template_id,
        interview_id=execution_data.get("interview_id"),
        # candidate_id: REMOVED
        input_variables=execution_data["input_variables"],
        output_text=execution_data.get("output_text"),
        # tokens_used: REMOVED
        prompt_tokens=execution_data.get("prompt_tokens"),
        completion_tokens=execution_data.get("completion_tokens"),
        ...
    )
```

### Step 7: Update get_analytics_summary()

```python
# Update to use new view fields
# avg_prompt_tokens, avg_completion_tokens instead of avg_tokens_used
```

---

## Todo List

- [ ] Update `PromptTemplateModel` (remove fields)
- [ ] Update `PromptMetadataChangeModel` (remove reason)
- [ ] Update `PromptExecutionModel` (remove fields)
- [ ] Update `PromptAnalyticsSummaryModel` (new fields)
- [ ] Update `PromptTemplateMapper`
- [ ] Update `PromptMetadataChangeMapper`
- [ ] Update `PromptExecutionMapper`
- [ ] Update `PromptAnalyticsSummaryMapper`
- [ ] Simplify `activate_version()` method
- [ ] Remove `adjust_ab_traffic()` method
- [ ] Simplify `get_active_prompt()` method
- [ ] Update `log_execution()` method
- [ ] Update `get_analytics_summary()` method
- [ ] Update repository tests

---

## Success Criteria

- ✅ All models match database schema
- ✅ Mappers work correctly
- ✅ Activation logic simplified
- ✅ No A/B testing code remains
- ✅ Analytics queries return correct data
- ✅ All tests pass

---

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Breaking existing queries | High | Test all repository methods |
| Mapper errors | Medium | Test mapper conversions |
| Transaction issues | Medium | Test activation atomicity |

---

## Security Considerations

- No security impact
- Ensure transaction integrity maintained

---

## Next Steps

- Proceed to Phase 4 (Application Layer)
- Update DTOs and API routes

