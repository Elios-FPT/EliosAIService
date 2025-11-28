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
import time
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

# Lazy import to avoid hanging during module import
# AsyncPostgresSaver will be imported only when create_checkpointer is called
logger = logging.getLogger(__name__)


class CheckpointerWrapper:
    """Wrapper to keep AsyncPostgresSaver context manager alive and handle connection errors.

    AsyncPostgresSaver.from_conn_string() returns a context manager that must
    remain open for the connection pool to stay alive. This wrapper keeps the
    context manager alive while proxying all method calls to the checkpointer.

    Also adds retry logic for connection errors (e.g., Neon idle timeout).
    """

    def __init__(
        self,
        context_manager,
        checkpointer,
        conn_string: str,
        timeout: float = 20.0,
        endpoint_type: str = "unknown",
    ):
        """Initialize wrapper.

        Args:
            context_manager: The async context manager from AsyncPostgresSaver.from_conn_string()
            checkpointer: The AsyncPostgresSaver instance
            conn_string: Connection string for recreating checkpointer on errors
            timeout: Timeout for checkpointer recreation
        """
        self._context_manager = context_manager
        self._checkpointer = checkpointer
        self._conn_string = conn_string
        self._timeout = timeout
        self._context_entered = False
        self._recreating = False
        self._retry_count = 0
        self._last_retry_ts: Optional[float] = None
        self.endpoint_type = endpoint_type

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

    async def _recreate_checkpointer(self):
        """Recreate checkpointer after connection error."""
        if self._recreating:
            # Prevent recursive recreation
            return
        self._recreating = True
        try:
            self._retry_count += 1
            now = time.monotonic()
            elapsed = None if self._last_retry_ts is None else now - self._last_retry_ts
            self._last_retry_ts = now
            logger.warning(
                "Recreating checkpointer due to connection error",
                extra={
                    "event": "checkpointer_retry",
                    "retry_count": self._retry_count,
                    "seconds_since_last_retry": round(elapsed, 3) if elapsed is not None else None,
                    "endpoint_type": self.endpoint_type,
                },
            )
            # Exit old context
            if self._context_entered:
                await self._context_manager.__aexit__(None, None, None)
                self._context_entered = False

            # Create new checkpointer
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
            standard_conn_string = _convert_to_standard_postgres_url(self._conn_string)
            new_context_manager = AsyncPostgresSaver.from_conn_string(standard_conn_string)
            new_checkpointer = await new_context_manager.__aenter__()
            await asyncio.wait_for(new_checkpointer.setup(), timeout=self._timeout)

            # Update references
            self._context_manager = new_context_manager
            self._checkpointer = new_checkpointer
            self._context_entered = True
            logger.info(
                "Checkpointer recreated successfully",
                extra={
                    "event": "checkpointer_retry_success",
                    "retry_count": self._retry_count,
                    "endpoint_type": self.endpoint_type,
                },
            )
        except Exception as e:
            logger.error(
                f"Failed to recreate checkpointer: {e}",
                exc_info=True,
                extra={
                    "event": "checkpointer_retry_failed",
                    "retry_count": self._retry_count,
                    "endpoint_type": self.endpoint_type,
                },
            )
            raise
        finally:
            self._recreating = False

    async def _call_with_retry(self, method_name: str, *args, **kwargs):
        """Call checkpointer method with retry on connection errors."""
        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                method = getattr(self._checkpointer, method_name)
                return await method(*args, **kwargs)
            except Exception as e:
                # Check if it's a connection error
                error_str = str(e).lower()
                is_connection_error = any(
                    keyword in error_str
                    for keyword in [
                        "connection",
                        "connection abort",
                        "terminating connection",
                        "could not receive data",
                        "admin shutdown",
                        "operationalerror",
                    ]
                )

                if is_connection_error and attempt < max_retries:
                    logger.warning(
                        f"Connection error in {method_name} (attempt {attempt + 1}/{max_retries + 1}): {e}. "
                        "Recreating checkpointer...",
                        extra={
                            "event": "checkpointer_connection_error",
                            "method": method_name,
                            "attempt": attempt + 1,
                            "endpoint_type": self.endpoint_type,
                        },
                    )
                    await self._recreate_checkpointer()
                    continue
                else:
                    # Not a connection error or max retries reached
                    raise

    async def aget_tuple(self, *args, **kwargs):
        """Get checkpoint tuple with retry logic."""
        return await self._call_with_retry("aget_tuple", *args, **kwargs)

    async def aput(self, *args, **kwargs):
        """Put checkpoint with retry logic."""
        return await self._call_with_retry("aput", *args, **kwargs)

    def alist(self, *args, **kwargs):
        """List checkpoints with retry logic.

        Note: alist() returns an async generator, not a coroutine.
        Consumers should use 'async for' to iterate over results.
        """
        method = getattr(self._checkpointer, "alist")
        return method(*args, **kwargs)

    def __getattr__(self, name):
        """Proxy all other attribute access to the checkpointer."""
        return getattr(self._checkpointer, name)


