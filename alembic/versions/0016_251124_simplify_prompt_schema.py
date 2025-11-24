"""simplify prompt schema

Revision ID: 0016
Revises: 0015
Create Date: 2025-11-24

Changes:
- Remove unused fields: template_json_legacy, ab_test_group, traffic_percentage, notes
- Remove reason from prompt_metadata_changes
- Remove candidate_id, tokens_used from prompt_executions
- Update prompt_analytics_summary view (remove ab_test_group, avg_tokens_used; add avg_prompt_tokens, avg_completion_tokens)
- Remove constraint ck_prompt_templates_traffic_percentage
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0016'
down_revision: Union[str, None] = '0015'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Simplify prompt schema by removing unused fields."""

    # Step 1: Drop materialized view (indexes auto-dropped)
    op.execute("DROP MATERIALIZED VIEW IF EXISTS prompt_analytics_summary")

    # Step 2: Remove constraint BEFORE dropping column (constraint is auto-dropped with column)
    # Use IF EXISTS to handle case where constraint might not exist
    op.execute("""
        ALTER TABLE prompt_templates
        DROP CONSTRAINT IF EXISTS ck_prompt_templates_traffic_percentage
    """)

    # Step 3: Remove columns from prompt_templates
    op.drop_column('prompt_templates', 'template_json_legacy')
    op.drop_column('prompt_templates', 'ab_test_group')
    op.drop_column('prompt_templates', 'traffic_percentage')
    op.drop_column('prompt_templates', 'notes')

    # Step 4: Drop index on ab_test_group (if exists)
    op.drop_index('idx_prompt_templates_ab_test', table_name='prompt_templates', if_exists=True)

    # Step 5: Remove columns from prompt_metadata_changes
    op.drop_column('prompt_metadata_changes', 'reason')

    # Step 6: Remove columns from prompt_executions
    # Drop foreign key constraint (PostgreSQL auto-names it as prompt_executions_candidate_id_fkey)
    op.execute("""
        ALTER TABLE prompt_executions
        DROP CONSTRAINT IF EXISTS prompt_executions_candidate_id_fkey
    """)
    op.drop_column('prompt_executions', 'candidate_id')
    op.drop_column('prompt_executions', 'tokens_used')

    # Step 7: Recreate analytics view with updated structure
    op.execute("""
        CREATE MATERIALIZED VIEW prompt_analytics_summary AS
        SELECT
            pt.id AS prompt_template_id,
            pt.name,
            pt.version,
            COUNT(pe.id) AS total_executions,
            AVG(pe.prompt_tokens) AS avg_prompt_tokens,
            AVG(pe.completion_tokens) AS avg_completion_tokens,
            AVG(pe.latency_ms) AS avg_latency_ms,
            CASE
                WHEN COUNT(pe.id) > 0 THEN
                    SUM(CASE WHEN pe.success THEN 1 ELSE 0 END)::FLOAT / COUNT(pe.id)
                ELSE 0
            END AS success_rate,
            -- Cost calculation (OpenAI gpt-4 pricing: $0.03/1k prompt, $0.06/1k completion)
            SUM(
                (COALESCE(pe.prompt_tokens, 0) * 0.03 / 1000.0) +
                (COALESCE(pe.completion_tokens, 0) * 0.06 / 1000.0)
            ) AS estimated_cost_usd,
            MAX(pe.executed_at) AS last_executed_at
        FROM prompt_templates pt
        LEFT JOIN prompt_executions pe ON pt.id = pe.prompt_template_id
        GROUP BY pt.id, pt.name, pt.version
    """)

    # Step 8: Recreate indexes on view
    op.execute("""
        CREATE UNIQUE INDEX idx_analytics_summary_template_id
        ON prompt_analytics_summary(prompt_template_id)
    """)

    op.execute("""
        CREATE INDEX idx_analytics_summary_name
        ON prompt_analytics_summary(name, version)
    """)


def downgrade() -> None:
    """Revert schema simplification."""

    # Drop materialized view
    op.execute("DROP MATERIALIZED VIEW IF EXISTS prompt_analytics_summary")

    # Recreate columns in prompt_executions
    op.add_column('prompt_executions', sa.Column('tokens_used', sa.Integer(), nullable=True))
    op.add_column('prompt_executions', sa.Column('candidate_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key('fk_prompt_executions_candidate_id', 'prompt_executions', 'candidates', ['candidate_id'], ['id'], ondelete='SET NULL')

    # Recreate columns in prompt_metadata_changes
    op.add_column('prompt_metadata_changes', sa.Column('reason', sa.Text(), nullable=True))

    # Recreate columns in prompt_templates
    op.add_column('prompt_templates', sa.Column('notes', sa.Text(), nullable=True))
    op.add_column('prompt_templates', sa.Column('traffic_percentage', sa.Integer(), server_default=sa.text('0'), nullable=False))
    op.add_column('prompt_templates', sa.Column('ab_test_group', sa.String(50), nullable=True))
    op.add_column('prompt_templates', sa.Column('template_json_legacy', postgresql.JSONB(), nullable=True))

    # Recreate constraint
    op.create_check_constraint('ck_prompt_templates_traffic_percentage', 'prompt_templates',
                               'traffic_percentage >= 0 AND traffic_percentage <= 100')

    # Recreate index
    op.create_index('idx_prompt_templates_ab_test', 'prompt_templates', ['ab_test_group'],
                    postgresql_where=sa.text('ab_test_group IS NOT NULL'))

    # Recreate analytics view with old structure
    op.execute("""
        CREATE MATERIALIZED VIEW prompt_analytics_summary AS
        SELECT
            pt.id AS prompt_template_id,
            pt.name,
            pt.version,
            pt.ab_test_group,
            COUNT(pe.id) AS total_executions,
            AVG(pe.tokens_used) AS avg_tokens_used,
            AVG(pe.latency_ms) AS avg_latency_ms,
            CASE
                WHEN COUNT(pe.id) > 0 THEN
                    SUM(CASE WHEN pe.success THEN 1 ELSE 0 END)::FLOAT / COUNT(pe.id)
                ELSE 0
            END AS success_rate,
            SUM(
                (COALESCE(pe.prompt_tokens, 0) * 0.03 / 1000.0) +
                (COALESCE(pe.completion_tokens, 0) * 0.06 / 1000.0)
            ) AS estimated_cost_usd,
            MAX(pe.executed_at) AS last_executed_at
        FROM prompt_templates pt
        LEFT JOIN prompt_executions pe ON pt.id = pe.prompt_template_id
        GROUP BY pt.id, pt.name, pt.version, pt.ab_test_group
    """)

    # Recreate indexes on view
    op.execute("""
        CREATE UNIQUE INDEX idx_analytics_summary_template_id
        ON prompt_analytics_summary(prompt_template_id)
    """)

    op.execute("""
        CREATE INDEX idx_analytics_summary_name
        ON prompt_analytics_summary(name, version)
    """)

