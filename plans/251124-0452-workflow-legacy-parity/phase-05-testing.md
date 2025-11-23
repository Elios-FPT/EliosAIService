# Phase 5: Testing & Validation

**Phase ID:** phase-05-testing
**Parent Plan:** 251124-0452-workflow-legacy-parity
**Priority:** CRITICAL
**Estimated Effort:** 4-5 hours
**Owner:** TBD
**Status:** Not Started
**Depends On:** All previous phases (1-4)

## Overview

Comprehensive parity testing and validation before production rollout:
- Parallel test suite comparing legacy vs workflow outputs
- Load testing with checkpointing
- Feature flag rollout validation
- Production readiness sign-off

## Testing Objectives

1. **Behavioral Parity:** Workflow produces identical outputs to legacy
2. **Performance:** Workflow meets latency/throughput requirements
3. **Reliability:** Checkpoint resume works under load
4. **Monitoring:** All metrics captured correctly
5. **Rollout Readiness:** Feature flag controls verified

## Test Suite Structure

```
tests/
├── parity/                      # NEW: Parity tests
│   ├── __init__.py
│   ├── conftest.py             # Shared fixtures
│   ├── test_evaluation_parity.py
│   ├── test_followup_parity.py
│   ├── test_message_parity.py
│   ├── test_gap_parity.py
│   └── test_completion_parity.py
├── load/                        # NEW: Load tests
│   ├── __init__.py
│   ├── test_concurrent_interviews.py
│   ├── test_checkpoint_performance.py
│   └── test_tts_cache.py
└── rollout/                     # NEW: Rollout tests
    ├── __init__.py
    ├── test_feature_flag.py
    └── test_gradual_rollout.py
```

## Implementation Tasks

### Task 5.1: Parity Test Suite (2 hours)

**File:** `tests/parity/test_evaluation_parity.py`

```python
"""Evaluation parity tests between legacy and workflow paths."""
import pytest
from uuid import uuid4


class TestEvaluationParity:
    """Compare evaluation outputs between legacy and workflow."""

    @pytest.fixture
    async def interview_fixture(self):
        """Create test interview with questions."""
        interview_id = await create_test_interview(
            questions=[
                "Explain async/await in Python",
                "What is the GIL?",
                "Describe decorator pattern",
            ]
        )
        return interview_id

    async def test_evaluation_scores_match(self, interview_fixture):
        """Test evaluation scores match within tolerance."""
        interview_id = interview_fixture
        answer_text = "Async allows concurrent execution using coroutines"

        # Run legacy path
        legacy_eval = await run_legacy_evaluation(interview_id, answer_text)

        # Run workflow path
        workflow_eval = await run_workflow_evaluation(interview_id, answer_text)

        # Assert scores within 2 points
        score_diff = abs(legacy_eval["score"] - workflow_eval["score"])
        assert score_diff < 2.0, (
            f"Score mismatch: legacy={legacy_eval['score']}, "
            f"workflow={workflow_eval['score']}"
        )

    async def test_evaluation_feedback_consistency(self, interview_fixture):
        """Test feedback fields present and similar."""
        interview_id = interview_fixture
        answer_text = "Brief answer with gaps"

        legacy_eval = await run_legacy_evaluation(interview_id, answer_text)
        workflow_eval = await run_workflow_evaluation(interview_id, answer_text)

        # Assert both have feedback
        assert legacy_eval["feedback"]
        assert workflow_eval["feedback"]

        # Assert both have strengths/weaknesses
        assert isinstance(legacy_eval["strengths"], list)
        assert isinstance(workflow_eval["strengths"], list)
        assert isinstance(legacy_eval["weaknesses"], list)
        assert isinstance(workflow_eval["weaknesses"], list)

    async def test_gap_detection_parity(self, interview_fixture):
        """Test gap detection produces same concepts."""
        interview_id = interview_fixture
        answer_text = "Async is concurrent"  # Missing key concepts

        legacy_eval = await run_legacy_evaluation(interview_id, answer_text)
        workflow_eval = await run_workflow_evaluation(interview_id, answer_text)

        # Extract gap concepts
        legacy_gaps = {gap["concept"] for gap in legacy_eval["gaps"]}
        workflow_gaps = {gap["concept"] for gap in workflow_eval["gaps"]}

        # Assert same gap concepts (order-independent)
        assert legacy_gaps == workflow_gaps, (
            f"Gap mismatch: legacy={legacy_gaps}, workflow={workflow_gaps}"
        )


# Similar files for:
# - test_followup_parity.py (follow-up generation decisions)
# - test_message_parity.py (WebSocket message formats)
# - test_gap_parity.py (gap accumulation across attempts)
# - test_completion_parity.py (interview summary generation)
```

