"""Mappers to convert between domain models and SQLAlchemy models.

These mappers handle the translation between the domain layer
(Pydantic models) and the persistence layer (SQLAlchemy models).
"""


from decimal import Decimal

from ...domain.models.answer import Answer, AnswerEvaluation
from ...domain.models.candidate import Candidate
from ...domain.models.cv_analysis import CVAnalysis
from ...domain.models.cv_skill import CVSkill, ProficiencyLevel
from ...domain.models.follow_up_question import FollowUpQuestion
from ...domain.models.interview import Interview, InterviewStatus
from ...domain.models.interview_question import InterviewQuestion
from ...domain.models.question import Difficulty, Question, QuestionType
from .models import (
    AnswerModel,
    CandidateModel,
    CVAnalysisModel,
    CVSkillModel,
    FollowUpQuestionModel,
    InterviewModel,
    InterviewQuestionModel,
    QuestionModel,
)


class CVSkillMapper:
    """Mapper for CVSkill domain model and CVSkillModel database model."""

    @staticmethod
    def to_domain(db_model: CVSkillModel) -> CVSkill:
        """Convert database model to domain model.

        Args:
            db_model: CVSkillModel SQLAlchemy model

        Returns:
            CVSkill domain model
        """
        return CVSkill(
            id=db_model.id,
            cv_analysis_id=db_model.cv_analysis_id,
            skill_name=db_model.skill_name,
            proficiency_level=ProficiencyLevel(db_model.proficiency_level) if db_model.proficiency_level else None,
            years_of_experience=db_model.years_of_experience,
            is_primary=db_model.is_primary,
            created_at=db_model.created_at,
        )

    @staticmethod
    def to_db_model(domain_model: CVSkill) -> CVSkillModel:
        """Convert domain model to database model.

        Args:
            domain_model: CVSkill domain model

        Returns:
            CVSkillModel SQLAlchemy model
        """
        return CVSkillModel(
            id=domain_model.id,
            cv_analysis_id=domain_model.cv_analysis_id,
            skill_name=domain_model.skill_name,
            proficiency_level=domain_model.proficiency_level.value if domain_model.proficiency_level else None,
            years_of_experience=domain_model.years_of_experience,
            is_primary=domain_model.is_primary,
            created_at=domain_model.created_at,
        )

    @staticmethod
    def update_db_model(db_model: CVSkillModel, domain_model: CVSkill) -> None:
        """Update database model from domain model.

        Args:
            db_model: CVSkillModel SQLAlchemy model to update
            domain_model: CVSkill domain model with new data
        """
        db_model.skill_name = domain_model.skill_name
        db_model.proficiency_level = domain_model.proficiency_level.value if domain_model.proficiency_level else None
        db_model.years_of_experience = domain_model.years_of_experience
        db_model.is_primary = domain_model.is_primary


class InterviewQuestionMapper:
    """Mapper for InterviewQuestion junction model and InterviewQuestionModel."""

    @staticmethod
    def to_domain(db_model: InterviewQuestionModel) -> InterviewQuestion:
        """Convert database model to domain model.

        Args:
            db_model: InterviewQuestionModel SQLAlchemy model

        Returns:
            InterviewQuestion domain model
        """
        return InterviewQuestion(
            id=db_model.id,
            interview_id=db_model.interview_id,
            question_id=db_model.question_id,
            sequence_order=db_model.sequence_order,
            asked_at=db_model.asked_at,
            skipped=db_model.skipped,
            skip_reason=db_model.skip_reason,
            created_at=db_model.created_at,
        )

    @staticmethod
    def to_db_model(domain_model: InterviewQuestion) -> InterviewQuestionModel:
        """Convert domain model to database model.

        Args:
            domain_model: InterviewQuestion domain model

        Returns:
            InterviewQuestionModel SQLAlchemy model
        """
        return InterviewQuestionModel(
            id=domain_model.id,
            interview_id=domain_model.interview_id,
            question_id=domain_model.question_id,
            sequence_order=domain_model.sequence_order,
            asked_at=domain_model.asked_at,
            skipped=domain_model.skipped,
            skip_reason=domain_model.skip_reason,
            created_at=domain_model.created_at,
        )

    @staticmethod
    def update_db_model(db_model: InterviewQuestionModel, domain_model: InterviewQuestion) -> None:
        """Update database model from domain model.

        Args:
            db_model: InterviewQuestionModel SQLAlchemy model to update
            domain_model: InterviewQuestion domain model with new data
        """
        db_model.sequence_order = domain_model.sequence_order
        db_model.asked_at = domain_model.asked_at
        db_model.skipped = domain_model.skipped
        db_model.skip_reason = domain_model.skip_reason


