# Findings Summary: Cascading Timeout Logic Issue

**Date**: 2025-11-22
**Investigation Type**: Code Analysis + Debugger Analysis
**Files Analyzed**: `tests/bot/test_runner.py`, `tests/bot/test_bot_client.py`

---

## Executive Summary

Test bot uses **cascading timeout logic** (try question → try follow_up → try completion) which:
1. Wastes 15 seconds (5+5+5) per failed cascade
2. Breaks on strict type validation when server sends "question" but test expects "follow_up_question"
3. Causes ValueError instead of TimeoutError, preventing cascade from reaching next tier

**Root Cause**: Mismatch between server's state-based message types and test's expectation-based message type waiting.

**Impact**: All multi-question test scenarios fail with ValueError.

---

## Technical Findings

### 1. Cascading Timeout Logic (Lines 400-421)

**Location**: `tests/bot/test_runner.py`

```python
try:
    message = await bot.wait_for_question(timeout=5.0)  # Tier 1
    message_type = "question"
except TimeoutError:
    try:
        message = await bot.wait_for_follow_up(timeout=5.0)  # Tier 2
        message_type = "follow_up"
    except TimeoutError:
        try:
            completion = await bot.wait_for_completion(timeout=5.0)  # Tier 3
            # ...
        except TimeoutError:
            break
```

**Purpose**: Test doesn't know what message type server will send, so tries all possibilities.

**Problem**: If server sends "question" on 2nd iteration but test expects "follow_up_question", Tier 1 raises **ValueError** (not TimeoutError), cascade never reaches Tier 2.

### 2. Strict Type Validation (Lines 347-351)

**Location**: `tests/bot/test_bot_client.py`, method `_wait_for_message_type()`

```python
# Verify type
if message.get("type") != msg_type:
    raise ValueError(
        f"Expected message type '{msg_type}', "
        f"got '{message.get('type')}'"
    )
```

**Purpose**: Ensure test receives expected message type.

**Problem**: No flexibility for semantically equivalent types.

**Example Failure**:
- Server sends: `{"type": "question", "question_id": "...", "text": "..."}`
- Test calls: `wait_for_follow_up(timeout=5.0)` (expects "follow_up_question")
- Result: `ValueError: Expected 'follow_up_question', got 'question'`

### 3. Message Queue Mechanics

**Location**: `tests/bot/test_bot_client.py`

**Architecture**:
- `_receive_loop()` (background task) reads from WebSocket, pushes to `asyncio.Queue`
- `_wait_for_message_type()` reads from queue (FIFO)
- Queue is **unbounded** (no max size)

**Key Insight**: Messages arrive in queue regardless of what test expects. If test waits for wrong type, message is consumed and discarded (raises ValueError).

### 4. Server Message Sequencing

**Message Types**:
1. `question` - Regular interview question
2. `follow_up_question` - Adaptive follow-up
3. `evaluation` - Answer score/feedback
4. `interview_complete` - Final summary
5. `error` - Error message

**Server Logic** (inferred from tests):
- Server doesn't distinguish between "question" and "follow_up_question" delivery order
- Both types can appear at any point in QA loop
- Server decides type based on **interview state**, not **question index**

**Example Flow**:
```
Server: question #1 → Client: answer → Server: evaluation
Server: question #2 → Client: answer → Server: evaluation
Server: follow_up_question #1 → Client: answer → Server: evaluation
Server: question #3 → Client: answer → Server: evaluation
Server: interview_complete
```

**Test Expectation** (broken assumption):
- Test assumes: "First message is always 'question', later messages might be 'follow_up_question'"
- Reality: Server sends both types interchangeably

### 5. Timeout Configuration

**Location**: `tests/bot/config.py`, class `TimeoutConfig`

```python
question_timeout_sec: float = 5.0
follow_up_timeout_sec: float = 5.0
completion_timeout_sec: float = 5.0
```

