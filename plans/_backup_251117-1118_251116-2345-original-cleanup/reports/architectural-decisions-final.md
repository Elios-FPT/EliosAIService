# Architectural Decisions - Final Approved

**Date**: 2025-11-16
**Status**: ✅ APPROVED
**Based On**: User feedback and analysis

---

## Executive Summary

All architectural decisions finalized based on user goals:
1. **Prompt Management**: Enable UI for testing, tracking, improvement
2. **Session Management**: Optimize thread ID storage for cleanup and analytics

---

## Decision 1: Prompt Storage Strategy

### User Goal
> "I can build a UI for easily prompt testing, tracking and improvement"

### Decision: **PostgreSQL JSONB + Python Fallback** ✅

**Rationale**:
- Database enables non-technical team to edit prompts via UI
- Versioning allows rollback to previous versions
- A/B testing infrastructure built-in (traffic splitting)
- Analytics tracking (token usage, latency, success rate)
- Python fallback ensures resilience if DB fails

**Implementation**:
```
Database Tables:
├── prompt_templates (stores versioned prompts)
│   ├── Versioning: name + version (unique constraint)
│   ├── Lifecycle: is_active, is_draft flags
│   ├── A/B Testing: ab_test_group, traffic_percentage
│   └── Analytics: total_executions, avg_tokens, success_rate
│
└── prompt_executions (tracks every LLM call)
    ├── Performance: tokens_used, latency_ms
    ├── Context: interview_id, candidate_id
    └── Debugging: input_variables, output_text, error_message

PromptRepository Pattern:
├── 1. Check in-memory cache (5-min TTL)
├── 2. Query database (active prompt)
└── 3. Fallback to Python constants (safety net)
```

**Files Created**:
- `phase-01-database-schema.md` - Complete schema + migrations
- Migration `0004_create_prompt_management_tables.py`
- Migration `0005_seed_initial_prompts.py`

**Benefits**:
- ✅ UI-driven prompt iteration (FastAPI + React admin panel)
- ✅ Zero downtime deployments (hot-swap prompts)
- ✅ Cost optimization (track which prompts use most tokens)
- ✅ Quality improvement (A/B test prompts, pick winner)

**Trade-offs**:
- ⚠️ DB query overhead (mitigated: in-memory cache)
- ⚠️ Schema migrations required (one-time cost)
- ⚠️ More complex than Python modules (acceptable for UI benefit)

**Rejected Alternatives**:
- ❌ Python modules: No UI, requires deployment for changes
- ❌ YAML files: No UI, no analytics, no A/B testing

---

## Decision 2: Thread ID Storage Strategy

### User Goal
> "Optimized Thread - analyze what happens when use Interview entity field vs separate table"

### Decision: **Separate `websocket_sessions` Table** ✅

**Rationale**:
- Clean separation: Interview = domain, WebSocketSession = infrastructure
- Easy cleanup queries (idle >10 minutes)
- Rich metadata for debugging (IP, user agent, connection time)
- Analytics-ready (session duration, reconnection rates)
- No Interview entity pollution

**Analysis: Interview Entity Field vs Separate Table**

| Aspect | Interview Field | Separate Table | Winner |
|--------|----------------|----------------|---------|
| **Simplicity** | ✅ One field, no JOIN | ⚠️ New table | Interview |
| **Cleanup Queries** | ❌ Hard: `WHERE thread_id IS NOT NULL AND last_activity < cutoff` (need new field) | ✅ Easy: `WHERE last_activity_at < cutoff AND is_active = true` | **Table** |
| **Metadata** | ❌ Can't store IP, user agent without polluting Interview | ✅ Rich metadata (connection_id, IP, user agent) | **Table** |
| **Analytics** | ❌ Hard: Session duration, reconnection rate | ✅ Easy: Built-in timestamps, queryable | **Table** |
| **Domain Purity** | ❌ Mixes domain (Interview) with infrastructure (thread_id) | ✅ Clean separation of concerns | **Table** |
| **Scalability** | ❌ Interview table grows, slows down | ✅ Can move to Redis later | **Table** |

