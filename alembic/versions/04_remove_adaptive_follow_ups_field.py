"""Remove adaptive_follow_ups field from interviews table

Revision ID: 04
Revises: 03
Create Date: 2025-12-02 12:00:00.000000

Description:
    - Drop adaptive_follow_ups column from interviews table
    - This field is redundant since follow-up questions are tracked in follow_up_questions table
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, UUID as PGUUID


# revision identifiers, used by Alembic.
revision: str = '04'
down_revision: Union[str, Sequence[str], None] = '03'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Remove adaptive_follow_ups column from interviews table."""
    op.drop_column('interviews', 'adaptive_follow_ups')


def downgrade() -> None:
    """Restore adaptive_follow_ups column to interviews table."""
    op.add_column(
        'interviews',
        sa.Column(
            'adaptive_follow_ups',
            ARRAY(PGUUID(as_uuid=True)),
            nullable=False,
            server_default=sa.text("ARRAY[]::uuid[]"),
        )
    )

