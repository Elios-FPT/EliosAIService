# Implementation Decisions - RESOLVED

**Date:** 2025-11-22
**Status:** APPROVED

## Questions Resolved

### 1. List Endpoint Filtering
**Question:** Should list endpoint support filtering by `is_active`, `is_deleted`?
**Decision:** ✅ **YES**

**Implementation:**
```python
@router.get("", response_model=PaginatedPromptsResponse)
async def list_prompts(
    is_active: bool | None = Query(None, description="Filter by active status"),
    include_deleted: bool = Query(False, description="Include soft-deleted prompts"),
    ...
)
```

**Rationale:** Essential for DevOps filtering active vs draft prompts, and debugging deleted templates.

---

### 2. Pagination Strategy
**Question:** Limit/offset or cursor-based?
**Decision:** ✅ **Limit/Offset**

**Implementation:**
```python
page: int = Query(1, ge=1, description="Page number (1-indexed)")
page_size: int = Query(20, ge=1, le=100, description="Items per page")
```

**Rationale:**
- **Simple:** Easy to implement, understand, test
- **SQL Native:** Direct LIMIT/OFFSET mapping
- **Client-Friendly:** Supports direct page jumping
- **Good Enough:** Prompts unlikely to exceed 10k records
- **Consistent:** Matches potential future codebase patterns

**Why Not Cursor-Based:**
- Overkill for prompt management (not 100k+ records)
- More complex implementation
- Can't jump to arbitrary pages
- Better for infinite scroll scenarios (not applicable here)

---

### 3. Soft Delete Endpoint
**Question:** Expose soft-delete endpoint or keep internal-only?
**Decision:** ✅ **EXPOSE**

**Implementation:** Add 13th endpoint
```python
@router.delete("/{prompt_id}", status_code=204)
async def soft_delete_prompt(
    prompt_id: UUID,
    session: AsyncSession = Depends(get_async_session)
)
```

**Rationale:**
- Enables API-driven lifecycle management
- Audit trail preserved (deleted_at timestamp)
- Can be reversed (undelete via setting deleted_at=None if needed)
- Follows RESTful conventions (DELETE verb)

**Phase Update:** Phase 05 now includes 4 endpoints (was 3)

---

### 4. Rate Limiting
**Question:** Rate limiting for analytics endpoints (high DB load)?
**Decision:** ✅ **NO** (not implemented)

**Rationale:**
- Analytics queries use **materialized view** (pre-aggregated, fast)
- Prompt management internal DevOps tool (trusted users)
- Can add later if load becomes issue
- Focus on core functionality first

**Future Consideration:** Monitor query latency; add if p95 > 500ms

---

### 5. PATCH Response Format
**Question:** Return updated PromptTemplate (200) or 204 No Content?
**Decision:** ✅ **204 No Content**

**Implementation:**
```python
@router.patch("/{prompt_id}/activate", status_code=204)
@router.patch("/{prompt_id}/traffic", status_code=204)
```

**Rationale:**
- **RESTful Convention:** State changes without body return 204
- **Performance:** No need to serialize/deserialize response
- **Consistency:** Matches PATCH semantics (modify resource state)
- **Client Flow:** Client can GET active prompt if needed

**Alternative Considered:** Return 200 with updated PromptTemplateResponse
- More data transfer
- Client may not need full response
- Less RESTful for state-only changes

---

## Updated Endpoint Count

**Total Endpoints:** 13 (was 12)

**Breakdown:**
- **Version Management:** 6 endpoints
- **Activation & A/B Testing:** 3 endpoints
- **Analytics & Audit:** 3 endpoints
- **Lifecycle Management:** 1 endpoint (soft delete) ← NEW

---

## Updated Success Criteria

- [ ] All **13** endpoints functional (updated from 12)
- [ ] List endpoint supports `is_active` and `include_deleted` filters
- [ ] Pagination with limit/offset (`?page=1&page_size=20`)
- [ ] PATCH endpoints return 204 No Content
- [ ] Soft delete endpoint sets `deleted_at` timestamp
- [ ] No rate limiting implemented (materialized view fast enough)

---

## Phase Updates Required

### Phase 01 (DTOs)
No changes - existing DTOs sufficient

### Phase 05 (Analytics & Audit)
**Updated:** Add soft-delete endpoint (4 endpoints total)

**New Endpoint:**
```python
DELETE /{prompt_id} - Soft delete prompt template
```

**New DTO:** None needed (204 response)

---

## Implementation Priority

1. ✅ **Phase 01-04:** Proceed as planned
2. ✅ **Phase 05:** Add soft-delete endpoint (simple addition)
3. ✅ **Phase 06:** Update test count to reflect 13 endpoints

---

## Migration Path (If Decisions Change)

### Add Cursor-Based Pagination Later
- Keep limit/offset as primary
- Add optional `cursor` query param
- Backward compatible

### Add Rate Limiting Later
- Implement as middleware
- Configure per-endpoint thresholds
- No code changes to endpoints

### Change PATCH to 200
- Simple status code change
- Add response_model back
- Return `PromptTemplateResponse.from_domain()`

---

**All decisions finalized. Ready to proceed with implementation.**
