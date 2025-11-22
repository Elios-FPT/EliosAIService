# Phase 05: Analytics, Audit & Lifecycle Endpoints

**Date:** 2025-11-22 (Updated with soft-delete endpoint)
**Status:** PENDING
**Priority:** MEDIUM
**Parent Plan:** [plan.md](./plan.md)
**Dependencies:** Phase 01 (DTOs), Phase 02 (DI Container)
**Decisions:** [DECISIONS.md](./DECISIONS.md)

## Context

Implement 4 endpoints for observability and lifecycle management: analytics metrics, audit trail, prompt list, soft delete.
Enable DevOps/ML teams to monitor prompt performance, track configuration changes, and manage template lifecycle.

**Related Files:**
- [Analytics View](../../alembic/versions/0012_251120_create_prompt_analytics_view.py)
- [DTOs](../../src/application/dto/prompt_dto.py)
- [Repository Port](../../src/domain/ports/prompt_repository_port.py)

## Overview

Add 4 endpoints to `src/adapters/api/rest/prompt_routes.py`:

1. GET `/api/prompts/{name}/analytics` - Analytics summary (executions, tokens, cost, latency)
2. GET `/api/prompts/{name}/audit-trail` - Metadata change history (activation, traffic adjustments)
3. GET `/api/prompts` - List all prompts (paginated, filterable by is_active, include_deleted)
4. DELETE `/api/prompts/{prompt_id}` - Soft delete prompt template (**NEW**)

## Key Insights from Research

**Analytics Data Source:**
- Materialized view `prompt_analytics_summary` (pre-aggregated)
- Refreshed periodically (not real-time)
- Includes: executions, avg tokens, latency, success rate, cost

**Audit Trail:**
- Table `prompt_metadata_changes` logs all non-version changes
- Tracks: field_name, old_value, new_value, changed_by, reason
- Chronological order (changed_at DESC)

**Pagination:**
- Not yet implemented in codebase
- Recommendation: Limit/offset pattern (simple, matches SQL)
- Alternative: Cursor-based (better performance for large datasets)

## Requirements

### Endpoint Specifications

#### 1. Get Analytics Summary
```python
@router.get("/{name}/analytics", response_model=AnalyticsSummaryResponse)
async def get_analytics_summary(
    name: str,
    session: AsyncSession = Depends(get_async_session)
)
```
**Logic:**
- Call `prompt_repo.get_analytics_summary(name)`
- Convert dict to AnalyticsSummaryResponse
- Raise 404 if no analytics data exists (prompt never executed)

**Response Fields:**
- total_executions: int
- avg_tokens_used: float
- avg_latency_ms: float
- success_rate: float (0.0-1.0)
- estimated_cost_usd: float
- last_executed_at: datetime | None

#### 2. Get Audit Trail
```python
@router.get("/{name}/audit-trail", response_model=list[AuditTrailResponse])
async def get_audit_trail(
    name: str,
    session: AsyncSession = Depends(get_async_session)
)
```
**Logic:**
- Call `prompt_repo.get_audit_trail(name)`
- Convert list[dict] to list[AuditTrailResponse]
- Return empty list if no audit entries (not 404)

**Response Fields:**
- field_name: str (e.g., "is_active", "traffic_percentage")
- old_value: str (serialized)
- new_value: str (serialized)
- changed_by: str
- changed_at: datetime
- reason: str

**Sorting:** Chronological order (changed_at DESC)

#### 3. List All Prompts (Paginated)
```python
@router.get("", response_model=PaginatedPromptsResponse)
async def list_prompts(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    is_active: bool | None = Query(None, description="Filter by active status"),
    include_deleted: bool = Query(False, description="Include soft-deleted prompts"),
    session: AsyncSession = Depends(get_async_session)
)
```
**Logic:**
- Calculate offset: `(page - 1) * page_size`
- Query prompts with filters (is_active, deleted_at)
- Count total matching prompts
- Return PaginatedPromptsResponse with metadata

**Response Fields:**
- prompts: list[PromptTemplateResponse]
- total: int (total matching prompts)
- page: int
- page_size: int
- has_next: bool (calculated: page * page_size < total)

**Filters:**
- `is_active=true/false` - Filter by activation status
- `include_deleted=true` - Include soft-deleted prompts (default: false)

#### 4. Soft Delete Prompt
```python
@router.delete("/{prompt_id}", status_code=204)
async def soft_delete_prompt(
    prompt_id: UUID,
    session: AsyncSession = Depends(get_async_session)
)
```
**Logic:**
- Get prompt by ID via repository
- Call `prompt.soft_delete()` domain method (sets deleted_at timestamp)
- Update via repository.update()
- Return 204 No Content
- Raise 404 if prompt not found
- Raise 400 if already deleted

**Behavior:**
- Sets `deleted_at` to current UTC timestamp
- Sets `is_active` to False (cascade deactivation)
- Preserves all data (soft delete, not hard delete)
- Audit trail preserved
- Can be reversed by setting `deleted_at=None` (future feature)

## Architecture

**Design Decisions:**
1. **Pagination Strategy:** Limit/offset (simple, matches existing interview_routes pattern)
2. **Default Page Size:** 20 items (balance between UX and DB load)
3. **Max Page Size:** 100 items (prevent excessive DB queries)
4. **Empty Results:** Return empty list (not 404) for audit trail and list endpoints
5. **Analytics 404:** Return 404 if prompt never executed (no data meaningful)

