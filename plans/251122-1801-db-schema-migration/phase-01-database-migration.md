# Phase 1: Database Migration

## Context Links

- **Parent Plan**: [plan.md](./plan.md)
- **Previous Phase**: [phase-00-pre-migration.md](./phase-00-pre-migration.md)
- **Dependencies**: Phase 0 complete (backup verified, no active interviews)
- **Documentation**:
  - [Migration SQL](../../alembic/versions/0015_251122_redesign_schema.py)
  - [Migration Guide](../../MIGRATION_GUIDE_REDESIGN.md)
  - [System Architecture](../../docs/system-architecture.md)

---

## Overview

**Date**: 2025-11-22
**Priority**: 🔴 Critical
**Estimated Duration**: 45-60 minutes
**Implementation Status**: ⏳ Pending
**Review Status**: ⏳ Pending

**Description**: Execute Alembic migration to create new tables (cv_skills, interview_questions), ENUMs, decompose prompt_templates, and migrate existing data.

---

## Key Insights

- Migration creates 2 new tables, 3 ENUMs, decomposes prompt_templates into 11 editable columns
- Data migration is automated (skills JSONB → table, question_ids array → junction table)
- Generated column in prompt_templates maintains LangChain compatibility
- Integrity checks embedded in migration prevent orphaned records
- Helper views created for common queries (interview_details, cv_analysis_with_skills)

---

## Requirements

### Functional Requirements
- Execute `alembic upgrade head` successfully
- Verify new tables created (cv_skills, interview_questions)
- Confirm ENUMs created (question_type_enum, difficulty_enum, proficiency_level_enum)
- Validate data migration completed (skills, question_ids, prompt decomposition)
- Check integrity constraints pass

### Non-Functional Requirements
- Migration completes within 60 minutes
- Zero data loss (row counts match pre-migration)
- No active interviews during migration (verified in Phase 0)
- Database remains consistent if migration fails (rollback-safe)

---

## Architecture

**Migration Flow**:
```
Alembic CLI
    ↓
0015_251122_redesign_schema.py
    ↓
Step 1: Create ENUMs (3)
    ↓
Step 2: Create Tables (cv_skills, interview_questions)
    ↓
Step 3: Migrate Data (JSONB → table, arrays → junction)
    ↓
Step 4: Modify Existing Tables (drop columns, convert to ENUMs)
    ↓
Step 5: Create Helper Views (2)
    ↓
Step 6: Integrity Validation
    ↓
Migration Complete ✅
```

**Database Changes**:
- **New Tables**: cv_skills (5 columns + indexes), interview_questions (7 columns + indexes)
- **New ENUMs**: question_type_enum, difficulty_enum, proficiency_level_enum
- **Modified Tables**: cv_analyses, questions, interviews, answers, prompt_templates
- **Views**: interview_details, cv_analysis_with_skills

---

## Related Code Files

### Files to Review (No code changes)
- `alembic/versions/0015_251122_redesign_schema.py` - Migration SQL
- `alembic/env.py` - Alembic configuration
- `.env` - Database connection string

### Scripts to Run
```bash
# Windows PowerShell
alembic upgrade head

# Validation queries
psql -d elios_interview -f plans/251122-1801-db-schema-migration/scripts/validate-migration.sql
```

---

## Implementation Steps

### Step 1: Verify Prerequisites (5 mins)

**Check Phase 0 Completion**:
```bash
# Verify backup exists
ls -la backups/backup_before_redesign_*.dump

# Confirm no active interviews
psql -d elios_interview -c "
SELECT COUNT(*) AS active_interviews
FROM interviews
WHERE status IN ('QUESTIONING', 'EVALUATING', 'FOLLOW_UP');"
# MUST return 0

# Check current Alembic revision
alembic current
# Expected: 0014 or earlier
```

### Step 2: Execute Migration (10-15 mins)

```bash
# Run migration with verbose output
alembic upgrade head -v

# Expected output:
# INFO  [alembic.runtime.migration] Running upgrade 0014 -> 0015, Redesign database schema - remove redundancy, normalize structures
# NOTICE:  cv_skills integrity check passed
# NOTICE:  interview_questions integrity check passed
```

