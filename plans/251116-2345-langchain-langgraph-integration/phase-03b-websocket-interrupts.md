# Phase 3B: WebSocket Interrupts & Real-Time Streaming

**Phase ID**: 03B
**Created**: 2025-11-16
**Priority**: High
**Estimated Duration**: 1 week
**Risk Level**: High
**Implementation Status**: Not Started
**Review Status**: Approved

---

## Context Links

- **Parent Plan**: [plan.md](plan.md)
- **Dependencies**: Phase 3A (simple workflow MUST work first)
- **Supersedes**: Original Phase 3 (second half)

---

## Overview

**Add human-in-loop interrupts** to Phase 3A workflow for real-time WebSocket streaming.

**Phase 3A Delivers**: Complete evaluation loop in single invocation (batch mode)

**Phase 3B Adds**:
- Interrupt nodes (pause after each evaluation)
- Real-time WebSocket streaming (send follow-up, wait for answer)
- Thread ID persistence (resume on disconnect)
- Refactor orchestrator to delegate to workflow

**User Decision Applied**: 10-minute timeout before checkpoint cleanup

---

## Requirements

### Functional Requirements
**FR1**: Pause workflow after each follow-up generation (interrupt)
**FR2**: Send follow-up question via WebSocket (real-time)
**FR3**: Wait for candidate answer (WebSocket message resumes workflow)
**FR4**: Resume workflow on WebSocket reconnect (thread_id lookup)
**FR5**: Clean up checkpoints after 10 minutes idle

### Non-Functional Requirements
**NFR1**: No data loss on disconnect (checkpoint persistence)
**NFR2**: Latency: <100ms to pause/resume
**NFR3**: Compatible with Phase 3A workflow (extend, not replace)

---

## Architecture

### Modified Workflow (With Interrupts)
```
StateGraph with interrupts:
┌─────────────────────────────────────────────────┐
│ START                                           │
└────────────┬────────────────────────────────────┘
             ↓
    ┌─────────────────────┐
    │ evaluate_answer     │
    └────────┬────────────┘
             ↓
    ┌─────────────────────┐
    │ check_followup      │
    └────────┬────────────┘
             ↓
      CONDITIONAL:
      ┌──────────┬──────────┐
  needs_followup?
      ↓          │          ↓
┌───────────┐   │   ┌──────────────┐
│ generate_ │   │   │ combine_eval │
│ followup  │   │   └──────────────┘
└─────┬─────┘   │          ↓
      ↓         │        END
┌───────────┐   │
│ [INTERRUPT]   │  ← PAUSE HERE
│ send_ws   │   │
└─────┬─────┘   │
      │         │
   WAIT FOR     │
   ANSWER       │
      ↓         │
   RESUME       │
   (loop back)  │
```

### Interrupt Node Implementation
```python
def send_websocket_node(state: AdaptiveEvalState):
    """Interrupt: Send follow-up, wait for answer."""
    from langgraph.graph import interrupt

    followup_question = state["current_followup_question"]

    # Pause workflow, send question via WebSocket (handled externally)
    # interrupt() returns control to caller, workflow pauses
    answer_text = interrupt({
        "type": "followup_question",
        "question": followup_question.to_dict(),
        "iteration": state["iteration"],
        "cumulative_gaps": state["cumulative_gaps"]
    })

    # When resumed, answer_text is provided by client
    return {"answer_text": answer_text}
```

### WebSocket Handler Integration
```python
# src/adapters/api/websocket/interview_handler.py
async def handle_text_answer(self, message: dict):
    thread_id = self.interview.thread_id or str(uuid4())

    # Start or resume workflow
    async for event in self.workflow.astream_events(
        {"answer_text": message["answer_text"], "question_id": message["question_id"]},
        config={"configurable": {"thread_id": thread_id}}
    ):
        # Filter for interrupt events
        if event["event"] == "on_interrupt":
            interrupt_data = event["data"]

            # Send follow-up question to client
            await self.websocket.send_json({
                "type": "followup_question",
                "question": interrupt_data["question"],
                "iteration": interrupt_data["iteration"]
            })

            # Workflow is paused - wait for next message
            break

        elif event["event"] == "on_chain_end":
            # Workflow completed
            await self.websocket.send_json({
                "type": "evaluation_complete",
                "combined_evaluation": event["data"]["combined_evaluation"]
            })

    # Store thread_id for resumption
    if not self.interview.thread_id:
        self.interview.thread_id = thread_id
        await self.interview_repo.save(self.interview)
```

---

## Implementation Steps

### Step 1: Create WebSocket Sessions Table (1 day)
1. Create domain model:
   ```python
   # src/domain/models/websocket_session.py
   @dataclass
   class WebSocketSession:
       id: UUID
       thread_id: str
       interview_id: UUID
       candidate_id: UUID
       connection_id: str | None
       ip_address: str | None
       user_agent: str | None
       created_at: datetime
       last_activity_at: datetime
       disconnected_at: datetime | None
       is_active: bool
       checkpoint_count: int

       def is_idle(self, timeout_minutes: int = 10) -> bool:
           idle_duration = (datetime.now() - self.last_activity_at).total_seconds() / 60
           return idle_duration > timeout_minutes
   ```

