"""Remove unused CV analysis fields

Revision ID: 03
Revises: 02
Create Date: 2025-12-03 01:38:48.130277

Description:
    - Drop 5 unused columns from cv_analyses table
    - Update cv_analysis_with_skills view (remove deleted fields)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY


# revision identifiers, used by Alembic.
revision: str = '03'
down_revision: Union[str, Sequence[str], None] = '02'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Remove unused fields from cv_analyses table."""

    # STEP 1: Drop view (removes dependency on columns)
    op.execute("DROP VIEW IF EXISTS cv_analysis_with_skills")

    # STEP 2: Drop columns (data deleted permanently)
    op.drop_column('cv_analyses', 'suggested_difficulty')
    op.drop_column('cv_analyses', 'suggested_topics')
    op.drop_column('cv_analyses', 'education_level')
    op.drop_column('cv_analyses', 'work_experience_years')
    op.drop_column('cv_analyses', 'extracted_text')

    # STEP 3: Recreate view with updated schema
    op.execute(
        """
        CREATE OR REPLACE VIEW cv_analysis_with_skills AS
        SELECT
            cv.id AS cv_analysis_id,
            cv.candidate_id,
            cv.embedding,
            cv.summary,
            cv.created_at,
            jsonb_agg(
                jsonb_build_object(
                    'id', s.id,
                    'skill_name', s.skill_name,
                    'proficiency_level', s.proficiency_level,
                    'years_of_experience', s.years_of_experience,
                    'is_primary', s.is_primary
                ) ORDER BY s.is_primary DESC, s.skill_name
            ) FILTER (WHERE s.id IS NOT NULL) AS skills
        FROM cv_analyses cv
        LEFT JOIN cv_skills s ON s.cv_analysis_id = cv.id
        GROUP BY cv.id
        """
    )


def downgrade() -> None:
    """Restore original schema (data NOT restored - only structure)."""

    # STEP 1: Drop updated view
    op.execute("DROP VIEW IF EXISTS cv_analysis_with_skills")

    # STEP 2: Recreate columns (nullable, empty data)
    op.add_column('cv_analyses', sa.Column('extracted_text', sa.Text(), nullable=True))
    op.add_column('cv_analyses', sa.Column('work_experience_years', sa.Float(), nullable=True))
    op.add_column('cv_analyses', sa.Column('education_level', sa.String(100), nullable=True))
    op.add_column('cv_analyses', sa.Column('suggested_topics', ARRAY(sa.String(200)), nullable=True, server_default='{}'))
    op.add_column('cv_analyses', sa.Column('suggested_difficulty', sa.String(50), nullable=True, server_default='medium'))

    # STEP 3: Restore original view definition
    op.execute(
        """
        CREATE OR REPLACE VIEW cv_analysis_with_skills AS
        SELECT
            cv.id AS cv_analysis_id,
            cv.candidate_id,
            cv.extracted_text,
            cv.work_experience_years,
            cv.education_level,
            cv.suggested_topics,
            cv.suggested_difficulty,
            cv.summary,
            cv.created_at,
            jsonb_agg(
                jsonb_build_object(
                    'id', s.id,
                    'skill_name', s.skill_name,
                    'proficiency_level', s.proficiency_level,
                    'years_of_experience', s.years_of_experience,
                    'is_primary', s.is_primary
                ) ORDER BY s.is_primary DESC, s.skill_name
            ) FILTER (WHERE s.id IS NOT NULL) AS skills
        FROM cv_analyses cv
        LEFT JOIN cv_skills s ON s.cv_analysis_id = cv.id
        GROUP BY cv.id
        """
    )
