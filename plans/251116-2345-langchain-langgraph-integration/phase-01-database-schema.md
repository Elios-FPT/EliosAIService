# Phase 1 Database Schema: Prompt Management System

**Parent**: [Phase 1: LangChain Adapter](phase-01-langchain-adapter.md)
**Created**: 2025-11-16
**Status**: Approved

---

## Overview

Database schema for UI-editable prompts with versioning, A/B testing, and analytics tracking.

**Goals**:
- ✅ Enable non-technical team to edit prompts via UI
- ✅ Version control for rollback capability
- ✅ A/B testing infrastructure (traffic splitting)
- ✅ Analytics (token usage, latency, success rate per prompt)

---

## Database Schema

### Table 1: `prompt_templates`

Stores prompt template versions with metadata.

```sql
CREATE TABLE prompt_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,  -- e.g., "generate_question", "evaluate_answer"
    version INTEGER NOT NULL,
    template_json JSONB NOT NULL,  -- {"messages": [{"role": "system", "content": "..."}, ...]}

    -- Lifecycle
    is_active BOOLEAN DEFAULT false,
    is_draft BOOLEAN DEFAULT true,

    -- A/B Testing
    ab_test_group VARCHAR(50),  -- NULL, "control", "variant_a", "variant_b"
    traffic_percentage INTEGER DEFAULT 0 CHECK (traffic_percentage BETWEEN 0 AND 100),

    -- Metadata
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    created_by VARCHAR(100),
    notes TEXT,

    -- Analytics (updated by background job)
    total_executions INTEGER DEFAULT 0,
    avg_tokens_used NUMERIC(10, 2),
    avg_latency_ms INTEGER,
    success_rate NUMERIC(5, 4),  -- 0.0000 to 1.0000
    last_analytics_update TIMESTAMP,

    UNIQUE(name, version),
    CHECK (NOT (is_active = true AND is_draft = true))  -- Can't be both active and draft
);

-- Indexes for performance
CREATE INDEX idx_prompts_active ON prompt_templates(name, is_active) WHERE is_active = true;
CREATE INDEX idx_prompts_ab_test ON prompt_templates(name, ab_test_group, traffic_percentage) WHERE ab_test_group IS NOT NULL;
CREATE INDEX idx_prompts_version ON prompt_templates(name, version DESC);
```

**Example Row**:
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "name": "generate_question",
  "version": 3,
  "template_json": {
    "messages": [
      {"role": "system", "content": "You are an expert technical interviewer..."},
      {"role": "user", "content": "Generate a {difficulty} question about {skill}..."}
    ]
  },
  "is_active": true,
  "is_draft": false,
  "ab_test_group": "control",
  "traffic_percentage": 90,
  "created_at": "2025-11-16T10:00:00Z",
  "created_by": "admin@elios.ai",
  "notes": "Optimized for technical questions",
  "total_executions": 1523,
  "avg_tokens_used": 487.5,
  "avg_latency_ms": 1200,
  "success_rate": 0.9523
}
```

---

### Table 2: `prompt_executions`

Tracks every prompt execution for analytics.

```sql
CREATE TABLE prompt_executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prompt_template_id UUID NOT NULL REFERENCES prompt_templates(id) ON DELETE CASCADE,

    -- Context
    interview_id UUID REFERENCES interviews(id) ON DELETE CASCADE,
    candidate_id UUID REFERENCES candidates(id) ON DELETE SET NULL,

    -- Input/Output
    input_variables JSONB NOT NULL,  -- {"skill": "Python", "difficulty": "hard", ...}
    output_text TEXT,

    -- Performance Metrics
    tokens_used INTEGER,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    latency_ms INTEGER NOT NULL,
    model_name VARCHAR(50),  -- "gpt-4", "claude-3-sonnet", etc.

    -- Status
    success BOOLEAN NOT NULL,
    error_message TEXT,

    -- Timestamp
    executed_at TIMESTAMP NOT NULL DEFAULT NOW(),

    INDEX idx_executions_template (prompt_template_id, executed_at DESC),
    INDEX idx_executions_interview (interview_id),
    INDEX idx_executions_success (success, executed_at DESC)
);

