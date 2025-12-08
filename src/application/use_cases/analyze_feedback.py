"""Use case for analyzing entities and generating feedback."""

import logging
from uuid import UUID, uuid4

from ...domain.models.feedback_request import FeedbackRequest
from ...domain.models.feedback_result import (
    FeedbackResult,
    FeedbackStatus,
    InputType,
)
from ...domain.ports.event_publisher_port import EventPublisherPort
from ...domain.ports.feedback_repository_port import (
    FeedbackRequestRepositoryPort,
    FeedbackResponseRepositoryPort,
)
from ...domain.ports.llm_port import LLMPort

logger = logging.getLogger(__name__)


class AnalyzeFeedbackUseCase:
    """Analyze entity and generate feedback.

    Simplified implementation - direct LLM call with fail-fast error handling.
    Frontend must provide feedback_input (no entity extraction).
    Synchronous processing pattern - no async queue.
    Frontend waits for completion (5-30s typical).
    """

    def __init__(
        self,
        request_repo: FeedbackRequestRepositoryPort,
        response_repo: FeedbackResponseRepositoryPort,
        event_publisher: EventPublisherPort,
        llm: LLMPort,
    ):
        """Initialize use case with required dependencies.

        Args:
            request_repo: Feedback request repository
            response_repo: Feedback response repository
            event_publisher: Event publisher for Kafka events
            llm: LLM port for feedback analysis
        """
        self.request_repo = request_repo
        self.response_repo = response_repo
        self.event_publisher = event_publisher
        self.llm = llm

    async def execute(
        self,
        entity_id: UUID,
        input_type: InputType,
        user_id: UUID | None = None,
        feedback_input: str | None = None,
    ) -> tuple[FeedbackRequest, FeedbackResult]:
        """Analyze entity and return feedback.

        Args:
            entity_id: UUID of entity to analyze
            input_type: Type of entity (CV/CODE only, INTERVIEW not supported)
            user_id: Optional user who requested analysis
            feedback_input: Required JSON string with entity content

        Returns:
            Tuple of (FeedbackRequest, FeedbackResult)

        Raises:
            ValueError: If input_type is INTERVIEW or feedback_input is missing/invalid
            RuntimeError: If LLM call fails
        """
        # Validate input_type (reject INTERVIEW)
        if input_type == InputType.INTERVIEW:
            raise ValueError(
                "INTERVIEW feedback analysis is not supported. "
                "Use CV or CODE input types."
            )

        # Validate feedback_input (required)
        if not feedback_input:
            raise ValueError(
                "feedback_input is required. Frontend must provide entity content as JSON string."
            )

        correlation_id = uuid4()

        # Create request
        feedback_request = await self.request_repo.create(
            entity_id=entity_id,
            input_type=input_type,
            user_id=user_id,
            feedback_input=feedback_input,
        )

        try:
            # Update status to PROCESSING
            await self.request_repo.update_status(
                request_id=feedback_request.id,
                status=FeedbackStatus.PROCESSING,
            )

            # Direct LLM call (fail fast - no retry)
            context = {
                "user_id": str(user_id) if user_id else None,
                "entity_id": str(entity_id),
                "request_id": str(feedback_request.id),
            }
            result = await self.llm.analyze_feedback(
                input_type=input_type,
                feedback_input=feedback_input,
                context=context,
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
                logger.error(
                    f"Failed to publish FEEDBACK_COMPLETED event: {e}",
                    extra={
                        "request_id": str(feedback_request.id),
                        "entity_id": str(entity_id),
                    },
                    exc_info=True,
                )

            feedback_request.status = FeedbackStatus.SUCCESS

            return feedback_request, result

        except Exception as e:
            # Update request with failure
            await self.request_repo.update_status(
                request_id=feedback_request.id,
                status=FeedbackStatus.FAILED,
                error_message=str(e),
            )
            raise


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

