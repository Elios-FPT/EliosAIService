# Phase 2: LangGraph Planning Workflow

**Phase ID**: 02
**Created**: 2025-11-16
**Priority**: Medium
**Estimated Duration**: 2 weeks
**Risk Level**: Medium
**Implementation Status**: Not Started
**Review Status**: Pending

---

## Context Links

- **Parent Plan**: [plan.md](plan.md)
- **Dependencies**: Phase 1 (LangChain adapter must be complete)
- **Related Docs**:
  - [System Architecture](../../docs/system-architecture.md)
  - [Research: LangGraph Workflows](research/researcher-02-langgraph-workflows.md)

---

## Overview

Migrate `PlanInterviewUseCase` from sequential question generation to parallel LangGraph StateGraph workflow with PostgreSQL checkpointing.

**Current Problem**:
- Sequential LLM calls (generate question → ideal answer → rationale) × n
- No crash recovery (partial generation lost)
- 15-30s to generate 5 questions (blocking)

**Solution**:
- LangGraph StateGraph with parallel generation nodes
- AsyncPostgresSaver for resumable workflows
- Real-time progress streaming via WebSocket
- 3-5x performance improvement (parallel execution)

---

## Key Insights

**From Research**:
1. **Parallel Execution**: `RunnableParallel` in single node generates all questions simultaneously
2. **Checkpointing**: `AsyncPostgresSaver` auto-creates `checkpoints` table, stores state on each node
3. **Resume Logic**: `app.aget_state(thread_id)` retrieves last checkpoint, `app.aupdate_state()` resumes
4. **Error Recovery**: Retry nodes with exponential backoff for rate limits, fallback to cached questions
5. **WebSocket Streaming**: `astream_events()` emits progress events (question 1/5 generated...)

---

## Requirements

### Functional Requirements
**FR1**: Generate n questions (2-5) based on CV skill diversity
**FR2**: Parallel generation: questions, ideal answers, rationales in single batch
**FR3**: Store questions in DB with vector embeddings (non-blocking)
**FR4**: Resume on crash from last checkpoint
**FR5**: Stream progress to WebSocket client (0%, 20%, 40%...)

### Non-Functional Requirements
**NFR1**: Performance: 3-5x faster than sequential (target: <5s for 5 questions)
**NFR2**: Reliability: 99% success rate with retry logic
**NFR3**: Testability: Mock LangGraph nodes independently
**NFR4**: Backward Compatibility: Feature flag `USE_LANGGRAPH_PLANNING` allows fallback

---

## Architecture

### Current Flow (Sequential)
```
PlanInterviewUseCase.execute():
  1. Load CV analysis (DB query)
  2. Calculate n (2-5 based on skill diversity)
  3. FOR i in range(n):
       a. Build search query
       b. Find exemplars (vector search)
       c. Generate question (LLM)      ← 3s
       d. Generate ideal answer (LLM)  ← 3s
       e. Generate rationale (LLM)     ← 2s
       f. Store question (DB)
  4. Mark interview as QUESTIONING

Total: 8s × 5 = 40s
```

### LangGraph Flow (Parallel + Checkpointed)
```
StateGraph nodes:
┌─────────────────────────────────────────────────┐
│ START                                           │
└────────────┬────────────────────────────────────┘
             ↓
    ┌────────────────┐
    │ load_cv_node   │ ← Fetch CVAnalysis from repo
    └────────┬───────┘
             ↓ [checkpoint 1]
    ┌────────────────────┐
    │ calculate_count    │ ← n = 2-5 (skill diversity)
    └────────┬───────────┘
             ↓ [checkpoint 2]
    ┌────────────────────┐
    │ prepare_specs      │ ← Build question specs array
    └────────┬───────────┘
             ↓ [checkpoint 3]
    ┌────────────────────────────────────┐
    │ generate_batch_parallel (RunnableBatch)│ ← ALL questions in parallel
    │  - questions × n                   │
    │  - ideal_answers × n               │
    │  - rationales × n                  │
    └────────┬───────────────────────────┘
             ↓ [checkpoint 4] ← 3-5s total (parallel)
    ┌────────────────────┐
    │ store_questions    │ ← Save to DB + vector embeddings
    └────────┬───────────┘
             ↓ [checkpoint 5]
    ┌────────────────────┐
    │ update_interview   │ ← Mark as QUESTIONING
    └────────┬───────────┘
             ↓
    ┌────────────────────┐
    │ END                │
    └────────────────────┘

Conditional edges:
- If CV not found → error_node
- If generation fails → retry_node (3 attempts) → fallback_node (use cached questions)
```

### State Definition
```python
# src/application/workflows/planning_workflow.py
class PlanningState(TypedDict):
    cv_analysis_id: UUID
    candidate_id: UUID
    cv_analysis: CVAnalysis | None
    question_count: int
    question_specs: list[dict[str, Any]]  # skill, difficulty, exemplars
    generated_questions: list[str]
    generated_answers: list[str]
    generated_rationales: list[str]
    stored_question_ids: list[UUID]
    interview: Interview | None
    errors: list[str]
    checkpoint_thread_id: str
```

