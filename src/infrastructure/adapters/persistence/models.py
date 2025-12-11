"""SQLAlchemy models for persistence.

These models represent the database schema and map domain entities
to database tables using SQLAlchemy ORM.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy import (
    Enum as SQLEnum,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.domain.models.interview import InterviewStatus
from src.domain.models.question import Difficulty, DifficultyLevel, QuestionType
from src.domain.models.cv_skill import ProficiencyLevel
from src.domain.models.feedback_result import FeedbackStatus, InputType
from src.infrastructure.database.base import Base


class CVSkillModel(Base):
    """SQLAlchemy model for CV Skill entity (normalized from JSONB)."""

    __tablename__ = "cvSkills"

    id: Mapped[UUID] = mapped_column("id", PGUUID(as_uuid=True), primary_key=True)
    cv_analysis_id: Mapped[UUID] = mapped_column(
        "cvAnalysisId",
        PGUUID(as_uuid=True),
        ForeignKey("cvAnalyses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    skill_name: Mapped[str] = mapped_column("skillName", String(100), nullable=False)
    proficiency_level: Mapped[str | None] = mapped_column(
        "proficiencyLevel",
        SQLEnum(
            ProficiencyLevel,
            native_enum=False,
            length=50,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=True,
    )
    years_of_experience: Mapped[float | None] = mapped_column("yearsOfExperience", Float, nullable=True)
    is_primary: Mapped[bool] = mapped_column("isPrimary", Boolean, server_default="false", nullable=False)
    created_at: Mapped[datetime] = mapped_column("createdAt", DateTime, nullable=False)

    # Relationships
    cv_analysis: Mapped["CVAnalysisModel"] = relationship(
        "CVAnalysisModel",
        back_populates="skills",
    )

    __table_args__ = (
        Index("idx_cvSkills_cvAnalysisId", "cvAnalysisId"),
        Index("idx_cvSkills_skillName", "skillName"),
        Index("idx_cvSkills_proficiencyLevel", "proficiencyLevel"),
    )


class InterviewQuestionModel(Base):
    """SQLAlchemy model for Interview-Question junction table."""

    __tablename__ = "interviewQuestions"

    id: Mapped[UUID] = mapped_column("id", PGUUID(as_uuid=True), primary_key=True)
    interview_id: Mapped[UUID] = mapped_column(
        "interviewId",
        PGUUID(as_uuid=True),
        ForeignKey("interviews.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    question_id: Mapped[UUID] = mapped_column(
        "questionId",
        PGUUID(as_uuid=True),
        ForeignKey("questions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sequence_order: Mapped[int] = mapped_column("sequenceOrder", Integer, nullable=False)
    asked_at: Mapped[datetime | None] = mapped_column("askedAt", DateTime, nullable=True)
    skipped: Mapped[bool] = mapped_column("skipped", Boolean, server_default="false", nullable=False)
    skip_reason: Mapped[str | None] = mapped_column("skipReason", Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column("createdAt", DateTime, nullable=False)

    # Relationships
    interview: Mapped["InterviewModel"] = relationship(
        "InterviewModel",
        back_populates="interview_questions",
    )
    question: Mapped["QuestionModel"] = relationship("QuestionModel")

    __table_args__ = (
        Index("idx_interviewQuestions_interviewId", "interviewId", "sequenceOrder"),
        Index("idx_interviewQuestions_questionId", "questionId"),
        Index("idx_interviewQuestions_askedAt", "askedAt"),
    )


class QuestionModel(Base):
    """SQLAlchemy model for Question entity."""

    __tablename__ = "questions"

    id: Mapped[UUID] = mapped_column("id", PGUUID(as_uuid=True), primary_key=True)
    text: Mapped[str] = mapped_column("text", Text, nullable=False)
    question_type: Mapped[str] = mapped_column(
        "questionType",
        SQLEnum(
            QuestionType,
            native_enum=False,
            length=50,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        index=True,
    )
    difficulty: Mapped[str] = mapped_column(
        "difficulty",
        SQLEnum(
            Difficulty,
            native_enum=False,
            length=50,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        index=True,
    )
    skills: Mapped[list[str]] = mapped_column("skills", ARRAY(String(100)), nullable=False, default=[])

    # Pre-planning fields for adaptive interviews
    ideal_answer: Mapped[str | None] = mapped_column("idealAnswer", Text, nullable=True)
    rationale: Mapped[str | None] = mapped_column("rationale", Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column("createdAt", DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column("updatedAt", DateTime, nullable=False)

    # Relationships
    answers: Mapped[list["AnswerModel"]] = relationship(
        "AnswerModel",
        back_populates="question",
    )

    __table_args__ = (
        Index("idx_questions_questionType", "questionType"),
        Index("idx_questions_difficulty", "difficulty"),
        Index("idx_questions_skills", "skills", postgresql_using="gin"),
    )


class InterviewModel(Base):
    """SQLAlchemy model for Interview entity."""

    __tablename__ = "interviews"

    id: Mapped[UUID] = mapped_column("id", PGUUID(as_uuid=True), primary_key=True)
    # Candidate ID is now a plain UUID (no FK) - candidate data owned by separate service
    candidate_id: Mapped[UUID] = mapped_column(
        "candidateId",
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    # Human-friendly interview title for history and UI display
    title: Mapped[str | None] = mapped_column("title", String(150), nullable=True)
    status: Mapped[str] = mapped_column(
        "status",
        SQLEnum(InterviewStatus, native_enum=False, length=50),
        nullable=False,
        index=True,
    )
    cv_analysis_id: Mapped[UUID | None] = mapped_column(
        "cvAnalysisId",
        PGUUID(as_uuid=True),
        ForeignKey("cvAnalyses.id", ondelete="SET NULL"),
        nullable=True,
    )
    current_question_index: Mapped[int] = mapped_column("currentQuestionIndex", Integer, nullable=False, default=0)

    # NEW: Pre-planning metadata for adaptive interviews
    plan_metadata: Mapped[dict] = mapped_column("planMetadata", JSONB, nullable=False, default={})

    # NEW: Follow-up tracking for current session
    current_parent_question_id: Mapped[UUID | None] = mapped_column(
        "currentParentQuestionId",
        PGUUID(as_uuid=True),
        nullable=True,
        default=None,
    )
    current_followup_count: Mapped[int] = mapped_column(
        "currentFollowupCount",
        Integer,
        nullable=False,
        default=0,
    )

    started_at: Mapped[datetime | None] = mapped_column("startedAt", DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column("completedAt", DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column("createdAt", DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column("updatedAt", DateTime, nullable=False)
    # Soft delete support (managed via repository methods)
    deleted_at: Mapped[datetime | None] = mapped_column("deletedAt", DateTime, nullable=True)

    # Relationships
    cv_analysis: Mapped["CVAnalysisModel | None"] = relationship(
        "CVAnalysisModel",
        foreign_keys=[cv_analysis_id],
    )
    answers: Mapped[list["AnswerModel"]] = relationship(
        "AnswerModel",
        back_populates="interview",
        cascade="all, delete-orphan",
    )
    interview_questions: Mapped[list["InterviewQuestionModel"]] = relationship(
        "InterviewQuestionModel",
        back_populates="interview",
        cascade="all, delete-orphan",
        order_by="InterviewQuestionModel.sequence_order",
    )

    __table_args__ = (
        Index("idx_interviews_candidateId", "candidateId"),
        Index("idx_interviews_status", "status"),
        Index("idx_interviews_createdAt", "createdAt"),
    )


class AnswerModel(Base):
    """SQLAlchemy model for Answer entity."""

    __tablename__ = "answers"

    id: Mapped[UUID] = mapped_column("id", PGUUID(as_uuid=True), primary_key=True)
    interview_id: Mapped[UUID] = mapped_column(
        "interviewId",
        PGUUID(as_uuid=True),
        ForeignKey("interviews.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    question_id: Mapped[UUID] = mapped_column(
        "questionId",
        PGUUID(as_uuid=True),
        ForeignKey("questions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    follow_up_question_id: Mapped[UUID | None] = mapped_column(
        "followUpQuestionId",
        PGUUID(as_uuid=True),
        ForeignKey("followUpQuestions.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    text: Mapped[str] = mapped_column("text", Text, nullable=False)
    is_voice: Mapped[bool] = mapped_column("isVoice", Boolean, nullable=False, default=False)
    audio_file_path: Mapped[str | None] = mapped_column("audioFilePath", String(500), nullable=True)

    # Note: voice_metrics is not stored in database yet (will be stored in Evaluation entity in future)
    # It exists in the domain model but is handled by the mapper (set to None when reading from DB)

    created_at: Mapped[datetime] = mapped_column("createdAt", DateTime, nullable=False)

    # Relationships
    interview: Mapped["InterviewModel"] = relationship(
        "InterviewModel",
        back_populates="answers",
    )
    question: Mapped["QuestionModel"] = relationship(
        "QuestionModel",
        back_populates="answers",
    )
    follow_up_question: Mapped["FollowUpQuestionModel | None"] = relationship(
        "FollowUpQuestionModel",
        foreign_keys=[follow_up_question_id],
    )

    __table_args__ = (
        Index("idx_answers_interviewId", "interviewId"),
        Index("idx_answers_questionId", "questionId"),
        Index("idx_answers_followUpQuestionId", "followUpQuestionId"),
        Index("idx_answers_createdAt", "createdAt"),
    )


class CVAnalysisModel(Base):
    """SQLAlchemy model for CV Analysis entity."""

    __tablename__ = "cvAnalyses"

    id: Mapped[UUID] = mapped_column("id", PGUUID(as_uuid=True), primary_key=True)
    # Candidate ID is now a plain UUID (no FK) - candidate data owned by separate service
    candidate_id: Mapped[UUID] = mapped_column(
        "candidateId",
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    summary: Mapped[str | None] = mapped_column("summary", Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column("createdAt", DateTime, nullable=False)
    # Soft delete support (managed via repository methods)
    deleted_at: Mapped[datetime | None] = mapped_column("deletedAt", DateTime, nullable=True)

    # Relationships
    skills: Mapped[list["CVSkillModel"]] = relationship(
        "CVSkillModel",
        back_populates="cv_analysis",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("idx_cvAnalyses_candidateId", "candidateId"),
        Index("idx_cvAnalyses_createdAt", "createdAt"),
    )


class FollowUpQuestionModel(Base):
    """SQLAlchemy model for FollowUpQuestion entity."""

    __tablename__ = "followUpQuestions"

    id: Mapped[UUID] = mapped_column("id", PGUUID(as_uuid=True), primary_key=True)
    parent_question_id: Mapped[UUID] = mapped_column(
        "parentQuestionId",
        PGUUID(as_uuid=True),
        ForeignKey("questions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    interview_id: Mapped[UUID] = mapped_column(
        "interviewId",
        PGUUID(as_uuid=True),
        ForeignKey("interviews.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    text: Mapped[str] = mapped_column("text", Text, nullable=False)
    generated_reason: Mapped[str] = mapped_column("generatedReason", Text, nullable=False)
    order_in_sequence: Mapped[int] = mapped_column("orderInSequence", Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column("createdAt", DateTime, nullable=False)

    __table_args__ = (
        Index("idx_followUpQuestions_parentQuestionId", "parentQuestionId"),
        Index("idx_followUpQuestions_interviewId", "interviewId"),
        Index("idx_followUpQuestions_createdAt", "createdAt"),
    )


class EvaluationModel(Base):
    """SQLAlchemy model for Evaluation entity."""

    __tablename__ = "evaluations"

    id: Mapped[UUID] = mapped_column("id", PGUUID(as_uuid=True), primary_key=True)
    answer_id: Mapped[UUID] = mapped_column(
        "answerId",
        PGUUID(as_uuid=True),
        ForeignKey("answers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Scores
    raw_score: Mapped[float] = mapped_column("rawScore", Float, nullable=False)
    penalty: Mapped[float] = mapped_column("penalty", Float, nullable=False, server_default="0")
    theoretical_score: Mapped[float | None] = mapped_column("theoreticalScore", Float, nullable=True)
    speaking_score: Mapped[float | None] = mapped_column("speakingScore", Float, nullable=True)
    final_score: Mapped[float] = mapped_column("finalScore", Float, nullable=False)
    similarity_score: Mapped[float | None] = mapped_column("similarityScore", Float, nullable=True)

    # LLM evaluation details
    completeness: Mapped[float] = mapped_column("completeness", Float, nullable=False)
    relevance: Mapped[float] = mapped_column("relevance", Float, nullable=False)
    sentiment: Mapped[str | None] = mapped_column("sentiment", String(50), nullable=True)
    voice_metrics: Mapped[dict[str, float] | None] = mapped_column("voiceMetrics", JSONB, nullable=True)
    reasoning: Mapped[str | None] = mapped_column("reasoning", Text, nullable=True)
    strengths: Mapped[list[str]] = mapped_column(
        "strengths", ARRAY(Text), nullable=False, server_default="{}"
    )
    weaknesses: Mapped[list[str]] = mapped_column(
        "weaknesses", ARRAY(Text), nullable=False, server_default="{}"
    )
    improvement_suggestions: Mapped[list[str]] = mapped_column(
        "improvementSuggestions", ARRAY(Text), nullable=False, server_default="{}"
    )

    # Follow-up context
    attempt_number: Mapped[int] = mapped_column("attemptNumber", Integer, nullable=False, server_default="1")
    parent_evaluation_id: Mapped[UUID | None] = mapped_column(
        "parentEvaluationId",
        PGUUID(as_uuid=True),
        ForeignKey("evaluations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column("createdAt", DateTime, nullable=False)
    evaluated_at: Mapped[datetime | None] = mapped_column("evaluatedAt", DateTime, nullable=True)

    # Relationships
    gaps: Mapped[list["EvaluationGapModel"]] = relationship(
        "EvaluationGapModel",
        back_populates="evaluation",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("idx_evaluations_answerId", "answerId"),
        Index("idx_evaluations_parentEvaluationId", "parentEvaluationId"),
        Index("idx_evaluations_attemptNumber", "attemptNumber"),
    )


class EvaluationGapModel(Base):
    """SQLAlchemy model for EvaluationGap entity."""

    __tablename__ = "evaluationGaps"

    id: Mapped[UUID] = mapped_column("id", PGUUID(as_uuid=True), primary_key=True)
    evaluation_id: Mapped[UUID] = mapped_column(
        "evaluationId",
        PGUUID(as_uuid=True),
        ForeignKey("evaluations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    concept: Mapped[str] = mapped_column("concept", Text, nullable=False)
    severity: Mapped[str] = mapped_column("severity", String(20), nullable=False, server_default="'moderate'")
    resolved: Mapped[bool] = mapped_column("resolved", Boolean, nullable=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column("createdAt", DateTime, nullable=False)

    # Relationships
    evaluation: Mapped["EvaluationModel"] = relationship(
        "EvaluationModel",
        back_populates="gaps",
    )

    __table_args__ = (
        Index("idx_evaluationGaps_evaluationId", "evaluationId"),
        Index("idx_evaluationGaps_resolved", "resolved"),
    )


class PromptTemplateModel(Base):
    """SQLAlchemy model for PromptTemplate entity (decomposed schema)."""

    __tablename__ = "promptTemplates"

    id: Mapped[UUID] = mapped_column("id", PGUUID(as_uuid=True), primary_key=True)
    prompt_name: Mapped[str] = mapped_column("name", String(100), nullable=False)
    version: Mapped[int] = mapped_column("version", Integer, nullable=False, server_default="1")
    is_active: Mapped[bool] = mapped_column("isActive", Boolean, nullable=False, server_default="false")

    # Version control and lineage
    parent_version_id: Mapped[UUID | None] = mapped_column(
        "parentVersionId",
        PGUUID(as_uuid=True),
        ForeignKey("promptTemplates.id", ondelete="SET NULL"),
        nullable=True,
    )
    change_summary: Mapped[str | None] = mapped_column("changeSummary", Text, nullable=True)
    is_draft: Mapped[bool] = mapped_column("isDraft", Boolean, nullable=False, server_default="true")
    created_by: Mapped[str | None] = mapped_column("createdBy", String(100), nullable=True)

    # Decomposed prompt structure (editable fields)
    system_prompt: Mapped[str] = mapped_column("systemPrompt", Text, nullable=False)
    user_template: Mapped[str] = mapped_column("userTemplate", Text, nullable=False)
    input_variables: Mapped[list[str]] = mapped_column(
        "inputVariables",
        ARRAY(String),
        nullable=False,
        server_default="{}",
    )
    partial_variables: Mapped[dict] = mapped_column("partialVariables", JSONB, nullable=False, server_default="{}")
    output_schema: Mapped[dict] = mapped_column("outputSchema", JSONB, nullable=False)

    # Model parameters
    temperature: Mapped[float] = mapped_column("temperature", Numeric(3, 2), nullable=False, server_default="0.30")
    max_tokens: Mapped[int] = mapped_column("maxTokens", Integer, nullable=False, server_default="2000")
    top_p: Mapped[float] = mapped_column("topP", Numeric(3, 2), nullable=False, server_default="0.95")
    frequency_penalty: Mapped[float] = mapped_column("frequencyPenalty", Numeric(3, 2), nullable=False, server_default="0.00")
    presence_penalty: Mapped[float] = mapped_column("presencePenalty", Numeric(3, 2), nullable=False, server_default="0.00")

    # Soft delete
    deleted_at: Mapped[datetime | None] = mapped_column("deletedAt", DateTime, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column("createdAt", DateTime, nullable=False)

    # Relationships
    executions: Mapped[list["PromptExecutionModel"]] = relationship(
        "PromptExecutionModel",
        back_populates="prompt_template",
        cascade="all, delete-orphan",
    )
    metadata_changes: Mapped[list["PromptMetadataChangeModel"]] = relationship(
        "PromptMetadataChangeModel",
        back_populates="prompt_template",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("idx_promptTemplates_name", "name"),
        Index("idx_promptTemplates_version", "name", "version"),
        Index("idx_promptTemplates_parentVersionId", "parentVersionId"),
        Index("idx_promptTemplates_deletedAt", "deletedAt"),
    )


class PromptMetadataChangeModel(Base):
    """SQLAlchemy model for PromptMetadataChange entity."""

    __tablename__ = "promptMetadataChanges"

    id: Mapped[UUID] = mapped_column("id", PGUUID(as_uuid=True), primary_key=True)
    prompt_template_id: Mapped[UUID] = mapped_column(
        "promptTemplateId",
        PGUUID(as_uuid=True),
        ForeignKey("promptTemplates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    field_name: Mapped[str] = mapped_column("fieldName", String(50), nullable=False)
    old_value: Mapped[str | None] = mapped_column("oldValue", Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column("newValue", Text, nullable=True)
    changed_by: Mapped[str] = mapped_column("changedBy", String(100), nullable=False)
    changed_at: Mapped[datetime] = mapped_column("changedAt", DateTime, nullable=False)

    # Relationships
    prompt_template: Mapped["PromptTemplateModel"] = relationship(
        "PromptTemplateModel",
        back_populates="metadata_changes",
    )

    __table_args__ = (
        Index("idx_promptMetadataChanges_templateId", "promptTemplateId", "changedAt"),
    )


class PromptExecutionModel(Base):
    """SQLAlchemy model for PromptExecution entity."""

    __tablename__ = "promptExecutions"

    id: Mapped[UUID] = mapped_column("id", PGUUID(as_uuid=True), primary_key=True)
    prompt_template_id: Mapped[UUID] = mapped_column(
        "promptTemplateId",
        PGUUID(as_uuid=True),
        ForeignKey("promptTemplates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    interview_id: Mapped[UUID | None] = mapped_column(
        "interviewId",
        PGUUID(as_uuid=True),
        ForeignKey("interviews.id", ondelete="CASCADE"),
        nullable=True,
    )
    input_variables: Mapped[dict] = mapped_column("inputVariables", JSONB, nullable=False)
    output_text: Mapped[str | None] = mapped_column("outputText", Text, nullable=True)
    prompt_tokens: Mapped[int | None] = mapped_column("promptTokens", Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column("completionTokens", Integer, nullable=True)
    latency_ms: Mapped[int] = mapped_column("latencyMs", Integer, nullable=False)
    model_name: Mapped[str | None] = mapped_column("modelName", String(50), nullable=True)
    success: Mapped[bool] = mapped_column("success", Boolean, nullable=False)
    error_message: Mapped[str | None] = mapped_column("errorMessage", Text, nullable=True)
    executed_at: Mapped[datetime] = mapped_column("executedAt", DateTime, nullable=False)

    # Relationships
    prompt_template: Mapped["PromptTemplateModel"] = relationship(
        "PromptTemplateModel",
        back_populates="executions",
    )

    __table_args__ = (
        Index("idx_promptExecutions_templateId", "promptTemplateId", "executedAt"),
        Index("idx_promptExecutions_success", "success", "executedAt"),
    )


class PromptAnalyticsSummaryModel(Base):
    """SQLAlchemy model for prompt_analytics_summary materialized view (read-only)."""

    __tablename__ = "promptAnalyticsSummary"

    prompt_template_id: Mapped[UUID] = mapped_column("promptTemplateId", PGUUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column("name", String(100), nullable=False)
    version: Mapped[int] = mapped_column("version", Integer, nullable=False)
    total_executions: Mapped[int] = mapped_column("totalExecutions", Integer, nullable=False)
    avg_prompt_tokens: Mapped[float | None] = mapped_column("avgPromptTokens", Float, nullable=True)
    avg_completion_tokens: Mapped[float | None] = mapped_column("avgCompletionTokens", Float, nullable=True)
    avg_latency_ms: Mapped[float | None] = mapped_column("avgLatencyMs", Float, nullable=True)
    success_rate: Mapped[float] = mapped_column("successRate", Float, nullable=False)
    estimated_cost_usd: Mapped[float] = mapped_column("estimatedCostUsd", Float, nullable=False)
    last_executed_at: Mapped[datetime | None] = mapped_column("lastExecutedAt", DateTime, nullable=True)


class FeedbackRequestModel(Base):
    """SQLAlchemy model for feedback requests."""

    __tablename__ = "feedbackRequest"

    id: Mapped[UUID] = mapped_column("id", PGUUID(as_uuid=True), primary_key=True)
    entity_id: Mapped[UUID] = mapped_column("entityId", PGUUID(as_uuid=True), nullable=False)
    input_type: Mapped[str] = mapped_column(
        "inputType",
        SQLEnum(
            InputType,
            native_enum=False,
            length=20,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    user_id: Mapped[UUID | None] = mapped_column("userId", PGUUID(as_uuid=True), nullable=True)
    status: Mapped[str] = mapped_column(
        "status",
        SQLEnum(
            FeedbackStatus,
            native_enum=False,
            length=20,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        server_default="PENDING",
    )
    error_message: Mapped[str | None] = mapped_column("errorMessage", Text, nullable=True)
    feedback_input: Mapped[str] = mapped_column("feedbackInput", Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column("createdAt", DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column("updatedAt", DateTime, nullable=False)

    # 1:1 relationship
    response: Mapped["FeedbackResponseModel | None"] = relationship(
        "FeedbackResponseModel",
        back_populates="request",
        uselist=False,
    )


class FeedbackResponseModel(Base):
    """SQLAlchemy model for feedback responses."""

    __tablename__ = "feedbackResponse"

    id: Mapped[UUID] = mapped_column("id", PGUUID(as_uuid=True), primary_key=True)
    feedback_request_id: Mapped[UUID] = mapped_column(
        "feedbackRequestId",
        PGUUID(as_uuid=True),
        ForeignKey("feedbackRequest.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    result_json: Mapped[dict] = mapped_column("resultJson", JSONB, nullable=False)
    prompt_execution_id: Mapped[UUID | None] = mapped_column(
        "promptExecutionId",
        PGUUID(as_uuid=True),
        ForeignKey("promptExecutions.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column("createdAt", DateTime, nullable=False)

    # Relationships
    request: Mapped["FeedbackRequestModel"] = relationship(
        "FeedbackRequestModel",
        back_populates="response",
    )
