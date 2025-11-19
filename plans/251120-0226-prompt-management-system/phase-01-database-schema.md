# Phase 1: Database Schema & Migrations

**Parent**: [Implementation Plan](./plan.md)
**Created**: 2025-11-20
**Duration**: 3-4 days
**Priority**: Critical
**Status**: ✅ Complete

---

## Overview

Create PostgreSQL database schema for prompt version control with 3 tables and 1 materialized view. Includes 4 Alembic migration scripts with seed data.

**Goals**:
- ✅ Immutable version tracking (append-only `prompt_templates`)
- ✅ Metadata audit trail (`prompt_metadata_changes`)
- ✅ Execution analytics (`prompt_executions`)
- ✅ Aggregated metrics (`prompt_analytics_summary` view)

---

## Database Schema

### Table 1: `prompt_templates`

**Purpose**: Store immutable prompt versions with A/B testing metadata.

```sql
CREATE TABLE prompt_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    version INTEGER NOT NULL,
    parent_version_id UUID REFERENCES prompt_templates(id) ON DELETE SET NULL,
    change_summary TEXT,
    template_json JSONB NOT NULL,
    is_active BOOLEAN DEFAULT false,
    is_draft BOOLEAN DEFAULT true,
    ab_test_group VARCHAR(50),
    traffic_percentage INTEGER DEFAULT 0 CHECK (traffic_percentage BETWEEN 0 AND 100),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    created_by VARCHAR(100),
    notes TEXT,
    UNIQUE(name, version),
    CHECK (NOT (is_active = true AND is_draft = true))
);

-- Indexes
CREATE INDEX idx_prompt_templates_name ON prompt_templates(name);
CREATE INDEX idx_prompt_templates_active ON prompt_templates(is_active) WHERE is_active = true;
CREATE INDEX idx_prompt_templates_version ON prompt_templates(name, version);
CREATE INDEX idx_prompt_templates_parent ON prompt_templates(parent_version_id);
CREATE INDEX idx_prompt_templates_ab_test ON prompt_templates(ab_test_group) WHERE ab_test_group IS NOT NULL;
```

**Fields**:
- `id` - UUID primary key
- `name` - Prompt identifier (e.g., "question_generation", "answer_evaluation")
- `version` - Auto-incremented integer within name scope
- `parent_version_id` - Lineage tracking for version ancestry
- `change_summary` - Human-readable change description
- `template_json` - Full prompt content (immutable)
  - Structure: `{"system": str, "user_template": str, "variables": list[str], "constraints": str}`
- `is_active` - Currently deployed version (only 1 active per name)
- `is_draft` - Draft vs production status
- `ab_test_group` - A/B test group identifier (e.g., "control", "variant_a")
- `traffic_percentage` - % of traffic for this version (0-100)
- `created_at` - Immutable timestamp
- `created_by` - User identifier (e.g., "admin", "system")
- `notes` - Additional metadata

**Constraints**:
- UNIQUE(name, version) - Prevent duplicate versions
- CHECK - Prevent active drafts
- CHECK - traffic_percentage 0-100

---

### Table 2: `prompt_metadata_changes`

**Purpose**: Audit log for non-content metadata changes.

```sql
CREATE TABLE prompt_metadata_changes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prompt_template_id UUID NOT NULL REFERENCES prompt_templates(id) ON DELETE CASCADE,
    field_name VARCHAR(50) NOT NULL,
    old_value TEXT,
    new_value TEXT,
    changed_by VARCHAR(100) NOT NULL,
    changed_at TIMESTAMP NOT NULL DEFAULT NOW(),
    reason TEXT
);

-- Indexes
CREATE INDEX idx_prompt_metadata_changes_template ON prompt_metadata_changes(prompt_template_id, changed_at);
CREATE INDEX idx_prompt_metadata_changes_field ON prompt_metadata_changes(field_name, changed_at);
```

**Fields**:
- `id` - UUID primary key
- `prompt_template_id` - Foreign key to prompt_templates
- `field_name` - Changed field (e.g., "is_active", "traffic_percentage", "ab_test_group")
- `old_value`, `new_value` - TEXT (serialized from any type)
- `changed_by` - User identifier
- `changed_at` - Change timestamp
- `reason` - Why change made

**What gets logged**:
- Activation/deactivation (`is_active`)
- Traffic adjustments (`traffic_percentage`)
- A/B test group changes (`ab_test_group`)
- Draft → production promotion (`is_draft`)
- NOT logged: Version creation (tracked by `prompt_templates.created_at`)

---

### Table 3: `prompt_executions`

**Purpose**: Track every LLM call for analytics.

