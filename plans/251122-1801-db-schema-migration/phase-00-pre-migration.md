# Phase 0: Pre-Migration

## Context Links

- **Parent Plan**: [plan.md](./plan.md)
- **Dependencies**: None (first phase)
- **Documentation**:
  - [Migration Guide](../../MIGRATION_GUIDE_REDESIGN.md)
  - [DB Redesign Summary](../../DB_REDESIGN_SUMMARY.md)
  - [Migration SQL](../../alembic/versions/0015_251122_redesign_schema.py)

---

## Overview

**Date**: 2025-11-22
**Priority**: 🔴 Critical
**Estimated Duration**: 30 minutes
**Implementation Status**: ⏳ Pending
**Review Status**: ⏳ Pending

**Description**: Backup database, validate current state, prepare for migration.

---

## Key Insights

- **Critical**: Migration removes array columns (`question_ids`, `answer_ids`) - active interviews will break
- Database backup MUST complete successfully before proceeding
- Backup retention: Keep for minimum 30 days post-migration
- Migration file exists and has been reviewed by brainstorming session
- PostgreSQL 14+ required for generated columns feature

---

## Requirements

### Functional Requirements
- Create full database backup (schema + data)
- Verify current database state (row counts, active sessions)
- Confirm no active interviews in progress
- Validate Alembic migration file exists

### Non-Functional Requirements
- Backup must be restorable (test restore on dev)
- Backup size estimation: ~500MB - 2GB depending on data volume
- Backup time: 5-10 minutes for typical database
- Zero production impact during this phase

---

## Architecture

**Target**: Database layer only
**Tools**: `pg_dump`, `psql`, Alembic CLI
**Environment**: Development → Staging → Production sequence

**Backup Strategy**:
```
Production DB
    ↓
pg_dump (custom format)
    ↓
Compressed .dump file
    ↓
Stored in secure location
    ↓
Verified via pg_restore --list
```

---

## Related Code Files

### Files to Review (No changes)
- `alembic/versions/0015_251122_redesign_schema.py` - Migration SQL
- `alembic/env.py` - Alembic configuration
- `.env` - Database connection string

### Scripts to Run
```bash
# Backup script (Windows PowerShell)
plans/251122-1801-db-schema-migration/scripts/backup-database.ps1

# Validation script (Cross-platform)
plans/251122-1801-db-schema-migration/scripts/validate-state.sql
```

---

## Implementation Steps

### Step 1: Database Backup (10 mins)

**Windows PowerShell**:
```powershell
# Set variables
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupFile = "backup_before_redesign_$timestamp.dump"
$backupPath = "H:\AI-course\EliosAIService\backups\$backupFile"

# Create backups directory if not exists
New-Item -ItemType Directory -Force -Path "H:\AI-course\EliosAIService\backups"

# Run pg_dump
pg_dump -h localhost -U postgres -d elios_interview `
  -F c -b -v -f $backupPath

# Verify backup file exists
if (Test-Path $backupPath) {
    Write-Host "✅ Backup created: $backupPath" -ForegroundColor Green
    $size = (Get-Item $backupPath).Length / 1MB
    Write-Host "   Size: $([math]::Round($size, 2)) MB" -ForegroundColor Cyan
} else {
    Write-Host "❌ Backup FAILED!" -ForegroundColor Red
    exit 1
}

# List backup contents (verification)
pg_restore --list $backupPath | Select-Object -First 20
```

**Linux/Mac Bash**:
```bash
#!/bin/bash
timestamp=$(date +%Y%m%d_%H%M%S)
backup_file="backup_before_redesign_$timestamp.dump"
backup_path="./backups/$backup_file"

mkdir -p ./backups

pg_dump -h localhost -U postgres -d elios_interview \
  -F c -b -v -f "$backup_path"

if [ -f "$backup_path" ]; then
    echo "✅ Backup created: $backup_path"
    ls -lh "$backup_path"
else
    echo "❌ Backup FAILED!"
    exit 1
fi

# Verify backup
pg_restore --list "$backup_path" | head -20
```

### Step 2: Data Volume Check (5 mins)

```sql
-- Check row counts before migration
SELECT 'candidates' AS table_name, COUNT(*) AS row_count FROM candidates
UNION ALL SELECT 'cv_analyses', COUNT(*) FROM cv_analyses
UNION ALL SELECT 'questions', COUNT(*) FROM questions
UNION ALL SELECT 'interviews', COUNT(*) FROM interviews
UNION ALL SELECT 'answers', COUNT(*) FROM answers
UNION ALL SELECT 'evaluations', COUNT(*) FROM evaluations
UNION ALL SELECT 'prompt_templates', COUNT(*) FROM prompt_templates;

-- Save results for post-migration comparison
-- Expected: Non-zero counts for cv_analyses, questions, interviews
```

### Step 3: Active Interviews Check (CRITICAL - 5 mins)

```sql
-- MUST return 0 before proceeding
SELECT COUNT(*) AS active_interviews
FROM interviews
WHERE status IN ('QUESTIONING', 'EVALUATING', 'FOLLOW_UP');

