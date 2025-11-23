# LangGraph Interview Conversation Migration Plan

**Created**: 2025-11-23
**Status**: In Development
**Complexity**: High (5 use cases → unified workflow, atomic migration required)
**Estimated Duration**: 1-2 weeks (development phases only)
**Mode**: Development (skipping analysis, canary, rollout phases)

## Executive Summary

Replace `session_orchestrator.py` (326 LOC) with LangGraph workflow for WebSocket interview QA phase. Consolidate 5 use cases into single stateful workflow with checkpointing, conversation memory, interrupt patterns.

**Key Goals**:
- Eliminate manual state tracking (orchestrator → domain workflow)
- Persistent conversation memory across reconnects
- Testable workflow nodes (vs. 326 LOC orchestrator)
- Foundation for human-in-loop interrupts (Phase 3B pattern)

**Scope**: WebSocket QA phase ONLY. Excludes planning phase (keep `PlanInterviewUseCase`).

---

## Architecture Analysis

### Current Architecture (v0.4.0)

**Stack**:
- `interview_handler.py` (342 LOC) - WebSocket I/O, audio streaming
- `session_orchestrator.py` (326 LOC) - **TARGET FOR REPLACEMENT**
- 5 use cases (700 LOC total):
  - `ProcessAnswerAdaptiveUseCase` (evaluation + gap detection)
  - `FollowUpDecisionUseCase` (break conditions)
  - `GetNextQuestionUseCase` (question retrieval)
  - `CompleteInterviewUseCase` (summary generation)
  - Follow-up generation (inline in orchestrator)
- `langchain_adapter.py` (1400 LOC) - LLM adapter (KEEP)

**State Management**:
```python
# Current: Manual state tracking in orchestrator
interview = await interview_repo.get_by_id(interview_id)  # DB roundtrip every operation
interview.mark_evaluating()  # Domain state transition
await interview_repo.update(interview)  # Persist

# Problem:
# - No conversation memory (loses context on reconnect)
# - State scattered across DB + orchestrator logic
# - Difficult to test (tightly coupled to WebSocket)
```

**Message Flow** (Current):
```
Client → WebSocket → Orchestrator → Use Case → Domain → Adapter → LLM
         ↓                                                         ↓
      DB State                                             Prompt Context
```

### Target Architecture (Post-Migration)

**Stack**:
- `interview_handler.py` (SIMPLIFIED to ~200 LOC)
- `InterviewConversationWorkflow` (NEW ~500 LOC)
- `langchain_adapter.py` (UNCHANGED)

**State Management**:
```python
# Target: LangGraph StateGraph with checkpointing
class ConversationState(TypedDict):
    interview_id: UUID
    messages: list[BaseMessage]  # LangChain conversation memory
    current_question_id: UUID | None
    answers: list[Answer]
    evaluations: list[Evaluation]
    followup_count: int
    cumulative_gaps: list[str]
    has_more_questions: bool

# Benefits:
# - Conversation memory persisted to PostgreSQL
# - State checkpointed after each node
# - Resume from last checkpoint on reconnect
# - Testable nodes in isolation
```

**Message Flow** (Target):
```
Client → WebSocket → Workflow Node → Adapter → LLM
         ↓              ↓                      ↓
    Checkpoint    State Update         Prompt (w/ memory)
```

**Workflow Graph**:
```
START
  ↓
load_question_node
  ↓
evaluate_answer_node  ←─────────┐
  ↓                             │
decide_followup_node            │
  ↓                             │
[conditional edge]              │
  ├─ needs_followup=True  →  generate_followup_node ──┘
  └─ needs_followup=False →  next_question_or_complete_node
                              ↓
                            END
```

---

## Migration Strategy

### Phase Breakdown

**Phase 1**: Core Workflow Implementation (1 week) ✅ ACTIVE
**Phase 2**: Integration & Testing (3-4 days)

### Feature Flag Strategy

```python
# settings.py
use_langgraph_conversation: bool = Field(
    default=True,  # Enabled for development
    description="Enable LangGraph conversation workflow (replaces session_orchestrator)"
)
```

**Development Mode**:
- Phase 1-2: `True` (local dev only)
- Production rollout: Handled separately (not in this plan)

### Architecture Decisions (RESOLVED)

**1. Thread Strategy**: Single thread per interview
   - All Q&A (main + follow-ups) in ONE thread
   - Full conversation context for LLM
   - Simpler state management

**2. Checkpoint Retention**: Delete after completion
   - No retention for debugging (development mode)
   - Cleanup after interview complete
   - Reduce storage overhead