### Component Responsibilities
**PlanningWorkflow** (`src/application/workflows/planning_workflow.py`):
- Build StateGraph with 6 nodes
- Configure AsyncPostgresSaver
- Expose `execute()` method for use case

**PlanInterviewUseCase** (refactored):
- Delegate to `workflow.execute(cv_analysis_id, candidate_id)`
- Feature flag check: `if settings.use_langgraph_planning`
- Backward compatibility: fallback to manual implementation

**AsyncPostgresSaver** (`src/infrastructure/database/langgraph_checkpointer.py`):
- Initialize in DI container (singleton)
- Call `await checkpointer.setup()` on startup
- Reuse existing async engine (no new connections)

---

## Related Code Files

### Existing Files to Modify
1. **`src/application/use_cases/plan_interview.py`**:
   - Add conditional: `if settings.use_langgraph_planning: return workflow.execute()`
   - Keep existing logic as fallback

2. **`src/infrastructure/dependency_injection/container.py`**:
   - Add `planning_workflow()` method
   - Inject LLM, repos, checkpointer

3. **`src/infrastructure/config/settings.py`**:
   - Add `use_langgraph_planning: bool = False`
   - Add `langgraph_checkpointer_type: str = "postgresql"`

### New Files to Create
1. **`src/application/workflows/planning_workflow.py`** (250 lines):
   - `PlanningState` TypedDict
   - `PlanningWorkflow` class with StateGraph
   - 6 node functions (load_cv, calculate, prepare, generate_batch, store, update)
   - Error handling nodes (retry, fallback)

2. **`src/application/workflows/base_workflow.py`** (80 lines):
   - Abstract base class for workflows
   - Common utilities (thread_id generation, error formatting)

3. **`src/infrastructure/database/langgraph_checkpointer.py`** (60 lines):
   - Setup AsyncPostgresSaver with existing engine
   - Connection pool configuration

4. **`tests/unit/application/workflows/test_planning_workflow.py`** (300 lines):
   - Test each node independently (mock repos)
   - Test conditional edges (error paths)
   - Test checkpoint/resume logic

5. **`tests/integration/workflows/test_planning_integration.py`** (150 lines):
   - End-to-end workflow test with real DB
   - Crash simulation and resume test

---

## Implementation Steps

### Step 1: Setup AsyncPostgresSaver (2 days)
1. Install dependencies: `langgraph-checkpoint-postgres==^0.2.0`
2. Create `langgraph_checkpointer.py`:
   ```python
   from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

   async def create_checkpointer(engine: AsyncEngine) -> AsyncPostgresSaver:
       checkpointer = AsyncPostgresSaver(engine)
       await checkpointer.setup()  # Creates checkpoints table
       return checkpointer
   ```
3. Update DI container: `self._checkpointer = create_checkpointer(self.async_engine)`
4. Test checkpoint table creation in dev DB

### Step 2: Create Base Workflow Class (1 day)
1. Define abstract base with `execute()` method
2. Add thread_id generation utility
3. Add error formatting helpers
4. Write unit tests