class CandidateMapper:
    """Mapper for Candidate domain model and CandidateModel database model."""

    @staticmethod
    def to_domain(db_model: CandidateModel) -> Candidate:
        """Convert database model to domain model.

        Args:
            db_model: SQLAlchemy model instance

        Returns:
            Domain model instance
        """
        return Candidate(
            id=db_model.id,
            name=db_model.name,
            email=db_model.email,
            cv_file_path=db_model.cv_file_path,
            created_at=db_model.created_at,
            updated_at=db_model.updated_at,
        )

    @staticmethod
    def to_db_model(domain_model: Candidate) -> CandidateModel:
        """Convert domain model to database model.

        Args:
            domain_model: Domain model instance

        Returns:
            SQLAlchemy model instance
        """
        return CandidateModel(
            id=domain_model.id,
            name=domain_model.name,
            email=domain_model.email,
            cv_file_path=domain_model.cv_file_path,
            created_at=domain_model.created_at,
            updated_at=domain_model.updated_at,
        )

    @staticmethod
    def update_db_model(db_model: CandidateModel, domain_model: Candidate) -> None:
        """Update database model from domain model.

        Args:
            db_model: SQLAlchemy model to update
            domain_model: Domain model with new data
        """
        db_model.name = domain_model.name
        db_model.email = domain_model.email
        db_model.cv_file_path = domain_model.cv_file_path
        db_model.updated_at = domain_model.updated_at


class QuestionMapper:
    """Mapper for Question domain model and QuestionModel database model."""

    @staticmethod
    def to_domain(db_model: QuestionModel) -> Question:
        """Convert database model to domain model."""
        return Question(
            id=db_model.id,
            text=db_model.text,
            question_type=QuestionType(db_model.question_type),
            difficulty=Difficulty(db_model.difficulty),
            skills=list(db_model.skills) if db_model.skills else [],
            version=db_model.version,
            embedding=list(db_model.embedding) if db_model.embedding else None,
            ideal_answer=db_model.ideal_answer,
            rationale=db_model.rationale,
            created_at=db_model.created_at,
            updated_at=db_model.updated_at,
        )

    @staticmethod
    def to_db_model(domain_model: Question) -> QuestionModel:
        """Convert domain model to database model."""
        return QuestionModel(
            id=domain_model.id,
            text=domain_model.text,
            question_type=domain_model.question_type.value,
            difficulty=domain_model.difficulty.value,
            skills=domain_model.skills,
            version=domain_model.version,
            embedding=domain_model.embedding,
            ideal_answer=domain_model.ideal_answer,
            rationale=domain_model.rationale,
            created_at=domain_model.created_at,
            updated_at=domain_model.updated_at,
        )

    @staticmethod
    def update_db_model(db_model: QuestionModel, domain_model: Question) -> None:
        """Update database model from domain model."""
        db_model.text = domain_model.text
        db_model.question_type = domain_model.question_type.value
        db_model.difficulty = domain_model.difficulty.value
        db_model.skills = domain_model.skills
        db_model.version = domain_model.version
        db_model.embedding = domain_model.embedding
        db_model.ideal_answer = domain_model.ideal_answer
        db_model.rationale = domain_model.rationale
        db_model.updated_at = domain_model.updated_at