**What Happens: Interview Entity Field**
```python
# Problem 1: Finding idle sessions
# Need to add `last_websocket_activity_at` to Interview (entity bloat)
idle_interviews = await session.execute(
    select(Interview)
    .where(Interview.thread_id.isnot(None))
    .where(Interview.last_websocket_activity_at < cutoff)
)
# Returns full Interview objects (wasteful - we only need thread_id)

# Problem 2: No metadata
# Can't answer: "Which IP has most reconnections?"
# Can't answer: "What's average session duration?"

# Problem 3: Domain pollution
class Interview:
    # Domain fields
    id: UUID
    candidate_id: UUID
    status: InterviewStatus

    # Infrastructure fields (BAD - violates SRP)
    thread_id: str | None
    last_websocket_activity_at: datetime | None
    websocket_connection_id: str | None  # More pollution...
```

**What Happens: Separate Table**
```python
# Benefit 1: Efficient cleanup
idle_sessions = await websocket_session_repo.get_idle_sessions(timeout_minutes=10)
# Returns lightweight WebSocketSession objects (only needed fields)

for session in idle_sessions:
    await langgraph_checkpointer.delete_thread(session.thread_id)
    await websocket_session_repo.delete_session(session.thread_id)

# Benefit 2: Rich analytics
avg_duration = await session.execute(
    select(func.avg(
        extract('epoch', WebSocketSessionModel.disconnected_at - WebSocketSessionModel.created_at)
    ))
)

# Benefit 3: Clean domain
class Interview:
    # Only domain fields (✅ Clean)
    id: UUID
    candidate_id: UUID
    status: InterviewStatus
    # No infrastructure leakage

class WebSocketSession:
    # Infrastructure fields (✅ Separated)
    thread_id: str
    interview_id: UUID  # Links to domain
    ip_address: str
    connection_id: str
    last_activity_at: datetime
```

**Implementation**:
```sql
CREATE TABLE websocket_sessions (
    id UUID PRIMARY KEY,
    thread_id VARCHAR(100) UNIQUE NOT NULL,
    interview_id UUID NOT NULL REFERENCES interviews(id) ON DELETE CASCADE,
    candidate_id UUID NOT NULL REFERENCES candidates(id),

    -- Metadata (debugging, security, analytics)
    connection_id VARCHAR(100),
    ip_address INET,
    user_agent TEXT,

    -- Lifecycle
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    last_activity_at TIMESTAMP NOT NULL DEFAULT NOW(),
    disconnected_at TIMESTAMP,
    is_active BOOLEAN DEFAULT true,

    -- Cleanup tracking
    checkpoint_count INTEGER DEFAULT 0,
    last_checkpoint_size_kb INTEGER,

    INDEX idx_thread_id (thread_id),
    INDEX idx_interview_id (interview_id),
    INDEX idx_last_activity (last_activity_at, is_active)  -- For cleanup queries
);
```

**Cleanup Background Task**:
```python
@scheduler.task("interval", minutes=5)
async def cleanup_idle_websocket_sessions():
    """Delete idle sessions (>10 min) and their checkpoints."""
    idle_sessions = await websocket_session_repo.get_idle_sessions(timeout_minutes=10)

    for session in idle_sessions:
        # 1. Delete LangGraph checkpoint
        await langgraph_checkpointer.delete_thread(session.thread_id)

        # 2. Delete session record
        await websocket_session_repo.delete_session(session.thread_id)

        logger.info(f"Cleaned up idle session {session.thread_id}")
```

**Benefits**:
- ✅ Efficient cleanup (indexed query on `last_activity_at`)
- ✅ Analytics queries (session duration, reconnection rate)
- ✅ Debugging (IP address, user agent, connection ID)
- ✅ Domain purity (Interview unchanged)
- ✅ Scalable (can move to Redis for high-throughput)

