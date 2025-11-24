# Database Redesign Migration Guide

## Overview
This guide covers the implementation of schema redesign including:
- Normalized `cv_skills` table
- Junction `interview_questions` table
- ENUMs for type safety
- **Decomposed `prompt_templates` for UI editing**
- Removed redundant fields

## 🚀 Migration Steps

### 1. Pre-Migration Checklist

```bash
# Backup database
pg_dump -h localhost -U postgres -d elios_interview \
  -F c -b -v -f backup_before_redesign_$(date +%Y%m%d_%H%M%S).dump

# Check current data volumes
psql -d elios_interview -c "
SELECT 'candidates' AS table_name, COUNT(*) AS row_count FROM candidates
UNION ALL SELECT 'cv_analyses', COUNT(*) FROM cv_analyses
UNION ALL SELECT 'questions', COUNT(*) FROM questions
UNION ALL SELECT 'interviews', COUNT(*) FROM interviews
UNION ALL SELECT 'prompt_templates', COUNT(*) FROM prompt_templates;"

# Verify no active interviews
psql -d elios_interview -c "
SELECT COUNT(*) AS active_interviews
FROM interviews
WHERE status IN ('in_progress', 'scheduled');"
```

### 2. Run Migration

```bash
# Test on dev/staging first
export DATABASE_URL="postgresql://user:pass@localhost/elios_interview_dev"

# Run migration
alembic upgrade head

# Verify current revision
alembic current
# Should show: 0015 (head)

# Check migration log
alembic history -v
```

### 3. Validate Migration

```sql
-- Verify new tables exist
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
AND table_name IN ('cv_skills', 'interview_questions');

-- Verify ENUMs created
SELECT typname FROM pg_type
WHERE typname IN ('question_type_enum', 'difficulty_enum', 'proficiency_level_enum');

-- Verify skills migration
SELECT
    cv.id,
    COUNT(s.id) AS skill_count,
    json_agg(s.skill_name) AS skills
FROM cv_analyses cv
LEFT JOIN cv_skills s ON s.cv_analysis_id = cv.id
GROUP BY cv.id
LIMIT 5;

-- Verify interview questions migration
SELECT
    i.id,
    COUNT(iq.id) AS question_count
FROM interviews i
LEFT JOIN interview_questions iq ON iq.interview_id = i.id
GROUP BY i.id
LIMIT 5;

-- Verify prompt_templates decomposition
SELECT
    name,
    version,
    LENGTH(system_prompt) AS system_prompt_length,
    LENGTH(user_template) AS user_template_length,
    array_length(input_variables, 1) AS variable_count,
    temperature,
    max_tokens
FROM prompt_templates
LIMIT 3;
```

### 4. Rollback (if needed)

```bash
# Rollback to previous revision
alembic downgrade -1

# Or rollback to specific revision
alembic downgrade 0014
```

---

## 📝 Code Updates Required

### 1. Update Domain Models

**`src/domain/models/cv_skill.py`** (NEW)
```python
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID
from enum import Enum

class ProficiencyLevel(str, Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"

@dataclass
class CVSkill:
    id: UUID
    cv_analysis_id: UUID
    skill_name: str
    proficiency_level: ProficiencyLevel | None = None
    years_of_experience: float | None = None
    is_primary: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)
```

**`src/domain/models/cv_analysis.py`** (UPDATED)
```python
from dataclasses import dataclass, field
from typing import List
from .cv_skill import CVSkill

@dataclass
class CVAnalysis:
    id: UUID
    candidate_id: UUID
    extracted_text: str
    skills: List[CVSkill] = field(default_factory=list)  # ✅ Changed from JSONB
    work_experience_years: float | None = None
    education_level: str | None = None
    suggested_topics: List[str] = field(default_factory=list)
    suggested_difficulty: str = "medium"
    embedding: List[float] | None = None
    summary: str | None = None
    # ❌ Removed: metadata, cv_file_path
    created_at: datetime = field(default_factory=datetime.utcnow)
```

