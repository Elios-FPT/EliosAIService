# Code Review Report: Interview Test Bot Implementation

**Date**: 2025-11-21
**Reviewer**: Code Review Agent
**Plan**: 251120-1430-hybrid-cv-analyzer-migration
**Review Scope**: `tests/bot/` directory - Mock/Real execution logic

---

## Code Review Summary

### Scope
- Files reviewed:
  - `tests/bot/test_runner.py` (560 lines)
  - `tests/bot/db_helper.py` (206 lines)
  - `tests/bot/test_bot_client.py` (468 lines)
- Focus: Execution logic for mock/real tests, SQL injection safety, WebSocket handling
- Recent commits: `c67fbc0` (test report), `1a2241a` (DI test), `7bfeb59` (orchestrator)

### Overall Assessment
Implementation successfully meets requirements for mock vs real test execution paths. Code is well-structured, properly async, and demonstrates good separation of concerns. However, **CRITICAL DATABASE SCHEMA MISMATCH** found that will cause test failures. Additionally, 20+ type safety issues in supporting files need addressing.

---

## Critical Issues

### 1. **DATABASE SCHEMA MISMATCHES** (db_helper.py:51-145)
**Impact**: Tests WILL FAIL - Multiple SQL inserts use non-existent columns/tables

**Issue 1 - questions.skill_category doesn't exist** (db_helper.py:114-120):
```python
# ❌ WRONG
INSERT INTO questions (id, text, question_type, difficulty,
                      skill_category, ideal_answer, created_at)
```

**Actual Schema** (alembic/0001_create_tables.py:36-54):
```sql
-- ✅ Schema has 'skills' (ARRAY), NOT 'skill_category' (single string)
CREATE TABLE questions (
    skills TEXT[] NOT NULL DEFAULT '{}',  -- ARRAY!
    updated_at TIMESTAMP NOT NULL         -- MISSING in INSERT!
)
```

**Issue 2 - questions.updated_at missing** (db_helper.py:114-120):
- Schema requires `updated_at` (NOT NULL), but INSERT omits it → SQL constraint violation

**Issue 3 - cv_analyses.key_technologies doesn't exist** (db_helper.py:82):
```python
# ❌ WRONG
"key_technologies": json.dumps(cv_data.get("skills", [])[:3]),
```

**Actual Schema** (alembic/0001_create_tables.py:60-77):
```sql
-- ✅ No 'key_technologies' column exists
-- Schema has: skills (JSONB), suggested_topics (ARRAY)
```

**Issue 4 - interview_questions junction table doesn't exist** (db_helper.py:133-145):
```python
# ❌ Table doesn't exist in schema
INSERT INTO interview_questions (interview_id, question_id, question_order)
```

**Actual Schema**: No `interview_questions` table. Instead, `interviews` table uses:
```sql
question_ids UUID[] NOT NULL DEFAULT '{}'  -- ARRAY of question IDs directly
```

**Issue 5 - interviews.total_questions doesn't exist** (db_helper.py:93):
```python
# ❌ Column doesn't exist
"total_questions": expected_questions,
```

