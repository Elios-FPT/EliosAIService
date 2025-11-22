# Database Schema Migration Plan

**Plan ID**: 251122-1801-db-schema-migration
**Created**: 2025-11-22
**Status**: Ready for Implementation

---

## What's This?

Complete implementation plan for migrating from current database schema to redesigned structure with:
- Normalized tables (cv_skills, interview_questions)
- ENUMs for type safety
- Decomposed prompt templates for UI editing
- Removed redundancy and deprecated fields

---

## Files in This Directory

| File | Purpose | When to Use |
|------|---------|-------------|
| **plan.md** | Overview with phase links (80 lines) | Read first, navigation hub |
| **phase-00-pre-migration.md** | Backup & validation (30 mins) | Before any changes |
| **phase-01-database-migration.md** | Run Alembic migration (45-60 mins) | After backup complete |
| **phase-02-domain-layer.md** | Update domain models (2-3 hours) | After DB migrated |
| **phase-03-adapters-layer.md** | Update repositories (3-4 hours) | After domain updated |
| **phase-04-application-layer.md** | Update use cases (1-2 hours) | After adapters updated |
| **phase-05-infrastructure.md** | Verify DI container (30 mins) | After use cases updated |
| **phase-06-api-layer.md** | Update REST/WebSocket (1-2 hours) | After infrastructure verified |
| **phase-07-testing.md** | Update tests (2-3 hours) | After all code updated |
| **phase-08-documentation.md** | Update docs (1 hour) | After tests passing |
| **phase-09-production-deploy.md** | Production deployment (1-2 hours) | After staging validated |
| **IMPLEMENTATION_NOTES.md** | Quick reference guide | During coding, troubleshooting |
| **CHECKLIST.md** | Progress tracker | Track completion |
| **README.md** | This file - overview and getting started | Starting point |

---

## Quick Start Guide

### 1. Before You Begin (5 mins)