**`src/domain/models/question.py`** (UPDATED)
```python
from enum import Enum

class QuestionType(str, Enum):
    TECHNICAL = "technical"
    BEHAVIORAL = "behavioral"
    SITUATIONAL = "situational"
    PROBLEM_SOLVING = "problem_solving"
    SYSTEM_DESIGN = "system_design"

class Difficulty(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    EXPERT = "expert"

@dataclass
class Question:
    id: UUID
    text: str
    question_type: QuestionType  # ✅ Changed to Enum
    difficulty: Difficulty       # ✅ Changed to Enum
    skills: List[str] = field(default_factory=list)
    # ❌ Removed: tags, evaluation_criteria
    ideal_answer: str | None = None
    rationale: str | None = None
    version: int = 1
    embedding: List[float] | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
```

**`src/domain/models/interview_question.py`** (NEW)
```python
@dataclass
class InterviewQuestion:
    """Junction model for interview-question relationship"""
    id: UUID
    interview_id: UUID
    question_id: UUID
    sequence_order: int
    asked_at: datetime | None = None
    skipped: bool = False
    skip_reason: str | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
```

**`src/domain/models/interview.py`** (UPDATED)
```python
@dataclass
class Interview:
    id: UUID
    candidate_id: UUID
    status: str
    cv_analysis_id: UUID | None = None
    # ❌ Removed: question_ids, answer_ids
    current_question_index: int = 0
    plan_metadata: dict = field(default_factory=dict)
    adaptive_follow_ups: List[UUID] = field(default_factory=list)
    current_parent_question_id: UUID | None = None
    current_followup_count: int = 0
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
```

**`src/domain/models/answer.py`** (UPDATED)
```python
@dataclass
class Answer:
    id: UUID
    interview_id: UUID
    question_id: UUID
    # ❌ Removed: candidate_id
    text: str
    is_voice: bool = False
    audio_file_path: str | None = None
    duration_seconds: float | None = None
    # ❌ Removed: evaluation, gaps, similarity_score, evaluated_at, metadata
    evaluation_id: UUID | None = None
    embedding: List[float] | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
```

**`src/domain/models/prompt_template.py`** (UPDATED)
```python
from decimal import Decimal

@dataclass
class PromptTemplate:
    id: UUID
    name: str
    version: int
    parent_version_id: UUID | None = None
    change_summary: str | None = None

    # ✅ NEW: Decomposed editable fields
    system_prompt: str = ""
    user_template: str = ""
    input_variables: List[str] = field(default_factory=list)
    partial_variables: dict = field(default_factory=dict)
    output_parser_type: str = "json_output_parser"
    output_schema: dict = field(default_factory=dict)

    # ✅ NEW: Model parameters
    temperature: Decimal = Decimal("0.3")
    max_tokens: int = 2000
    top_p: Decimal = Decimal("0.95")
    frequency_penalty: Decimal = Decimal("0")
    presence_penalty: Decimal = Decimal("0")

    # Computed field (read-only, generated by DB)
    template_json: dict = field(default_factory=dict)

    # Metadata
    is_active: bool = False
    is_draft: bool = True
    ab_test_group: str | None = None
    traffic_percentage: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    created_by: str | None = None
    notes: str | None = None
    deleted_at: datetime | None = None  # ✅ NEW: Soft delete
```

---

### 2. Update Repository Queries