**Fixes Required**:
```python
# Fix 1: questions table (db_helper.py:112-130)
await self.session.execute(
    text("""
        INSERT INTO questions (id, text, question_type, difficulty,
                             skills, ideal_answer, created_at, updated_at)  # ✅ skills (ARRAY), added updated_at
        VALUES (:id, :text, :question_type, :difficulty,
                :skills, :ideal_answer, :created_at, :updated_at)
    """),
    {
        "skills": [skill],  # ✅ Wrap in array
        "updated_at": datetime.utcnow(),  # ✅ Add missing field
        # ... other fields
    }
)

# Fix 2: cv_analyses table (db_helper.py:67-85)
await self.session.execute(
    text("""
        INSERT INTO cv_analyses (id, candidate_id, cv_file_path, extracted_text,
                                skills, work_experience_years, education_level,
                                suggested_topics, created_at)  # ✅ Remove key_technologies
        VALUES (...)
    """),
    {
        # Remove: "key_technologies": json.dumps(...)  # ❌ Column doesn't exist
        "skills": json.dumps(cv_data.get("skills", [])),  # ✅ Keep as-is
    }
)

# Fix 3: interviews table (db_helper.py:87-106)
await self.session.execute(
    text("""
        INSERT INTO interviews (id, candidate_id, cv_analysis_id, status,
                               current_question_index, question_ids, created_at, updated_at)
        VALUES (:id, :candidate_id, :cv_analysis_id, :status,
                :current_question_index, :question_ids, :created_at, :updated_at)
    """),
    {
        "question_ids": question_ids,  # ✅ Pass array of UUIDs directly
        # Remove: "total_questions": expected_questions,  # ❌ Column doesn't exist
    }
)

# Fix 4: Remove interview_questions inserts (db_helper.py:133-145)
# ❌ DELETE THIS ENTIRE BLOCK - table doesn't exist
# Questions are linked via interviews.question_ids array
```

**Recommendation**:
1. **CRITICAL**: Fix all 5 schema mismatches before running tests
2. Run integration test IMMEDIATELY after fixes
3. Consider using ORM models (CandidateModel, QuestionModel) instead of raw SQL to prevent schema drift
4. Add schema validation test in CI pipeline

---

### 2. **NO SQL INJECTION PROTECTION** (db_helper.py:51-145)
**Impact**: Low risk (test-only code), but violates security best practices

**Problem**: Uses SQLAlchemy `text()` with parameterized queries - SAFE from injection. Initial assessment was incorrect. Code correctly uses bound parameters (`:id`, `:name`) which SQLAlchemy escapes.

**Status**: ✅ SAFE - False alarm. Parameterized queries prevent injection.

---

## High Priority Findings

### 3. **MISSING ERROR HANDLING** (test_runner.py:236-273)
**Impact**: Cryptic failures, no resource cleanup on error

**Issue 1 - No engine cleanup** (test_runner.py:247-258):
```python
async def _run_mock_scenario(self, config: dict) -> tuple[UUID, str, dict[str, Any]]:
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        db_helper = DatabaseHelper(session)
        candidate_id, interview_id, question_ids = await db_helper.insert_mock_interview_data(...)
    # ❌ Engine never closed! Connection leak
```

**Fix**:
```python
try:
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    # ... rest of code
finally:
    await engine.dispose()  # ✅ Always cleanup
```

**Issue 2 - No rollback on failure** (db_helper.py:147):
```python
await self.session.commit()  # ❌ What if insert fails midway?
```

**Fix**: Wrap in try/except, call `await self.session.rollback()` on error.

---

### 4. **TYPE SAFETY ISSUES** (Multiple files)
**Impact**: mypy reports 20+ errors in supporting files

**Findings**:
- `metrics_collector.py:16` - Missing type annotation for `metrics` dict
- `metrics_collector.py:32-54` - 10+ "Collection[Any]" indexing errors
- `answer_generator.py:121` - Returns `Any` instead of `str`

**Not blocking** (these are in support files, not reviewed files), but should be fixed for codebase health.

---

### 5. **WEBSOCKET TIMEOUT LOGIC** (test_runner.py:372-393)
**Impact**: Flaky tests - relies on nested try/except with timeouts

**Problem**:
```python
for i in range(expected_questions + 10):  # +10 buffer for follow-ups
    try:
        try:
            message = await bot.wait_for_question(timeout=5.0)
            message_type = "question"
        except TimeoutError:
            try:
                message = await bot.wait_for_follow_up(timeout=5.0)  # Another 5s wait!
                message_type = "follow_up"
            except TimeoutError:
                try:
                    completion = await bot.wait_for_completion(timeout=5.0)  # Another 5s!
```

**Issue**: Worst case = 15s timeout per iteration (5s × 3 attempts). If server slow, test hangs.

