# Phase 1: Critical UX Fixes

**Phase ID:** phase-01-critical-fixes
**Parent Plan:** 251124-0452-workflow-legacy-parity
**Priority:** CRITICAL
**Estimated Effort:** 6-8 hours
**Owner:** TBD
**Status:** Not Started

## Overview

Fix 3 critical user-facing regressions blocking production rollout of LangGraph workflow:
1. Missing evaluation feedback in WebSocket messages
2. No TTS audio generation
3. Follow-up decision logic using wrong criteria

These issues directly impact UX - users receive no feedback on answers, voice interviews broken, inconsistent follow-up behavior.

## Issues Addressed

### Issue #1: Missing Evaluation Feedback
**Source:** INCONSISTENCIES_ANALYSIS.md Line 14-46
**Impact:** HIGH - No scores, strengths, weaknesses shown to users
**Priority:** P0

### Issue #5: TTS Audio Generation
**Source:** INCONSISTENCIES_ANALYSIS.md Line 203-232
**Impact:** HIGH - Voice interviews broken, accessibility issue
**Priority:** P0

### Issue #2: Follow-Up Decision Logic
**Source:** INCONSISTENCIES_ANALYSIS.md Line 49-102
**Impact:** MEDIUM - Inconsistent behavior between paths
**Priority:** P1

## Implementation Tasks

### Task 1.1: Add Evaluation to Workflow Return Value (2 hours)

**File:** `src/application/workflows/interview_conversation_workflow.py`

**Changes:**

```python
# In process_answer() method (around line 1270)
async def process_answer(
    self,
    thread_id: str,
    answer_text: str,
    is_voice: bool = False,
    voice_metrics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Process answer and continue workflow.

    Returns:
        Dict with next question (if follow-up), completion status, or summary
        NEW: Also includes evaluation data for client display
    """
    # ... existing code ...

    return {
        "complete": result.get("complete", False),
        "question": result.get("current_question"),
        "question_id": result.get("current_question_id"),
        "summary": result.get("summary"),
        "final_status": result.get("final_status"),
        "has_more": result.get("has_more_questions"),
        "errors": result.get("errors", []),
        # NEW: Add evaluation data
        "evaluation": self._extract_latest_evaluation(result),  # Extract from state
    }

# NEW METHOD: Extract latest evaluation from workflow result
def _extract_latest_evaluation(self, result: dict[str, Any]) -> dict[str, Any] | None:
    """Extract latest evaluation from workflow state.

    Args:
        result: Workflow execution result containing state

    Returns:
        Evaluation dict with score, feedback, strengths, weaknesses, gaps
        None if no evaluations in state
    """
    evaluations = result.get("evaluations", [])
    if not evaluations:
        return None

    latest_eval = evaluations[-1]  # Last evaluation in list

    return {
        "answer_id": latest_eval.get("answer_id"),
        "score": latest_eval.get("final_score"),
        "feedback": latest_eval.get("reasoning"),
        "strengths": latest_eval.get("strengths", []),
        "weaknesses": latest_eval.get("weaknesses", []),
        "gaps": latest_eval.get("gaps", []),
    }
```

**Testing:**
```python
# tests/unit/application/workflows/test_interview_conversation_workflow.py

async def test_process_answer_returns_evaluation():
    """Test that process_answer includes evaluation in response."""
    workflow = create_workflow_fixture()
    thread_id = await start_test_session(workflow)

    result = await workflow.process_answer(
        thread_id=thread_id,
        answer_text="Async allows concurrent execution",
    )

    # Assert evaluation present
    assert "evaluation" in result
    assert result["evaluation"] is not None

    # Assert evaluation fields
    eval_data = result["evaluation"]
    assert "score" in eval_data
    assert "feedback" in eval_data
    assert "strengths" in eval_data
    assert "weaknesses" in eval_data
    assert "gaps" in eval_data
```

---

### Task 1.2: Send Evaluation Message in WebSocket Handler (1.5 hours)

**File:** `src/adapters/api/websocket/interview_handler.py`

**Changes:**

