# LangGraph State Machine Patterns for Production Interview Workflows

**Research Date**: 2025-11-16
**Context**: Elios AI Interview Service - Multi-step LLM orchestration
**Max Depth**: 150 lines

---

## 1. StateGraph Core Concepts

### 1.1 State Definition with TypedDict

LangGraph states use `TypedDict` for type-safe workflow data:

```python
from typing import TypedDict, Annotated
from langgraph.graph.message import add_messages

class InterviewState(TypedDict):
    candidate_id: str
    cv_skills: list[str]
    question_queue: list[dict]
    current_question: dict
    candidate_answer: str
    evaluation_score: float
    attempt_count: int
    should_continue: bool
```

- **Reducer pattern** (e.g., `add_messages`) automatically manages list concatenation
- **Annotated types** enable custom merge strategies per field
- States persist at every node completion (checkpoint-friendly)

### 1.2 Node Functions & Edges

Nodes are async callables that receive state, return updates:

```python
async def generate_question_node(state: InterviewState) -> dict:
    # Vector search for semantic similarity
    question = await llm_port.generate_question(state["cv_skills"])
    return {"current_question": question, "attempt_count": 0}

async def evaluate_answer_node(state: InterviewState) -> dict:
    score = await evaluation_port.score_answer(
        state["current_question"],
        state["candidate_answer"]
    )
    return {"evaluation_score": score}
```

**Conditional edges** branch based on state:

```python
def should_ask_followup(state: InterviewState) -> str:
    if state["evaluation_score"] < 0.6 and state["attempt_count"] < 2:
        return "followup"  # Ask clarification
    return "next_question"
```

### 1.3 Parallel Execution & Interrupts

LangGraph handles concurrent nodes via dependency graph analysis:

```python
# Two independent nodes run in parallel
graph.add_edge("generate", "evaluate")  # Sequential
graph.add_edge("store_feedback", "generate")  # Parallel with evaluate
```

**Human-in-the-loop interrupts**:

```python
# Break execution before node, allow state modification
graph.add_node("review_step", node=review_node, interrupt_before=True)
```

---

## 2. Checkpointing & Persistence (PostgreSQL Focus)

### 2.1 AsyncPostgresSaver Setup

```python
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

# Initialize checkpointer (auto-creates tables)
checkpointer = AsyncPostgresSaver.from_conn_string(
    "postgresql+asyncpg://user:pass@host/db"
)
await checkpointer.setup()

# Compile graph with checkpointer
app = graph.compile(checkpointer=checkpointer)
```

**Critical async config**:
- Use `asyncpg` driver (supports async/await)
- SQLAlchemy 2.0 with `create_async_engine()`
- Connection pooling: `pool_size=20, max_overflow=10`
- Thread pool: `await asyncio.to_thread()` for blocking ops

### 2.2 Resume/Replay Capabilities

```python
# Save thread config after first run
config = {"configurable": {"thread_id": "interview_001"}}

# Resume from last checkpoint
async with AsyncPostgresSaver.from_conn_string(DB_URI) as checkpointer:
    state = await app.aget_state(config)  # Fetch current state
    updates = {"candidate_answer": "new answer"}
    await app.aupdate_state(config, updates)  # Modify before resume
    result = await app.ainvoke({"resume": True}, config)
```

**State versioning**: Checkpointer auto-versions on each node completion. Query history with `aget_state_history()`.

---

## 3. WebSocket Real-Time Streaming Integration

### 3.1 astream_events() Pattern

```python
async def websocket_handler(websocket: WebSocket, config: dict):
    async for event in app.astream_events(
        {"input": "start_interview"},
        config,
        version="v2"
    ):
        if event["event"] == "on_chat_model_stream":
            token = event["data"]["chunk"].content
            await websocket.send_json({"type": "token", "data": token})

        elif event["event"] == "on_tool_end":
            result = event["data"]["output"]
            await websocket.send_json({"type": "evaluation", "data": result})
```