**3. Message Truncation**: 10 messages (5 Q&A pairs)
   - Balance cost vs. context
   - Covers typical follow-up chains (1 main + 2-3 follow-ups)
   - Applied before LLM evaluation

**4. Checkpoint Compression**: No compression
   - Typical state <15KB (compression overhead > savings)
   - Keep implementation simple
   - Monitor size in Phase 2

### Risk Mitigation

**High-Risk Areas** (Development Focus):
1. **State Schema Design** - Must support all current features
   - Mitigation: Map existing use case logic to nodes carefully
2. **Conversation Memory Integration** - LangChain BaseMessage serialization
   - Mitigation: Test serialization in Phase 1 unit tests
3. **Testing Coverage** - Complex state transitions
   - Mitigation: >85% test coverage target

---

## Success Criteria

**Functional**:
- [ ] All 13 test scenarios pass (8 mock + 5 real from test bot)
- [ ] Conversation memory persists across WebSocket reconnects
- [ ] Follow-up logic identical to current (3 attempts max, same break conditions)
- [ ] Summary generation unchanged (same API response)

**Performance** (Development baseline):
- [ ] Workflow executes without errors
- [ ] Memory cleanup after completion (no leaks)
- [ ] Latency measured (no target for dev mode)

**Code Quality**:
- [ ] LOC reduction: 1026 LOC → ~700 LOC (30% reduction)
- [ ] Test coverage: >85% for workflow nodes
- [ ] No circular dependencies
- [ ] Mypy type checking passes

---

## Implementation Phases


### Phase 1: Core Workflow Implementation (1 week)

**Goals**: Build `InterviewConversationWorkflow` with 7 nodes, state management, checkpointing.

**Workflow Nodes** (7 total):

1. **start_session_node** - Initialize conversation, send first question
2. **evaluate_answer_node** - LLM evaluation + gap detection
3. **update_memory_node** - Append Q&A to conversation memory
4. **decide_followup_node** - Break condition logic
5. **generate_followup_node** - Generate follow-up question
6. **next_question_node** - Load next main question
7. **complete_interview_node** - Generate summary, finalize

**State Schema**:
```python
class ConversationState(TypedDict):
    # Input
    interview_id: UUID
    candidate_id: UUID

    # Conversation memory (LangChain)
    messages: list[BaseMessage]  # HumanMessage, AIMessage

    # Current context
    current_question_id: UUID | None
    current_question: Question | None
    parent_question_id: UUID | None  # For follow-ups

    # Accumulated results
    answers: list[Answer]
    evaluations: list[Evaluation]
    followup_count: int
    cumulative_gaps: list[str]

    # Control flow
    has_more_questions: bool
    needs_followup: bool
    complete: bool

    # Error handling
    errors: list[str]
    retry_count: int

    # Checkpointing
    checkpoint_thread_id: str
```

**Conditional Edges**:
```python
def _should_generate_followup(state: ConversationState) -> str:
    """Route after decide_followup_node."""
    if state["needs_followup"]:
        return "generate_followup"
    return "next_question_or_complete"

def _should_complete(state: ConversationState) -> str:
    """Route after next_question_node."""
    if state["has_more_questions"]:
        return "evaluate_answer"  # Wait for next answer
    return "complete_interview"
```

**Code Structure**:
```
src/application/workflows/
├── interview_conversation_workflow.py  (NEW ~500 LOC)
└── base_workflow.py  (EXISTING)
```

**Tasks**:
1. Create `ConversationState` TypedDict with full schema
2. Implement 7 workflow nodes (async functions)
3. Build StateGraph with conditional edges
4. Add conversation memory management (truncation)
5. Integrate checkpointing (AsyncPostgresSaver)
6. Add error handling to all nodes
7. Write unit tests for nodes (7 test files)

**Deliverables**:
- `src/application/workflows/interview_conversation_workflow.py`
- Unit tests: `tests/unit/application/workflows/test_conversation_workflow_nodes.py`
- Workflow diagram (Mermaid graph in docs)

**Implementation Details**:
- Memory truncation: BEFORE evaluation node (reduce LLM context)
- Error recovery: Log errors, fail workflow (no retry for dev)

See: [phase1-implementation.md](./phase1-implementation.md)

---

### Phase 2: Integration & Testing (3-4 days)

**Goals**: Wire workflow to WebSocket handler, integration tests, test bot validation.

**Integration Points**:

