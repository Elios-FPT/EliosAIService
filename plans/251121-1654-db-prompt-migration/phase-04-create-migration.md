# Phase 4: Create Migration 0014 - Seed Missing Prompts

**Phase ID**: 04
**Plan**: 251121-1654-db-prompt-migration
**Estimated Effort**: 1 hour
**Complexity**: LOW
**Status**: PENDING
**Depends On**: None (can run in parallel with Phases 1-3)

---

## Objective

Create Alembic migration 0014 to seed 3 missing DB prompts required for complete LangChainAdapter migration:
- `cv_summary`
- `skill_extraction`
- `interview_recommendations`

**Principle Applied**: KISS - Extract existing prompts from PROMPT_REGISTRY, no modifications

---

## Missing Prompts Analysis

### Prompt 1: cv_summary

**Source**: `src/adapters/llm/prompts/__init__.py` - SUMMARIZE_CV_PROMPT (lines 219-237)
**Used By**: `summarize_cv()` method (line 226)
**Purpose**: Generate professional CV summary (100-200 words)

**Prompt Structure**:
```python
SUMMARIZE_CV_PROMPT = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_CV_ANALYZER),
    ("human", """Summarize this CV concisely.

CV Text:
{cv_text}

Create a professional summary (100-200 words) highlighting:
- Years of experience (estimate if not explicit)
- Key technical skills
- Notable projects or achievements
- Education background

Return in JSON format:
{{
    "summary_text": "summary here (100-200 words)",
    "years_experience": 5
}}""")
])
```

**Variables**: `cv_text`
**Constraints**: 100-200 words, JSON output, estimate experience

---

### Prompt 2: skill_extraction

**Source**: `src/adapters/llm/prompts/__init__.py` - EXTRACT_SKILLS_PROMPT (lines 241-266)
**Used By**: `extract_skills_from_text()` method (line 237)
**Purpose**: Extract structured skills from CV text

**Prompt Structure**:
```python
EXTRACT_SKILLS_PROMPT = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_CV_ANALYZER),
    ("human", """Extract technical skills from this text.

Text:
{text}

Identify:
- Programming languages
- Frameworks and libraries
- Databases and tools
- Methodologies and practices

For each skill, provide:
- name: skill name
- category: type of skill (e.g., "programming", "framework", "database")
- proficiency: level if mentioned (e.g., "beginner", "intermediate", "expert")

Return in JSON format:
{{
    "skills": [
        {{"name": "Python", "category": "programming", "proficiency": "expert"}},
        {{"name": "FastAPI", "category": "framework", "proficiency": "intermediate"}}
    ]
}}""")
])
```

**Variables**: `text`
**Constraints**: JSON output with structured skills array

---

### Prompt 3: interview_recommendations

**Source**: `src/adapters/llm/prompts/__init__.py` - RECOMMENDATIONS_PROMPT (lines 270-293)
**Used By**: `generate_interview_recommendations()` method (line 412)
**Purpose**: Generate personalized interview feedback with study recommendations

**Prompt Structure**:
```python
RECOMMENDATIONS_PROMPT = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_EVALUATOR),
    ("human", """Generate personalized interview recommendations.

Interview Context:
- Interview ID: {interview_id}
- Total Answers: {total_answers}
- Gap Progression: {gap_progression}
- Evaluations: {evaluations}

Provide:
1. Top 3-5 strengths demonstrated
2. Top 3-5 weaknesses to address
3. Specific study topics (be concrete)
4. Interview technique tips (voice, pacing, structure)

Return in JSON format:
{{
    "strengths": ["strength 1", "strength 2", ...],
    "weaknesses": ["weakness 1", "weakness 2", ...],
    "study_topics": ["topic 1", "topic 2", ...],
    "technique_tips": ["tip 1", "tip 2", ...]
}}""")
])
```

**Variables**: `interview_id`, `total_answers`, `gap_progression`, `evaluations`
**Constraints**: JSON output, 3-7 items per category

---

## Migration File Structure

**File**: `alembic/versions/0014_251121_seed_missing_prompts.py`
**Revises**: `0013_251120_seed_initial_prompts`
**Date**: 2025-11-21

### Migration Template

