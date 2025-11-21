# Implementation Plan: LangChainAdapter DB-Driven Prompt Migration

**Plan ID**: `251121-1654-db-prompt-migration`
**Created**: 2025-11-21
**Status**: READY FOR IMPLEMENTATION
**Estimated Effort**: 8-12 hours
**Risk Level**: MEDIUM (backward compatibility critical)

---

## Executive Summary

Migrate LangChainAdapter from hardcoded PROMPT_REGISTRY to database-driven prompts via PromptRepositoryPort. This enables version control, A/B testing, and prompt optimization without code deployments.

**Current State**:
- 13 methods in LangChainAdapter use PROMPT_REGISTRY (hardcoded)
- 1 method (generate_ideal_answer:268-287) already implements DB loading with fallback pattern
- DB infrastructure complete: PromptRepositoryPort, PostgresPromptRepository, migrations, analytics
- 7 prompts seeded (migration 0013): question_generation, answer_evaluation, ideal_answer_generation, rationale_generation, gap_detection, follow_up_generation, feedback_report
- **3 prompts missing**: cv_summary, skill_extraction, interview_recommendations

**Target State**:
- ALL 13 methods load DB prompts first, fallback to PROMPT_REGISTRY
- Execution logging via prompt_repo.log_execution() for analytics
- 3 missing prompts seeded in new migration 0014
- Backward compatibility preserved (PROMPT_REGISTRY remains fallback)
- Token usage, latency, success metrics tracked

---

## Architecture Principles Applied

### Clean Architecture
- **Domain Layer**: PromptRepositoryPort (interface) remains stable
- **Adapter Layer**: LangChainAdapter uses port interface, not concrete implementation
- **Dependency Inversion**: Adapter depends on PromptRepositoryPort abstraction

### SOLID Principles
- **Single Responsibility**: Each method has ONE job (load prompt, execute chain, log)
- **Open/Closed**: Adding DB prompts doesn't modify existing PROMPT_REGISTRY code
- **Dependency Inversion**: Adapter injects PromptRepositoryPort, not PostgreSQL implementation

### YAGNI, KISS, DRY
- **YAGNI**: Only migrate actual methods (no future features)
- **KISS**: Reuse existing generate_ideal_answer:268-287 pattern
- **DRY**: Centralize DB loading logic in helper method

---

## Method-to-DB-Prompt Mapping

| Method | DB Prompt Name | Current Status | Action |
|--------|----------------|----------------|--------|
| evaluate_answer | answer_evaluation | ❌ Hardcoded | Migrate |
| generate_ideal_answer | ideal_answer_generation | ✅ DB-enabled | Log execution |
| generate_rationale | rationale_generation | ❌ Hardcoded | Migrate |
| detect_concept_gaps | gap_detection | ❌ Hardcoded | Migrate |
| generate_followup_question | follow_up_generation | ❌ Hardcoded | Migrate |
| generate_feedback_report | feedback_report | ❌ Hardcoded | Migrate |
| summarize_cv | cv_summary | ❌ Hardcoded + Missing DB | Seed + Migrate |
| extract_skills_from_text | skill_extraction | ❌ Hardcoded + Missing DB | Seed + Migrate |
| generate_interview_recommendations | interview_recommendations | ❌ Hardcoded + Missing DB | Seed + Migrate |
| generate_questions_batch | question_generation | ❌ Hardcoded (batch) | Migrate |
| generate_ideal_answers_batch | ideal_answer_generation | ❌ Hardcoded (batch) | Migrate |
| generate_rationales_batch | rationale_generation | ❌ Hardcoded (batch) | Migrate |
| generate_question | question_generation | ❌ Not implemented | Skip (future) |

**Total**: 12 methods to migrate, 3 prompts to seed

---

## Implementation Phases

### Phase 1: Create Helper Methods
**File**: `src/adapters/llm/langchain_adapter.py`
**Effort**: 1 hour
**Details**: [phase-01-create-helper-methods.md](./phase-01-create-helper-methods.md)

- Create `_load_prompt_from_db(prompt_name: str) -> tuple[dict|None, str|None]`
- Standardize DB loading pattern (reuse generate_ideal_answer:268-287 logic)
- Handle errors, logging, fallback

