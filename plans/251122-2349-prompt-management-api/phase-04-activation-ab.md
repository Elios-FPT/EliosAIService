# Phase 04: Activation & A/B Testing Endpoints

**Date:** 2025-11-22
**Status:** PENDING
**Priority:** HIGH
**Parent Plan:** [plan.md](./plan.md)
**Dependencies:** Phase 01 (DTOs), Phase 02 (DI Container), Phase 03 (Version Management)

## Context

Implement 3 endpoints for prompt activation lifecycle and A/B testing.
Enables production deployment strategies: full rollout (traffic=100%) or gradual A/B testing.

**Related Files:**
- [Router Pattern](../../src/adapters/api/rest/interview_routes.py)
- [DTOs](../../src/application/dto/prompt_dto.py)
- [Repository Port](../../src/domain/ports/prompt_repository_port.py)

## Overview

Add 3 endpoints to `src/adapters/api/rest/prompt_routes.py`:

1. PATCH `/api/prompts/{id}/activate` - Activate version (deactivates others if traffic=100%)
2. PATCH `/api/prompts/{id}/traffic` - Adjust A/B test traffic percentage
3. GET `/api/prompts/{name}/active` - Get current active prompt (with A/B weighted selection)

## Key Insights from Research

**A/B Testing Logic:**
- Repository handles weighted random selection based on traffic_percentage
- Multiple versions can be active simultaneously (sum of traffic ≤ 100%)
- Activation atomic operation (uses nested transactions)
- Metadata changes logged automatically

**State Transitions:**
- Draft → Active (activate_version with traffic=100%)
- Active → Inactive (activate different version with traffic=100%)
- Active (50%) + Active (50%) → A/B test (adjust_ab_traffic)

## Requirements

### Endpoint Specifications

#### 1. Activate Version
```python
@router.patch("/{prompt_id}/activate", status_code=204)
async def activate_prompt_version(
    prompt_id: UUID,
    request: ActivatePromptRequest,
    session: AsyncSession = Depends(get_async_session)
)
```
**Logic:**
- Call `prompt_repo.activate_version(prompt_id, changed_by, reason, traffic_percentage, ab_test_group)`
- Return 204 No Content (state change, no body needed)
- Raise 404 if prompt_id not found
- Raise 400 if traffic_percentage invalid or prompt is deleted

**Behavior:**
- If `traffic_percentage=100`: deactivates all other versions of same prompt
- If `traffic_percentage<100`: allows multiple active versions (A/B test)
- Logs metadata change to `prompt_metadata_changes` table

#### 2. Adjust A/B Traffic
```python
@router.patch("/{prompt_id}/traffic", status_code=204)
async def adjust_ab_traffic(
    prompt_id: UUID,
    request: AdjustTrafficRequest,
    session: AsyncSession = Depends(get_async_session)
)
```
**Logic:**
- Call `prompt_repo.adjust_ab_traffic(prompt_id, new_traffic_percentage, changed_by, reason)`
- Return 204 No Content
- Raise 404 if prompt_id not found
- Raise 400 if prompt not active or traffic invalid

**Validation:**
- Prompt must be currently active
- new_traffic_percentage must be 0-100
- Sum of active versions' traffic should ≤ 100% (repository validates)

#### 3. Get Active Prompt
```python
@router.get("/{name}/active", response_model=PromptTemplateResponse)
async def get_active_prompt(
    name: str,
    session: AsyncSession = Depends(get_async_session)
)
```
**Logic:**
- Call `prompt_repo.get_active_prompt(name)`
- Return PromptTemplateResponse.from_domain(prompt)
- Raise 404 if no active version exists

**A/B Behavior:**
- If single active version: returns that version
- If multiple active (A/B test): weighted random selection based on traffic_percentage
- Repository handles selection logic (not endpoint concern)

## Architecture

**Design Decisions:**
1. **204 No Content for PATCH:** State changes don't need response body (reduces payload)
2. **Atomic Activation:** Repository uses nested transactions for consistency
3. **Audit Logging:** Repository automatically logs all metadata changes
4. **Traffic Validation:** Repository enforces 0-100 range and sum constraints