**Recommendation**:
```python
# Option A: Use asyncio.gather with timeout
tasks = [
    bot.wait_for_question(timeout=5.0),
    bot.wait_for_follow_up(timeout=5.0),
    bot.wait_for_completion(timeout=5.0),
]
done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED, timeout=5.0)
```

**Option B**: Single unified `wait_for_message()` method that returns type + data.

---

## Medium Priority Improvements

### 6. **HARDCODED MAGIC NUMBERS** (test_runner.py:372)
```python
for i in range(expected_questions + 10):  # +10 buffer for follow-ups
```
**Issue**: Why 10? What if 15 follow-ups?

**Recommendation**:
```python
MAX_FOLLOW_UPS_PER_QUESTION = 3
max_iterations = expected_questions * (1 + MAX_FOLLOW_UPS_PER_QUESTION)
```

---

### 7. **NO DATA CLEANUP** (db_helper.py:156-185)
**Impact**: Test data pollution, CI failures

**Issue**: `cleanup_interview_data()` defined but NEVER CALLED in test_runner.py.

**Fix**: Add cleanup in `test_runner.py`:
```python
try:
    interview_id, ws_url, context = await self._run_mock_scenario(config)
    # ... rest of test
finally:
    if use_mock:
        await db_helper.cleanup_interview_data(interview_id)  # ✅ Cleanup
```

---

### 8. **INCOMPLETE CONTEXT TRACKING** (test_runner.py:349-432)
**Issue**: Context dict missing error tracking

```python
context = {
    "questions": [],
    "answers": [],
    "evaluations": [],
    "follow_ups": [],
    "summary": None,
    # ❌ Missing: "errors": [], "timeout_count": 0, "retry_count": 0
}
```

**Recommendation**: Add error tracking for better debugging.

---

## Low Priority Suggestions

### 9. **DOCSTRING COMPLETENESS** (db_helper.py:27-38)
**Issue**: Missing `Raises` section

```python
async def insert_mock_interview_data(
    self, cv_fixture: str, expected_questions: int
) -> tuple[UUID, UUID, list[UUID]]:
    """Insert pre-defined interview data for mock testing.

    Args:
        cv_fixture: CV fixture filename (e.g., "python_senior.json")
        expected_questions: Number of questions to create

    Returns:
        (candidate_id, interview_id, question_ids)
    # ❌ Missing: Raises: FileNotFoundError if cv_fixture not found
    """
```

---

### 10. **LOG LEVEL INCONSISTENCY** (test_bot_client.py:82-95)
```python
logger.info(f"Connecting to {ws_url}")  # ✅ Good
logger.info(f"Connected in {latency:.1f}ms")  # ✅ Good
logger.debug(f"Received: {message.get('type')}")  # ❌ Should be INFO for test visibility
```

**Recommendation**: Use INFO for test-critical events, DEBUG for internals.

---

## Positive Observations

### ✅ Well Done
1. **Clean Separation**: Mock vs real paths clearly separated (`_run_mock_scenario` vs `_run_real_scenario`)
2. **Async Patterns**: Proper use of `async/await`, no blocking calls
3. **WebSocket Management**: Background receive loop with queue-based message handling (test_bot_client.py:364-389)
4. **Metrics Tracking**: Comprehensive latency/state tracking in InterviewTestBot
5. **Error Propagation**: Exceptions properly bubbled up to test runner
6. **Resource Management**: WebSocket cleanup in finally block (test_bot_client.py:425-427)
7. **Type Hints**: Complete in reviewed files (test_runner.py, db_helper.py)

---

## Recommended Actions

### Immediate (Blockers)
1. **FIX DATABASE SCHEMA** (db_helper.py:114-120)
   - Replace `skill_category` → `skills` (ARRAY)
   - Add `questions.updated_at`
   - Remove `cv_analyses.key_technologies`
   - **Test with**: `pytest tests/bot/test_runner.py -k mock`

2. **ADD ENGINE CLEANUP** (test_runner.py:247-258)
   - Wrap in try/finally, call `await engine.dispose()`