### Phase 2: Refactor Single-Execution Methods
**Files**: `src/adapters/llm/langchain_adapter.py`
**Effort**: 3-4 hours
**Details**: [phase-02-refactor-methods.md](./phase-02-refactor-methods.md)

Migrate 9 methods:
- evaluate_answer → answer_evaluation
- generate_rationale → rationale_generation
- detect_concept_gaps → gap_detection
- generate_followup_question → follow_up_generation
- generate_feedback_report → feedback_report
- summarize_cv → cv_summary
- extract_skills_from_text → skill_extraction
- generate_interview_recommendations → interview_recommendations
- generate_ideal_answer (add logging only)

### Phase 3: Add Execution Logging
**Files**: `src/adapters/llm/langchain_adapter.py`
**Effort**: 2 hours
**Details**: [phase-03-add-execution-logging.md](./phase-03-add-execution-logging.md)

- Update `_log_execution()` to extract tokens from LangChain callbacks
- Add logging to all 9 refactored methods
- Handle LangSmith token tracking integration

### Phase 4: Create Migration 0014
**Files**: `alembic/versions/0014_251121_seed_missing_prompts.py`
**Effort**: 1 hour
**Details**: [phase-04-create-migration.md](./phase-04-create-migration.md)

Seed 3 missing prompts:
- cv_summary (from SUMMARIZE_CV_PROMPT)
- skill_extraction (from EXTRACT_SKILLS_PROMPT)
- interview_recommendations (from RECOMMENDATIONS_PROMPT)

### Phase 5: Update Tests
**Files**: `tests/unit/adapters/llm/test_langchain_adapter.py`
**Effort**: 2-3 hours
**Details**: [phase-05-update-tests.md](./phase-05-update-tests.md)

Test scenarios:
- DB prompt loading (happy path)
- Fallback to PROMPT_REGISTRY (DB failure)
- Execution logging (success/failure)
- A/B testing (multiple active prompts)
- Cache invalidation

### Phase 6: Code Review & Documentation
**Files**: Multiple
**Effort**: 1 hour
**Details**: [phase-06-code-review.md](./phase-06-code-review.md)

- Self-review against Clean Architecture, SOLID
- Update CLAUDE.md (prompt management workflow)
- Update docs/system-architecture.md (DB-driven prompts)
- Performance benchmarking (DB overhead)

---

## Risk Assessment & Mitigation

### Risk 1: DB Unavailable at Runtime
**Severity**: HIGH
**Probability**: LOW
**Impact**: Methods fail if DB down and no fallback
**Mitigation**:
- Preserve PROMPT_REGISTRY fallback in ALL methods
- Graceful degradation (log warning, continue with hardcoded)
- Test DB failure scenarios

### Risk 2: Breaking Existing Behavior
**Severity**: CRITICAL
**Probability**: MEDIUM
**Impact**: Interview sessions fail mid-conversation
**Mitigation**:
- Zero changes to method signatures (backward compatible)
- Comprehensive unit tests (before/after behavior)
- Integration tests with real DB
- Rollback plan (revert to PROMPT_REGISTRY only)

### Risk 3: Performance Degradation
**Severity**: MEDIUM
**Probability**: LOW
**Impact**: Latency increase from DB queries
**Mitigation**:
- Chain caching via `_db_chain_cache` (already implemented)
- Monitor latency in execution logs
- Optimize with DB connection pooling
- Benchmark before/after (target: <10ms overhead)

### Risk 4: Prompt Template Incompatibility
**Severity**: HIGH
**Probability**: MEDIUM
**Impact**: DB template missing required variables, LangChain fails
**Mitigation**:
- Validate template_json schema in migration
- `_get_or_build_chain()` validates required keys (lines 97-105)
- Fallback to PROMPT_REGISTRY if validation fails
- Unit tests for invalid templates

---

## Success Criteria

### Functional Requirements
- ✅ All 13 methods load DB prompts first
- ✅ Fallback to PROMPT_REGISTRY if DB fails
- ✅ Execution logging tracks: tokens, latency, success, model_name
- ✅ 3 missing prompts seeded in migration 0014
- ✅ Zero breaking changes (100% backward compatible)

