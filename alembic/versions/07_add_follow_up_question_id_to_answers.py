"""add follow_up_question_id to answers

Revision ID: 07
Revises: 06
Create Date: 2025-12-03 05:07:55.392143

Description:
    - Add follow_up_question_id column to answers table (nullable UUID)
    - Backfill existing follow-up answers using timestamp inference
    - Create FK constraint to follow_up_questions.id (CASCADE delete)
    - Create index on follow_up_question_id for query performance
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = '07'
down_revision: Union[str, Sequence[str], None] = '06'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def backfill_follow_up_question_ids() -> None:
    """Backfill follow_up_question_id for existing answers using timestamp inference.

    Strategy:
    1. For each interview with follow-ups:
       - Get all answers for parent questions (ordered by created_at ASC)
       - Get all follow-ups for parent questions (ordered by order_in_sequence ASC)
       - Match answers[1..N] to follow-ups[0..N-1] (first answer = parent, rest = follow-ups)
    2. Update answers.follow_up_question_id in batches
    3. Validate: Check FK constraint violations
    """
    conn = op.get_bind()

    # Get all interviews with follow-ups
    interviews_with_followups = conn.execute(text("""
        SELECT DISTINCT interview_id
        FROM follow_up_questions
    """)).fetchall()

    total_updated = 0
    errors = []

    for (interview_id,) in interviews_with_followups:
        try:
            # Get all parent questions with follow-ups
            parent_questions = conn.execute(text("""
                SELECT DISTINCT parent_question_id
                FROM follow_up_questions
                WHERE interview_id = :interview_id
            """), {"interview_id": interview_id}).fetchall()

            for (parent_question_id,) in parent_questions:
                # Get answers for this parent (ordered by time)
                answers = conn.execute(text("""
                    SELECT id, created_at
                    FROM answers
                    WHERE interview_id = :interview_id
                      AND question_id = :parent_question_id
                    ORDER BY created_at ASC
                """), {
                    "interview_id": interview_id,
                    "parent_question_id": parent_question_id
                }).fetchall()

                # Get follow-ups (ordered by sequence)
                follow_ups = conn.execute(text("""
                    SELECT id, order_in_sequence
                    FROM follow_up_questions
                    WHERE interview_id = :interview_id
                      AND parent_question_id = :parent_question_id
                    ORDER BY order_in_sequence ASC
                """), {
                    "interview_id": interview_id,
                    "parent_question_id": parent_question_id
                }).fetchall()

                # Match: answers[0] = parent (NULL FK), answers[1..N] = follow-ups
                if len(answers) == len(follow_ups) + 1:
                    # Expected case: 1 parent answer + N follow-up answers
                    for i, (follow_up_id, _) in enumerate(follow_ups):
                        answer_id = answers[i + 1][0]  # Skip first answer (parent)
                        conn.execute(text("""
                            UPDATE answers
                            SET follow_up_question_id = :follow_up_id
                            WHERE id = :answer_id
                        """), {
                            "follow_up_id": follow_up_id,
                            "answer_id": answer_id
                        })
                        total_updated += 1
                else:
                    # Edge case: Mismatch (log for manual review)
                    errors.append({
                        "interview_id": str(interview_id),
                        "parent_question_id": str(parent_question_id),
                        "answer_count": len(answers),
                        "follow_up_count": len(follow_ups),
                        "reason": "Count mismatch (skipped)"
                    })

        except Exception as e:
            errors.append({
                "interview_id": str(interview_id),
                "error": str(e)
            })

    # Log results
    print(f"✅ Backfilled {total_updated} follow-up answer FKs")
    if errors:
        print(f"⚠️  Errors/warnings: {len(errors)}")
        for err in errors[:10]:  # Show first 10
            print(f"   - {err}")

    # Validation: Check FK violations
    invalid_fks = conn.execute(text("""
        SELECT COUNT(*)
        FROM answers
        WHERE follow_up_question_id IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM follow_up_questions
              WHERE id = answers.follow_up_question_id
          )
    """)).scalar()

    if invalid_fks > 0:
        raise ValueError(f"❌ Migration failed: {invalid_fks} invalid FKs found!")


def upgrade() -> None:
    """Add follow_up_question_id column, backfill data, create FK and index."""
    # Step 1: Add column (nullable, no FK yet)
    op.add_column(
        'answers',
        sa.Column(
            'follow_up_question_id',
            postgresql.UUID(as_uuid=True),
            nullable=True
        )
    )

    # Step 2: Backfill data using timestamp inference
    backfill_follow_up_question_ids()

    # Step 3: Add FK constraint (after backfill)
    op.create_foreign_key(
        'fk_answers_follow_up_question_id',
        'answers', 'follow_up_questions',
        ['follow_up_question_id'], ['id'],
        ondelete='CASCADE'
    )

    # Step 4: Create index
    op.create_index(
        'idx_answers_follow_up_question_id',
        'answers',
        ['follow_up_question_id']
    )


def downgrade() -> None:
    """Remove follow_up_question_id column, FK constraint, and index."""
    # Reverse order
    op.drop_index('idx_answers_follow_up_question_id', table_name='answers')
    op.drop_constraint('fk_answers_follow_up_question_id', 'answers', type_='foreignkey')
    op.drop_column('answers', 'follow_up_question_id')