Read these documents in order:
1. This README (you're here!)
2. `../../MIGRATION_GUIDE_REDESIGN.md` (migration technical details)
3. `../../DB_REDESIGN_SUMMARY.md` (design decisions rationale)
4. `plan.md` (full implementation plan)

### 2. Pre-Flight Checklist (10 mins)

```bash
# Verify migration file exists
ls -la ../../alembic/versions/0015_251122_redesign_schema.py

# Check current database revision
alembic current
# Should show: 0014 or earlier

# Backup database
pg_dump -F c backup_before_redesign_$(date +%Y%m%d_%H%M%S).dump

# Verify no active interviews
psql -d elios_interview -c "SELECT COUNT(*) FROM interviews WHERE status IN ('QUESTIONING', 'EVALUATING', 'FOLLOW_UP');"
# MUST return 0
```

### 3. Implementation Phases

Follow in order (see `plan.md` for details):

```
Phase 0: Pre-Migration          (30 mins)   - Backup, validation
Phase 1: Database Migration      (45-60m)   - Run Alembic migration
Phase 2: Domain Layer           (2-3 hrs)   - Update models
Phase 3: Adapters Layer         (3-4 hrs)   - Update repositories
Phase 4: Application Layer      (1-2 hrs)   - Update use cases
Phase 5: Infrastructure Layer   (30 mins)   - Update DI container
Phase 6: API Layer              (1-2 hrs)   - Update endpoints
Phase 7: Testing                (2-3 hrs)   - Update/create tests
Phase 8: Documentation          (1 hour)    - Update docs
Phase 9: Production Deployment  (1-2 hrs)   - Deploy to prod
```

**Estimated Total**: 12-18 hours over 2-3 days

### 4. Daily Workflow

**Day 1** (4-6 hours):
- Complete Phase 0-2 (Pre-migration, DB migration, Domain layer)
- Commit & push: "feat(domain): migrate to new schema - domain models"

**Day 2** (4-6 hours):
- Complete Phase 3-5 (Adapters, Application, Infrastructure)
- Commit & push: "feat(adapters): migrate to new schema - repositories"

**Day 3** (4-6 hours):
- Complete Phase 6-8 (API, Testing, Documentation)
- Code review
- Commit & push: "feat(api): migrate to new schema - complete"

**Day 4** (Weekend/Off-hours):
- Phase 9 (Production deployment)
- Monitor for 24 hours

---

## Key Principles

### Architecture
- **Clean Architecture**: Dependencies point inward (Domain ← Application ← Adapters)
- **Repository Pattern**: All data access through ports
- **Domain Purity**: Domain layer has zero external dependencies

### Implementation
- **Incremental**: One layer at a time, test after each phase
- **Reversible**: Can rollback migration with `alembic downgrade -1`
- **Traceable**: Commit after each phase with descriptive messages

### Testing
- **Test-Driven**: Write/update tests BEFORE code changes (when possible)
- **Comprehensive**: Unit + Integration + E2E tests
- **Coverage**: Maintain >85% test coverage

---

## Common Workflows

### Running Migration (Dev)
```bash
# Backup first!
pg_dump -F c backup_dev.dump

# Run migration
alembic upgrade head

# Verify
alembic current  # Should show: 0015 (head)

# Validate data
psql -d elios_interview -f validate_migration.sql
```

### Updating Domain Model
```python
# 1. Update domain/models/cv_analysis.py
from .cv_skill import CVSkill

@dataclass
class CVAnalysis:
    skills: list[CVSkill]  # Changed from list[ExtractedSkill]

# 2. Update tests/unit/domain/test_cv_analysis.py
def test_cv_analysis_with_skills():
    skill = CVSkill(skill_name="Python", proficiency_level=ProficiencyLevel.EXPERT)
    cv = CVAnalysis(skills=[skill])
    assert len(cv.skills) == 1

# 3. Run tests
pytest tests/unit/domain/test_cv_analysis.py -v
```

### Updating Repository
```python
# 1. Update adapters/persistence/cv_analysis_repository.py
async def get_cv_analysis_with_skills(self, cv_id: UUID) -> CVAnalysis:
    query = """
        SELECT cv.*, s.*
        FROM cv_analyses cv
        LEFT JOIN cv_skills s ON s.cv_analysis_id = cv.id
        WHERE cv.id = $1
    """
    rows = await self.db.fetch_all(query, cv_id)
    # Map to domain model...

# 2. Update tests/integration/adapters/persistence/test_cv_analysis_repository.py
async def test_get_cv_with_skills(db_session):
    cv = await repo.get_cv_analysis_with_skills(cv_id)
    assert len(cv.skills) > 0

# 3. Run tests
pytest tests/integration/adapters/persistence/test_cv_analysis_repository.py -v
```

---

## Troubleshooting

### Migration Fails

**Error**: "ENUM does not exist"
```bash
# Solution: Drop and recreate
psql -d elios_interview -c "DROP TYPE IF EXISTS question_type_enum CASCADE;"
alembic upgrade head
```

**Error**: "Active interviews detected"
```bash
# Solution: Complete or cancel active interviews first
psql -d elios_interview -c "UPDATE interviews SET status = 'CANCELLED' WHERE status IN ('QUESTIONING', 'EVALUATING', 'FOLLOW_UP');"
# Then retry migration
```

### Tests Failing

**Error**: "AttributeError: 'CVAnalysis' has no attribute 'cv_file_path'"
```python
# Solution: Update code to remove cv_file_path references
# It was moved to candidates table
```

**Error**: "Column 'question_ids' does not exist"
```python
# Solution: Use repository method instead
# OLD: interview.question_ids[0]
# NEW: await repo.get_current_question(interview.id)
```

### Performance Issues

**Slow query**: "SELECT * FROM cv_analyses JOIN cv_skills"
```sql
-- Solution: Use helper view instead
SELECT * FROM cv_analysis_with_skills WHERE id = ?;
```

**N+1 queries**: Loading skills for multiple CVs
```python
# Solution: Batch load or use JOIN
# Use get_cv_analysis_with_skills() which JOINs in single query
```

---

## Rollback Procedures

### Rollback Migration Only
```bash
# If migration completed but need to revert
alembic downgrade -1

# Restart application with old code
```

### Full Rollback (Production)
```bash
# 1. Stop application
systemctl stop elios-api  # Or your deployment method

# 2. Restore database
pg_restore --clean --if-exists -d elios_interview backup_before_redesign_*.dump

# 3. Deploy previous code version
git checkout <previous-commit>
# Deploy...

# 4. Start application
systemctl start elios-api
```

---

## Success Metrics

After completion, verify:

✅ **Technical**
- All tests passing (>85% coverage)
- Zero data loss
- No performance degradation (<10%)
- No error spikes (<1%)

✅ **Business**
- All interviews created pre-migration accessible
- New interviews can be created/completed
- CV analysis functional
- Zero customer complaints

✅ **Code Quality**
- No linting errors: `ruff check src/`
- Code formatted: `black src/`
- Type checking: `mypy src/`
- Documentation complete

---

## Resources

### Documentation
- [MIGRATION_GUIDE_REDESIGN.md](../../MIGRATION_GUIDE_REDESIGN.md) - Technical migration steps
- [DB_REDESIGN_SUMMARY.md](../../DB_REDESIGN_SUMMARY.md) - Design decisions
- [docs/system-architecture.md](../../docs/system-architecture.md) - Architecture overview
- [docs/code-standards.md](../../docs/code-standards.md) - Coding conventions

### Migration Files
- [0015_251122_redesign_schema.py](../../alembic/versions/0015_251122_redesign_schema.py) - Alembic migration SQL

### Reference
- Clean Architecture: https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html
- SQLAlchemy 2.0: https://docs.sqlalchemy.org/en/20/
- Alembic: https://alembic.sqlalchemy.org/

---

## Getting Help

### Self-Service
1. Check `IMPLEMENTATION_NOTES.md` for common patterns
2. Review `plan.md` for detailed phase instructions
3. Search error messages in migration guide
4. Check validation queries in Phase 1 of plan

### Escalation
1. Review plan + migration guide thoroughly
2. Check database logs + application logs
3. Run validation queries to diagnose issue
4. Consult with tech lead if critical
5. Rollback if severity high + no quick fix

---

## Post-Implementation

After successful migration:
1. Archive plan to `docs/migrations/`
2. Update team wiki/documentation
3. Create post-mortem document
4. Share lessons learned with team
5. Plan next iteration (UI features, optimizations)

---

## Questions?

- **Architecture**: See `docs/system-architecture.md`
- **Code Standards**: See `docs/code-standards.md`
- **Migration Details**: See `MIGRATION_GUIDE_REDESIGN.md`
- **Design Rationale**: See `DB_REDESIGN_SUMMARY.md`
- **Implementation**: See `plan.md`

---

**Ready to Start?**

1. ✅ Read this README
2. ✅ Review referenced documentation
3. ✅ Backup database
4. ✅ Open `CHECKLIST.md` for tracking
5. ✅ Begin Phase 0 of `plan.md`

Good luck! 🚀

---

**Last Updated**: 2025-11-22
**Version**: 1.0
