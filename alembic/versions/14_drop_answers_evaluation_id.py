"""Drop evaluation_id from answers table."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "14"
down_revision: Union[str, Sequence[str], None] = "13"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Remove evaluation_id column and related constraints/index."""
    op.drop_index("idx_answers_evaluation_id", table_name="answers")
    op.drop_constraint("fk_answers_evaluation_id", "answers", type_="foreignkey")
    op.drop_column("answers", "evaluation_id")


def downgrade() -> None:
    """Restore evaluation_id column and constraint/index."""
    op.add_column(
        "answers",
        sa.Column(
            "evaluation_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_answers_evaluation_id",
        "answers",
        "evaluations",
        ["evaluation_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("idx_answers_evaluation_id", "answers", ["evaluation_id"])