```python
# Around line 140-152 (replace TODO with implementation)

# Send evaluation if present
if "evaluation" in result and result["evaluation"]:
    await manager.send_message(
        interview_id,
        {
            "type": "evaluation",
            "answer_id": result["evaluation"]["answer_id"],
            "score": result["evaluation"]["score"],
            "feedback": result["evaluation"]["feedback"],
            "strengths": result["evaluation"]["strengths"],
            "weaknesses": result["evaluation"]["weaknesses"],
            "gaps": result["evaluation"]["gaps"],
        },
    )
    logger.info(
        f"Sent evaluation for answer {result['evaluation']['answer_id']}, "
        f"score={result['evaluation']['score']:.1f}"
    )
```

**Testing:**
```python
# tests/integration/api/websocket/test_interview_handler.py

async def test_workflow_path_sends_evaluation_message(
    websocket_client, interview_id
):
    """Test that workflow path sends evaluation after answer."""
    # Start session
    await websocket_client.send_json({
        "type": "start_session",
        "interview_id": str(interview_id),
    })

    question_msg = await websocket_client.receive_json()
    assert question_msg["type"] == "question"

    # Send answer
    await websocket_client.send_json({
        "type": "answer",
        "text": "Test answer",
    })

    # Expect evaluation message
    eval_msg = await websocket_client.receive_json()
    assert eval_msg["type"] == "evaluation"
    assert "score" in eval_msg
    assert "feedback" in eval_msg
    assert "strengths" in eval_msg
    assert "weaknesses" in eval_msg
    assert "gaps" in eval_msg
```

---

### Task 1.3: Add TTS Audio Generation (2.5 hours)

**File:** `src/adapters/api/websocket/interview_handler.py`

**Changes:**

```python
# Add TTS generation helper method

async def _generate_tts_audio(
    self,
    text: str,
    container: Any,
) -> str | None:
    """Generate TTS audio and encode as base64.

    Args:
        text: Text to synthesize
        container: DI container for TTS adapter

    Returns:
        Base64-encoded audio data, or None if generation fails
    """
    try:
        tts = container.text_to_speech_port()
        audio_bytes = await tts.synthesize_speech(text)
        audio_data = base64.b64encode(audio_bytes).decode("utf-8")
        logger.debug(f"Generated TTS audio: {len(audio_bytes)} bytes")
        return audio_data
    except Exception as exc:
        logger.error(f"TTS generation failed: {exc}", exc_info=True)
        return None  # Non-blocking failure


# Update question sending logic (around line 154-178)

if result.get("question"):
    question_dict = result["question"]
    question_text = question_dict.get("text", "")

    # Generate TTS audio
    audio_data = await self._generate_tts_audio(
        text=question_text,
        container=self.container,
    )

    await manager.send_message(
        interview_id,
        {
            "type": "question",  # Will be fixed in Phase 2 for follow-ups
            "question": question_dict,
            "question_id": result.get("question_id"),
            "has_more": result.get("has_more"),
            "audio_data": audio_data,  # NEW: Include TTS audio
        },
    )
```

**Testing:**
```python
# tests/integration/api/websocket/test_interview_handler.py

async def test_workflow_path_includes_tts_audio(
    websocket_client, interview_id
):
    """Test that workflow path includes TTS audio in questions."""
    # Start session
    await websocket_client.send_json({
        "type": "start_session",
        "interview_id": str(interview_id),
    })

    question_msg = await websocket_client.receive_json()
    assert question_msg["type"] == "question"

    # Assert TTS audio present
    assert "audio_data" in question_msg
    assert question_msg["audio_data"] is not None

    # Verify base64 format (can decode)
    import base64
    audio_bytes = base64.b64decode(question_msg["audio_data"])
    assert len(audio_bytes) > 0
```

**Performance Note:**
- TTS adds ~200-500ms latency
- Consider caching for common questions (future optimization)
- Non-blocking failure if TTS unavailable

---

### Task 1.4: Fix Follow-Up Decision Logic (2 hours)

**File:** `src/application/workflows/interview_conversation_workflow.py`

**Changes:**

