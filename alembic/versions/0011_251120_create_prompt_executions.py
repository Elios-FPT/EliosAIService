"""create prompt executions

Revision ID: 0011_251120_create_prompt_executions
Revises: 0010_251120_create_prompt_tables
Create Date: 2025-11-20

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0011'
down_revision = '0010'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create prompt_executions table for analytics tracking."""

    # Create prompt_executions table
    op.create_table(
        'prompt_executions',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('prompt_template_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('interview_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('candidate_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('input_variables', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('output_text', sa.Text(), nullable=True),
        sa.Column('tokens_used', sa.Integer(), nullable=True),
        sa.Column('prompt_tokens', sa.Integer(), nullable=True),
        sa.Column('completion_tokens', sa.Integer(), nullable=True),
        sa.Column('latency_ms', sa.Integer(), nullable=False),
        sa.Column('model_name', sa.String(50), nullable=True),
        sa.Column('success', sa.Boolean(), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('executed_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['prompt_template_id'], ['prompt_templates.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['interview_id'], ['interviews.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['candidate_id'], ['candidates.id'], ondelete='SET NULL')
    )

    # Create indexes for prompt_executions
    op.create_index('idx_prompt_executions_template', 'prompt_executions',
                    ['prompt_template_id', 'executed_at'])
    op.create_index('idx_prompt_executions_interview', 'prompt_executions', ['interview_id'])
    op.create_index('idx_prompt_executions_success', 'prompt_executions',
                    ['success', 'executed_at'])
    op.create_index('idx_prompt_executions_model', 'prompt_executions',
                    ['model_name', 'executed_at'])


def downgrade() -> None:
    """Drop prompt_executions table."""

    # Drop indexes for prompt_executions
    op.drop_index('idx_prompt_executions_model', table_name='prompt_executions')
    op.drop_index('idx_prompt_executions_success', table_name='prompt_executions')
    op.drop_index('idx_prompt_executions_interview', table_name='prompt_executions')
    op.drop_index('idx_prompt_executions_template', table_name='prompt_executions')

    # Drop prompt_executions table
    op.drop_table('prompt_executions')
