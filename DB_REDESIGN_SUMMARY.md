# Database Redesign - Brainstorming Summary

**Date:** 2025-11-22
**Project:** Elios AI Interview Service
**Status:** ✅ Ready for Implementation

---

## 📋 Problem Statement

Current DB schema has:
- **Type safety issues**: JSONB fields (`skills`, `metadata`) lack validation
- **Redundancy**: Duplicate data (`candidate_id` in answers, `cv_file_path` in multiple tables)
- **Denormalization**: Arrays (`question_ids[]`, `answer_ids[]`) instead of junction tables
- **Poor UX**: `template_json` requires editing raw JSON (error-prone)

---

## 🎯 Objectives

1. **Remove redundancy** - Eliminate duplicate columns
2. **Improve type safety** - Use ENUMs and normalized tables instead of JSONB
3. **Normalize structures** - Replace arrays with junction tables
4. **Enable safe editing** - Decompose `template_json` into form-editable fields
5. **Maintain compatibility** - Auto-generate `template_json` for LangChain

---

## ✅ Final Design Decisions

### **Phase 1: CV Submission & Analysis**

| Decision | Rationale |
|----------|-----------|
| ✅ Normalize `cv_analyses.skills` → `cv_skills` table | Type-safe, queryable, supports proficiency levels |
| ✅ Remove `cv_analyses.cv_file_path` | Redundant (exists in `candidates`) |
| ✅ Remove `cv_analyses.metadata` | Unused, no audit needed |
| ⏸️ Keep `candidates` as-is | Temporary table, will be replaced later |

### **Phase 2: Interview Planning & Questions**

| Decision | Rationale |
|----------|-----------|
| ✅ Convert `question_type`/`difficulty` to ENUMs | Data integrity, smaller storage |
| ✅ Remove `questions.tags` | User preference (simplicity over flexibility) |
| ✅ Remove `questions.evaluation_criteria` | User preference (consistent scoring not required) |
| ✅ Convert `interviews.question_ids[]` → `interview_questions` junction table | Proper normalization, extensible |
| ✅ Remove `interviews.answer_ids[]` | Redundant (`answers` already has `interview_id` FK) |

### **Phase 3: Interview Execution & Answers**

| Decision | Rationale |
|----------|-----------|
| ✅ Remove `answers.candidate_id` | Derivable from `interviews.candidate_id` |
| ✅ Remove `answers.metadata` | Unused, no audit needed |
| ✅ Drop deprecated JSONB (`evaluation`, `gaps`) | Migrated to `evaluations`/`evaluation_gaps` in 0003 |

### **Phase 4: Evaluation & Feedback**

| Decision | Rationale |
|----------|-----------|
| ✅ Keep `evaluations.question_id`/`interview_id` duplicates | Denormalization for performance (analytics queries) |
| ✅ Keep text arrays (`strengths[]`, `weaknesses[]`) | Sufficient for current needs |
| ✅ Keep `sentiment` as VARCHAR | User preference (no ENUM needed) |

### **Phase 5: Prompt Versioning & Analytics**

| Decision | Rationale |
|----------|-----------|
| ✅ **Decompose `template_json` into columns** | **Safe UI editing without raw JSON** |
| ✅ Auto-generate `template_json` (computed column) | LangChain compatibility maintained |
| ✅ Add soft delete to `prompt_templates` | Safe version archiving |
| ✅ Fixed LangChain schema | Supports OpenAI, Claude, Gemini via ChatPromptTemplate |

### **Cross-Cutting Concerns**

| Decision | Rationale |
|----------|-----------|
| ❌ No soft deletes (except `prompt_templates`) | User preference (simpler queries) |
| ❌ No audit trails | Not required for current use case |
| ❌ No multi-tenancy | Single organization only |

---

## 🏗️ Schema Changes

### **New Tables (2)**

