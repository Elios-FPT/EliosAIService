"""Rename all tables and columns from camelCase to PascalCase.

Revision ID: 20
Revises: 19
Create Date: 2025-12-12

Single atomic migration for company-wide database naming standard.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20"
down_revision: Union[str, Sequence[str], None] = "19"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# =============================================================================
# TABLE RENAME MAPPING (camelCase → PascalCase)
# =============================================================================
TABLE_RENAMES = [
    # Multi-word tables
    ("cvAnalyses", "CvAnalyses"),
    ("cvSkills", "CvSkills"),
    ("interviewQuestions", "InterviewQuestions"),
    ("followUpQuestions", "FollowUpQuestions"),
    ("evaluationGaps", "EvaluationGaps"),
    ("promptTemplates", "PromptTemplates"),
    ("promptMetadataChanges", "PromptMetadataChanges"),
    ("promptExecutions", "PromptExecutions"),
    ("feedbackRequest", "FeedbackRequest"),
    ("feedbackResponse", "FeedbackResponse"),
    # Single-word tables
    ("questions", "Questions"),
    ("interviews", "Interviews"),
    ("answers", "Answers"),
    ("evaluations", "Evaluations"),
]


# =============================================================================
# COLUMN RENAME MAPPING (table_PascalCase, old_camelCase, new_PascalCase)
# =============================================================================
COLUMN_RENAMES = [
    # Questions
    ("Questions", "id", "Id"),
    ("Questions", "questionType", "QuestionType"),
    ("Questions", "idealAnswer", "IdealAnswer"),
    ("Questions", "createdAt", "CreatedAt"),
    ("Questions", "updatedAt", "UpdatedAt"),

    # CvAnalyses
    ("CvAnalyses", "id", "Id"),
    ("CvAnalyses", "candidateId", "CandidateId"),
    ("CvAnalyses", "createdAt", "CreatedAt"),
    ("CvAnalyses", "deletedAt", "DeletedAt"),

    # CvSkills
    ("CvSkills", "id", "Id"),
    ("CvSkills", "cvAnalysisId", "CvAnalysisId"),
    ("CvSkills", "skillName", "SkillName"),
    ("CvSkills", "proficiencyLevel", "ProficiencyLevel"),
    ("CvSkills", "yearsOfExperience", "YearsOfExperience"),
    ("CvSkills", "isPrimary", "IsPrimary"),
    ("CvSkills", "createdAt", "CreatedAt"),

    # Interviews
    ("Interviews", "id", "Id"),
    ("Interviews", "candidateId", "CandidateId"),
    ("Interviews", "cvAnalysisId", "CvAnalysisId"),
    ("Interviews", "currentQuestionIndex", "CurrentQuestionIndex"),
    ("Interviews", "planMetadata", "PlanMetadata"),
    ("Interviews", "currentParentQuestionId", "CurrentParentQuestionId"),
    ("Interviews", "currentFollowupCount", "CurrentFollowupCount"),
    ("Interviews", "startedAt", "StartedAt"),
    ("Interviews", "completedAt", "CompletedAt"),
    ("Interviews", "createdAt", "CreatedAt"),
    ("Interviews", "updatedAt", "UpdatedAt"),
    ("Interviews", "deletedAt", "DeletedAt"),

    # InterviewQuestions
    ("InterviewQuestions", "id", "Id"),
    ("InterviewQuestions", "interviewId", "InterviewId"),
    ("InterviewQuestions", "questionId", "QuestionId"),
    ("InterviewQuestions", "sequenceOrder", "SequenceOrder"),
    ("InterviewQuestions", "askedAt", "AskedAt"),
    ("InterviewQuestions", "skipReason", "SkipReason"),
    ("InterviewQuestions", "createdAt", "CreatedAt"),

    # Answers
    ("Answers", "id", "Id"),
    ("Answers", "interviewId", "InterviewId"),
    ("Answers", "questionId", "QuestionId"),
    ("Answers", "followUpQuestionId", "FollowUpQuestionId"),
    ("Answers", "isVoice", "IsVoice"),
    ("Answers", "audioFilePath", "AudioFilePath"),
    ("Answers", "createdAt", "CreatedAt"),

    # FollowUpQuestions
    ("FollowUpQuestions", "id", "Id"),
    ("FollowUpQuestions", "parentQuestionId", "ParentQuestionId"),
    ("FollowUpQuestions", "interviewId", "InterviewId"),
    ("FollowUpQuestions", "generatedReason", "GeneratedReason"),
    ("FollowUpQuestions", "orderInSequence", "OrderInSequence"),
    ("FollowUpQuestions", "createdAt", "CreatedAt"),

    # Evaluations
    ("Evaluations", "id", "Id"),
    ("Evaluations", "answerId", "AnswerId"),
    ("Evaluations", "rawScore", "RawScore"),
    ("Evaluations", "theoreticalScore", "TheoreticalScore"),
    ("Evaluations", "speakingScore", "SpeakingScore"),
    ("Evaluations", "finalScore", "FinalScore"),
    ("Evaluations", "similarityScore", "SimilarityScore"),
    ("Evaluations", "voiceMetrics", "VoiceMetrics"),
    ("Evaluations", "improvementSuggestions", "ImprovementSuggestions"),
    ("Evaluations", "attemptNumber", "AttemptNumber"),
    ("Evaluations", "parentEvaluationId", "ParentEvaluationId"),
    ("Evaluations", "createdAt", "CreatedAt"),
    ("Evaluations", "evaluatedAt", "EvaluatedAt"),

    # EvaluationGaps
    ("EvaluationGaps", "id", "Id"),
    ("EvaluationGaps", "evaluationId", "EvaluationId"),
    ("EvaluationGaps", "createdAt", "CreatedAt"),

    # PromptTemplates
    ("PromptTemplates", "id", "Id"),
    ("PromptTemplates", "isActive", "IsActive"),
    ("PromptTemplates", "parentVersionId", "ParentVersionId"),
    ("PromptTemplates", "changeSummary", "ChangeSummary"),
    ("PromptTemplates", "isDraft", "IsDraft"),
    ("PromptTemplates", "createdBy", "CreatedBy"),
    ("PromptTemplates", "systemPrompt", "SystemPrompt"),
    ("PromptTemplates", "userTemplate", "UserTemplate"),
    ("PromptTemplates", "inputVariables", "InputVariables"),
    ("PromptTemplates", "partialVariables", "PartialVariables"),
    ("PromptTemplates", "outputSchema", "OutputSchema"),
    ("PromptTemplates", "maxTokens", "MaxTokens"),
    ("PromptTemplates", "topP", "TopP"),
    ("PromptTemplates", "frequencyPenalty", "FrequencyPenalty"),
    ("PromptTemplates", "presencePenalty", "PresencePenalty"),
    ("PromptTemplates", "deletedAt", "DeletedAt"),
    ("PromptTemplates", "createdAt", "CreatedAt"),

    # PromptMetadataChanges
    ("PromptMetadataChanges", "id", "Id"),
    ("PromptMetadataChanges", "promptTemplateId", "PromptTemplateId"),
    ("PromptMetadataChanges", "fieldName", "FieldName"),
    ("PromptMetadataChanges", "oldValue", "OldValue"),
    ("PromptMetadataChanges", "newValue", "NewValue"),
    ("PromptMetadataChanges", "changedBy", "ChangedBy"),
    ("PromptMetadataChanges", "changedAt", "ChangedAt"),

    # PromptExecutions
    ("PromptExecutions", "id", "Id"),
    ("PromptExecutions", "promptTemplateId", "PromptTemplateId"),
    ("PromptExecutions", "interviewId", "InterviewId"),
    ("PromptExecutions", "inputVariables", "InputVariables"),
    ("PromptExecutions", "outputText", "OutputText"),
    ("PromptExecutions", "promptTokens", "PromptTokens"),
    ("PromptExecutions", "completionTokens", "CompletionTokens"),
    ("PromptExecutions", "latencyMs", "LatencyMs"),
    ("PromptExecutions", "modelName", "ModelName"),
    ("PromptExecutions", "errorMessage", "ErrorMessage"),
    ("PromptExecutions", "executedAt", "ExecutedAt"),

    # FeedbackRequest
    ("FeedbackRequest", "id", "Id"),
    ("FeedbackRequest", "entityId", "EntityId"),
    ("FeedbackRequest", "inputType", "InputType"),
    ("FeedbackRequest", "userId", "UserId"),
    ("FeedbackRequest", "errorMessage", "ErrorMessage"),
    ("FeedbackRequest", "feedbackInput", "FeedbackInput"),
    ("FeedbackRequest", "createdAt", "CreatedAt"),
    ("FeedbackRequest", "updatedAt", "UpdatedAt"),

    # FeedbackResponse
    ("FeedbackResponse", "id", "Id"),
    ("FeedbackResponse", "feedbackRequestId", "FeedbackRequestId"),
    ("FeedbackResponse", "resultJson", "ResultJson"),
    ("FeedbackResponse", "promptExecutionId", "PromptExecutionId"),
    ("FeedbackResponse", "createdAt", "CreatedAt"),
]


# =============================================================================
# FK CONSTRAINTS TO DROP AND RECREATE (with PascalCase names)
# =============================================================================
FK_CONSTRAINTS = [
    # (constraint_name, table, column, ref_table, ref_column, on_delete)
    # CvSkills
    ("CvSkills_CvAnalysisId_fkey", "CvSkills", "CvAnalysisId", "CvAnalyses", "Id", "CASCADE"),

    # Interviews
    ("Interviews_CvAnalysisId_fkey", "Interviews", "CvAnalysisId", "CvAnalyses", "Id", "SET NULL"),

    # InterviewQuestions
    ("InterviewQuestions_InterviewId_fkey", "InterviewQuestions", "InterviewId", "Interviews", "Id", "CASCADE"),
    ("InterviewQuestions_QuestionId_fkey", "InterviewQuestions", "QuestionId", "Questions", "Id", "CASCADE"),

    # Answers
    ("Answers_InterviewId_fkey", "Answers", "InterviewId", "Interviews", "Id", "CASCADE"),
    ("Answers_QuestionId_fkey", "Answers", "QuestionId", "Questions", "Id", "CASCADE"),
    ("Answers_FollowUpQuestionId_fkey", "Answers", "FollowUpQuestionId", "FollowUpQuestions", "Id", "CASCADE"),

    # FollowUpQuestions
    ("FollowUpQuestions_ParentQuestionId_fkey", "FollowUpQuestions", "ParentQuestionId", "Questions", "Id", "CASCADE"),
    ("FollowUpQuestions_InterviewId_fkey", "FollowUpQuestions", "InterviewId", "Interviews", "Id", "CASCADE"),

    # Evaluations
    ("Evaluations_AnswerId_fkey", "Evaluations", "AnswerId", "Answers", "Id", "CASCADE"),
    ("Evaluations_ParentEvaluationId_fkey", "Evaluations", "ParentEvaluationId", "Evaluations", "Id", "SET NULL"),

    # EvaluationGaps
    ("EvaluationGaps_EvaluationId_fkey", "EvaluationGaps", "EvaluationId", "Evaluations", "Id", "CASCADE"),

    # PromptTemplates (self-reference)
    ("PromptTemplates_ParentVersionId_fkey", "PromptTemplates", "ParentVersionId", "PromptTemplates", "Id", "SET NULL"),

    # PromptMetadataChanges
    ("PromptMetadataChanges_PromptTemplateId_fkey", "PromptMetadataChanges", "PromptTemplateId", "PromptTemplates", "Id", "CASCADE"),

    # PromptExecutions
    ("PromptExecutions_PromptTemplateId_fkey", "PromptExecutions", "PromptTemplateId", "PromptTemplates", "Id", "CASCADE"),
    ("PromptExecutions_InterviewId_fkey", "PromptExecutions", "InterviewId", "Interviews", "Id", "CASCADE"),

    # FeedbackResponse
    ("FeedbackResponse_FeedbackRequestId_fkey", "FeedbackResponse", "FeedbackRequestId", "FeedbackRequest", "Id", "CASCADE"),
    ("FeedbackResponse_PromptExecutionId_fkey", "FeedbackResponse", "PromptExecutionId", "PromptExecutions", "Id", "SET NULL"),
]


def upgrade() -> None:
    """Rename tables and columns from camelCase to PascalCase."""

    # =========================================================================
    # STEP 1: DROP VIEWS (must be dropped before table/column renames)
    # =========================================================================
    op.execute('DROP VIEW IF EXISTS "interviewDetails" CASCADE')
    op.execute('DROP VIEW IF EXISTS "cvAnalysisWithSkills" CASCADE')
    op.execute('DROP MATERIALIZED VIEW IF EXISTS "promptAnalyticsSummary" CASCADE')

    # =========================================================================
    # STEP 2: DROP TRIGGER (references old column names)
    # =========================================================================
    op.execute('DROP TRIGGER IF EXISTS trg_generate_template_json ON "promptTemplates"')
    op.execute('DROP FUNCTION IF EXISTS generate_template_json()')

    # =========================================================================
    # STEP 3: DROP ALL FOREIGN KEY CONSTRAINTS
    # =========================================================================
    # CvSkills
    op.drop_constraint("cvSkills_cvAnalysisId_fkey", "cvSkills", type_="foreignkey")

    # Interviews
    op.drop_constraint("interviews_cvAnalysisId_fkey", "interviews", type_="foreignkey")

    # InterviewQuestions
    op.drop_constraint("interviewQuestions_interviewId_fkey", "interviewQuestions", type_="foreignkey")
    op.drop_constraint("interviewQuestions_questionId_fkey", "interviewQuestions", type_="foreignkey")

    # Answers
    op.drop_constraint("answers_interviewId_fkey", "answers", type_="foreignkey")
    op.drop_constraint("answers_questionId_fkey", "answers", type_="foreignkey")
    op.drop_constraint("answers_followUpQuestionId_fkey", "answers", type_="foreignkey")

    # FollowUpQuestions
    op.drop_constraint("followUpQuestions_parentQuestionId_fkey", "followUpQuestions", type_="foreignkey")
    op.drop_constraint("followUpQuestions_interviewId_fkey", "followUpQuestions", type_="foreignkey")

    # Evaluations
    op.drop_constraint("evaluations_answerId_fkey", "evaluations", type_="foreignkey")
    op.drop_constraint("evaluations_parentEvaluationId_fkey", "evaluations", type_="foreignkey")

    # EvaluationGaps
    op.drop_constraint("evaluationGaps_evaluationId_fkey", "evaluationGaps", type_="foreignkey")

    # PromptTemplates
    op.drop_constraint("promptTemplates_parentVersionId_fkey", "promptTemplates", type_="foreignkey")

    # PromptMetadataChanges
    op.drop_constraint("promptMetadataChanges_promptTemplateId_fkey", "promptMetadataChanges", type_="foreignkey")

    # PromptExecutions
    op.drop_constraint("promptExecutions_promptTemplateId_fkey", "promptExecutions", type_="foreignkey")
    op.drop_constraint("promptExecutions_interviewId_fkey", "promptExecutions", type_="foreignkey")

    # FeedbackResponse
    op.drop_constraint("feedbackResponse_feedbackRequestId_fkey", "feedbackResponse", type_="foreignkey")
    op.drop_constraint("feedbackResponse_promptExecutionId_fkey", "feedbackResponse", type_="foreignkey")

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
    # STEP 7: RECREATE VIEWS WITH PASCALCASE COLUMN NAMES
    # =========================================================================

    # InterviewDetails view
    op.execute("""
        CREATE OR REPLACE VIEW "InterviewDetails" AS
        SELECT
            i."Id" AS "InterviewId",
            i."CandidateId",
            i.status,
            i."CvAnalysisId",
            i."CurrentQuestionIndex",
            COUNT(DISTINCT iq."Id") AS "TotalQuestions",
            COUNT(DISTINCT iq."AskedAt") AS "QuestionsAsked",
            COUNT(DISTINCT a."Id") AS "AnswersSubmitted",
            i."StartedAt",
            i."CompletedAt",
            i."CreatedAt",
            i."UpdatedAt"
        FROM "Interviews" i
        LEFT JOIN "InterviewQuestions" iq ON iq."InterviewId" = i."Id"
        LEFT JOIN "Answers" a ON a."InterviewId" = i."Id"
        GROUP BY i."Id"
    """)

    # CvAnalysisWithSkills view
    op.execute("""
        CREATE OR REPLACE VIEW "CvAnalysisWithSkills" AS
        SELECT
            cv."Id" AS "CvAnalysisId",
            cv."CandidateId",
            cv.summary,
            cv."CreatedAt",
            jsonb_agg(
                jsonb_build_object(
                    'id', s."Id",
                    'skillName', s."SkillName",
                    'proficiencyLevel', s."ProficiencyLevel",
                    'yearsOfExperience', s."YearsOfExperience",
                    'isPrimary', s."IsPrimary"
                ) ORDER BY s."IsPrimary" DESC, s."SkillName"
            ) FILTER (WHERE s."Id" IS NOT NULL) AS skills
        FROM "CvAnalyses" cv
        LEFT JOIN "CvSkills" s ON s."CvAnalysisId" = cv."Id"
        GROUP BY cv."Id"
    """)

    # PromptAnalyticsSummary materialized view
    op.execute("""
        CREATE MATERIALIZED VIEW "PromptAnalyticsSummary" AS
        SELECT
            pt."Id" AS "PromptTemplateId",
            pt.name,
            pt.version,
            COUNT(pe."Id") AS "TotalExecutions",
            AVG(pe."PromptTokens") AS "AvgPromptTokens",
            AVG(pe."CompletionTokens") AS "AvgCompletionTokens",
            AVG(pe."LatencyMs") AS "AvgLatencyMs",
            CASE
                WHEN COUNT(pe."Id") > 0 THEN
                    SUM(CASE WHEN pe.success THEN 1 ELSE 0 END)::FLOAT / COUNT(pe."Id")
                ELSE 0
            END AS "SuccessRate",
            SUM(
                (COALESCE(pe."PromptTokens", 0) * 0.03 / 1000.0) +
                (COALESCE(pe."CompletionTokens", 0) * 0.06 / 1000.0)
            ) AS "EstimatedCostUsd",
            MAX(pe."ExecutedAt") AS "LastExecutedAt"
        FROM "PromptTemplates" pt
        LEFT JOIN "PromptExecutions" pe ON pt."Id" = pe."PromptTemplateId"
        GROUP BY pt."Id", pt.name, pt.version
    """)

    op.execute("""
        CREATE UNIQUE INDEX "Idx_AnalyticsSummary_TemplateId"
        ON "PromptAnalyticsSummary"("PromptTemplateId")
    """)

    op.execute("""
        CREATE INDEX "Idx_AnalyticsSummary_Name"
        ON "PromptAnalyticsSummary"(name, version)
    """)


def downgrade() -> None:
    """Revert PascalCase back to camelCase."""

    # Drop views
    op.execute('DROP VIEW IF EXISTS "CvAnalysisWithSkills" CASCADE')
    op.execute('DROP VIEW IF EXISTS "InterviewDetails" CASCADE')
    op.execute('DROP MATERIALIZED VIEW IF EXISTS "PromptAnalyticsSummary" CASCADE')

    # Drop trigger
    op.execute('DROP TRIGGER IF EXISTS trg_generate_template_json ON "PromptTemplates"')
    op.execute('DROP FUNCTION IF EXISTS generate_template_json()')

    # Drop FK constraints (use PascalCase names)
    for fk_name, table, col, ref_table, ref_col, on_delete in FK_CONSTRAINTS:
        op.drop_constraint(fk_name, table, type_="foreignkey")

    # Rename columns back (reverse order)
    for table, old_col, new_col in reversed(COLUMN_RENAMES):
        # In downgrade, swap old and new
        op.alter_column(table, new_col, new_column_name=old_col)

    # Rename tables back
    for old_name, new_name in reversed(TABLE_RENAMES):
        op.rename_table(new_name, old_name)

    # Recreate FK constraints with camelCase names
    # CvSkills
    op.create_foreign_key(
        "cvSkills_cvAnalysisId_fkey", "cvSkills", "cvAnalyses", ["cvAnalysisId"], ["id"], ondelete="CASCADE"
    )

    # Interviews
    op.create_foreign_key(
        "interviews_cvAnalysisId_fkey", "interviews", "cvAnalyses", ["cvAnalysisId"], ["id"], ondelete="SET NULL"
    )

    # InterviewQuestions
    op.create_foreign_key(
        "interviewQuestions_interviewId_fkey", "interviewQuestions", "interviews", ["interviewId"], ["id"], ondelete="CASCADE"
    )
    op.create_foreign_key(
        "interviewQuestions_questionId_fkey", "interviewQuestions", "questions", ["questionId"], ["id"], ondelete="CASCADE"
    )

    # Answers
    op.create_foreign_key(
        "answers_interviewId_fkey", "answers", "interviews", ["interviewId"], ["id"], ondelete="CASCADE"
    )
    op.create_foreign_key(
        "answers_questionId_fkey", "answers", "questions", ["questionId"], ["id"], ondelete="CASCADE"
    )
    op.create_foreign_key(
        "answers_followUpQuestionId_fkey", "answers", "followUpQuestions", ["followUpQuestionId"], ["id"], ondelete="CASCADE"
    )

    # FollowUpQuestions
    op.create_foreign_key(
        "followUpQuestions_parentQuestionId_fkey", "followUpQuestions", "questions", ["parentQuestionId"], ["id"], ondelete="CASCADE"
    )
    op.create_foreign_key(
        "followUpQuestions_interviewId_fkey", "followUpQuestions", "interviews", ["interviewId"], ["id"], ondelete="CASCADE"
    )

    # Evaluations
    op.create_foreign_key(
        "evaluations_answerId_fkey", "evaluations", "answers", ["answerId"], ["id"], ondelete="CASCADE"
    )
    op.create_foreign_key(
        "evaluations_parentEvaluationId_fkey", "evaluations", "evaluations", ["parentEvaluationId"], ["id"], ondelete="SET NULL"
    )

    # EvaluationGaps
    op.create_foreign_key(
        "evaluationGaps_evaluationId_fkey", "evaluationGaps", "evaluations", ["evaluationId"], ["id"], ondelete="CASCADE"
    )

    # PromptTemplates
    op.create_foreign_key(
        "promptTemplates_parentVersionId_fkey", "promptTemplates", "promptTemplates", ["parentVersionId"], ["id"], ondelete="SET NULL"
    )

    # PromptMetadataChanges
    op.create_foreign_key(
        "promptMetadataChanges_promptTemplateId_fkey", "promptMetadataChanges", "promptTemplates", ["promptTemplateId"], ["id"], ondelete="CASCADE"
    )

    # PromptExecutions
    op.create_foreign_key(
        "promptExecutions_promptTemplateId_fkey", "promptExecutions", "promptTemplates", ["promptTemplateId"], ["id"], ondelete="CASCADE"
    )
    op.create_foreign_key(
        "promptExecutions_interviewId_fkey", "promptExecutions", "interviews", ["interviewId"], ["id"], ondelete="CASCADE"
    )

    # FeedbackResponse
    op.create_foreign_key(
        "feedbackResponse_feedbackRequestId_fkey", "feedbackResponse", "feedbackRequest", ["feedbackRequestId"], ["id"], ondelete="CASCADE"
    )
    op.create_foreign_key(
        "feedbackResponse_promptExecutionId_fkey", "feedbackResponse", "promptExecutions", ["promptExecutionId"], ["id"], ondelete="SET NULL"
    )

    # Recreate views with camelCase
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

