# Database Schema Migration Implementation Plan

**Plan ID**: `251122-1801-db-schema-migration`
**Created**: 2025-11-22
**Status**: 🟡 Ready for Implementation
**Estimated Effort**: 12-18 hours over 2-3 days
**Risk Level**: Medium (with proper testing & backups)

---

## Executive Summary

Migrate database schema to redesigned structure:
- Normalize `cv_skills` (JSONB → table)
- Add junction `interview_questions` (arrays → relationships)
- ENUMs for type safety
- Decompose `prompt_templates` for UI editing
- Remove redundant/deprecated fields

**Migration file**: `alembic/versions/0015_251122_redesign_schema.py` ✅ Created

---

## Implementation Phases

| Phase | Duration | Status | Priority | File |
|-------|----------|--------|----------|------|
| [Phase 0: Pre-Migration](./phase-00-pre-migration.md) | 30 mins | ⏳ Pending | 🔴 Critical | Backup, validation |
| [Phase 1: Database Migration](./phase-01-database-migration.md) | 45-60 mins | ⏳ Pending | 🔴 Critical | Run Alembic, validate |
| [Phase 2: Domain Layer](./phase-02-domain-layer.md) | 2-3 hours | ⏳ Pending | 🔴 Critical | Update 7 models |
| [Phase 3: Adapters Layer](./phase-03-adapters-layer.md) | 3-4 hours | ⏳ Pending | 🔴 Critical | Repositories, mappers |
| [Phase 4: Application Layer](./phase-04-application-layer.md) | 1-2 hours | ⏳ Pending | 🟡 High | Use cases, DTOs |
| [Phase 5: Infrastructure](./phase-05-infrastructure.md) | 30 mins | ⏳ Pending | 🟢 Medium | DI container |
| [Phase 6: API Layer](./phase-06-api-layer.md) | 1-2 hours | ⏳ Pending | 🟡 High | REST/WebSocket |
| [Phase 7: Testing](./phase-07-testing.md) | 2-3 hours | ⏳ Pending | 🔴 Critical | All layers |
| [Phase 8: Documentation](./phase-08-documentation.md) | 1 hour | ⏳ Pending | 🟡 High | 5 doc files |
| [Phase 9: Production Deploy](./phase-09-production-deploy.md) | 1-2 hours | ⏳ Pending | 🔴 Critical | Zero downtime |

---

## Key Schema Changes

**New Tables**: `cv_skills`, `interview_questions`
**New ENUMs**: `question_type_enum`, `difficulty_enum`, `proficiency_level_enum`
**Decomposed**: `prompt_templates.template_json` → 11 editable columns
**Removed**: Redundant fields (cv_file_path, candidate_id, arrays, deprecated JSONB)

---

## Prerequisites

- ✅ Migration file reviewed: `alembic/versions/0015_251122_redesign_schema.py`
- ⏳ Database backup strategy confirmed
- ⏳ No active interviews (verify before migration)
- ⏳ PostgreSQL 14+ with UUID support

---

## Dependencies

```
Phase 0 (Pre-Migration)
  ↓
Phase 1 (Database Migration)
  ↓
Phase 2 (Domain Layer) ──────┐
  ↓                          │
Phase 3 (Adapters Layer)     │
  ↓                          │
Phase 4 (Application Layer) ─┤
  ↓                          │
Phase 5 (Infrastructure)     │ → Phase 7 (Testing)
  ↓                          │         ↓
Phase 6 (API Layer) ─────────┘   Phase 8 (Docs)
                                       ↓
                                 Phase 9 (Production)
```

---

## Success Criteria

- ✅ All tests passing (>85% coverage maintained)
- ✅ Zero data loss (row counts verified)
- ✅ Performance maintained (<10% degradation)
- ✅ API compatibility (or documented changes)

---

## Rollback Strategy

**Quick**: `alembic downgrade -1` + restart with old code
**Full**: Restore from backup + deploy previous version

**Triggers**: Data loss, >10% perf degradation, >5% error rate, critical failures

---

## References

- [Migration Guide](../../MIGRATION_GUIDE_REDESIGN.md)
- [Design Summary](../../DB_REDESIGN_SUMMARY.md)
- [Migration SQL](../../alembic/versions/0015_251122_redesign_schema.py)
- [System Architecture](../../docs/system-architecture.md)
