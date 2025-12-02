"""Remove duration_seconds and metadata fields from answers table

Revision ID: 06
Revises: 05
Create Date: 2025-12-03 12:00:00.000000

Description:
    - Drop duration_seconds column from answers table
    - Drop metadata column from answers table (if exists)
    - These fields are no longer used in the application
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '06'
down_revision: Union[str, Sequence[str], None] = '05'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Remove duration_seconds and metadata columns from answers table."""
    # Drop duration_seconds column
    op.drop_column('answers', 'duration_seconds')

    # Drop metadata column (if it exists - it may have been removed in code but not in DB)
    # Using raw SQL to check and drop safely
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('answers')]

    if 'metadata' in columns:
        op.drop_column('answers', 'metadata')


def downgrade() -> None:
    """Restore duration_seconds and metadata columns to answers table."""
    # Restore duration_seconds column
    op.add_column(
        'answers',
        sa.Column(
            'duration_seconds',
            sa.Float(),
            nullable=True,
        )
    )

    # Restore metadata column
    op.add_column(
        'answers',
        sa.Column(
            'metadata',
            postgresql.JSONB(),
            nullable=False,
            server_default='{}',
        )
    )