-- Partition by month for performance (optional, for high volume)
-- CREATE TABLE prompt_executions_2025_11 PARTITION OF prompt_executions
-- FOR VALUES FROM ('2025-11-01') TO ('2025-12-01');
```

**Example Row**:
```json
{
  "id": "987fcdeb-51a2-43d1-b456-426614174111",
  "prompt_template_id": "123e4567-e89b-12d3-a456-426614174000",
  "interview_id": "abc-123",
  "candidate_id": "def-456",
  "input_variables": {
    "skill": "Python",
    "difficulty": "hard",
    "context": {"experience": 5}
  },
  "output_text": "Explain the Global Interpreter Lock (GIL) in Python...",
  "tokens_used": 523,
  "prompt_tokens": 145,
  "completion_tokens": 378,
  "latency_ms": 1250,
  "model_name": "gpt-4",
  "success": true,
  "error_message": null,
  "executed_at": "2025-11-16T14:30:00Z"
}
```

---

## Migration Script

### Alembic Migration: `0004_create_prompt_management_tables.py`

```python
"""create prompt management tables

Revision ID: 0004
Revises: 0003
Create Date: 2025-11-16

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade():
    # Create prompt_templates table
    op.create_table(
        'prompt_templates',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('template_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column('is_draft', sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column('ab_test_group', sa.String(50), nullable=True),
        sa.Column('traffic_percentage', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(), server_default=sa.func.now(), nullable=False),
        sa.Column('created_by', sa.String(100), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('total_executions', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('avg_tokens_used', sa.Numeric(10, 2), nullable=True),
        sa.Column('avg_latency_ms', sa.Integer(), nullable=True),
        sa.Column('success_rate', sa.Numeric(5, 4), nullable=True),
        sa.Column('last_analytics_update', sa.TIMESTAMP(), nullable=True),
        sa.UniqueConstraint('name', 'version', name='uq_prompt_name_version'),
        sa.CheckConstraint('traffic_percentage >= 0 AND traffic_percentage <= 100', name='chk_traffic_percentage'),
        sa.CheckConstraint('NOT (is_active = true AND is_draft = true)', name='chk_not_active_and_draft')
    )

    # Create indexes
    op.create_index('idx_prompts_active', 'prompt_templates', ['name', 'is_active'],
                    postgresql_where=sa.text('is_active = true'))
    op.create_index('idx_prompts_ab_test', 'prompt_templates', ['name', 'ab_test_group', 'traffic_percentage'],
                    postgresql_where=sa.text('ab_test_group IS NOT NULL'))
    op.create_index('idx_prompts_version', 'prompt_templates', ['name', sa.text('version DESC')])

    # Create prompt_executions table
    op.create_table(
        'prompt_executions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('prompt_template_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('prompt_templates.id', ondelete='CASCADE'), nullable=False),
        sa.Column('interview_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('interviews.id', ondelete='CASCADE'), nullable=True),
        sa.Column('candidate_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('candidates.id', ondelete='SET NULL'), nullable=True),
        sa.Column('input_variables', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('output_text', sa.Text(), nullable=True),
        sa.Column('tokens_used', sa.Integer(), nullable=True),
        sa.Column('prompt_tokens', sa.Integer(), nullable=True),
        sa.Column('completion_tokens', sa.Integer(), nullable=True),
        sa.Column('latency_ms', sa.Integer(), nullable=False),
        sa.Column('model_name', sa.String(50), nullable=True),
        sa.Column('success', sa.Boolean(), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('executed_at', sa.TIMESTAMP(), server_default=sa.func.now(), nullable=False),
    )

    # Create indexes for executions
    op.create_index('idx_executions_template', 'prompt_executions', ['prompt_template_id', sa.text('executed_at DESC')])
    op.create_index('idx_executions_interview', 'prompt_executions', ['interview_id'])
    op.create_index('idx_executions_success', 'prompt_executions', ['success', sa.text('executed_at DESC')])


def downgrade():
    op.drop_table('prompt_executions')
    op.drop_table('prompt_templates')
```

---

## Seed Data: Initial Prompts

### Script: `alembic/versions/0005_seed_initial_prompts.py`

```python
"""seed initial prompts

Revision ID: 0005
Revises: 0004

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import json

revision = '0005'
down_revision = '0004'


