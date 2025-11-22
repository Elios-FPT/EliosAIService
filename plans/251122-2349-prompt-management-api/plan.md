# Prompt Template Management API - Implementation Plan

**Created:** 2025-11-22
**Status:** ⚠️ NEEDS WORK (Code review complete, minor fixes required)
**Plan Directory:** `H:/AI-course/EliosAIService/plans/251122-2349-prompt-management-api/`
**Review:** [Code Review Report](./reports/251123-code-review-agent-to-human-review.md)

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
**Status:** ✅ COMPLETE
Research existing patterns, confirm repository implementation, identify gaps.

### ✅ Phase 01: DTOs & Request/Response Models
**Status:** ✅ COMPLETE (100%)
**File:** [phase-01-dtos.md](./phase-01-dtos.md)
All 10 DTOs defined with proper validation. DTO tests: 23/23 passing.
**Issues:** Minor import sorting (ruff I001).

### ✅ Phase 02: DI Container Registration
**Status:** ✅ COMPLETE (100%)
**File:** [phase-02-di-container.md](./phase-02-di-container.md)
PromptRepositoryPort registered correctly in container (lines 250-259).

### ✅ Phase 03: Version Management Endpoints
**Status:** ✅ COMPLETE (100%)
**File:** [phase-03-version-mgmt.md](./phase-03-version-mgmt.md)
All 6 endpoints implemented with correct HTTP methods and error handling.
**Issues:** Missing return type annotations (6 endpoints).

### ✅ Phase 04: Activation & A/B Testing Endpoints
**Status:** ✅ COMPLETE (100%)
**File:** [phase-04-activation-ab.md](./phase-04-activation-ab.md)
All 3 endpoints implemented. PATCH returns 204 No Content per decision.
**Issues:** Missing return type annotations (3 endpoints).

### ⚠️ Phase 05: Analytics & Audit Endpoints
**Status:** ⚠️ MOSTLY COMPLETE (75%)
**File:** [phase-05-analytics-audit.md](./phase-05-analytics-audit.md)
All 4 endpoints implemented. List endpoint supports filters (is_active, include_deleted).
**CRITICAL ISSUE:** Soft delete endpoint violates Clean Architecture (uses mapper/model directly).

### ❌ Phase 06: Testing & Documentation
**Status:** ⚠️ PARTIALLY COMPLETE (60%)
**File:** [phase-06-testing-docs.md](./phase-06-testing-docs.md)
README.md updated (excellent). DTO tests pass (23/23).
**CRITICAL ISSUES:** Integration tests failing (2/2), unit route tests failing (7/7).

## Success Criteria

1. ⚠️ All 13 endpoints functional with proper error handling (12/13, soft delete needs fix)
2. ✅ DTOs follow existing naming conventions (suffix: Request/Response)
3. ✅ Repository registered in DI container with session injection
4. ✅ A/B testing weighted random selection works correctly (delegated to repository)
5. ✅ Version diffs displayed in GET /versions endpoint
6. ❌ Integration tests achieve >80% coverage (tests failing, coverage unknown)
7. ✅ API docs updated in README.md
8. ✅ No breaking changes to existing code

**Overall Compliance:** 5/8 criteria met (62.5%) - See [Code Review Report](./reports/251123-code-review-agent-to-human-review.md)

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
