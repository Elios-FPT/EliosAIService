import asyncio

import pytest

from src.infrastructure.background.checkpointer_heartbeat import (
    start_checkpointer_heartbeat,
)


@pytest.mark.asyncio
async def test_heartbeat_runs_until_stopped():
    counter = 0

    async def ping():
        nonlocal counter
        counter += 1

    handle = await start_checkpointer_heartbeat(ping, 0.01)
    await asyncio.sleep(0.05)
    await handle.stop()

    assert counter >= 1


@pytest.mark.asyncio
async def test_heartbeat_recovers_from_ping_failures():
    attempts = 0

    async def ping():
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("boom")

    handle = await start_checkpointer_heartbeat(ping, 0.01)
    await asyncio.sleep(0.05)
    await handle.stop()

    assert attempts >= 2

