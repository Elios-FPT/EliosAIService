"""Redesign database schema - remove redundancy, normalize structures

Revision ID: 0015
Revises: 0014
Create Date: 2025-11-22

Changes:
- Normalize cv_analyses.skills (JSONB) → cv_skills table
- Convert interviews arrays → interview_questions junction table
- Add ENUMs for question_type, difficulty, proficiency_level
- Remove redundant columns (candidate_id in answers, metadata fields)
- Drop deprecated JSONB (evaluation, gaps - migrated in 0003)
- Decompose prompt_templates.template_json into editable columns
- Add soft delete to prompt_templates
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0015'
down_revision: Union[str, None] = '0014'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Apply schema redesign."""

    # ========================================================================
    # STEP 1: CREATE NEW ENUMS
    # ========================================================================

    # Create question_type ENUM
    op.execute("""
        CREATE TYPE question_type_enum AS ENUM (
            'technical',
            'behavioral',
            'situational',
            'problem_solving',
            'system_design'
        )
    """)

    # Create difficulty ENUM
    op.execute("""
        CREATE TYPE difficulty_enum AS ENUM (
            'easy',
            'medium',
            'hard',
            'expert'
        )
    """)

    # Create proficiency_level ENUM
    op.execute("""
        CREATE TYPE proficiency_level_enum AS ENUM (
            'beginner',
            'intermediate',
            'advanced',
            'expert'
        )
    """)

    # ========================================================================
    # STEP 2: CREATE NEW TABLES
    # ========================================================================

    # Create cv_skills table (normalized skills)
    op.create_table(
        'cv_skills',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('cv_analysis_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('skill_name', sa.String(100), nullable=False),
        sa.Column('proficiency_level', postgresql.ENUM('beginner', 'intermediate', 'advanced', 'expert', name='proficiency_level_enum'), nullable=True),
        sa.Column('years_of_experience', sa.Float(), nullable=True),
        sa.Column('is_primary', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=False),
        sa.ForeignKeyConstraint(['cv_analysis_id'], ['cv_analyses.id'], ondelete='CASCADE')
    )

    # Create indexes for cv_skills
    op.create_index('idx_cv_skills_cv_analysis_id', 'cv_skills', ['cv_analysis_id'])
    op.create_index('idx_cv_skills_skill_name', 'cv_skills', ['skill_name'])
    op.create_index('idx_cv_skills_proficiency', 'cv_skills', ['proficiency_level'])
    op.create_index('idx_cv_skills_primary', 'cv_skills', ['is_primary'],
                    postgresql_where=sa.text('is_primary = true'))

    # Create interview_questions table (junction table)
    op.create_table(
        'interview_questions',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('interview_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('question_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('sequence_order', sa.Integer(), nullable=False),
        sa.Column('asked_at', sa.DateTime(), nullable=True),
        sa.Column('skipped', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('skip_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=False),
        sa.ForeignKeyConstraint(['interview_id'], ['interviews.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['question_id'], ['questions.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('interview_id', 'sequence_order', name='uq_interview_questions_sequence'),
        sa.UniqueConstraint('interview_id', 'question_id', name='uq_interview_questions_pair')
    )

    # Create indexes for interview_questions
    op.create_index('idx_interview_questions_interview_id', 'interview_questions', ['interview_id', 'sequence_order'])
    op.create_index('idx_interview_questions_question_id', 'interview_questions', ['question_id'])
    op.create_index('idx_interview_questions_asked_at', 'interview_questions', ['asked_at'])

    # ========================================================================
    # STEP 3: MIGRATE DATA TO NEW STRUCTURES
    # ========================================================================

    # Migrate cv_analyses.skills (JSONB) → cv_skills table
    op.execute("""
        INSERT INTO cv_skills (cv_analysis_id, skill_name, proficiency_level, years_of_experience, is_primary, created_at)
        SELECT
            cv.id AS cv_analysis_id,
            skill->>'name' AS skill_name,
            CASE
                WHEN skill->>'proficiency' IN ('beginner', 'intermediate', 'advanced', 'expert')
                THEN (skill->>'proficiency')::proficiency_level_enum
                ELSE 'intermediate'::proficiency_level_enum
            END AS proficiency_level,
            NULLIF(skill->>'years', '')::FLOAT AS years_of_experience,
            COALESCE((skill->>'is_primary')::BOOLEAN, false) AS is_primary,
            cv.created_at
        FROM cv_analyses cv
        CROSS JOIN LATERAL jsonb_array_elements(cv.skills) AS skill
        WHERE cv.skills IS NOT NULL
          AND jsonb_typeof(cv.skills) = 'array'
          AND jsonb_array_length(cv.skills) > 0
    """)

    # Migrate interviews.question_ids[] → interview_questions table
    op.execute("""
        INSERT INTO interview_questions (interview_id, question_id, sequence_order, asked_at, created_at)
        SELECT
            i.id AS interview_id,
            question_id,
            (row_number - 1) AS sequence_order,
            CASE
                WHEN (row_number - 1) < i.current_question_index
                THEN i.started_at + (interval '5 minutes' * (row_number - 1))
                ELSE NULL
            END AS asked_at,
            i.created_at
        FROM interviews i
        CROSS JOIN LATERAL unnest(i.question_ids) WITH ORDINALITY AS t(question_id, row_number)
        WHERE i.question_ids IS NOT NULL
          AND array_length(i.question_ids, 1) > 0
    """)

    # ========================================================================
    # STEP 4: MODIFY EXISTING TABLES
    # ========================================================================

    # 4.1: cv_analyses - Drop redundant columns
    op.drop_column('cv_analyses', 'cv_file_path')
    op.drop_column('cv_analyses', 'skills')
    op.drop_column('cv_analyses', 'metadata')

    # 4.2: questions - Convert to ENUMs and drop columns
    # Add temporary columns
    op.add_column('questions', sa.Column('question_type_new', postgresql.ENUM('technical', 'behavioral', 'situational', 'problem_solving', 'system_design', name='question_type_enum'), nullable=True))
    op.add_column('questions', sa.Column('difficulty_new', postgresql.ENUM('easy', 'medium', 'hard', 'expert', name='difficulty_enum'), nullable=True))

    # Migrate data with fallback defaults
    op.execute("""
        UPDATE questions
        SET
            question_type_new = CASE
                WHEN question_type IN ('technical', 'behavioral', 'situational', 'problem_solving', 'system_design')
                THEN question_type::question_type_enum
                ELSE 'technical'::question_type_enum
            END,
            difficulty_new = CASE
                WHEN difficulty IN ('easy', 'medium', 'hard', 'expert')
                THEN difficulty::difficulty_enum
                ELSE 'medium'::difficulty_enum
            END
    """)

    # Drop old indexes
    op.drop_index('idx_questions_type', 'questions')
    op.drop_index('idx_questions_difficulty', 'questions')
    op.drop_index('idx_questions_tags', 'questions')

    # Drop old columns
    op.drop_column('questions', 'question_type')
    op.drop_column('questions', 'difficulty')
    op.drop_column('questions', 'tags')
    op.drop_column('questions', 'evaluation_criteria')

    # Rename new columns
    op.alter_column('questions', 'question_type_new', new_column_name='question_type', nullable=False)
    op.alter_column('questions', 'difficulty_new', new_column_name='difficulty', nullable=False)

    # Recreate indexes
    op.create_index('idx_questions_type', 'questions', ['question_type'])
    op.create_index('idx_questions_difficulty', 'questions', ['difficulty'])

    # 4.3: interviews - Drop array columns
    op.drop_column('interviews', 'question_ids')
    op.drop_column('interviews', 'answer_ids')

    # 4.4: answers - Drop redundant/migrated columns
    op.drop_index('idx_answers_candidate_id', 'answers')
    op.drop_index('idx_answers_similarity_score', 'answers')
    op.drop_index('idx_answers_gaps', 'answers')

    # Drop check constraint
    op.drop_constraint('check_similarity_score_bounds', 'answers', type_='check')

    # Drop columns
    op.drop_column('answers', 'candidate_id')
    op.drop_column('answers', 'metadata')
    op.drop_column('answers', 'evaluation')
    op.drop_column('answers', 'gaps')
    op.drop_column('answers', 'similarity_score')
    op.drop_column('answers', 'evaluated_at')

    # 4.5: prompt_templates - Decompose template_json into editable columns

    # Add new columns for decomposed structure
    op.add_column('prompt_templates', sa.Column('system_prompt', sa.Text(), nullable=True))
    op.add_column('prompt_templates', sa.Column('user_template', sa.Text(), nullable=True))
    op.add_column('prompt_templates', sa.Column('input_variables', postgresql.ARRAY(sa.String()), server_default='{}', nullable=False))
    op.add_column('prompt_templates', sa.Column('partial_variables', postgresql.JSONB(), server_default='{}', nullable=False))
    op.add_column('prompt_templates', sa.Column('output_parser_type', sa.String(50), server_default='json_output_parser', nullable=False))
    op.add_column('prompt_templates', sa.Column('output_schema', postgresql.JSONB(), nullable=True))
    op.add_column('prompt_templates', sa.Column('temperature', sa.Numeric(3, 2), server_default='0.3', nullable=False))
    op.add_column('prompt_templates', sa.Column('max_tokens', sa.Integer(), server_default='2000', nullable=False))
    op.add_column('prompt_templates', sa.Column('top_p', sa.Numeric(3, 2), server_default='0.95', nullable=False))
    op.add_column('prompt_templates', sa.Column('frequency_penalty', sa.Numeric(3, 2), server_default='0', nullable=False))
    op.add_column('prompt_templates', sa.Column('presence_penalty', sa.Numeric(3, 2), server_default='0', nullable=False))
    op.add_column('prompt_templates', sa.Column('deleted_at', sa.DateTime(), nullable=True))

    # Migrate existing template_json to decomposed columns
    op.execute("""
        UPDATE prompt_templates
        SET
            system_prompt = COALESCE(
                template_json->'messages'->0->>'content',
                ''
            ),
            user_template = COALESCE(
                template_json->'messages'->1->>'content',
                ''
            ),
            input_variables = COALESCE(
                ARRAY(SELECT jsonb_array_elements_text(template_json->'input_variables')),
                ARRAY[]::TEXT[]
            ),
            partial_variables = COALESCE(
                template_json->'partial_variables',
                '{}'::jsonb
            ),
            output_parser_type = COALESCE(
                template_json->'output_parser'->>'type',
                'json_output_parser'
            ),
            output_schema = COALESCE(
                template_json->'output_parser'->'schema',
                '{}'::jsonb
            ),
            temperature = COALESCE(
                (template_json->'model_params'->>'temperature')::NUMERIC,
                0.3
            ),
            max_tokens = COALESCE(
                (template_json->'model_params'->>'max_tokens')::INTEGER,
                2000
            ),
            top_p = COALESCE(
                (template_json->'model_params'->>'top_p')::NUMERIC,
                0.95
            ),
            frequency_penalty = COALESCE(
                (template_json->'model_params'->>'frequency_penalty')::NUMERIC,
                0.0
            ),
            presence_penalty = COALESCE(
                (template_json->'model_params'->>'presence_penalty')::NUMERIC,
                0.0
            )
        WHERE template_json IS NOT NULL
    """)

    # Add CHECK constraints for model parameters
    op.create_check_constraint('ck_prompt_templates_temperature', 'prompt_templates',
                               'temperature >= 0 AND temperature <= 2')
    op.create_check_constraint('ck_prompt_templates_max_tokens', 'prompt_templates',
                               'max_tokens > 0 AND max_tokens <= 100000')
    op.create_check_constraint('ck_prompt_templates_top_p', 'prompt_templates',
                               'top_p >= 0 AND top_p <= 1')
    op.create_check_constraint('ck_prompt_templates_frequency_penalty', 'prompt_templates',
                               'frequency_penalty >= -2 AND frequency_penalty <= 2')
    op.create_check_constraint('ck_prompt_templates_presence_penalty', 'prompt_templates',
                               'presence_penalty >= -2 AND presence_penalty <= 2')

    # Set NOT NULL after migration
    op.alter_column('prompt_templates', 'system_prompt', nullable=False)
    op.alter_column('prompt_templates', 'user_template', nullable=False)
    op.alter_column('prompt_templates', 'output_schema', nullable=False)

    # Rename old template_json to template_json_legacy (backup)
    op.alter_column('prompt_templates', 'template_json', new_column_name='template_json_legacy')

    # Create computed template_json column for LangChain compatibility
    # Note: PostgreSQL GENERATED columns require specific syntax
    op.execute("""
        ALTER TABLE prompt_templates
        ADD COLUMN template_json JSONB GENERATED ALWAYS AS (
            jsonb_build_object(
                'template_type', 'chat',
                'messages', jsonb_build_array(
                    jsonb_build_object('role', 'system', 'content', system_prompt),
                    jsonb_build_object('role', 'user', 'content', user_template)
                ),
                'input_variables', to_jsonb(input_variables),
                'partial_variables', partial_variables,
                'output_parser', jsonb_build_object(
                    'type', output_parser_type,
                    'schema', output_schema
                ),
                'model_params', jsonb_build_object(
                    'temperature', temperature,
                    'max_tokens', max_tokens,
                    'top_p', top_p,
                    'frequency_penalty', frequency_penalty,
                    'presence_penalty', presence_penalty
                )
            )
        ) STORED
    """)

    # Create index for soft deletes
    op.create_index('idx_prompt_templates_deleted_at', 'prompt_templates', ['deleted_at'],
                    postgresql_where=sa.text('deleted_at IS NOT NULL'))

    # ========================================================================
    # STEP 5: CREATE HELPER VIEWS
    # ========================================================================

    # View: interview_details (aggregated interview data)
    op.execute("""
        CREATE OR REPLACE VIEW interview_details AS
        SELECT
            i.id AS interview_id,
            i.candidate_id,
            i.status,
            i.cv_analysis_id,
            i.current_question_index,
            COUNT(DISTINCT iq.id) AS total_questions,
            COUNT(DISTINCT iq.asked_at) AS questions_asked,
            COUNT(DISTINCT a.id) AS answers_submitted,
            i.started_at,
            i.completed_at,
            i.created_at,
            i.updated_at
        FROM interviews i
        LEFT JOIN interview_questions iq ON iq.interview_id = i.id
        LEFT JOIN answers a ON a.interview_id = i.id
        GROUP BY i.id
    """)

    # View: cv_analysis_with_skills (CV with aggregated skills)
    op.execute("""
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
    """)

    # ========================================================================
    # STEP 6: DATA INTEGRITY VALIDATION
    # ========================================================================

    # Verify no orphaned cv_skills
    op.execute("""
        DO $$
        DECLARE
            orphaned_count INT;
        BEGIN
            SELECT COUNT(*) INTO orphaned_count
            FROM cv_skills s
            LEFT JOIN cv_analyses cv ON cv.id = s.cv_analysis_id
            WHERE cv.id IS NULL;

            IF orphaned_count > 0 THEN
                RAISE EXCEPTION 'Found % orphaned cv_skills records', orphaned_count;
            END IF;

            RAISE NOTICE 'cv_skills integrity check passed';
        END $$
    """)

    # Verify no orphaned interview_questions
    op.execute("""
        DO $$
        DECLARE
            orphaned_count INT;
        BEGIN
            SELECT COUNT(*) INTO orphaned_count
            FROM interview_questions iq
            LEFT JOIN interviews i ON i.id = iq.interview_id
            WHERE i.id IS NULL;

            IF orphaned_count > 0 THEN
                RAISE EXCEPTION 'Found % orphaned interview_questions records', orphaned_count;
            END IF;

            RAISE NOTICE 'interview_questions integrity check passed';
        END $$
    """)


def downgrade() -> None:
    """Revert schema redesign."""

    # Drop views
    op.execute('DROP VIEW IF EXISTS cv_analysis_with_skills')
    op.execute('DROP VIEW IF EXISTS interview_details')

    # Revert prompt_templates
    op.drop_index('idx_prompt_templates_deleted_at', 'prompt_templates')
    op.drop_constraint('ck_prompt_templates_presence_penalty', 'prompt_templates', type_='check')
    op.drop_constraint('ck_prompt_templates_frequency_penalty', 'prompt_templates', type_='check')
    op.drop_constraint('ck_prompt_templates_top_p', 'prompt_templates', type_='check')
    op.drop_constraint('ck_prompt_templates_max_tokens', 'prompt_templates', type_='check')
    op.drop_constraint('ck_prompt_templates_temperature', 'prompt_templates', type_='check')

    op.execute('ALTER TABLE prompt_templates DROP COLUMN template_json')
    op.alter_column('prompt_templates', 'template_json_legacy', new_column_name='template_json')

    op.drop_column('prompt_templates', 'deleted_at')
    op.drop_column('prompt_templates', 'presence_penalty')
    op.drop_column('prompt_templates', 'frequency_penalty')
    op.drop_column('prompt_templates', 'top_p')
    op.drop_column('prompt_templates', 'max_tokens')
    op.drop_column('prompt_templates', 'temperature')
    op.drop_column('prompt_templates', 'output_schema')
    op.drop_column('prompt_templates', 'output_parser_type')
    op.drop_column('prompt_templates', 'partial_variables')
    op.drop_column('prompt_templates', 'input_variables')
    op.drop_column('prompt_templates', 'user_template')
    op.drop_column('prompt_templates', 'system_prompt')

    # Revert answers
    op.add_column('answers', sa.Column('evaluated_at', sa.DateTime(), nullable=True))
    op.add_column('answers', sa.Column('similarity_score', sa.Float(), nullable=True))
    op.add_column('answers', sa.Column('gaps', postgresql.JSONB(), nullable=True))
    op.add_column('answers', sa.Column('evaluation', postgresql.JSONB(), nullable=True))
    op.add_column('answers', sa.Column('metadata', postgresql.JSONB(), server_default='{}', nullable=False))
    op.add_column('answers', sa.Column('candidate_id', postgresql.UUID(as_uuid=True), nullable=True))

    # Restore candidate_id from interviews
    op.execute("""
        UPDATE answers a
        SET candidate_id = i.candidate_id
        FROM interviews i
        WHERE a.interview_id = i.id
    """)

    op.alter_column('answers', 'candidate_id', nullable=False)
    op.create_foreign_key('fk_answers_candidate_id', 'answers', 'candidates', ['candidate_id'], ['id'], ondelete='CASCADE')

    op.create_index('idx_answers_candidate_id', 'answers', ['candidate_id'])
    op.create_index('idx_answers_similarity_score', 'answers', ['similarity_score'],
                    postgresql_where=sa.text('similarity_score IS NOT NULL'))
    op.create_index('idx_answers_gaps', 'answers', ['gaps'], postgresql_using='gin',
                    postgresql_where=sa.text('gaps IS NOT NULL'))
    op.create_check_constraint('check_similarity_score_bounds', 'answers',
                               'similarity_score IS NULL OR (similarity_score >= 0 AND similarity_score <= 1)')

    # Revert interviews
    op.add_column('interviews', sa.Column('answer_ids', postgresql.ARRAY(postgresql.UUID(as_uuid=True)), server_default='{}', nullable=False))
    op.add_column('interviews', sa.Column('question_ids', postgresql.ARRAY(postgresql.UUID(as_uuid=True)), server_default='{}', nullable=False))

    # Restore arrays from junction table
    op.execute("""
        UPDATE interviews i
        SET question_ids = ARRAY(
            SELECT question_id
            FROM interview_questions
            WHERE interview_id = i.id
            ORDER BY sequence_order
        )
    """)

    op.execute("""
        UPDATE interviews i
        SET answer_ids = ARRAY(
            SELECT id
            FROM answers
            WHERE interview_id = i.id
            ORDER BY created_at
        )
    """)

    # Revert questions
    op.add_column('questions', sa.Column('evaluation_criteria', sa.Text(), nullable=True))
    op.add_column('questions', sa.Column('tags', postgresql.ARRAY(sa.String(100)), server_default='{}', nullable=False))
    op.add_column('questions', sa.Column('difficulty', sa.String(50), nullable=True))
    op.add_column('questions', sa.Column('question_type', sa.String(50), nullable=True))

    # Convert ENUMs back to strings
    op.execute("""
        UPDATE questions
        SET
            question_type = question_type::text,
            difficulty = difficulty::text
    """)

    op.drop_index('idx_questions_difficulty', 'questions')
    op.drop_index('idx_questions_type', 'questions')

    op.drop_column('questions', 'difficulty')
    op.drop_column('questions', 'question_type')

    op.alter_column('questions', 'question_type', nullable=False)
    op.alter_column('questions', 'difficulty', nullable=False)

    op.create_index('idx_questions_tags', 'questions', ['tags'], postgresql_using='gin')
    op.create_index('idx_questions_difficulty', 'questions', ['difficulty'])
    op.create_index('idx_questions_type', 'questions', ['question_type'])

    # Revert cv_analyses
    op.add_column('cv_analyses', sa.Column('metadata', postgresql.JSONB(), server_default='{}', nullable=False))
    op.add_column('cv_analyses', sa.Column('skills', postgresql.JSONB(), server_default='[]', nullable=False))
    op.add_column('cv_analyses', sa.Column('cv_file_path', sa.String(500), nullable=True))

    # Restore skills from cv_skills table
    op.execute("""
        UPDATE cv_analyses cv
        SET skills = COALESCE(
            (SELECT jsonb_agg(
                jsonb_build_object(
                    'name', s.skill_name,
                    'proficiency', s.proficiency_level::text,
                    'years', s.years_of_experience,
                    'is_primary', s.is_primary
                ) ORDER BY s.is_primary DESC, s.skill_name
            )
            FROM cv_skills s
            WHERE s.cv_analysis_id = cv.id),
            '[]'::jsonb
        )
    """)

    # Drop new tables
    op.drop_table('interview_questions')
    op.drop_table('cv_skills')

    # Drop ENUMs
    op.execute('DROP TYPE IF EXISTS proficiency_level_enum')
    op.execute('DROP TYPE IF EXISTS difficulty_enum')
    op.execute('DROP TYPE IF EXISTS question_type_enum')
