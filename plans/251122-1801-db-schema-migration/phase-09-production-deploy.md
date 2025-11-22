# Phase 9: Production Deployment

## Context Links

- **Parent Plan**: [plan.md](./plan.md)
- **Previous Phase**: [phase-08-documentation.md](./phase-08-documentation.md)
- **Dependencies**: All phases 0-8 complete, staging validated

---

## Overview

**Date**: 2025-11-22
**Priority**: 🔴 Critical
**Estimated Duration**: 1-2 hours
**Implementation Status**: ⏳ Pending
**Review Status**: ⏳ Pending

**Description**: Deploy to production with zero downtime strategy. Full backup, migration, validation, monitoring.

---

## Key Insights

- **Downtime**: 30-45 minutes maintenance window required
- **Critical**: MUST verify no active interviews before migration
- **Backup**: Full database backup mandatory (keep 30 days)
- **Rollback**: Ready if issues occur (alembic downgrade OR restore backup)
- **Monitoring**: 24-hour post-deployment observation

---

## Requirements

### Functional Requirements
- Complete database migration on production
- Deploy updated code
- Zero data loss
- Application functional post-deployment

### Non-Functional Requirements
- Downtime <45 minutes
- Automatic rollback on critical errors
- Post-deployment monitoring active
- Team notified of maintenance window

---

## Architecture

**Deployment Strategy**: Blue-Green with Maintenance Window

```
Pre-Deployment
    ↓
Maintenance Window Start (Stop app)
    ↓
Verify No Active Interviews
    ↓
Run Migration (15-20 mins)
    ↓
Validate Data Integrity
    ↓
Deploy New Code
    ↓
Start Application
    ↓
Smoke Tests
    ↓
Maintenance Window End
    ↓
Monitoring (24 hours)
```

---

## Implementation Steps

### Step 1: Pre-Deployment Checklist (T-24 hours)

```bash
# Verify all prerequisites
- [ ] All tests passing (dev, staging)
- [ ] Code review approved
- [ ] Migration tested on staging (with production-size data)
- [ ] Backup strategy confirmed
- [ ] Rollback plan documented and tested
- [ ] Team notified of maintenance window
- [ ] Monitoring dashboards prepared
- [ ] On-call engineer identified
```

### Step 2: Pre-Migration Backup (T-5 mins)

```bash
# Create production backup
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupFile = "backup_prod_before_redesign_$timestamp.dump"

pg_dump -h prod-db-host -U postgres -d elios_interview `
  -F c -b -v -f $backupFile

# Verify backup
if (Test-Path $backupFile) {
    Write-Host "✅ Backup created: $backupFile"
    $size = (Get-Item $backupFile).Length / 1MB
    Write-Host "   Size: $([math]::Round($size, 2)) MB"

    # Store in multiple locations
    Copy-Item $backupFile "\\backup-server\backups\"
    # Upload to cloud storage (S3, Azure Blob, etc.)
} else {
    Write-Host "❌ ABORT: Backup FAILED!"
    exit 1
}
```

### Step 3: Stop Application (T+0 mins)

```bash
# Stop application (prevent new interviews from starting)
# Method depends on deployment:

# Option A: Systemd
sudo systemctl stop elios-api

# Option B: Docker Compose
docker-compose down

# Option C: Kubernetes
kubectl scale deployment elios-api --replicas=0

# Verify app stopped
curl https://prod-api/health
# Should return: Connection refused or 503
```

### Step 4: Verify No Active Interviews (T+2 mins - CRITICAL)

```sql
-- MUST return 0 before proceeding
SELECT COUNT(*) AS active_interviews
FROM interviews
WHERE status IN ('QUESTIONING', 'EVALUATING', 'FOLLOW_UP');

-- If > 0:
-- 1. Wait for interviews to complete (max 10 mins)
-- 2. OR contact users to pause interviews
-- 3. DO NOT PROCEED if active_interviews > 0
```

### Step 5: Run Migration (T+5 mins, Duration: 15-20 mins)

```bash
# Set production DATABASE_URL
export DATABASE_URL="postgresql://user:pass@prod-db-host/elios_interview"

