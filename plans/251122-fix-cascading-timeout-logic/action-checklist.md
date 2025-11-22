# Action Checklist: Fix Cascading Timeout Logic

**Date**: 2025-11-22
**Developer**: [Your Name]
**Estimated Time**: 2 hours

## Pre-Implementation

- [ ] Read full plan (`plan.md`)
- [ ] Review current code in `tests/bot/test_runner.py` (lines 400-421)
- [ ] Review current code in `tests/bot/test_bot_client.py` (lines 347-351)
- [ ] Ensure development environment ready
- [ ] Create feature branch: `git checkout -b fix/cascading-timeout-logic`

## Phase 1: Test Bot Client (30 min)

### Add New Methods

- [ ] Open `tests/bot/test_bot_client.py`
- [ ] Add `_wait_for_message_types()` after line 363
  - [ ] Copy implementation from plan
  - [ ] Add proper type hints
  - [ ] Add docstring
  - [ ] Add logging statements
- [ ] Add `wait_for_next_question()` after line 220
  - [ ] Copy implementation from plan
  - [ ] Handle state updates for both types
  - [ ] Add metrics tracking
  - [ ] Add logging statements
- [ ] Run mypy: `mypy tests/bot/test_bot_client.py`
- [ ] Fix any type errors

## Phase 2: Test Runner (20 min)

### Replace Cascade Logic

- [ ] Open `tests/bot/test_runner.py`
- [ ] Locate lines 395-421 (cascading try-except blocks)
- [ ] Delete old cascade code
- [ ] Insert new 2-tier cascade from plan
- [ ] Update context storage logic (questions vs follow_ups)
- [ ] Add comment explaining change
- [ ] Run ruff: `ruff check tests/bot/test_runner.py`
- [ ] Fix any linting issues

## Phase 3: Configuration (5 min, OPTIONAL)

- [ ] Open `tests/bot/config.py`
- [ ] Locate `follow_up_timeout_sec` field (lines 102-105)
- [ ] Update description to include "[DEPRECATED]"
- [ ] Save file

## Testing (45 min)

### Unit Tests

- [ ] Create `tests/bot/test_test_bot_client.py`
- [ ] Add `test_wait_for_message_types_success()`
- [ ] Add `test_wait_for_message_types_invalid_type()`
- [ ] Add `test_wait_for_next_question_handles_both_types()`
- [ ] Run unit tests: `pytest tests/bot/test_test_bot_client.py -v`
- [ ] Verify all 3 tests pass

### Integration Tests

- [ ] Run mock tests: `pytest tests/bot/run_tests.py -k mock -v`
- [ ] Verify 0 timeout-related failures
- [ ] Check logs for cascading warnings (should be none)

### Manual Verification

- [ ] Check test report: `cat reports/test_report_*.json`
  - [ ] Verify `avg_duration_sec` reduced
  - [ ] Verify no timeout errors
- [ ] Review logs: `tail -100 reports/test_*.log`
  - [ ] Look for "Received question" and "Received follow-up" logs
  - [ ] Verify no "Timeout waiting for 'question'" → "Timeout waiting for 'follow_up'" cascade

## Documentation (10 min)

- [ ] Add entry to `CHANGELOG.md`:
  ```markdown
  ### Fixed
  - Eliminated cascading timeout logic in test bot (question → follow_up → completion)
  - Test bot now accepts both "question" and "follow_up_question" in QA loop
  - Reduced max timeout from 15s to 10s per cascade
  ```
- [ ] Add comment in `test_runner.py` explaining change:
  ```python
  # NOTE: wait_for_next_question() accepts both "question" and "follow_up_question"
  # to avoid cascading timeouts when server sends either type based on interview state
  ```

## Code Quality (10 min)

- [ ] Run mypy on all changed files: `mypy tests/bot/`
- [ ] Run ruff: `ruff check tests/bot/`
- [ ] Run black: `black tests/bot/`
- [ ] Fix any errors/warnings

## Final Validation (10 min)

- [ ] Run full test suite: `pytest tests/bot/run_tests.py`
- [ ] Verify 100% pass rate
- [ ] Check test coverage: `pytest --cov=tests.bot tests/bot/`
- [ ] Review diff: `git diff`

## Pre-Commit (5 min)

- [ ] Stage changes: `git add tests/bot/`
- [ ] Stage CHANGELOG: `git add CHANGELOG.md`
- [ ] Run pre-commit hooks (if configured)
- [ ] Commit with message:
  ```bash
  git commit -m "fix: eliminate cascading timeout logic in test bot

  - Add flexible message type waiting (_wait_for_message_types)
  - Add wait_for_next_question() accepting both question types
  - Replace 3-tier cascade (question → follow_up → completion) with 2-tier
  - Reduce max timeout from 15s to 10s per cascade
  - Add unit tests for new methods
  - Maintain backward compatibility with existing tests

  Fixes: Cascading timeout issue breaking multi-question scenarios
  "
  ```

## Post-Implementation

- [ ] Push branch: `git push origin fix/cascading-timeout-logic`
- [ ] Create PR (if using GitHub)
- [ ] Request code review
- [ ] Monitor CI/CD pipeline
- [ ] Merge to main after approval

## Rollback (If Needed)

- [ ] Revert commits: `git revert HEAD`
- [ ] Or checkout main: `git checkout main`
- [ ] Run tests: `pytest tests/bot/run_tests.py`
- [ ] Document failure reason in `rollback-notes.md`

## Notes

**Issues Encountered**:
- [Add any issues here during implementation]

**Deviations from Plan**:
- [Add any changes to plan here]

**Performance Improvements Observed**:
- [Add metrics comparison here after testing]

**Completion Time**:
- Start: [HH:MM]
- End: [HH:MM]
- Total: [X hours]
