"""Token confirmation service for request-response over Kafka."""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict
from uuid import UUID

from src.application.dto.event import TokenResponseEnvelope

logger = logging.getLogger(__name__)


@dataclass
class PendingRequest:
    """Tracks a pending token confirmation request."""

    correlation_id: UUID
    event: asyncio.Event = field(default_factory=asyncio.Event)
    response: TokenResponseEnvelope | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class TokenConfirmationService:
    """Coordinates token request-response flow.

    Thread-safe service that:
    1. Registers pending requests before publishing
    2. Resolves requests when consumer receives matching response
    3. Cleans up stale requests to prevent memory leaks

    Usage:
        service = TokenConfirmationService()

        # Before publishing
        await service.register_pending(correlation_id)

        # Publish to Kafka...

        # Wait for response
        response = await service.wait_for_response(correlation_id, timeout=30.0)
    """

    def __init__(self, stale_timeout_seconds: float = 120.0):
        """Initialize service.

        Args:
            stale_timeout_seconds: TTL for abandoned requests (default: 2 min)
        """
        self._pending_requests: Dict[UUID, PendingRequest] = {}
        self._lock = asyncio.Lock()
        self._stale_timeout = timedelta(seconds=stale_timeout_seconds)
        self._cleanup_task: asyncio.Task | None = None
        self._running = False

    async def start(self) -> None:
        """Start background cleanup task."""
        if self._running:
            return
        self._running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("TokenConfirmationService started")

    async def stop(self) -> None:
        """Stop background cleanup and clear pending requests."""
        self._running = False

        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        # Signal all pending requests to unblock waiters
        async with self._lock:
            for pending in self._pending_requests.values():
                pending.event.set()
            self._pending_requests.clear()

        logger.info("TokenConfirmationService stopped")

    async def register_pending(self, correlation_id: UUID) -> None:
        """Register a pending request before publishing.

        Args:
            correlation_id: Unique ID to match response
        """
        async with self._lock:
            if correlation_id in self._pending_requests:
                logger.warning(
                    "Duplicate correlation_id registered",
                    extra={"correlation_id": str(correlation_id)},
                )
            self._pending_requests[correlation_id] = PendingRequest(
                correlation_id=correlation_id
            )

        logger.debug(
            "Pending request registered",
            extra={"correlation_id": str(correlation_id)},
        )

    async def resolve_pending(
        self, correlation_id: UUID, response: TokenResponseEnvelope
    ) -> None:
        """Resolve a pending request with response.

        Called by consumer when matching response received.

        Args:
            correlation_id: Request correlation ID
            response: Parsed response envelope
        """
        async with self._lock:
            pending = self._pending_requests.get(correlation_id)

            if pending is None:
                # Response for unknown/expired request
                logger.warning(
                    "Received response for unknown correlation_id",
                    extra={
                        "correlation_id": str(correlation_id),
                        "success": response.success,
                    },
                )
                return

            pending.response = response
            pending.event.set()

        logger.debug(
            "Pending request resolved",
            extra={
                "correlation_id": str(correlation_id),
                "success": response.success,
            },
        )

    async def wait_for_response(
        self, correlation_id: UUID, timeout: float = 30.0
    ) -> TokenResponseEnvelope | None:
        """Wait for response with timeout.

        Args:
            correlation_id: Request correlation ID
            timeout: Max wait time in seconds

        Returns:
            Response envelope if received, None if timeout

        Raises:
            KeyError: If correlation_id not registered
        """
        async with self._lock:
            pending = self._pending_requests.get(correlation_id)
            if pending is None:
                raise KeyError(f"Unknown correlation_id: {correlation_id}")

        try:
            await asyncio.wait_for(pending.event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning(
                "Token confirmation timeout",
                extra={
                    "correlation_id": str(correlation_id),
                    "timeout_seconds": timeout,
                },
            )
            return None
        finally:
            # Always cleanup after wait completes
            async with self._lock:
                self._pending_requests.pop(correlation_id, None)

        return pending.response

    async def _cleanup_loop(self) -> None:
        """Background task to cleanup stale requests."""
        while self._running:
            try:
                await asyncio.sleep(60.0)  # Run every minute
                await self._cleanup_stale_requests()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup loop error: {e}", exc_info=True)

    async def _cleanup_stale_requests(self) -> None:
        """Remove requests older than stale_timeout."""
        now = datetime.now(timezone.utc)
        stale_ids = []

        async with self._lock:
            for cid, pending in self._pending_requests.items():
                if now - pending.created_at > self._stale_timeout:
                    stale_ids.append(cid)

            for cid in stale_ids:
                pending = self._pending_requests.pop(cid)
                pending.event.set()  # Unblock any waiters

        if stale_ids:
            logger.info(
                "Cleaned up stale pending requests",
                extra={"count": len(stale_ids)},
            )

    @property
    def pending_count(self) -> int:
        """Number of pending requests (for monitoring)."""
        return len(self._pending_requests)