class InterviewMapper:
    """Mapper for Interview domain model and InterviewModel database model."""

    @staticmethod
    def to_domain(db_model: InterviewModel) -> Interview:
        """Convert database model to domain model.

        Note: interview_questions relationship handled separately via InterviewQuestionMapper.
        """
        return Interview(
            id=db_model.id,
            candidate_id=db_model.candidate_id,
            status=InterviewStatus(db_model.status),
            cv_analysis_id=db_model.cv_analysis_id,
            current_question_index=db_model.current_question_index,
            plan_metadata=dict(db_model.plan_metadata) if db_model.plan_metadata else {},
            adaptive_follow_ups=list(db_model.adaptive_follow_ups) if db_model.adaptive_follow_ups else [],
            current_parent_question_id=db_model.current_parent_question_id,
            current_followup_count=db_model.current_followup_count,
            started_at=db_model.started_at,
            completed_at=db_model.completed_at,
            created_at=db_model.created_at,
            updated_at=db_model.updated_at,
        )

    @staticmethod
    def to_db_model(domain_model: Interview) -> InterviewModel:
        """Convert domain model to database model.

        Note: interview_questions relationship handled separately via InterviewQuestionMapper.
        """
        return InterviewModel(
            id=domain_model.id,
            candidate_id=domain_model.candidate_id,
            status=domain_model.status.value,
            cv_analysis_id=domain_model.cv_analysis_id,
            current_question_index=domain_model.current_question_index,
            plan_metadata=domain_model.plan_metadata,
            adaptive_follow_ups=domain_model.adaptive_follow_ups,
            current_parent_question_id=domain_model.current_parent_question_id,
            current_followup_count=domain_model.current_followup_count,
            started_at=domain_model.started_at,
            completed_at=domain_model.completed_at,
            created_at=domain_model.created_at,
            updated_at=domain_model.updated_at,
        )

    @staticmethod
    def update_db_model(db_model: InterviewModel, domain_model: Interview) -> None:
        """Update database model from domain model.

        Note: interview_questions relationship handled separately via repository.
        """
        db_model.status = domain_model.status.value
        db_model.cv_analysis_id = domain_model.cv_analysis_id
        db_model.current_question_index = domain_model.current_question_index
        db_model.plan_metadata = domain_model.plan_metadata
        db_model.adaptive_follow_ups = domain_model.adaptive_follow_ups
        db_model.current_parent_question_id = domain_model.current_parent_question_id
        db_model.current_followup_count = domain_model.current_followup_count
        db_model.started_at = domain_model.started_at
        db_model.completed_at = domain_model.completed_at
        db_model.updated_at = domain_model.updated_at


class AnswerMapper:
    """Mapper for Answer domain model and AnswerModel database model."""

    @staticmethod
    def to_domain(db_model: AnswerModel) -> Answer:
        """Convert database model to domain model."""
        return Answer(
            id=db_model.id,
            interview_id=db_model.interview_id,
            question_id=db_model.question_id,
            text=db_model.text,
            is_voice=db_model.is_voice,
            audio_file_path=db_model.audio_file_path,
            duration_seconds=db_model.duration_seconds,
            embedding=list(db_model.embedding) if db_model.embedding else None,
            evaluation_id=db_model.evaluation_id,
            voice_metrics=None,  # Not persisted yet
            created_at=db_model.created_at,
        )

    @staticmethod
    def to_db_model(domain_model: Answer) -> AnswerModel:
        """Convert domain model to database model."""
        return AnswerModel(
            id=domain_model.id,
            interview_id=domain_model.interview_id,
            question_id=domain_model.question_id,
            text=domain_model.text,
            is_voice=domain_model.is_voice,
            audio_file_path=domain_model.audio_file_path,
            duration_seconds=domain_model.duration_seconds,
            embedding=domain_model.embedding,
            evaluation_id=domain_model.evaluation_id,
            created_at=domain_model.created_at,
        )

    @staticmethod
    def update_db_model(db_model: AnswerModel, domain_model: Answer) -> None:
        """Update database model from domain model."""
        db_model.text = domain_model.text
        db_model.is_voice = domain_model.is_voice
        db_model.audio_file_path = domain_model.audio_file_path
        db_model.duration_seconds = domain_model.duration_seconds
        db_model.evaluation_id = domain_model.evaluation_id
        db_model.embedding = domain_model.embedding