```sql
CREATE TABLE prompt_executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prompt_template_id UUID NOT NULL REFERENCES prompt_templates(id) ON DELETE CASCADE,
    interview_id UUID REFERENCES interviews(id) ON DELETE CASCADE,
    candidate_id UUID REFERENCES candidates(id) ON DELETE SET NULL,
    input_variables JSONB NOT NULL,
    output_text TEXT,
    tokens_used INTEGER,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    latency_ms INTEGER NOT NULL,
    model_name VARCHAR(50),
    success BOOLEAN NOT NULL,
    error_message TEXT,
    executed_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_prompt_executions_template ON prompt_executions(prompt_template_id, executed_at);
CREATE INDEX idx_prompt_executions_interview ON prompt_executions(interview_id);
CREATE INDEX idx_prompt_executions_success ON prompt_executions(success, executed_at);
CREATE INDEX idx_prompt_executions_model ON prompt_executions(model_name, executed_at);
```

**Fields**:
- `id` - UUID primary key
- `prompt_template_id` - Which version executed
- `interview_id` - Context (nullable for non-interview executions)
- `candidate_id` - Context (nullable)
- `input_variables` - JSONB (e.g., `{"skill": "Python", "difficulty": "medium"}`)
- `output_text` - LLM response (truncated if >10k chars)
- `tokens_used` - Total tokens (fallback if prompt/completion missing)
- `prompt_tokens`, `completion_tokens` - OpenAI API response
- `latency_ms` - Execution time (milliseconds)
- `model_name` - LLM model identifier (e.g., "gpt-4")
- `success` - Boolean execution status
- `error_message` - Error details (if failed)
- `executed_at` - Execution timestamp

**Integration Point**: LLM adapters (`OpenAIAdapter`, `LangChainAdapter`) log executions after every call.

---

### Materialized View: `prompt_analytics_summary`

**Purpose**: Aggregated performance metrics per prompt version.

```sql
CREATE MATERIALIZED VIEW prompt_analytics_summary AS
SELECT
    pt.id AS prompt_template_id,
    pt.name,
    pt.version,
    pt.ab_test_group,
    COUNT(pe.id) AS total_executions,
    AVG(pe.tokens_used) AS avg_tokens_used,
    AVG(pe.latency_ms) AS avg_latency_ms,
    SUM(CASE WHEN pe.success THEN 1 ELSE 0 END)::FLOAT / COUNT(pe.id) AS success_rate,
    -- Cost calculation (OpenAI gpt-4 pricing: $0.03/1k prompt, $0.06/1k completion)
    SUM(
        (COALESCE(pe.prompt_tokens, 0) * 0.03 / 1000.0) +
        (COALESCE(pe.completion_tokens, 0) * 0.06 / 1000.0)
    ) AS estimated_cost_usd,
    MAX(pe.executed_at) AS last_executed_at
FROM prompt_templates pt
LEFT JOIN prompt_executions pe ON pt.id = pe.prompt_template_id
GROUP BY pt.id, pt.name, pt.version, pt.ab_test_group;

-- Indexes on view
CREATE UNIQUE INDEX idx_analytics_summary_template_id ON prompt_analytics_summary(prompt_template_id);
CREATE INDEX idx_analytics_summary_name ON prompt_analytics_summary(name, version);
```

**Refresh Strategy**: Background job every 5 minutes (Phase 5)

---

## Migration Scripts

### Migration 1: Core Tables

**File**: `alembic/versions/0010_create_prompt_tables.py`

**Content**: Create `prompt_templates` and `prompt_metadata_changes` tables with indexes.

### Migration 2: Analytics Table

**File**: `alembic/versions/0011_create_prompt_executions.py`

**Content**: Create `prompt_executions` table with indexes.

### Migration 3: Analytics View

**File**: `alembic/versions/0012_create_prompt_analytics_view.py`

**Content**: Create `prompt_analytics_summary` materialized view.

### Migration 4: Seed Data

**File**: `alembic/versions/0013_seed_initial_prompts.py`

**Content**: Seed 7 initial prompts from `openai_adapter.py`:

1. `question_generation` (v1) - Verbal-only constraints
2. `answer_evaluation` (v1)
3. `ideal_answer_generation` (v1)
4. `rationale_generation` (v1)
5. `gap_detection` (v1)
6. `follow_up_generation` (v1)
7. `feedback_report` (v1)

**Seed Pattern**:
```python
def upgrade() -> None:
    """Seed initial prompt templates."""
    prompts = [
        {
            "name": "question_generation",
            "version": 1,
            "template_json": {
                "system": "You are an AI interview question generator...",
                "user_template": "Generate question for skill: {skill}...",
                "variables": ["skill", "difficulty", "cv_summary", "exemplars"],
                "constraints": "VERBAL ONLY - no code/diagrams/whiteboard..."
            },
            "is_active": True,
            "is_draft": False,
            "created_by": "system",
            "notes": "Initial prompt migrated from openai_adapter.py"
        },
        # ... other 6 prompts
    ]

    for prompt in prompts:
        op.execute(
            prompt_templates.insert().values(**prompt)
        )
```