**Event filtering**: Only listen to relevant events (`llm_stream`, `tool_end`, `node_finish`).

### 3.2 Interrupt Nodes for User Input

```python
# Break before accept_answer node
graph.add_node("accept_answer", accept_answer_node, interrupt_before=True)

# Frontend sends corrected answer
await app.aupdate_state(config, {"candidate_answer": corrected_text})
result = await app.ainvoke(None, config)  # Resume
```

---

## 4. Production Error Recovery & Break Conditions

### 4.1 Node-Level Error Handling

```python
async def generate_with_retry(state: InterviewState) -> dict:
    max_retries, attempts = 3, 0

    while attempts < max_retries:
        try:
            return {"current_question": await llm_port.generate()}
        except RateLimitError:
            attempts += 1
            await asyncio.sleep(2 ** attempts)  # Exponential backoff

    # Fallback to cached question
    return {"current_question": get_fallback_question()}
```

### 4.2 Break Conditions (Quality Thresholds)

```python
def should_continue(state: InterviewState) -> str:
    # Exit conditions
    if state["evaluation_score"] > 0.95:  # Excellent response
        return "skip_followup"

    if state["attempt_count"] >= 3:  # Max attempts reached
        return "next_question"

    if len(state["question_queue"]) == 0:  # Out of questions
        return "end_interview"

    return "followup"  # Continue evaluating
```

### 4.3 Timeout Handling

```python
# Use asyncio.wait_for() per node
async def timed_node(state):
    try:
        return await asyncio.wait_for(
            expensive_operation(state),
            timeout=30.0  # 30-second limit
        )
    except asyncio.TimeoutError:
        return {"error": "timeout", "fallback_response": "..."}
```

---

## 5. Multi-Step Interview Workflow (Practical Example)

```
┌─────────────────────────────────────┐
│ START: Load Candidate CV             │
└────────────┬────────────────────────┘
             │
             ▼
┌─────────────────────────────────────┐
│ generate_question_node              │
│ (Vector DB + LLM)                   │
└────────────┬────────────────────────┘
             │
             ▼
┌─────────────────────────────────────┐
│ [INTERRUPT] Wait for answer         │
│ (WebSocket: astream_events)         │
└────────────┬────────────────────────┘
             │
             ▼
┌─────────────────────────────────────┐
│ evaluate_answer_node                │
│ (Semantic scoring + LLM eval)       │
└────────────┬────────────────────────┘
             │
        ┌────┴────┐
        ▼         ▼
   score>0.7  score<0.7
        │         │
        │    ┌────▼─────────┐
        │    │ followup_node │
        │    └────┬──────────┘
        │         │
        └────┬────┘
             ▼
       ┌──────────────┐
       │should_continue?
       └──┬─────────┬──┘
          │         │
        YES       NO
          │         │
          ▼         ▼
      [LOOP]    [END: Generate Report]
```

---

## 6. Key Implementation Questions for Elios AI

1. **WebSocket + PostgreSQL**: Use `AsyncPostgresSaver` with `asyncpg` driver. Stream events via `astream_events()`, store thread_id in Candidate interview record.

2. **Checkpointer async setup**: Call `checkpointer.setup()` on app startup. Store connection pool in DI container (singleton).

3. **Break conditions**: Define thresholds in `should_continue()` edge. Stop at: score threshold, attempt limit, or empty question queue.

4. **Error handling**: Wrap LLM/vector DB calls in retry nodes. Store error state in checkpoint for debugging (LangSmith integration optional).

---

## References

- LangGraph PyPI: `langgraph-checkpoint-postgres` v0.2+
- PostgreSQL Checkpointer: `AsyncPostgresSaver.from_conn_string()`
- WebSocket Pattern: `app.astream_events(config)` with interrupt_before
- Error Recovery: Retry logic + fallback nodes
- Production: LangGraph Cloud (Postgres included) or self-hosted

**Unresolved**: Real-time state serialization size limits for large answer transcripts in PostgreSQL; requires testing with typical interview data.
