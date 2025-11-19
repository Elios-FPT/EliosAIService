# Phase 5: Background Jobs

**Parent**: [Implementation Plan](./plan.md)
**Dependencies**: [Phase 1](./phase-01-database-schema.md)
**Created**: 2025-11-20
**Duration**: 1-2 days
**Priority**: Medium
**Status**: ⏳ Pending

---

## Overview

Implement background job to refresh `prompt_analytics_summary` materialized view every 5 minutes. Two implementation options: PostgreSQL pg_cron (recommended) or Python APScheduler.

**Goals**:
- ✅ Auto-refresh materialized view every 5 minutes
- ✅ Logging and error handling
- ✅ Performance monitoring

---

## Option A: PostgreSQL pg_cron (Recommended)

**Pros**:
- Native PostgreSQL extension
- No Python code required
- Runs independently of app
- Built-in scheduling

**Cons**:
- Requires PostgreSQL extension installation
- Less flexible than Python

**Implementation**:

**File**: `alembic/versions/0014_setup_view_refresh_job.py`

```python
"""Setup pg_cron job for materialized view refresh."""

from alembic import op


def upgrade() -> None:
    """Enable pg_cron and schedule refresh job."""
    # Enable pg_cron extension
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_cron;")

    # Schedule refresh every 5 minutes
    op.execute("""
        SELECT cron.schedule(
            'refresh-prompt-analytics',
            '*/5 * * * *',  -- Every 5 minutes
            $$REFRESH MATERIALIZED VIEW CONCURRENTLY prompt_analytics_summary;$$
        );
    """)


def downgrade() -> None:
    """Remove pg_cron job."""
    op.execute("""
        SELECT cron.unschedule('refresh-prompt-analytics');
    """)
```

**Verify Job**:
```sql
-- Check scheduled jobs
SELECT * FROM cron.job WHERE jobname = 'refresh-prompt-analytics';

-- Check job run history
SELECT * FROM cron.job_run_details
WHERE jobid = (SELECT jobid FROM cron.job WHERE jobname = 'refresh-prompt-analytics')
ORDER BY start_time DESC LIMIT 10;
```

---

## Option B: Python APScheduler

**Pros**:
- Full Python control
- Easy to add logging, monitoring
- Can integrate with app startup/shutdown

**Cons**:
- Requires app to be running
- More code to maintain

**Implementation**:

**File**: `src/infrastructure/background/view_refresh_job.py`

```python
"""Background job for refreshing materialized views."""

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class ViewRefreshJob:
    """Background job to refresh materialized views."""

    def __init__(self, session_factory):
        """Initialize job with session factory."""
        self.session_factory = session_factory
        self.scheduler = AsyncIOScheduler()

    async def refresh_analytics_view(self):
        """Refresh prompt_analytics_summary materialized view."""
        try:
            async with self.session_factory() as session:
                start_time = asyncio.get_event_loop().time()

                await session.execute(
                    text("REFRESH MATERIALIZED VIEW CONCURRENTLY prompt_analytics_summary")
                )
                await session.commit()

                duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000

                logger.info(
                    f"Successfully refreshed prompt_analytics_summary in {duration_ms:.2f}ms"
                )
        except Exception as e:
            logger.error(f"Failed to refresh view: {e}", exc_info=True)

    def start(self):
        """Start background job scheduler."""
        # Schedule refresh every 5 minutes
        self.scheduler.add_job(
            self.refresh_analytics_view,
            'interval',
            minutes=5,
            id='refresh_prompt_analytics',
        )

        self.scheduler.start()
        logger.info("Started view refresh job (every 5 minutes)")

    def stop(self):
        """Stop scheduler."""
        self.scheduler.shutdown()
        logger.info("Stopped view refresh job")
```

**Integration**: Add to `src/main.py`

```python
from .infrastructure.background.view_refresh_job import ViewRefreshJob

# Global instance
view_refresh_job = None

@app.on_event("startup")
async def startup_event():
    """Start background jobs on app startup."""
    global view_refresh_job

    # Start view refresh job
    view_refresh_job = ViewRefreshJob(session_factory=get_async_session)
    view_refresh_job.start()

    logger.info("Application started")

@app.on_event("shutdown")
async def shutdown_event():
    """Stop background jobs on app shutdown."""
    global view_refresh_job

    # Stop view refresh job
    if view_refresh_job:
        view_refresh_job.stop()

    logger.info("Application shutdown")
```

**Add Dependency**: `pyproject.toml`

```toml
dependencies = [
    # ... existing
    "apscheduler>=3.10.0",  # Background job scheduling
]
```

---

## Implementation Steps

### Option A: pg_cron (Recommended)

**Step 1**: Install pg_cron Extension (10 min)
```bash
# Ubuntu/Debian
sudo apt-get install postgresql-contrib

# Or via Docker
docker exec -it postgres psql -U postgres -c "CREATE EXTENSION pg_cron;"
```

