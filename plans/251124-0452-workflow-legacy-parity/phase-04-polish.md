# Phase 4: Polish & Edge Cases

**Phase ID:** phase-04-polish
**Parent Plan:** 251124-0452-workflow-legacy-parity
**Priority:** LOW
**Estimated Effort:** 3-4 hours
**Owner:** TBD
**Status:** Not Started
**Depends On:** Phase 1, Phase 2, Phase 3

## Overview

Handle minor issues and edge cases:
- State synchronization and validation
- Retry logic for transient failures
- Audio file path storage decision
- Error handling improvements

## Issues Addressed

### Issue #7: State Synchronization
**Source:** INCONSISTENCIES_ANALYSIS.md Line 302-316
**Impact:** LOW - Edge case where external DB updates cause stale state

### Issue #8: Incomplete Retry Logic
**Source:** INCONSISTENCIES_ANALYSIS.md Line 318-330
**Impact:** LOW - No resilience for transient LLM failures

### Issue #3: Missing Audio File Path
**Source:** INCONSISTENCIES_ANALYSIS.md Line 104-149
**Impact:** LOW - Storage verification needed

## Implementation Tasks

### Task 4.1: State Refresh for Critical Operations (1.5 hours)

**Objective:** Reload interview from DB before critical state transitions to avoid stale state.

**File:** `src/application/workflows/interview_conversation_workflow.py`

**Changes:**

```python
# Add state refresh helper

async def _refresh_interview_state(
    self,
    state: ConversationState,
) -> dict[str, Any]:
    """Reload interview from DB to sync critical fields.

    Refreshes:
    - interview.status
    - interview.current_question_index
    - interview.current_followup_count

    Args:
        state: Current workflow state

    Returns:
        State updates with refreshed fields
    """
    try:
        interview_id = UUID(state["interview_id"])
        interview = await self.interview_repo.get_by_id(interview_id)

        if not interview:
            logger.error(f"Interview {interview_id} not found during refresh")
            return {}

        # Return refreshed fields (don't overwrite entire state)
        return {
            "interview_status": interview.status.value,
            "current_question_index": interview.current_question_index,
            "followup_count": interview.current_followup_count,
        }

    except Exception as exc:
        logger.warning(f"State refresh failed: {exc}")
        return {}  # Non-blocking


# Call before critical nodes

async def _complete_interview_node(self, state: ConversationState) -> dict[str, Any]:
    """Complete interview with state refresh."""
    try:
        # Refresh state before completion
        refreshed = await self._refresh_interview_state(state)
        if refreshed:
            logger.debug("State refreshed before completion")

        # ... existing completion logic ...
```

**Testing:**
```python
async def test_state_refresh_syncs_db():
    """Test state refresh updates stale fields."""
    workflow = create_workflow_fixture()

    # Create stale state
    state = create_state_with_stale_status()

    # Refresh
    refreshed = await workflow._refresh_interview_state(state)

    # Assert updated
    assert "interview_status" in refreshed
    assert refreshed["interview_status"] == "EVALUATING"
```

---

### Task 4.2: Implement Retry Logic (1 hour)

**Objective:** Add exponential backoff retry for transient LLM failures.

**File:** `src/application/workflows/interview_conversation_workflow.py`

**Changes:**

```python
import asyncio
from typing import Callable, TypeVar, ParamSpec

P = ParamSpec("P")
T = TypeVar("T")


async def _retry_with_backoff(
    self,
    func: Callable[P, T],
    *args: P.args,
    **kwargs: P.kwargs,
) -> T:
    """Retry function with exponential backoff.

    Args:
        func: Async function to retry
        *args, **kwargs: Function arguments

    Returns:
        Function result

    Raises:
        Last exception if all retries exhausted
    """
    max_retries = 3
    base_delay = 1.0  # seconds

    for attempt in range(max_retries):
        try:
            return await func(*args, **kwargs)
        except Exception as exc:
            if attempt == max_retries - 1:
                # Last attempt - raise
                raise

            # Exponential backoff
            delay = base_delay * (2 ** attempt)
            logger.warning(
                f"Retry {attempt + 1}/{max_retries} after {delay}s: {exc}",
                extra={"error": str(exc), "attempt": attempt + 1},
            )
            await asyncio.sleep(delay)

    raise RuntimeError("Retry logic failed")  # Should never reach


# Use in LLM calls

async def _evaluate_answer_node(self, state: ConversationState) -> dict[str, Any]:
    """Evaluate answer with retry logic."""
    try:
        # ... existing setup ...

        # Wrap LLM call with retry
        llm_eval = await self._retry_with_backoff(
            self.llm.evaluate_answer,
            question=question,
            answer_text=answer_text,
            context=context,
            followup_context=followup_context,
        )

        # ... rest of evaluation ...
```

**Testing:**
```python
async def test_retry_with_backoff_succeeds_on_third_attempt():
    """Test retry succeeds after transient failures."""
    workflow = create_workflow_fixture()

    call_count = 0

    async def flaky_function():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ConnectionError("Transient failure")
        return "success"

    result = await workflow._retry_with_backoff(flaky_function)

    assert result == "success"
    assert call_count == 3


async def test_retry_raises_after_max_attempts():
    """Test retry raises after exhausting retries."""
    workflow = create_workflow_fixture()

    async def always_fails():
        raise ValueError("Permanent failure")

    with pytest.raises(ValueError):
        await workflow._retry_with_backoff(always_fails)
```

---

### Task 4.3: Audio File Path Decision (30 min)

