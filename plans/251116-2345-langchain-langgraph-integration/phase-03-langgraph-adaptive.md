# Phase 3: LangGraph Adaptive Evaluation Workflow

**Phase ID**: 03
**Created**: 2025-11-16
**Priority**: High
**Estimated Duration**: 2 weeks
**Risk Level**: High
**Implementation Status**: Not Started
**Review Status**: Pending

---

## Context Links

- **Parent Plan**: [plan.md](plan.md)
- **Dependencies**: Phase 1 (LangChain adapter), Phase 2 (LangGraph basics)
- **Related Docs**:
  - [System Architecture - Session Orchestrator](../../docs/system-architecture.md#session-orchestrator-pattern-state-machine)
  - [Research: LangGraph WebSocket Integration](research/researcher-02-langgraph-workflows.md)

---

## Overview

Replace WebSocket-based imperative follow-up loop with LangGraph declarative state machine, enabling crash recovery and clearer logic flow.

**Current Problem**:
- `InterviewSessionOrchestrator` (584 lines) manages state imperatively
- WebSocket disconnect loses session state (no persistence)
- Break conditions (max 3, similarity ≥0.8, no gaps) buried in if-else chains
- Hard to visualize or debug follow-up logic

**Solution**:
- LangGraph StateGraph with human-in-loop interrupts
- Conditional edges for break conditions (declarative)
- AsyncPostgresSaver or MemorySaver for session persistence
- Resume on WebSocket reconnect via thread_id
- 80% reduction in orchestrator complexity

---

## Key Insights

**From Research**:
1. **Human-in-Loop**: Interrupt nodes pause before state modifications, wait for external input (WebSocket message)
2. **Thread IDs**: Store in Interview entity for session continuity across disconnects
3. **Streaming Events**: `astream_events()` emits events (evaluation, followup_question, interview_complete)
4. **Conditional Edges**: Break conditions as pure functions (no side effects)
5. **Resume Logic**: `app.ainvoke(None, config={"thread_id": thread_id})` continues from last interrupt

---

## Requirements

### Functional Requirements
**FR1**: Evaluate answer with LLM (semantic analysis + gap detection)
**FR2**: Decide follow-up based on break conditions (max 3, similarity ≥0.8, no gaps)
**FR3**: Generate targeted follow-up question if needed
**FR4**: Combine parent + child evaluations into COMBINED type
**FR5**: Resume session on WebSocket reconnect (thread_id-based)
**FR6**: Stream events to WebSocket (evaluation, followup_question, next_question, interview_complete)

### Non-Functional Requirements
**NFR1**: Crash Recovery: Resume from last checkpoint (MemorySaver or PostgreSQL)
**NFR2**: Clarity: StateGraph visual representation (easier debugging than imperative code)
**NFR3**: Testability: Mock nodes independently, test conditional logic
**NFR4**: Performance: No degradation vs current orchestrator (<100ms per step)

---

## Architecture

### Current Flow (Imperative WebSocket)
```
InterviewSessionOrchestrator.handle_text_answer():
  1. Transition QUESTIONING → EVALUATING
  2. Call ProcessAnswerAdaptiveUseCase (LLM eval + gaps)
  3. Send evaluation to WebSocket
  4. Call FollowUpDecisionUseCase (check break conditions)
  5. IF needs_followup:
       a. Generate follow-up question (LLM)
       b. Send via WebSocket
       c. BREAK (wait for next message)
  6. ELSE:
       a. Transition EVALUATING → QUESTIONING
       b. Send next question
```

### LangGraph Flow (Declarative State Machine)
```
StateGraph with interrupts:
┌─────────────────────────────────────────────────┐
│ START (answer received via WebSocket)          │
└────────────┬────────────────────────────────────┘
             ↓
    ┌─────────────────────┐
    │ evaluate_answer     │ ← LLM evaluation + gaps
    └────────┬────────────┘
             ↓ [checkpoint 1]
    ┌─────────────────────┐
    │ detect_gaps         │ ← Semantic gap analysis
    └────────┬────────────┘
             ↓ [checkpoint 2]
    ┌─────────────────────┐
    │ decide_followup     │ ← Check break conditions
    └────────┬────────────┘
             ↓
      CONDITIONAL EDGE:
      ┌──────────┬──────────┐
      │          │          │
  needs_followup=True    False
      ↓          │          ↓
┌───────────┐   │   ┌──────────────┐
│ generate_ │   │   │ combine_     │
│ followup  │   │   │ evaluations  │
└─────┬─────┘   │   └──────┬───────┘
      ↓         │          ↓
┌───────────┐   │   ┌──────────────┐
│ [INTERRUPT]   │   │ next_question│
│ send_ws   │   │   │              │
└─────┬─────┘   │   └──────┬───────┘
      │         │          │
      ↓         │          ↓
   WAIT FOR     │         END
   NEXT ANSWER  │         (or repeat)
```

### State Definition
```python
# src/application/workflows/adaptive_eval_workflow.py
class AdaptiveEvalState(TypedDict):
    interview_id: UUID
    interview: Interview | None
    current_question_id: UUID
    parent_question_id: UUID | None  # For follow-ups
    answer_text: str
    answer_id: UUID | None
    evaluation: Evaluation | None
    followup_count: int  # 0, 1, 2, 3
    cumulative_gaps: list[str]
    needs_followup: bool
    followup_question: Question | None
    combined_evaluation: Evaluation | None
    has_more_questions: bool
    thread_id: str
    errors: list[str]
```

### Break Conditions (Conditional Edge)
```python
def should_generate_followup(state: AdaptiveEvalState) -> str:
    """Decide next node based on break conditions."""
    # Condition 1: Max attempts reached
    if state["followup_count"] >= 3:
        return "combine_evaluations"

    # Condition 2: High quality answer
    if state["evaluation"].similarity_score >= 0.8:
        return "combine_evaluations"

    # Condition 3: No gaps detected
    if not state["evaluation"].gaps or not state["evaluation"].gaps.confirmed:
        return "combine_evaluations"

    # All conditions failed → need follow-up
    return "generate_followup"
```

### Component Responsibilities
**AdaptiveEvalWorkflow** (`src/application/workflows/adaptive_eval_workflow.py`):
- Build StateGraph with 6 nodes + interrupt
- Configure checkpointer (MemorySaver or AsyncPostgresSaver)
- Expose `execute()` and `resume()` methods

**InterviewSessionOrchestrator** (refactored):
- Simplify to WebSocket I/O handler only (no state logic)
- Delegate to `workflow.astream_events()`
- Store thread_id in Interview entity
- On reconnect: resume via `workflow.resume(thread_id)`

**ProcessAnswerAdaptiveUseCase** (unchanged):
- Keep existing logic (called by `evaluate_answer_node`)
- Returns Answer + Evaluation entities

---

## Related Code Files

### Existing Files to Modify
1. **`src/adapters/api/websocket/interview_handler.py`**:
   - Simplify to ~150 lines (vs 131 current)
   - Remove state management logic
   - Delegate to AdaptiveEvalWorkflow
   - Handle `astream_events()` output

2. **`src/adapters/api/websocket/session_orchestrator.py`**:
   - OPTION A: Deprecate entirely (logic moved to LangGraph)
   - OPTION B: Keep as thin wrapper around workflow

3. **`src/domain/models/interview.py`**:
   - Add field: `thread_id: str | None = None` (for session resumption)
   - Migration: `alembic revision --autogenerate -m "add thread_id to interviews"`

4. **`src/infrastructure/dependency_injection/container.py`**:
   - Add `adaptive_eval_workflow()` method
   - Inject use cases, checkpointer

### New Files to Create
1. **`src/application/workflows/adaptive_eval_workflow.py`** (350 lines):
   - `AdaptiveEvalState` TypedDict
   - `AdaptiveEvalWorkflow` class
   - 6 nodes: evaluate, detect_gaps, decide_followup, generate_followup, combine, next_question
   - Conditional edge function: `should_generate_followup()`
   - Interrupt node: `send_ws_node`

2. **`src/adapters/api/websocket/workflow_streamer.py`** (100 lines):
   - Stream LangGraph events to WebSocket
   - Filter events by type (on_chat_model_end, on_tool_end)
   - Format events for frontend JSON protocol

3. **`tests/unit/application/workflows/test_adaptive_eval_workflow.py`** (400 lines):
   - Test each node independently
   - Test conditional edge logic (all 3 break conditions)
   - Test interrupt/resume flow

4. **`tests/integration/workflows/test_adaptive_websocket.py`** (200 lines):
   - End-to-end WebSocket test with workflow
   - Disconnect/reconnect simulation

---

## Implementation Steps

### Step 1: Database Migration (1 day)
1. Add `thread_id` to Interview entity:
   ```python
   # src/domain/models/interview.py
   thread_id: str | None = None  # LangGraph session ID
   ```
2. Create migration: `alembic revision --autogenerate -m "add thread_id"`
3. Run migration: `alembic upgrade head`
4. Update InterviewMapper to handle thread_id

### Step 2: Define AdaptiveEvalState (1 day)
1. Create TypedDict with all required fields
2. Add reducer functions for list fields (cumulative_gaps)
3. Document state transitions

### Step 3: Implement Core Nodes (3 days)
1. **evaluate_answer_node**:
   - Call `ProcessAnswerAdaptiveUseCase.execute()`
   - Store evaluation in state
2. **detect_gaps_node**:
   - Extract gaps from evaluation
   - Accumulate with previous gaps
3. **decide_followup_node**:
   - Implement break condition checks
   - Set `needs_followup` flag
4. **generate_followup_node**:
   - Call `LLMPort.generate_followup_question()`
   - Create FollowUpQuestion entity
5. **combine_evaluations_node**:
   - Call `CombineEvaluationUseCase`
   - Aggregate parent + children
6. **next_question_node**:
   - Call `GetNextQuestionUseCase`
   - Check if interview complete

### Step 4: Implement Conditional Edge (1 day)
1. Create `should_generate_followup()` function
2. Test all 3 break conditions:
   - followup_count >= 3
   - similarity_score >= 0.8
   - gaps.confirmed == False
3. Unit tests for edge function

### Step 5: Add Interrupt Node (2 days)
1. Create `send_ws_node` with `interrupt()` call:
   ```python
   from langgraph.graph import interrupt

   def send_ws_node(state: AdaptiveEvalState):
       # Pause workflow here
       user_input = interrupt(state["followup_question"].text)
       return {"answer_text": user_input}
   ```
2. Configure interrupt in graph compilation
3. Test interrupt/resume flow

### Step 6: Build StateGraph (2 days)
1. Create graph with all nodes:
   ```python
   graph = StateGraph(AdaptiveEvalState)
   graph.add_node("evaluate", evaluate_answer_node)
   graph.add_node("detect_gaps", detect_gaps_node)
   graph.add_node("decide_followup", decide_followup_node)
   graph.add_node("generate_followup", generate_followup_node)
   graph.add_node("send_ws", send_ws_node)  # INTERRUPT
   graph.add_node("combine", combine_evaluations_node)
   graph.add_node("next_question", next_question_node)

   graph.add_conditional_edges("decide_followup", should_generate_followup, {
       "generate_followup": "generate_followup",
       "combine_evaluations": "combine"
   })

   app = graph.compile(checkpointer=checkpointer, interrupt_before=["send_ws"])
   ```
2. Test graph compilation and visualization

### Step 7: Refactor WebSocket Handler (2 days)
1. Update `interview_handler.py`:
   ```python
   async def handle_text_answer(self, message: dict):
       # Get or create thread_id
       thread_id = interview.thread_id or str(uuid4())

       # Stream workflow events
       async for event in workflow.astream_events(
           {"answer_text": message["answer_text"]},
           config={"thread_id": thread_id}
       ):
           if event["event"] == "on_chat_model_stream":
               await websocket.send_json({"type": "evaluation", ...})
           elif event["event"] == "on_tool_end":
               await websocket.send_json({"type": "followup_question", ...})
   ```
2. Handle reconnection: `workflow.resume(thread_id)`
3. Update Interview entity with thread_id after first run

### Step 8: Implement Workflow Streamer (1 day)
1. Create `workflow_streamer.py`:
   - Filter events by type
   - Convert to WebSocket JSON protocol
   - Handle errors gracefully
2. Unit tests for event filtering

### Step 9: Testing (3 days)
1. Unit tests: Test each node with mocks
2. Integration tests: Full workflow with real DB
3. WebSocket tests: Disconnect/reconnect scenarios
4. Stress test: 100 concurrent workflows

---

## Todo List

- [ ] Add `thread_id` field to Interview entity
- [ ] Create Alembic migration for thread_id
- [ ] Update InterviewMapper to serialize thread_id
- [ ] Define `AdaptiveEvalState` TypedDict
- [ ] Implement `evaluate_answer_node`
- [ ] Implement `detect_gaps_node`
- [ ] Implement `decide_followup_node` with break conditions
- [ ] Implement `generate_followup_node`
- [ ] Implement `combine_evaluations_node`
- [ ] Implement `next_question_node`
- [ ] Create `should_generate_followup()` conditional edge
- [ ] Add interrupt node (`send_ws_node`)
- [ ] Build StateGraph with all nodes and edges
- [ ] Configure checkpointer (MemorySaver or PostgreSQL)
- [ ] Refactor WebSocket handler to use `astream_events()`
- [ ] Implement workflow streamer (event filtering)
- [ ] Add thread_id storage logic in handler
- [ ] Add resume logic for reconnections
- [ ] Write unit tests for each node
- [ ] Write integration test for full workflow
- [ ] Test interrupt/resume flow
- [ ] Test WebSocket disconnect/reconnect
- [ ] Stress test with 100 concurrent sessions
- [ ] Document LangGraph adaptive workflow in architecture docs

---

## Success Criteria

**Crash Recovery**:
- ✅ Resume session after WebSocket disconnect (thread_id lookup)
- ✅ No loss of evaluation history or follow-up count

**Code Clarity**:
- ✅ 80% reduction in orchestrator complexity (584 → ~150 lines)
- ✅ Visual StateGraph diagram in LangSmith

**Functionality**:
- ✅ All 3 break conditions work correctly
- ✅ Follow-up loop max 3 iterations
- ✅ Combined evaluation generated correctly

**Performance**:
- ✅ No degradation vs current implementation (<100ms per node)

---

## Risk Assessment

### Technical Risks
1. **Human-in-Loop Complexity**:
   - Risk: Interrupt nodes not well-documented, tricky to debug
   - Mitigation: Follow LangGraph examples closely, extensive unit tests

2. **WebSocket Event Streaming**:
   - Risk: `astream_events()` emits too many events, overwhelms client
   - Mitigation: Filter events aggressively, test with slow connections

3. **Thread ID Management**:
   - Risk: Thread ID collisions or orphaned checkpoints
   - Mitigation: UUID v4 (random), cleanup job for old checkpoints

4. **State Serialization**:
   - Risk: Complex objects (Evaluation, Question) fail to serialize
   - Mitigation: Use Pydantic models, test checkpoint save/load

### Rollback Plan
- Feature flag: `USE_LANGGRAPH_ADAPTIVE=false` keeps current orchestrator
- Thread ID field nullable (backward compatible)
- No breaking changes to WebSocket protocol

---

## Security Considerations

**Thread ID Exposure**:
- Thread IDs in Interview records could enable session hijacking
- Mitigation: Validate thread_id belongs to interview_id + candidate_id before resume

**Checkpoint PII**:
- Checkpoints contain answer text, evaluation feedback (sensitive)
- Mitigation: Encrypt checkpoints table, purge after interview completion

**Interrupt Attack**:
- Malicious client could spam interrupts, DoS workflow
- Mitigation: Rate limit interrupt nodes, timeout after 5 minutes idle

---

## Next Steps

1. **Phase 2 Completion**: Ensure planning workflow tested before starting
2. **Database Migration**: Run thread_id migration on dev DB
3. **Prototype**: Build minimal StateGraph with 2 nodes, test interrupt
4. **Start Implementation**: Follow step-by-step (Step 1: Migration)
5. **Documentation**: Update architecture docs with adaptive workflow diagram

---

**Dependencies**:
- Phase 1 (LangChain adapter)
- Phase 2 (LangGraph basics, checkpointer setup)
- Alembic migration system

**Blocking**:
- Phase 4 (observability) benefits from this phase completion
