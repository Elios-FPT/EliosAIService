"""create prompt analytics view

Revision ID: 0012_251120_create_prompt_analytics_view
Revises: 0011_251120_create_prompt_executions
Create Date: 2025-11-20

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0012'
down_revision = '0011'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create materialized view for prompt analytics aggregation."""

    # Create materialized view
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
            -- Cost calculation (OpenAI gpt-4 pricing: $0.03/1k prompt, $0.06/1k completion)
            SUM(
                (COALESCE(pe.prompt_tokens, 0) * 0.03 / 1000.0) +
                (COALESCE(pe.completion_tokens, 0) * 0.06 / 1000.0)
            ) AS estimated_cost_usd,
            MAX(pe.executed_at) AS last_executed_at
        FROM prompt_templates pt
        LEFT JOIN prompt_executions pe ON pt.id = pe.prompt_template_id
        GROUP BY pt.id, pt.name, pt.version, pt.ab_test_group
    """)

    # Create unique index on materialized view
    op.execute("""
        CREATE UNIQUE INDEX idx_analytics_summary_template_id
        ON prompt_analytics_summary(prompt_template_id)
    """)

    # Create additional index for efficient lookups by name/version
    op.execute("""
        CREATE INDEX idx_analytics_summary_name
        ON prompt_analytics_summary(name, version)
    """)


def downgrade() -> None:
    """Drop prompt_analytics_summary materialized view."""

    # Drop materialized view (indexes are dropped automatically)
    op.execute("DROP MATERIALIZED VIEW IF EXISTS prompt_analytics_summary")
