# Phase 2: Domain Models

**Parent**: [Implementation Plan](./plan.md)
**Created**: 2025-11-24
**Duration**: 1-2 hours
**Priority**: High
**Status**: ⏳ Pending

---

## Context Links

- [Parent Plan](./plan.md)
- [Phase 1: Database Migration](./phase-01-database-migration.md)
- [Current Domain Models](../../src/domain/models/prompt_template.py)

---

## Overview

Update domain models to remove deleted fields. Simplify activation logic (no A/B testing). Remove A/B test service.

**Goals**:
- Remove unused fields from domain models
- Simplify activation methods
- Delete A/B test service
- Update model validators

---

## Key Insights

- Domain models must match new schema
- Activation logic simplified (always deactivate others)
- A/B test service no longer needed
- Model validators may need updates

---

## Requirements

### Functional Requirements
- Remove `ab_test_group`, `traffic_percentage`, `notes`, `template_json_legacy` from `PromptTemplate`
- Remove `reason` from `PromptMetadataChange`
- Remove `candidate_id`, `tokens_used` from `PromptExecution`
- Simplify `activate_version()` method signature
- Remove `adjust_ab_traffic()` method

### Non-Functional Requirements
- Maintain backward compatibility at API level
- Type hints remain complete
- Docstrings updated

---

## Architecture

### Domain Model Changes

```
PromptTemplate:
  - Remove: ab_test_group, traffic_percentage, notes, template_json_legacy
  - Keep: id, name, version, is_active, etc.

PromptMetadataChange:
  - Remove: reason
  - Keep: field_name, old_value, new_value, changed_by, changed_at

PromptExecution:
  - Remove: candidate_id, tokens_used
  - Keep: prompt_template_id, interview_id, prompt_tokens, completion_tokens, etc.
```

### Service Deletion

```
Delete: src/domain/services/ab_test_service.py
- No longer needed (A/B testing removed)
```

---

## Related Code Files

**Modified Files**:
- `src/domain/models/prompt_template.py`
- `src/domain/models/prompt_metadata_change.py`
- `src/domain/models/prompt_execution.py`
- `src/domain/ports/prompt_repository_port.py`

**Deleted Files**:
- `src/domain/services/ab_test_service.py`

---

## Implementation Steps

### Step 1: Update PromptTemplate Model

```python
# Remove fields
class PromptTemplate(BaseModel):
    # ... existing fields ...
    # REMOVE: ab_test_group, traffic_percentage, notes, template_json_legacy

    # Update activate_version method signature
    def activate_version(self, ...) -> None:
        # Simplified: always deactivate others
        pass
```

### Step 2: Update PromptMetadataChange Model

```python
# Remove reason field
class PromptMetadataChange(BaseModel):
    # ... existing fields ...
    # REMOVE: reason
```

### Step 3: Update PromptExecution Model

```python
# Remove fields
class PromptExecution(BaseModel):
    # ... existing fields ...
    # REMOVE: candidate_id, tokens_used
```

### Step 4: Update Repository Port

```python
# Remove adjust_ab_traffic method
# Simplify activate_version signature
async def activate_version(
    self,
    prompt_id: UUID,
    changed_by: str,
    reason: str,  # Keep for logging, but remove from model
) -> None:
    """Activate version (always deactivates others)."""
    pass
```

### Step 5: Delete A/B Test Service

```bash
# Delete file
rm src/domain/services/ab_test_service.py
```

### Step 6: Update Tests

- Remove tests for deleted fields
- Update activation tests (no A/B logic)
- Remove A/B test service tests

---

## Todo List

- [ ] Update `PromptTemplate` model (remove fields)
- [ ] Update `PromptMetadataChange` model (remove reason)
- [ ] Update `PromptExecution` model (remove fields)
- [ ] Update `PromptRepositoryPort` interface
- [ ] Delete `ab_test_service.py`
- [ ] Update domain model tests
- [ ] Verify type hints complete
- [ ] Update docstrings

---

## Success Criteria

- ✅ All domain models match new schema
- ✅ No references to deleted fields
- ✅ Type hints complete
- ✅ Tests updated and passing
- ✅ A/B test service removed

---

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Breaking existing code | Medium | Update all references |
| Missing field references | Low | Comprehensive search/replace |
| Test failures | Low | Update tests systematically |

---

## Security Considerations

- No security impact
- Ensure no sensitive data in removed fields

---

## Next Steps

- Proceed to Phase 3 (Persistence Layer)
- Update mappers to match domain models