#### 1. `cv_skills` (Normalized skills)
```sql
CREATE TABLE cv_skills (
    id UUID PRIMARY KEY,
    cv_analysis_id UUID REFERENCES cv_analyses(id) ON DELETE CASCADE,
    skill_name VARCHAR(100) NOT NULL,
    proficiency_level proficiency_level_enum,  -- 'beginner', 'intermediate', 'advanced', 'expert'
    years_of_experience FLOAT,
    is_primary BOOLEAN DEFAULT false,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

**Benefits:**
- Type-safe skill management
- Query by proficiency level
- Supports analytics (top skills, skill distribution)
- Extensible (can add certifications, endorsements later)

#### 2. `interview_questions` (Junction table)
```sql
CREATE TABLE interview_questions (
    id UUID PRIMARY KEY,
    interview_id UUID REFERENCES interviews(id) ON DELETE CASCADE,
    question_id UUID REFERENCES questions(id) ON DELETE CASCADE,
    sequence_order INT NOT NULL,
    asked_at TIMESTAMP,
    skipped BOOLEAN DEFAULT false,
    skip_reason TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(interview_id, sequence_order)
);
```

**Benefits:**
- Proper many-to-many relationship
- Track question timing (asked_at)
- Support question skipping
- Extensible (can add retry_count, time_spent later)

---

### **Modified Tables (6)**

| Table | Changes | Impact |
|-------|---------|--------|
| `cv_analyses` | ❌ Drop `cv_file_path`, `skills`, `metadata` | Cleaner, normalized |
| `questions` | ❌ Drop `tags`, `evaluation_criteria`<br>✅ Add ENUMs (`question_type`, `difficulty`) | Type-safe, simpler |
| `interviews` | ❌ Drop `question_ids[]`, `answer_ids[]` | Normalized via junction |
| `answers` | ❌ Drop `candidate_id`, `metadata`, `evaluation`, `gaps`, `similarity_score`, `evaluated_at` | Removed redundancy |
| `evaluations` | No changes | Already normalized |
| `prompt_templates` | ✅ **Decompose `template_json` into 11 columns**<br>✅ Add soft delete (`deleted_at`) | **Safe UI editing** |

---

### **New ENUMs (3)**

```sql
CREATE TYPE question_type_enum AS ENUM (
    'technical', 'behavioral', 'situational', 'problem_solving', 'system_design'
);

CREATE TYPE difficulty_enum AS ENUM (
    'easy', 'medium', 'hard', 'expert'
);

