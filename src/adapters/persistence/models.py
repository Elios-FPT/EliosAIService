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

from ...domain.models.interview import InterviewStatus
from ...domain.models.question import Difficulty, DifficultyLevel, QuestionType
from ...domain.models.cv_skill import ProficiencyLevel
from ...infrastructure.database.base import Base


class CandidateModel(Base):
    """SQLAlchemy model for Candidate entity."""

    __tablename__ = "candidates"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    cv_file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # Relationships
    interviews: Mapped[list["InterviewModel"]] = relationship(
        "InterviewModel",
        back_populates="candidate",
        cascade="all, delete-orphan",
    )
    cv_analyses: Mapped[list["CVAnalysisModel"]] = relationship(
        "CVAnalysisModel",
        back_populates="candidate",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("idx_candidates_email", "email"),
        Index("idx_candidates_created_at", "created_at"),
    )


class CVSkillModel(Base):
    """SQLAlchemy model for CV Skill entity (normalized from JSONB)."""

    __tablename__ = "cv_skills"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    cv_analysis_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("cv_analyses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    skill_name: Mapped[str] = mapped_column(String(100), nullable=False)
    proficiency_level: Mapped[str | None] = mapped_column(
        SQLEnum(ProficiencyLevel, native_enum=False, length=50),
        nullable=True,
    )
    years_of_experience: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, server_default="false", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # Relationships
    cv_analysis: Mapped["CVAnalysisModel"] = relationship(
        "CVAnalysisModel",
        back_populates="skills",
    )

    __table_args__ = (
        Index("idx_cv_skills_cv_analysis_id", "cv_analysis_id"),
        Index("idx_cv_skills_skill_name", "skill_name"),
        Index("idx_cv_skills_proficiency", "proficiency_level"),
    )


class InterviewQuestionModel(Base):
    """SQLAlchemy model for Interview-Question junction table."""

    __tablename__ = "interview_questions"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    interview_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("interviews.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    question_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("questions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sequence_order: Mapped[int] = mapped_column(Integer, nullable=False)
    asked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    skipped: Mapped[bool] = mapped_column(Boolean, server_default="false", nullable=False)
    skip_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # Relationships
    interview: Mapped["InterviewModel"] = relationship(
        "InterviewModel",
        back_populates="interview_questions",
    )
    question: Mapped["QuestionModel"] = relationship("QuestionModel")

    __table_args__ = (
        Index("idx_interview_questions_interview_id", "interview_id", "sequence_order"),
        Index("idx_interview_questions_question_id", "question_id"),
        Index("idx_interview_questions_asked_at", "asked_at"),
    )


class QuestionModel(Base):
    """SQLAlchemy model for Question entity."""

    __tablename__ = "questions"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    question_type: Mapped[str] = mapped_column(
        SQLEnum(QuestionType, native_enum=False, length=50),
        nullable=False,
        index=True,
    )
    difficulty: Mapped[str] = mapped_column(
        SQLEnum(Difficulty, native_enum=False, length=50),
        nullable=False,
        index=True,
    )
    skills: Mapped[list[str]] = mapped_column(ARRAY(String(100)), nullable=False, default=[])
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    embedding: Mapped[list[float] | None] = mapped_column(ARRAY(Float), nullable=True)

    # Pre-planning fields for adaptive interviews
    ideal_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # Relationships
    answers: Mapped[list["AnswerModel"]] = relationship(
        "AnswerModel",
        back_populates="question",
    )

    __table_args__ = (
        Index("idx_questions_type", "question_type"),
        Index("idx_questions_difficulty", "difficulty"),
        Index("idx_questions_skills", "skills", postgresql_using="gin"),
        Index("idx_questions_tags", "tags", postgresql_using="gin"),
    )


class InterviewModel(Base):
    """SQLAlchemy model for Interview entity."""

    __tablename__ = "interviews"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    candidate_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        SQLEnum(InterviewStatus, native_enum=False, length=50),
        nullable=False,
        index=True,
    )
    cv_analysis_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("cv_analyses.id", ondelete="SET NULL"),
        nullable=True,
    )
    current_question_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # NEW: Pre-planning metadata for adaptive interviews
    plan_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default={})
    adaptive_follow_ups: Mapped[list[UUID]] = mapped_column(
        ARRAY(PGUUID(as_uuid=True)),
        nullable=False,
        default=[],
    )

    # NEW: Follow-up tracking for current session
    current_parent_question_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
        default=None,
    )
    current_followup_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # Relationships
    candidate: Mapped["CandidateModel"] = relationship(
        "CandidateModel",
        back_populates="interviews",
    )
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
        Index("idx_interviews_candidate_id", "candidate_id"),
        Index("idx_interviews_status", "status"),
        Index("idx_interviews_created_at", "created_at"),
    )


