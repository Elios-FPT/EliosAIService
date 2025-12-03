"""Use case for analyzing entities and generating feedback."""

import asyncio
from datetime import datetime
from uuid import UUID, uuid4

from ...domain.models.feedback_request import FeedbackRequest
from ...domain.models.feedback_result import (
    CVFeedbackResult,
    CodeReviewFeedbackResult,
    FeedbackResult,
    FeedbackStatus,
    InputType,
    InterviewFeedbackResult,
)
from ...domain.ports.cv_analysis_repository_port import CVAnalysisRepositoryPort
from ...domain.ports.event_publisher_port import EventPublisherPort
from ...domain.ports.feedback_repository_port import (
    FeedbackRequestRepositoryPort,
    FeedbackResponseRepositoryPort,
)
from ...domain.ports.interview_repository_port import InterviewRepositoryPort
from ..dto.detailed_feedback_dto import DetailedInterviewFeedback
from .complete_interview import CompleteInterviewUseCase


class LLMTimeoutError(Exception):
    """Transient error - should retry."""

    pass


class LLMRateLimitError(Exception):
    """Transient error - should retry."""

    pass


class LLMMaxRetriesError(Exception):
    """Permanent error - max retries exceeded."""

    pass


class AnalyzeFeedbackUseCase:
    """Analyze entity and generate feedback with retry logic.

    Synchronous processing pattern - no async queue.
    Frontend waits for completion (5-30s typical).
    """

    def __init__(
        self,
        request_repo: FeedbackRequestRepositoryPort,
        response_repo: FeedbackResponseRepositoryPort,
        event_publisher: EventPublisherPort,
        interview_repo: InterviewRepositoryPort,
        cv_analysis_repo: CVAnalysisRepositoryPort,
        complete_interview_use_case: CompleteInterviewUseCase,
        # Future: code_submission_repo when CODE analysis implemented
    ):
        """Initialize use case with required dependencies.

        Args:
            request_repo: Feedback request repository
            response_repo: Feedback response repository
            event_publisher: Event publisher for Kafka events
            interview_repo: Interview repository
            cv_analysis_repo: CV analysis repository
            complete_interview_use_case: Complete interview use case for INTERVIEW analysis
        """
        self.request_repo = request_repo
        self.response_repo = response_repo
        self.event_publisher = event_publisher
        self.interview_repo = interview_repo
        self.cv_analysis_repo = cv_analysis_repo
        self.complete_interview_use_case = complete_interview_use_case

    async def execute(
        self,
        entity_id: UUID,
        input_type: InputType,
        user_id: UUID | None = None,
    ) -> tuple[FeedbackRequest, FeedbackResult]:
        """Analyze entity and return feedback with retry.

        Args:
            entity_id: UUID of entity to analyze
            input_type: Type of entity (INTERVIEW/CV/CODE)
            user_id: Optional user who requested analysis

        Returns:
            Tuple of (FeedbackRequest, FeedbackResult)

        Raises:
            ValueError: Entity doesn't exist
            LLMMaxRetriesError: LLM failed after max retries
        """
        correlation_id = uuid4()

        # Create request
        feedback_request = await self.request_repo.create(
            entity_id=entity_id,
            input_type=input_type,
            user_id=user_id,
        )

        try:
            # Execute with retry (max 3 attempts)
            result = await self._analyze_with_retry(
                request_id=feedback_request.id,
                entity_id=entity_id,
                input_type=input_type,
                max_retries=3,
            )

            # Save response
            await self.response_repo.create(
                request_id=feedback_request.id,
                result=result,
            )

            # Update request status to SUCCESS
            await self.request_repo.update_status(
                request_id=feedback_request.id,
                status=FeedbackStatus.SUCCESS,
            )

            # Publish event (fire-and-forget)
            try:
                await self.event_publisher.publish_feedback_completed(
                    request_id=feedback_request.id,
                    entity_id=entity_id,
                    input_type=input_type.value,
                    user_id=user_id,
                    result=result,
                    correlation_id=correlation_id,
                )
            except Exception as e:
                # Log error but don't fail use case (fire-and-forget)
                import logging

                logger = logging.getLogger(__name__)
                logger.error(
                    f"Failed to publish FEEDBACK_COMPLETED event: {e}",
                    extra={
                        "request_id": str(feedback_request.id),
                        "entity_id": str(entity_id),
                    },
                    exc_info=True,
                )

            return feedback_request, result

        except Exception as e:
            # Update request with failure
            await self.request_repo.update_status(
                request_id=feedback_request.id,
                status=FeedbackStatus.FAILED,
                error_message=str(e),
            )
            raise

    async def _analyze_with_retry(
        self,
        request_id: UUID,
        entity_id: UUID,
        input_type: InputType,
        max_retries: int = 3,
    ) -> FeedbackResult:
        """Execute analysis with exponential backoff retry.

        Retry Schedule:
        - Attempt 1: 0s wait
        - Attempt 2: 2s wait
        - Attempt 3: 4s wait
        - Attempt 4: FAILED

        Args:
            request_id: Feedback request UUID
            entity_id: Entity UUID
            input_type: Entity type
            max_retries: Max retry attempts (default 3)

        Returns:
            FeedbackResult on success

        Raises:
            LLMMaxRetriesError: After max retries
            ValueError: Entity not found
        """
        for attempt in range(1, max_retries + 1):
            try:
                # Update status
                status = (
                    FeedbackStatus.PROCESSING
                    if attempt == 1
                    else FeedbackStatus.RETRYING
                )
                await self.request_repo.update_status(
                    request_id=request_id,
                    status=status,
                )

                # Route to appropriate analyzer
                if input_type == InputType.INTERVIEW:
                    result = await self._analyze_interview(entity_id)
                elif input_type == InputType.CV:
                    result = await self._analyze_cv(entity_id)
                elif input_type == InputType.CODE:
                    result = await self._analyze_code(entity_id)
                else:
                    raise ValueError(f"Unknown input_type: {input_type}")

                # Success - status already updated in execute()
                return result

            except (LLMTimeoutError, LLMRateLimitError) as e:
                # Transient error - retry
                if attempt >= max_retries:
                    raise LLMMaxRetriesError(
                        f"Failed after {max_retries} retries: {e}"
                    ) from e

                # Exponential backoff: 2^attempt seconds
                wait_seconds = 2 ** attempt
                await asyncio.sleep(wait_seconds)
                continue

            except ValueError as e:
                # Permanent error - don't retry
                raise

    async def _analyze_interview(
        self, interview_id: UUID
    ) -> InterviewFeedbackResult:
        """Analyze interview and generate feedback.

        Reuses existing CompleteInterviewUseCase logic.
        Works with interviews in EVALUATING status (will complete them) or COMPLETE status.

        Args:
            interview_id: Interview UUID

        Returns:
            InterviewFeedbackResult

        Raises:
            ValueError: Interview not found
        """
        # Fetch interview
        interview = await self.interview_repo.get_by_id(interview_id)
        if not interview:
            raise ValueError(f"Interview {interview_id} not found")

        # If interview is already COMPLETE, extract summary from metadata
        if interview.status == InterviewStatus.COMPLETE:
            if (
                interview.plan_metadata
                and "completion_summary" in interview.plan_metadata
            ):
                # Extract existing summary
                summary_dict = interview.plan_metadata["completion_summary"]
                detailed_feedback = DetailedInterviewFeedback(**summary_dict)
            else:
                # No summary stored - need to regenerate (shouldn't happen, but handle gracefully)
                # Call CompleteInterviewUseCase which will handle this
                # But it requires EVALUATING status, so we can't call it
                # Instead, generate a basic summary
                raise ValueError(
                    f"Interview {interview_id} is COMPLETE but has no stored summary. "
                    f"Cannot generate feedback."
                )
        elif interview.status == InterviewStatus.EVALUATING:
            # Use CompleteInterviewUseCase to complete and generate summary
            completion_result = await self.complete_interview_use_case.execute(
                interview_id
            )
            detailed_feedback: DetailedInterviewFeedback = completion_result.summary
        else:
            raise ValueError(
                f"Interview {interview_id} must be in EVALUATING or COMPLETE status "
                f"to generate feedback. Current status: {interview.status}"
            )

        # Convert DetailedInterviewFeedback to InterviewFeedbackResult
        return InterviewFeedbackResult(
            interview_id=interview_id,
            overall_score=detailed_feedback.overall_score,
            theoretical_score_avg=detailed_feedback.theoretical_score_avg,
            speaking_score_avg=detailed_feedback.speaking_score_avg,
            total_questions=detailed_feedback.total_questions,
            total_follow_ups=detailed_feedback.total_follow_ups,
            question_feedback=[
                qf.model_dump(mode="json") for qf in detailed_feedback.question_feedback
            ],
            gap_progression=detailed_feedback.gap_progression,
            strengths=detailed_feedback.strengths,
            weaknesses=detailed_feedback.weaknesses,
            study_recommendations=detailed_feedback.study_recommendations,
            technique_tips=detailed_feedback.technique_tips,
            completion_time=detailed_feedback.completion_time.isoformat(),
        )

    async def _analyze_cv(self, cv_analysis_id: UUID) -> CVFeedbackResult:
        """Analyze CV.

        Reuses existing AnalyzeCVUseCase logic.

        Args:
            cv_analysis_id: CVAnalysis UUID

        Returns:
            CVFeedbackResult

        Raises:
            ValueError: CV analysis not found
        """
        # Fetch CV analysis
        cv_analysis = await self.cv_analysis_repo.get_by_id(cv_analysis_id)
        if not cv_analysis:
            raise ValueError(f"CV analysis {cv_analysis_id} not found")

        # Get skills from CV analysis
        from ...domain.models.cv_skill import CVSkill

        # Note: Skills are stored in cv_analysis.skills list (CVSkill entities)
        skills_identified = [
            {
                "name": skill.skill_name,
                "proficiency": skill.proficiency_level.value
                if skill.proficiency_level
                else "intermediate",
                "years": skill.years_of_experience or 0.0,
            }
            for skill in cv_analysis.skills
        ]

        primary_skills = [
            skill.skill_name for skill in cv_analysis.skills if skill.is_primary
        ]
        secondary_skills = [
            skill.skill_name
            for skill in cv_analysis.skills
            if not skill.is_primary
        ]

        # Calculate total experience (sum of years from all skills, or estimate)
        total_experience_years = max(
            (skill.years_of_experience or 0.0 for skill in cv_analysis.skills),
            default=0.0,
        )

        # Convert to CVFeedbackResult
        return CVFeedbackResult(
            cv_analysis_id=cv_analysis_id,
            skills_identified=skills_identified,
            primary_skills=primary_skills,
            secondary_skills=secondary_skills,
            total_experience_years=total_experience_years,
            work_experience_summary=cv_analysis.summary or "No summary available",
            education_level="Unknown",  # Not stored in CVAnalysis (removed in v0.6.0)
            education_details=[],
            skill_gaps=[],  # TODO: Generate via LLM analysis
            improvement_areas=[],  # TODO: Generate via LLM analysis
            suggested_certifications=[],  # TODO: Generate via LLM analysis
            language="en",  # Default, could be detected from CV
        )

    async def _analyze_code(
        self, code_submission_id: UUID
    ) -> CodeReviewFeedbackResult:
        """Analyze code submission.

        STUB - Not implemented in Phase 04.

        Args:
            code_submission_id: Code submission UUID

        Returns:
            CodeReviewFeedbackResult

        Raises:
            NotImplementedError: CODE analysis not yet implemented
        """
        raise NotImplementedError("CODE analysis not yet implemented")

    async def list_user_feedback(
        self,
        user_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[FeedbackRequest]:
        """List feedback history for user (frontend dashboard).

        Args:
            user_id: User UUID
            limit: Max results (default 50, max 100)
            offset: Pagination offset

        Returns:
            List of FeedbackRequest ordered by created_at DESC
        """
        return await self.request_repo.list_by_user(user_id, limit, offset)