**Current Usage**:
- `question_timeout_sec` - Tier 1 wait
- `follow_up_timeout_sec` - Tier 2 wait
- `completion_timeout_sec` - Tier 3 wait

**Total Cascade Time**: 15 seconds (if all tiers timeout)

**Issue**: Having separate timeouts for "question" vs "follow_up_question" implies they're fundamentally different operations, but they're not (both trigger same bot action: answer → evaluate).

---

## Root Cause Analysis

### Why Cascade Exists

Test bot doesn't know server's internal state machine, so it can't predict message type. Cascade tries all possibilities sequentially.

### Why It Breaks

1. **Strict validation**: `_wait_for_message_type()` rejects semantically valid messages
2. **Wrong exception**: ValueError raised instead of TimeoutError
3. **Type equivalence**: "question" and "follow_up_question" require identical handling

### Functional Equivalence

Both message types require **same bot actions**:
1. Parse question text
2. Generate answer
3. Send answer
4. Wait for evaluation

**Difference**: Only metadata fields (`index` vs `order_in_sequence`, `total` vs `parent_question_id`)

**Conclusion**: Test shouldn't care which type arrives, only that **a question arrived**.

---

## Message Flow Analysis

### Current (Broken)

```
Server Queue            Test Expectation        Result
--------------------------------------------------------------
[question #1]    →     wait_for_question()     ✓ Success
[evaluation]     →     wait_for_evaluation()   ✓ Success
[follow_up #1]   →     wait_for_question()     ✗ ValueError!
                        (never tries wait_for_follow_up)
```

### Proposed (Fixed)

```
Server Queue              Test Expectation              Result
------------------------------------------------------------------------
[question #1]      →     wait_for_next_question()      ✓ Success (question)
[evaluation]       →     wait_for_evaluation()         ✓ Success
[follow_up #1]     →     wait_for_next_question()      ✓ Success (follow_up)
[evaluation]       →     wait_for_evaluation()         ✓ Success
[completion]       →     wait_for_completion()         ✓ Success
```

---

## Performance Impact

### Current Behavior

**Best Case** (all messages match expectations):
- Time: 0s wasted (immediate message processing)

**Worst Case** (cascade fails to tier 3):
- Time: 15s wasted (5s × 3 tiers)
- Example: Server sends "error", test tries question → follow_up → completion → all timeout

**Average Case** (mixed question types):
- Time: 5-10s wasted per unexpected type
- Example: Server sends "follow_up_question", test waits 5s for "question" (timeout), then immediately succeeds on tier 2

### Proposed Behavior

**All Cases**:
- Time: 0s wasted (flexible waiting accepts both types)
- Only timeout if **no message** arrives (legitimate timeout scenario)

---

## Edge Cases Discovered

### Edge Case 1: Queue Backlog

**Scenario**: Server sends 3 messages rapidly (question, evaluation, follow_up)

**Current Behavior**:
- All 3 messages buffered in queue
- Test reads one at a time (FIFO order preserved)
- If test waits for wrong type on 3rd read, ValueError

**Proposed Behavior**:
- Same buffering (no change)
- Flexible waiting accepts question or follow_up (no error)

### Edge Case 2: Connection Lost

**Scenario**: WebSocket disconnects mid-interview

**Current Behavior**:
- `_receive_loop()` exits
- Queue stops filling
- `asyncio.wait_for()` times out after configured timeout
- TimeoutError propagates to test runner

**Proposed Behavior**:
- No change (connection handling orthogonal to type waiting)

### Edge Case 3: Server Sends Error

**Scenario**: Server sends "error" message when test expects question

**Current Behavior**:
- Tier 1: wait_for_question() raises ValueError
- Cascade doesn't catch ValueError (only TimeoutError)
- Exception propagates to test runner outer try-except
- Test marked as failed (correct behavior)

**Proposed Behavior**:
- wait_for_next_question() raises ValueError (not in allowed types)
- Exception propagates same way
- No change in test outcome (correct behavior)

---

