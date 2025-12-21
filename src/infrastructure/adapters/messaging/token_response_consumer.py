"""Kafka consumer for token confirmation responses."""

import json
import logging

from aiokafka import AIOKafkaConsumer
from pydantic import ValidationError

from src.application.dto.event import TokenResponseEnvelope
from .token_confirmation_service import TokenConfirmationService

logger = logging.getLogger(__name__)


class TokenResponseConsumer:
    """Consumes token confirmation responses from Kafka.

    Listens to ai-token-responses topic and resolves pending requests
    via TokenConfirmationService.
    """

    def __init__(
        self,
        bootstrap_servers: str,
        topic: str,
        group_id: str,
        confirmation_service: TokenConfirmationService,
    ):
        """Initialize consumer.

        Args:
            bootstrap_servers: Kafka broker addresses
            topic: Response topic name (e.g., "ai-token-responses")
            group_id: Consumer group ID
            confirmation_service: Service to resolve pending requests
        """
        self.bootstrap_servers = bootstrap_servers
        self.topic = topic
        self.group_id = group_id
        self.confirmation_service = confirmation_service
        self.consumer: AIOKafkaConsumer | None = None
        self._running = False

    async def start(self) -> None:
        """Start Kafka consumer."""
        if self._running:
            return

        self.consumer = AIOKafkaConsumer(
            self.topic,
            bootstrap_servers=self.bootstrap_servers,
            group_id=self.group_id,
            auto_offset_reset="latest",  # Only care about new messages
            enable_auto_commit=True,
            value_deserializer=lambda m: m.decode("utf-8"),
        )
        await self.consumer.start()
        self._running = True

        logger.info(
            "Token response consumer started",
            extra={
                "topic": self.topic,
                "group_id": self.group_id,
            },
        )

    async def stop(self) -> None:
        """Stop Kafka consumer."""
        self._running = False

        if self.consumer:
            await self.consumer.stop()
            self.consumer = None
            logger.info("Token response consumer stopped")

    async def consume_loop(self) -> None:
        """Main consume loop (run as background task).

        Continuously reads messages and resolves pending requests.
        """
        if not self.consumer:
            raise RuntimeError("Consumer not started")

        try:
            async for message in self.consumer:
                if not self._running:
                    break
                await self._process_message(message)
        except Exception as e:
            if self._running:
                logger.error(f"Consumer loop error: {e}", exc_info=True)
                raise

    async def _process_message(self, message) -> None:
        """Process single Kafka message."""
        try:
            # Parse JSON
            raw_data = json.loads(message.value)

            # Validate against schema
            response = TokenResponseEnvelope.model_validate(raw_data)

            # Resolve pending request
            await self.confirmation_service.resolve_pending(
                correlation_id=response.correlation_id,
                response=response,
            )

            logger.debug(
                "Processed token response",
                extra={
                    "correlation_id": str(response.correlation_id),
                    "success": response.success,
                    "topic": message.topic,
                    "partition": message.partition,
                    "offset": message.offset,
                },
            )

        except json.JSONDecodeError as e:
            logger.error(
                "Invalid JSON in token response",
                extra={
                    "error": str(e),
                    "raw_value": message.value[:200] if message.value else None,
                },
            )
        except ValidationError as e:
            logger.error(
                "Invalid token response schema",
                extra={
                    "error": str(e),
                    "raw_value": message.value[:500] if message.value else None,
                },
                exc_info=True,
            )
        except Exception as e:
            logger.error(
                "Failed to process token response",
                extra={
                    "error": str(e),
                    "topic": message.topic,
                    "partition": message.partition,
                    "offset": message.offset,
                },
                exc_info=True,
            )
