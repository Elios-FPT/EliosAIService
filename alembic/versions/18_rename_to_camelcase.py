"""Rename all tables and columns from snake_case to camelCase.

Revision ID: 18
Revises: 17
Create Date: 2025-12-11

Single atomic migration for company-wide database naming standard.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "18"
down_revision: Union[str, Sequence[str], None] = "17"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# =============================================================================
# TABLE RENAME MAPPING
# =============================================================================
TABLE_RENAMES = [
    ("cv_analyses", "cvAnalyses"),
    ("cv_skills", "cvSkills"),
    ("interview_questions", "interviewQuestions"),
    ("follow_up_questions", "followUpQuestions"),
    ("evaluation_gaps", "evaluationGaps"),
    ("prompt_templates", "promptTemplates"),
    ("prompt_metadata_changes", "promptMetadataChanges"),
    ("prompt_executions", "promptExecutions"),
    ("feedback_request", "feedbackRequest"),
    ("feedback_response", "feedbackResponse"),
    # Single-word tables: no rename needed
    # ("questions", "questions"),
    # ("interviews", "interviews"),
    # ("answers", "answers"),
    # ("evaluations", "evaluations"),
]


# =============================================================================
# COLUMN RENAME MAPPING (table_new_name, old_col, new_col)
# =============================================================================
COLUMN_RENAMES = [
    # questions
    ("questions", "question_type", "questionType"),
    ("questions", "ideal_answer", "idealAnswer"),
    ("questions", "created_at", "createdAt"),
    ("questions", "updated_at", "updatedAt"),

    # cvAnalyses
    ("cvAnalyses", "candidate_id", "candidateId"),
    ("cvAnalyses", "created_at", "createdAt"),
    ("cvAnalyses", "deleted_at", "deletedAt"),

    # cvSkills
    ("cvSkills", "cv_analysis_id", "cvAnalysisId"),
    ("cvSkills", "skill_name", "skillName"),
    ("cvSkills", "proficiency_level", "proficiencyLevel"),
    ("cvSkills", "years_of_experience", "yearsOfExperience"),
    ("cvSkills", "is_primary", "isPrimary"),
    ("cvSkills", "created_at", "createdAt"),

    # interviews
    ("interviews", "candidate_id", "candidateId"),
    ("interviews", "cv_analysis_id", "cvAnalysisId"),
    ("interviews", "current_question_index", "currentQuestionIndex"),
    ("interviews", "plan_metadata", "planMetadata"),
    ("interviews", "current_parent_question_id", "currentParentQuestionId"),
    ("interviews", "current_followup_count", "currentFollowupCount"),
    ("interviews", "started_at", "startedAt"),
    ("interviews", "completed_at", "completedAt"),
    ("interviews", "created_at", "createdAt"),
    ("interviews", "updated_at", "updatedAt"),
    ("interviews", "deleted_at", "deletedAt"),

    # interviewQuestions
    ("interviewQuestions", "interview_id", "interviewId"),
    ("interviewQuestions", "question_id", "questionId"),
    ("interviewQuestions", "sequence_order", "sequenceOrder"),
    ("interviewQuestions", "asked_at", "askedAt"),
    ("interviewQuestions", "skip_reason", "skipReason"),
    ("interviewQuestions", "created_at", "createdAt"),

    # answers
    ("answers", "interview_id", "interviewId"),
    ("answers", "question_id", "questionId"),
    ("answers", "follow_up_question_id", "followUpQuestionId"),
    ("answers", "is_voice", "isVoice"),
    ("answers", "audio_file_path", "audioFilePath"),
    ("answers", "created_at", "createdAt"),

    # followUpQuestions
    ("followUpQuestions", "parent_question_id", "parentQuestionId"),
    ("followUpQuestions", "interview_id", "interviewId"),
    ("followUpQuestions", "generated_reason", "generatedReason"),
    ("followUpQuestions", "order_in_sequence", "orderInSequence"),
    ("followUpQuestions", "created_at", "createdAt"),

    # evaluations
    ("evaluations", "answer_id", "answerId"),
    ("evaluations", "raw_score", "rawScore"),
    ("evaluations", "theoretical_score", "theoreticalScore"),
    ("evaluations", "speaking_score", "speakingScore"),
    ("evaluations", "final_score", "finalScore"),
    ("evaluations", "similarity_score", "similarityScore"),
    ("evaluations", "voice_metrics", "voiceMetrics"),
    ("evaluations", "improvement_suggestions", "improvementSuggestions"),
    ("evaluations", "attempt_number", "attemptNumber"),
    ("evaluations", "parent_evaluation_id", "parentEvaluationId"),
    ("evaluations", "created_at", "createdAt"),
    ("evaluations", "evaluated_at", "evaluatedAt"),

    # evaluationGaps
    ("evaluationGaps", "evaluation_id", "evaluationId"),
    ("evaluationGaps", "created_at", "createdAt"),

    # promptTemplates
    ("promptTemplates", "is_active", "isActive"),
    ("promptTemplates", "parent_version_id", "parentVersionId"),
    ("promptTemplates", "change_summary", "changeSummary"),
    ("promptTemplates", "is_draft", "isDraft"),
    ("promptTemplates", "created_by", "createdBy"),
    ("promptTemplates", "system_prompt", "systemPrompt"),
    ("promptTemplates", "user_template", "userTemplate"),
    ("promptTemplates", "input_variables", "inputVariables"),
    ("promptTemplates", "partial_variables", "partialVariables"),
    ("promptTemplates", "output_schema", "outputSchema"),
    ("promptTemplates", "max_tokens", "maxTokens"),
    ("promptTemplates", "top_p", "topP"),
    ("promptTemplates", "frequency_penalty", "frequencyPenalty"),
    ("promptTemplates", "presence_penalty", "presencePenalty"),
    ("promptTemplates", "deleted_at", "deletedAt"),
    ("promptTemplates", "created_at", "createdAt"),

    # promptMetadataChanges
    ("promptMetadataChanges", "prompt_template_id", "promptTemplateId"),
    ("promptMetadataChanges", "field_name", "fieldName"),
    ("promptMetadataChanges", "old_value", "oldValue"),
    ("promptMetadataChanges", "new_value", "newValue"),
    ("promptMetadataChanges", "changed_by", "changedBy"),
    ("promptMetadataChanges", "changed_at", "changedAt"),

    # promptExecutions
    ("promptExecutions", "prompt_template_id", "promptTemplateId"),
    ("promptExecutions", "interview_id", "interviewId"),
    ("promptExecutions", "input_variables", "inputVariables"),
    ("promptExecutions", "output_text", "outputText"),
    ("promptExecutions", "prompt_tokens", "promptTokens"),
    ("promptExecutions", "completion_tokens", "completionTokens"),
    ("promptExecutions", "latency_ms", "latencyMs"),
    ("promptExecutions", "model_name", "modelName"),
    ("promptExecutions", "error_message", "errorMessage"),
    ("promptExecutions", "executed_at", "executedAt"),

    # feedbackRequest
    ("feedbackRequest", "entity_id", "entityId"),
    ("feedbackRequest", "input_type", "inputType"),
    ("feedbackRequest", "user_id", "userId"),
    ("feedbackRequest", "error_message", "errorMessage"),
    ("feedbackRequest", "feedback_input", "feedbackInput"),
    ("feedbackRequest", "created_at", "createdAt"),
    ("feedbackRequest", "updated_at", "updatedAt"),

    # feedbackResponse
    ("feedbackResponse", "feedback_request_id", "feedbackRequestId"),
    ("feedbackResponse", "result_json", "resultJson"),
    ("feedbackResponse", "prompt_execution_id", "promptExecutionId"),
    ("feedbackResponse", "created_at", "createdAt"),
]


# =============================================================================
# FK CONSTRAINTS TO DROP AND RECREATE
# =============================================================================
FK_CONSTRAINTS = [
    # (constraint_name, table, column, ref_table, ref_column, on_delete)
    # cvSkills
    ("cvSkills_cvAnalysisId_fkey", "cvSkills", "cvAnalysisId", "cvAnalyses", "id", "CASCADE"),

    # interviews
    ("interviews_cvAnalysisId_fkey", "interviews", "cvAnalysisId", "cvAnalyses", "id", "SET NULL"),

    # interviewQuestions
    ("interviewQuestions_interviewId_fkey", "interviewQuestions", "interviewId", "interviews", "id", "CASCADE"),
    ("interviewQuestions_questionId_fkey", "interviewQuestions", "questionId", "questions", "id", "CASCADE"),

    # answers
    ("answers_interviewId_fkey", "answers", "interviewId", "interviews", "id", "CASCADE"),
    ("answers_questionId_fkey", "answers", "questionId", "questions", "id", "CASCADE"),
    ("answers_followUpQuestionId_fkey", "answers", "followUpQuestionId", "followUpQuestions", "id", "CASCADE"),

    # followUpQuestions
    ("followUpQuestions_parentQuestionId_fkey", "followUpQuestions", "parentQuestionId", "questions", "id", "CASCADE"),
    ("followUpQuestions_interviewId_fkey", "followUpQuestions", "interviewId", "interviews", "id", "CASCADE"),

    # evaluations
    ("evaluations_answerId_fkey", "evaluations", "answerId", "answers", "id", "CASCADE"),
    ("evaluations_parentEvaluationId_fkey", "evaluations", "parentEvaluationId", "evaluations", "id", "SET NULL"),

    # evaluationGaps
    ("evaluationGaps_evaluationId_fkey", "evaluationGaps", "evaluationId", "evaluations", "id", "CASCADE"),

    # promptTemplates (self-reference)
    ("promptTemplates_parentVersionId_fkey", "promptTemplates", "parentVersionId", "promptTemplates", "id", "SET NULL"),

    # promptMetadataChanges
    ("promptMetadataChanges_promptTemplateId_fkey", "promptMetadataChanges", "promptTemplateId", "promptTemplates", "id", "CASCADE"),

    # promptExecutions
    ("promptExecutions_promptTemplateId_fkey", "promptExecutions", "promptTemplateId", "promptTemplates", "id", "CASCADE"),
    ("promptExecutions_interviewId_fkey", "promptExecutions", "interviewId", "interviews", "id", "CASCADE"),

    # feedbackResponse
    ("feedbackResponse_feedbackRequestId_fkey", "feedbackResponse", "feedbackRequestId", "feedbackRequest", "id", "CASCADE"),
    ("feedbackResponse_promptExecutionId_fkey", "feedbackResponse", "promptExecutionId", "promptExecutions", "id", "SET NULL"),
]


def upgrade() -> None:
    """Rename tables and columns from snake_case to camelCase."""

    # =========================================================================
    # STEP 1: DROP VIEWS (must be dropped before table/column renames)
    # =========================================================================
    op.execute("DROP VIEW IF EXISTS cv_analysis_with_skills CASCADE")
    op.execute("DROP VIEW IF EXISTS interview_details CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS prompt_analytics_summary CASCADE")

    # =========================================================================
    # STEP 2: DROP TRIGGER (references old column names)
    # =========================================================================
    op.execute("DROP TRIGGER IF EXISTS trg_generate_template_json ON prompt_templates")
    op.execute("DROP FUNCTION IF EXISTS generate_template_json()")

    # =========================================================================
    # STEP 3: DROP ALL FOREIGN KEY CONSTRAINTS
    # =========================================================================
    # cvSkills
    op.drop_constraint("cv_skills_cv_analysis_id_fkey", "cv_skills", type_="foreignkey")

    # interviews
    op.drop_constraint("interviews_cv_analysis_id_fkey", "interviews", type_="foreignkey")

    # interviewQuestions
    op.drop_constraint("interview_questions_interview_id_fkey", "interview_questions", type_="foreignkey")
    op.drop_constraint("interview_questions_question_id_fkey", "interview_questions", type_="foreignkey")

    # answers
    op.drop_constraint("answers_interview_id_fkey", "answers", type_="foreignkey")
    op.drop_constraint("answers_question_id_fkey", "answers", type_="foreignkey")
    # Note: Migration 07 created this as 'fk_answers_follow_up_question_id', not 'answers_follow_up_question_id_fkey'
    op.execute("ALTER TABLE answers DROP CONSTRAINT IF EXISTS fk_answers_follow_up_question_id")

    # followUpQuestions
    op.drop_constraint("follow_up_questions_parent_question_id_fkey", "follow_up_questions", type_="foreignkey")
    op.drop_constraint("follow_up_questions_interview_id_fkey", "follow_up_questions", type_="foreignkey")

    # evaluations
    op.drop_constraint("evaluations_answer_id_fkey", "evaluations", type_="foreignkey")
    op.drop_constraint("evaluations_parent_evaluation_id_fkey", "evaluations", type_="foreignkey")

    # evaluationGaps
    op.drop_constraint("evaluation_gaps_evaluation_id_fkey", "evaluation_gaps", type_="foreignkey")

    # promptTemplates
    op.drop_constraint("prompt_templates_parent_version_id_fkey", "prompt_templates", type_="foreignkey")

    # promptMetadataChanges
    op.drop_constraint("prompt_metadata_changes_prompt_template_id_fkey", "prompt_metadata_changes", type_="foreignkey")

    # promptExecutions
    op.drop_constraint("prompt_executions_prompt_template_id_fkey", "prompt_executions", type_="foreignkey")
    op.drop_constraint("prompt_executions_interview_id_fkey", "prompt_executions", type_="foreignkey")

    # feedbackResponse
    op.drop_constraint("feedback_response_feedback_request_id_fkey", "feedback_response", type_="foreignkey")
    op.drop_constraint("feedback_response_prompt_execution_id_fkey", "feedback_response", type_="foreignkey")

    # =========================================================================
    # STEP 4: RENAME TABLES
    # =========================================================================
    for old_name, new_name in TABLE_RENAMES:
        op.rename_table(old_name, new_name)

    # =========================================================================
    # STEP 5: RENAME COLUMNS
    # =========================================================================
    for table, old_col, new_col in COLUMN_RENAMES:
        op.alter_column(table, old_col, new_column_name=new_col)

    # =========================================================================
    # STEP 6: RECREATE FOREIGN KEY CONSTRAINTS
    # =========================================================================
    for fk_name, table, col, ref_table, ref_col, on_delete in FK_CONSTRAINTS:
        op.create_foreign_key(
            fk_name, table, ref_table, [col], [ref_col], ondelete=on_delete
        )

    # =========================================================================
    # STEP 7: RECREATE VIEWS WITH CAMELCASE COLUMN NAMES
    # =========================================================================

    # interviewDetails view
    op.execute("""
        CREATE OR REPLACE VIEW "interviewDetails" AS
        SELECT
            i.id AS "interviewId",
            i."candidateId",
            i.status,
            i."cvAnalysisId",
            i."currentQuestionIndex",
            COUNT(DISTINCT iq.id) AS "totalQuestions",
            COUNT(DISTINCT iq."askedAt") AS "questionsAsked",
            COUNT(DISTINCT a.id) AS "answersSubmitted",
            i."startedAt",
            i."completedAt",
            i."createdAt",
            i."updatedAt"
        FROM interviews i
        LEFT JOIN "interviewQuestions" iq ON iq."interviewId" = i.id
        LEFT JOIN answers a ON a."interviewId" = i.id
        GROUP BY i.id
    """)

    # cvAnalysisWithSkills view
    op.execute("""
        CREATE OR REPLACE VIEW "cvAnalysisWithSkills" AS
        SELECT
            cv.id AS "cvAnalysisId",
            cv."candidateId",
            cv.summary,
            cv."createdAt",
            jsonb_agg(
                jsonb_build_object(
                    'id', s.id,
                    'skillName', s."skillName",
                    'proficiencyLevel', s."proficiencyLevel",
                    'yearsOfExperience', s."yearsOfExperience",
                    'isPrimary', s."isPrimary"
                ) ORDER BY s."isPrimary" DESC, s."skillName"
            ) FILTER (WHERE s.id IS NOT NULL) AS skills
        FROM "cvAnalyses" cv
        LEFT JOIN "cvSkills" s ON s."cvAnalysisId" = cv.id
        GROUP BY cv.id
    """)

    # promptAnalyticsSummary materialized view
    op.execute("""
        CREATE MATERIALIZED VIEW "promptAnalyticsSummary" AS
        SELECT
            pt.id AS "promptTemplateId",
            pt.name,
            pt.version,
            COUNT(pe.id) AS "totalExecutions",
            AVG(pe."promptTokens") AS "avgPromptTokens",
            AVG(pe."completionTokens") AS "avgCompletionTokens",
            AVG(pe."latencyMs") AS "avgLatencyMs",
            CASE
                WHEN COUNT(pe.id) > 0 THEN
                    SUM(CASE WHEN pe.success THEN 1 ELSE 0 END)::FLOAT / COUNT(pe.id)
                ELSE 0
            END AS "successRate",
            SUM(
                (COALESCE(pe."promptTokens", 0) * 0.03 / 1000.0) +
                (COALESCE(pe."completionTokens", 0) * 0.06 / 1000.0)
            ) AS "estimatedCostUsd",
            MAX(pe."executedAt") AS "lastExecutedAt"
        FROM "promptTemplates" pt
        LEFT JOIN "promptExecutions" pe ON pt.id = pe."promptTemplateId"
        GROUP BY pt.id, pt.name, pt.version
    """)

    op.execute("""
        CREATE UNIQUE INDEX "idx_analyticsSummary_templateId"
        ON "promptAnalyticsSummary"("promptTemplateId")
    """)

    op.execute("""
        CREATE INDEX "idx_analyticsSummary_name"
        ON "promptAnalyticsSummary"(name, version)
    """)

    # =========================================================================
    # STEP 8: TRIGGER HANDLING
    # =========================================================================
    # Note: Trigger was dropped in migration 13 along with template_json column.
    # No trigger recreation needed as template_json column no longer exists.


def downgrade() -> None:
    """Revert camelCase back to snake_case."""

    # Drop views
    op.execute('DROP VIEW IF EXISTS "cvAnalysisWithSkills" CASCADE')
    op.execute('DROP VIEW IF EXISTS "interviewDetails" CASCADE')
    op.execute('DROP MATERIALIZED VIEW IF EXISTS "promptAnalyticsSummary" CASCADE')

    # Drop trigger
    op.execute('DROP TRIGGER IF EXISTS trg_generate_template_json ON "promptTemplates"')
    op.execute('DROP FUNCTION IF EXISTS generate_template_json()')

    # Drop FK constraints (use camelCase names)
    for fk_name, table, col, ref_table, ref_col, on_delete in FK_CONSTRAINTS:
        op.drop_constraint(fk_name, table, type_="foreignkey")

    # Rename columns back (reverse order)
    for table, old_col, new_col in reversed(COLUMN_RENAMES):
        # In downgrade, swap old and new
        op.alter_column(table, new_col, new_column_name=old_col)

    # Rename tables back
    for old_name, new_name in reversed(TABLE_RENAMES):
        op.rename_table(new_name, old_name)

    # Recreate FK constraints with snake_case names
    # cvSkills
    op.create_foreign_key(
        "cv_skills_cv_analysis_id_fkey", "cv_skills", "cv_analyses", ["cv_analysis_id"], ["id"], ondelete="CASCADE"
    )

    # interviews
    op.create_foreign_key(
        "interviews_cv_analysis_id_fkey", "interviews", "cv_analyses", ["cv_analysis_id"], ["id"], ondelete="SET NULL"
    )

    # interviewQuestions
    op.create_foreign_key(
        "interview_questions_interview_id_fkey", "interview_questions", "interviews", ["interview_id"], ["id"], ondelete="CASCADE"
    )
    op.create_foreign_key(
        "interview_questions_question_id_fkey", "interview_questions", "questions", ["question_id"], ["id"], ondelete="CASCADE"
    )

    # answers
    op.create_foreign_key(
        "answers_interview_id_fkey", "answers", "interviews", ["interview_id"], ["id"], ondelete="CASCADE"
    )
    op.create_foreign_key(
        "answers_question_id_fkey", "answers", "questions", ["question_id"], ["id"], ondelete="CASCADE"
    )
    op.create_foreign_key(
        "answers_follow_up_question_id_fkey", "answers", "follow_up_questions", ["follow_up_question_id"], ["id"], ondelete="CASCADE"
    )

    # followUpQuestions
    op.create_foreign_key(
        "follow_up_questions_parent_question_id_fkey", "follow_up_questions", "questions", ["parent_question_id"], ["id"], ondelete="CASCADE"
    )
    op.create_foreign_key(
        "follow_up_questions_interview_id_fkey", "follow_up_questions", "interviews", ["interview_id"], ["id"], ondelete="CASCADE"
    )

    # evaluations
    op.create_foreign_key(
        "evaluations_answer_id_fkey", "evaluations", "answers", ["answer_id"], ["id"], ondelete="CASCADE"
    )
    op.create_foreign_key(
        "evaluations_parent_evaluation_id_fkey", "evaluations", "evaluations", ["parent_evaluation_id"], ["id"], ondelete="SET NULL"
    )

    # evaluationGaps
    op.create_foreign_key(
        "evaluation_gaps_evaluation_id_fkey", "evaluation_gaps", "evaluations", ["evaluation_id"], ["id"], ondelete="CASCADE"
    )

    # promptTemplates
    op.create_foreign_key(
        "prompt_templates_parent_version_id_fkey", "prompt_templates", "prompt_templates", ["parent_version_id"], ["id"], ondelete="SET NULL"
    )

    # promptMetadataChanges
    op.create_foreign_key(
        "prompt_metadata_changes_prompt_template_id_fkey", "prompt_metadata_changes", "prompt_templates", ["prompt_template_id"], ["id"], ondelete="CASCADE"
    )

    # promptExecutions
    op.create_foreign_key(
        "prompt_executions_prompt_template_id_fkey", "prompt_executions", "prompt_templates", ["prompt_template_id"], ["id"], ondelete="CASCADE"
    )
    op.create_foreign_key(
        "prompt_executions_interview_id_fkey", "prompt_executions", "interviews", ["interview_id"], ["id"], ondelete="CASCADE"
    )

    # feedbackResponse
    op.create_foreign_key(
        "feedback_response_feedback_request_id_fkey", "feedback_response", "feedback_request", ["feedback_request_id"], ["id"], ondelete="CASCADE"
    )
    op.create_foreign_key(
        "feedback_response_prompt_execution_id_fkey", "feedback_response", "prompt_executions", ["prompt_execution_id"], ["id"], ondelete="SET NULL"
    )

    # Recreate views with snake_case
    # interview_details view
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

    # cv_analysis_with_skills view
    op.execute("""
        CREATE OR REPLACE VIEW cv_analysis_with_skills AS
        SELECT
            cv.id AS cv_analysis_id,
            cv.candidate_id,
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

    # prompt_analytics_summary materialized view
    op.execute("""
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
    """)

    op.execute("""
        CREATE UNIQUE INDEX idx_analytics_summary_template_id
        ON prompt_analytics_summary(prompt_template_id)
    """)

    op.execute("""
        CREATE INDEX idx_analytics_summary_name
        ON prompt_analytics_summary(name, version)
    """)

