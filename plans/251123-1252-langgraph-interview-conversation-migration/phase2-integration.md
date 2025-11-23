# Phase 2: Integration & Testing

**Duration**: 3-4 days
**Status**: Not Started
**Dependencies**: Phase 1 complete (workflow nodes + StateGraph)

## Objectives

Wire `InterviewConversationWorkflow` to WebSocket handler, validate with test bot, ensure parity with orchestrator.

## Integration Architecture

### DI Container Updates

```python
# src/infrastructure/dependency_injection/container.py

async def create_interview_conversation_workflow(
    self,
    session: AsyncSession
) -> InterviewConversationWorkflow:
    """Factory for conversation workflow with checkpointing."""
    from ...application.workflows.interview_conversation_workflow import (
        InterviewConversationWorkflow
    )

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

### WebSocket Handler Simplification

```python
# src/adapters/api/websocket/interview_handler.py (SIMPLIFIED)

from ....infrastructure.config.settings import get_settings

async def handle_interview_websocket(websocket: WebSocket, interview_id: UUID):
    """WebSocket handler with feature flag routing."""
    await manager.connect(interview_id, websocket)
    settings = get_settings()

    try:
        if settings.use_langgraph_conversation:
            await _handle_with_workflow(websocket, interview_id)
        else:
            await _handle_with_orchestrator(websocket, interview_id)  # Legacy

    except WebSocketDisconnect:
        manager.disconnect(interview_id)
    except Exception as exc:
        logger.error(f"WebSocket error: {exc}", exc_info=True)
        await manager.send_message(interview_id, {
            "type": "error",
            "code": "INTERNAL_ERROR",
            "message": str(exc)
        })

async def _handle_with_workflow(websocket: WebSocket, interview_id: UUID):
    """New workflow-based handler (Phase 2)."""
    container = get_container()

    async for session in get_async_session():
        workflow = await container.create_interview_conversation_workflow(session)

        # Start session (sends first question)
        result = await workflow.start_session(interview_id)
        thread_id = result["thread_id"]

        # Send first question to client
        await manager.send_message(interview_id, {
            "type": "question",
            "question_id": result["current_question_id"],
            "text": result["current_question"]["text"],
            "question_type": result["current_question"]["question_type"],
        })

        # Listen for answers
        while True:
            data = await websocket.receive_json()

            if data["type"] == "text_answer":
                # Process answer through workflow
                result = await workflow.process_answer(
                    answer_text=data["answer_text"],
                    thread_id=thread_id  # Resume from checkpoint
                )

                # Send evaluation
                await manager.send_message(interview_id, {
                    "type": "evaluation",
                    **result["evaluation"]
                })

                # Handle next step based on workflow result
                if result.get("followup_question"):
                    # Send follow-up
                    await manager.send_message(interview_id, {
                        "type": "followup_question",
                        **result["followup_question"]
                    })
                elif result.get("next_question"):
                    # Send next main question
                    await manager.send_message(interview_id, {
                        "type": "question",
                        **result["next_question"]
                    })
                elif result.get("complete"):
                    # Interview complete
                    await manager.send_message(interview_id, {
                        "type": "interview_complete",
                        **result["summary"]
                    })
                    break

            elif data["type"] == "audio_chunk":
                # Audio handled separately (unchanged from Phase 1)
                await handle_audio_chunk(interview_id, data, container)

        break  # Exit session loop
```

**LOC Reduction**: 342 LOC → ~200 LOC (42% reduction)

---

## Workflow Public API

```python
# src/application/workflows/interview_conversation_workflow.py

class InterviewConversationWorkflow(BaseWorkflow):
    """Public API for WebSocket integration."""

    async def start_session(self, interview_id: UUID) -> dict[str, Any]:
        """Start interview session.

        Returns:
            {
                "thread_id": str,
                "current_question_id": str,
                "current_question": {...},
            }
        """
        thread_id = self.generate_thread_id("interview")

        initial_state: ConversationState = {
            "interview_id": str(interview_id),
            "candidate_id": str(candidate_id),  # Load from DB
            "messages": [],
            "answers": [],
            "evaluations": [],
            "followup_count": 0,
            "cumulative_gaps": [],
            "has_more_questions": True,
            "needs_followup": False,
            "complete": False,
            "errors": [],
            "retry_count": 0,
            "checkpoint_thread_id": thread_id,
            "last_checkpoint_time": None,
        }

        # Execute start_session_node
        result = await self.app.ainvoke(
            initial_state,
            {"configurable": {"thread_id": thread_id}}
        )

        return {
            "thread_id": thread_id,
            "current_question_id": result["current_question_id"],
            "current_question": result["current_question"],
        }

    async def process_answer(
        self,
        answer_text: str,
        thread_id: str,
        voice_metrics: dict | None = None
    ) -> dict[str, Any]:
        """Process answer and execute workflow nodes.

        Returns:
            {
                "evaluation": {...},
                "followup_question": {...} | None,
                "next_question": {...} | None,
                "complete": bool,
                "summary": {...} | None,
            }
        """
        # Resume workflow from checkpoint
        state_update = {
            "pending_answer_text": answer_text,
            "voice_metrics": voice_metrics,
            "is_voice_answer": voice_metrics is not None,
        }

        result = await self.app.ainvoke(
            state_update,
            {"configurable": {"thread_id": thread_id}}
        )

        # Format response for WebSocket
        response = {
            "evaluation": result["evaluations"][-1] if result.get("evaluations") else None,
            "complete": result.get("complete", False),
        }

        if result.get("needs_followup"):
            response["followup_question"] = result["current_question"]
        elif result.get("has_more_questions") and not result.get("complete"):
            response["next_question"] = result["current_question"]
        elif result.get("complete"):
            response["summary"] = result.get("summary")

        return response
