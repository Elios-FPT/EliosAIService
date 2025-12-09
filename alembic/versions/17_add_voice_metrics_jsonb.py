"""Add voice_metrics JSONB column to evaluations table.

This migration adds a JSONB column to store raw voice analysis metrics:
- intonation_score: float (0-1)
- fluency_score: float (0-1)
- confidence_score: float (0-1)
- speaking_rate_wpm: int

This enables storing raw voice metrics for future analysis while maintaining
backward compatibility with existing sentiment field.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "17"
down_revision: Union[str, Sequence[str], None] = "16"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add voice_metrics JSONB column to evaluations table."""
    # Add voice_metrics JSONB column (nullable)
    op.add_column(
        "evaluations",
        sa.Column("voice_metrics", postgresql.JSONB(), nullable=True),
    )

    # Add GIN index for efficient JSONB queries
    op.create_index(
        "idx_evaluations_voice_metrics",
        "evaluations",
        ["voice_metrics"],
        postgresql_using="gin",
        unique=False,
    )


def downgrade() -> None:
    """Remove voice_metrics JSONB column and index."""
    op.drop_index("idx_evaluations_voice_metrics", table_name="evaluations")
    op.drop_column("evaluations", "voice_metrics")

