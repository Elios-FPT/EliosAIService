"""Feedback repository port interfaces."""

from abc import ABC, abstractmethod
from uuid import UUID

from src.domain.models.feedback_request import FeedbackRequest
from src.domain.models.feedback_response import FeedbackResponse
from src.domain.models.feedback_result import FeedbackResult, FeedbackStatus, InputType


class FeedbackRequestRepositoryPort(ABC):
    """Interface for feedback request persistence.

    Follows repository pattern with abstract methods for all persistence operations.
    """

    @abstractmethod
    async def create(
        self,
        entity_id: UUID,
        input_type: InputType,
        user_id: UUID | None = None,
    ) -> FeedbackRequest:
        """Create new feedback request with status=PENDING.

        Args:
            entity_id: UUID of entity to analyze
            input_type: Type of entity (INTERVIEW/CV/CODE)
            user_id: Optional user who requested analysis

        Returns:
            Created FeedbackRequest

        Raises:
            ValueError: If creation fails
        """
        pass

    @abstractmethod
    async def get_by_id(self, request_id: UUID) -> FeedbackRequest | None:
        """Get request by ID.

        Args:
            request_id: Request UUID

        Returns:
            FeedbackRequest if found, None otherwise
        """
        pass

    @abstractmethod
    async def update_status(
        self,
        request_id: UUID,
        status: FeedbackStatus,
        error_message: str | None = None,
    ) -> FeedbackRequest:
        """Update request status and optional error message.

        Args:
            request_id: Request UUID
            status: New status
            error_message: Error message if status=FAILED

        Returns:
            Updated FeedbackRequest

        Raises:
            ValueError: If request not found
        """
        pass

    @abstractmethod
    async def list_by_user(
        self,
        user_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[FeedbackRequest]:
        """List requests for user (for frontend dashboard).

        Args:
            user_id: User UUID
            limit: Max results (default 50, max 100)
            offset: Pagination offset

        Returns:
            List of FeedbackRequest ordered by created_at DESC
        """
        pass


class FeedbackResponseRepositoryPort(ABC):
    """Interface for feedback response persistence.

    Handles type-safe storage and retrieval of feedback results.
    """

    @abstractmethod
    async def create(
        self,
        request_id: UUID,
        result: FeedbackResult,
        prompt_execution_id: UUID | None = None,
    ) -> FeedbackResponse:
        """Create feedback response with type-safe result.

        Args:
            request_id: Foreign key to feedback_request
            result: Typed feedback result (Interview/Code/CV)
            prompt_execution_id: Optional link to prompt_executions for cost tracking

        Returns:
            Created FeedbackResponse

        Raises:
            ValueError: If creation fails

        Note:
            Uses Pydantic model_dump() to serialize result to JSON.
        """
        pass

    @abstractmethod
    async def get_by_request_id(self, request_id: UUID) -> FeedbackResponse | None:
        """Get response for request with type-safe deserialization.

        Args:
            request_id: Request UUID

        Returns:
            FeedbackResponse with deserialized result, or None

        Note:
            Fetches request.input_type to determine result class for deserialization.
        """
        pass

