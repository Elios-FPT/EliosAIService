"""Database query monitoring and performance tracking.

Phase 2 Optimization: Event listeners for slow query detection and N+1 pattern identification.
"""

import logging
import time
from collections import defaultdict
from typing import Any

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.pool import Pool, NullPool

from ..config.settings import get_settings

logger = logging.getLogger(__name__)

# Query execution tracking
_query_counts: dict[str, int] = defaultdict(int)
_slow_query_threshold_seconds = 0.5  # 500ms

# Check if monitoring is enabled
settings = get_settings()
MONITORING_ENABLED = settings.db_monitoring_enabled

# Log monitoring state at module initialization
if MONITORING_ENABLED:
    logger.info("Database monitoring enabled (slow query detection, N+1 detection, pool monitoring)")
else:
    logger.info("Database monitoring disabled")


def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    """Record query start time before execution.

    Phase 2: Performance monitoring for slow query detection.
    """
    conn.info.setdefault("query_start_times", []).append(time.time())


if MONITORING_ENABLED:
    event.listens_for(Engine, "before_cursor_execute")(before_cursor_execute)


def after_cursor_execute_slow_query(conn, cursor, statement, parameters, context, executemany):
    """Detect and log slow queries after execution.

    Phase 2: Identifies queries exceeding 500ms threshold.
    Helps detect performance regressions and missing indexes.
    """
    total_time = time.time() - conn.info["query_start_times"].pop(-1)

    if total_time > _slow_query_threshold_seconds:
        # Truncate statement for readability
        statement_preview = statement[:300].replace("\n", " ")
        logger.warning(
            f"Slow query detected ({total_time:.2f}s): {statement_preview}",
            extra={
                "duration_seconds": total_time,
                "threshold_seconds": _slow_query_threshold_seconds,
                "statement": statement,
                "parameters": parameters,
            },
        )


if MONITORING_ENABLED:
    event.listens_for(Engine, "after_cursor_execute")(after_cursor_execute_slow_query)


def after_cursor_execute_n_plus_one_detection(
    conn, cursor, statement, parameters, context, executemany
):
    """Detect potential N+1 query patterns.

    Phase 2: Counts repeated queries with same pattern.
    Triggers warning if same query executed >5 times in single request.
    """
    # Normalize query by removing specific values (basic pattern matching)
    # This is a simple heuristic - production systems would use more sophisticated detection
    query_pattern = statement[:200]  # Use first 200 chars as pattern

    # Track query counts in connection info
    query_counts = conn.info.setdefault("query_patterns", defaultdict(int))
    query_counts[query_pattern] += 1

    # Warn if query executed multiple times (potential N+1)
    if query_counts[query_pattern] > 5:
        logger.warning(
            f"Potential N+1 query pattern detected: Query executed {query_counts[query_pattern]} times",
            extra={
                "query_pattern": query_pattern,
                "execution_count": query_counts[query_pattern],
                "recommendation": "Consider using selectinload() or joinedload() for eager loading",
            },
        )


if MONITORING_ENABLED:
    event.listens_for(Engine, "after_cursor_execute")(after_cursor_execute_n_plus_one_detection)


def on_pool_connect(dbapi_conn, connection_record):
    """Track pool connection events.

    Phase 2: Monitor connection pool usage.
    """
    logger.debug("Database connection established", extra={"pool_event": "connect"})


if MONITORING_ENABLED:
    event.listens_for(Pool, "connect")(on_pool_connect)


def on_pool_checkout(dbapi_conn, connection_record, connection_proxy):
    """Track connection checkout from pool.

    Phase 2: Detect pool exhaustion warnings.
    """
    pool = connection_proxy._pool

    # NullPool (test environment) doesn't have size/overflow/checkedout methods
    if isinstance(pool, NullPool):
        logger.debug(
            "Connection checked out from pool",
            extra={
                "pool_event": "checkout",
                "pool_type": "NullPool",
            },
        )
        return

    # For QueuePool (production), log detailed metrics
    logger.debug(
        f"Connection checked out from pool",
        extra={
            "pool_event": "checkout",
            "pool_type": type(pool).__name__,
            "pool_size": pool.size(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
        },
    )

    # Warn if pool is near capacity
    if pool.overflow() > 0 and pool.checkedout() >= pool.size():
        logger.warning(
            f"Connection pool near capacity: {pool.checkedout()}/{pool.size() + pool.overflow()}",
            extra={
                "pool_size": pool.size(),
                "overflow": pool.overflow(),
                "checked_out": pool.checkedout(),
                "recommendation": "Consider increasing db_pool_size if this warning persists",
            },
        )


if MONITORING_ENABLED:
    event.listens_for(Pool, "checkout")(on_pool_checkout)


def on_pool_checkin(dbapi_conn, connection_record):
    """Track connection return to pool.

    Phase 2: Monitor connection lifecycle.
    """
    # Reset query pattern tracking on checkin
    if hasattr(connection_record, "info"):
        connection_record.info.pop("query_patterns", None)

    logger.debug("Connection returned to pool", extra={"pool_event": "checkin"})


if MONITORING_ENABLED:
    event.listens_for(Pool, "checkin")(on_pool_checkin)


def configure_monitoring_threshold(threshold_seconds: float) -> None:
    """Configure slow query threshold.

    Args:
        threshold_seconds: Threshold in seconds (e.g., 0.5 for 500ms)
    """
    global _slow_query_threshold_seconds
    _slow_query_threshold_seconds = threshold_seconds
    logger.info(f"Slow query threshold set to {threshold_seconds}s")


def get_query_statistics() -> dict[str, Any]:
    """Get query execution statistics.

    Returns:
        Dictionary with query count and pattern information
    """
    return {
        "query_counts": dict(_query_counts),
        "slow_query_threshold": _slow_query_threshold_seconds,
    }
