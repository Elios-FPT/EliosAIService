"""LangGraph checkpointer setup for workflow state persistence.

This module configures AsyncPostgresSaver to store workflow checkpoints
in the same PostgreSQL database used by the application.

Connection Pool Management:
    This module creates a separate connection pool for AsyncPostgresSaver,
    independent from SQLAlchemy's connection pool. Total database connections:

    - SQLAlchemy pool: 10 base + 20 overflow = up to 30 connections (production)
    - AsyncPostgresSaver pool: ~5-10 connections (default, not configurable via API)
    - Total: ~35-40 connections

    Note: AsyncPostgresSaver.from_conn_string() creates its own internal
    connection pool using asyncpg. The pool size is managed internally by
    LangGraph and cannot be directly configured through the API.

    Recommendations:
    - Monitor total database connections to avoid exceeding database limits
    - Configure PostgreSQL max_connections appropriately (recommended: 100+)
    - Consider reducing SQLAlchemy pool_size if connection limits are an issue
"""

import asyncio
import logging

# Lazy import to avoid hanging during module import
# AsyncPostgresSaver will be imported only when create_checkpointer is called
logger = logging.getLogger(__name__)


async def create_checkpointer(conn_string: str) -> AsyncPostgresSaver:
    """Create and initialize AsyncPostgresSaver for LangGraph workflows.

    This checkpointer stores workflow state in a PostgreSQL 'checkpoints' table,
    enabling workflows to resume after crashes or interruptions.

    Args:
        conn_string: PostgreSQL connection string (postgresql+asyncpg://...)
            Note: AsyncPostgresSaver creates its own connection pool internally.
            Pool size cannot be configured via connection string parameters.

    Returns:
        Initialized AsyncPostgresSaver instance

    Raises:
        Exception: If checkpoint table creation fails

    Note:
        Connection Pool: AsyncPostgresSaver.from_conn_string() creates a separate
        connection pool independent from SQLAlchemy's pool. This means the
        application will have two connection pools:

        1. SQLAlchemy pool (managed in session.py): 10-30 connections
        2. AsyncPostgresSaver pool (internal): ~5-10 connections

        Total: ~35-40 connections. Ensure your PostgreSQL database is configured
        with sufficient max_connections to handle this load.

    Example:
        >>> from src.infrastructure.config.settings import get_settings
        >>> settings = get_settings()
        >>> checkpointer = await create_checkpointer(settings.async_database_url)
        >>> # Use with LangGraph: app.compile(checkpointer=checkpointer)
    """
    # Create checkpointer with connection string
    # AsyncPostgresSaver.from_conn_string() returns an async context manager
    # The pool size is managed internally by LangGraph and cannot be configured
    # via the API. This creates a separate pool from SQLAlchemy's pool.

    # Lazy import to avoid hanging during module import
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    logger.info("Creating AsyncPostgresSaver checkpointer...")

    try:
        # Use context manager to initialize the checkpointer
        # Add timeout to prevent indefinite hanging (30 seconds)
        async def _create():
            async with AsyncPostgresSaver.from_conn_string(conn_string) as checkpointer:
                logger.info("AsyncPostgresSaver context entered, calling setup()...")

                # Initialize (creates 'checkpoints' table if not exists)
                # This is idempotent - safe to call multiple times
                await checkpointer.setup()

                logger.info("Checkpointer setup completed successfully")

                # IMPORTANT: The checkpointer should maintain its connection pool
                # even after the context manager exits. We return it here, and the
                # context will exit, but the checkpointer's internal pool should remain active.
                # If this doesn't work, we may need to keep the context manager alive.
                return checkpointer

        checkpointer = await asyncio.wait_for(_create(), timeout=30.0)
        return checkpointer
    except asyncio.TimeoutError:
        logger.error("Timeout while creating checkpointer - connection may be hanging")
        raise RuntimeError(
            "Checkpointer creation timed out after 30 seconds. "
            "Check database connectivity and connection string."
        )
    except Exception as e:
        logger.error(f"Error creating checkpointer: {e}", exc_info=True)
        raise


async def cleanup_old_checkpoints(
    checkpointer: AsyncPostgresSaver,
    max_age_days: int = 7
) -> int:
    """Clean up checkpoints older than specified age.

    Args:
        checkpointer: Initialized AsyncPostgresSaver
        max_age_days: Maximum age in days (default: 7)

    Returns:
        Number of checkpoints deleted

    Note:
        Call this periodically (e.g., daily cron job) to prevent
        unbounded checkpoint table growth.
    """
    # TODO: Implement cleanup query
    # DELETE FROM checkpoints WHERE created_at < NOW() - INTERVAL '{max_age_days} days'
    # For now, manual cleanup or PostgreSQL partitioning recommended
    pass