### Step 3: Implement PlanningState & Nodes (3 days)
1. Define `PlanningState` TypedDict with all fields
2. Implement nodes:
   - `load_cv_node`: Fetch from repo, handle not found
   - `calculate_count_node`: n = min(5, max(2, unique_skills // 3))
   - `prepare_specs_node`: Build question specs with exemplars
   - `generate_batch_node`: Use `RunnableParallel` for all LLM calls
   - `store_questions_node`: Save to DB, generate embeddings
   - `update_interview_node`: Mark as QUESTIONING
3. Add error nodes: `retry_node`, `fallback_node`

### Step 4: Build StateGraph (2 days)
1. Create StateGraph instance:
   ```python
   graph = StateGraph(PlanningState)
   graph.add_node("load_cv", load_cv_node)
   graph.add_node("calculate_count", calculate_count_node)
   # ... add all nodes
   graph.add_edge("load_cv", "calculate_count")
   graph.add_conditional_edges("generate_batch", route_on_error, {...})
   graph.set_entry_point("load_cv")
   graph.set_finish_point("update_interview")
   app = graph.compile(checkpointer=checkpointer)
   ```
2. Add conditional edges for error handling
3. Test graph compilation

### Step 5: Implement Parallel Generation (2 days)
1. Use `RunnableParallel` in `generate_batch_node`:
   ```python
   from langchain_core.runnables import RunnableParallel

   batch_chain = RunnableParallel(
       questions=llm.generate_questions_batch,
       answers=llm.generate_ideal_answers_batch,
       rationales=llm.generate_rationales_batch
   )
   results = await batch_chain.ainvoke({"specs": state["question_specs"]})
   ```
2. Handle partial failures (some questions succeed, some fail)
3. Test with 5 questions (verify parallel execution)

### Step 6: Refactor Use Case (1 day)
1. Update `PlanInterviewUseCase.execute()`:
   ```python
   if self.settings.use_langgraph_planning:
       return await self.workflow.execute(cv_analysis_id, candidate_id)
   else:
       # Original implementation (fallback)
   ```
2. Inject workflow via DI container
3. Add feature flag to settings

### Step 7: WebSocket Progress Streaming (2 days)
1. Use `astream_events()` in API endpoint:
   ```python
   async for event in workflow.app.astream_events(initial_state, thread_id=thread_id):
       if event["event"] == "on_chain_end":
           await websocket.send_json({"progress": event["metadata"]["progress"]})
   ```
2. Emit progress: 0% (load), 20% (calculate), 40% (prepare), 60% (generate), 80% (store), 100% (update)
3. Test real-time updates on frontend

### Step 8: Testing (3 days)
1. Unit tests: Mock all repos, test each node
2. Integration tests: Real DB, test checkpoint/resume
3. Crash simulation: Kill process mid-generation, verify resume
4. A/B test: Compare outputs (LangGraph vs manual)

---

## Todo List

- [ ] Install `langgraph-checkpoint-postgres` dependency
- [ ] Create `langgraph_checkpointer.py` with AsyncPostgresSaver setup
- [ ] Update DI container with checkpointer injection
- [ ] Test checkpoints table creation in dev DB
- [ ] Define `PlanningState` TypedDict
- [ ] Implement `load_cv_node` with error handling
- [ ] Implement `calculate_count_node` (skill diversity logic)
- [ ] Implement `prepare_specs_node` (exemplar search)
- [ ] Implement `generate_batch_node` (RunnableParallel)
- [ ] Implement `store_questions_node` (DB + embeddings)
- [ ] Implement `update_interview_node` (state transition)
- [ ] Create StateGraph with all nodes and edges
- [ ] Add conditional edges for error paths
- [ ] Refactor `PlanInterviewUseCase` with feature flag
- [ ] Add WebSocket progress streaming
- [ ] Write unit tests for each node
- [ ] Write integration test for full workflow
- [ ] Test checkpoint/resume on crash
- [ ] A/B test outputs (LangGraph vs manual)
- [ ] Document LangGraph setup in CLAUDE.md

---

## Success Criteria

**Performance**:
- ✅ Generate 5 questions in <5s (vs 40s sequential)
- ✅ 3-5x speedup verified in benchmarks

**Reliability**:
- ✅ Resume on crash from last checkpoint (integration test)
- ✅ Retry logic handles rate limits (3 attempts)
- ✅ Fallback to cached questions on total failure

**Compatibility**:
- ✅ Existing tests pass with feature flag disabled
- ✅ A/B test shows identical outputs (LangGraph vs manual)

**Observability**:
- ✅ LangSmith traces show parallel execution
- ✅ WebSocket progress updates functional

---

## Risk Assessment

### Technical Risks
1. **PostgreSQL Checkpoint Performance**:
   - Risk: High checkpoint volume slows DB
   - Mitigation: Connection pooling, test with 1000+ checkpoints, monitor query time

2. **Partial Generation Failures**:
   - Risk: Some questions fail, workflow stuck
   - Mitigation: Fallback to cached questions, retry failed only

3. **WebSocket Disconnect During Generation**:
   - Risk: Client loses progress updates
   - Mitigation: Store thread_id in Interview, resume on reconnect

4. **LangGraph Learning Curve**:
   - Risk: Team unfamiliar with StateGraph patterns
   - Mitigation: Start simple, document heavily, pair programming

### Rollback Plan
- Feature flag: `USE_LANGGRAPH_PLANNING=false` reverts to manual implementation
- Existing code remains functional
- No database schema changes (checkpoints table is additive)

---

## Security Considerations

**PII in Checkpoints**:
- Checkpoints store full state (includes CV text, candidate names)
- Mitigation: Encrypt checkpoints table at rest (PostgreSQL transparent encryption)

**Thread ID Exposure**:
- Thread IDs in URLs could allow replay attacks
- Mitigation: UUID v4 (random), scope to interview_id + candidate_id

**API Key Leakage**:
- LLM API keys in checkpointed state
- Mitigation: Never serialize API keys, pass via context only

---

## Next Steps

1. **Phase 1 Completion**: Ensure LangChain adapter tested before starting
2. **Dev Environment Setup**: Configure LangSmith for trace visualization
3. **Database Prep**: Test checkpoints table on dev DB
4. **Start Implementation**: Follow step-by-step plan (Step 1: AsyncPostgresSaver)
5. **Documentation**: Update `docs/system-architecture.md` with LangGraph workflows section

---

**Dependencies**:
- Phase 1 (LangChain adapter) MUST be complete
- AsyncPostgresSaver requires `asyncpg` driver (already installed)
- PostgreSQL 12+ for checkpoints table (Neon cloud compatible)

**Blocking**:
- Phase 3 (adaptive evaluation) waits for this phase
