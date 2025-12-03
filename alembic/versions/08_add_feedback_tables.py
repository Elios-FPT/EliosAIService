"""add feedback_request and feedback_response tables

Revision ID: 08
Revises: 07
Create Date: 2025-12-03 10:05:00.000000

Description:
    - Create input_type_enum and feedback_status_enum ENUM types
    - Create feedback_request table (8 columns)
    - Create feedback_response table (5 columns with JSONB result and prompt_execution_id)
    - Create indexes for performance (status, entity lookup, user lookup, JSONB GIN)
    - Enforce 1:1 relationship via unique constraint on feedback_request_id
    - Link feedback_response to prompt_executions for cost tracking
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "08"
down_revision: Union[str, Sequence[str], None] = "07"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create feedback tables with ENUMs and indexes."""

    # 1. Create ENUM types (with error handling for idempotency)
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE input_type_enum AS ENUM ('CODE', 'CV', 'INTERVIEW');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
        """
    )

    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE feedback_status_enum AS ENUM (
                'PENDING', 'PROCESSING', 'SUCCESS', 'FAILED', 'RETRYING'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
        """
    )

    # 2. Create feedback_request table
    op.create_table(
        "feedback_request",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "input_type",
            postgresql.ENUM(
                "CODE",
                "CV",
                "INTERVIEW",
                name="input_type_enum",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(
                "PENDING",
                "PROCESSING",
                "SUCCESS",
                "FAILED",
                "RETRYING",
                name="feedback_status_enum",
                create_type=False,
            ),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    # 3. Create indexes for feedback_request
    op.create_index(
        "idx_feedback_request_status", "feedback_request", ["status"]
    )
    op.create_index(
        "idx_feedback_request_entity",
        "feedback_request",
        ["entity_id", "input_type"],
    )
    op.create_index(
        "idx_feedback_request_user",
        "feedback_request",
        ["user_id"],
        postgresql_where=sa.text("user_id IS NOT NULL"),
    )
    op.create_index(
        "idx_feedback_request_created",
        "feedback_request",
        [sa.text("created_at DESC")],
    )

    # 4. Create feedback_response table
    op.create_table(
        "feedback_response",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "feedback_request_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            unique=True,
        ),
        sa.Column("result_json", postgresql.JSONB(), nullable=False),
        sa.Column(
            "prompt_execution_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(
            ["feedback_request_id"],
            ["feedback_request.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["prompt_execution_id"],
            ["prompt_executions.id"],
            ondelete="SET NULL",
        ),
    )

    # 5. Create indexes for feedback_response
    op.create_index(
        "idx_feedback_response_request_id",
        "feedback_response",
        ["feedback_request_id"],
        unique=True,
    )
    op.create_index(
        "idx_feedback_response_created",
        "feedback_response",
        [sa.text("created_at DESC")],
    )
    op.create_index(
        "idx_feedback_response_result_gin",
        "feedback_response",
        ["result_json"],
        postgresql_using="gin",
    )
    op.create_index(
        "idx_feedback_response_prompt_execution",
        "feedback_response",
        ["prompt_execution_id"],
        postgresql_where=sa.text("prompt_execution_id IS NOT NULL"),
    )


def downgrade() -> None:
    """Drop feedback tables and ENUM types."""

    # Drop tables first (FK constraint)
    op.drop_index("idx_feedback_response_result_gin", table_name="feedback_response")
    op.drop_index(
        "idx_feedback_response_prompt_execution", table_name="feedback_response"
    )
    op.drop_index(
        "idx_feedback_response_created", table_name="feedback_response"
    )
    op.drop_index(
        "idx_feedback_response_request_id", table_name="feedback_response"
    )
    op.drop_table("feedback_response")

    op.drop_index("idx_feedback_request_created", table_name="feedback_request")
    op.drop_index("idx_feedback_request_user", table_name="feedback_request")
    op.drop_index("idx_feedback_request_entity", table_name="feedback_request")
    op.drop_index("idx_feedback_request_status", table_name="feedback_request")
    op.drop_table("feedback_request")

    # Drop ENUMs
    op.execute("DROP TYPE IF EXISTS feedback_status_enum")
    op.execute("DROP TYPE IF EXISTS input_type_enum")

