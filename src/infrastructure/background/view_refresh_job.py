"""Background job for refreshing materialized views."""

import asyncio
import logging
import time
from typing import Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class ViewRefreshJob:
    """Background job to refresh materialized views."""

    def __init__(self, session_factory: Callable):
        """Initialize job with session factory.

        Args:
            session_factory: Async context manager that yields AsyncSession
        """
        self.session_factory = session_factory
        self.scheduler = AsyncIOScheduler()
        self._refresh_count = 0
        self._failure_count = 0
        self._last_refresh_duration_ms: float | None = None

    async def refresh_analytics_view(self) -> None:
        """Refresh prompt_analytics_summary materialized view.

        Logs success/failure and tracks performance metrics.
        """
        try:
            start_time = time.time()

            async with self.session_factory() as session:
                # Use CONCURRENTLY to avoid table locks
                await session.execute(
                    text("REFRESH MATERIALIZED VIEW CONCURRENTLY prompt_analytics_summary")
                )
                await session.commit()

            duration_ms = (time.time() - start_time) * 1000
            self._last_refresh_duration_ms = duration_ms
            self._refresh_count += 1

            logger.info(
                f"Successfully refreshed prompt_analytics_summary "
                f"(run #{self._refresh_count}, duration: {duration_ms:.2f}ms)"
            )

            # Alert if refresh is slow
            if duration_ms > 10000:  # 10 seconds
                logger.warning(
                    f"View refresh took {duration_ms:.2f}ms (>10s threshold). "
                    f"Consider performance tuning."
                )

        except Exception as e:
            self._failure_count += 1
            logger.error(
                f"Failed to refresh materialized view (failure #{self._failure_count}): {e}",
                exc_info=True,
            )

            # Alert if 3 consecutive failures
            if self._failure_count >= 3:
                logger.critical(
                    f"View refresh has failed {self._failure_count} times. "
                    f"Immediate attention required!"
                )

    def start(self, interval_minutes: int = 5) -> None:
        """Start background job scheduler.

        Args:
            interval_minutes: Refresh interval in minutes (default: 5)
        """
        # Schedule refresh at specified interval
        self.scheduler.add_job(
            self.refresh_analytics_view,
            "interval",
            minutes=interval_minutes,
            id="refresh_prompt_analytics",
            name="Refresh Prompt Analytics View",
        )

        self.scheduler.start()
        logger.info(f"Started view refresh job (every {interval_minutes} minutes)")

    def stop(self) -> None:
        """Stop scheduler and cleanup."""
        self.scheduler.shutdown(wait=True)
        logger.info(
            f"Stopped view refresh job "
            f"(total runs: {self._refresh_count}, failures: {self._failure_count})"
        )

    def get_stats(self) -> dict:
        """Get job statistics.

        Returns:
            Dictionary with refresh count, failures, last duration
        """
        return {
            "refresh_count": self._refresh_count,
            "failure_count": self._failure_count,
            "last_refresh_duration_ms": self._last_refresh_duration_ms,
            "is_running": self.scheduler.running,
        }

    async def refresh_now(self) -> None:
        """Manually trigger immediate refresh.

        Useful for testing or manual intervention.
        """
        logger.info("Manual refresh triggered")
        await self.refresh_analytics_view()
