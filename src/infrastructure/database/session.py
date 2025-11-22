"""Database session management with async support.

Connection Pool Management:
    This module manages SQLAlchemy's connection pool for the application.
    However, note that AsyncPostgresSaver (used by LangGraph workflows)
    creates its own separate connection pool.

    Total Database Connections:
    - SQLAlchemy pool (this module):
      * Production: 10 base + 20 overflow = up to 30 connections
      * Development/Testing: NullPool (no pooling)
    - AsyncPostgresSaver pool (langgraph_checkpointer.py):
      * ~5-10 connections (internal, not configurable via API)
    - Total (production): ~35-40 connections

    Recommendations:
    - Configure PostgreSQL max_connections to at least 100
    - Monitor active connections to avoid exceeding limits
    - Consider reducing SQLAlchemy pool_size if connection limits are an issue
"""

from collections.abc import AsyncGenerator

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
            "pool_size": 10,
            "max_overflow": 20,
            "pool_pre_ping": True,  # Verify connections before using
            "pool_recycle": 3600,  # Recycle connections after 1 hour
        })

    engine = create_async_engine(**engine_config)

    return engine


async def init_db() -> None:
    """Initialize database engine and session factory.

    This should be called once during application startup.
    Creates the async engine and configures the session factory.
    """
    global _async_engine, AsyncSessionLocal

    if _async_engine is None:
        _async_engine = create_engine()
        AsyncSessionLocal = async_sessionmaker(
            bind=_async_engine,
            class_=AsyncSession,
            expire_on_commit=False,  # Don't expire objects after commit
            autocommit=False,
            autoflush=False,
        )


async def close_db() -> None:
    """Close database connections and cleanup resources.

    This should be called during application shutdown.
    Disposes the engine and closes all connections.
    """
    global _async_engine, AsyncSessionLocal

    if _async_engine is not None:
        await _async_engine.dispose()
        _async_engine = None
        AsyncSessionLocal = None


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
    if AsyncSessionLocal is None:
        raise RuntimeError(
            "Database not initialized. Call init_db() during application startup."
        )

    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


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
