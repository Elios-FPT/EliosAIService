"""Remove candidates table and add soft deletes.

Revision ID: 0018
Revises: 0017
Create Date: 2025-12-02
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0018"
down_revision: Union[str, Sequence[str], None] = "0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: add soft deletes and remove candidates table."""

    # Add soft delete columns
    op.add_column("interviews", sa.Column("deleted_at", sa.DateTime(), nullable=True))
    op.add_column("cv_analyses", sa.Column("deleted_at", sa.DateTime(), nullable=True))

    # Create indexes for soft delete queries (partial index - only deleted records)
    op.create_index(
        "idx_interviews_deleted_at",
        "interviews",
        ["deleted_at"],
        postgresql_where=sa.text("deleted_at IS NOT NULL"),
    )
    op.create_index(
        "idx_cv_analyses_deleted_at",
        "cv_analyses",
        ["deleted_at"],
        postgresql_where=sa.text("deleted_at IS NOT NULL"),
    )

    # Drop foreign key constraints from interviews/cv_analyses to candidates
    # These names rely on PostgreSQL default FK naming: {table}_{column}_fkey
    op.drop_constraint(
        "interviews_candidate_id_fkey", "interviews", type_="foreignkey"
    )
    op.drop_constraint(
        "cv_analyses_candidate_id_fkey", "cv_analyses", type_="foreignkey"
    )

    # Drop candidates table (candidate data is now owned by another service)
    op.drop_table("candidates")


def downgrade() -> None:
    """Downgrade schema: restore candidates table and FK constraints."""

    # Recreate candidates table
    op.create_table(
        "candidates",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("cv_file_path", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_candidates_email", "candidates", ["email"], unique=True)
    op.create_index(
        "idx_candidates_created_at", "candidates", ["created_at"], unique=False
    )

    # Recreate foreign key constraints
    op.create_foreign_key(
        "interviews_candidate_id_fkey",
        "interviews",
        "candidates",
        ["candidate_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "cv_analyses_candidate_id_fkey",
        "cv_analyses",
        "candidates",
        ["candidate_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # Drop soft delete indexes and columns
    op.drop_index("idx_cv_analyses_deleted_at", table_name="cv_analyses")
    op.drop_index("idx_interviews_deleted_at", table_name="interviews")
    op.drop_column("cv_analyses", "deleted_at")
    op.drop_column("interviews", "deleted_at")


