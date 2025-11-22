# Fix Cascading Timeout Logic in Test Bot

**Status**: READY_FOR_IMPLEMENTATION
**Date**: 2025-11-22
**Priority**: HIGH

## Quick Summary

Test bot uses cascading timeout logic that wastes 15s and breaks on strict type validation. Fix by adding flexible message type waiting that accepts both "question" and "follow_up_question".

## Problem

```python
# Current broken cascade
try:
    message = await wait_for_question(timeout=5)  # Strict "question" only
except TimeoutError:
    try:
        message = await wait_for_follow_up(timeout=5)  # Strict "follow_up" only
    except TimeoutError:
        try:
            completion = await wait_for_completion(timeout=5)
        except TimeoutError:
            break
```

**Issues**:
- If server sends "question" when test expects "follow_up_question": **ValueError**
- Wastes 15 seconds (5+5+5) per failed cascade
- Breaks all multi-question scenarios

## Solution

Add flexible waiting:

```python
# New flexible approach
try:
    message = await wait_for_next_question(timeout=5)  # Accepts BOTH types
except TimeoutError:
    try:
        completion = await wait_for_completion(timeout=5)
    except TimeoutError:
        break
```

**Benefits**:
- Zero false failures on valid messages
- Reduces timeout from 15s → 10s max
- Maintains backward compatibility

## Files to Change

1. `tests/bot/test_bot_client.py` - Add 2 new methods
2. `tests/bot/test_runner.py` - Replace cascade logic (lines 395-421)
3. `tests/bot/config.py` - Deprecate old timeout field (optional)

## Implementation Time

**Estimated**: 2 hours (includes testing)

## Risk Level

**LOW** - Additive change, preserves existing methods

## Next Steps

1. Read full plan: `plan.md`
2. Implement Phase 1 (test_bot_client.py)
3. Implement Phase 2 (test_runner.py)
4. Run tests: `pytest tests/bot/run_tests.py`
5. Verify in reports: `reports/test_report_*.json`

## References

- Full plan: `plan.md`
- Scout report: `../scout-async-db/scout-report.txt`
- Code review: `reports/251122-code-review-timeout-fix.md` (TODO: create after implementation)