```

---

## Tasks

### Task 2.1: Update DI Container (2h)

- Add `create_interview_conversation_workflow()` factory
- Wire dependencies (repos + LLM)
- Test factory method

**Test**: `test_container_creates_workflow`

---

### Task 2.2: Simplify WebSocket Handler (6h)

- Extract workflow logic from orchestrator
- Add feature flag check
- Implement `_handle_with_workflow()`
- Keep `_handle_with_orchestrator()` for rollback
- Add audio handling compatibility

**LOC**: 342 → 200 (remove orchestrator calls)

**Tests**:
- `test_websocket_with_workflow_flag_true`
- `test_websocket_with_workflow_flag_false` (legacy path)

---

### Task 2.3: Add Feature Flag (1h)

```python
# src/infrastructure/config/settings.py

class Settings(BaseSettings):
    # Existing flags
    use_langgraph_adaptive_simple: bool = False
    use_langgraph_adaptive_interrupt: bool = False

    # NEW flag
    use_langgraph_conversation: bool = Field(
        default=False,
        description="Enable LangGraph conversation workflow (replaces session_orchestrator)"
    )

    # Optional: Rollout percentage for canary
    langgraph_rollout_percentage: int = Field(
        default=0,
        ge=0,
        le=100,
        description="Percentage of traffic for LangGraph conversation (0-100)"
    )
```

---

### Task 2.4: Integration Tests (8h)

**Test Scenarios** (5 tests):

1. **test_workflow_main_question_cycle**:
   - Start session → Answer main Q → Eval → Next Q → Repeat × 3 → Complete

2. **test_workflow_followup_generation**:
   - Answer with low score → Follow-up generated → Answer follow-up → Continue

3. **test_workflow_checkpoint_resume**:
   - Start session → Answer → Disconnect → Reconnect → Resume from checkpoint

4. **test_workflow_memory_persistence**:
   - Verify conversation history grows correctly over 5 Q&A pairs

5. **test_workflow_vs_orchestrator_parity**:
   - Same inputs → Compare outputs (scores, follow-ups, summary)

```python
# tests/integration/workflows/test_conversation_workflow_integration.py

async def test_workflow_main_question_cycle(db_session):
    """Test complete Q&A cycle with workflow."""
    # Setup
    interview = await seed_interview(db_session, question_count=3)

    workflow = InterviewConversationWorkflow(
        checkpointer=await get_checkpointer(),
        interview_repo=PostgreSQLInterviewRepository(db_session),
        question_repo=PostgreSQLQuestionRepository(db_session),
        answer_repo=PostgreSQLAnswerRepository(db_session),
        evaluation_repo=PostgreSQLEvaluationRepository(db_session),
        followup_repo=PostgreSQLFollowUpQuestionRepository(db_session),
        llm=MockLLMAdapter(),  # Deterministic responses
    )

    # Start session
    result = await workflow.start_session(interview.id)
    assert result["current_question_id"]
    thread_id = result["thread_id"]

    # Answer 3 questions
    for i in range(3):
        result = await workflow.process_answer(
            answer_text=f"Answer {i}",
            thread_id=thread_id
        )

        assert result["evaluation"]["final_score"] > 0

        if i < 2:
            assert result.get("next_question")  # More questions
        else:
            assert result.get("complete")  # Last question
            assert result.get("summary")

