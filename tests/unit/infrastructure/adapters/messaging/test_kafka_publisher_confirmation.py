"""Unit tests for token confirmation in KafkaEventPublisher."""

import pytest
from unittest.mock import AsyncMock
from uuid import uuid4
from decimal import Decimal
from datetime import datetime

from src.infrastructure.adapters.messaging import (
    KafkaEventPublisher,
    TokenConfirmationService,
)
from src.application.dto.event import TokenResponseEnvelope, TokenResponsePayload
from src.application.ports.event_publisher_port import (
    TokenConfirmationResult,
    TokenConfirmationError,
)


@pytest.fixture
def mock_producer():
    """Create mock Kafka producer."""
    producer = AsyncMock()
    producer.send = AsyncMock()
    return producer


@pytest.fixture
def mock_confirmation_service():
    """Create mock confirmation service."""
    service = AsyncMock(spec=TokenConfirmationService)
    return service


@pytest.fixture
def publisher(mock_producer, mock_confirmation_service):
    """Create publisher with mocks."""
    pub = KafkaEventPublisher(
        bootstrap_servers="localhost:9092",
        confirmation_service=mock_confirmation_service,
    )
    pub.producer = mock_producer
    return pub


class TestPublishTokenDeltaWithConfirmation:
    """Tests for confirmed token delta."""

    @pytest.mark.asyncio
    async def test_success_returns_result(self, publisher, mock_confirmation_service):
        """Successful confirmation returns result with balance."""
        cid = uuid4()
        user_id = uuid4()

        # Mock response
        response = TokenResponseEnvelope(
            event_id=uuid4(),
            correlation_id=cid,
            event_type="UPDATE",
            payload=TokenResponsePayload(
                processed_at=datetime.now(),
                success=True,
                new_balance=Decimal("6220.00"),
                user_id=user_id,
            ),
            success=True,
            error_message=None,
        )
        mock_confirmation_service.wait_for_response.return_value = response

        result = await publisher.publish_token_delta_with_confirmation(
            user_id=user_id,
            tokens=-100,
            correlation_id=cid,
        )

        assert result.success is True
        assert result.new_balance == Decimal("6220.00")
        mock_confirmation_service.register_pending.assert_called_once_with(cid)

    @pytest.mark.asyncio
    async def test_failure_returns_error_message(
        self, publisher, mock_confirmation_service
    ):
        """Failed confirmation returns error message."""
        cid = uuid4()
        user_id = uuid4()

        response = TokenResponseEnvelope(
            event_id=uuid4(),
            correlation_id=cid,
            event_type="UPDATE",
            payload=None,
            success=False,
            error_message="Insufficient balance",
        )
        mock_confirmation_service.wait_for_response.return_value = response

        result = await publisher.publish_token_delta_with_confirmation(
            user_id=user_id,
            tokens=-100,
            correlation_id=cid,
        )

        assert result.success is False
        assert result.error_message == "Insufficient balance"

    @pytest.mark.asyncio
    async def test_timeout_returns_timeout_result(
        self, publisher, mock_confirmation_service
    ):
        """Timeout returns timeout result."""
        cid = uuid4()
        mock_confirmation_service.wait_for_response.return_value = None

        result = await publisher.publish_token_delta_with_confirmation(
            user_id=uuid4(),
            tokens=-100,
            correlation_id=cid,
            timeout=1.0,
        )

        assert result.success is False
        assert "timeout" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_no_confirmation_service_raises(self, mock_producer):
        """Missing confirmation service raises error."""
        publisher = KafkaEventPublisher(bootstrap_servers="localhost:9092")
        publisher.producer = mock_producer

        with pytest.raises(TokenConfirmationError) as exc_info:
            await publisher.publish_token_delta_with_confirmation(
                user_id=uuid4(),
                tokens=-100,
                correlation_id=uuid4(),
            )

        assert "not configured" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_producer_not_started_raises(self, mock_confirmation_service):
        """Unstarted producer raises error."""
        publisher = KafkaEventPublisher(
            bootstrap_servers="localhost:9092",
            confirmation_service=mock_confirmation_service,
        )
        # producer is None

        with pytest.raises(TokenConfirmationError) as exc_info:
            await publisher.publish_token_delta_with_confirmation(
                user_id=uuid4(),
                tokens=-100,
                correlation_id=uuid4(),
            )

        assert "not started" in str(exc_info.value)
