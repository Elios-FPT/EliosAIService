# Database Schema Migration - Quick Checklist

**Plan**: 251122-1801-db-schema-migration
**Use this for**: Quick progress tracking during implementation

---

## Phase 0: Pre-Migration (30 mins)

- [ ] Database backup created
  ```bash
  pg_dump -F c backup_before_redesign_$(date +%Y%m%d_%H%M%S).dump
  ```
- [ ] No active interviews confirmed
  ```sql
  SELECT COUNT(*) FROM interviews WHERE status IN ('QUESTIONING', 'EVALUATING', 'FOLLOW_UP');
  -- Must return 0
  ```
- [ ] Migration file reviewed: `alembic/versions/0015_251122_redesign_schema.py`
- [ ] Current revision confirmed: `alembic current`

---

## Phase 1: Database Migration (45-60 mins)

- [ ] Migration executed: `alembic upgrade head`
- [ ] Current revision verified: 0015 (head)
- [ ] New tables exist: cv_skills, interview_questions
- [ ] ENUMs created: question_type_enum, difficulty_enum, proficiency_level_enum
- [ ] cv_skills data migrated correctly
- [ ] interview_questions data migrated correctly
- [ ] prompt_templates decomposed correctly
- [ ] Helper views functional: interview_details, cv_analysis_with_skills
- [ ] Integrity checks passed (no orphaned records)

---

## Phase 2: Domain Layer Updates (2-3 hours)

### New Models
- [ ] `src/domain/models/cv_skill.py` created
  - [ ] `CVSkill` dataclass
  - [ ] `ProficiencyLevel` enum
- [ ] `src/domain/models/interview_question.py` created
  - [ ] `InterviewQuestion` dataclass

### Updated Models
- [ ] `src/domain/models/cv_analysis.py` updated
  - [ ] `skills: list[CVSkill]` instead of `list[ExtractedSkill]`
  - [ ] Removed `cv_file_path`, `metadata`
- [ ] `src/domain/models/question.py` updated
  - [ ] `QuestionType`: Added PROBLEM_SOLVING, SYSTEM_DESIGN
  - [ ] `DifficultyLevel`: Added EXPERT
  - [ ] Removed `tags`, `evaluation_criteria`
- [ ] `src/domain/models/interview.py` updated
  - [ ] Removed `question_ids`, `answer_ids`
  - [ ] Methods updated for repository-based access
- [ ] `src/domain/models/answer.py` updated
  - [ ] Removed `candidate_id`, `metadata`, deprecated fields
- [ ] `src/domain/models/prompt_template.py` updated
  - [ ] Added 11 decomposed fields
  - [ ] Added `deleted_at`
  - [ ] `template_json` as read-only
- [ ] `src/domain/models/__init__.py` updated with new exports

### Testing
- [ ] Domain model tests passing: `pytest tests/unit/domain/ -v`

---

## Phase 3: Adapters Layer - Persistence (3-4 hours)

### Models & Mappers
- [ ] `src/adapters/persistence/models.py` updated
  - [ ] `CVSkillModel` added
  - [ ] `InterviewQuestionModel` added
  - [ ] 6 existing models updated
- [ ] `src/adapters/persistence/mappers.py` updated
  - [ ] `CVSkillMapper` added
  - [ ] `InterviewQuestionMapper` added
  - [ ] 4 existing mappers updated

### Repositories
- [ ] `src/adapters/persistence/cv_analysis_repository.py` updated
  - [ ] `get_cv_analysis_with_skills()` method
  - [ ] `add_skill_to_cv()` method
  - [ ] `remove_skill_from_cv()` method
- [ ] `src/adapters/persistence/interview_repository.py` updated
  - [ ] `get_interview_questions()` method
  - [ ] `add_question_to_interview()` method
  - [ ] `get_current_question()` method
  - [ ] `mark_question_asked()` method
- [ ] `src/adapters/persistence/question_repository.py` updated
  - [ ] ENUM type filters updated
- [ ] `src/adapters/persistence/postgres_prompt_repository.py` updated
  - [ ] Methods use decomposed fields

### Testing
- [ ] Repository tests passing: `pytest tests/integration/adapters/persistence/ -v`

---

## Phase 4: Application Layer Updates (1-2 hours)

### Use Cases
- [ ] `src/application/use_cases/analyze_cv.py` updated
  - [ ] Creates `CVSkill` entities
  - [ ] Calls `add_skill_to_cv()`
- [ ] `src/application/use_cases/plan_interview.py` updated
  - [ ] Uses `add_question_to_interview()` with sequence_order
- [ ] `src/application/use_cases/get_next_question.py` updated
  - [ ] Uses `get_current_question()`
  - [ ] Marks question as asked

### DTOs (Optional)
- [ ] `src/application/dto/interview_dto.py` updated

### Testing
- [ ] Use case tests passing: `pytest tests/unit/application/use_cases/ -v`

---