**Objective:** Document decision on whether to store `audio_file_path` in Answer entity.

**Analysis:**

**Legacy stores:**
```python
answer = Answer(
    # ...
    audio_file_path=audio_file_path,  # Path to saved audio file
    # ...
)
```

**Workflow doesn't store:**
```python
answer = Answer(
    # ...
    # No audio_file_path field
    # ...
)
```

**Verification:**
- Check `src/domain/models/answer.py` schema
- Review use cases for stored audio files
- Performance/storage implications

**Decision Matrix:**

| Criterion | Store File | Don't Store |
|-----------|------------|-------------|
| **Playback** | Can replay original audio | TTS regeneration only |
| **Forensics** | Original recording preserved | Lost after session |
| **Storage** | ~100KB per answer | Zero storage |
| **Compliance** | May violate GDPR (voice data) | Privacy-friendly |

**Recommendation:** DON'T STORE (align with workflow)
- Voice metrics already captured (WPM, fluency, etc.)
- Privacy concerns with storing voice recordings
- TTS can regenerate audio for playback
- Reduces storage costs

**Documentation:**

```markdown
# Audio Storage Decision

## Decision: Don't Store Audio Files

**Rationale:**
- Voice metrics (WPM, fluency, confidence) captured in Answer.voice_metrics
- Privacy: Avoid storing voice recordings (GDPR compliance)
- Storage: Save ~100KB per voice answer
- Playback: Use TTS to regenerate audio from text

**Migration:**
- Legacy code continues storing for backwards compatibility
- Workflow path doesn't store (new standard)
- Deprecate audio_file_path field in v2.0

**Logged:** 2025-11-24
```

**File:** `docs/decisions/audio-storage.md` (NEW)

---

### Task 4.4: Error Handling Audit (1 hour)

**Objective:** Review and improve error handling across workflow nodes.

**Checklist:**

```python
# Audit each node for error handling

✓ _route_entry_node: Pass-through, no errors expected
✓ _start_session_node: Try-catch with errors array
✓ _evaluate_answer_node: Try-catch with retry_count
✓ _update_memory_node: Try-catch with errors array
✓ _decide_followup_node: Try-catch, sets needs_followup=False
✓ _generate_followup_node: Try-catch, sets needs_followup=False
✓ _next_question_or_complete_node: Try-catch, sets complete=True
✓ _complete_interview_node: Try-catch, sets complete=True

# Add missing error context

# In each node, enhance error logging:
logger.error(
    f"Node {node_name} failed: {exc}",
    exc_info=True,
    extra={
        "interview_id": state["interview_id"],
        "node": node_name,
        "state_snapshot": {
            "followup_count": state.get("followup_count"),
            "has_more": state.get("has_more_questions"),
            "errors": state.get("errors", []),
        },
    },
)
```

**Testing:**
```python
async def test_error_handling_in_evaluate_node():
    """Test graceful error handling in evaluate node."""
    workflow = create_workflow_fixture()

    # Mock LLM to raise exception
    workflow.llm.evaluate_answer = AsyncMock(
        side_effect=ConnectionError("LLM unavailable")
    )

    state = create_state_with_pending_answer()

    result = await workflow._evaluate_answer_node(state)

    # Assert error captured
    assert "errors" in result
    assert len(result["errors"]) > 0
    assert "LLM unavailable" in result["errors"][0]
    assert result["retry_count"] == 1
```

---

## Testing Strategy

### Unit Tests (5 new)
1. `test_state_refresh_syncs_db()` - State refresh logic
2. `test_retry_with_backoff_succeeds_on_third_attempt()` - Retry success
3. `test_retry_raises_after_max_attempts()` - Retry exhaustion
4. `test_error_handling_in_evaluate_node()` - Error capture
5. `test_non_blocking_state_refresh_failure()` - Graceful degradation

### Documentation (2 new docs)
1. `docs/decisions/audio-storage.md` - Audio storage decision
2. Update workflow docstrings with retry behavior

**Total:** 5 tests + 2 docs

## Acceptance Criteria

- [ ] **AC1:** State refresh implemented for critical nodes
- [ ] **AC2:** Retry logic with exponential backoff working
- [ ] **AC3:** Audio storage decision documented
- [ ] **AC4:** All error handlers include context logging
- [ ] **AC5:** All 5 tests passing
- [ ] **AC6:** No regressions in existing tests
- [ ] **AC7:** Error rate <0.1% in manual testing

## Rollout Checklist

- [ ] Code reviewed
- [ ] Tests passing
- [ ] Documentation updated
- [ ] Manual error injection testing
- [ ] Monitoring alerts configured
- [ ] Rollback plan ready

## Risks & Mitigation

### Risk 1: State Refresh Race Condition
**Impact:** Low | **Likelihood:** Very Low
**Mitigation:** Refresh only reads DB, doesn't write

### Risk 2: Retry Amplification
**Impact:** Medium | **Likelihood:** Low
**Mitigation:** Max 3 retries, exponential backoff

## Estimated Timeline

| Task | Effort |
|------|--------|
| 4.1: State Refresh | 1.5h |
| 4.2: Retry Logic | 1h |
| 4.3: Audio Decision | 30min |
| 4.4: Error Audit | 1h |

**Total:** 4 hours (Day 4 AM)

## Next Phase

Proceed to **Phase 5: Testing & Validation**
- Parity test suite
- Load testing
- Rollout validation
- See [phase-05-testing.md](phase-05-testing.md)