def _convert_to_standard_postgres_url(sqlalchemy_url: str) -> str:
    """Convert SQLAlchemy connection URL to standard PostgreSQL format.

    AsyncPostgresSaver uses psycopg which expects standard PostgreSQL URLs
    (postgresql:// or postgres://), not SQLAlchemy format (postgresql+asyncpg://).

    For Neon pooler endpoints, we convert to direct connection as psycopg
    may not work well with poolers. Neon poolers use port 5432, direct uses 5432.
    We replace '-pooler' with nothing to get the direct endpoint.

    Also adds keepalive parameters to prevent Neon idle timeout (5 minutes).
    Keepalives are sent every 4 minutes to keep connections alive.

    Args:
        sqlalchemy_url: SQLAlchemy connection string (e.g., postgresql+asyncpg://...)

    Returns:
        Standard PostgreSQL connection string (e.g., postgresql://...) with keepalive params
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

    # Build query parameters
    params = []

    # Add SSL mode for cloud providers
    if is_cloud and 'sslmode=' not in url:
        params.append('sslmode=require')

    # Add keepalive parameters to prevent Neon idle timeout (5 minutes)
    # keepalives_idle: seconds before sending first keepalive (240s = 4 min, before Neon's 5 min timeout)
    # keepalives_interval: seconds between keepalives (30s)
    # keepalives_count: number of failed keepalives before considering connection dead (3)
    if 'keepalives_idle=' not in url:
        params.append('keepalives_idle=240')
    if 'keepalives_interval=' not in url:
        params.append('keepalives_interval=30')
    if 'keepalives_count=' not in url:
        params.append('keepalives_count=3')

    # Append parameters to URL
    if params:
        separator = '?' if '?' not in url else '&'
        url = f"{url}{separator}{'&'.join(params)}"

    return url


def _detect_endpoint_type(sqlalchemy_url: str) -> str:
    """Identify whether URL uses Neon pooler endpoint."""
    lowered = sqlalchemy_url.lower()
    if "-pooler." in lowered:
        return "pooler"
    if "neon.tech" in lowered:
        return "direct"
    return "unknown"


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

        Idle Timeout Protection: For Neon and other cloud providers with idle
        connection timeouts, keepalive parameters are automatically added to the
        connection string:
        - keepalives_idle=240 (4 minutes, before Neon's 5-minute timeout)
        - keepalives_interval=30 (check every 30 seconds)
        - keepalives_count=3 (3 failed keepalives = dead connection)

        This ensures connections stay alive even during idle periods.

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
    endpoint_type = _detect_endpoint_type(conn_string)
    standard_conn_string = _convert_to_standard_postgres_url(conn_string)

    # Log connection string (mask password for security)
    masked_conn_string = re.sub(r':([^:@]+)@', ':***@', standard_conn_string)
    logger.info(
        f"Creating AsyncPostgresSaver checkpointer with connection: {masked_conn_string}",
        extra={"event": "checkpointer_create", "endpoint_type": endpoint_type},
    )
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

        # Create wrapper that keeps context manager alive and handles connection errors
        # The context manager is already entered and will stay entered
        wrapper = CheckpointerWrapper(
            context_manager,
            checkpointer,
            conn_string,
            timeout,
            endpoint_type=endpoint_type,
        )
        wrapper._context_entered = True  # Mark as already entered

        logger.info("Checkpointer created and initialized successfully")
        return wrapper
    except TimeoutError as e:
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
