"""Remove embedding columns from questions, answers, and cvAnalyses tables.

Revision ID: 19
Revises: 18
Create Date: 2025-12-12

Pinecone handles all embeddings automatically via hosted embedding feature,
making database storage redundant.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "19"
down_revision: Union[str, Sequence[str], None] = "18"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Remove embedding columns from tables."""
    # Drop embedding columns (order doesn't matter - no dependencies)
    op.drop_column("questions", "embedding")
    op.drop_column("answers", "embedding")
    op.drop_column("cvAnalyses", "embedding")


def downgrade() -> None:
    """Restore embedding columns."""
    # Recreate embedding columns as nullable ARRAY(Float)
    op.add_column(
        "questions",
        sa.Column("embedding", postgresql.ARRAY(sa.Float()), nullable=True),
    )
    op.add_column(
        "answers",
        sa.Column("embedding", postgresql.ARRAY(sa.Float()), nullable=True),
    )
    op.add_column(
        "cvAnalyses",
        sa.Column("embedding", postgresql.ARRAY(sa.Float()), nullable=True),
    )