async def test_workflow_vs_orchestrator_parity(db_session):
    """Compare workflow vs. orchestrator outputs."""
    # Setup same interview for both
    interview = await seed_interview(db_session, question_count=2)
    answers = ["Answer 1", "Answer 2"]

    # Run with workflow
    workflow_result = await run_interview_with_workflow(interview.id, answers)

    # Run with orchestrator (legacy)
    orchestrator_result = await run_interview_with_orchestrator(interview.id, answers)

    # Compare
    assert len(workflow_result["evaluations"]) == len(orchestrator_result["evaluations"])
    for w_eval, o_eval in zip(workflow_result["evaluations"], orchestrator_result["evaluations"]):
        # Scores should be identical (same LLM, same prompts)
        assert abs(w_eval["final_score"] - o_eval["final_score"]) < 1.0

    # Summary should be identical
    assert workflow_result["summary"]["overall_score"] == orchestrator_result["summary"]["overall_score"]
```

---

### Task 2.5: Test Bot Validation (6h)

**Run Test Bot** against workflow:

```bash
# Enable workflow feature flag
export USE_LANGGRAPH_CONVERSATION=true

# Run test bot (13 scenarios)
python -m tests.bot.run_tests \
    --mode=real \
    --output=reports/workflow_validation.json

# Compare with orchestrator baseline
python -m tests.bot.compare_runs \
    --baseline=reports/orchestrator_baseline.json \
    --current=reports/workflow_validation.json \
    --tolerance=2.0  # Allow ±2 points score difference
```

**Success Criteria**:
- All 13 scenarios pass (8 mock + 5 real)
- Score differences <2 points (workflow vs. orchestrator)
- No timeout errors
- Follow-up logic identical (same break conditions)

---

### Task 2.6: Performance Baseline (4h)

**Metrics to Collect**:

1. **Latency per Operation**:
   - Evaluate answer: Target <2s
   - Generate follow-up: Target <1.5s
   - Load next question: Target <500ms
   - Complete interview: Target <3s

2. **Checkpoint Overhead**:
   - Time per checkpoint write: Target <50ms
   - State size per checkpoint: Target <10KB

3. **Memory Usage**:
   - Conversation state size after 10 Q&A pairs: Target <50KB
   - Memory growth rate: Target linear (not exponential)

```python
# tests/integration/workflows/test_workflow_performance.py

import time

async def test_workflow_latency_baseline(db_session):
    """Measure workflow operation latency."""
    workflow = create_workflow(db_session)
    interview = await seed_interview(db_session, question_count=5)

    latencies = {
        "start_session": [],
        "process_answer": [],
        "checkpoint_write": [],
    }

    # Start session
    start = time.perf_counter()
    result = await workflow.start_session(interview.id)
    latencies["start_session"].append(time.perf_counter() - start)

    # Process 5 answers
    for i in range(5):
        start = time.perf_counter()
        result = await workflow.process_answer(
            answer_text=f"Answer {i}",
            thread_id=result["thread_id"]
        )
        latencies["process_answer"].append(time.perf_counter() - start)

    # Report
    print("=== Latency Baseline ===")
    for op, times in latencies.items():
        avg = sum(times) / len(times) * 1000  # ms
        p95 = percentile(times, 95) * 1000
        print(f"{op}: avg={avg:.2f}ms, p95={p95:.2f}ms")

    # Assertions
    assert percentile(latencies["process_answer"], 95) * 1000 < 2500  # <2.5s P95
```

**Deliverable**: `metrics/performance-baseline.json` with P50/P95/P99 for all operations

---

## Success Criteria

**Integration**:
- [ ] DI container creates workflow successfully
- [ ] WebSocket handler routes to workflow with feature flag
- [ ] Audio handling works with workflow (voice answers)

**Testing**:
- [ ] 5 integration tests pass
- [ ] 13 test bot scenarios pass
- [ ] Workflow vs. orchestrator parity (<2 points score diff)

**Performance**:
- [ ] All latency targets met (P95)
- [ ] Checkpoint overhead <50ms
- [ ] Memory growth linear (<50KB per interview)

## Deliverables

- [ ] Updated `container.py` with workflow factory
- [ ] Simplified `interview_handler.py` (~200 LOC)
- [ ] Integration tests (5 files)
- [ ] Test bot validation report
- [ ] Performance baseline report

## Risks

**Risk**: Test bot failures due to minor output differences
- **Mitigation**: Allow ±2 points tolerance, focus on logic parity (not exact scores)

**Risk**: Performance targets not met
- **Mitigation**: Profile with py-spy, optimize state size, reduce checkpoint frequency

## Unresolved Questions

1. WebSocket reconnect: resume from checkpoint or restart?
2. Test bot tolerance: ±2 points or ±5%?
3. Performance baseline: collect in dev or staging environment?

---

**Phase 2 Status**: Ready to start after Phase 1 complete
**Next Phase**: Phase 3 (Canary Deployment)
