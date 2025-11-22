# Prompt Template Management API - Implementation Plan

**Created:** 2025-11-22
**Status:** READY
**Plan Directory:** `H:/AI-course/EliosAIService/plans/251122-2349-prompt-management-api/`

## Context

Add REST API for LLM prompt template management with version control, A/B testing, rollback, analytics.
Repository layer fully implemented; need API layer (routes, DTOs) and DI registration.

**Research Reports:**
- [API Patterns](./research/researcher-01-api-patterns.md)
- [Repository Patterns](./research/researcher-02-repository-patterns.md)

**Codebase Docs:**
- [System Architecture](../../docs/system-architecture.md)
- [Code Standards](../../docs/code-standards.md)
- [Codebase Summary](../../docs/codebase-summary.md)

## Implementation Phases

### ✅ Phase 00: Research & Analysis
**Status:** COMPLETE
Research existing patterns, confirm repository implementation, identify gaps.

### ⏳ Phase 01: DTOs & Request/Response Models
**Status:** PENDING
**File:** [phase-01-dtos.md](./phase-01-dtos.md)
Define 10 request/response DTOs matching API contract with `from_domain()` factory methods.

### ⏳ Phase 02: DI Container Registration
**Status:** PENDING
**File:** [phase-02-di-container.md](./phase-02-di-container.md)
Register PromptRepositoryPort in dependency container with session injection pattern.

### ⏳ Phase 03: Version Management Endpoints
**Status:** PENDING
**File:** [phase-03-version-mgmt.md](./phase-03-version-mgmt.md)
Implement 6 endpoints: create initial, create version, rollback, get version history, get specific version, get by ID.

### ⏳ Phase 04: Activation & A/B Testing Endpoints
**Status:** PENDING
**File:** [phase-04-activation-ab.md](./phase-04-activation-ab.md)
Implement 3 endpoints: activate version, adjust traffic, get active prompt (with A/B logic).

### ⏳ Phase 05: Analytics & Audit Endpoints
**Status:** PENDING
**File:** [phase-05-analytics-audit.md](./phase-05-analytics-audit.md)
Implement 3 endpoints: analytics summary, audit trail, list prompts (paginated).

### ⏳ Phase 06: Testing & Documentation
**Status:** PENDING
**File:** [phase-06-testing.md](./phase-06-testing.md)
Integration tests, error case validation, API docs update, postman collection.

## Success Criteria

1. ✅ All 12 endpoints functional with proper error handling
2. ✅ DTOs follow existing naming conventions (suffix: Request/Response)
3. ✅ Repository registered in DI container with session injection
4. ✅ A/B testing weighted random selection works correctly
5. ✅ Version diffs displayed in GET /versions endpoint
6. ✅ Integration tests achieve >80% coverage
7. ✅ API docs updated in README.md
8. ✅ No breaking changes to existing code

## Key Technical Decisions

- **No Use Case Layer:** Direct repository access from routes (matches existing pattern)
- **Factory Pattern:** DTOs use `from_domain()` for entity conversion
- **Session Injection:** `Depends(get_async_session)` for repository instantiation
- **Error Handling:** HTTPException with 400/404/500 status codes
- **Pagination:** Limit/offset pattern for list endpoint (future enhancement)
- **A/B Testing:** Weighted random selection based on traffic_percentage

## Dependencies

- ✅ PostgreSQLPromptRepository (fully implemented)
- ✅ PromptTemplate domain model
- ✅ FastAPI router patterns established
- ⚠️ Need pagination utility for list endpoint

## Risk Assessment

**Low Risk:**
- Repository already tested and working
- API patterns well-established in codebase
- No database schema changes needed

**Medium Risk:**
- A/B testing weighted random logic correctness
- Version diff display performance with large histories
- Pagination edge cases

## Unresolved Questions

1. Should list endpoint support filtering by is_active, is_deleted?
2. Pagination: Limit/offset or cursor-based?
3. Should we expose soft-delete endpoint or keep internal-only?
4. Rate limiting for analytics endpoints (high DB load)?
5. Should activate_version return updated PromptTemplate or 204 No Content?

**Decisions:** [DECISIONS.md](./DECISIONS.md)

## Next Steps

1. Review and approve this plan
2. Start Phase 01: DTOs & Request/Response Models
3. Proceed sequentially through phases 02-06
4. Run integration tests after Phase 03, 04, 05 completion
5. Update API documentation in Phase 06