**`src/adapters/persistence/cv_analysis_repository.py`**
```python
async def get_cv_analysis_with_skills(self, cv_analysis_id: UUID) -> CVAnalysis:
    """Fetch CV analysis with normalized skills"""
    query = """
        SELECT
            cv.*,
            s.id as skill_id,
            s.skill_name,
            s.proficiency_level,
            s.years_of_experience,
            s.is_primary,
            s.created_at as skill_created_at
        FROM cv_analyses cv
        LEFT JOIN cv_skills s ON s.cv_analysis_id = cv.id
        WHERE cv.id = $1
        ORDER BY s.is_primary DESC, s.skill_name
    """
    rows = await self.db.fetch_all(query, cv_analysis_id)

    if not rows:
        raise NotFoundError(f"CV analysis {cv_analysis_id} not found")

    # Group skills
    skills = [
        CVSkill(
            id=row['skill_id'],
            cv_analysis_id=cv_analysis_id,
            skill_name=row['skill_name'],
            proficiency_level=row['proficiency_level'],
            years_of_experience=row['years_of_experience'],
            is_primary=row['is_primary'],
            created_at=row['skill_created_at']
        )
        for row in rows if row['skill_id'] is not None
    ]

    # Map to domain model
    return CVAnalysis(
        id=rows[0]['id'],
        candidate_id=rows[0]['candidate_id'],
        extracted_text=rows[0]['extracted_text'],
        skills=skills,
        work_experience_years=rows[0]['work_experience_years'],
        education_level=rows[0]['education_level'],
        suggested_topics=rows[0]['suggested_topics'],
        suggested_difficulty=rows[0]['suggested_difficulty'],
        embedding=rows[0]['embedding'],
        summary=rows[0]['summary'],
        created_at=rows[0]['created_at']
    )

async def add_skill_to_cv(self, cv_skill: CVSkill) -> CVSkill:
    """Add skill to CV analysis"""
    query = """
        INSERT INTO cv_skills (cv_analysis_id, skill_name, proficiency_level, years_of_experience, is_primary)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING *
    """
    row = await self.db.fetch_one(
        query,
        cv_skill.cv_analysis_id,
        cv_skill.skill_name,
        cv_skill.proficiency_level.value if cv_skill.proficiency_level else None,
        cv_skill.years_of_experience,
        cv_skill.is_primary
    )
    return self._map_skill(row)
```

**`src/adapters/persistence/interview_repository.py`**
```python
async def get_interview_questions(self, interview_id: UUID) -> List[InterviewQuestion]:
    """Fetch questions for interview via junction table"""
    query = """
        SELECT * FROM interview_questions
        WHERE interview_id = $1
        ORDER BY sequence_order
    """
    rows = await self.db.fetch_all(query, interview_id)
    return [self._map_interview_question(row) for row in rows]

async def add_question_to_interview(
    self,
    interview_id: UUID,
    question_id: UUID,
    sequence_order: int
) -> InterviewQuestion:
    """Add question to interview"""
    query = """
        INSERT INTO interview_questions (interview_id, question_id, sequence_order)
        VALUES ($1, $2, $3)
        RETURNING *
    """
    row = await self.db.fetch_one(query, interview_id, question_id, sequence_order)
    return self._map_interview_question(row)

async def get_current_question(self, interview_id: UUID) -> Question | None:
    """Get current question based on interview.current_question_index"""
    query = """
        SELECT q.*
        FROM interviews i
        JOIN interview_questions iq ON iq.interview_id = i.id
        JOIN questions q ON q.id = iq.question_id
        WHERE i.id = $1 AND iq.sequence_order = i.current_question_index
    """
    row = await self.db.fetch_one(query, interview_id)
    return self._map_question(row) if row else None
```

---

### 3. Update API Endpoints