1. **DI Container** (`container.py`):
```python
async def create_interview_conversation_workflow(
    self, session: AsyncSession
) -> InterviewConversationWorkflow:
    return InterviewConversationWorkflow(
        checkpointer=await self.get_checkpointer(),
        interview_repo=self.interview_repository_port(session),
        question_repo=self.question_repository_port(session),
        answer_repo=self.answer_repository_port(session),
        evaluation_repo=self.evaluation_repository_port(session),
        followup_repo=self.follow_up_question_repository(session),
        llm=self.llm_port(),
    )
```

2. **WebSocket Handler** (`interview_handler.py`):
```python
# Simplified handler (reduced from 342 LOC → ~200 LOC)
async def handle_interview_websocket(websocket, interview_id):
    await manager.connect(interview_id, websocket)

    # Check feature flag
    if settings.use_langgraph_conversation:
        await _handle_with_workflow(websocket, interview_id)
    else:
        await _handle_with_orchestrator(websocket, interview_id)  # Legacy

async def _handle_with_workflow(websocket, interview_id):
    """New workflow-based handler."""
    workflow = await container.create_interview_conversation_workflow(session)

    # Start session
    result = await workflow.start_session(interview_id)

    # Listen for answers
    while True:
        data = await websocket.receive_json()

        if data["type"] == "text_answer":
            result = await workflow.process_answer(
                answer_text=data["answer_text"],
                thread_id=result.get("thread_id")  # Resume from checkpoint
            )

            if result["complete"]:
                break
```

**Tasks**:
1. Add workflow factory method to DI container
2. Simplify `interview_handler.py` (remove orchestrator logic)
3. Add feature flag check in handler
4. Write integration tests (workflow + DB)
5. Run test bot against workflow (13 scenarios)
6. Compare outputs: workflow vs. orchestrator (exact match required)

**Test Coverage**:
- Integration tests: 5 scenarios (main Q&A, follow-up, completion, edge cases)
- Test bot validation: 13 scenarios (8 mock + 5 real)
- Performance baseline: avg latency per operation

**Deliverables**:
- Updated `interview_handler.py` with feature flag
- Integration tests: `tests/integration/workflows/test_conversation_workflow_integration.py`
- Test bot report (workflow vs. orchestrator comparison)

**Implementation Details**:
- WebSocket reconnect: Restart workflow (dev mode, no resume needed)
- Test validation: Manual testing (no automated test bot for dev)

See: [phase2-integration.md](./phase2-integration.md)

---


## Technical Details

### Conversation Memory Implementation

**LangChain BaseMessage**:
```python
from langchain_core.messages import HumanMessage, AIMessage

# Node: update_memory_node
async def _update_memory_node(state: ConversationState) -> dict:
    """Append Q&A to conversation memory."""
    messages = state.get("messages", [])

    # Add question
    messages.append(AIMessage(
        content=state["current_question"].text,
        additional_kwargs={"question_id": str(state["current_question_id"])}
    ))

    # Add answer
    messages.append(HumanMessage(
        content=state["answers"][-1].text,
        additional_kwargs={"answer_id": str(state["answers"][-1].id)}
    ))

    # Truncate to last 10 messages (5 Q&A pairs)
    if len(messages) > 10:
        messages = messages[-10:]

    return {"messages": messages}
```

**Memory Injection to LLM**:
```python
# In evaluate_answer_node
async def _evaluate_answer_node(state: ConversationState) -> dict:
    """Evaluate answer with conversation context."""

    # Build context dict with conversation memory
    context = {
        "interview_id": state["interview_id"],
        "conversation_history": [
            {"role": "ai" if isinstance(m, AIMessage) else "human", "content": m.content}
            for m in state["messages"]
        ]
    }

    # LLM adapter receives context (UNCHANGED API)
    evaluation = await llm.evaluate_answer(
        question=state["current_question"],
        answer_text=state["answers"][-1].text,
        context=context  # Now includes conversation_history
    )

    return {"evaluations": state["evaluations"] + [evaluation]}
```

### Checkpointing Strategy

**Checkpoint Triggers**:
- After each node execution (automatic by LangGraph)
- Cleanup after `complete_interview_node` (delete all checkpoints)

**Thread ID Format**:
```python
thread_id = f"interview_{interview_id}"
# Example: "interview_abc123-def456-..."
# One thread per interview (includes main + follow-ups)
```

**Cleanup After Completion**:
```python
async def _complete_interview_node(state: ConversationState) -> dict:
    """Complete interview and cleanup checkpoints."""
    # Generate summary
    summary = await generate_summary(state)

    # Delete checkpoints (no retention in dev mode)
    thread_id = state["checkpoint_thread_id"]
    await checkpointer.delete_thread(thread_id)

    return {"complete": True, "summary": summary}
```

### Error Handling Pattern