**Fixtures:**

```python
# tests/parity/conftest.py

import pytest
from typing import Any


@pytest.fixture
async def legacy_runner():
    """Run interview through legacy session_orchestrator."""
    async def _run(interview_id: UUID, answers: list[str]) -> dict[str, Any]:
        # Create WebSocket mock
        ws_mock = create_websocket_mock()

        # Initialize session orchestrator
        orchestrator = InterviewSessionOrchestrator(
            interview_id=interview_id,
            websocket=ws_mock,
            container=get_container(),
        )

        # Start session
        await orchestrator.start_session()

        # Send answers
        messages = []
        for answer_text in answers:
            await orchestrator.handle_answer(answer_text)
            messages.extend(ws_mock.sent_messages)

        return {
            "messages": messages,
            "evaluations": extract_evaluations(messages),
            "followups": extract_followups(messages),
        }

    return _run


@pytest.fixture
async def workflow_runner():
    """Run interview through LangGraph workflow."""
    async def _run(interview_id: UUID, answers: list[str]) -> dict[str, Any]:
        workflow = create_workflow_instance()

        # Start session
        start_result = await workflow.start_session(
            interview_id=interview_id,
            candidate_id=uuid4(),
        )
        thread_id = start_result["thread_id"]

        # Send answers
        results = []
        for answer_text in answers:
            result = await workflow.process_answer(
                thread_id=thread_id,
                answer_text=answer_text,
            )
            results.append(result)

        return {
            "results": results,
            "evaluations": extract_evaluations_from_results(results),
            "followups": extract_followups_from_results(results),
        }

    return _run
```

---

### Task 5.2: Load Testing (1.5 hours)

**File:** `tests/load/test_concurrent_interviews.py`

```python
"""Load tests for concurrent workflow execution."""
import asyncio
import pytest
from datetime import datetime


async def test_50_concurrent_interviews():
    """Test 50 concurrent interviews with checkpointing."""
    num_interviews = 50
    workflow = create_workflow_instance()

    # Create interview IDs
    interview_ids = [uuid4() for _ in range(num_interviews)]

    # Start all sessions concurrently
    start_time = datetime.utcnow()

    sessions = await asyncio.gather(*[
        workflow.start_session(
            interview_id=iid,
            candidate_id=uuid4(),
        )
        for iid in interview_ids
    ])

    session_time = (datetime.utcnow() - start_time).total_seconds()

    # Process first answer for all interviews
    answer_time_start = datetime.utcnow()

    await asyncio.gather(*[
        workflow.process_answer(
            thread_id=session["thread_id"],
            answer_text="Test answer for load testing",
        )
        for session in sessions
    ])

    answer_time = (datetime.utcnow() - answer_time_start).total_seconds()

    # Assert performance
    assert session_time < 10.0, f"Session start too slow: {session_time}s"
    assert answer_time < 15.0, f"Answer processing too slow: {answer_time}s"

    # Assert checkpoint table size reasonable
    checkpoint_size = await get_checkpoint_table_size_mb()
    assert checkpoint_size < 50, f"Checkpoint table too large: {checkpoint_size}MB"


async def test_checkpoint_resume_under_load():
    """Test checkpoint resume works under concurrent load."""
    num_resumes = 20
    workflow = create_workflow_instance()

    # Create checkpoints
    thread_ids = []
    for _ in range(num_resumes):
        session = await workflow.start_session(
            interview_id=uuid4(),
            candidate_id=uuid4(),
        )
        thread_ids.append(session["thread_id"])

    # Simulate resume from checkpoints
    resume_results = await asyncio.gather(*[
        workflow.get_workflow_state(thread_id)
        for thread_id in thread_ids
    ])

    # Assert all resumes successful
    assert len(resume_results) == num_resumes
    assert all(result is not None for result in resume_results)
```

**File:** `tests/load/test_tts_cache.py`