**Monitor Progress**:
```bash
# In separate terminal, watch table creation
watch -n 2 "psql -d elios_interview -c '\dt+' | grep -E 'cv_skills|interview_questions'"
```

### Step 3: Validate New Tables (10 mins)

**Check cv_skills Table**:
```sql
-- Verify table exists
\d+ cv_skills

-- Expected structure:
--   id                   | uuid
--   cv_analysis_id       | uuid (FK to cv_analyses.id)
--   skill_name           | varchar(100)
--   proficiency_level    | proficiency_level_enum
--   years_of_experience  | float
--   is_primary           | boolean
--   created_at           | timestamp

-- Check row count (should match total skills in old JSONB)
SELECT COUNT(*) FROM cv_skills;

-- Verify indexes
\di+ idx_cv_skills_*

-- Sample data
SELECT * FROM cv_skills LIMIT 5;
```

**Check interview_questions Table**:
```sql
-- Verify table exists
\d+ interview_questions

-- Expected structure:
--   id              | uuid
--   interview_id    | uuid (FK to interviews.id)
--   question_id     | uuid (FK to questions.id)
--   sequence_order  | integer
--   asked_at        | timestamp
--   skipped         | boolean
--   skip_reason     | text
--   created_at      | timestamp

-- Check row count (should match sum of array_length(question_ids))
SELECT COUNT(*) FROM interview_questions;

-- Verify unique constraints
\d interview_questions
-- Look for: uq_interview_questions_sequence, uq_interview_questions_pair

-- Sample data
SELECT * FROM interview_questions ORDER BY interview_id, sequence_order LIMIT 10;
```

### Step 4: Validate ENUMs (5 mins)

```sql
-- Check ENUMs created
SELECT typname, typcategory
FROM pg_type
WHERE typname IN ('question_type_enum', 'difficulty_enum', 'proficiency_level_enum');

-- Check ENUM values
SELECT enumlabel
FROM pg_enum
JOIN pg_type ON pg_enum.enumtypid = pg_type.oid
WHERE pg_type.typname = 'question_type_enum'
ORDER BY enumsortorder;
-- Expected: technical, behavioral, situational, problem_solving, system_design

SELECT enumlabel
FROM pg_enum
JOIN pg_type ON pg_enum.enumtypid = pg_type.oid
WHERE pg_type.typname = 'difficulty_enum'
ORDER BY enumsortorder;
-- Expected: easy, medium, hard, expert

SELECT enumlabel
FROM pg_enum
JOIN pg_type ON pg_enum.enumtypid = pg_type.oid
WHERE pg_type.typname = 'proficiency_level_enum'
ORDER BY enumsortorder;
-- Expected: beginner, intermediate, advanced, expert
```

### Step 5: Validate Data Migration (15 mins)

**cv_analyses Skills Migration**:
```sql
-- Check old skills JSONB column dropped
\d cv_analyses
-- Should NOT see: skills, cv_file_path, metadata

-- Verify skills migrated correctly
SELECT
    cv.id,
    cv.candidate_id,
    COUNT(s.id) AS skill_count
FROM cv_analyses cv
LEFT JOIN cv_skills s ON s.cv_analysis_id = cv.id
GROUP BY cv.id
ORDER BY skill_count DESC
LIMIT 10;

-- Compare with backup (if you have access to old data)
-- Old: SELECT jsonb_array_length(skills) FROM cv_analyses WHERE id = '<some-id>';
-- New: SELECT COUNT(*) FROM cv_skills WHERE cv_analysis_id = '<same-id>';
```

**interviews Question Migration**:
```sql
-- Check old question_ids/answer_ids arrays dropped
\d interviews
-- Should NOT see: question_ids, answer_ids

-- Verify questions migrated correctly
SELECT
    i.id,
    i.status,
    COUNT(iq.id) AS question_count,
    MAX(iq.sequence_order) AS max_sequence
FROM interviews i
LEFT JOIN interview_questions iq ON iq.interview_id = i.id
GROUP BY i.id
ORDER BY question_count DESC
LIMIT 10;

-- Check sequence_order integrity (no gaps)
SELECT interview_id, sequence_order
FROM interview_questions
WHERE interview_id = (SELECT id FROM interviews LIMIT 1)
ORDER BY sequence_order;
-- Should be: 0, 1, 2, 3, ... (no gaps)
```