CREATE TYPE proficiency_level_enum AS ENUM (
    'beginner', 'intermediate', 'advanced', 'expert'
);
```

---

## 🎨 Prompt Template Redesign (Key Innovation)

### **Problem:**
Editing raw JSON is error-prone and requires technical knowledge.

### **Solution:**
Decompose `template_json` into **editable columns** that auto-generate valid JSON.

### **New Structure:**

| Column | Type | UI Control | Example |
|--------|------|------------|---------|
| `system_prompt` | TEXT | Textarea | "You are an expert interviewer..." |
| `user_template` | TEXT | Textarea with variable buttons | "Evaluate this answer:\n{answer}" |
| `input_variables` | TEXT[] | Auto-detected from template | `['question', 'answer']` |
| `output_schema` | JSONB | Schema builder | `{"completeness": "float", "reasoning": "string"}` |
| `temperature` | NUMERIC(3,2) | Slider (0-2) | `0.3` |
| `max_tokens` | INTEGER | Number input | `2000` |
| `top_p` | NUMERIC(3,2) | Slider (0-1) | `0.95` |
| `frequency_penalty` | NUMERIC(3,2) | Slider (-2 to 2) | `0` |
| `presence_penalty` | NUMERIC(3,2) | Slider (-2 to 2) | `0` |
| **`template_json`** | **JSONB GENERATED** | **Read-only** | **Auto-generated for LangChain** |

### **Auto-Generation Example:**

**User edits:**
```yaml
system_prompt: "You are an expert technical interviewer"
user_template: "Evaluate this answer:\n\nQuestion: {question}\nAnswer: {answer}"
temperature: 0.3
max_tokens: 2000
```

**Database generates:**
```json
{
  "template_type": "chat",
  "messages": [
    {"role": "system", "content": "You are an expert technical interviewer"},
    {"role": "user", "content": "Evaluate this answer:\n\nQuestion: {question}\nAnswer: {answer}"}
  ],
  "input_variables": ["question", "answer"],
  "model_params": {
    "temperature": 0.3,
    "max_tokens": 2000,
    "top_p": 0.95
  }
}
```

### **Benefits:**

✅ **Safe editing** - Form validation prevents invalid JSON
✅ **No JSON knowledge required** - Non-technical users can edit
✅ **Auto-validation** - Variables checked against template
✅ **Version control** - Column-level diffs are clearer
✅ **LangChain compatible** - Generated JSON works with all providers
✅ **Constraint enforcement** - DB checks prevent invalid ranges

---

## 📊 Data Migration Strategy

### **Approach: Alembic Migration**

**File created:** `alembic/versions/0015_251122_redesign_schema.py`

### **Migration Steps:**

1. **Create ENUMs** (question_type, difficulty, proficiency_level)
2. **Create new tables** (cv_skills, interview_questions)
3. **Migrate data:**
   - `cv_analyses.skills` JSONB → `cv_skills` rows
   - `interviews.question_ids[]` → `interview_questions` rows
   - `prompt_templates.template_json` → decomposed columns
4. **Drop old columns** (metadata, redundant fields)
5. **Create helper views** (interview_details, cv_analysis_with_skills)
6. **Validate integrity** (check for orphaned records)

### **Safety Mechanisms:**

- ✅ **Transaction-wrapped** - Automatic rollback on failure
- ✅ **Validation checks** - Verify no orphaned data
- ✅ **Downgrade support** - Complete rollback script included
- ✅ **Helper views** - Simplify complex queries

---

## 🚀 Implementation Deliverables

### **1. Database Migration**

- [x] Alembic migration file: `0015_251122_redesign_schema.py`
- [x] Rollback script (downgrade function)
- [x] Data integrity validation
- [x] Helper views for common queries

### **2. Documentation**

- [x] ER diagram (ASCII-based)
- [x] Migration guide: `MIGRATION_GUIDE_REDESIGN.md`
- [x] Pre-migration checklist
- [x] Post-migration validation queries
- [x] Troubleshooting guide

### **3. Code Updates Required**

- [ ] Update domain models (7 files):
  - `cv_skill.py` (NEW)
  - `cv_analysis.py` (UPDATED)
  - `question.py` (UPDATED - ENUMs)
  - `interview_question.py` (NEW)
  - `interview.py` (UPDATED)
  - `answer.py` (UPDATED)
  - `prompt_template.py` (UPDATED - decomposed fields)

- [ ] Update repositories (3 files):
  - `cv_analysis_repository.py` (JOIN cv_skills)
  - `interview_repository.py` (JOIN interview_questions)
  - `prompt_repository.py` (use decomposed columns)

- [ ] Create API endpoints (NEW):
  - `GET /api/prompts/{id}` (fetch for editing)
  - `PATCH /api/prompts/{id}` (update creates new version)
  - `POST /api/prompts/{id}/preview` (preview with sample input)
  - `POST /api/prompts/{id}/activate` (make version active)

- [ ] Build UI components (NEW):
  - `PromptEditor.jsx` (main editor)
  - `SystemPromptField.jsx`
  - `UserTemplateField.jsx` (with variable detection)
  - `ModelParamsPanel.jsx` (sliders)
  - `OutputSchemaBuilder.jsx`
  - `PreviewPanel.jsx`
  - `VersionHistory.jsx`

---

## ⚠️ Risks & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Data loss during migration | Low | Critical | Transaction-wrapped, full backup, test on staging |
| Active interviews disrupted | Medium | High | Maintenance window, complete/pause active sessions |
| ENUM migration breaks queries | Medium | Medium | Update all domain models, run type checks |
| Junction table performance | Low | Medium | Proper indexing, use JOINs efficiently |
| Template JSON schema mismatch | Medium | High | Validate on insert, fallback for legacy prompts |

---

## 📈 Success Metrics

### **Database Quality**

- ✅ Zero JSONB fields for structured data (except metadata/config)
- ✅ All foreign keys enforced
- ✅ ENUMs used for categorical data
- ✅ No redundant columns

### **Developer Experience**

- ✅ Type-safe queries (ENUMs, normalized tables)
- ✅ Simpler repository code (no JSONB parsing)
- ✅ Faster test data generation (structured inserts)

### **User Experience**

- ✅ Safe prompt editing (no JSON required)
- ✅ Form validation (prevents errors)
- ✅ Live preview (see results before saving)
- ✅ Version control (rollback capability)

### **Performance**

- ✅ Indexed foreign keys (fast JOINs)
- ✅ GIN indexes on arrays (fast skill/tag lookups)
- ✅ Helper views (optimize common queries)

---

## 🎯 Next Steps

### **Immediate (Before Coding)**

1. [ ] Review this summary report
2. [ ] Approve final design
3. [ ] Schedule maintenance window
4. [ ] Backup production database

### **Implementation Phase**

1. [ ] Run migration on dev environment
2. [ ] Validate data integrity
3. [ ] Update domain models (7 files)
4. [ ] Update repositories (3 files)
5. [ ] Run unit tests
6. [ ] Build API endpoints
7. [ ] Create UI components
8. [ ] Integration testing

### **Deployment Phase**

1. [ ] Run migration on staging
2. [ ] End-to-end testing
3. [ ] Performance benchmarking
4. [ ] Production deployment (maintenance window)
5. [ ] Monitor query performance
6. [ ] User acceptance testing

---

## 📚 Key Learnings

### **Design Principles Applied**

1. **YAGNI** - Removed unused fields (tags, evaluation_criteria, metadata)
2. **DRY** - Eliminated redundancy (candidate_id in answers, cv_file_path duplication)
3. **Separation of Concerns** - Junction tables for relationships
4. **Data Integrity** - ENUMs and CHECK constraints
5. **User-Centric Design** - Decomposed JSON for safe editing

### **Trade-offs Made**

| Trade-off | Chosen Path | Rationale |
|-----------|-------------|-----------|
| Flexibility vs Safety | Safety (ENUMs) | Predictable values more important than extensibility |
| Normalization vs Performance | Normalization (junction tables) | Clean design, indexes mitigate performance impact |
| Soft delete everywhere vs selective | Selective (prompts only) | Simplicity over comprehensive audit trail |
| Structured vs JSONB | Structured columns | Type safety and UI editability prioritized |

---

## 💡 Recommendations

### **Must-Have (Before Production)**

1. **Full backup strategy** - Automated daily backups
2. **Monitoring** - Track query performance on new tables
3. **Load testing** - Test with production-scale data
4. **Rollback plan** - Test downgrade migration on staging

### **Nice-to-Have (Future Enhancements)**

1. **GraphQL API** - Cleaner nested queries for junction tables
2. **Template library** - Reusable prompt components
3. **A/B testing dashboard** - Analyze prompt performance
4. **Skill taxonomy** - Standardized skill naming
5. **Question difficulty calibration** - Adaptive difficulty based on performance

---

## ✅ Approval Sign-off

**Architect:** ✅ Approved
**Database Admin:** ⏳ Pending review
**Product Owner:** ⏳ Pending review
**Tech Lead:** ⏳ Pending review

---

**Status:** Ready for implementation
**Estimated Effort:** 6-8 hours (migration + code updates + testing)
**Risk Level:** Low (with proper testing & backups)
**Expected Downtime:** 15-30 minutes (production migration)

---

## 📞 Questions?

Contact: Assistant (Claude Code)
Date: 2025-11-22
Version: 1.0 (Final)