# Run migration
alembic upgrade head

# Expected output:
# INFO  [alembic.runtime.migration] Running upgrade 0014 -> 0015
# NOTICE:  cv_skills integrity check passed
# NOTICE:  interview_questions integrity check passed

# Verify current revision
alembic current
# Should show: 0015 (head)
```

### Step 6: Validate Data Integrity (T+20 mins, Duration: 5 mins)

```sql
-- Quick validation queries

-- 1. Check new tables exist
SELECT COUNT(*) FROM cv_skills;
SELECT COUNT(*) FROM interview_questions;

-- 2. Verify row counts match baseline (from Phase 0)
SELECT 'candidates' AS table, COUNT(*) FROM candidates
UNION ALL SELECT 'cv_analyses', COUNT(*) FROM cv_analyses
UNION ALL SELECT 'interviews', COUNT(*) FROM interviews;
-- Compare with Phase 0 baseline - MUST MATCH

-- 3. Check for orphaned records (should be 0)
SELECT COUNT(*) FROM cv_skills s
LEFT JOIN cv_analyses cv ON cv.id = s.cv_analysis_id
WHERE cv.id IS NULL;
-- Expected: 0

-- 4. Verify prompt_templates decomposed
SELECT COUNT(*) FROM prompt_templates
WHERE system_prompt IS NOT NULL AND user_template IS NOT NULL;
-- Expected: All rows

-- If ANY validation fails: ROLLBACK immediately
```

### Step 7: Deploy New Code (T+25 mins, Duration: 5 mins)

```bash
# Deploy updated codebase
# Method depends on deployment:

# Option A: Git pull + systemd restart
cd /opt/elios-api
git pull origin main
pip install -r requirements.txt --upgrade

# Option B: Docker image deploy
docker pull elios-api:latest

# Option C: Kubernetes rolling update
kubectl set image deployment/elios-api elios-api=elios-api:latest

# DO NOT start application yet
```

### Step 8: Start Application (T+30 mins)

```bash
# Start application
sudo systemctl start elios-api
# OR
docker-compose up -d
# OR
kubectl scale deployment elios-api --replicas=3

# Wait for startup (30 seconds)
sleep 30
```

### Step 9: Smoke Tests (T+32 mins, Duration: 5 mins)

```bash
# Health check
curl https://prod-api/health
# Expected: {"status": "healthy"}

# Test interview creation
curl -X POST https://prod-api/api/interviews \
  -H "Content-Type: application/json" \
  -d '{"candidate_id": "test-candidate-id"}'
# Expected: 201 Created

# Test interview retrieval
curl https://prod-api/api/interviews/{interview_id}
# Expected: JSON with total_questions, questions_asked (no question_ids)

# Test CV analysis (if applicable)
# ... additional smoke tests
```

### Step 10: Post-Deployment Monitoring (T+37 mins → 24 hours)

```bash
# Monitor application logs
tail -f /var/log/elios-api/app.log
# Watch for errors, warnings

# Monitor database performance
SELECT schemaname, tablename, idx_scan, idx_tup_read
FROM pg_stat_user_indexes
WHERE tablename IN ('cv_skills', 'interview_questions')
ORDER BY idx_scan DESC;

# Monitor API response times
# Use monitoring tools (Grafana, Datadog, etc.)

# Check error rates
# Alert if error rate >1%
```

---

## Rollback Plan

### Trigger Conditions
Rollback if:
- Data integrity validation fails (orphaned records)
- >10% performance degradation
- Critical errors in production (>5% error rate)
- Data loss detected
- Application fails to start

### Quick Rollback (Migration only)

```bash
# Stop application
sudo systemctl stop elios-api

# Rollback migration
alembic downgrade -1

# Verify rollback
alembic current
# Should show: 0014

# Deploy old code
git checkout previous-release-tag

# Restart application
sudo systemctl start elios-api
```

### Full Rollback (Restore from Backup)

```bash
# Stop application
sudo systemctl stop elios-api

# Drop and recreate database (CAREFUL!)
dropdb elios_interview
createdb elios_interview

# Restore from backup
pg_restore -h prod-db-host -U postgres -d elios_interview \
  --clean --if-exists backup_prod_*.dump

