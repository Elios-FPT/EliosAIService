"""Drop question_id and interview_id from evaluations table.

Revision ID: 12
Revises: 11
Create Date: 2025-12-08 00:00:00.000000

Description:
    - Drop question_id and interview_id columns from evaluations
    - Drop related indexes
    - Data in these columns is discarded (non-recoverable)
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "12"
down_revision: Union[str, Sequence[str], None] = "11"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Drop obsolete columns and indexes."""
    op.drop_index("idx_evaluations_question_id", table_name="evaluations")
    op.drop_index("idx_evaluations_interview_id", table_name="evaluations")

    op.drop_column("evaluations", "question_id")
    op.drop_column("evaluations", "interview_id")


def downgrade() -> None:
    """Recreate columns with relaxed nullability (data cannot be restored)."""
    op.add_column(
        "evaluations",
        sa.Column(
            "interview_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.add_column(
        "evaluations",
        sa.Column(
            "question_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )

    op.create_index(
        "idx_evaluations_interview_id",
        "evaluations",
        ["interview_id"],
        unique=False,
    )
    op.create_index(
        "idx_evaluations_question_id",
        "evaluations",
        ["question_id"],
        unique=False,
    )

    op.create_foreign_key(
        "fk_evaluations_interview_id",
        "evaluations",
        "interviews",
        ["interview_id"],
        ["id"],
        ondelete="CASCADE",
    )

