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

from __future__ import annotations

import asyncio
import logging
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

# Lazy import to avoid hanging during module import
# AsyncPostgresSaver will be imported only when create_checkpointer is called
logger = logging.getLogger(__name__)


class CheckpointerWrapper:
    """Wrapper to keep AsyncPostgresSaver context manager alive.

    AsyncPostgresSaver.from_conn_string() returns a context manager that must
    remain open for the connection pool to stay alive. This wrapper keeps the
    context manager alive while proxying all method calls to the checkpointer.
    """

    def __init__(self, context_manager, checkpointer):
        """Initialize wrapper.

        Args:
            context_manager: The async context manager from AsyncPostgresSaver.from_conn_string()
            checkpointer: The AsyncPostgresSaver instance
        """
        self._context_manager = context_manager
        self._checkpointer = checkpointer
        self._context_entered = False

    async def __aenter__(self):
        """Enter context manager."""
        if not self._context_entered:
            await self._context_manager.__aenter__()
            self._context_entered = True
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager (should not be called during normal operation)."""
        if self._context_entered:
            await self._context_manager.__aexit__(exc_type, exc_val, exc_tb)
            self._context_entered = False

    def __getattr__(self, name):
        """Proxy all attribute access to the checkpointer."""
        return getattr(self._checkpointer, name)


def _convert_to_standard_postgres_url(sqlalchemy_url: str) -> str:
    """Convert SQLAlchemy connection URL to standard PostgreSQL format.

    AsyncPostgresSaver uses psycopg which expects standard PostgreSQL URLs
    (postgresql:// or postgres://), not SQLAlchemy format (postgresql+asyncpg://).

    For Neon pooler endpoints, we convert to direct connection as psycopg
    may not work well with poolers. Neon poolers use port 5432, direct uses 5432.
    We replace '-pooler' with nothing to get the direct endpoint.

    Args:
        sqlalchemy_url: SQLAlchemy connection string (e.g., postgresql+asyncpg://...)

    Returns:
        Standard PostgreSQL connection string (e.g., postgresql://...)
    """
    # Replace postgresql+asyncpg:// with postgresql://
    # Also handle postgres+asyncpg:// for compatibility
    url = re.sub(r'^postgresql\+asyncpg:', 'postgresql:', sqlalchemy_url)
    url = re.sub(r'^postgres\+asyncpg:', 'postgres:', url)

    # Convert Neon pooler endpoint to direct endpoint
    # Pooler: ep-xxx-pooler.region.aws.neon.tech
    # Direct: ep-xxx.region.aws.neon.tech (remove -pooler)
    # psycopg may not work well with poolers, so use direct connection
    url = re.sub(r'([\w-]+)-pooler\.([\w.-]+)', r'\1.\2', url)

    # For cloud providers (Neon, etc.), psycopg may need SSL
    # Check if URL contains cloud provider indicators
    is_cloud = any(provider in url.lower() for provider in ['neon', 'aws', 'azure', 'gcp', 'cloud'])

    # If it's a cloud provider and no sslmode is specified, add sslmode=require
    if is_cloud and 'sslmode=' not in url:
        separator = '?' if '?' not in url else '&'
        url = f"{url}{separator}sslmode=require"

    return url


async def create_checkpointer(conn_string: str, timeout: float = 20.0) -> AsyncPostgresSaver:
    """Create and initialize AsyncPostgresSaver for LangGraph workflows.

    This checkpointer stores workflow state in a PostgreSQL 'checkpoints' table,
    enabling workflows to resume after crashes or interruptions.

    Args:
        conn_string: PostgreSQL connection string (postgresql+asyncpg://... or postgresql://...)
            SQLAlchemy format (postgresql+asyncpg://) will be automatically converted to
            standard PostgreSQL format (postgresql://) for AsyncPostgresSaver.
            Note: AsyncPostgresSaver creates its own connection pool internally.
            Pool size cannot be configured via connection string parameters.
        timeout: Timeout in seconds for checkpointer setup operation (default: 20.0).
            Increase this value if you experience timeouts due to slow network or database connectivity.

    Returns:
        Initialized AsyncPostgresSaver instance

    Raises:
        RuntimeError: If checkpointer setup times out
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
        >>> checkpointer = await create_checkpointer(settings.async_database_url, timeout=20.0)
        >>> # Use with LangGraph: app.compile(checkpointer=checkpointer)
    """
    # Lazy import to avoid hanging during module import
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    # Convert SQLAlchemy connection string to standard PostgreSQL format
    # AsyncPostgresSaver uses psycopg which expects postgresql:// not postgresql+asyncpg://
    # Also convert pooler endpoints to direct endpoints (psycopg may not work with poolers)
    standard_conn_string = _convert_to_standard_postgres_url(conn_string)

    # Log connection string (mask password for security)
    masked_conn_string = re.sub(r':([^:@]+)@', ':***@', standard_conn_string)
    logger.info(f"Creating AsyncPostgresSaver checkpointer with connection: {masked_conn_string}")
    logger.info(f"Setup timeout: {timeout} seconds")
    logger.info("Note: Using separate connection pool from SQLAlchemy (psycopg vs asyncpg)")

    try:
        # AsyncPostgresSaver.from_conn_string() returns an async context manager
        # that MUST remain open for the connection pool to stay alive.
        # We create a wrapper that keeps the context manager alive.
        logger.info("Creating AsyncPostgresSaver context manager...")
        logger.debug(f"Full connection string (masked): {masked_conn_string}")

        # Get the context manager
        context_manager = AsyncPostgresSaver.from_conn_string(standard_conn_string)

        # Enter the context manager and keep it alive
        # We'll use a wrapper to maintain the context
        logger.info("Entering AsyncPostgresSaver context...")
        checkpointer = await context_manager.__aenter__()

        logger.info("AsyncPostgresSaver context entered, calling setup()...")

        # Initialize (creates 'checkpoints' table if not exists)
        # This is idempotent - safe to call multiple times
        # Note: setup() may take time on first run if table doesn't exist
        logger.debug(f"Calling checkpointer.setup() with timeout={timeout}s...")
        await asyncio.wait_for(checkpointer.setup(), timeout=timeout)
        logger.debug("checkpointer.setup() completed")

        logger.info("Checkpointer setup completed successfully")

        # Create wrapper that keeps context manager alive
        # The context manager is already entered and will stay entered
        wrapper = CheckpointerWrapper(context_manager, checkpointer)
        wrapper._context_entered = True  # Mark as already entered

        logger.info("Checkpointer created and initialized successfully")
        return wrapper
    except asyncio.TimeoutError as e:
        logger.error(
            f"Timeout while creating checkpointer after {timeout} seconds. "
            f"Connection string: {masked_conn_string}. "
            f"This may indicate database connectivity issues, slow network, "
            f"or database server not responding. "
            f"Consider increasing langgraph_checkpointer_setup_timeout setting."
        )
        raise RuntimeError(
            f"Checkpointer creation timed out after {timeout} seconds. "
            "Possible causes: database connectivity issues, slow network, "
            "or database server not responding. "
            "Check database connectivity and connection string. "
            f"Consider increasing langgraph_checkpointer_setup_timeout setting (current: {timeout}s)."
        ) from e
    except Exception as e:
        logger.error(
            f"Error creating checkpointer: {e}. "
            f"Connection string: {masked_conn_string}. "
            f"Timeout was set to {timeout}s.",
            exc_info=True
        )
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