class CVAnalysisMapper:
    """Mapper for CVAnalysis domain model and CVAnalysisModel database model."""

    @staticmethod
    def to_domain(db_model: CVAnalysisModel) -> CVAnalysis:
        """Convert database model to domain model.

        Note: Skills relationship handled by CVSkillMapper. Repository must
        load skills with joinedload/selectinload for complete domain object.
        """
        # Convert CVSkillModel relationship to CVSkill domain objects
        skills = [CVSkillMapper.to_domain(skill_model) for skill_model in db_model.skills]

        return CVAnalysis(
            id=db_model.id,
            candidate_id=db_model.candidate_id,
            extracted_text=db_model.extracted_text,
            skills=skills,
            work_experience_years=db_model.work_experience_years,
            education_level=db_model.education_level,
            suggested_topics=(
                list(db_model.suggested_topics) if db_model.suggested_topics else []
            ),
            suggested_difficulty=db_model.suggested_difficulty,
            embedding=list(db_model.embedding) if db_model.embedding else None,
            summary=db_model.summary,
            created_at=db_model.created_at,
        )

    @staticmethod
    def to_db_model(domain_model: CVAnalysis) -> CVAnalysisModel:
        """Convert domain model to database model.

        Note: Skills must be saved separately via CVSkillMapper/repository
        to maintain relationship integrity.
        """
        return CVAnalysisModel(
            id=domain_model.id,
            candidate_id=domain_model.candidate_id,
            extracted_text=domain_model.extracted_text,
            work_experience_years=domain_model.work_experience_years,
            education_level=domain_model.education_level,
            suggested_topics=domain_model.suggested_topics,
            suggested_difficulty=domain_model.suggested_difficulty,
            embedding=domain_model.embedding,
            summary=domain_model.summary,
            created_at=domain_model.created_at,
        )

    @staticmethod
    def update_db_model(db_model: CVAnalysisModel, domain_model: CVAnalysis) -> None:
        """Update database model from domain model.

        Note: Skills relationship updated separately via repository layer.
        """
        db_model.extracted_text = domain_model.extracted_text
        db_model.work_experience_years = domain_model.work_experience_years
        db_model.education_level = domain_model.education_level
        db_model.suggested_topics = domain_model.suggested_topics
        db_model.suggested_difficulty = domain_model.suggested_difficulty
        db_model.embedding = domain_model.embedding
        db_model.summary = domain_model.summary


class FollowUpQuestionMapper:
    """Mapper for FollowUpQuestion domain model and FollowUpQuestionModel database model."""

    @staticmethod
    def to_domain(db_model: FollowUpQuestionModel) -> FollowUpQuestion:
        """Convert database model to domain model.

        Args:
            db_model: SQLAlchemy model instance

        Returns:
            FollowUpQuestion domain model
        """
        return FollowUpQuestion(
            id=db_model.id,
            parent_question_id=db_model.parent_question_id,
            interview_id=db_model.interview_id,
            text=db_model.text,
            generated_reason=db_model.generated_reason,
            order_in_sequence=db_model.order_in_sequence,
            created_at=db_model.created_at,
        )

    @staticmethod
    def to_db_model(domain_model: FollowUpQuestion) -> FollowUpQuestionModel:
        """Convert domain model to database model.

        Args:
            domain_model: FollowUpQuestion domain model

        Returns:
            FollowUpQuestionModel SQLAlchemy model
        """
        return FollowUpQuestionModel(
            id=domain_model.id,
            parent_question_id=domain_model.parent_question_id,
            interview_id=domain_model.interview_id,
            text=domain_model.text,
            generated_reason=domain_model.generated_reason,
            order_in_sequence=domain_model.order_in_sequence,
            created_at=domain_model.created_at,
        )

    @staticmethod
    def update_db_model(
        db_model: FollowUpQuestionModel, domain_model: FollowUpQuestion
    ) -> None:
        """Update database model from domain model.

        Args:
            db_model: SQLAlchemy model to update
            domain_model: FollowUpQuestion domain model with new data
        """
        db_model.text = domain_model.text
        db_model.generated_reason = domain_model.generated_reason
        db_model.order_in_sequence = domain_model.order_in_sequence


