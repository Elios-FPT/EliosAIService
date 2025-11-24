"""Integration tests for ViewRefreshJob."""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest
from sqlalchemy import text

from src.infrastructure.background.view_refresh_job import ViewRefreshJob


@pytest.mark.asyncio
async def test_refresh_analytics_view_success(async_session):
    """Test successful view refresh."""

    async def session_factory():
        """Mock session factory."""
        yield async_session

    job = ViewRefreshJob(session_factory)

    # Execute refresh
    await job.refresh_analytics_view()

    # Verify stats updated
    stats = job.get_stats()
    assert stats["refresh_count"] == 1
    assert stats["failure_count"] == 0
    assert stats["last_refresh_duration_ms"] is not None
    assert stats["last_refresh_duration_ms"] > 0


@pytest.mark.asyncio
async def test_refresh_analytics_view_failure(async_session):
    """Test view refresh handles errors."""

    async def failing_session_factory():
        """Mock session factory that raises error."""
        mock_session = AsyncMock()
        mock_session.execute.side_effect = Exception("Database connection failed")
        yield mock_session

    job = ViewRefreshJob(failing_session_factory)

    # Execute refresh (should not raise)
    await job.refresh_analytics_view()

    # Verify failure tracked
    stats = job.get_stats()
    assert stats["refresh_count"] == 0
    assert stats["failure_count"] == 1


@pytest.mark.asyncio
async def test_refresh_analytics_view_logs_slow_refresh():
    """Test warning logged for slow refresh."""

    class SlowSessionFactory:
        """Mock session factory that simulates slow query."""

        async def __aenter__(self):
            mock_session = AsyncMock()
            mock_session.execute = AsyncMock()
            mock_session.commit = AsyncMock()
            return mock_session

        async def __aexit__(self, *args):
            pass

    def session_factory():
        return SlowSessionFactory()

    job = ViewRefreshJob(session_factory)

    # Patch time to simulate 11 seconds
    with patch("src.infrastructure.background.view_refresh_job.time.time") as mock_time:
        mock_time.side_effect = [0, 11]  # 11 second duration

        with patch("src.infrastructure.background.view_refresh_job.logger") as mock_logger:
            await job.refresh_analytics_view()

            # Verify warning logged
            assert any("10s threshold" in str(call) for call in mock_logger.warning.call_args_list)


@pytest.mark.asyncio
async def test_refresh_now_triggers_immediate_refresh(async_session):
    """Test manual refresh trigger."""

    async def session_factory():
        yield async_session

    job = ViewRefreshJob(session_factory)

    # Trigger manual refresh
    await job.refresh_now()

    # Verify refresh executed
    stats = job.get_stats()
    assert stats["refresh_count"] == 1


@pytest.mark.asyncio
async def test_start_stop_scheduler(async_session):
    """Test starting and stopping scheduler."""

    async def session_factory():
        yield async_session

    job = ViewRefreshJob(session_factory)

    # Start scheduler
    job.start(interval_minutes=1)

    # Verify running
    stats = job.get_stats()
    assert stats["is_running"] is True

    # Stop scheduler
    job.stop()

    # Verify stopped
    stats = job.get_stats()
    assert stats["is_running"] is False


@pytest.mark.asyncio
async def test_scheduler_runs_at_interval(async_session):
    """Test scheduler executes job at specified interval."""

    async def session_factory():
        yield async_session

    job = ViewRefreshJob(session_factory)

    # Start with 1 second interval (for fast testing)
    # Note: APScheduler minimum is 1 second, so we use seconds for testing
    job.scheduler.add_job(
        job.refresh_analytics_view,
        "interval",
        seconds=1,
        id="test_refresh",
    )
    job.scheduler.start()

    # Wait for at least 2 runs (2+ seconds)
    await asyncio.sleep(2.5)

    # Stop scheduler
    job.scheduler.shutdown(wait=True)

    # Verify multiple runs
    stats = job.get_stats()
    assert stats["refresh_count"] >= 2


@pytest.mark.asyncio
async def test_get_stats_returns_correct_data(async_session):
    """Test get_stats returns all metrics."""

    async def session_factory():
        yield async_session

    job = ViewRefreshJob(session_factory)

    # Initial stats
    stats = job.get_stats()
    assert stats["refresh_count"] == 0
    assert stats["failure_count"] == 0
    assert stats["last_refresh_duration_ms"] is None
    assert stats["is_running"] is False

    # After refresh
    await job.refresh_analytics_view()

    stats = job.get_stats()
    assert stats["refresh_count"] == 1
    assert stats["failure_count"] == 0
    assert stats["last_refresh_duration_ms"] is not None


@pytest.mark.asyncio
async def test_consecutive_failures_trigger_critical_alert():
    """Test critical alert after 3 consecutive failures."""

    async def failing_session_factory():
        mock_session = AsyncMock()
        mock_session.execute.side_effect = Exception("Connection failed")
        yield mock_session

    job = ViewRefreshJob(failing_session_factory)

    with patch("src.infrastructure.background.view_refresh_job.logger") as mock_logger:
        # Trigger 3 failures
        for _ in range(3):
            await job.refresh_analytics_view()

        # Verify critical alert on 3rd failure
        assert any(
            "Immediate attention required" in str(call)
            for call in mock_logger.critical.call_args_list
        )


@pytest.mark.asyncio
async def test_refresh_uses_concurrently():
    """Test that REFRESH uses CONCURRENTLY to avoid locks."""

    mock_session = AsyncMock()

    class MockSessionFactory:
        async def __aenter__(self):
            return mock_session

        async def __aexit__(self, *args):
            pass

    def session_factory():
        return MockSessionFactory()

    job = ViewRefreshJob(session_factory)

    await job.refresh_analytics_view()

    # Verify CONCURRENTLY in SQL
    mock_session.execute.assert_called_once()
    call_args = mock_session.execute.call_args[0][0]
    sql_text = str(call_args)
    assert "CONCURRENTLY" in sql_text
    assert "prompt_analytics_summary" in sql_text


@pytest.mark.asyncio
async def test_stop_reports_final_stats():
    """Test stop() logs final statistics."""

    class MockSessionFactory:
        async def __aenter__(self):
            mock_session = AsyncMock()
            mock_session.execute = AsyncMock()
            mock_session.commit = AsyncMock()
            return mock_session

        async def __aexit__(self, *args):
            pass

    def session_factory():
        return MockSessionFactory()

    job = ViewRefreshJob(session_factory)

    # Run some refreshes
    await job.refresh_analytics_view()
    await job.refresh_analytics_view()

    job.start(interval_minutes=5)

    with patch("src.infrastructure.background.view_refresh_job.logger") as mock_logger:
        job.stop()

        # Verify final stats logged
        assert any(
            "total runs: 2" in str(call) for call in mock_logger.info.call_args_list
        )