```python
"""seed missing prompts for LangChain adapter

Revision ID: 0014_251121_seed_missing_prompts
Revises: 0013_251120_seed_initial_prompts
Create Date: 2025-11-21

Seeds 3 prompts required for complete LangChainAdapter DB migration:
- cv_summary (SUMMARIZE_CV_PROMPT)
- skill_extraction (EXTRACT_SKILLS_PROMPT)
- interview_recommendations (RECOMMENDATIONS_PROMPT)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import json

# revision identifiers, used by Alembic.
revision = '0014'
down_revision = '0013'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Seed 3 missing prompt templates."""

    prompts = [
        {
            "name": "cv_summary",
            "version": 1,
            "template_json": json.dumps({
                "system": "You are an expert HR professional and technical recruiter analyzing candidate CVs.\nExtract relevant information accurately and professionally.",
                "user_template": """Summarize this CV concisely.

CV Text:
{cv_text}

Create a professional summary (100-200 words) highlighting:
- Years of experience (estimate if not explicit)
- Key technical skills
- Notable projects or achievements
- Education background

Return in JSON format:
{{
    "summary_text": "summary here (100-200 words)",
    "years_experience": 5
}}""",
                "variables": ["cv_text"],
                "constraints": "100-200 words. JSON output. Estimate years_experience if not explicit in CV."
            }),
            "is_active": True,
            "is_draft": False,
            "created_by": "system",
            "notes": "Migrated from SUMMARIZE_CV_PROMPT in prompts/__init__.py"
        },
        {
            "name": "skill_extraction",
            "version": 1,
            "template_json": json.dumps({
                "system": "You are an expert HR professional and technical recruiter analyzing candidate CVs.\nExtract relevant information accurately and professionally.",
                "user_template": """Extract technical skills from this text.

Text:
{text}

Identify:
- Programming languages
- Frameworks and libraries
- Databases and tools
- Methodologies and practices

For each skill, provide:
- name: skill name
- category: type of skill (e.g., "programming", "framework", "database")
- proficiency: level if mentioned (e.g., "beginner", "intermediate", "expert")

Return in JSON format:
{{
    "skills": [
        {{"name": "Python", "category": "programming", "proficiency": "expert"}},
        {{"name": "FastAPI", "category": "framework", "proficiency": "intermediate"}}
    ]
}}""",
                "variables": ["text"],
                "constraints": "JSON output. Extract all technical skills mentioned. Infer proficiency from context (years, project complexity)."
            }),
            "is_active": True,
            "is_draft": False,
            "created_by": "system",
            "notes": "Migrated from EXTRACT_SKILLS_PROMPT in prompts/__init__.py"
        },
        {
            "name": "interview_recommendations",
            "version": 1,
            "template_json": json.dumps({
                "system": "You are an expert technical interviewer evaluating candidate answers.\nProvide objective, constructive feedback with specific scores.",
                "user_template": """Generate personalized interview recommendations.

Interview Context:
- Interview ID: {interview_id}
- Total Answers: {total_answers}
- Gap Progression: {gap_progression}
- Evaluations: {evaluations}

Provide:
1. Top 3-5 strengths demonstrated
2. Top 3-5 weaknesses to address
3. Specific study topics (be concrete)
4. Interview technique tips (voice, pacing, structure)

Return in JSON format:
{{
    "strengths": ["strength 1", "strength 2", ...],
    "weaknesses": ["weakness 1", "weakness 2", ...],
    "study_topics": ["topic 1", "topic 2", ...],
    "technique_tips": ["tip 1", "tip 2", ...]
}}""",
                "variables": ["interview_id", "total_answers", "gap_progression", "evaluations"],
                "constraints": "JSON output. 3-5 strengths/weaknesses, 3-7 study topics, 2-5 technique tips. Be specific (not generic advice)."
            }),
            "is_active": True,
            "is_draft": False,
            "created_by": "system",
            "notes": "Migrated from RECOMMENDATIONS_PROMPT in prompts/__init__.py"
        }
    ]

    # Get database connection
    connection = op.get_bind()

    # Insert prompts
    for prompt in prompts:
        connection.execute(
            sa.text("""
                INSERT INTO prompt_templates
                (name, version, template_json, is_active, is_draft, created_by, notes)
                VALUES
                (:name, :version, CAST(:template_json AS jsonb), :is_active, :is_draft, :created_by, :notes)
            """),
            {
                "name": prompt["name"],
                "version": prompt["version"],
                "template_json": prompt["template_json"],
                "is_active": prompt["is_active"],
                "is_draft": prompt["is_draft"],
                "created_by": prompt["created_by"],
                "notes": prompt["notes"]
            }
        )


def downgrade() -> None:
    """Remove seeded prompt templates."""

    connection = op.get_bind()
    connection.execute(
        sa.text("""
            DELETE FROM prompt_templates
            WHERE created_by = 'system'
            AND version = 1
            AND name IN (
                'cv_summary',
                'skill_extraction',
                'interview_recommendations'
            )
        """)
    )
```

