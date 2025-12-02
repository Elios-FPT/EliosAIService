"""Remove version field from questions table

Revision ID: 05
Revises: 04
Create Date: 2025-12-02 12:00:00.000000

Description:
    - Drop version column from questions table
    - This field is unused in business logic
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '05'
down_revision: Union[str, Sequence[str], None] = '04'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Remove version column from questions table."""
    op.drop_column('questions', 'version')


def downgrade() -> None:
    """Restore version column to questions table."""
    op.add_column(
        'questions',
        sa.Column(
            'version',
            sa.Integer(),
            nullable=False,
            server_default='1',
        )
    )

