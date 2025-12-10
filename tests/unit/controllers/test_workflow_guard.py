import pytest
from unittest.mock import AsyncMock
from psycopg import OperationalError

from src.controllers.websocket.workflow_guard import execute_with_workflow_guard


@pytest.mark.asyncio
async def test_execute_with_workflow_guard_retries_then_succeeds():
    ensure_alive = AsyncMock()
    attempts = 0

    async def action():
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise OperationalError("connection dropped")
        return "ok"

    result = await execute_with_workflow_guard(
        "start_session",
        action,
        ensure_alive,
        max_attempts=2,
    )

    assert result == "ok"
    assert attempts == 2
    assert ensure_alive.await_count == 2


@pytest.mark.asyncio
async def test_execute_with_workflow_guard_raises_after_exhaustion():
    ensure_alive = AsyncMock()

    async def action():
        raise OperationalError("still down")

    with pytest.raises(OperationalError):
        await execute_with_workflow_guard(
            "process_answer",
            action,
            ensure_alive,
            max_attempts=2,
        )

    assert ensure_alive.await_count == 2