**Alternative Considered:**
- Return updated PromptTemplate (200) instead of 204
- **Decision:** Use 204 to match RESTful conventions for state changes

## Implementation Steps

1. **Implement PATCH /{id}/activate**
   - Parse ActivatePromptRequest
   - Get prompt_repository_port from container
   - Call repository.activate_version()
   - Return 204 on success
   - Handle ValueError → 400 (validation errors)
   - Handle not found → 404

2. **Implement PATCH /{id}/traffic**
   - Parse AdjustTrafficRequest
   - Get prompt_repository_port from container
   - Call repository.adjust_ab_traffic()
   - Return 204 on success
   - Handle ValueError → 400 (prompt not active, invalid traffic)
   - Handle not found → 404

3. **Implement GET /{name}/active**
   - Get prompt_repository_port from container
   - Call repository.get_active_prompt(name)
   - Return PromptTemplateResponse.from_domain(prompt)
   - Raise 404 if None returned

4. **Add Error Handling**
   - Detailed error messages for validation failures
   - Log activation events for observability
   - Include context in 400 errors (current traffic, prompt name)

5. **Add Endpoint Documentation**
   - Docstrings explaining A/B testing logic
   - Examples for traffic_percentage scenarios
   - Notes on atomic operation behavior

## Todo List

- [ ] Implement PATCH /{id}/activate endpoint
- [ ] Implement PATCH /{id}/traffic endpoint
- [ ] Implement GET /{name}/active endpoint
- [ ] Add comprehensive error handling (404, 400)
- [ ] Add detailed docstrings with A/B testing examples
- [ ] Test activation with traffic=100% (deactivates others)
- [ ] Test A/B scenario (two versions with traffic=50% each)
- [ ] Test traffic adjustment edge cases (sum > 100%)
- [ ] Verify weighted random selection works
- [ ] Test concurrent activation requests (race conditions)

## Success Criteria

- ✅ Activation with traffic=100% deactivates other versions
- ✅ A/B testing allows multiple active versions
- ✅ Traffic adjustment validates constraints (0-100, sum ≤ 100)
- ✅ Weighted random selection returns different versions
- ✅ Metadata changes logged to audit table
- ✅ Concurrent activations handled safely (no race conditions)
- ✅ 204 returned for successful state changes
- ✅ 404 for missing prompts, 400 for validation errors

## Risk Assessment

**Medium Risk:**
- **Concurrent activations:** Race condition if two requests activate different versions simultaneously
  - **Mitigation:** Database constraints + nested transactions ensure atomicity
- **Weighted random selection correctness:** Traffic percentages must match probabilities
  - **Mitigation:** Repository layer tested thoroughly, use statistical validation
- **Sum of traffic > 100%:** Multiple active versions could exceed 100%
  - **Mitigation:** Repository validates sum before committing

**Low Risk:**
- API layer straightforward (delegates to repository)
- State machine logic in repository (already tested)

## Security Considerations

1. **Authorization:** Should activate_version require admin role? (Future: add RBAC)
2. **Audit Logging:** All changes logged with changed_by field for accountability
3. **Traffic Manipulation:** Validate traffic_percentage to prevent gaming A/B tests
4. **Concurrent Requests:** Nested transactions prevent race conditions

## Testing Strategy

**Unit Tests:**
- Mock repository, test endpoint logic only
- Verify 204/404/400 status codes
- Test error message formatting

**Integration Tests:**
- Real repository with test database
- Test activation workflow: v1 active → activate v2 → v1 inactive
- Test A/B scenario: activate v1 (50%) + v2 (50%) → adjust v1 (75%), v2 (25%)
- Test weighted selection: activate 1000 times, verify distribution matches traffic %

**Edge Cases:**
- Activate deleted prompt → 400
- Adjust traffic on inactive prompt → 400
- Get active when no version active → 404
- Sum of traffic = 100% exactly (valid)
- Sum of traffic > 100% (invalid)

## Next Steps

1. Implement all 3 endpoints in prompt_routes.py
2. Create integration tests for A/B testing workflow
3. Verify weighted selection statistical correctness
4. Proceed to Phase 05: Analytics & Audit Endpoints