```python
# In _decide_followup_node() (around line 539-598)

async def _decide_followup_node(self, state: ConversationState) -> dict[str, Any]:
    """Decide if follow-up question needed.

    Break conditions (aligned with FollowUpDecisionUseCase):
    1. followup_count >= 3 (max reached)
    2. evaluation.is_adaptive_complete() (similarity >= 0.8 OR no gaps)

    Uses domain method for consistency with legacy path.
    """
    try:
        followup_count = state.get("followup_count", 0)
        latest_eval_dict = state["evaluations"][-1]

        # Break condition 1: Max follow-ups
        if followup_count >= 3:
            logger.info(f"Max follow-ups reached ({followup_count})")
            return {"needs_followup": False, "followup_reason": "Max follow-ups reached"}

        # Reconstruct Evaluation entity to call domain method
        from ...domain.models.evaluation import Evaluation
        evaluation = Evaluation(**latest_eval_dict)

        # Break condition 2: Adaptive completion criteria (domain method)
        if evaluation.is_adaptive_complete():
            reason = (
                f"Answer meets completion criteria: "
                f"similarity={evaluation.similarity_score:.2f}"
                if evaluation.similarity_score and evaluation.similarity_score >= 0.8
                else "No unresolved gaps"
            )
            logger.info(reason)
            return {"needs_followup": False, "followup_reason": reason}

        # Accumulate gaps from unresolved
        unresolved_gaps = [
            gap for gap in evaluation.gaps if not gap.resolved
        ]

        cumulative = state.get("cumulative_gaps", [])
        for gap in unresolved_gaps:
            if gap.concept and gap.concept not in cumulative:
                cumulative.append(gap.concept)

        logger.info(
            f"Follow-up needed: {len(unresolved_gaps)} gaps detected",
            extra={"gaps": cumulative},
        )

        return {
            "needs_followup": True,
            "cumulative_gaps": cumulative,
            "followup_reason": f"Detected {len(unresolved_gaps)} gaps",
        }

    except Exception as exc:
        logger.error(f"decide_followup_node failed: {exc}", exc_info=True)
        return {
            "errors": state.get("errors", []) + [f"decide_followup: {str(exc)}"],
            "needs_followup": False,
        }
```

**Testing:**
```python
# tests/unit/application/workflows/test_interview_conversation_workflow.py

async def test_decide_followup_uses_is_adaptive_complete():
    """Test that follow-up decision uses domain method."""
    workflow = create_workflow_fixture()

    # Case 1: High similarity (>= 0.8) → No follow-up
    state = create_state_with_evaluation(similarity_score=0.85)
    result = await workflow._decide_followup_node(state)
    assert result["needs_followup"] is False
    assert "similarity" in result["followup_reason"]

    # Case 2: No gaps → No follow-up
    state = create_state_with_evaluation(gaps=[])
    result = await workflow._decide_followup_node(state)
    assert result["needs_followup"] is False
    assert "No unresolved gaps" in result["followup_reason"]

    # Case 3: Low similarity + gaps → Follow-up
    state = create_state_with_evaluation(
        similarity_score=0.65,
        gaps=[{"concept": "async/await", "resolved": False}]
    )
    result = await workflow._decide_followup_node(state)
    assert result["needs_followup"] is True

    # Case 4: Max count reached → No follow-up
    state = create_state_with_evaluation(followup_count=3)
    result = await workflow._decide_followup_node(state)
    assert result["needs_followup"] is False
```

**Behavioral Change Note:**
- Previously: Only checked `final_score >= 80.0`
- Now: Uses `evaluation.is_adaptive_complete()` (similarity OR gaps)
- **More lenient** - stops follow-ups earlier if quality sufficient

---

## Testing Strategy

### Unit Tests (3 new tests)
1. `test_process_answer_returns_evaluation()` - Workflow return value
2. `test_decide_followup_uses_is_adaptive_complete()` - Follow-up logic
3. `test_generate_tts_audio_handles_failures()` - TTS error handling

### Integration Tests (2 new tests)
1. `test_workflow_path_sends_evaluation_message()` - WebSocket evaluation
2. `test_workflow_path_includes_tts_audio()` - WebSocket TTS

### Regression Tests (1 existing test updated)
1. Update `test_interview_workflow_full_cycle()` to verify evaluation + TTS