## Phase 5: Infrastructure Layer Updates (30 mins)

- [ ] `src/infrastructure/dependency_injection/container.py` reviewed
  - [ ] All dependencies resolve correctly
  - [ ] DI container initializes without errors

---

## Phase 6: API Layer Updates (1-2 hours)

### REST API
- [ ] `src/adapters/api/rest/interview_routes.py` updated
  - [ ] Response models updated (no question_ids array)
- [ ] `src/adapters/api/rest/prompt_template_routes.py` created (OPTIONAL)
  - [ ] GET /api/prompts/{id} - Fetch for editing
  - [ ] PATCH /api/prompts/{id} - Update (creates version)
  - [ ] POST /api/prompts/{id}/preview - Preview with sample

### WebSocket
- [ ] `src/adapters/api/websocket/interview_handler.py` updated
  - [ ] Uses `get_current_question()`

### Testing
- [ ] API tests passing: `pytest tests/integration/api/ -v`

---

## Phase 7: Testing (2-3 hours)

### Unit Tests
- [ ] `tests/unit/domain/test_cv_skill.py` created
- [ ] `tests/unit/domain/test_interview_question.py` created
- [ ] `tests/unit/domain/test_cv_analysis.py` updated
- [ ] `tests/unit/domain/test_question.py` updated
- [ ] `tests/unit/domain/test_interview.py` updated

### Integration Tests
- [ ] `tests/integration/adapters/persistence/test_cv_analysis_repository.py` updated
- [ ] `tests/integration/adapters/persistence/test_interview_repository.py` updated
- [ ] `tests/integration/adapters/persistence/test_question_repository.py` updated
- [ ] `tests/integration/adapters/persistence/test_prompt_repository.py` updated

### Application Tests
- [ ] `tests/unit/application/use_cases/test_analyze_cv.py` updated
- [ ] `tests/unit/application/use_cases/test_plan_interview.py` updated
- [ ] `tests/integration/api/test_interview_routes.py` updated

### Full Suite
- [ ] All tests passing: `pytest --cov=src --cov-report=html -v`
- [ ] Test coverage >85%

---

## Phase 8: Documentation Updates (1 hour)

- [ ] `docs/codebase-summary.md` updated
  - [ ] Domain models section (9 models total)
  - [ ] Repository methods documented
- [ ] `docs/system-architecture.md` updated
  - [ ] Database architecture diagram
  - [ ] New tables/ENUMs documented
- [ ] `docs/migrations/0015-schema-redesign.md` created
  - [ ] Summary of changes
  - [ ] Breaking changes documented
  - [ ] Migration instructions
- [ ] `CLAUDE.md` updated with examples
- [ ] `README.md` reviewed (optional)

---

## Phase 9: Production Deployment (1-2 hours)

### Pre-Deployment
- [ ] All tests passing (dev, staging)
- [ ] Code review approved
- [ ] Migration tested on staging
- [ ] Backup strategy confirmed
- [ ] Rollback plan documented
- [ ] Team notified of maintenance window

### Deployment Steps
- [ ] T-5min: Final production backup created
- [ ] T+0min: Application stopped
- [ ] T+2min: No active interviews verified
- [ ] T+5min: Migration executed (`alembic upgrade head`)
- [ ] T+20min: Data integrity validated
- [ ] T+25min: New code deployed
- [ ] T+30min: Smoke tests completed
- [ ] T+35min: Application resumed

### Post-Deployment
- [ ] API health check passing
- [ ] Interview creation/completion working
- [ ] No error spikes in logs
- [ ] Database query performance acceptable

---

## Success Criteria

### Technical
- [ ] All tests passing (>85% coverage maintained)
- [ ] Zero data loss (row counts match)
- [ ] No performance degradation (<10% increase)
- [ ] No error spikes (<1% error rate)

### Business
- [ ] Zero downtime or <30 min maintenance
- [ ] Pre-migration interviews accessible
- [ ] New interviews functional
- [ ] CV analysis working

### Code Quality
- [ ] No linting errors: `ruff check src/`
- [ ] Code formatted: `black src/`
- [ ] Type hints coverage >95%: `mypy src/`
- [ ] Documentation complete

---

## Rollback Triggers

Rollback if:
- [ ] Data integrity validation fails
- [ ] Performance degradation >10%
- [ ] Error rate >5% in production
- [ ] Data loss detected
- [ ] Application fails to start

**Rollback Command**: `alembic downgrade -1`

**Full Restore**: `pg_restore --clean backup_before_redesign_*.dump`

---

## Final Sign-off

- [ ] Architect approval
- [ ] Database admin approval
- [ ] Tech lead approval
- [ ] Product owner approval

---

## Progress Tracking

**Start Date**: ___________
**Target Completion**: ___________
**Actual Completion**: ___________

**Notes**:
```
[Space for implementation notes, issues encountered, lessons learned]
```

---

**Last Updated**: 2025-11-22
**Version**: 1.0
