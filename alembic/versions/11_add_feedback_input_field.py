"""add feedback_input field to feedback_request table

Revision ID: 11
Revises: 10
Create Date: 2025-12-08 05:51:00.000000

Description:
    - Add nullable feedback_input TEXT column
    - Backfill existing rows (extract from entities)
    - Make column NOT NULL
"""
from typing import Sequence, Union
import json
from uuid import UUID

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "11"
down_revision: Union[str, Sequence[str], None] = "10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _extract_interview_content(conn, interview_id: UUID) -> str:
    """Extract interview Q&A content for audit trail.

    Returns JSON string with questions, answers, and metadata.
    """
    # Get interview questions with answers
    questions = conn.execute(
        sa.text("""
            SELECT
                iq.sequence_order,
                iq.question_text,
                iq.question_type,
                a.answer_text,
                a.is_voice,
                a.created_at as answer_created_at
            FROM interview_questions iq
            LEFT JOIN answers a ON a.question_id = iq.question_id
            WHERE iq.interview_id = :interview_id
            ORDER BY iq.sequence_order
        """),
        {"interview_id": str(interview_id)}
    ).fetchall()

    # Build content dict
    content = {
        "interview_id": str(interview_id),
        "questions": []
    }

    for q in questions:
        content["questions"].append({
            "sequence": q.sequence_order,
            "question": q.question_text,
            "type": q.question_type,
            "answer": q.answer_text or None,
            "is_voice": q.is_voice or False,
            "answered_at": q.answer_created_at.isoformat() if q.answer_created_at else None
        })

    return json.dumps(content, indent=2)


def _extract_cv_content(conn, cv_analysis_id: UUID) -> str:
    """Extract CV analysis content for audit trail.

    Returns JSON string with skills, summary, and metadata.
    """
    # Get CV analysis
    cv = conn.execute(
        sa.text("""
            SELECT summary, created_at
            FROM cv_analyses
            WHERE id = :cv_id
        """),
        {"cv_id": str(cv_analysis_id)}
    ).fetchone()

    if not cv:
        return json.dumps({"error": "CV analysis not found"})

    # Get skills
    skills = conn.execute(
        sa.text("""
            SELECT
                skill_name,
                proficiency_level,
                years_of_experience,
                is_primary
            FROM cv_skills
            WHERE cv_analysis_id = :cv_id
            ORDER BY is_primary DESC, skill_name
        """),
        {"cv_id": str(cv_analysis_id)}
    ).fetchall()

    # Build content dict
    content = {
        "cv_analysis_id": str(cv_analysis_id),
        "summary": cv.summary or "",
        "skills": [
            {
                "name": s.skill_name,
                "proficiency": s.proficiency_level or "intermediate",
                "years": float(s.years_of_experience) if s.years_of_experience else None,
                "is_primary": s.is_primary
            }
            for s in skills
        ],
        "created_at": cv.created_at.isoformat() if cv.created_at else None
    }

    return json.dumps(content, indent=2)


def upgrade() -> None:
    """Add feedback_input column with backfill."""

    # Step 1: Add nullable column
    op.add_column(
        'feedback_request',
        sa.Column('feedback_input', sa.Text(), nullable=True)
    )

    # Step 2: Backfill existing rows
    conn = op.get_bind()

    # Get all feedback requests without feedback_input
    feedback_requests = conn.execute(
        sa.text("""
            SELECT id, entity_id, input_type
            FROM feedback_request
            WHERE feedback_input IS NULL
        """)
    ).fetchall()

    for req in feedback_requests:
        req_id, entity_id, input_type = req

        try:
            if input_type == 'INTERVIEW':
                # Extract interview content
                content = _extract_interview_content(conn, UUID(str(entity_id)))
            elif input_type == 'CV':
                # Extract CV content
                content = _extract_cv_content(conn, UUID(str(entity_id)))
            elif input_type == 'CODE':
                # Placeholder (not implemented)
                content = json.dumps({
                    "code_submission_id": str(entity_id),
                    "note": "CODE submission (not implemented)"
                })
            else:
                content = json.dumps({
                    "error": f"Unknown input_type: {input_type}",
                    "entity_id": str(entity_id)
                })

            # Update row
            conn.execute(
                sa.text("""
                    UPDATE feedback_request
                    SET feedback_input = :content
                    WHERE id = :req_id
                """),
                {"content": content, "req_id": str(req_id)}
            )
            conn.commit()
        except Exception as e:
            # Log error, use fallback
            content = json.dumps({
                "error": f"Error extracting content: {str(e)}",
                "entity_id": str(entity_id),
                "input_type": input_type
            })
            conn.execute(
                sa.text("""
                    UPDATE feedback_request
                    SET feedback_input = :content
                    WHERE id = :req_id
                """),
                {"content": content, "req_id": str(req_id)}
            )
            conn.commit()

    # Step 3: Make column NOT NULL
    op.alter_column(
        'feedback_request',
        'feedback_input',
        nullable=False
    )


def downgrade() -> None:
    """Remove feedback_input column."""
    op.drop_column('feedback_request', 'feedback_input')

