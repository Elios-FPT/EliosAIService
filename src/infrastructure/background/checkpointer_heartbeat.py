"""Heartbeat helper for keeping LangGraph checkpointer connections alive."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)


async def _heartbeat_loop(
    ping_func: Callable[[], Awaitable[Any]],
    interval_seconds: float,
    stop_event: asyncio.Event,
) -> None:
    """Run periodic ping until stop_event is set."""
    try:
        while not stop_event.is_set():
            try:
                await ping_func()
                logger.debug("Checkpointer heartbeat ping succeeded")
            except Exception as exc:  # pragma: no cover - logging path
                logger.warning("Checkpointer heartbeat ping failed: %s", exc)
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
            except asyncio.TimeoutError:
                continue
    except asyncio.CancelledError:  # pragma: no cover
        logger.info("Checkpointer heartbeat task cancelled")
        raise


class HeartbeatHandle:
    """Handle for managing heartbeat lifecycle."""

    def __init__(self, task: asyncio.Task[Any], stop_event: asyncio.Event):
        self._task = task
        self._stop_event = stop_event

    async def stop(self) -> None:
        """Stop heartbeat gracefully."""
        self._stop_event.set()
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:  # pragma: no cover
            logger.info("Heartbeat task cancelled cleanly")


async def start_checkpointer_heartbeat(
    ping_callable: Callable[[], Awaitable[Any]],
    interval_seconds: float,
) -> HeartbeatHandle:
    """Start heartbeat to keep checkpointer connection alive."""

    stop_event = asyncio.Event()
    task = asyncio.create_task(_heartbeat_loop(ping_callable, interval_seconds, stop_event))
    return HeartbeatHandle(task, stop_event)