### Non-Functional Requirements
- ✅ Performance: <10ms DB overhead per method call
- ✅ Test coverage: >90% on refactored methods
- ✅ Code quality: Passes ruff, black, mypy
- ✅ Documentation: Updated CLAUDE.md, system-architecture.md

### Rollback Criteria
If ANY of these occur, revert immediately:
- Interview sessions fail with DB errors
- Latency >50ms increase
- Token usage spikes >20%
- Test coverage drops below 85%

---

## Detailed Phase Breakdown

### Phase 1: Helper Methods (1 hour)
[📄 View Phase 1 Details](./phase-01-create-helper-methods.md)

**Deliverables**:
- `_load_prompt_from_db(prompt_name: str) -> tuple[dict|None, str|None]`
- `_should_log_execution(prompt_name: str) -> bool`
- Error handling with logging

**Acceptance Criteria**:
- Returns (template_json, cache_key) on success
- Returns (None, None) on failure (with warning log)
- Handles DB connection errors gracefully

---

### Phase 2: Refactor Methods (3-4 hours)
[📄 View Phase 2 Details](./phase-02-refactor-methods.md)

**Deliverables**:
- Migrate 9 single-execution methods
- Standardize pattern: load DB → _get_or_build_chain() → execute → log
- Preserve exact output format (no breaking changes)

**Acceptance Criteria**:
- Each method follows template:
  ```python
  template_json, cache_key = await self._load_prompt_from_db("prompt_name")
  chain = self._get_or_build_chain("method_name", template_json, cache_key)
  result = await chain.ainvoke(variables, config)
  await self._log_execution(...)
  ```
- No changes to method signatures or return types
- Fallback to PROMPT_REGISTRY if DB fails

---

### Phase 3: Execution Logging (2 hours)
[📄 View Phase 3 Details](./phase-03-add-execution-logging.md)

**Deliverables**:
- Enhanced `_log_execution()` with token extraction
- Integration with LangSmith callbacks (token tracking)
- Success/failure tracking

**Acceptance Criteria**:
- Log execution after EVERY DB prompt usage
- Extract tokens from LangChain model response metadata
- Handle missing token data gracefully (log warning)
- Track: prompt_tokens, completion_tokens, latency_ms, model_name, success

---

### Phase 4: Create Migration (1 hour)
[📄 View Phase 4 Details](./phase-04-create-migration.md)

**Deliverables**:
- Migration file: `0014_251121_seed_missing_prompts.py`
- Seed 3 prompts extracted from PROMPT_REGISTRY
- Downgrade function (rollback support)

**Acceptance Criteria**:
- Prompts validated against schema:
  ```json
  {
    "system": "...",
    "user_template": "...",
    "variables": ["var1", "var2"],
    "constraints": "..."
  }
  ```
- Alembic upgrade succeeds
- Alembic downgrade removes prompts cleanly

---

### Phase 5: Update Tests (2-3 hours)
[📄 View Phase 5 Details](./phase-05-update-tests.md)

**Deliverables**:
- Unit tests for DB loading + fallback
- Execution logging tests
- Integration tests with PostgreSQL
- Mock PromptRepository tests

**Test Coverage**:
- DB prompt loading (happy path)
- DB failure fallback (DB down, invalid template)
- Execution logging (success, failure, missing tokens)
- A/B testing (weighted selection)
- Cache behavior (hit/miss)

---

### Phase 6: Code Review (1 hour)
[📄 View Phase 6 Details](./phase-06-code-review.md)

**Deliverables**:
- Self-review checklist (Clean Architecture, SOLID, security)
- Updated documentation (CLAUDE.md, system-architecture.md)
- Performance benchmark report
- Rollback procedure documented

**Review Checklist**:
- ✅ No domain logic in adapter
- ✅ Dependency inversion preserved
- ✅ Error handling covers all edge cases
- ✅ No secrets in logs (input_variables may contain PII)
- ✅ Performance <10ms overhead

---

## Dependencies & Prerequisites

### Required Infrastructure
- ✅ PostgreSQL with prompt_templates, prompt_executions tables
- ✅ PromptRepositoryPort interface (domain/ports)
- ✅ PostgresPromptRepository implementation
- ✅ Migration 0013 applied (7 prompts seeded)