class PromptTemplateMapper:
    """Mapper for PromptTemplate domain model and PromptTemplateModel (decomposed schema)."""

    @staticmethod
    def to_domain(db_model: "PromptTemplateModel") -> "PromptTemplate":
        """Convert database model to domain model.

        Args:
            db_model: PromptTemplateModel SQLAlchemy model

        Returns:
            PromptTemplate domain model
        """
        from ...domain.models.prompt_template import PromptTemplate

        return PromptTemplate(
            id=db_model.id,
            prompt_name=db_model.prompt_name,
            version=db_model.version,
            is_active=db_model.is_active,
            traffic_percentage=db_model.traffic_percentage,
            # Decomposed fields
            system_prompt=db_model.system_prompt,
            user_template=db_model.user_template,
            input_variables=list(db_model.input_variables),
            partial_variables=dict(db_model.partial_variables),
            output_parser_type=db_model.output_parser_type,
            output_schema=dict(db_model.output_schema),
            temperature=Decimal(str(db_model.temperature)),
            max_tokens=db_model.max_tokens,
            top_p=Decimal(str(db_model.top_p)),
            frequency_penalty=Decimal(str(db_model.frequency_penalty)),
            presence_penalty=Decimal(str(db_model.presence_penalty)),
            # Soft delete
            deleted_at=db_model.deleted_at,
            # Legacy (read-only, auto-generated by trigger)
            template_json_legacy=dict(db_model.template_json_legacy) if db_model.template_json_legacy else None,
            # Timestamps
            created_at=db_model.created_at,
        )

    @staticmethod
    def to_db_model(domain_model: "PromptTemplate") -> "PromptTemplateModel":
        """Convert domain model to database model.

        Args:
            domain_model: PromptTemplate domain model

        Returns:
            PromptTemplateModel SQLAlchemy model
        """
        from .models import PromptTemplateModel

        return PromptTemplateModel(
            id=domain_model.id,
            prompt_name=domain_model.prompt_name,
            version=domain_model.version,
            is_active=domain_model.is_active,
            traffic_percentage=domain_model.traffic_percentage,
            # Decomposed fields
            system_prompt=domain_model.system_prompt,
            user_template=domain_model.user_template,
            input_variables=domain_model.input_variables,
            partial_variables=domain_model.partial_variables,
            output_parser_type=domain_model.output_parser_type,
            output_schema=domain_model.output_schema,
            temperature=float(domain_model.temperature),
            max_tokens=domain_model.max_tokens,
            top_p=float(domain_model.top_p),
            frequency_penalty=float(domain_model.frequency_penalty),
            presence_penalty=float(domain_model.presence_penalty),
            # Soft delete
            deleted_at=domain_model.deleted_at,
            # Legacy (read-only, auto-generated by trigger)
            template_json_legacy=domain_model.template_json_legacy,
            # Timestamps
            created_at=domain_model.created_at,
        )

    @staticmethod
    def update_db_model(db_model: "PromptTemplateModel", domain_model: "PromptTemplate") -> None:
        """Update database model from domain model.

        Args:
            db_model: PromptTemplateModel SQLAlchemy model to update
            domain_model: PromptTemplate domain model with new data

        Note: template_json auto-generated by trigger, no manual update needed.
        """
        db_model.prompt_name = domain_model.prompt_name
        db_model.version = domain_model.version
        db_model.is_active = domain_model.is_active
        db_model.traffic_percentage = domain_model.traffic_percentage
        # Decomposed fields (trigger will regenerate template_json)
        db_model.system_prompt = domain_model.system_prompt
        db_model.user_template = domain_model.user_template
        db_model.input_variables = domain_model.input_variables
        db_model.partial_variables = domain_model.partial_variables
        db_model.output_parser_type = domain_model.output_parser_type
        db_model.output_schema = domain_model.output_schema
        db_model.temperature = float(domain_model.temperature)
        db_model.max_tokens = domain_model.max_tokens
        db_model.top_p = float(domain_model.top_p)
        db_model.frequency_penalty = float(domain_model.frequency_penalty)
        db_model.presence_penalty = float(domain_model.presence_penalty)
        db_model.deleted_at = domain_model.deleted_at


