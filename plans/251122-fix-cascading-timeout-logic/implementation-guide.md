# Quick Implementation Guide

**For developers who want to implement the fix immediately**

---

## TL;DR

Replace cascading timeout logic with flexible message type waiting. Add 2 methods, update 1 function, run tests.

**Time**: 2 hours | **Risk**: LOW | **Impact**: HIGH

---

## Step-by-Step Implementation

### Step 1: Add Flexible Wait Helper (10 min)

**File**: `tests/bot/test_bot_client.py`
**Location**: After line 363 (after `_wait_for_message_type()`)

```python
async def _wait_for_message_types(
    self,
    msg_types: list[str],
    timeout: float,
) -> tuple[str, dict[str, Any]]:
    """Wait for any of multiple message types from queue.

    Args:
        msg_types: List of acceptable message types
        timeout: Timeout in seconds

    Returns:
        Tuple of (actual_type, message_dict)

    Raises:
        TimeoutError: If timeout exceeded
        ValueError: If message type not in allowed list
    """
    start = datetime.utcnow()

    try:
        # Wait for message from queue
        message = await asyncio.wait_for(
            self._message_queue.get(), timeout=timeout
        )

        # Verify type is in allowed list
        actual_type = message.get("type")
        if actual_type not in msg_types:
            raise ValueError(
                f"Expected message type in {msg_types}, "
                f"got '{actual_type}'"
            )

        # Track latency
        latency = (datetime.utcnow() - start).total_seconds() * 1000
        self._track_metric("latency", f"wait_{actual_type}", latency)

        return actual_type, message

    except asyncio.TimeoutError:
        raise TimeoutError(
            f"Timeout waiting for message types {msg_types} "
            f"(waited {timeout}s)"
        )
```

### Step 2: Add Flexible Question Wait (15 min)

**File**: `tests/bot/test_bot_client.py`
**Location**: After line 220 (after `wait_for_question()`)

```python
async def wait_for_next_question(
    self,
    timeout: float | None = None,
) -> dict[str, Any]:
    """Wait for next question (either regular or follow-up).

    Accepts both "question" and "follow_up_question" message types
    since they serve the same purpose in the QA loop.

    Args:
        timeout: Timeout in seconds (default: self.timeout)

    Returns:
        Question message dict (with type, question_id, text fields)

    Raises:
        TimeoutError: If timeout exceeded
        ValueError: If unexpected message type received
    """
    timeout = timeout or self.timeout
    msg_type, message = await self._wait_for_message_types(
        ["question", "follow_up_question"],
        timeout
    )

    # Update state based on actual type
    self.current_question_id = UUID(message["question_id"])
    self.current_question_text = message["text"]

    if msg_type == "question":
        self.current_status = "QUESTIONING"
        self.questions_received += 1
        self._track_state("QUESTIONING")
        logger.info(
            f"Received question #{message['index']}/{message['total']}: "
            f"{message['text'][:80]}..."
        )
    else:  # follow_up_question
        self.current_status = "FOLLOW_UP"
        self.follow_ups_received += 1
        self._track_state("FOLLOW_UP")
        logger.info(
            f"Received follow-up #{message['order_in_sequence']}: "
            f"{message['text'][:80]}..."
        )

    return message
```

### Step 3: Update Test Runner (15 min)

**File**: `tests/bot/test_runner.py`
**Location**: Lines 395-424

**DELETE this code**:
```python
try:
    # Wait for question or follow-up
    message = None
    message_type = None

    try:
        message = await bot.wait_for_question(
            timeout=self.config.timeouts.question_timeout_sec
        )
        message_type = "question"
    except TimeoutError:
        try:
            message = await bot.wait_for_follow_up(
                timeout=self.config.timeouts.follow_up_timeout_sec
            )
            message_type = "follow_up"
        except TimeoutError:
            try:
                completion = await bot.wait_for_completion(
                    timeout=self.config.timeouts.completion_timeout_sec
                )
                context["summary"] = completion
                logger.info("Interview completed")
                break
            except TimeoutError:
                logger.warning(f"No message after {i} iterations")
                break

    if not message:
        break

    # Store question/follow-up
    if message_type == "question":
        context["questions"].append(message)
    else:
        context["follow_ups"].append(message)
```

