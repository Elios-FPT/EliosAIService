"""Kafka consumer for candidate lifecycle events."""

import logging
from datetime import datetime

from aiokafka import AIOKafkaConsumer
from pydantic import ValidationError

from src.domain.models.candidate_event import CandidateEvent, EventType
from src.application.ports.cv_analysis_repository_port import CVAnalysisRepositoryPort
from src.application.ports.interview_repository_port import InterviewRepositoryPort


logger = logging.getLogger(__name__)


class CandidateEventConsumer:
    """Consumes candidate lifecycle events from Kafka.

    Handles:
    - candidate DELETED → soft delete interviews + CV analyses
    """

    def __init__(
        self,
        bootstrap_servers: str,
        topic: str,
        group_id: str,
        interview_repo: InterviewRepositoryPort,
        cv_analysis_repo: CVAnalysisRepositoryPort,
    ):
        """Initialize consumer.

        Args:
            bootstrap_servers: Kafka broker addresses (e.g., "localhost:9092")
            topic: Kafka topic name (e.g., "user-interview-candidate")
            group_id: Consumer group ID (e.g., "interview-service-candidate-events")
            interview_repo: Interview repository for soft deletes
            cv_analysis_repo: CV analysis repository for soft deletes
        """
        self.bootstrap_servers = bootstrap_servers
        self.topic = topic
        self.group_id = group_id
        self.interview_repo = interview_repo
        self.cv_analysis_repo = cv_analysis_repo
        self.consumer: AIOKafkaConsumer | None = None

    async def start(self) -> None:
        """Start Kafka consumer."""
        self.consumer = AIOKafkaConsumer(
            self.topic,
            bootstrap_servers=self.bootstrap_servers,
            group_id=self.group_id,
            auto_offset_reset="earliest",
            enable_auto_commit=True,
            value_deserializer=lambda m: m.decode("utf-8"),
        )
        await self.consumer.start()
        logger.info(
            "Candidate event consumer started",
            extra={
                "event": "kafka_consumer_started",
                "topic": self.topic,
                "group_id": self.group_id,
            },
        )

    async def stop(self) -> None:
        """Stop Kafka consumer."""
        if self.consumer:
            await self.consumer.stop()
            logger.info("Candidate event consumer stopped")

    async def consume_events(self) -> None:
        """Consume and process candidate events (blocking loop)."""
        if not self.consumer:
            raise RuntimeError("Consumer not started. Call start() first.")

        async for message in self.consumer:
            await self._process_message(message)

    async def _process_message(self, message) -> None:
        """Process a single Kafka message."""
        try:
            event = CandidateEvent.model_validate_json(message.value)

            if event.event_type == EventType.DELETED:
                await self._handle_candidate_deleted(event)
            else:
                logger.debug(
                    "Ignoring candidate event type",
                    extra={
                        "event": "kafka_event_ignored",
                        "event_type": event.event_type,
                        "event_id": str(event.event_id),
                    },
                )
        except ValidationError as exc:
            logger.error(
                "Invalid candidate event schema",
                extra={
                    "event": "kafka_validation_error",
                    "error": str(exc),
                    "raw_message": message.value[:500],
                },
                exc_info=True,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "Failed to process candidate event message",
                extra={
                    "event": "kafka_processing_error",
                    "error": str(exc),
                    "topic": message.topic,
                    "partition": message.partition,
                    "offset": message.offset,
                },
                exc_info=True,
            )

    async def _handle_candidate_deleted(self, event: CandidateEvent) -> None:
        """Handle candidate.DELETED event.

        Soft deletes all interviews + CV analyses for the candidate.
        """
        candidate_id = event.payload.UserId

        try:
            interviews_deleted = await self.interview_repo.soft_delete_by_candidate_id(
                candidate_id
            )
            cv_analyses_deleted = (
                await self.cv_analysis_repo.soft_delete_by_candidate_id(candidate_id)
            )

            logger.info(
                "Candidate data soft deleted",
                extra={
                    "event": "candidate_deleted_processed",
                    "candidate_id": str(candidate_id),
                    "event_id": str(event.event_id),
                    "correlation_id": str(event.correlation_id),
                    "interviews_deleted": interviews_deleted,
                    "cv_analyses_deleted": cv_analyses_deleted,
                },
            )
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "Failed to soft delete candidate data",
                extra={
                    "event": "candidate_deletion_failed",
                    "candidate_id": str(candidate_id),
                    "event_id": str(event.event_id),
                    "error": str(exc),
                },
                exc_info=True,
            )
            raise


