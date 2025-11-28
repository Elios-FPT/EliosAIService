"""Database session management with async support.

Connection Pool Management:
    This module manages SQLAlchemy's connection pool for the application.
    However, note that AsyncPostgresSaver (used by LangGraph workflows)
    creates its own separate connection pool.

    Neon / Serverless Considerations:
    - Neon free tier closes idle connections after ~5 minutes.
    - We mitigate by enabling pool_pre_ping and recycling connections before 4 minutes.
    - Keep pool sizes conservative (defaults: 5 base + 5 overflow) to stay within Neon limits.

    Total Database Connections (default production config):
    - SQLAlchemy pool (this module): up to 10 connections (5 base + 5 overflow)
    - AsyncPostgresSaver pool (langgraph_checkpointer.py): ~5-10 connections
    - Total: ~15-20 connections

    Recommendations:
    - Monitor active connections to avoid exceeding Neon quotas.
    - Increase pool sizes only if Neon plan allows higher limits.
"""

from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool, QueuePool

from ..config.settings import get_settings

# Global engine instance
_async_engine: AsyncEngine | None = None
AsyncSessionLocal: async_sessionmaker[AsyncSession] | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def create_engine() -> AsyncEngine:
    """Create and configure the async database engine.

    Returns:
        Configured async SQLAlchemy engine

    Notes:
        - Uses connection pooling in production for better performance
        - Disables pooling in testing to avoid connection leaks
        - Enables echo in development for SQL debugging
    """
    settings = get_settings()

    # Configure pool based on environment
    is_prod = settings.is_production()
    poolclass = QueuePool if is_prod else NullPool

    # Base engine configuration
    # Set echo=False to prevent SQLAlchemy from adding its own handler
    # SQL logging will be handled by the logging configuration instead
    engine_config = {
        "url": settings.async_database_url,
        "echo": False,  # Disable echo to prevent duplicate handlers
        "poolclass": poolclass,
    }

    # Add pool-specific parameters only when using QueuePool
    if is_prod:
        engine_config.update({
            "pool_size": settings.db_pool_size,
            "max_overflow": settings.db_max_overflow,
            "pool_timeout": settings.db_pool_timeout,
            "pool_pre_ping": True,  # Verify connections before using
            # Recycle connections before Neon idle timeout (~5 minutes)
            "pool_recycle": settings.db_pool_recycle_seconds,
        })
    else:
        # Even without pooling, pre-ping protects long-lived single connections
        engine_config.update({
            "pool_pre_ping": True,
        })

    engine = create_async_engine(**engine_config)

    return engine


async def init_db() -> None:
    """Initialize database engine and session factory.

    This should be called once during application startup.
    Creates the async engine and configures the session factory.
    """
    global _async_engine, AsyncSessionLocal, _session_factory

    if _async_engine is None:
        _async_engine = create_engine()
        _session_factory = async_sessionmaker(
            bind=_async_engine,
            class_=AsyncSession,
            expire_on_commit=False,  # Don't expire objects after commit
            autocommit=False,
            autoflush=False,
        )
        AsyncSessionLocal = _session_factory  # Backwards-compatible alias


async def close_db() -> None:
    """Close database connections and cleanup resources.

    This should be called during application shutdown.
    Disposes the engine and closes all connections.
    """
    global _async_engine, AsyncSessionLocal, _session_factory

    if _async_engine is not None:
        await _async_engine.dispose()
        _async_engine = None
        AsyncSessionLocal = None
        _session_factory = None


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Get an async database session.

    This is a dependency injection function for FastAPI.
    It yields a session and ensures proper cleanup.

    Yields:
        AsyncSession: Database session

    Example:
        ```python
        @app.get("/users")
        async def get_users(db: AsyncSession = Depends(get_async_session)):
            result = await db.execute(select(User))
            return result.scalars().all()
        ```
    """
    async with session_scope() as session:
        yield session


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the global async session factory."""
    if _session_factory is None:
        raise RuntimeError(
            "Database not initialized. Call init_db() during application startup."
        )
    return _session_factory


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """Yield a managed AsyncSession for background tasks or manual usage.

    Ensures consistent rollback/cleanup semantics outside of FastAPI dependencies.
    """
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


def get_engine() -> AsyncEngine:
    """Get the current async database engine.

    Returns:
        AsyncEngine: The global async engine instance

    Raises:
        RuntimeError: If database not initialized
    """
    if _async_engine is None:
        raise RuntimeError(
            "Database not initialized. Call init_db() during application startup."
        )
    return _async_engine