---

## Validation Steps

### Step 1: Validate JSON Structure

Run JSON validation before migration:

```python
# scripts/validate_prompt_templates.py
import json

def validate_prompt_template(template_json: dict) -> list[str]:
    """Validate prompt template JSON structure.

    Returns list of validation errors (empty if valid).
    """
    errors = []

    # Required keys
    required_keys = ["system", "user_template", "variables"]
    for key in required_keys:
        if key not in template_json:
            errors.append(f"Missing required key: {key}")

    # Variables must be list
    if "variables" in template_json and not isinstance(template_json["variables"], list):
        errors.append("'variables' must be a list")

    # Check user_template contains all variables
    if "user_template" in template_json and "variables" in template_json:
        user_template = template_json["user_template"]
        for var in template_json["variables"]:
            if f"{{{var}}}" not in user_template:
                errors.append(f"Variable '{var}' not found in user_template")

    return errors


# Test migration prompts
prompts_to_test = [
    # cv_summary, skill_extraction, interview_recommendations
    # ... (copy from migration)
]

for prompt in prompts_to_test:
    template_json = json.loads(prompt["template_json"])
    errors = validate_prompt_template(template_json)
    if errors:
        print(f"❌ {prompt['name']}: {errors}")
    else:
        print(f"✅ {prompt['name']}: Valid")
```

---

### Step 2: Test Migration Locally

```bash
# Create test database
createdb elios_test_migration

# Point to test DB
export DATABASE_URL="postgresql://user:pass@localhost:5432/elios_test_migration"

# Run migrations up to 0013
alembic upgrade 0013

# Verify 7 prompts exist
psql -d elios_test_migration -c "SELECT name, version FROM prompt_templates ORDER BY name;"

# Run migration 0014
alembic upgrade head

# Verify 10 prompts exist (7 + 3 new)
psql -d elios_test_migration -c "SELECT name, version FROM prompt_templates ORDER BY name;"

# Test downgrade
alembic downgrade -1

# Verify 7 prompts remain (3 removed)
psql -d elios_test_migration -c "SELECT name, version FROM prompt_templates ORDER BY name;"

# Cleanup
dropdb elios_test_migration
```

---

### Step 3: Verify Prompt Activation

```python
# scripts/test_new_prompts.py
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from src.adapters.persistence.postgres_prompt_repository import PostgreSQLPromptRepository

async def test_new_prompts():
    """Test new prompts are active and retrievable."""
    engine = create_async_engine("postgresql+asyncpg://...")
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        repo = PostgreSQLPromptRepository(session)

        # Test each new prompt
        new_prompts = ["cv_summary", "skill_extraction", "interview_recommendations"]

        for prompt_name in new_prompts:
            prompt = await repo.get_active_prompt(prompt_name)

            if not prompt:
                print(f"❌ {prompt_name}: Not found or not active")
            elif prompt.version != 1:
                print(f"⚠️ {prompt_name}: Expected v1, got v{prompt.version}")
            else:
                print(f"✅ {prompt_name}: Active (v{prompt.version})")

                # Validate template structure
                required_keys = {"system", "user_template", "variables"}
                missing = required_keys - set(prompt.template_json.keys())
                if missing:
                    print(f"   ❌ Missing keys: {missing}")
                else:
                    print(f"   ✅ Template valid")

asyncio.run(test_new_prompts())
```

---

## Integration with LangChainAdapter

### Test Usage After Migration