**Trade-offs**:
- ⚠️ One more table (acceptable - 5 columns)
- ⚠️ Need to JOIN for interview context (mitigated: proper indexing)

**Rejected Alternative**:
- ❌ Interview entity field: Pollutes domain, hard to query, no metadata

---

## Updated Plan Files

### New Files Created
1. **`phase-01-database-schema.md`** - Prompt management schema
   - `prompt_templates` table
   - `prompt_executions` table
   - Migration scripts (0004, 0005)
   - Seed data

2. **`reports/architectural-decisions-final.md`** - This file
   - Decision rationale
   - Trade-off analysis
   - Implementation details

### Modified Files
1. **`plan.md`**:
   - Added architectural decisions section
   - Updated database schema section
   - Added prompt caching decision

2. **`phase-01-langchain-adapter.md`**:
   - Added PromptRepository component
   - Updated architecture section
   - Added database-backed prompts

3. **`phase-03b-websocket-interrupts.md`**:
   - Replaced Interview.thread_id with WebSocketSession table
   - Added repository port/implementation
   - Added cleanup background task

---

## Migration Timeline

### Phase 1 (Week 1-2): Prompt Management
**Day 1-2**: Database setup
- Run migration `0004_create_prompt_management_tables`
- Run migration `0005_seed_initial_prompts`
- Verify tables: `SELECT * FROM prompt_templates;`

**Day 3-5**: Repository implementation
- Implement `PromptRepository` with cache + fallback
- Integrate with `LangChainAdapter`
- Unit tests

**Day 6-7**: Testing
- A/B test: Python prompts vs DB prompts (same output?)
- Performance test: Cache hit rate >90%
- Integration test: DB failure → fallback works

**Optional (Month 2)**: Admin UI
- FastAPI endpoint: `/admin/prompts`
- React UI: List, edit, version, A/B test
- Analytics dashboard

### Phase 3B (Week 6): WebSocket Sessions
**Day 1**: Database setup
- Create migration for `websocket_sessions` table
- Create `WebSocketSession` domain model
- Create repository port + implementation

**Day 2-3**: Integration
- Update WebSocket handler to create sessions
- Store thread_id in session (not Interview)
- Implement cleanup background task

**Day 4**: Testing
- Test session creation on connect
- Test cleanup after 10 min idle
- Test reconnection (thread_id lookup)

---

## Success Criteria

### Prompt Management
- ✅ Prompts editable via SQL (Phase 1)
- ✅ Cache hit rate >90% (performance)
- ✅ Fallback works if DB fails (resilience)
- ✅ Analytics queries functional (token usage, latency)
- 🔮 Admin UI deployed (Phase 1 optional, defer to Month 2)

### Session Management
- ✅ WebSocket sessions tracked in separate table
- ✅ Idle sessions cleaned up after 10 minutes
- ✅ Reconnection works (thread_id lookup)
- ✅ Analytics queries functional (avg duration, reconnection rate)
- ✅ Interview entity unchanged (domain purity preserved)

---

## Cost Impact

**Prompt Management**:
- Database storage: ~1 MB for 100 prompts × 10 versions = negligible
- Query overhead: ~5ms (mitigated by cache)
- Analytics storage: ~10 GB/year for 1M executions (acceptable)

**Session Management**:
- Database storage: ~1 KB/session × 1000 active = 1 MB (negligible)
- Cleanup overhead: 1 query every 5 min = minimal
- Analytics value: High (understand usage patterns, optimize costs)

**Net Cost**: Negligible storage/compute, high analytics value

---

## Conclusion

**Both Decisions Approved** ✅

**Prompt Storage**: Database enables UI, A/B testing, analytics (aligns with user goal)
**Thread ID Storage**: Separate table optimizes cleanup, analytics, domain purity

**Next Actions**:
1. Review `phase-01-database-schema.md` for migration details
2. Start Phase 0 (prototypes & benchmarks)
3. After Phase 0 validation → implement Phase 1 with DB prompts

---

**Document Status**: Final
**Approved By**: User
**Implementation**: Ready to Start