-- If > 0, wait for interviews to complete or coordinate with users
-- DO NOT PROCEED if active_interviews > 0
```

### Step 4: Migration File Validation (5 mins)

```bash
# Check Alembic current revision
alembic current
# Expected output: 0014 (or earlier)

# View migration history
alembic history -v

# Verify 0015 migration exists
ls -la alembic/versions/0015_251122_redesign_schema.py

# Review migration file (optional but recommended)
cat alembic/versions/0015_251122_redesign_schema.py | head -100
```

### Step 5: Test Backup Restore (Optional but Recommended - 10 mins)

```bash
# Create test database
createdb elios_interview_backup_test

# Restore backup
pg_restore -h localhost -U postgres -d elios_interview_backup_test \
  --clean --if-exists backup_before_redesign_*.dump

# Verify row counts match
psql -d elios_interview_backup_test -c "
SELECT 'candidates' AS table_name, COUNT(*) AS row_count FROM candidates
UNION ALL SELECT 'interviews', COUNT(*) FROM interviews;"

# Drop test database
dropdb elios_interview_backup_test
```

---

## Todo List

- [ ] Create database backup using `pg_dump`
- [ ] Verify backup file created and size is reasonable
- [ ] Test backup restore on test database (recommended)
- [ ] Run data volume check query
- [ ] Save row counts for comparison
- [ ] Check for active interviews (MUST BE ZERO)
- [ ] Verify Alembic current revision (should be 0014)
- [ ] Review migration file `0015_251122_redesign_schema.py`
- [ ] Confirm PostgreSQL version (14+)
- [ ] Notify team of upcoming migration window

---

## Success Criteria

### Must-Have
- ✅ Database backup created successfully
- ✅ Backup file verified (can list contents with `pg_restore --list`)
- ✅ No active interviews (`active_interviews = 0`)
- ✅ Current Alembic revision confirmed (0014 or earlier)
- ✅ Migration file exists at correct path

### Nice-to-Have
- ✅ Backup restore tested on temporary database
- ✅ Backup stored in multiple locations (local + cloud)
- ✅ Team notified of migration schedule
- ✅ Row counts documented for later comparison

---

## Risk Assessment

### Risk 1: Backup Failure
**Likelihood**: Low
**Impact**: Critical (cannot proceed without backup)
**Mitigation**:
- Test `pg_dump` connection before backup
- Ensure sufficient disk space (check with `df -h`)
- Run backup during low-traffic period
- Verify backup immediately after creation

### Risk 2: Active Interviews During Migration
**Likelihood**: Medium (depends on timing)
**Impact**: Critical (interviews will break)
**Mitigation**:
- Check active interviews before every phase
- Schedule migration during low-usage hours (e.g., 2-4 AM)
- Notify users of maintenance window
- Implement interview pause feature (optional)

### Risk 3: Insufficient Disk Space
**Likelihood**: Low
**Impact**: High (backup fails)
**Mitigation**:
- Check available disk space before backup
- Estimate backup size (typically ~70% of database size)
- Clean up old backups if needed
- Use compressed format (`-F c`)

### Risk 4: Backup Corruption
**Likelihood**: Very Low
**Impact**: Critical
**Mitigation**:
- Verify backup with `pg_restore --list`
- Test restore on temporary database
- Create multiple backup copies
- Store backup in secure, backed-up location

---

## Security Considerations

### Database Credentials
- **Risk**: Backup file contains sensitive data
- **Mitigation**:
  - Store backup in secure location with restricted permissions
  - Encrypt backup file if storing remotely
  - Use environment variables for DB credentials (not hardcoded)

### Access Control
- **Risk**: Unauthorized access to backup
- **Mitigation**:
  - Set file permissions: `chmod 600 backup_*.dump` (Linux/Mac)
  - Windows: Right-click → Properties → Security → Edit permissions
  - Only DBA and authorized personnel should access backups

### Data Privacy
- **Risk**: PII data in backup (candidate CVs, answers)
- **Mitigation**:
  - Follow data retention policies
  - Delete backups after 30 days (or per policy)
  - Do not share backup files via insecure channels

---

## Next Steps

**On Success**:
- ✅ Proceed to [Phase 1: Database Migration](./phase-01-database-migration.md)
- Document backup file location
- Share backup location with team (secure channel)

**On Failure**:
- ❌ Troubleshoot backup issues (check logs, permissions, disk space)
- ❌ Do NOT proceed to Phase 1 until backup succeeds
- ❌ Escalate to DBA if backup repeatedly fails

**Rollback**:
- N/A (no database changes in this phase)

---

**Phase Status**: ⏳ Ready to Start
**Blocker**: None
**Dependencies Met**: Yes (no prerequisites)