class PromptMetadataChangeMapper:
    """Mapper for PromptMetadataChange domain model and PromptMetadataChangeModel."""

    @staticmethod
    def to_domain(db_model: "PromptMetadataChangeModel") -> "PromptMetadataChange":
        """Convert database model to domain model.

        Args:
            db_model: PromptMetadataChangeModel SQLAlchemy model

        Returns:
            PromptMetadataChange domain model
        """
        from ...domain.models.prompt_metadata_change import PromptMetadataChange

        return PromptMetadataChange(
            id=db_model.id,
            prompt_template_id=db_model.prompt_template_id,
            field_name=db_model.field_name,
            old_value=db_model.old_value,
            new_value=db_model.new_value,
            changed_by=db_model.changed_by,
            changed_at=db_model.changed_at,
            reason=db_model.reason,
        )

    @staticmethod
    def to_db_model(domain_model: "PromptMetadataChange") -> "PromptMetadataChangeModel":
        """Convert domain model to database model.

        Args:
            domain_model: PromptMetadataChange domain model

        Returns:
            PromptMetadataChangeModel SQLAlchemy model
        """
        from .models import PromptMetadataChangeModel

        return PromptMetadataChangeModel(
            id=domain_model.id,
            prompt_template_id=domain_model.prompt_template_id,
            field_name=domain_model.field_name,
            old_value=domain_model.old_value,
            new_value=domain_model.new_value,
            changed_by=domain_model.changed_by,
            changed_at=domain_model.changed_at,
            reason=domain_model.reason,
        )


class PromptExecutionMapper:
    """Mapper for PromptExecution domain model and PromptExecutionModel."""

    @staticmethod
    def to_domain(db_model: "PromptExecutionModel") -> "PromptExecution":
        """Convert database model to domain model.

        Args:
            db_model: PromptExecutionModel SQLAlchemy model

        Returns:
            PromptExecution domain model
        """
        from ...domain.models.prompt_execution import PromptExecution

        return PromptExecution(
            id=db_model.id,
            prompt_template_id=db_model.prompt_template_id,
            interview_id=db_model.interview_id,
            candidate_id=db_model.candidate_id,
            input_variables=db_model.input_variables,
            output_text=db_model.output_text,
            tokens_used=db_model.tokens_used,
            prompt_tokens=db_model.prompt_tokens,
            completion_tokens=db_model.completion_tokens,
            latency_ms=db_model.latency_ms,
            model_name=db_model.model_name,
            success=db_model.success,
            error_message=db_model.error_message,
            executed_at=db_model.executed_at,
        )

    @staticmethod
    def to_db_model(domain_model: "PromptExecution") -> "PromptExecutionModel":
        """Convert domain model to database model.

        Args:
            domain_model: PromptExecution domain model

        Returns:
            PromptExecutionModel SQLAlchemy model
        """
        from .models import PromptExecutionModel

        return PromptExecutionModel(
            id=domain_model.id,
            prompt_template_id=domain_model.prompt_template_id,
            interview_id=domain_model.interview_id,
            candidate_id=domain_model.candidate_id,
            input_variables=domain_model.input_variables,
            output_text=domain_model.output_text,
            tokens_used=domain_model.tokens_used,
            prompt_tokens=domain_model.prompt_tokens,
            completion_tokens=domain_model.completion_tokens,
            latency_ms=domain_model.latency_ms,
            model_name=domain_model.model_name,
            success=domain_model.success,
            error_message=domain_model.error_message,
            executed_at=domain_model.executed_at,
        )
