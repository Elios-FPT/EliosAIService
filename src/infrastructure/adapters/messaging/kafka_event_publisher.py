"""Kafka event publisher adapter using aiokafka."""

import json
import logging
from uuid import UUID

from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaError

from src.application.dto.event import (
    EventWrapper,
    FeedbackCompletedPayload,
    InterviewAttemptedPayload,
    TokenDeltaPayload,
)
from src.domain.models.feedback_result import FeedbackResult
from src.application.ports.event_publisher_port import EventPublisherPort

logger = logging.getLogger(__name__)


class KafkaEventPublisher(EventPublisherPort):
    """Kafka event publisher using aiokafka.

    Publishes domain events to Kafka topics following fire-and-forget pattern.
    Partitions by user_id for ordering guarantees per user.
    """

    def __init__(
        self,
        bootstrap_servers: str,
        interview_topic: str = "interview-user-interview",
        feedback_topic: str = "ai-feedback-results",
        token_topic: str = "user-token-updates",
    ):
        """Initialize Kafka publisher (not started yet).

        Args:
            bootstrap_servers: Kafka broker addresses (e.g., "localhost:9092")
            interview_topic: Topic name for interview events
            feedback_topic: Topic name for feedback events
        """
        self.bootstrap_servers = bootstrap_servers
        self.interview_topic = interview_topic
        self.feedback_topic = feedback_topic
        self.token_topic = token_topic
        self.producer: AIOKafkaProducer | None = None
        logger.info(
            "KafkaEventPublisher initialized",
            extra={
                "bootstrap_servers": bootstrap_servers,
                "interview_topic": interview_topic,
                "feedback_topic": feedback_topic,
                "token_topic": token_topic,
            }
        )

    async def start(self) -> None:
        """Start Kafka producer (called in FastAPI lifespan).

        Raises:
            Exception: If producer fails to start
        """
        if self.producer is not None:
            logger.warning("KafkaEventPublisher already started")
            return

        try:
            self.producer = AIOKafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                key_serializer=lambda k: k.encode("utf-8") if k else None,
                compression_type="gzip",  # Compress messages
                acks=1,  # Leader acknowledgment (balance speed/reliability)
                request_timeout_ms=30000,  # Request timeout (30 seconds)
            )
            await self.producer.start()
            logger.info("KafkaEventPublisher started successfully")
        except Exception as e:
            logger.error(f"Failed to start KafkaEventPublisher: {e}", exc_info=True)
            raise

    async def stop(self) -> None:
        """Stop Kafka producer (called in FastAPI lifespan).

        Flushes pending messages before stopping.
        """
        if self.producer is None:
            logger.warning("KafkaEventPublisher not started, skipping stop")
            return

        try:
            await self.producer.stop()
            logger.info("KafkaEventPublisher stopped successfully")
            self.producer = None
        except Exception as e:
            logger.error(f"Error stopping KafkaEventPublisher: {e}", exc_info=True)

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
        """Publish INTERVIEW_ATTEMPTED event to Kafka.

        Args:
            candidate_id: Candidate UUID (maps to UserId, used for partitioning)
            interview_id: Interview UUID
            correlation_id: Correlation ID
            overall_score: Overall score
            theoretical_score_avg: Theoretical score
            speaking_score_avg: Speaking score

        Note:
            Errors are logged and swallowed (fire-and-forget).
        """
        if self.producer is None:
            logger.error("Cannot publish: KafkaEventPublisher not started")
            return

        try:
            # Build payload
            payload = InterviewAttemptedPayload.from_summary(
                candidate_id=candidate_id,
                interview_id=interview_id,
                overall_score=overall_score,
                theoretical_score_avg=theoretical_score_avg,
                speaking_score_avg=speaking_score_avg,
                title=title,
            )

            # Wrap in event envelope
            event = EventWrapper(
                correlation_id=correlation_id,
                event_type="INTERVIEW_ATTEMPTED",
                payload=payload,
            )

            # Serialize to JSON-safe dict (PascalCase keys via alias)
            event_dict = event.model_dump(mode="json", by_alias=True)

            # Partition by user_id for ordering
            partition_key = str(candidate_id)

            # Send to Kafka (fire-and-forget, no await on send result)
            await self.producer.send(
                self.interview_topic,
                value=event_dict,
                key=partition_key,
            )

            logger.info(
                "Published INTERVIEW_ATTEMPTED event",
                extra={
                    "interview_id": str(interview_id),
                    "candidate_id": str(candidate_id),
                    "correlation_id": str(correlation_id),
                    "overall_score": overall_score,
                    "topic": self.interview_topic,
                }
            )

        except KafkaError as e:
            logger.error(
                f"Kafka error publishing INTERVIEW_ATTEMPTED: {e}",
                extra={
                    "interview_id": str(interview_id),
                    "candidate_id": str(candidate_id),
                },
                exc_info=True,
            )
        except Exception as e:
            logger.error(
                f"Unexpected error publishing INTERVIEW_ATTEMPTED: {e}",
                extra={
                    "interview_id": str(interview_id),
                    "candidate_id": str(candidate_id),
                },
                exc_info=True,
            )

    async def publish_feedback_completed(
        self,
        request_id: UUID,
        entity_id: UUID,
        input_type: str,
        user_id: UUID | None,
        result: FeedbackResult,
        correlation_id: UUID,
    ) -> None:
        """Publish FEEDBACK_COMPLETED event to Kafka.

        Args:
            request_id: Feedback request UUID
            entity_id: Entity UUID (used for partitioning)
            input_type: Type of entity (INTERVIEW/CV/CODE)
            user_id: User UUID (nullable)
            result: Typed feedback result
            correlation_id: Correlation ID for tracing

        Note:
            Errors are logged and swallowed (fire-and-forget).
        """
        if self.producer is None:
            logger.error("Cannot publish: KafkaEventPublisher not started")
            return

        try:
            # Build payload from typed FeedbackResult
            payload = FeedbackCompletedPayload.from_feedback(
                request_id=request_id,
                entity_id=entity_id,
                input_type=input_type,
                user_id=user_id,
                result=result,
            )

            # Wrap in event envelope
            event = EventWrapper(
                correlation_id=correlation_id,
                event_type="FEEDBACK_COMPLETED",
                payload=payload,
            )

            # Serialize to JSON-safe dict (PascalCase keys via alias)
            event_dict = event.model_dump(mode="json", by_alias=True)

            # Partition by entity_id for ordering guarantees per entity
            partition_key = str(entity_id)

            # Send to Kafka (fire-and-forget, no await on send result)
            await self.producer.send(
                self.feedback_topic,
                value=event_dict,
                key=partition_key,
            )

            logger.info(
                "Published FEEDBACK_COMPLETED event",
                extra={
                    "request_id": str(request_id),
                    "entity_id": str(entity_id),
                    "input_type": input_type,
                    "correlation_id": str(correlation_id),
                    "topic": self.feedback_topic,
                }
            )

        except KafkaError as e:
            logger.error(
                f"Kafka error publishing FEEDBACK_COMPLETED: {e}",
                extra={
                    "request_id": str(request_id),
                    "entity_id": str(entity_id),
                },
                exc_info=True,
            )
        except Exception as e:
            logger.error(
                f"Unexpected error publishing FEEDBACK_COMPLETED: {e}",
                extra={
                    "request_id": str(request_id),
                    "entity_id": str(entity_id),
                },
                exc_info=True,
            )

    async def publish_token_delta(
        self,
        user_id: UUID,
        tokens: int,
        correlation_id: UUID,
    ) -> None:
        """Publish token delta event to Kafka."""
        if self.producer is None:
            logger.error("Cannot publish: KafkaEventPublisher not started")
            return

        try:
            payload = TokenDeltaPayload(user_id=user_id, tokens=tokens)
            event = EventWrapper(
                correlation_id=correlation_id,
                event_type="UPDATE",
                payload=payload,
            )
            event_dict = event.model_dump(mode="json", by_alias=True)

            await self.producer.send(
                self.token_topic,
                value=event_dict,
                key=str(user_id),
            )

            logger.info(
                "Published TOKEN_DELTA event",
                extra={
                    "user_id": str(user_id),
                    "tokens": tokens,
                    "correlation_id": str(correlation_id),
                    "topic": self.token_topic,
                },
            )
        except KafkaError as e:
            logger.error(
                f"Kafka error publishing TOKEN_DELTA: {e}",
                extra={"user_id": str(user_id), "tokens": tokens},
                exc_info=True,
            )
        except Exception as e:
            logger.error(
                f"Unexpected error publishing TOKEN_DELTA: {e}",
                extra={"user_id": str(user_id), "tokens": tokens},
                exc_info=True,
            )