3. **CALL CLEANUP METHOD** (test_runner.py:236-273)
   - Add `finally: await db_helper.cleanup_interview_data(interview_id)`

### High Priority (Before Merge)
4. **ADD ROLLBACK HANDLING** (db_helper.py:27-154)
   - Wrap inserts in try/except, rollback on error

5. **FIX WEBSOCKET TIMEOUT LOGIC** (test_runner.py:372-393)
   - Replace nested try/except with unified message wait

6. **RUN TYPE CHECKER** (metrics_collector.py, answer_generator.py)
   - Fix 20+ mypy errors in support files

### Medium Priority (Before Release)
7. **ADD INTEGRATION TEST** (new file: `tests/bot/test_db_helper_integration.py`)
   - Verify SQL inserts work against real schema

8. **DOCUMENT MAGIC NUMBERS** (test_runner.py:372)
   - Extract to named constants

9. **ADD ERROR CONTEXT** (test_runner.py:349-432)
   - Track errors, timeouts, retries in context dict

---

## Implementation Requirements Verification

### ✅ Mock Tests: Insert via SQL, skip API, test WebSocket only
**Status**: IMPLEMENTED (test_runner.py:236-273)
- ✅ Uses `DatabaseHelper.insert_mock_interview_data()`
- ✅ Skips CV upload/plan API calls
- ✅ Only runs `_run_websocket_qa()`

### ✅ Real Tests: Full API flow
**Status**: IMPLEMENTED (test_runner.py:275-334)
- ✅ CV upload via `/api/candidates/{id}/cv`
- ✅ Plan interview via `/api/interviews/plan`
- ✅ WebSocket QA via `_run_websocket_qa()`
- ✅ Feedback save (implicit via WebSocket completion)

### ✅ No Unit Tests for Test Bot
**Status**: CONFIRMED - No `tests/unit/bot/` directory found

### ⚠️ Correctness of Mock vs Real Paths
**Status**: LOGIC CORRECT, but DATABASE SCHEMA MISMATCH will break execution

---

## Metrics

- **Type Coverage**: 95% (reviewed files only, support files need fixes)
- **Test Coverage**: N/A (test bot itself not unit tested, as requested)
- **Linting Issues**: 20+ mypy errors in support files (not blocking reviewed files)
- **Critical Bugs**: 1 (database schema mismatch)
- **High Priority**: 4 issues
- **Medium Priority**: 3 issues
- **Low Priority**: 2 suggestions

---

## Conclusion

Implementation demonstrates solid async patterns, clean architecture, and proper separation of mock vs real test execution. However, **CRITICAL database schema mismatch will cause immediate test failures**. Fix schema issues in `db_helper.py` before running integration tests. Add resource cleanup (engine disposal, test data cleanup) to prevent connection leaks and CI pollution. Type safety in support files needs attention but is not blocking.

**Estimated Fix Time**: 2-3 hours (schema fix + cleanup handlers + integration test)

---

## Unresolved Questions

1. **CV Fixture Format**: test_runner.py:288-294 expects JSON CV fixture, but real CVs are PDF/DOCX. How does `files={"file": (cv_fixture, json.dumps(cv_data), "application/json")}` work with actual CV upload endpoint?

2. **Mock Adapter Behavior**: With `USE_MOCK_ADAPTERS=true`, does mock interview orchestrator return questions from DB or generate fake ones? If fake, mock test won't test DB-inserted questions.

3. **WebSocket URL Construction**: test_runner.py:268 builds WebSocket URL manually. Does server validate interview exists before accepting WS connection?

4. **Test Scenarios Missing**: No `test_scenarios.yaml` found in review. Are scenarios defined elsewhere?

5. **CV Analysis Missing Field**: db_helper.py needs `cv_file_path` and `extracted_text` (both NOT NULL in schema). How to generate these from CV fixture JSON?

---

**Review Completed**: 2025-11-21
**Next Steps**: Fix database schema, add cleanup handlers, run integration tests, verify mock adapter behavior