```python
# Test summarize_cv with DB prompt
async def test_summarize_cv_db_prompt():
    """Test summarize_cv loads cv_summary from DB."""
    from src.adapters.llm.langchain_adapter import LangChainAdapter
    from src.adapters.persistence.postgres_prompt_repository import PostgreSQLPromptRepository

    # Setup
    engine = create_async_engine(...)
    async with async_session() as session:
        prompt_repo = PostgreSQLPromptRepository(session)
        adapter = LangChainAdapter(
            model=ChatOpenAI(model="gpt-3.5-turbo"),
            prompt_repository=prompt_repo
        )

        # Execute (should load from DB)
        cv_text = "John Doe, 5 years Python developer..."
        summary = await adapter.summarize_cv(cv_text, context={"candidate_id": "123"})

        print(f"Summary: {summary}")

        # Verify execution logged
        analytics = await prompt_repo.get_analytics_summary("cv_summary")
        assert analytics["total_executions"] >= 1
        print(f"✅ Execution logged: {analytics['total_executions']} total")
```

---

## Rollback Plan

### Scenario 1: Migration Fails

**Error**: Duplicate key violation (prompt already exists)

**Cause**: Manual testing created prompts before migration

**Solution**:
```sql
-- Check for existing prompts
SELECT name, version, created_by FROM prompt_templates
WHERE name IN ('cv_summary', 'skill_extraction', 'interview_recommendations');

-- If found, delete manually created prompts
DELETE FROM prompt_templates
WHERE name IN ('cv_summary', 'skill_extraction', 'interview_recommendations')
AND created_by != 'system';

-- Re-run migration
alembic upgrade head
```

### Scenario 2: Invalid JSON

**Error**: JSON validation fails in PostgreSQL

**Cause**: Malformed template_json

**Solution**:
1. Fix JSON in migration file (validate with `scripts/validate_prompt_templates.py`)
2. Downgrade: `alembic downgrade -1`
3. Edit migration file
4. Upgrade: `alembic upgrade head`

### Scenario 3: Prompts Not Activating

**Error**: `get_active_prompt()` returns None

**Cause**: `is_active=False` or `is_draft=True`

**Solution**:
```sql
-- Check activation status
SELECT name, version, is_active, is_draft FROM prompt_templates
WHERE name IN ('cv_summary', 'skill_extraction', 'interview_recommendations');

-- Activate if needed
UPDATE prompt_templates
SET is_active = TRUE, is_draft = FALSE
WHERE name IN ('cv_summary', 'skill_extraction', 'interview_recommendations')
AND version = 1;
```

---

## Testing Requirements

### Pre-Migration Tests

#### Test 1: Validate JSON Structure
```bash
python scripts/validate_prompt_templates.py
# Expected: All 3 prompts valid ✅
```

#### Test 2: Test on Isolated DB
```bash
# Create test DB, run migration, verify count
# See "Step 2: Test Migration Locally" above
```

### Post-Migration Tests

#### Test 3: Verify Activation
```bash
python scripts/test_new_prompts.py
# Expected: All 3 prompts active ✅
```

#### Test 4: Test LangChainAdapter Integration
```python
# Run tests/integration/test_langchain_adapter_db_integration.py
pytest tests/integration/test_langchain_adapter_db_integration.py::test_new_prompts
```

---

## Acceptance Criteria

### Functional
- [ ] Migration 0014 runs without errors
- [ ] 3 new prompts inserted with `version=1`, `is_active=True`, `is_draft=False`
- [ ] Total prompts in DB: 10 (7 from 0013 + 3 new)
- [ ] Downgrade removes 3 prompts cleanly (7 remain)

### Validation
- [ ] JSON structure validated (all required keys present)
- [ ] Variables match placeholders in user_template
- [ ] No SQL errors (duplicate keys, invalid JSON)

### Integration
- [ ] `get_active_prompt()` returns prompts successfully
- [ ] LangChainAdapter methods use DB prompts (not fallback)
- [ ] Execution logging tracks usage

---

## Files Created/Modified

```
alembic/versions/0014_251121_seed_missing_prompts.py (NEW)
  - Migration file

scripts/validate_prompt_templates.py (NEW)
  - JSON validation script

scripts/test_new_prompts.py (NEW)
  - Integration test script

tests/integration/test_langchain_adapter_db_integration.py (MODIFY)
  - Add tests for new prompts
```

---

## Next Phase

**Phase 5**: [Update Tests](./phase-05-update-tests.md)

Create comprehensive unit and integration tests for DB-driven prompt loading, fallback behavior, and execution logging.

---

**END OF PHASE 4**
