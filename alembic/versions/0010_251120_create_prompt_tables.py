"""create prompt tables

Revision ID: 0010_251120_create_prompt_tables
Revises: 0009_seed_followup_questions_vi
Create Date: 2025-11-20

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0010'
down_revision = '0009'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create prompt_templates and prompt_metadata_changes tables."""

    # Create prompt_templates table
    op.create_table(
        'prompt_templates',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('parent_version_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('change_summary', sa.Text(), nullable=True),
        sa.Column('template_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('is_draft', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('ab_test_group', sa.String(50), nullable=True),
        sa.Column('traffic_percentage', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('created_by', sa.String(100), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['parent_version_id'], ['prompt_templates.id'], ondelete='SET NULL'),
        sa.UniqueConstraint('name', 'version', name='uq_prompt_templates_name_version'),
        sa.CheckConstraint('traffic_percentage >= 0 AND traffic_percentage <= 100', name='ck_prompt_templates_traffic_percentage'),
        sa.CheckConstraint('NOT (is_active = true AND is_draft = true)', name='ck_prompt_templates_no_active_draft')
    )

    # Create indexes for prompt_templates
    op.create_index('idx_prompt_templates_name', 'prompt_templates', ['name'])
    op.create_index('idx_prompt_templates_active', 'prompt_templates', ['is_active'],
                    postgresql_where=sa.text('is_active = true'))
    op.create_index('idx_prompt_templates_version', 'prompt_templates', ['name', 'version'])
    op.create_index('idx_prompt_templates_parent', 'prompt_templates', ['parent_version_id'])
    op.create_index('idx_prompt_templates_ab_test', 'prompt_templates', ['ab_test_group'],
                    postgresql_where=sa.text('ab_test_group IS NOT NULL'))

    # Create prompt_metadata_changes table
    op.create_table(
        'prompt_metadata_changes',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('prompt_template_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('field_name', sa.String(50), nullable=False),
        sa.Column('old_value', sa.Text(), nullable=True),
        sa.Column('new_value', sa.Text(), nullable=True),
        sa.Column('changed_by', sa.String(100), nullable=False),
        sa.Column('changed_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['prompt_template_id'], ['prompt_templates.id'], ondelete='CASCADE')
    )

    # Create indexes for prompt_metadata_changes
    op.create_index('idx_prompt_metadata_changes_template', 'prompt_metadata_changes',
                    ['prompt_template_id', 'changed_at'])
    op.create_index('idx_prompt_metadata_changes_field', 'prompt_metadata_changes',
                    ['field_name', 'changed_at'])


def downgrade() -> None:
    """Drop prompt_metadata_changes and prompt_templates tables."""

    # Drop indexes for prompt_metadata_changes
    op.drop_index('idx_prompt_metadata_changes_field', table_name='prompt_metadata_changes')
    op.drop_index('idx_prompt_metadata_changes_template', table_name='prompt_metadata_changes')

    # Drop prompt_metadata_changes table
    op.drop_table('prompt_metadata_changes')

    # Drop indexes for prompt_templates
    op.drop_index('idx_prompt_templates_ab_test', table_name='prompt_templates')
    op.drop_index('idx_prompt_templates_parent', table_name='prompt_templates')
    op.drop_index('idx_prompt_templates_version', table_name='prompt_templates')
    op.drop_index('idx_prompt_templates_active', table_name='prompt_templates')
    op.drop_index('idx_prompt_templates_name', table_name='prompt_templates')

    # Drop prompt_templates table
    op.drop_table('prompt_templates')
