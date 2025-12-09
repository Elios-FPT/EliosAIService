"""Add theoretical_score and speaking_score to evaluations table.

This migration adds two nullable columns to support combined scoring:
- theoretical_score: LLM score (for combined scoring)
- speaking_score: Voice metrics score (from STT)

These fields enable 70/30 weighted scoring (theoretical + speaking).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "16"
down_revision: Union[str, Sequence[str], None] = "15"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add theoretical_score and speaking_score columns to evaluations table."""
    # Add theoretical_score column (nullable, 0-100)
    op.add_column(
        "evaluations",
        sa.Column("theoretical_score", sa.Float(), nullable=True),
    )

    # Add speaking_score column (nullable, 0-100)
    op.add_column(
        "evaluations",
        sa.Column("speaking_score", sa.Float(), nullable=True),
    )

    # Add check constraints for score bounds
    op.create_check_constraint(
        "check_theoretical_score_bounds",
        "evaluations",
        "theoretical_score IS NULL OR (theoretical_score >= 0 AND theoretical_score <= 100)",
    )
    op.create_check_constraint(
        "check_speaking_score_bounds",
        "evaluations",
        "speaking_score IS NULL OR (speaking_score >= 0 AND speaking_score <= 100)",
    )


def downgrade() -> None:
    """Remove theoretical_score and speaking_score columns."""
    op.drop_constraint("check_speaking_score_bounds", "evaluations", type_="check")
    op.drop_constraint("check_theoretical_score_bounds", "evaluations", type_="check")
    op.drop_column("evaluations", "speaking_score")
    op.drop_column("evaluations", "theoretical_score")