def upgrade():
    # Define initial prompts (migrated from openai_adapter.py)
    prompts = [
        {
            "name": "generate_question",
            "version": 1,
            "template_json": {
                "messages": [
                    {"role": "system", "content": "You are an expert technical interviewer specializing in creating challenging, relevant interview questions."},
                    {"role": "user", "content": """Generate a {difficulty} technical question about {skill}.

Context:
- Candidate experience: {experience} years
- Target role: {context}
- Similar questions (for inspiration): {exemplars}

Requirements:
1. Question should test deep understanding, not just syntax
2. Include practical scenarios when possible
3. Be clear and unambiguous
4. Avoid questions that can be easily googled

Output format (JSON):
{
  "question_text": "The interview question",
  "reasoning": "Why this question is appropriate"
}"""}
                ]
            },
            "is_active": True,
            "is_draft": False,
            "ab_test_group": "control",
            "traffic_percentage": 100,
            "created_by": "system",
            "notes": "Initial prompt migrated from OpenAI adapter"
        },
        {
            "name": "evaluate_answer",
            "version": 1,
            "template_json": {
                "messages": [
                    {"role": "system", "content": "You are an expert interviewer evaluating candidate answers."},
                    {"role": "user", "content": """Evaluate the following answer:

Question: {question_text}
Ideal Answer: {ideal_answer}
Candidate Answer: {answer_text}

Provide:
1. Score (0-100): Overall quality
2. Similarity to ideal (0-1): Semantic similarity
3. Strengths: What was good
4. Weaknesses: What was missing
5. Missing concepts: Key concepts not mentioned

Output format (JSON):
{
  "score": 85,
  "similarity_score": 0.82,
  "strengths": ["clear explanation", "good examples"],
  "weaknesses": ["missed edge cases"],
  "missing_concepts": ["concurrency implications"]
}"""}
                ]
            },
            "is_active": True,
            "is_draft": False,
            "created_by": "system"
        }
        # Add more prompts for other LLMPort methods...
    ]

    # Insert prompts
    conn = op.get_bind()
    for prompt in prompts:
        conn.execute(
            sa.text("""
                INSERT INTO prompt_templates (name, version, template_json, is_active, is_draft, ab_test_group, traffic_percentage, created_by, notes)
                VALUES (:name, :version, :template_json, :is_active, :is_draft, :ab_test_group, :traffic_percentage, :created_by, :notes)
            """),
            {
                "name": prompt["name"],
                "version": prompt["version"],
                "template_json": json.dumps(prompt["template_json"]),
                "is_active": prompt["is_active"],
                "is_draft": prompt["is_draft"],
                "ab_test_group": prompt.get("ab_test_group"),
                "traffic_percentage": prompt.get("traffic_percentage", 0),
                "created_by": prompt["created_by"],
                "notes": prompt.get("notes")
            }
        )


def downgrade():
    conn = op.get_bind()
    conn.execute(sa.text("DELETE FROM prompt_templates WHERE created_by = 'system'"))
```

---

## Usage Examples

### Fetching Active Prompt
```python
# In LangChainAdapter
prompt_template = await self.prompt_repo.get_active_prompt("generate_question")
# Returns: ChatPromptTemplate with messages from DB
```

### Logging Execution
```python
# After LLM call
await self.prompt_repo.log_execution(
    prompt_template_id=prompt.id,
    execution=PromptExecution(
        interview_id=interview_id,
        input_variables={"skill": "Python", "difficulty": "hard"},
        output_text=result.question_text,
        tokens_used=response.usage.total_tokens,
        latency_ms=elapsed_ms,
        success=True
    )
)
```

### A/B Testing
```sql
-- Set up A/B test: 90% control, 10% variant
UPDATE prompt_templates SET ab_test_group = 'control', traffic_percentage = 90
WHERE name = 'generate_question' AND version = 3;

UPDATE prompt_templates SET ab_test_group = 'variant_a', traffic_percentage = 10
WHERE name = 'generate_question' AND version = 4;
```

---

## Analytics Queries

### Prompt Performance Comparison
```sql
SELECT
    pt.name,
    pt.version,
    pt.ab_test_group,
    COUNT(pe.id) as executions,
    AVG(pe.tokens_used) as avg_tokens,
    AVG(pe.latency_ms) as avg_latency_ms,
    SUM(CASE WHEN pe.success THEN 1 ELSE 0 END)::float / COUNT(*) as success_rate
FROM prompt_templates pt
LEFT JOIN prompt_executions pe ON pt.id = pe.prompt_template_id
WHERE pt.name = 'generate_question'
  AND pe.executed_at >= NOW() - INTERVAL '7 days'
GROUP BY pt.name, pt.version, pt.ab_test_group
ORDER BY pt.version DESC;
```

### Cost Analysis
```sql
SELECT
    pt.name,
    COUNT(pe.id) as total_calls,
    SUM(pe.tokens_used) as total_tokens,
    SUM(pe.tokens_used) * 0.00003 as estimated_cost_usd  -- GPT-4 pricing
FROM prompt_templates pt
JOIN prompt_executions pe ON pt.id = pe.prompt_template_id
WHERE pe.executed_at >= NOW() - INTERVAL '30 days'
GROUP BY pt.name
ORDER BY estimated_cost_usd DESC;
```

---

## Next Steps

1. Run migration: `alembic upgrade head`
2. Verify tables created: `\dt prompt_*` in psql
3. Run seed: Apply 0005 migration
4. Verify data: `SELECT * FROM prompt_templates;`
5. Implement `PromptRepository` class
6. Build admin UI (Phase 1 optional, can defer)

---

**Status**: Ready for implementation
**Migration Files**: 2 (0004_create_tables, 0005_seed_data)
**Schema Version**: Compatible with PostgreSQL 12+