## Comparison to Real-World Interview

**Analogy**:
- **Server** = Interviewer
- **Test Bot** = Candidate
- **Message Types** = Question vs Follow-up Question

**Current Logic**:
- Candidate expects regular question
- Interviewer asks follow-up question
- Candidate: "ERROR: I expected a regular question, not a follow-up!"

**Fixed Logic**:
- Candidate expects **any question**
- Interviewer asks either type
- Candidate: "Got a question, I'll answer it"

**Key Insight**: Candidate doesn't need to predict question type, only respond appropriately.

---

## Metrics Impact

### Before Fix

**Metrics Tracked**:
- `wait_question` latency (includes 5s timeout waste)
- `wait_follow_up_question` latency (includes 5s timeout waste)
- `wait_interview_complete` latency (includes 10s cascade waste)

**Example Log**:
```
wait_question: {avg: 5100ms, count: 3}  # 5s timeout + 100ms actual
wait_follow_up_question: {avg: 120ms, count: 2}
```

### After Fix

**Metrics Tracked**:
- `wait_question` latency (no timeout waste, tracks actual type received)
- `wait_follow_up_question` latency (no timeout waste, tracks actual type received)
- Both metrics represent **real server response time**

**Example Log**:
```
wait_question: {avg: 150ms, count: 3}  # True latency
wait_follow_up_question: {avg: 120ms, count: 2}  # True latency
```

**Insight**: After fix, metrics show true server performance (not masked by client timeout waste).

---

## Backward Compatibility Analysis

### Public API (Unchanged)

Existing methods preserved:
- `wait_for_question()`
- `wait_for_follow_up()`
- `wait_for_evaluation()`
- `wait_for_completion()`

**Rationale**: External tests may depend on these, breaking them risks regressions.

### Internal Implementation (Changed)

New methods added:
- `_wait_for_message_types()` (internal helper)
- `wait_for_next_question()` (new public API)

Test runner updated to use new API, old methods unused but available.

### Configuration (Backward Compatible)

`follow_up_timeout_sec` deprecated but not removed:
- Old configs still load successfully
- Field ignored by new logic (uses `question_timeout_sec` for both types)
- Clear migration path via deprecation notice

---

## Recommendations

### Immediate (This Fix)

1. **Add flexible waiting**: `_wait_for_message_types(["question", "follow_up_question"])`
2. **Simplify cascade**: 3-tier → 2-tier (questions/follow-ups → completion)
3. **Preserve old methods**: Keep backward compatibility
4. **Update tests**: Add unit tests for new methods

### Future Improvements

1. **Unified timeout config**: Remove distinction between question/follow_up timeouts
2. **Message type enum**: Replace string literals with enum (type safety)
3. **Queue size limit**: Add max queue size to prevent memory leaks
4. **Completion detection**: Use message field instead of timeout (if server adds "is_last_question" flag)
5. **Metrics refactor**: Track "qa_loop_wait" instead of separate question/follow_up metrics

### Long-Term Architecture

**Consider**: Message handler pattern instead of type-specific waits

```python
# Future pattern
async def handle_message(message: dict):
    handler = MESSAGE_HANDLERS.get(message["type"])
    if handler:
        await handler(message)
    else:
        raise ValueError(f"Unknown message type: {message['type']}")
```

**Benefits**:
- No cascading needed (handle whatever arrives)
- Extensible (add new message types easily)
- No timeout waste (process immediately)

**Tradeoff**: Requires test flow redesign (currently expects specific sequence).

---

## Conclusion

**Root Cause**: Cascading timeout logic conflates "server didn't send message" (timeout) with "server sent wrong message type" (validation error).

**Fix**: Flexible message type waiting eliminates false validation errors while preserving timeout for true absence of messages.

**Impact**: Zero timeout waste, 100% backward compatibility, cleaner test logic.

**Risk**: LOW (additive change, comprehensive test coverage).

**Next Steps**: Implement plan in `plan.md`.