```python
"""Load tests for TTS caching performance."""

async def test_tts_cache_hit_rate():
    """Test TTS cache improves performance for common questions."""
    workflow = create_workflow_instance()

    # Same question asked 10 times
    question_text = "Explain dependency injection"

    # First call (cache miss)
    start = datetime.utcnow()
    audio1 = await generate_tts_with_cache(question_text)
    first_time = (datetime.utcnow() - start).total_seconds()

    # Subsequent calls (cache hit)
    times = []
    for _ in range(9):
        start = datetime.utcnow()
        audio = await generate_tts_with_cache(question_text)
        times.append((datetime.utcnow() - start).total_seconds())

    avg_cached_time = sum(times) / len(times)

    # Assert cache improves performance
    assert avg_cached_time < first_time * 0.5, (
        f"Cache not effective: first={first_time}s, avg={avg_cached_time}s"
    )
```

---

### Task 5.3: Feature Flag Validation (1 hour)

**File:** `tests/rollout/test_feature_flag.py`

```python
"""Feature flag rollout validation tests."""

async def test_feature_flag_controls_path():
    """Test feature flag controls legacy vs workflow path."""
    # Flag OFF → Legacy path
    settings = get_settings()
    settings.use_langgraph_conversation_workflow = False

    handler = InterviewHandler(container=get_container())
    path = handler._get_execution_path()

    assert path == "legacy"

    # Flag ON → Workflow path
    settings.use_langgraph_conversation_workflow = True

    handler = InterviewHandler(container=get_container())
    path = handler._get_execution_path()

    assert path == "workflow"


async def test_gradual_rollout_percentage():
    """Test percentage-based rollout."""
    settings = get_settings()
    settings.workflow_rollout_percentage = 50  # 50% traffic

    # Run 100 interviews
    paths_used = []
    for _ in range(100):
        handler = InterviewHandler(container=get_container())
        path = handler._select_path_with_rollout()
        paths_used.append(path)

    # Assert ~50% use workflow
    workflow_pct = paths_used.count("workflow") / len(paths_used)
    assert 0.40 <= workflow_pct <= 0.60, f"Rollout percentage off: {workflow_pct}"


async def test_sticky_sessions():
    """Test interview always uses same path (no mid-interview switching)."""
    interview_id = uuid4()

    # First call
    handler1 = InterviewHandler(container=get_container())
    path1 = handler1._get_path_for_interview(interview_id)

    # Second call (should be same path)
    handler2 = InterviewHandler(container=get_container())
    path2 = handler2._get_path_for_interview(interview_id)

    assert path1 == path2, "Path switched mid-interview"
```

---

### Task 5.4: Monitoring Validation (30 min)

**File:** `tests/monitoring/test_metrics.py`

```python
"""Monitoring and metrics validation."""

async def test_evaluation_delivery_metric():
    """Test evaluation delivery rate metric emitted."""
    workflow = create_workflow_instance()
    metrics_collector = get_metrics_collector()

    # Run interview
    session = await workflow.start_session(uuid4(), uuid4())
    await workflow.process_answer(session["thread_id"], "Test answer")

    # Assert metric emitted
    metric = metrics_collector.get_counter("evaluation.delivered")
    assert metric.value == 1


async def test_gap_validation_mismatch_metric():
    """Test gap mismatch metric emitted on validation failure."""
    workflow = create_workflow_instance()
    metrics_collector = get_metrics_collector()

    # Create mismatch scenario
    state = create_state_with_gap_mismatch()
    await workflow._validate_gaps_node(state)

    # Assert metric emitted
    metric = metrics_collector.get_counter("gap_validation.mismatch")
    assert metric.value > 0
```

---

## Test Execution Plan

### Day 4 PM Schedule

| Time | Activity | Tests Run |
|------|----------|-----------|
| 13:00-14:00 | Write parity tests | 15 tests |
| 14:00-15:00 | Write load tests | 5 tests |
| 15:00-15:30 | Write feature flag tests | 3 tests |
| 15:30-16:00 | Write monitoring tests | 2 tests |
| 16:00-17:00 | Run full suite, fix failures | All 25 tests |

### Test Categories

| Category | Tests | Pass Rate Target |
|----------|-------|------------------|
| Parity | 15 | 100% |
| Load | 5 | 100% |
| Feature Flag | 3 | 100% |
| Monitoring | 2 | 100% |
| **TOTAL** | **25** | **100%** |