**Repository Method Addition:**
```python
# Need to add to PromptRepositoryPort
async def list_prompts(
    self,
    limit: int,
    offset: int,
    is_active: bool | None = None,
    include_deleted: bool = False
) -> tuple[list[PromptTemplate], int]:
    """List prompts with pagination.

    Returns:
        Tuple of (prompts, total_count)
    """
```

## Implementation Steps

1. **Add Repository Method**
   - Add `list_prompts()` to PromptRepositoryPort interface
   - Implement in PostgreSQLPromptRepository
   - Query with LIMIT, OFFSET, filters
   - Count total matching prompts (separate query)

2. **Implement GET /{name}/analytics**
   - Call repository.get_analytics_summary()
   - Convert dict to AnalyticsSummaryResponse
   - Raise 404 if None
   - Handle edge case: prompt exists but never executed

3. **Implement GET /{name}/audit-trail**
   - Call repository.get_audit_trail()
   - Convert list[dict] to list[AuditTrailResponse]
   - Return empty list if no entries
   - Sort by changed_at DESC (repository handles)

4. **Implement GET /**
   - Parse query parameters (page, page_size, is_active, include_deleted)
   - Calculate offset = (page - 1) * page_size
   - Call repository.list_prompts(limit, offset, filters)
   - Build PaginatedPromptsResponse with has_next calculation
   - Return 200 with pagination metadata

5. **Implement DELETE /{prompt_id}** (Soft Delete)
   - Get prompt by ID via repository.get_by_id()
   - Check if already deleted (prompt.is_deleted()) → raise 400
   - Call prompt.soft_delete() domain method
   - Update via repository.update()
   - Return 204 No Content
   - Handle not found → 404

6. **Add Query Parameter Validation**
   - page ≥ 1 (1-indexed)
   - page_size: 1-100 range
   - Default page_size=20

## Todo List

- [ ] Add `list_prompts()` method to PromptRepositoryPort
- [ ] Implement `list_prompts()` in PostgreSQLPromptRepository
- [ ] Implement GET /{name}/analytics endpoint
- [ ] Implement GET /{name}/audit-trail endpoint
- [ ] Implement GET / endpoint with pagination
- [ ] Implement DELETE /{prompt_id} endpoint (soft delete)
- [ ] Add query parameter validation (page, page_size)
- [ ] Test pagination edge cases (page beyond total, empty results)
- [ ] Test analytics endpoint with no execution data
- [ ] Test audit trail with many entries (performance)
- [ ] Test soft delete (already deleted → 400, success → 204)
- [ ] Verify has_next calculation correct
- [ ] Add docstrings explaining filter parameters

## Success Criteria

- ✅ All 4 endpoints functional (analytics, audit, list, soft delete)
- ✅ Analytics endpoint returns data from materialized view
- ✅ Audit trail chronologically ordered (DESC)
- ✅ Pagination works correctly (limit, offset, has_next)
- ✅ Filters work (is_active, include_deleted)
- ✅ Soft delete sets deleted_at and is_active=False
- ✅ Soft delete returns 204, prevents double-delete (400)
- ✅ Empty results return [] not 404 (except analytics)
- ✅ Page size validation enforced (1-100)
- ✅ Total count accurate for filtered results
- ✅ Performance acceptable for large prompt lists (>1000 prompts)

## Risk Assessment

**Medium Risk:**
- **Analytics refresh lag:** Materialized view not real-time
  - **Mitigation:** Document refresh schedule, add last_updated_at to response
- **Audit trail performance:** Many metadata changes could slow query
  - **Mitigation:** Add pagination to audit trail if needed
- **List endpoint performance:** Large offset values slow (OFFSET 10000)
  - **Mitigation:** Document max page recommendation, consider cursor-based later

**Low Risk:**
- Read-only endpoints (no state changes)
- Repository methods already implemented (analytics, audit)

## Security Considerations

1. **PII in Audit Trail:** changed_by field may contain usernames
   - **Mitigation:** Sanitize in logs, consider hashing
2. **Analytics Exposure:** Cost data reveals LLM usage patterns
   - **Mitigation:** Add authorization checks (future RBAC)
3. **DoS via Pagination:** Large page_size could overload DB
   - **Mitigation:** Max page_size=100, rate limiting recommended

## Testing Strategy

**Unit Tests:**
- Mock repository, test DTO conversions
- Verify pagination math (offset, has_next)
- Test filter combinations

**Integration Tests:**
- Query analytics for prompt with executions
- Query audit trail with multiple changes
- Test pagination: first page, middle page, last page, beyond total
- Test filters: is_active=true, include_deleted=true
- Performance test: list 1000+ prompts

**Edge Cases:**
- Analytics for never-executed prompt → 404
- Audit trail for prompt with no changes → []
- List with page beyond total → empty list with has_next=false
- List with is_active=None → all prompts regardless of status

## Performance Considerations

**Materialized View Refresh:**
- Currently manual: `REFRESH MATERIALIZED VIEW CONCURRENTLY prompt_analytics_summary`
- Recommendation: Add cron job or trigger-based refresh (every 5 minutes)
- Include refresh timestamp in response for transparency

**Pagination Optimization:**
- Use indexed columns for filtering (is_active, deleted_at)
- Consider adding composite index: (is_active, deleted_at, created_at)
- For very large datasets (>10k prompts), recommend cursor-based pagination

## Next Steps

1. Add list_prompts() to repository interface and implementation
2. Implement all 3 endpoints in prompt_routes.py
3. Test pagination thoroughly (edge cases)
4. Proceed to Phase 06: Testing & Documentation