**Step 2**: Create Migration (30 min)
- [ ] Create `alembic/versions/0014_setup_view_refresh_job.py`
- [ ] Add `CREATE EXTENSION pg_cron`
- [ ] Add `cron.schedule()` call
- [ ] Test migration

**Step 3**: Verification (10 min)
- [ ] Run migration: `alembic upgrade head`
- [ ] Verify job scheduled: `SELECT * FROM cron.job;`
- [ ] Wait 5 minutes, check `cron.job_run_details`

### Option B: APScheduler

**Step 1**: Create Background Job Class (1-2 hours)
- [ ] Create `src/infrastructure/background/view_refresh_job.py`
- [ ] Implement `refresh_analytics_view()` with logging
- [ ] Implement `start()` and `stop()` methods

**Step 2**: Integrate with App Lifecycle (30 min)
- [ ] Modify `src/main.py`
- [ ] Add startup event handler
- [ ] Add shutdown event handler
- [ ] Test app startup/shutdown

**Step 3**: Add Dependency (5 min)
- [ ] Add `apscheduler` to `pyproject.toml`
- [ ] Run `pip install -e .`

---

## Testing

### Manual Testing

**Option A (pg_cron)**:
```sql
-- 1. Verify job exists
SELECT * FROM cron.job WHERE jobname = 'refresh-prompt-analytics';

-- 2. Manually trigger job
SELECT cron.schedule(
    'manual-refresh',
    '* * * * *',  -- Every minute (for testing)
    $$REFRESH MATERIALIZED VIEW CONCURRENTLY prompt_analytics_summary;$$
);

-- 3. Wait 1 minute, check run history
SELECT * FROM cron.job_run_details ORDER BY start_time DESC LIMIT 1;

-- 4. Remove test job
SELECT cron.unschedule('manual-refresh');
```

**Option B (APScheduler)**:
```python
# tests/integration/test_view_refresh_job.py
async def test_view_refresh_job():
    """Test background job refreshes view."""
    job = ViewRefreshJob(session_factory)
    job.start()

    # Wait for next run (max 5 min)
    await asyncio.sleep(5 * 60)

    # Verify view was refreshed
    async with session_factory() as session:
        result = await session.execute(
            text("SELECT last_executed_at FROM prompt_analytics_summary LIMIT 1")
        )
        last_run = result.scalar()
        assert last_run is not None

    job.stop()
```

---

## Monitoring

**Metrics to Track**:
- Refresh frequency (every 5 minutes)
- Refresh duration (should be <5 seconds for 10k executions)
- Failure rate (should be 0%)

**Logging**:
```python
logger.info("Refreshing prompt_analytics_summary...")
logger.info(f"Refresh completed in {duration_ms:.2f}ms")
logger.error(f"Refresh failed: {error}", exc_info=True)
```

**Alerts**:
- Alert if refresh fails 3 times consecutively
- Alert if refresh duration >10 seconds

---

## Success Criteria

- ✅ Materialized view refreshes every 5 minutes
- ✅ Refresh duration <5 seconds (for 10k executions)
- ✅ Failures logged with stack traces
- ✅ Job starts on app startup (Option B)
- ✅ Job stops on app shutdown (Option B)
- ✅ No data corruption (CONCURRENTLY prevents locks)

---

## Performance Tuning

**If refresh is slow (>5 seconds)**:

1. **Add indexes** on join columns:
```sql
CREATE INDEX idx_executions_template_id ON prompt_executions(prompt_template_id);
```

2. **Partition `prompt_executions`** by month:
```sql
CREATE TABLE prompt_executions_2025_11 PARTITION OF prompt_executions
FOR VALUES FROM ('2025-11-01') TO ('2025-12-01');
```

3. **Increase `work_mem`** for aggregation:
```sql
SET work_mem = '256MB';
REFRESH MATERIALIZED VIEW CONCURRENTLY prompt_analytics_summary;
```

---

## Related Files

**Option A (pg_cron)**:
- `alembic/versions/0014_setup_view_refresh_job.py` (new)

**Option B (APScheduler)**:
- `src/infrastructure/background/view_refresh_job.py` (new)
- `src/main.py` (modified)
- `pyproject.toml` (modified - add apscheduler)

---

## Next Phase

→ [Phase 6: LLM Integration](./phase-06-llm-integration.md)

**Blockers**: Phase 1 complete (materialized view exists)

---

## Notes

- Use `REFRESH MATERIALIZED VIEW CONCURRENTLY` to avoid table locks
- pg_cron runs in PostgreSQL backend (survives app restarts)
- APScheduler runs in app process (requires app to be running)
- Recommended: Start with Option A (pg_cron), fallback to Option B if pg_cron unavailable

---

**Phase Status**: Ready to implement
**Last Updated**: 2025-11-20
