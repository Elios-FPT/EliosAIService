"""LangGraph checkpointer setup for workflow state persistence.

This module configures AsyncPostgresSaver to store workflow checkpoints
in the same PostgreSQL database used by the application.
"""

from sqlalchemy.ext.asyncio import AsyncEngine
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver


async def create_checkpointer(engine: AsyncEngine) -> AsyncPostgresSaver:
    """Create and initialize AsyncPostgresSaver for LangGraph workflows.

    This checkpointer stores workflow state in a PostgreSQL 'checkpoints' table,
    enabling workflows to resume after crashes or interruptions.

    Args:
        engine: SQLAlchemy async engine (shared with application)

    Returns:
        Initialized AsyncPostgresSaver instance

    Raises:
        Exception: If checkpoint table creation fails

    Example:
        >>> from src.infrastructure.database.session import get_async_engine
        >>> engine = get_async_engine()
        >>> checkpointer = await create_checkpointer(engine)
        >>> # Use with LangGraph: app.compile(checkpointer=checkpointer)
    """
    # Create checkpointer with existing async engine
    checkpointer = AsyncPostgresSaver(engine)

    # Initialize (creates 'checkpoints' table if not exists)
    # This is idempotent - safe to call multiple times
    await checkpointer.setup()

    return checkpointer


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
