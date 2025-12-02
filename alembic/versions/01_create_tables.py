"""Create all database tables in their final schema form.

This migration is a consolidated baseline that replaces the 0001–0018 chain
for new environments. It assumes a fresh, empty database.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "01"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create enums, tables, indexes, views and triggers for the final schema."""

    # ======================================================================
    # ENUM TYPES
    # ======================================================================

    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE question_type_enum AS ENUM (
                'technical',
                'behavioral',
                'situational',
                'problem_solving',
                'system_design'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
        """
    )

    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE difficulty_enum AS ENUM (
                'easy',
                'medium',
                'hard',
                'expert'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
        """
    )

    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE proficiency_level_enum AS ENUM (
                'beginner',
                'intermediate',
                'advanced',
                'expert'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
        """
    )

    # ======================================================================
    # CORE TABLES
    # ======================================================================

    # questions
    op.create_table(
        "questions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "question_type",
            postgresql.ENUM(
                "technical",
                "behavioral",
                "situational",
                "problem_solving",
                "system_design",
                name="question_type_enum",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "difficulty",
            postgresql.ENUM(
                "easy",
                "medium",
                "hard",
                "expert",
                name="difficulty_enum",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "skills",
            postgresql.ARRAY(sa.String(100)),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("embedding", postgresql.ARRAY(sa.Float()), nullable=True),
        sa.Column("ideal_answer", sa.Text(), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("idx_questions_type", "questions", ["question_type"])
    op.create_index("idx_questions_difficulty", "questions", ["difficulty"])
    op.create_index(
        "idx_questions_skills",
        "questions",
        ["skills"],
        postgresql_using="gin",
    )

    # cv_analyses
    op.create_table(
        "cv_analyses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("extracted_text", sa.Text(), nullable=False),
        sa.Column("work_experience_years", sa.Float(), nullable=True),
        sa.Column("education_level", sa.String(100), nullable=True),
        sa.Column(
            "suggested_topics",
            postgresql.ARRAY(sa.String(200)),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "suggested_difficulty",
            sa.String(50),
            nullable=False,
            server_default="'medium'",
        ),
        sa.Column("embedding", postgresql.ARRAY(sa.Float()), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "idx_cv_analyses_candidate_id", "cv_analyses", ["candidate_id"]
    )
    op.create_index(
        "idx_cv_analyses_created_at", "cv_analyses", ["created_at"]
    )
    op.create_index(
        "idx_cv_analyses_deleted_at",
        "cv_analyses",
        ["deleted_at"],
        postgresql_where=sa.text("deleted_at IS NOT NULL"),
    )

    # interviews
    op.create_table(
        "interviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("cv_analysis_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "current_question_index",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "plan_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "adaptive_follow_ups",
            postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "current_parent_question_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "current_followup_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["cv_analysis_id"], ["cv_analyses.id"], ondelete="SET NULL"
        ),
    )
    op.create_index("idx_interviews_candidate_id", "interviews", ["candidate_id"])
    op.create_index("idx_interviews_status", "interviews", ["status"])
    op.create_index("idx_interviews_created_at", "interviews", ["created_at"])
    op.create_index(
        "idx_interviews_deleted_at",
        "interviews",
        ["deleted_at"],
        postgresql_where=sa.text("deleted_at IS NOT NULL"),
    )

    # answers (without evaluation_id; added after evaluations below)
    op.create_table(
        "answers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("interview_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("question_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "is_voice",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.Column("audio_file_path", sa.String(500), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("embedding", postgresql.ARRAY(sa.Float()), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["interview_id"], ["interviews.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["question_id"], ["questions.id"], ondelete="CASCADE"
        ),
    )
    op.create_index(
        "idx_answers_interview_id", "answers", ["interview_id"]
    )
    op.create_index(
        "idx_answers_question_id", "answers", ["question_id"]
    )
    op.create_index("idx_answers_created_at", "answers", ["created_at"])

    # follow_up_questions
    op.create_table(
        "follow_up_questions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "parent_question_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("questions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "interview_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("interviews.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("generated_reason", sa.Text(), nullable=False),
        sa.Column("order_in_sequence", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "idx_follow_up_questions_parent_question_id",
        "follow_up_questions",
        ["parent_question_id"],
    )
    op.create_index(
        "idx_follow_up_questions_interview_id",
        "follow_up_questions",
        ["interview_id"],
    )
    op.create_index(
        "idx_follow_up_questions_created_at",
        "follow_up_questions",
        ["created_at"],
    )

    # cv_skills
    op.create_table(
        "cv_skills",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("cv_analysis_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("skill_name", sa.String(100), nullable=False),
        sa.Column(
            "proficiency_level",
            postgresql.ENUM(
                "beginner",
                "intermediate",
                "advanced",
                "expert",
                name="proficiency_level_enum",
                create_type=False,
            ),
            nullable=True,
        ),
        sa.Column("years_of_experience", sa.Float(), nullable=True),
        sa.Column(
            "is_primary",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["cv_analysis_id"], ["cv_analyses.id"], ondelete="CASCADE"
        ),
    )
    op.create_index(
        "idx_cv_skills_cv_analysis_id", "cv_skills", ["cv_analysis_id"]
    )

    # evaluations (normalized evaluation details for answers)
    op.create_table(
        "evaluations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("answer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("question_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("interview_id", postgresql.UUID(as_uuid=True), nullable=False),
        # Scores
        sa.Column("raw_score", sa.Float(), nullable=False),
        sa.Column(
            "penalty",
            sa.Float(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("final_score", sa.Float(), nullable=False),
        sa.Column("similarity_score", sa.Float(), nullable=True),
        # LLM evaluation details
        sa.Column("completeness", sa.Float(), nullable=False),
        sa.Column("relevance", sa.Float(), nullable=False),
        sa.Column("sentiment", sa.String(50), nullable=True),
        sa.Column("reasoning", sa.Text(), nullable=True),
        sa.Column(
            "strengths",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "weaknesses",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "improvement_suggestions",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        # Follow-up context
        sa.Column(
            "attempt_number",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
        sa.Column(
            "parent_evaluation_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        # Timestamps
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(), nullable=True),
        # Foreign keys
        sa.ForeignKeyConstraint(
            ["answer_id"], ["answers.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["interview_id"], ["interviews.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["parent_evaluation_id"], ["evaluations.id"], ondelete="SET NULL"
        ),
    )
    # Indexes for evaluations
    op.create_index(
        "idx_evaluations_answer_id", "evaluations", ["answer_id"]
    )
    op.create_index(
        "idx_evaluations_question_id", "evaluations", ["question_id"]
    )
    op.create_index(
        "idx_evaluations_interview_id", "evaluations", ["interview_id"]
    )
    op.create_index(
        "idx_evaluations_parent_id", "evaluations", ["parent_evaluation_id"]
    )
    op.create_index(
        "idx_evaluations_attempt_number",
        "evaluations",
        ["attempt_number"],
    )
    # Constraints for evaluations
    op.create_check_constraint(
        "check_raw_score_bounds",
        "evaluations",
        "raw_score >= 0 AND raw_score <= 100",
    )
    op.create_check_constraint(
        "check_penalty_bounds",
        "evaluations",
        "penalty >= -15 AND penalty <= 0",
    )
    op.create_check_constraint(
        "check_final_score_bounds",
        "evaluations",
        "final_score >= 0 AND final_score <= 100",
    )
    op.create_check_constraint(
        "check_similarity_score_bounds",
        "evaluations",
        "similarity_score IS NULL OR (similarity_score >= 0 AND similarity_score <= 1)",
    )
    op.create_check_constraint(
        "check_completeness_bounds",
        "evaluations",
        "completeness >= 0 AND completeness <= 1",
    )
    op.create_check_constraint(
        "check_relevance_bounds",
        "evaluations",
        "relevance >= 0 AND relevance <= 1",
    )
    op.create_check_constraint(
        "check_attempt_number_bounds",
        "evaluations",
        "attempt_number >= 1 AND attempt_number <= 3",
    )

    # evaluation_gaps (normalized gaps per evaluation)
    op.create_table(
        "evaluation_gaps",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("evaluation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("concept", sa.Text(), nullable=False),
        sa.Column(
            "severity",
            sa.String(20),
            nullable=False,
            server_default="'moderate'",
        ),
        sa.Column(
            "resolved",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["evaluation_id"], ["evaluations.id"], ondelete="CASCADE"
        ),
    )
    op.create_index(
        "idx_evaluation_gaps_evaluation_id",
        "evaluation_gaps",
        ["evaluation_id"],
    )
    op.create_index(
        "idx_evaluation_gaps_resolved",
        "evaluation_gaps",
        ["resolved"],
    )
    op.create_check_constraint(
        "check_severity_values",
        "evaluation_gaps",
        "severity IN ('minor', 'moderate', 'major')",
    )

    # Add evaluation_id column and FK to answers now that evaluations exist
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
    op.create_index("idx_cv_skills_skill_name", "cv_skills", ["skill_name"])
    op.create_index(
        "idx_cv_skills_proficiency", "cv_skills", ["proficiency_level"]
    )
    op.create_index(
        "idx_cv_skills_primary",
        "cv_skills",
        ["is_primary"],
        postgresql_where=sa.text("is_primary = true"),
    )
    # performance indexes from 0017
    op.create_index(
        "idx_cv_skills_cv_analysis",
        "cv_skills",
        ["cv_analysis_id"],
        unique=False,
    )
    op.create_index(
        "idx_cv_skills_is_primary",
        "cv_skills",
        ["cv_analysis_id", "is_primary"],
        unique=False,
    )

    # interview_questions
    op.create_table(
        "interview_questions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("interview_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("question_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sequence_order", sa.Integer(), nullable=False),
        sa.Column("asked_at", sa.DateTime(), nullable=True),
        sa.Column(
            "skipped",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("skip_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["interview_id"], ["interviews.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["question_id"], ["questions.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint(
            "interview_id",
            "sequence_order",
            name="uq_interview_questions_sequence",
        ),
        sa.UniqueConstraint(
            "interview_id",
            "question_id",
            name="uq_interview_questions_pair",
        ),
    )
    op.create_index(
        "idx_interview_questions_interview_id",
        "interview_questions",
        ["interview_id", "sequence_order"],
    )
    op.create_index(
        "idx_interview_questions_question_id",
        "interview_questions",
        ["question_id"],
    )
    op.create_index(
        "idx_interview_questions_asked_at",
        "interview_questions",
        ["asked_at"],
    )
    # additional performance indexes from 0017
    op.create_index(
        "idx_interview_questions_interview",
        "interview_questions",
        ["interview_id"],
        unique=False,
    )
    op.create_index(
        "idx_interview_questions_question",
        "interview_questions",
        ["question_id"],
        unique=False,
    )
    op.create_index(
        "idx_interview_questions_composite",
        "interview_questions",
        ["interview_id", "sequence_order"],
        unique=False,
    )

    # prompt_templates
    op.create_table(
        "prompt_templates",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("parent_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("change_summary", sa.Text(), nullable=True),
        sa.Column(
            "system_prompt",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "user_template",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "input_variables",
            postgresql.ARRAY(sa.String()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "partial_variables",
            postgresql.JSONB(),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "output_parser_type",
            sa.String(50),
            server_default="json_output_parser",
            nullable=False,
        ),
        sa.Column("output_schema", postgresql.JSONB(), nullable=False),
        sa.Column(
            "temperature",
            sa.Numeric(3, 2),
            server_default="0.3",
            nullable=False,
        ),
        sa.Column(
            "max_tokens",
            sa.Integer(),
            server_default="2000",
            nullable=False,
        ),
        sa.Column(
            "top_p",
            sa.Numeric(3, 2),
            server_default="0.95",
            nullable=False,
        ),
        sa.Column(
            "frequency_penalty",
            sa.Numeric(3, 2),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "presence_penalty",
            sa.Numeric(3, 2),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "is_draft",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("created_by", sa.String(100), nullable=True),
        sa.Column("template_json", postgresql.JSONB(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["parent_version_id"], ["prompt_templates.id"], ondelete="SET NULL"
        ),
        sa.UniqueConstraint(
            "name", "version", name="uq_prompt_templates_name_version"
        ),
    )
    op.create_index(
        "idx_prompt_templates_name", "prompt_templates", ["name"]
    )
    op.create_index(
        "idx_prompt_templates_active",
        "prompt_templates",
        ["is_active"],
        postgresql_where=sa.text("is_active = true"),
    )
    op.create_index(
        "idx_prompt_templates_version",
        "prompt_templates",
        ["name", "version"],
    )
    op.create_index(
        "idx_prompt_templates_parent",
        "prompt_templates",
        ["parent_version_id"],
    )
    op.create_index(
        "idx_prompt_templates_deleted_at",
        "prompt_templates",
        ["deleted_at"],
        postgresql_where=sa.text("deleted_at IS NOT NULL"),
    )
    op.create_check_constraint(
        "ck_prompt_templates_temperature",
        "prompt_templates",
        "temperature >= 0 AND temperature <= 2",
    )
    op.create_check_constraint(
        "ck_prompt_templates_max_tokens",
        "prompt_templates",
        "max_tokens > 0 AND max_tokens <= 100000",
    )
    op.create_check_constraint(
        "ck_prompt_templates_top_p",
        "prompt_templates",
        "top_p >= 0 AND top_p <= 1",
    )
    op.create_check_constraint(
        "ck_prompt_templates_frequency_penalty",
        "prompt_templates",
        "frequency_penalty >= -2 AND frequency_penalty <= 2",
    )
    op.create_check_constraint(
        "ck_prompt_templates_presence_penalty",
        "prompt_templates",
        "presence_penalty >= -2 AND presence_penalty <= 2",
    )
    op.create_check_constraint(
        "ck_prompt_templates_no_active_draft",
        "prompt_templates",
        "NOT (is_active = true AND is_draft = true)",
    )

    # prompt_metadata_changes
    op.create_table(
        "prompt_metadata_changes",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("prompt_template_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("field_name", sa.String(50), nullable=False),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("changed_by", sa.String(100), nullable=False),
        sa.Column(
            "changed_at",
            sa.DateTime(),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["prompt_template_id"], ["prompt_templates.id"], ondelete="CASCADE"
        ),
    )
    op.create_index(
        "idx_prompt_metadata_changes_template",
        "prompt_metadata_changes",
        ["prompt_template_id", "changed_at"],
    )
    op.create_index(
        "idx_prompt_metadata_changes_field",
        "prompt_metadata_changes",
        ["field_name", "changed_at"],
    )

    # prompt_executions
    op.create_table(
        "prompt_executions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("prompt_template_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("interview_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("input_variables", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("output_text", sa.Text(), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("model_name", sa.String(50), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "executed_at",
            sa.DateTime(),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["prompt_template_id"], ["prompt_templates.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["interview_id"], ["interviews.id"], ondelete="CASCADE"
        ),
    )
    op.create_index(
        "idx_prompt_executions_template",
        "prompt_executions",
        ["prompt_template_id", "executed_at"],
    )
    op.create_index(
        "idx_prompt_executions_interview",
        "prompt_executions",
        ["interview_id"],
    )
    op.create_index(
        "idx_prompt_executions_success",
        "prompt_executions",
        ["success", "executed_at"],
    )
    op.create_index(
        "idx_prompt_executions_model",
        "prompt_executions",
        ["model_name", "executed_at"],
    )

    # ======================================================================
    # TRIGGERS AND VIEWS (PROMPTS + ANALYTICS + INTERVIEW/CV VIEWS)
    # ======================================================================

    # generate_template_json() and trigger
    op.execute(
        """
        CREATE OR REPLACE FUNCTION generate_template_json()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.template_json := jsonb_build_object(
                'template_type', 'chat',
                'messages', jsonb_build_array(
                    jsonb_build_object('role', 'system', 'content', NEW.system_prompt),
                    jsonb_build_object('role', 'user', 'content', NEW.user_template)
                ),
                'input_variables', to_jsonb(NEW.input_variables),
                'partial_variables', NEW.partial_variables,
                'output_parser', jsonb_build_object(
                    'type', NEW.output_parser_type,
                    'schema', NEW.output_schema
                ),
                'model_params', jsonb_build_object(
                    'temperature', NEW.temperature,
                    'max_tokens', NEW.max_tokens,
                    'top_p', NEW.top_p,
                    'frequency_penalty', NEW.frequency_penalty,
                    'presence_penalty', NEW.presence_penalty
                )
            );
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    op.execute(
        """
        CREATE TRIGGER trg_generate_template_json
        BEFORE INSERT OR UPDATE OF system_prompt, user_template, input_variables,
                                   partial_variables, output_parser_type, output_schema,
                                   temperature, max_tokens, top_p,
                                   frequency_penalty, presence_penalty
        ON prompt_templates
        FOR EACH ROW
        EXECUTE FUNCTION generate_template_json();
        """
    )

    # prompt_analytics_summary (final simplified version from 0016)
    op.execute(
        """
        CREATE MATERIALIZED VIEW prompt_analytics_summary AS
        SELECT
            pt.id AS prompt_template_id,
            pt.name,
            pt.version,
            COUNT(pe.id) AS total_executions,
            AVG(pe.prompt_tokens) AS avg_prompt_tokens,
            AVG(pe.completion_tokens) AS avg_completion_tokens,
            AVG(pe.latency_ms) AS avg_latency_ms,
            CASE
                WHEN COUNT(pe.id) > 0 THEN
                    SUM(CASE WHEN pe.success THEN 1 ELSE 0 END)::FLOAT / COUNT(pe.id)
                ELSE 0
            END AS success_rate,
            SUM(
                (COALESCE(pe.prompt_tokens, 0) * 0.03 / 1000.0) +
                (COALESCE(pe.completion_tokens, 0) * 0.06 / 1000.0)
            ) AS estimated_cost_usd,
            MAX(pe.executed_at) AS last_executed_at
        FROM prompt_templates pt
        LEFT JOIN prompt_executions pe ON pt.id = pe.prompt_template_id
        GROUP BY pt.id, pt.name, pt.version
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX idx_analytics_summary_template_id
        ON prompt_analytics_summary(prompt_template_id)
        """
    )
    op.execute(
        """
        CREATE INDEX idx_analytics_summary_name
        ON prompt_analytics_summary(name, version)
        """
    )

    # interview_details view (from 0015, adjusted to final schema)
    op.execute(
        """
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
        """
    )

    # cv_analysis_with_skills view (from 0015)
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


def downgrade() -> None:
    """Drop all views, triggers, tables and enums created in this baseline."""

    # Drop views
    op.execute("DROP VIEW IF EXISTS cv_analysis_with_skills")
    op.execute("DROP VIEW IF EXISTS interview_details")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS prompt_analytics_summary")

    # Drop trigger and function
    op.execute(
        "DROP TRIGGER IF EXISTS trg_generate_template_json ON prompt_templates"
    )
    op.execute("DROP FUNCTION IF EXISTS generate_template_json()")

    # Drop prompt-related tables
    op.drop_index("idx_prompt_executions_model", table_name="prompt_executions")
    op.drop_index(
        "idx_prompt_executions_success", table_name="prompt_executions"
    )
    op.drop_index(
        "idx_prompt_executions_interview", table_name="prompt_executions"
    )
    op.drop_index(
        "idx_prompt_executions_template", table_name="prompt_executions"
    )
    op.drop_table("prompt_executions")

    op.drop_index(
        "idx_prompt_metadata_changes_field",
        table_name="prompt_metadata_changes",
    )
    op.drop_index(
        "idx_prompt_metadata_changes_template",
        table_name="prompt_metadata_changes",
    )
    op.drop_table("prompt_metadata_changes")

    op.drop_constraint(
        "ck_prompt_templates_presence_penalty",
        "prompt_templates",
        type_="check",
    )
    op.drop_constraint(
        "ck_prompt_templates_frequency_penalty",
        "prompt_templates",
        type_="check",
    )
    op.drop_constraint(
        "ck_prompt_templates_top_p",
        "prompt_templates",
        type_="check",
    )
    op.drop_constraint(
        "ck_prompt_templates_max_tokens",
        "prompt_templates",
        type_="check",
    )
    op.drop_constraint(
        "ck_prompt_templates_temperature",
        "prompt_templates",
        type_="check",
    )
    op.drop_constraint(
        "ck_prompt_templates_no_active_draft",
        "prompt_templates",
        type_="check",
    )

    op.drop_index("idx_prompt_templates_deleted_at", table_name="prompt_templates")
    op.drop_index("idx_prompt_templates_parent", table_name="prompt_templates")
    op.drop_index("idx_prompt_templates_version", table_name="prompt_templates")
    op.drop_index("idx_prompt_templates_active", table_name="prompt_templates")
    op.drop_index("idx_prompt_templates_name", table_name="prompt_templates")
    op.drop_table("prompt_templates")

    # Drop interview-related tables
    op.drop_index(
        "idx_interview_questions_composite",
        table_name="interview_questions",
    )
    op.drop_index(
        "idx_interview_questions_question",
        table_name="interview_questions",
    )
    op.drop_index(
        "idx_interview_questions_interview",
        table_name="interview_questions",
    )
    op.drop_index(
        "idx_interview_questions_asked_at",
        table_name="interview_questions",
    )
    op.drop_index(
        "idx_interview_questions_question_id",
        table_name="interview_questions",
    )
    op.drop_index(
        "idx_interview_questions_interview_id",
        table_name="interview_questions",
    )
    op.drop_table("interview_questions")

    op.drop_index("idx_follow_up_questions_created_at", table_name="follow_up_questions")
    op.drop_index(
        "idx_follow_up_questions_interview_id",
        table_name="follow_up_questions",
    )
    op.drop_index(
        "idx_follow_up_questions_parent_question_id",
        table_name="follow_up_questions",
    )
    op.drop_table("follow_up_questions")

    # Drop evaluations-related schema before dropping answers/interviews
    op.drop_index("idx_answers_evaluation_id", table_name="answers")
    op.drop_constraint(
        "fk_answers_evaluation_id", "answers", type_="foreignkey"
    )
    op.drop_column("answers", "evaluation_id")

    op.drop_index(
        "idx_evaluation_gaps_resolved", table_name="evaluation_gaps"
    )
    op.drop_index(
        "idx_evaluation_gaps_evaluation_id",
        table_name="evaluation_gaps",
    )
    op.drop_constraint(
        "check_severity_values",
        "evaluation_gaps",
        type_="check",
    )
    op.drop_table("evaluation_gaps")

    op.drop_index(
        "idx_evaluations_attempt_number", table_name="evaluations"
    )
    op.drop_index("idx_evaluations_parent_id", table_name="evaluations")
    op.drop_index("idx_evaluations_interview_id", table_name="evaluations")
    op.drop_index("idx_evaluations_question_id", table_name="evaluations")
    op.drop_index("idx_evaluations_answer_id", table_name="evaluations")
    op.drop_constraint(
        "check_attempt_number_bounds",
        "evaluations",
        type_="check",
    )
    op.drop_constraint(
        "check_relevance_bounds", "evaluations", type_="check"
    )
    op.drop_constraint(
        "check_completeness_bounds", "evaluations", type_="check"
    )
    op.drop_constraint(
        "check_similarity_score_bounds",
        "evaluations",
        type_="check",
    )
    op.drop_constraint(
        "check_final_score_bounds",
        "evaluations",
        type_="check",
    )
    op.drop_constraint(
        "check_penalty_bounds", "evaluations", type_="check"
    )
    op.drop_constraint(
        "check_raw_score_bounds", "evaluations", type_="check"
    )
    op.drop_table("evaluations")

    op.drop_index("idx_answers_created_at", table_name="answers")
    op.drop_index("idx_answers_question_id", table_name="answers")
    op.drop_index("idx_answers_interview_id", table_name="answers")
    op.drop_table("answers")

    op.drop_index("idx_interviews_deleted_at", table_name="interviews")
    op.drop_index("idx_interviews_created_at", table_name="interviews")
    op.drop_index("idx_interviews_status", table_name="interviews")
    op.drop_index("idx_interviews_candidate_id", table_name="interviews")
    op.drop_table("interviews")

    # Drop CV-related tables
    op.drop_index("idx_cv_skills_is_primary", table_name="cv_skills")
    op.drop_index("idx_cv_skills_cv_analysis", table_name="cv_skills")
    op.drop_index("idx_cv_skills_primary", table_name="cv_skills")
    op.drop_index("idx_cv_skills_proficiency", table_name="cv_skills")
    op.drop_index("idx_cv_skills_skill_name", table_name="cv_skills")
    op.drop_index("idx_cv_skills_cv_analysis_id", table_name="cv_skills")
    op.drop_table("cv_skills")

    op.drop_index("idx_cv_analyses_deleted_at", table_name="cv_analyses")
    op.drop_index("idx_cv_analyses_created_at", table_name="cv_analyses")
    op.drop_index("idx_cv_analyses_candidate_id", table_name="cv_analyses")
    op.drop_table("cv_analyses")

    # Drop questions
    op.drop_index("idx_questions_skills", table_name="questions")
    op.drop_index("idx_questions_difficulty", table_name="questions")
    op.drop_index("idx_questions_type", table_name="questions")
    op.drop_table("questions")

    # Drop ENUMs
    op.execute("DROP TYPE IF EXISTS proficiency_level_enum")
    op.execute("DROP TYPE IF EXISTS difficulty_enum")
    op.execute("DROP TYPE IF EXISTS question_type_enum")