### Parity Test (NEW)
```python
# tests/integration/test_legacy_vs_workflow_parity.py

async def test_evaluation_feedback_parity():
    """Compare evaluation feedback between legacy and workflow paths."""
    interview_id = create_test_interview()

    # Run through legacy path
    legacy_messages = await run_legacy_interview(interview_id)
    legacy_eval = find_message_by_type(legacy_messages, "evaluation")

    # Run through workflow path
    workflow_messages = await run_workflow_interview(interview_id)
    workflow_eval = find_message_by_type(workflow_messages, "evaluation")

    # Assert both paths send evaluation
    assert legacy_eval is not None
    assert workflow_eval is not None

    # Assert evaluation fields match (within tolerance)
    assert abs(legacy_eval["score"] - workflow_eval["score"]) < 2.0
    assert set(legacy_eval["strengths"]) == set(workflow_eval["strengths"])
    assert set(legacy_eval["weaknesses"]) == set(workflow_eval["weaknesses"])
```

## Acceptance Criteria

- [ ] **AC1:** Workflow's `process_answer()` returns evaluation dict with score, feedback, strengths, weaknesses, gaps
- [ ] **AC2:** WebSocket handler sends `"type": "evaluation"` message after answer processing
- [ ] **AC3:** All questions (main + follow-up) include `audio_data` field with base64 TTS audio
- [ ] **AC4:** Follow-up decision uses `evaluation.is_adaptive_complete()` method
- [ ] **AC5:** Follow-up stops when `similarity_score >= 0.8` (matches legacy behavior)
- [ ] **AC6:** All 5 new/updated tests pass
- [ ] **AC7:** Parity test shows evaluation messages in both paths
- [ ] **AC8:** No regression in existing workflow tests

## Rollout Checklist

- [ ] Code reviewed and approved
- [ ] All tests passing (unit + integration + parity)
- [ ] Manual testing with test bot (8 scenarios)
- [ ] Documentation updated (WebSocket API docs)
- [ ] Feature flag `use_langgraph_conversation_workflow` ready
- [ ] Monitoring dashboard updated (evaluation delivery rate metric)
- [ ] Rollback plan documented

## Dependencies

### Upstream
- None (self-contained changes)

### Downstream
- Phase 2 depends on this phase (message standardization builds on evaluation messages)
- Phase 5 testing requires all Phase 1 fixes complete

## Risks & Mitigation

### Risk 1: Evaluation Extraction Complexity
**Impact:** Medium | **Likelihood:** Low
**Description:** Extracting evaluation from workflow state may fail if state schema changes
**Mitigation:**
- Add schema validation in `_extract_latest_evaluation()`
- Log warnings for missing fields, use defaults
- Monitor error rate in production

### Risk 2: TTS Latency Impact
**Impact:** Medium | **Likelihood:** High
**Description:** Adding TTS adds 200-500ms latency to question delivery
**Mitigation:**
- Make TTS generation non-blocking (return None on failure)
- Cache TTS audio for common questions (future optimization)
- Monitor p95 latency, alert if >1s

### Risk 3: Domain Method Breaking Changes
**Impact:** Low | **Likelihood:** Very Low
**Description:** `is_adaptive_complete()` signature/behavior may change
**Mitigation:**
- Document dependency on domain method
- Add unit test for method behavior
- Version domain models if changes needed

## Estimated Timeline

| Task | Effort | Start | End |
|------|--------|-------|-----|
| 1.1: Evaluation Return Value | 2h | Day 1 09:00 | Day 1 11:00 |
| 1.2: WebSocket Evaluation Message | 1.5h | Day 1 11:00 | Day 1 12:30 |
| Lunch | - | Day 1 12:30 | Day 1 13:30 |
| 1.3: TTS Audio Generation | 2.5h | Day 1 13:30 | Day 1 16:00 |
| 1.4: Follow-Up Logic Fix | 2h | Day 1 16:00 | Day 1 18:00 |

**Total:** 8 hours (1 day)

## Success Metrics

- **Evaluation Delivery Rate:** 100% of workflow answers receive evaluation message
- **TTS Generation Success:** >99.5% of questions include audio_data
- **Follow-Up Accuracy:** Match legacy decision rate within +/- 5%
- **Test Pass Rate:** 100% (8/8 tests passing)
- **Zero Regressions:** No existing tests broken

## Next Phase

Once Phase 1 complete:
- Proceed to **Phase 2: Message Standardization**
- Fix follow-up question message types
- Add missing metadata fields
- See [phase-02-message-standardization.md](phase-02-message-standardization.md)
