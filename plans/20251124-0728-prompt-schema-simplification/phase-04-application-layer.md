# Phase 4: Application Layer

**Parent**: [Implementation Plan](./plan.md)
**Created**: 2025-11-24
**Duration**: 2-3 hours
**Priority**: Medium
**Status**: ⏳ Pending

---

## Context Links

- [Parent Plan](./plan.md)
- [Phase 3: Persistence Layer](./phase-03-persistence-layer.md)
- [Current DTOs](../../src/application/dto/prompt_dto.py)
- [Current API Routes](../../src/adapters/api/rest/prompt_routes.py)

---

## Overview

Update DTOs and API routes to remove deleted fields. Remove A/B testing endpoints. Update analytics response structure.

**Goals**:
- Remove fields from request/response DTOs
- Remove `adjust_ab_traffic` endpoint
- Update `activate_version` endpoint
- Update analytics summary response

---

## Key Insights

- DTOs must match domain models
- API responses should exclude removed fields
- Endpoint signatures need updates
- Analytics response structure changed

---

## Requirements

### Functional Requirements
- Remove fields from DTOs
- Remove `adjust_ab_traffic` endpoint
- Update `activate_version` endpoint (remove traffic params)
- Update `AnalyticsSummaryResponse` (new fields)

### Non-Functional Requirements
- Maintain API backward compatibility where possible
- Update OpenAPI documentation
- Keep response validation

---

## Architecture

### DTO Updates

```
PromptTemplateRequest/Response:
  - Remove: ab_test_group, traffic_percentage, notes

ActivatePromptRequest:
  - Remove: traffic_percentage, ab_test_group

AnalyticsSummaryResponse:
  - Remove: ab_test_group, avg_tokens_used
  - Add: avg_prompt_tokens, avg_completion_tokens
```

### API Endpoint Changes

```
DELETE: PATCH /api/prompts/{id}/traffic
UPDATE: PATCH /api/prompts/{id}/activate (remove params)
UPDATE: GET /api/prompts/{name}/analytics (new response structure)
```

---

## Related Code Files

**Modified Files**:
- `src/application/dto/prompt_dto.py`
- `src/adapters/api/rest/prompt_routes.py`

---

## Implementation Steps

### Step 1: Update DTOs

```python
# prompt_dto.py
class PromptTemplateResponse(BaseModel):
    # Remove: ab_test_group, traffic_percentage, notes
    # ... existing fields ...

class ActivatePromptRequest(BaseModel):
    # Remove: traffic_percentage, ab_test_group
    changed_by: str
    reason: str

class AnalyticsSummaryResponse(BaseModel):
    # Remove: ab_test_group, avg_tokens_used
    # Add: avg_prompt_tokens, avg_completion_tokens
    total_executions: int
    avg_prompt_tokens: float | None
    avg_completion_tokens: float | None
    avg_latency_ms: float | None
    success_rate: float
    estimated_cost_usd: float
    last_executed_at: datetime | None
```

### Step 2: Update activate_version Endpoint

```python
@router.patch("/{prompt_id}/activate", status_code=204)
async def activate_prompt_version(
    prompt_id: UUID,
    request: ActivatePromptRequest,
    session: AsyncSession = Depends(get_async_session),
) -> None:
    """Activate prompt version (deactivates others)."""
    repo = PostgreSQLPromptRepository(session)
    await repo.activate_version(
        prompt_id=prompt_id,
        changed_by=request.changed_by,
        reason=request.reason,
    )
```

### Step 3: Remove adjust_ab_traffic Endpoint

```python
# DELETE entire endpoint
# @router.patch("/{prompt_id}/traffic", ...)
```

### Step 4: Update get_analytics_summary Endpoint

```python
@router.get("/{name}/analytics")
async def get_analytics_summary(
    name: str,
    session: AsyncSession = Depends(get_async_session),
) -> AnalyticsSummaryResponse:
    """Get analytics summary for active prompt."""
    repo = PostgreSQLPromptRepository(session)
    summary = await repo.get_analytics_summary(name)

    return AnalyticsSummaryResponse(
        total_executions=summary["total_executions"],
        avg_prompt_tokens=summary["avg_prompt_tokens"],
        avg_completion_tokens=summary["avg_completion_tokens"],
        avg_latency_ms=summary["avg_latency_ms"],
        success_rate=summary["success_rate"],
        estimated_cost_usd=summary["estimated_cost_usd"],
        last_executed_at=summary["last_executed_at"],
    )
```

### Step 5: Update API Tests

- Remove tests for deleted endpoints
- Update activation tests
- Update analytics tests

---

## Todo List

- [ ] Update `PromptTemplateResponse` DTO
- [ ] Update `ActivatePromptRequest` DTO
- [ ] Update `AnalyticsSummaryResponse` DTO
- [ ] Update `activate_version` endpoint
- [ ] Remove `adjust_ab_traffic` endpoint
- [ ] Update `get_analytics_summary` endpoint
- [ ] Update API tests
- [ ] Update OpenAPI documentation

---

## Success Criteria

- ✅ All DTOs match domain models
- ✅ API endpoints work correctly
- ✅ Removed endpoints deleted
- ✅ Analytics response correct
- ✅ All API tests pass
- ✅ OpenAPI docs updated

---

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Breaking API clients | Medium | Version API if needed |
| Response validation errors | Low | Test all endpoints |
| Missing field references | Low | Comprehensive search |

---

## Security Considerations

- No security impact
- Ensure input validation maintained

---

## Next Steps

- Proceed to Phase 5 (LLM Adapters)
- Update only `langchain_adapter.py`

