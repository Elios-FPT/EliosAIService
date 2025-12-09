"""Add title column to interviews table.

Revision ID: 09
Revises: 08
Create Date: 2025-12-04 15:30:00.000000

Description:
    - Add nullable title column to interviews table for human-friendly names
    - Backfill existing rows with a deterministic, non-date-based title
      using primary CV skills when available, otherwise a generic label.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "09"
down_revision: Union[str, Sequence[str], None] = "08"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add title column and backfill existing interviews."""
    # 1) Add nullable title column
    op.add_column(
        "interviews",
        sa.Column("title", sa.String(length=150), nullable=True),
    )

    # 2) Backfill existing rows with a simple, non-date-based title.
    # Prefer primary CV skills when available; otherwise fall back to a generic label.
    op.execute(
        """
        UPDATE interviews AS i
        SET title = COALESCE(
            (
                SELECT 'Interview – ' || s.skill_name
                FROM cv_skills AS s
                WHERE s.cv_analysis_id = i.cv_analysis_id
                ORDER BY s.is_primary DESC, s.skill_name
                LIMIT 1
            ),
            'General Interview'
        )
        WHERE i.title IS NULL
        """
    )


def downgrade() -> None:
    """Remove title column from interviews table."""
    op.drop_column("interviews", "title")


