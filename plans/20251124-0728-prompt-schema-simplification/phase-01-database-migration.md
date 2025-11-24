# Phase 1: Database Migration

**Parent**: [Implementation Plan](./plan.md)
**Created**: 2025-11-24
**Duration**: 2-3 hours
**Priority**: Critical
**Status**: ⏳ Pending

---

## Context Links

- [Parent Plan](./plan.md)
- [Current Schema](../../251120-0226-prompt-management-system/phase-01-database-schema.md)
- [Migration 0015](../../alembic/versions/0015_251122_redesign_schema.py)

---

## Overview

Create Alembic migration to remove unused fields and simplify schema. Drop materialized view, remove columns, recreate view with updated structure.

**Goals**:
- Remove unused columns from all tables
- Update analytics view structure
- Maintain data integrity
- Zero downtime migration

---

## Key Insights

- Materialized view must be dropped before column changes
- Foreign key constraints may need temporary removal
- Indexes on removed columns will be auto-dropped
- View recreation requires updated GROUP BY clause

---

## Requirements

### Functional Requirements
- Remove `template_json_legacy` from `prompt_templates`
- Remove `ab_test_group`, `traffic_percentage`, `notes` from `prompt_templates`
- Remove `reason` from `prompt_metadata_changes`
- Remove `candidate_id`, `tokens_used` from `prompt_executions`
- Update `prompt_analytics_summary` view (remove `ab_test_group`, `avg_tokens_used`, add `avg_prompt_tokens`, `avg_completion_tokens`)
- Remove constraint `ck_prompt_templates_traffic_percentage`

### Non-Functional Requirements
- Migration must be reversible (downgrade function)
- No data loss
- Migration time < 30 seconds for production data

---

## Architecture

### Migration Strategy

```
1. Drop materialized view (indexes auto-dropped)
2. Remove columns from prompt_templates
3. Remove constraint from prompt_templates
4. Remove columns from prompt_metadata_changes
5. Remove columns from prompt_executions
6. Recreate materialized view with new structure
7. Recreate indexes on view
```

### Data Flow

```
Existing Data → Migration → Simplified Schema
- No data transformation needed (just column removal)
- View aggregates from remaining columns
```

---

## Related Code Files

**New Files**:
- `alembic/versions/0016_simplify_prompt_schema.py`

**Modified Files**:
- None (migration only)

---

## Implementation Steps

### Step 1: Create Migration Script

```bash
alembic revision -m "simplify prompt schema"
```

### Step 2: Implement upgrade()

```python
def upgrade() -> None:
    # 1. Drop materialized view
    op.execute("DROP MATERIALIZED VIEW IF EXISTS prompt_analytics_summary")

    # 2. Remove columns from prompt_templates
    op.drop_column('prompt_templates', 'template_json_legacy')
    op.drop_column('prompt_templates', 'ab_test_group')
    op.drop_column('prompt_templates', 'traffic_percentage')
    op.drop_column('prompt_templates', 'notes')

    # 3. Remove constraint
    op.drop_constraint('ck_prompt_templates_traffic_percentage', 'prompt_templates', type_='check')

    # 4. Remove columns from prompt_metadata_changes
    op.drop_column('prompt_metadata_changes', 'reason')

    # 5. Remove columns from prompt_executions
    op.drop_column('prompt_executions', 'candidate_id')
    op.drop_column('prompt_executions', 'tokens_used')

    # 6. Recreate analytics view
    op.execute("""
        CREATE MATERIALIZED VIEW prompt_analytics_summary AS
        SELECT
            pt.id AS prompt_template_id,
            pt.name,
            pt.version,
            COUNT(pe.id) AS total_executions,
            AVG(pe.prompt_tokens) AS avg_prompt_tokens,
            AVG(pe.completion_tokens) AS avg_completion_tokens,
            AVG(pe.latency_ms) AS avg_latency_ms,
            CASE
                WHEN COUNT(pe.id) > 0 THEN
                    SUM(CASE WHEN pe.success THEN 1 ELSE 0 END)::FLOAT / COUNT(pe.id)
                ELSE 0
            END AS success_rate,
            SUM(
                (COALESCE(pe.prompt_tokens, 0) * 0.03 / 1000.0) +
                (COALESCE(pe.completion_tokens, 0) * 0.06 / 1000.0)
            ) AS estimated_cost_usd,
            MAX(pe.executed_at) AS last_executed_at
        FROM prompt_templates pt
        LEFT JOIN prompt_executions pe ON pt.id = pe.prompt_template_id
        GROUP BY pt.id, pt.name, pt.version
    """)

    # 7. Recreate indexes
    op.execute("""
        CREATE UNIQUE INDEX idx_analytics_summary_template_id
        ON prompt_analytics_summary(prompt_template_id)
    """)

    op.execute("""
        CREATE INDEX idx_analytics_summary_name
        ON prompt_analytics_summary(name, version)
    """)
```

### Step 3: Implement downgrade()

```python
def downgrade() -> None:
    # Reverse all changes (add columns back with defaults)
    # ... (detailed rollback)
```

### Step 4: Test Migration

```bash
# Test upgrade
alembic upgrade head

# Verify schema
psql -c "\d prompt_templates"
psql -c "\d prompt_analytics_summary"

# Test downgrade
alembic downgrade -1

# Test upgrade again
alembic upgrade head
```

---

## Todo List

- [ ] Create migration script `0016_simplify_prompt_schema.py`
- [ ] Implement `upgrade()` function
- [ ] Implement `downgrade()` function
- [ ] Test migration on staging database
- [ ] Verify data integrity after migration
- [ ] Test rollback procedure
- [ ] Update migration documentation

---

## Success Criteria

- ✅ Migration runs without errors
- ✅ All columns removed successfully
- ✅ View recreated with correct structure
- ✅ Indexes recreated correctly
- ✅ Downgrade works (rollback possible)
- ✅ No data loss
- ✅ Query performance maintained

---

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Breaking existing queries | High | Test all queries before migration |
| Data loss | Critical | Backup database before migration |
| View recreation failure | Medium | Test view SQL separately |
| Downgrade complexity | Low | Implement full rollback logic |

---

## Security Considerations

- No security impact (schema simplification only)
- Ensure migration runs in transaction
- Verify no sensitive data in removed columns

---

## Next Steps

- Proceed to Phase 2 (Domain Models) after migration tested
- Update integration tests to reflect schema changes