# Deploy old code
git checkout previous-release-tag

# Restart application
sudo systemctl start elios-api

# Verify
curl https://prod-api/health
```

---

## Todo List

### Pre-Deployment (T-24 hours)
- [ ] All tests passing (dev, staging)
- [ ] Code review approved
- [ ] Migration tested on staging
- [ ] Backup strategy confirmed
- [ ] Rollback plan tested
- [ ] Team notified (email, Slack)
- [ ] Monitoring dashboards ready

### Maintenance Window (T+0 to T+45 mins)
- [ ] Create production backup
- [ ] Verify backup integrity
- [ ] Stop application
- [ ] Verify no active interviews (CRITICAL)
- [ ] Run migration
- [ ] Validate data integrity
- [ ] Deploy new code
- [ ] Start application
- [ ] Run smoke tests
- [ ] Verify monitoring active

### Post-Deployment (T+45 mins → 24 hours)
- [ ] Monitor logs for errors
- [ ] Monitor database performance
- [ ] Monitor API response times
- [ ] Check error rates hourly
- [ ] Collect user feedback
- [ ] Document any issues
- [ ] Update team on status

---

## Success Criteria

### Critical
- ✅ Migration completes without errors
- ✅ Zero data loss (row counts match)
- ✅ Application starts successfully
- ✅ Smoke tests pass
- ✅ No critical errors in logs

### Important
- ✅ Downtime <45 minutes
- ✅ Performance maintained (<10% degradation)
- ✅ Error rate <1%
- ✅ User experience unchanged

### Nice-to-Have
- ✅ Monitoring shows normal behavior (24 hours)
- ✅ No customer complaints
- ✅ Team confident in deployment

---

## Risk Assessment

### Risk 1: Active Interviews During Migration
**Likelihood**: Low (if properly checked)
**Impact**: Critical (interviews broken)
**Mitigation**: MUST verify no active interviews before migration; schedule during low-usage hours

### Risk 2: Data Loss
**Likelihood**: Very Low (transaction-wrapped)
**Impact**: Critical
**Mitigation**: Full backup before migration; integrity validation post-migration

### Risk 3: Application Fails to Start
**Likelihood**: Low (tested on staging)
**Impact**: High
**Mitigation**: Smoke tests immediately after startup; rollback ready

### Risk 4: Performance Degradation
**Likelihood**: Low (proper indexing)
**Impact**: Medium
**Mitigation**: Monitor query times; optimize slow queries; rollback if >10% degradation

---

## Security Considerations

- Use dedicated migration user with DDL privileges
- Revoke DDL permissions after migration
- Do not expose backup files (contain sensitive data)
- Rotate database credentials post-deployment (optional)
- Review logs before sharing (remove PII)

---

## Communication Plan

### T-24 hours
**To**: All stakeholders, users
**Message**: "Scheduled maintenance window on [date] [time]. Platform unavailable for 45 minutes. Emails sent."

### T-1 hour
**To**: Engineering team
**Message**: "Migration starting in 1 hour. On-call engineer: [name]. Monitoring active."

### T+0 (Start)
**To**: Status page
**Message**: "Maintenance in progress. Expected completion: [time]."

### T+45 mins (Complete)
**To**: Status page, stakeholders
**Message**: "Maintenance complete. Platform operational. Monitoring for 24 hours."

### T+24 hours
**To**: Engineering team
**Message**: "Post-deployment monitoring complete. No issues detected. Migration successful."

---

## Next Steps

**On Success**:
- ✅ Monitor for 24 hours
- ✅ Document lessons learned
- ✅ Archive migration plan
- ✅ Plan next iteration (if needed)

**On Failure**:
- ❌ Execute rollback plan
- ❌ Investigate root cause
- ❌ Fix issues
- ❌ Re-test on staging
- ❌ Reschedule deployment

---

**Phase Status**: ⏳ Ready (After Phases 0-8 Complete)
**Blocker**: Must complete all previous phases + staging validation
**Estimated Downtime**: 30-45 minutes
**Recommended Time**: 2-4 AM (low traffic)
