# Prompt Schema Simplification - Implementation Plan

**Created**: 2025-11-24
**Plan ID**: 20251124-0728
**Status**: 📋 Planning Complete
**Complexity**: Medium (2-3 days)
**Architecture**: Clean Architecture (Ports & Adapters)

---

## Executive Summary

Simplify prompt management schema by removing unused fields and A/B testing complexity. Keep UUID-based structure for maintainability. Remove: `template_json_legacy`, `ab_test_group`, `traffic_percentage`, `notes`, `reason`, `candidate_id`, `tokens_used`. Update analytics view to use separate prompt/completion token averages.

**Key Changes**:
- ✅ Remove A/B testing (one active version at a time)
- ✅ Remove unused/redundant fields
- ✅ Simplify activation logic
- ✅ Update analytics view structure
- ✅ Only update `langchain_adapter.py` (not other LLM adapters)

**Tech Stack**: Python 3.11+, PostgreSQL, SQLAlchemy 2.0 async, Alembic

---

## Implementation Phases

| Phase | Description | Duration | Status | Progress |
|-------|-------------|----------|--------|----------|
| **[Phase 1](./phase-01-database-migration.md)** | Database Migration | 2-3 hours | ⏳ Pending | 0% |
| **[Phase 2](./phase-02-domain-models.md)** | Domain Models | 1-2 hours | ⏳ Pending | 0% |
| **[Phase 3](./phase-03-persistence-layer.md)** | Persistence Layer | 3-4 hours | ⏳ Pending | 0% |
| **[Phase 4](./phase-04-application-layer.md)** | Application Layer | 2-3 hours | ⏳ Pending | 0% |
| **[Phase 5](./phase-05-llm-adapters.md)** | LLM Adapters | 1-2 hours | ⏳ Pending | 0% |

**Total Estimate**: 9-14 hours (2-3 days for 1 developer)

---

## Architecture Overview

### Schema Changes

**prompt_templates**:
- Remove: `template_json_legacy`, `ab_test_group`, `traffic_percentage`, `notes`
- Keep: UUID `id` as primary key

**prompt_metadata_changes**:
- Remove: `reason`

**prompt_executions**:
- Remove: `candidate_id`, `tokens_used`

**prompt_analytics_summary** (view):
- Remove: `ab_test_group`, `avg_tokens_used`
- Add: `avg_prompt_tokens`, `avg_completion_tokens`

---

## Deliverables

**New Files**:
- 1 Alembic migration (`0016_simplify_prompt_schema.py`)

**Modified Files** (10):
- Domain models (3 files)
- Persistence models/mappers (2 files)
- Repository (1 file)
- DTOs (1 file)
- API routes (1 file)
- LLM adapter (1 file - `langchain_adapter.py` only)
- Delete: `ab_test_service.py`

---

## Success Criteria

- ✅ All tests pass
- ✅ Migration completes without errors
- ✅ No data loss
- ✅ API responses valid (removed fields excluded)
- ✅ Analytics view returns correct metrics
- ✅ Activation workflow works (one active at a time)

---

## Timeline

| Day | Phases | Deliverables |
|-----|--------|--------------|
| **Day 1** | Phase 1-2 | DB migration + Domain models |
| **Day 2** | Phase 3-4 | Persistence + Application layer |
| **Day 3** | Phase 5 + Testing | LLM adapters + Integration testing |

---

## Key Design Decisions

1. **Keep UUID `id`**: Maintain current structure (no composite PK)
2. **Remove A/B Testing**: One active version at a time
3. **Simplified Activation**: Always deactivate others when activating
4. **Analytics Update**: Separate prompt/completion token averages

---

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Breaking existing queries | Medium | High | Comprehensive test suite |
| Data loss during migration | Low | High | Backup before migration |
| Performance regression | Low | Medium | Monitor query performance |

---

## References

- [Brainstorming Session](../251120-0226-prompt-management-system/phase-01-database-schema.md)
- [Current Schema](../251120-0226-prompt-management-system/phase-01-database-schema.md)

---

**Plan Status**: Ready for implementation
**Last Updated**: 2025-11-24