## Acceptance Criteria

- [ ] **AC1:** All 15 parity tests passing (100% pass rate)
- [ ] **AC2:** Evaluation scores match within +/- 2 points
- [ ] **AC3:** Gap concepts match exactly (order-independent)
- [ ] **AC4:** Message formats identical between paths
- [ ] **AC5:** Load test passes (50 concurrent interviews < 15s)
- [ ] **AC6:** Checkpoint table < 50MB after load test
- [ ] **AC7:** Feature flag controls path selection
- [ ] **AC8:** Sticky sessions prevent mid-interview switching
- [ ] **AC9:** All monitoring metrics emitted correctly
- [ ] **AC10:** Zero regressions in existing test suite (500+ tests)

## Production Readiness Checklist

### Code Quality
- [ ] All phases (1-5) implemented and reviewed
- [ ] Code coverage > 90% for new code
- [ ] No critical/high severity linter warnings
- [ ] All TODOs resolved or tracked

### Testing
- [ ] 25/25 parity tests passing
- [ ] Load test passes under 50 concurrent users
- [ ] Manual QA complete (8 test scenarios)
- [ ] No regressions in existing tests

### Documentation
- [ ] API docs updated (WebSocket message schemas)
- [ ] System architecture doc updated
- [ ] Deployment guide updated
- [ ] Rollout plan documented

### Monitoring
- [ ] Evaluation delivery rate metric live
- [ ] TTS generation success metric live
- [ ] Gap validation mismatch alert configured
- [ ] Feature flag rollout dashboard created

### Rollout Plan
- [ ] Feature flag implemented and tested
- [ ] Canary rollout plan approved (5% → 25% → 50% → 100%)
- [ ] Rollback procedure documented and tested
- [ ] On-call team briefed

## Rollout Stages

### Stage 1: Canary (5% - Week 1)
- Enable workflow for 5% of new interviews
- Monitor metrics hourly for first 24h
- **Rollback criteria:** Error rate > 1% OR latency p95 > 2s

### Stage 2: Gradual (25% - Week 2)
- Increase to 25% if Stage 1 stable
- Daily metric review
- **Rollback criteria:** Evaluation delivery < 99% OR TTS failures > 0.5%

### Stage 3: Majority (50% - Week 3)
- Increase to 50%
- Compare legacy vs workflow metrics side-by-side
- **Go/No-Go decision point**

### Stage 4: Full Rollout (100% - Week 4)
- Complete migration to workflow path
- Freeze for 72h observation
- Decommission legacy path (Month 2)

## Success Metrics (Production)

| Metric | Target | Alert Threshold |
|--------|--------|-----------------|
| Evaluation Delivery Rate | 100% | < 99% |
| TTS Generation Success | > 99.5% | < 99% |
| Follow-Up Decision Accuracy | +/- 2% of legacy | > 5% diff |
| Gap Validation Mismatch | < 5/hour | > 10/hour |
| Checkpoint Resume Success | > 99% | < 98% |
| P95 Latency | < 1.5s | > 2.0s |

## Estimated Timeline

| Task | Effort | Completion |
|------|--------|------------|
| 5.1: Parity Test Suite | 2h | 40% |
| 5.2: Load Testing | 1.5h | 30% |
| 5.3: Feature Flag Tests | 1h | 20% |
| 5.4: Monitoring Tests | 30min | 10% |

**Total:** 5 hours (Day 4 PM)

## Deliverables

1. **Test Suite:** 25 new tests covering parity, load, flags, monitoring
2. **Test Report:** Summary of results, pass rates, performance data
3. **Rollout Checklist:** Production readiness sign-off document
4. **Metrics Dashboard:** Real-time comparison of legacy vs workflow
5. **Runbook:** On-call guide for workflow issues

## Final Sign-Off

Before production rollout, obtain sign-off from:
- [ ] Engineering Lead (code quality, tests passing)
- [ ] QA Lead (manual testing complete)
- [ ] Product Manager (feature complete, UX validated)
- [ ] DevOps Lead (monitoring, rollback plan ready)
- [ ] On-Call Team (runbook reviewed, alerts configured)

---

**Once all phases complete and tests passing → READY FOR PRODUCTION ROLLOUT**
