"""Add UUID foreign key indexes for performance optimization

Revision ID: 0017
Revises: 0016
Create Date: 2025-11-30 14:23:56.088314

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0017'
down_revision: Union[str, Sequence[str], None] = '0016'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add UUID foreign key indexes for performance optimization.

    PostgreSQL does NOT auto-create indexes on FK columns.
    These indexes improve query performance for junction tables (interview_questions, cv_skills).

    Expected gains:
    - 200-400ms query speedup on question/skill retrieval
    - Index scan instead of sequential scan on junction table queries
    """
    # Junction table: interview_questions
    # Indexes for common query patterns
    op.create_index(
        'idx_interview_questions_interview',
        'interview_questions',
        ['interview_id'],
        unique=False
    )
    op.create_index(
        'idx_interview_questions_question',
        'interview_questions',
        ['question_id'],
        unique=False
    )
    # Composite index for ordered retrieval (interview_id + sequence_order)
    op.create_index(
        'idx_interview_questions_composite',
        'interview_questions',
        ['interview_id', 'sequence_order'],
        unique=False
    )

    # Normalized table: cv_skills
    # Index for foreign key lookups
    op.create_index(
        'idx_cv_skills_cv_analysis',
        'cv_skills',
        ['cv_analysis_id'],
        unique=False
    )
    # Composite index for primary skill filtering
    op.create_index(
        'idx_cv_skills_is_primary',
        'cv_skills',
        ['cv_analysis_id', 'is_primary'],
        unique=False
    )


def downgrade() -> None:
    """Remove UUID foreign key indexes."""
    # Drop indexes in reverse order
    op.drop_index('idx_cv_skills_is_primary', table_name='cv_skills')
    op.drop_index('idx_cv_skills_cv_analysis', table_name='cv_skills')
    op.drop_index('idx_interview_questions_composite', table_name='interview_questions')
    op.drop_index('idx_interview_questions_question', table_name='interview_questions')
    op.drop_index('idx_interview_questions_interview', table_name='interview_questions')