---

## Implementation Steps

### Step 1: Create Migration 0010 (Core Tables)
**Duration**: 1-2 hours

```bash
alembic revision --autogenerate -m "create prompt tables"
```

- [ ] Add `prompt_templates` table creation
- [ ] Add `prompt_metadata_changes` table creation
- [ ] Add all indexes
- [ ] Add constraints (UNIQUE, CHECK)
- [ ] Test upgrade: `alembic upgrade head`
- [ ] Test downgrade: `alembic downgrade -1`

### Step 2: Create Migration 0011 (Analytics Table)
**Duration**: 1 hour

```bash
alembic revision --autogenerate -m "create prompt executions"
```

- [ ] Add `prompt_executions` table creation
- [ ] Add foreign keys to `interviews`, `candidates`
- [ ] Add indexes (template, interview, success, model)
- [ ] Test upgrade/downgrade

### Step 3: Create Migration 0012 (Materialized View)
**Duration**: 1 hour

```bash
alembic revision -m "create prompt analytics view"
```

- [ ] Add materialized view creation SQL
- [ ] Add indexes on view
- [ ] Test view creation
- [ ] Verify aggregation query performance

### Step 4: Create Migration 0013 (Seed Data)
**Duration**: 2-3 hours

```bash
alembic revision -m "seed initial prompts"
```

- [ ] Extract prompts from `openai_adapter.py`
- [ ] Convert to seed data format
- [ ] Insert 7 prompts
- [ ] Test seed migration
- [ ] Verify data: `SELECT * FROM prompt_templates;`

### Step 5: Verification
**Duration**: 1-2 hours

```bash
# Run all migrations
alembic upgrade head

# Verify tables created
psql -c "\dt prompt_*"

# Verify indexes
psql -c "\di prompt_*"

# Verify materialized view
psql -c "\d+ prompt_analytics_summary"

# Check seed data
psql -c "SELECT name, version, is_active FROM prompt_templates ORDER BY name, version;"
```

**Expected Output**: 7 prompts seeded, all active, version 1

---

## Testing

### Unit Tests
None for this phase (schema only).

### Integration Tests

**File**: `tests/integration/test_prompt_schema.py`

```python
async def test_prompt_templates_table_exists(db_session):
    """Verify prompt_templates table exists with correct schema."""
    result = await db_session.execute(
        text("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'prompt_templates'")
    )
    columns = {row[0]: row[1] for row in result}

    assert "id" in columns
    assert "name" in columns
    assert "version" in columns
    assert "template_json" in columns
    assert columns["template_json"] == "jsonb"

async def test_unique_constraint_name_version(db_session):
    """Verify UNIQUE(name, version) constraint."""
    # Insert v1
    await db_session.execute(
        prompt_templates.insert().values(name="test", version=1, template_json={})
    )

    # Try duplicate → should fail
    with pytest.raises(IntegrityError):
        await db_session.execute(
            prompt_templates.insert().values(name="test", version=1, template_json={})
        )
```

---

## Success Criteria

- ✅ All 4 migrations run without errors
- ✅ Tables created with correct schema
- ✅ Indexes created (verify with `\di`)
- ✅ Materialized view queryable
- ✅ Seed data inserted (7 prompts)
- ✅ Constraints enforced (UNIQUE, CHECK)
- ✅ Foreign keys working

---

## Rollback Plan

```bash
# Rollback all migrations
alembic downgrade -4

# Verify tables dropped
psql -c "\dt prompt_*"
```

---

## Related Files

**New Files**:
- `alembic/versions/0010_create_prompt_tables.py`
- `alembic/versions/0011_create_prompt_executions.py`
- `alembic/versions/0012_create_prompt_analytics_view.py`
- `alembic/versions/0013_seed_initial_prompts.py`

**Modified Files**:
- None

---

## Next Phase

→ [Phase 2: Domain Models](./phase-02-domain-models.md)

**Blockers**: None (can start immediately)

---

## Notes

- Use `gen_random_uuid()` for UUID generation (built-in PostgreSQL)
- Materialized view refresh configured in Phase 5
- Seed prompts extracted from existing `openai_adapter.py` hardcoded prompts
- Cost calculation uses OpenAI gpt-4 pricing (update if provider changes)

---

**Phase Status**: Ready to implement
**Last Updated**: 2025-11-20
