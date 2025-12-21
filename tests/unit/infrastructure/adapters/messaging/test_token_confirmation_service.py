"""Unit tests for TokenConfirmationService."""

import pytest
import asyncio
from uuid import uuid4

from src.infrastructure.adapters.messaging import TokenConfirmationService
from src.application.dto.event import TokenResponseEnvelope


@pytest.fixture
async def service():
    """Create and start service for tests."""
    svc = TokenConfirmationService(stale_timeout_seconds=5.0)
    await svc.start()
    yield svc
    await svc.stop()


class TestTokenConfirmationService:
    """Tests for TokenConfirmationService."""

    @pytest.mark.asyncio
    async def test_register_and_resolve(self, service):
        """Register request, resolve it, wait returns response."""
        cid = uuid4()

        # Register
        await service.register_pending(cid)
        assert service.pending_count == 1

        # Create mock response
        response = TokenResponseEnvelope(
            event_id=uuid4(),
            correlation_id=cid,
            event_type="UPDATE",
            payload=None,
            success=True,
            error_message=None,
        )

        # Resolve in background
        async def resolve_later():
            await asyncio.sleep(0.1)
            await service.resolve_pending(cid, response)

        asyncio.create_task(resolve_later())

        # Wait should return response
        result = await service.wait_for_response(cid, timeout=5.0)
        assert result is not None
        assert result.correlation_id == cid

    @pytest.mark.asyncio
    async def test_timeout_returns_none(self, service):
        """Timeout returns None without error."""
        cid = uuid4()
        await service.register_pending(cid)

        result = await service.wait_for_response(cid, timeout=0.1)
        assert result is None

    @pytest.mark.asyncio
    async def test_unknown_correlation_raises(self, service):
        """Wait for unknown correlation_id raises KeyError."""
        with pytest.raises(KeyError):
            await service.wait_for_response(uuid4(), timeout=1.0)

    @pytest.mark.asyncio
    async def test_resolve_unknown_logs_warning(self, service, caplog):
        """Resolving unknown correlation_id logs warning."""
        response = TokenResponseEnvelope(
            event_id=uuid4(),
            correlation_id=uuid4(),
            event_type="UPDATE",
            payload=None,
            success=True,
            error_message=None,
        )

        await service.resolve_pending(uuid4(), response)
        assert "unknown correlation_id" in caplog.text.lower()

    @pytest.mark.asyncio
    async def test_stop_unblocks_waiters(self, service):
        """Stop signals all pending requests."""
        cid = uuid4()
        await service.register_pending(cid)

        async def wait_and_catch():
            return await service.wait_for_response(cid, timeout=60.0)

        task = asyncio.create_task(wait_and_catch())

        await asyncio.sleep(0.1)
        await service.stop()

        # Wait should complete (not hang)
        result = await asyncio.wait_for(task, timeout=1.0)
        assert result is None