2. Create migration: `alembic revision -m "create websocket_sessions table"`
   ```sql
   CREATE TABLE websocket_sessions (
       id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
       thread_id VARCHAR(100) UNIQUE NOT NULL,
       interview_id UUID NOT NULL REFERENCES interviews(id) ON DELETE CASCADE,
       candidate_id UUID NOT NULL REFERENCES candidates(id),
       connection_id VARCHAR(100),
       ip_address INET,
       user_agent TEXT,
       created_at TIMESTAMP NOT NULL DEFAULT NOW(),
       last_activity_at TIMESTAMP NOT NULL DEFAULT NOW(),
       disconnected_at TIMESTAMP,
       is_active BOOLEAN DEFAULT true,
       checkpoint_count INTEGER DEFAULT 0,
       last_checkpoint_size_kb INTEGER,

       INDEX idx_thread_id (thread_id),
       INDEX idx_interview_id (interview_id),
       INDEX idx_last_activity (last_activity_at, is_active)
   );
   ```

3. Create repository port:
   ```python
   # src/domain/ports/websocket_session_repository_port.py
   class WebSocketSessionRepositoryPort(ABC):
       @abstractmethod
       async def create_session(self, session: WebSocketSession) -> WebSocketSession:
           pass

       @abstractmethod
       async def get_by_thread_id(self, thread_id: str) -> WebSocketSession | None:
           pass

       @abstractmethod
       async def get_idle_sessions(self, timeout_minutes: int = 10) -> list[WebSocketSession]:
           pass

       @abstractmethod
       async def update_activity(self, thread_id: str):
           pass

       @abstractmethod
       async def delete_session(self, thread_id: str):
           pass
   ```

4. Implement repository:
   ```python
   # src/adapters/persistence/websocket_session_repository.py
   class WebSocketSessionRepository(WebSocketSessionRepositoryPort):
       async def get_idle_sessions(self, timeout_minutes: int = 10):
           cutoff = datetime.now() - timedelta(minutes=timeout_minutes)
           result = await self.session.execute(
               select(WebSocketSessionModel)
               .where(WebSocketSessionModel.last_activity_at < cutoff)
               .where(WebSocketSessionModel.is_active == True)
           )
           return [self.mapper.to_domain(model) for model in result.scalars().all()]
   ```

### Step 2: Modify Phase 3A Workflow (1 day)
1. Add interrupt node after `generate_followup`
2. Configure `interrupt_before=["send_websocket"]`
3. Test interrupt/resume locally (manual script)

### Step 3: Refactor WebSocket Handler (2 days)
1. Replace state management with workflow delegation
2. Implement `astream_events()` listener
3. Handle interrupt events (send follow-up, pause)
4. Handle completion events (send final evaluation)
5. Store thread_id on first run

### Step 4: Checkpoint Cleanup (1 day)
1. Create background task:
   ```python
   # src/infrastructure/tasks/checkpoint_cleanup.py
   async def cleanup_idle_checkpoints():
       """Delete checkpoints idle >10 minutes."""
       cutoff = datetime.now() - timedelta(minutes=10)

       # Query checkpoints table
       result = await session.execute(
           select(CheckpointModel).where(
               CheckpointModel.updated_at < cutoff,
               CheckpointModel.status == "interrupted"
           )
       )
       idle_checkpoints = result.scalars().all()

       for cp in idle_checkpoints:
           await session.delete(cp)
       await session.commit()
   ```
2. Schedule via APScheduler (every 5 minutes)

### Step 5: Testing (2 days)
1. Test interrupt flow (send follow-up, wait, resume)
2. Test WebSocket disconnect/reconnect (thread_id lookup)
3. Test checkpoint cleanup (wait 11 minutes, verify deleted)
4. Integration test: Full interview with 3 follow-ups

---

## Success Criteria

**Real-Time Streaming**:
- ✅ Follow-up questions sent immediately (not batched)
- ✅ Client receives questions one-by-one

**Resume Capability**:
- ✅ WebSocket reconnect continues from last state
- ✅ No duplicate evaluations or questions

**Cleanup**:
- ✅ Idle checkpoints deleted after 10 minutes
- ✅ No storage leak

---

## Risk Mitigation

**Risk 1: Interrupt node fails** (from Phase 0 validation)
- Mitigation: Phase 0 prototyped interrupts successfully
- Fallback: Keep Phase 3A (batch mode) as alternative

**Risk 2: WebSocket message ordering**
- Risk: Out-of-order messages break workflow
- Mitigation: Message sequence numbers, idempotency checks

**Risk 3: Thread ID collisions**
- Risk: UUID collision (extremely rare)
- Mitigation: UUID v4 (2^122 space), validate uniqueness

---

## Next Steps After Phase 3B

1. Deploy to staging with feature flag
2. Monitor checkpoint table growth
3. Tune cleanup interval (10 min may be too aggressive)
4. Proceed to Phase 4 (observability)

---

**Phase Status**: Ready to Start (after Phase 3A)
**Dependencies**: Phase 3A MUST complete successfully
**Estimated Start**: Week 6