**questions ENUM Migration**:
```sql
-- Check old columns dropped
\d questions
-- Should NOT see: tags, evaluation_criteria

-- Verify ENUMs converted correctly
SELECT question_type, difficulty, COUNT(*)
FROM questions
GROUP BY question_type, difficulty
ORDER BY question_type, difficulty;

-- Check no data loss
SELECT COUNT(*) FROM questions;
-- Compare with Phase 0 row count
```

**prompt_templates Decomposition**:
```sql
-- Check new columns exist
\d+ prompt_templates
-- Should see: system_prompt, user_template, temperature, max_tokens, etc.
-- Should see: template_json (GENERATED STORED)
-- Should see: template_json_legacy (old JSONB backup)

-- Verify decomposition worked
SELECT
    prompt_name,
    version,
    LENGTH(system_prompt) AS sys_len,
    LENGTH(user_template) AS usr_len,
    temperature,
    max_tokens,
    deleted_at
FROM prompt_templates
LIMIT 5;

-- Check generated template_json column
SELECT prompt_name, template_json->'model_params'->>'temperature' AS temp
FROM prompt_templates
LIMIT 3;
-- Should match temperature column
```

### Step 6: Validate Helper Views (5 mins)

**interview_details View**:
```sql
-- Check view exists
\dv+ interview_details

-- Query view
SELECT * FROM interview_details LIMIT 5;

-- Verify aggregations
SELECT
    interview_id,
    total_questions,
    questions_asked,
    answers_submitted
FROM interview_details
WHERE total_questions > 0;
```

**cv_analysis_with_skills View**:
```sql
-- Check view exists
\dv+ cv_analysis_with_skills

-- Query view
SELECT
    cv_analysis_id,
    jsonb_array_length(skills) AS skill_count
FROM cv_analysis_with_skills
LIMIT 5;

-- Verify skills JSONB structure
SELECT skills FROM cv_analysis_with_skills LIMIT 1;
-- Should be array of objects with: id, skill_name, proficiency_level, etc.
```

### Step 7: Row Count Validation (5 mins)

```sql
-- Compare with Phase 0 counts
SELECT 'candidates' AS table_name, COUNT(*) AS row_count FROM candidates
UNION ALL SELECT 'cv_analyses', COUNT(*) FROM cv_analyses
UNION ALL SELECT 'questions', COUNT(*) FROM questions
UNION ALL SELECT 'interviews', COUNT(*) FROM interviews
UNION ALL SELECT 'answers', COUNT(*) FROM answers
UNION ALL SELECT 'evaluations', COUNT(*) FROM evaluations
UNION ALL SELECT 'prompt_templates', COUNT(*) FROM prompt_templates
UNION ALL SELECT 'cv_skills', COUNT(*) FROM cv_skills -- NEW
UNION ALL SELECT 'interview_questions', COUNT(*) FROM interview_questions; -- NEW

-- Save results and compare with Phase 0 backup
-- NO tables should have fewer rows (except prompt_templates if soft-deleted)
```

---

## Todo List

- [ ] Verify Phase 0 complete (backup exists, no active interviews)
- [ ] Check Alembic current revision (0014)
- [ ] Execute `alembic upgrade head`
- [ ] Monitor migration progress
- [ ] Validate cv_skills table created with indexes
- [ ] Validate interview_questions table created with constraints
- [ ] Verify 3 ENUMs created with correct values
- [ ] Check cv_analyses skills migrated (JSONB → table)
- [ ] Check interviews questions migrated (array → junction)
- [ ] Check questions ENUMs converted
- [ ] Check prompt_templates decomposed (11 columns + generated)
- [ ] Validate helper views created (interview_details, cv_analysis_with_skills)
- [ ] Run row count comparison (no data loss)
- [ ] Verify integrity checks passed (no orphaned records)
- [ ] Document migration completion time
- [ ] Save migration logs for Phase 8 documentation