**`src/adapters/api/rest/prompt_template_routes.py`** (NEW)
```python
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import List
from decimal import Decimal

router = APIRouter(prefix="/api/prompts", tags=["prompts"])

class PromptTemplateEditRequest(BaseModel):
    """Request model for editing prompt template"""
    system_prompt: str = Field(..., min_length=10, max_length=5000)
    user_template: str = Field(..., min_length=10, max_length=5000)
    input_variables: List[str] = Field(default_factory=list)
    output_schema: dict
    temperature: Decimal = Field(default=Decimal("0.3"), ge=0, le=2)
    max_tokens: int = Field(default=2000, ge=1, le=100000)
    top_p: Decimal = Field(default=Decimal("0.95"), ge=0, le=1)
    change_summary: str | None = None
    notes: str | None = None

@router.get("/{template_id}")
async def get_prompt_template(template_id: UUID):
    """Get prompt template for editing"""
    template = await prompt_repo.get_by_id(template_id)

    return {
        "id": template.id,
        "name": template.name,
        "version": template.version,
        "system_prompt": template.system_prompt,
        "user_template": template.user_template,
        "input_variables": template.input_variables,
        "output_schema": template.output_schema,
        "temperature": float(template.temperature),
        "max_tokens": template.max_tokens,
        "top_p": float(template.top_p),
        "is_active": template.is_active,
        "is_draft": template.is_draft
    }

@router.patch("/{template_id}")
async def update_prompt_template(
    template_id: UUID,
    request: PromptTemplateEditRequest
):
    """Update prompt template (creates new version)"""
    use_case = UpdatePromptTemplateUseCase(prompt_repo)
    new_version = await use_case.execute(template_id, request, created_by="api_user")

    return {
        "id": new_version.id,
        "version": new_version.version,
        "message": f"Created version {new_version.version} (draft)"
    }

@router.post("/{template_id}/preview")
async def preview_prompt_template(
    template_id: UUID,
    sample_input: dict
):
    """Preview prompt with sample input"""
    use_case = PreviewPromptTemplateUseCase(llm_adapter)
    preview = await use_case.execute(template_id, sample_input)

    return preview

@router.post("/{template_id}/activate")
async def activate_prompt_version(template_id: UUID):
    """Activate prompt version (make it production)"""
    await prompt_repo.activate_version(template_id)

    return {"message": "Version activated"}
```

---

## 🎨 UI Implementation (React)

**Frontend structure:**
```
src/components/PromptEditor/
├── PromptEditor.jsx          # Main editor component
├── SystemPromptField.jsx     # System prompt textarea
├── UserTemplateField.jsx     # User template with variable highlighting
├── VariableDetector.jsx      # Auto-detect {variables}
├── ModelParamsPanel.jsx      # Temperature, max_tokens sliders
├── OutputSchemaBuilder.jsx   # JSON schema editor
├── PreviewPanel.jsx          # Live preview
└── VersionHistory.jsx        # Version comparison
```

See previous React example for implementation details.

---

## ✅ Post-Migration Testing

```bash
# Run unit tests
pytest tests/domain/

# Run integration tests
pytest tests/adapters/persistence/

# Run API tests
pytest tests/adapters/api/

# Test prompt editor
curl -X GET http://localhost:8000/api/prompts/{template_id}
```

---

## 📊 Monitoring

After migration, monitor:

1. **Query performance**:
   ```sql
   SELECT schemaname, tablename, idx_scan, idx_tup_read
   FROM pg_stat_user_indexes
   WHERE tablename IN ('cv_skills', 'interview_questions')
   ORDER BY idx_scan DESC;
   ```

2. **Table sizes**:
   ```sql
   SELECT
       tablename,
       pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
   FROM pg_tables
   WHERE schemaname = 'public'
   ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
   ```

3. **Template_json generation**:
   ```sql
   SELECT
       name,
       version,
       template_json->'template_type' as type,
       jsonb_array_length(template_json->'messages') as message_count
   FROM prompt_templates
   WHERE deleted_at IS NULL
   LIMIT 5;
   ```

---

## 🚨 Troubleshooting

**Issue: Migration fails at ENUM creation**
```bash
# Drop existing ENUMs if they exist
psql -d elios_interview -c "DROP TYPE IF EXISTS question_type_enum CASCADE;"
alembic upgrade head
```

**Issue: Skills migration produces NULL values**
```sql
-- Check original JSONB structure
SELECT id, skills FROM cv_analyses LIMIT 1;

-- Adjust migration SQL if structure differs
```

**Issue: template_json not generating**
```sql
-- Verify columns exist
SELECT column_name, data_type FROM information_schema.columns
WHERE table_name = 'prompt_templates';

-- Manually trigger computation
SELECT template_json FROM prompt_templates LIMIT 1;
```

---

## 📚 Additional Resources

- **LangChain Prompt Templates**: https://python.langchain.com/docs/modules/model_io/prompts/
- **PostgreSQL Generated Columns**: https://www.postgresql.org/docs/current/ddl-generated-columns.html
- **Alembic Migrations**: https://alembic.sqlalchemy.org/en/latest/tutorial.html
