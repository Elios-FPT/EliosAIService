# Prompt Management System - Implementation Plan

**Created**: 2025-11-20
**Plan ID**: 251120-0226
**Status**: ✅ Planning Complete
**Complexity**: High (4 weeks)
**Architecture**: Clean Architecture (Ports & Adapters)

---

## Executive Summary

Implement **pure DB-based prompt version control system** (Option 1 from brainstorming) - NO Git integration. System tracks immutable prompt versions, A/B testing with traffic splitting, metadata audit trails, and execution analytics. Uses PostgreSQL with materialized views for aggregation.

**Key Features**:
- ✅ Immutable version history (append-only)
- ✅ A/B testing with traffic_percentage
- ✅ Metadata audit logging (all changes tracked)
- ✅ Execution analytics (tokens, latency, cost)
- ✅ JSON diff calculation (DeepDiff)
- ✅ Weighted random selection for A/B tests

**Tech Stack**: Python 3.11+, PostgreSQL, SQLAlchemy 2.0 async, Alembic, DeepDiff

---

## Implementation Phases

| Phase | Description | Duration | Status | Progress |
|-------|-------------|----------|--------|----------|
| **[Phase 1](./phase-01-database-schema.md)** | Database Schema & Migrations | 3-4 days | ✅ Complete | 100% |
| **[Phase 2](./phase-02-domain-models.md)** | Domain Models | 2 days | ✅ Complete | 100% |
| **[Phase 3](./phase-03-repository-layer.md)** | Repository Port & Adapter | 4-5 days | ✅ Complete | 100% |
| **[Phase 4](./phase-04-helper-utilities.md)** | Helper Utilities | 1-2 days | ✅ Complete | 100% |
| **[Phase 5](./phase-05-background-jobs.md)** | Background Jobs | 1-2 days | ✅ Complete | 100% |
| **[Phase 6](./phase-06-llm-integration.md)** | LLM Integration (Optional) | 2-3 days | ⏳ Pending | 0% |

**Total Estimate**: ~4 weeks (160 hours for 1 developer)

---

## Architecture Overview

### Database Schema (3 tables + 1 view)

```
prompt_templates (14 columns)
├── Versioning: version, parent_version_id, change_summary
├── Lifecycle: is_active, is_draft
├── A/B Testing: ab_test_group, traffic_percentage
└── Metadata: created_at, created_by, notes

prompt_metadata_changes (8 columns)
└── Audit: field_name, old_value, new_value, changed_by, reason

prompt_executions (13 columns)
└── Analytics: tokens_used, latency_ms, success, model_name

prompt_analytics_summary (materialized view)
└── Aggregates: total_executions, avg_tokens, avg_latency, success_rate, cost_usd
```

### Repository Port (14 methods)

**Version Management**:
- `create_initial_prompt` - Create v1
- `create_new_version` - Fork from parent
- `rollback_to_version` - Create new version with old content

**Activation & A/B Testing**:
- `activate_version` - Activate version (deactivate others)
- `adjust_ab_traffic` - Adjust traffic split

**Retrieval**:
- `get_active_prompt` - Get with A/B logic
- `get_by_id` - Get any version
- `get_version` - Get specific version
- `get_version_history` - With JSON diffs
- `get_audit_trail` - All metadata changes

**Analytics**:
- `log_execution` - Track LLM call
- `get_analytics_summary` - Aggregated metrics

---

## Deliverables

**New Files** (28 total):
- 4 Alembic migrations
- 3 Domain models
- 2 Domain services (diff calculator, A/B selector)
- 1 Repository port
- 1 Repository adapter (PostgreSQL)
- 1 Background job
- 16 Test files

**Modified Files** (5):
- `src/adapters/persistence/models.py` - Add DB models
- `src/adapters/persistence/mappers.py` - Add mappers
- `src/adapters/llm/*.py` - Integrate prompt loading (3 adapters)
- `src/infrastructure/dependency_injection/container.py` - Add repository DI
- `pyproject.toml` - Add deepdiff dependency

---

## Success Criteria

**Functional**:
- ✅ All CRUD operations work (create, activate, rollback)
- ✅ Version history shows complete lineage + diffs
- ✅ Audit trail captures all metadata changes
- ✅ A/B testing traffic splitting works (50/50 → ~50% each variant)
- ✅ Analytics aggregation performs well (<100ms queries)
- ✅ No data corruption (transactions + constraints enforced)

**Performance**:
- Materialized view refresh: <5 seconds (for 10k executions)
- `get_active_prompt()`: <10ms (indexed queries)
- `log_execution()`: <5ms (single INSERT)
- `get_version_history()`: <50ms (with DeepDiff calculation)

**Scalability**:
- Support 1M+ executions per day
- Support 100+ prompt versions per name
- Support 10+ concurrent A/B tests

---

## Timeline

| Week | Phases | Deliverables |
|------|--------|--------------|
| **Week 1** | Phase 1-2 | DB schema + Domain models |
| **Week 2** | Phase 3 | Repository implementation |
| **Week 3** | Phase 4-5 | Utilities + Background jobs + Testing |
| **Week 4** | Phase 6 | LLM integration + Deployment |

**Total**: 4 weeks (160 hours)

---

## Key Design Decisions

1. **Immutability**: `prompt_templates` rows are append-only (never UPDATE)
2. **Transactions**: `activate_version` uses atomic transaction to deactivate others
3. **A/B Testing**: Weighted random selection based on `traffic_percentage`
4. **Diff Calculation**: DeepDiff library for JSON comparison
5. **Analytics**: Materialized view refreshed every 5 minutes

---

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Database migration conflicts | Low | Medium | Review existing migrations, test on copy |
| A/B test distribution skew | Medium | Low | Add statistical validation tests |
| Materialized view refresh latency | Low | Medium | Monitor refresh time, add alerts |
| LLM adapter integration complexity | Medium | High | Make Phase 6 optional, backward compatible |
| DeepDiff performance on large JSONs | Low | Medium | Add max JSON size validation |

---

## Next Steps

1. ✅ Review plan with team
2. ⏳ Start Phase 1 (Database schema)
3. ⏳ Set up project tracking (GitHub issues)
4. ⏳ Create feature branch: `feature/prompt-management-system`

---

## References

- [Brainstorming Session](../../brainstorming-sessions/251120-prompt-management.md)
- [DeepDiff Documentation](https://zepworks.com/deepdiff/current/)
- [PostgreSQL Materialized Views](https://www.postgresql.org/docs/current/sql-creatematerializedview.html)
- [A/B Testing Statistics](https://en.wikipedia.org/wiki/A/B_testing#Statistical_significance)

---

**Plan Status**: Ready for implementation
**Last Updated**: 2025-11-20
