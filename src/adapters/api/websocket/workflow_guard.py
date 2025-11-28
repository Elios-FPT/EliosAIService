"""Utility to retry workflow calls when checkpointer connections flap."""

from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable, TypeVar

from psycopg import OperationalError as PsycopgOperationalError

logger = logging.getLogger(__name__)

T = TypeVar("T")


async def execute_with_workflow_guard(
    action_name: str,
    action: Callable[[], Awaitable[T]],
    ensure_alive: Callable[[], Awaitable[None]],
    max_attempts: int = 2,
) -> T:
    """Execute workflow action with retry for psycopg OperationalErrors."""
    last_exc: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            await ensure_alive()
            return await action()
        except PsycopgOperationalError as exc:
            last_exc = exc
            logger.warning(
                "Workflow action %s attempt %s/%s failed due to DB connection: %s",
                action_name,
                attempt,
                max_attempts,
                exc,
            )
            await asyncio.sleep(min(0.1, 0.05 * attempt))
            continue

    if last_exc is not None:
        raise last_exc
    raise RuntimeError("Workflow guard exited without executing action")