class AnswerModel(Base):
    """SQLAlchemy model for Answer entity."""

    __tablename__ = "answers"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    interview_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("interviews.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    question_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("questions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    is_voice: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    audio_file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(ARRAY(Float), nullable=True)

    # Link to Evaluation entity
    evaluation_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("evaluations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Voice metrics (will be stored in Evaluation entity in future)
    voice_metrics: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # Relationships
    interview: Mapped["InterviewModel"] = relationship(
        "InterviewModel",
        back_populates="answers",
    )
    question: Mapped["QuestionModel"] = relationship(
        "QuestionModel",
        back_populates="answers",
    )

    __table_args__ = (
        Index("idx_answers_interview_id", "interview_id"),
        Index("idx_answers_question_id", "question_id"),
        Index("idx_answers_created_at", "created_at"),
    )


class CVAnalysisModel(Base):
    """SQLAlchemy model for CV Analysis entity."""

    __tablename__ = "cv_analyses"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    candidate_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    extracted_text: Mapped[str] = mapped_column(Text, nullable=False)
    work_experience_years: Mapped[float | None] = mapped_column(Float, nullable=True)
    education_level: Mapped[str | None] = mapped_column(String(100), nullable=True)
    suggested_topics: Mapped[list[str]] = mapped_column(
        ARRAY(String(200)),
        nullable=False,
        default=[],
    )
    suggested_difficulty: Mapped[str] = mapped_column(String(50), nullable=False, default="medium")
    embedding: Mapped[list[float] | None] = mapped_column(ARRAY(Float), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # Relationships
    candidate: Mapped["CandidateModel"] = relationship(
        "CandidateModel",
        back_populates="cv_analyses",
    )
    skills: Mapped[list["CVSkillModel"]] = relationship(
        "CVSkillModel",
        back_populates="cv_analysis",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("idx_cv_analyses_candidate_id", "candidate_id"),
        Index("idx_cv_analyses_created_at", "created_at"),
    )


class FollowUpQuestionModel(Base):
    """SQLAlchemy model for FollowUpQuestion entity."""

    __tablename__ = "follow_up_questions"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    parent_question_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("questions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    interview_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("interviews.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    generated_reason: Mapped[str] = mapped_column(Text, nullable=False)
    order_in_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    __table_args__ = (
        Index("idx_follow_up_questions_parent_question_id", "parent_question_id"),
        Index("idx_follow_up_questions_interview_id", "interview_id"),
        Index("idx_follow_up_questions_created_at", "created_at"),
    )


class EvaluationModel(Base):
    """SQLAlchemy model for Evaluation entity."""

    __tablename__ = "evaluations"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    answer_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("answers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    question_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    interview_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("interviews.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Scores
    raw_score: Mapped[float] = mapped_column(Float, nullable=False)
    penalty: Mapped[float] = mapped_column(Float, nullable=False, server_default="0")
    final_score: Mapped[float] = mapped_column(Float, nullable=False)
    similarity_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # LLM evaluation details
    completeness: Mapped[float] = mapped_column(Float, nullable=False)
    relevance: Mapped[float] = mapped_column(Float, nullable=False)
    sentiment: Mapped[str | None] = mapped_column(String(50), nullable=True)
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    strengths: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default="{}"
    )
    weaknesses: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default="{}"
    )
    improvement_suggestions: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default="{}"
    )

    # Follow-up context
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    parent_evaluation_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("evaluations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    evaluated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Relationships
    gaps: Mapped[list["EvaluationGapModel"]] = relationship(
        "EvaluationGapModel",
        back_populates="evaluation",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("idx_evaluations_answer_id", "answer_id"),
        Index("idx_evaluations_question_id", "question_id"),
        Index("idx_evaluations_interview_id", "interview_id"),
        Index("idx_evaluations_parent_id", "parent_evaluation_id"),
        Index("idx_evaluations_attempt_number", "attempt_number"),
    )


class EvaluationGapModel(Base):
    """SQLAlchemy model for EvaluationGap entity."""

    __tablename__ = "evaluation_gaps"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    evaluation_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("evaluations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    concept: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, server_default="'moderate'")
    resolved: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # Relationships
    evaluation: Mapped["EvaluationModel"] = relationship(
        "EvaluationModel",
        back_populates="gaps",
    )

    __table_args__ = (
        Index("idx_evaluation_gaps_evaluation_id", "evaluation_id"),
        Index("idx_evaluation_gaps_resolved", "resolved"),
    )


class PromptTemplateModel(Base):
    """SQLAlchemy model for PromptTemplate entity (decomposed schema)."""

    __tablename__ = "prompt_templates"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    prompt_name: Mapped[str] = mapped_column("name", String(100), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    traffic_percentage: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    # Decomposed prompt structure (editable fields)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    user_template: Mapped[str] = mapped_column(Text, nullable=False)
    input_variables: Mapped[list[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
        server_default="{}",
    )
    partial_variables: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    output_parser_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default="json_output_parser",
    )
    output_schema: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # Model parameters
    temperature: Mapped[float] = mapped_column(Numeric(3, 2), nullable=False, server_default="0.30")
    max_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default="2000")
    top_p: Mapped[float] = mapped_column(Numeric(3, 2), nullable=False, server_default="0.95")
    frequency_penalty: Mapped[float] = mapped_column(Numeric(3, 2), nullable=False, server_default="0.00")
    presence_penalty: Mapped[float] = mapped_column(Numeric(3, 2), nullable=False, server_default="0.00")

    # Soft delete
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Auto-generated fields (read-only, created by trigger)
    template_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    template_json_legacy: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

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
        Index("idx_prompt_templates_name", "name"),
        Index("idx_prompt_templates_version", "name", "version"),
        Index("idx_prompt_templates_deleted_at", "deleted_at"),
    )


class PromptMetadataChangeModel(Base):
    """SQLAlchemy model for PromptMetadataChange entity."""

    __tablename__ = "prompt_metadata_changes"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    prompt_template_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("prompt_templates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    field_name: Mapped[str] = mapped_column(String(50), nullable=False)
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    changed_by: Mapped[str] = mapped_column(String(100), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    prompt_template: Mapped["PromptTemplateModel"] = relationship(
        "PromptTemplateModel",
        back_populates="metadata_changes",
    )

    __table_args__ = (
        Index("idx_prompt_metadata_changes_template", "prompt_template_id", "changed_at"),
    )


class PromptExecutionModel(Base):
    """SQLAlchemy model for PromptExecution entity."""

    __tablename__ = "prompt_executions"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    prompt_template_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("prompt_templates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    interview_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("interviews.id", ondelete="CASCADE"),
        nullable=True,
    )
    candidate_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("candidates.id", ondelete="SET NULL"),
        nullable=True,
    )
    input_variables: Mapped[dict] = mapped_column(JSONB, nullable=False)
    output_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    tokens_used: Mapped[int | None] = mapped_column(Integer, nullable=True)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    model_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    executed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # Relationships
    prompt_template: Mapped["PromptTemplateModel"] = relationship(
        "PromptTemplateModel",
        back_populates="executions",
    )

    __table_args__ = (
        Index("idx_prompt_executions_template", "prompt_template_id", "executed_at"),
        Index("idx_prompt_executions_success", "success", "executed_at"),
    )


class PromptAnalyticsSummaryModel(Base):
    """SQLAlchemy model for prompt_analytics_summary materialized view (read-only)."""

    __tablename__ = "prompt_analytics_summary"

    prompt_template_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    ab_test_group: Mapped[str | None] = mapped_column(String(50), nullable=True)
    total_executions: Mapped[int] = mapped_column(Integer, nullable=False)
    avg_tokens_used: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    success_rate: Mapped[float] = mapped_column(Float, nullable=False)
    estimated_cost_usd: Mapped[float] = mapped_column(Float, nullable=False)
    last_executed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