**REPLACE with**:
```python
try:
    # Try to wait for next question (question or follow_up)
    # NOTE: wait_for_next_question() accepts both "question" and "follow_up_question"
    # to avoid cascading timeouts when server sends either type based on interview state
    try:
        message = await bot.wait_for_next_question(
            timeout=self.config.timeouts.question_timeout_sec
        )

        # Store in appropriate list based on actual type
        if message["type"] == "question":
            context["questions"].append(message)
        else:  # follow_up_question
            context["follow_ups"].append(message)

    except TimeoutError:
        # No more questions, check for completion
        try:
            completion = await bot.wait_for_completion(
                timeout=self.config.timeouts.completion_timeout_sec
            )
            context["summary"] = completion
            logger.info("Interview completed")
            break
        except TimeoutError:
            logger.warning(f"No message after {i} iterations")
            break
```

### Step 4: Run Tests (10 min)

```bash
# Run type checking
mypy tests/bot/

# Run linting
ruff check tests/bot/

# Run tests
pytest tests/bot/run_tests.py -v

# Check report
cat reports/test_report_*.json
```

### Step 5: Verify Fix (5 min)

Check logs for:
- ✓ No cascading timeout warnings
- ✓ Both "Received question" and "Received follow-up" logs present
- ✓ No ValueError about unexpected message types

---

## Quick Validation Commands

```bash
# Type check
mypy tests/bot/test_bot_client.py tests/bot/test_runner.py

# Lint
ruff check tests/bot/

# Format
black tests/bot/

# Test
pytest tests/bot/run_tests.py

# Check results
jq '.scenarios[] | select(.status=="failed")' reports/test_report_*.json
```

---

## Expected Changes Summary

### Files Modified
1. `tests/bot/test_bot_client.py` (+70 lines)
2. `tests/bot/test_runner.py` (-25 lines, +20 lines)

### Methods Added
1. `_wait_for_message_types()` - Internal helper
2. `wait_for_next_question()` - Public API

### Methods Unchanged
- `wait_for_question()` - Preserved for backward compat
- `wait_for_follow_up()` - Preserved for backward compat
- `wait_for_evaluation()` - No changes needed
- `wait_for_completion()` - No changes needed

### Behavior Changes
- **Before**: Cascade through 3 message types (15s max)
- **After**: Try questions (both types), then completion (10s max)
- **Impact**: Faster tests, no false failures

---

## Rollback Command

If issues arise:

```bash
# Revert changes
git checkout HEAD -- tests/bot/test_bot_client.py tests/bot/test_runner.py

# Verify rollback
pytest tests/bot/run_tests.py
```

---

## Common Issues

### Issue 1: Import Error

**Symptom**: `NameError: name 'asyncio' is not defined`

**Fix**: Check imports at top of file (asyncio should already be imported)

### Issue 2: Type Errors

**Symptom**: `mypy` reports type mismatches

**Fix**: Ensure `tuple[str, dict[str, Any]]` return type uses `tuple` (not `Tuple`)

### Issue 3: Linting Errors

**Symptom**: `ruff` reports line too long

**Fix**: Break long lines at 88 characters (black default)

### Issue 4: Tests Still Failing

**Symptom**: Tests fail with timeout errors

**Fix**: Check timeout config in `tests/bot/config.py` - ensure timeouts >= 5s

---

## Success Criteria

- [ ] No ValueError about unexpected message types
- [ ] Tests complete in < 30s per scenario (vs 45s before)
- [ ] All assertions pass
- [ ] Logs show both "question" and "follow_up_question" processed
- [ ] Metrics show realistic latencies (< 1s, not 5s timeouts)

---

## Next Steps After Implementation

1. Run full test suite
2. Review test report JSON
3. Commit changes
4. Create PR
5. Monitor CI/CD

---

## Questions?

See full plan: `plan.md`
See findings: `findings-summary.md`
See checklist: `action-checklist.md`