### Code Dependencies
- ✅ LangChain LCEL chains (already implemented)
- ✅ Chain caching (`_db_chain_cache`)
- ✅ LangSmith observability (callbacks)

### Development Tools
- ✅ Alembic (migrations)
- ✅ pytest (testing)
- ✅ ruff, black, mypy (code quality)

---

## Testing Strategy

### Unit Tests (Fast, No DB)
- Mock PromptRepository with predefined responses
- Test DB loading logic
- Test fallback to PROMPT_REGISTRY
- Test execution logging

### Integration Tests (Real DB)
- Test with PostgreSQL test database
- Test A/B testing (multiple active prompts)
- Test cache behavior
- Test analytics queries

### E2E Tests (Full Stack)
- Test interview flow with DB prompts
- Test prompt version rollback
- Test DB failure recovery

### Performance Tests
- Benchmark DB overhead (target: <10ms)
- Load test with 100 concurrent executions
- Memory profiling (cache size)

---

## Rollback Plan

### Scenario 1: DB Failures in Production
**Trigger**: Error rate >5% with "DB prompt loading failed"
**Action**: No action needed (fallback automatic)
**Verification**: Check logs for "Falling back to hardcoded chain"

### Scenario 2: Breaking Changes Detected
**Trigger**: Interview sessions fail, tests fail
**Action**:
1. Revert to commit before migration
2. Run alembic downgrade -1 (remove migration 0014)
3. Deploy previous version
4. Verify PROMPT_REGISTRY working

### Scenario 3: Performance Degradation
**Trigger**: Latency >50ms increase
**Action**:
1. Set `USE_DB_PROMPTS=false` in env (if implemented)
2. Investigate DB connection pooling
3. Optimize queries (add indexes)

---

## Monitoring & Metrics

### Key Metrics
- **DB Prompt Usage**: % of executions using DB vs fallback
- **Latency**: p50, p95, p99 latency for DB prompt loading
- **Token Usage**: Compare DB prompts vs PROMPT_REGISTRY
- **Success Rate**: % of successful executions

### Alerts
- ⚠️ DB prompt loading failure rate >5%
- ⚠️ Latency increase >50ms
- ⚠️ Token usage spike >20%
- 🔥 Interview session failure rate >1%

### Dashboards
- LangSmith: Token usage, cost tracking
- PostgreSQL: prompt_analytics_summary view
- Application logs: Execution success/failure

---

## Post-Implementation Tasks

### Immediate (Week 1)
- Monitor DB prompt usage metrics
- Validate execution logging accuracy
- Review LangSmith traces for anomalies

### Short-term (Month 1)
- Analyze prompt performance (A/B testing)
- Optimize slow prompts (version updates)
- Document prompt engineering best practices

### Long-term (Quarter 1)
- Build prompt management UI (admin panel)
- Implement automated prompt testing
- Create prompt optimization playbook

---

## File Manifest

```
plans/251121-1654-db-prompt-migration/
├── plan.md (THIS FILE)
├── phase-01-create-helper-methods.md
├── phase-02-refactor-methods.md
├── phase-03-add-execution-logging.md
├── phase-04-create-migration.md
├── phase-05-update-tests.md
└── phase-06-code-review.md
```

---

## References

### Codebase Files
- `src/adapters/llm/langchain_adapter.py` - Main implementation file
- `src/adapters/llm/prompts/__init__.py` - PROMPT_REGISTRY source
- `src/domain/ports/prompt_repository_port.py` - Interface
- `src/adapters/persistence/postgres_prompt_repository.py` - Implementation
- `alembic/versions/0013_251120_seed_initial_prompts.py` - Existing seed

### Documentation
- `docs/system-architecture.md` - Architecture overview
- `docs/code-standards.md` - Clean Architecture, SOLID principles
- `.claude/workflows/development-rules.md` - Development guidelines

### Related Issues
- None (proactive refactoring)

---

## Approval & Sign-off

**Reviewed By**: Claude Code (AI Planner)
**Review Date**: 2025-11-21
**Approved For**: Implementation

**Next Steps**:
1. Review plan with team
2. Begin Phase 1 implementation
3. Update plan status as phases complete

---

**END OF PLAN**