**Node Error Wrapper**:
```python
async def _safe_node_execution(
    node_func: Callable,
    state: ConversationState,
    node_name: str
) -> dict:
    """Wrap node execution with error handling."""
    try:
        return await node_func(state)
    except Exception as exc:
        logger.error(f"Node {node_name} failed: {exc}", exc_info=True)

        # Increment retry count
        retry_count = state.get("retry_count", 0) + 1

        if retry_count >= 3:
            # Max retries - fail workflow
            return {
                "errors": state.get("errors", []) + [f"{node_name}: {str(exc)}"],
                "complete": True  # Force end
            }

        # Retry node
        return {
            "retry_count": retry_count,
            "errors": state.get("errors", []) + [f"{node_name} retry {retry_count}"]
        }
```

---

## Dependencies

**New Dependencies**: None (all dependencies exist in v0.4.0)

**Existing Dependencies**:
- `langgraph>=0.2.0` (StateGraph, checkpointing)
- `langgraph-checkpoint-postgres>=0.2.0` (AsyncPostgresSaver)
- `langchain-core>=0.2.0` (BaseMessage, Runnable)
- PostgreSQL 14+ (checkpoint storage)

**DB Schema**: No changes required (reuses existing `langgraph_checkpoints` table from v0.3.0)

---

## Testing Strategy

### Test Pyramid

**Unit Tests** (50 tests):
- 7 workflow nodes (isolation testing)
- State schema validation
- Conditional edge logic
- Memory truncation

**Integration Tests** (10 tests):
- Full workflow execution (DB + LLM)
- Checkpoint persistence
- Resume from checkpoint
- Error recovery

**Test Bot** (13 scenarios):
- 8 mock scenarios (no LLM cost)
- 5 real scenarios (OpenAI GPT-4)
- Workflow vs. orchestrator comparison

**Performance Tests** (5 benchmarks):
- Checkpoint latency
- Memory growth
- State serialization overhead
- LLM token usage (parity check)

### Test Coverage Targets

- Workflow nodes: >90%
- State management: >85%
- Error handling: >80%
- Overall: >85%

---

## Architecture Decisions (RESOLVED)

All key decisions finalized for development:

**1. Thread Strategy** ✅ RESOLVED
- Single thread per interview (main + follow-ups)
- Simpler state, full conversation context

**2. Checkpoint Retention** ✅ RESOLVED
- Delete after interview completion
- No debugging retention needed (dev mode)

**3. Message Truncation** ✅ RESOLVED
- 10 messages (last 5 Q&A pairs)
- Applied before LLM evaluation
- Balance cost vs. context

**4. Checkpoint Compression** ✅ RESOLVED
- No compression (typical state <15KB)
- Keep implementation simple

**5. Error Recovery** ✅ RESOLVED
- Log errors, fail workflow
- No retry logic (dev mode)

**6. WebSocket Reconnect** ✅ RESOLVED
- Restart workflow (no resume)
- Simplify dev testing

---

## Appendices

### A. File Structure

```
plans/251123-1252-langgraph-interview-conversation-migration/
├── plan.md                     # This file (overview + phases)
├── phase1-implementation.md    # Phase 1 detailed tasks
└── phase2-integration.md       # Phase 2 detailed tasks
```

### B. Code LOC Summary

**Before Migration**:
- `session_orchestrator.py`: 326 LOC
- 4 use cases: 550 LOC
- `interview_handler.py`: 342 LOC
- **Total**: 1218 LOC

**After Migration**:
- `interview_conversation_workflow.py`: 500 LOC (NEW)
- `interview_handler.py`: 200 LOC (SIMPLIFIED)
- `complete_interview.py`: 150 LOC (REUSED)
- **Total**: 850 LOC

**Reduction**: 368 LOC (30%)

### C. Timeline

```
Week 1: Phase 1 (Core Workflow Implementation)
Week 2: Phase 2 (Integration + Testing)
```

**Total Duration**: 1-2 weeks

### D. Stakeholders

- **Engineering**: Backend team (implementation)
- **QA**: Test bot validation, integration testing
- **DevOps**: Deployment, monitoring setup
- **Product**: Acceptance criteria, success metrics

---

## Next Steps

1. ✅ Architecture decisions finalized
2. Start Phase 1: Core workflow implementation
3. Focus areas:
   - Create `ConversationState` schema
   - Implement 7 workflow nodes
   - Add conversation memory (10 message truncation)
   - Checkpoint cleanup after completion
4. Target: Phase 1 complete in 1 week

---

**Plan Status**: Ready for review
**Author**: Claude Code (Sonnet 4.5)
**Reviewers**: [TBD]
**Approval Date**: [TBD]