---

## Success Criteria

### Must-Have
- ✅ Migration completes without errors (`alembic upgrade head` exits 0)
- ✅ cv_skills table created with 4 indexes
- ✅ interview_questions table created with 2 unique constraints + 3 indexes
- ✅ 3 ENUMs created (question_type, difficulty, proficiency_level)
- ✅ Data migrated (cv_skills rows > 0, interview_questions rows > 0)
- ✅ Old columns dropped (cv_analyses.skills, interviews.question_ids, etc.)
- ✅ prompt_templates decomposed (11 new columns + generated template_json)
- ✅ Helper views created and queryable
- ✅ Integrity checks passed (NOTICE messages in migration output)
- ✅ Row counts match Phase 0 (except new tables)

### Nice-to-Have
- ✅ Migration completes in < 45 minutes
- ✅ No warnings in Alembic output
- ✅ Generated template_json column works correctly
- ✅ Indexes created with optimal size

---

## Risk Assessment

### Risk 1: Migration Timeout
**Likelihood**: Low
**Impact**: High
**Mitigation**:
- Monitor migration progress in real-time
- Large databases may take longer (adjust timeout if needed)
- Run during low-traffic period
- If timeout, rollback and investigate (check table sizes, index creation time)

### Risk 2: Data Migration Errors
**Likelihood**: Low
**Impact**: Critical
**Mitigation**:
- Migration tested on dev/staging first
- Integrity checks embedded in migration SQL
- Backup verified in Phase 0
- Rollback available via `alembic downgrade -1`

### Risk 3: ENUM Conversion Failures
**Likelihood**: Low
**Impact**: Medium
**Mitigation**:
- Migration uses CASE statements with fallback defaults
- Invalid values converted to safe defaults (e.g., 'technical', 'medium')
- Test data validated in Phase 0

### Risk 4: Generated Column Not Supported
**Likelihood**: Very Low (PostgreSQL 12+)
**Impact**: High
**Mitigation**:
- Requires PostgreSQL 12+ (verified in Phase 0)
- Generated STORED columns supported in PG 12+
- Fallback: Create trigger-based update if needed

### Risk 5: View Creation Conflicts
**Likelihood**: Very Low
**Impact**: Low
**Mitigation**:
- Migration uses `CREATE OR REPLACE VIEW`
- Views dropped in downgrade script
- No dependencies on views (they're helpers only)

---

## Security Considerations

### Database Connection Security
- **Risk**: Migration runs with elevated privileges
- **Mitigation**:
  - Use service account with DDL permissions
  - Log all migration actions
  - Revoke DDL permissions after migration

### Data Exposure
- **Risk**: Migration logs may contain sensitive data
- **Mitigation**:
  - Review Alembic logs before sharing
  - Redact sensitive info (CV text, candidate names)
  - Store logs securely

### Integrity Checks
- **Risk**: Orphaned records after migration
- **Mitigation**:
  - Embedded integrity checks in migration
  - Foreign keys with CASCADE delete
  - Post-migration validation queries

---

## Next Steps

**On Success**:
- ✅ Proceed to [Phase 2: Domain Layer](./phase-02-domain-layer.md)
- Document migration completion time
- Save row counts for later phases
- Keep backup for 30 days

**On Failure**:
- ❌ Review Alembic error logs
- ❌ Rollback: `alembic downgrade -1`
- ❌ Restore from backup if rollback fails
- ❌ Investigate root cause before retrying
- ❌ Test fix on dev/staging first

**Rollback Command**:
```bash
# Quick rollback
alembic downgrade -1

# Verify downgrade
alembic current

# Full restore (if rollback fails)
psql -d elios_interview -c "DROP DATABASE elios_interview;"
createdb elios_interview
pg_restore -d elios_interview backups/backup_before_redesign_*.dump
```

---

**Phase Status**: ⏳ Ready to Start
**Blocker**: Phase 0 must be complete
**Estimated Time**: 45-60 minutes
**Rollback Risk**: Low (automated downgrade script available)
