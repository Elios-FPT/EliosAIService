"""Event publisher port interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from src.domain.models.feedback_result import FeedbackResult

if TYPE_CHECKING:
    from src.application.dto.event import TokenResponseEnvelope


class EventPublisherPort(ABC):
    """Interface for publishing domain events to message brokers.

    Abstracts event publishing (Kafka, RabbitMQ, SNS, etc.) following
    fire-and-forget pattern. Failures should be logged but not block business logic.
    """

    @abstractmethod
    async def publish_interview_attempted(
        self,
        candidate_id: UUID,
        interview_id: UUID,
        correlation_id: UUID,
        overall_score: float,
        theoretical_score_avg: float,
        speaking_score_avg: float | None,
        title: str | None = None,
    ) -> None:
        """Publish INTERVIEW_ATTEMPTED event to User Service.

        Args:
            candidate_id: Candidate UUID (maps to UserId in downstream services)
            interview_id: Interview UUID
            correlation_id: Request correlation ID for tracing
            overall_score: Weighted overall score (0-100)
            theoretical_score_avg: Theoretical score average (0-100)
            speaking_score_avg: Speaking score average (0-100), or None if text-only interview

        Note:
            This method should NOT raise exceptions (fire-and-forget).
            Errors should be logged and swallowed.
        """
        pass

    @abstractmethod
    async def publish_feedback_completed(
        self,
        request_id: UUID,
        entity_id: UUID,
        input_type: str,  # InputType enum value as string
        user_id: UUID | None,
        result: FeedbackResult,
        correlation_id: UUID,
    ) -> None:
        """Publish FEEDBACK_COMPLETED event to Kafka.

        Args:
            request_id: Feedback request UUID
            entity_id: Entity UUID that was analyzed
            input_type: Type of entity (INTERVIEW/CV/CODE)
            user_id: Optional user who requested analysis
            result: Typed feedback result
            correlation_id: Request correlation ID for tracing

        Note:
            This method should NOT raise exceptions (fire-and-forget).
            Errors should be logged and swallowed.
        """
        pass

    @abstractmethod
    async def publish_token_delta(
        self,
        user_id: UUID,
        tokens: int,
        correlation_id: UUID,
    ) -> None:
        """Publish token balance delta event.

        Args:
            user_id: User UUID (partition + payload)
            tokens: Token delta (negative to deduct)
            correlation_id: Correlation ID for tracing/idempotency

        Note:
            Fire-and-forget: log failures and swallow to avoid blocking API flows.
        """
        pass

    @abstractmethod
    async def publish_token_delta_with_confirmation(
        self,
        user_id: UUID,
        tokens: int,
        correlation_id: UUID,
        timeout: float = 30.0,
    ) -> "TokenConfirmationResult":
        """Publish token delta and wait for confirmation.

        Synchronous request-response pattern over Kafka.
        Blocks until User Service responds or timeout.

        Args:
            user_id: User UUID
            tokens: Token delta (negative to deduct)
            correlation_id: Correlation ID for matching response
            timeout: Max wait time in seconds

        Returns:
            TokenConfirmationResult with success status and details

        Raises:
            TokenConfirmationError: On timeout or communication failure
        """
        pass


@dataclass
class TokenConfirmationResult:
    """Result of token confirmation request."""

    success: bool
    new_balance: Decimal | None = None
    error_message: str | None = None
    correlation_id: UUID | None = None

    @classmethod
    def from_response(
        cls, response: "TokenResponseEnvelope"
    ) -> "TokenConfirmationResult":
        """Create result from response envelope."""
        if response.is_success() and response.payload:
            return cls(
                success=True,
                new_balance=response.payload.new_balance,
                correlation_id=response.correlation_id,
            )
        return cls(
            success=False,
            error_message=response.get_error_detail(),
            correlation_id=response.correlation_id,
        )

    @classmethod
    def timeout(cls, correlation_id: UUID) -> "TokenConfirmationResult":
        """Create timeout result."""
        return cls(
            success=False,
            error_message="Token confirmation timeout",
            correlation_id=correlation_id,
        )


class TokenConfirmationError(Exception):
    """Error during token confirmation."""

    def __init__(self, message: str, correlation_id: UUID | None = None):
        super().__init__(message)
        self.correlation_id = correlation_id
