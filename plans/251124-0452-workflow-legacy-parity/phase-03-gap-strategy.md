# Phase 3: Gap Accumulation Strategy Alignment

**Phase ID:** phase-03-gap-strategy
**Parent Plan:** 251124-0452-workflow-legacy-parity
**Priority:** MEDIUM
**Estimated Effort:** 4-5 hours
**Owner:** TBD
**Status:** Not Started
**Depends On:** Phase 1, Phase 2

## Overview

Align gap accumulation logic between legacy (DB-query based) and workflow (state-based) paths. Decide on single unified strategy with clear rationale, implement in workflow, verify gap tracking consistency across follow-up iterations.

## Issues Addressed

### Issue #6: Gap Accumulation Strategy Differences
**Source:** INCONSISTENCIES_ANALYSIS.md Line 234-298
**Impact:** MEDIUM - May generate duplicate follow-ups, inconsistent gap history
**Priority:** P2

## Current State Comparison

| Aspect | Legacy (DB-Query) | Workflow (State-Based) |
|--------|-------------------|------------------------|
| **Data Source** | Queries DB for all previous follow-up evaluations | Uses in-memory state `cumulative_gaps` array |
| **Scope** | All historical gaps from DB | Only gaps accumulated in current checkpoint session |
| **Persistence** | Always fresh from DB | Persisted in checkpoint, may lose if thread reset |
| **Performance** | 2-3 DB queries per decision | Zero DB queries (state lookup only) |
| **Reliability** | Comprehensive, never misses gaps | May miss gaps if checkpoint corrupted/reset |
| **Complexity** | Higher (async queries, loop through evaluations) | Lower (simple array append) |

## Architecture Decision: Hybrid Approach

**Decision:** Implement **hybrid strategy** combining strengths of both approaches.

### Strategy Details

**Primary:** State-based accumulation (fast path)
- Use `cumulative_gaps` from state during normal flow
- Append new gaps as detected in `_decide_followup_node()`
- Checkpoint persists full gap history

**Fallback:** DB-query validation (safety net)
- On workflow resume (checkpoint restore), validate gaps against DB
- Query all previous evaluations for parent question
- Merge DB gaps into state if missing
- Log gap mismatches for monitoring

### Rationale

**Advantages:**
- Fast: Zero DB queries during normal flow (state-based)
- Reliable: DB validation catches missed gaps after resume
- Best of both: Performance + correctness
- Future-proof: Works with multi-session interviews

**Trade-offs:**
- Slightly more complex implementation
- One-time DB query overhead on resume only
- Requires state reconciliation logic

## Implementation Tasks

### Task 3.1: Add Gap Validation on Resume (2.5 hours)

**File:** `src/application/workflows/interview_conversation_workflow.py`

**Changes:**

```python
# Add new node for gap validation (optional, runs only on resume)

async def _validate_gaps_node(self, state: ConversationState) -> dict[str, Any]:
    """Validate cumulative gaps against DB (resume safety check).

    Only runs when resuming from checkpoint. Ensures no gaps missed
    if state was corrupted or reset.

    Args:
        state: Current conversation state

    Returns:
        State updates: cumulative_gaps (validated/merged from DB)
    """
    try:
        # Skip if no parent question (new main question)
        parent_question_id_str = state.get("parent_question_id")
        if not parent_question_id_str:
            return {}  # No validation needed

        parent_question_id = UUID(parent_question_id_str)
        interview_id = UUID(state["interview_id"])

        # Query DB for all evaluations of this parent question
        parent_question_evaluations = (
            await self.evaluation_repo.get_by_parent_question(parent_question_id)
        )

        if not parent_question_evaluations:
            return {}  # No previous evaluations

        # Extract all unresolved gaps from DB
        db_gaps = set()
        for evaluation in parent_question_evaluations:
            for gap in evaluation.gaps:
                if not gap.resolved:
                    db_gaps.add(gap.concept)

        # Compare with state gaps
        state_gaps = set(state.get("cumulative_gaps", []))
        missing_gaps = db_gaps - state_gaps

        if missing_gaps:
            logger.warning(
                f"Gap mismatch detected: {len(missing_gaps)} gaps missing from state",
                extra={
                    "interview_id": state["interview_id"],
                    "missing_gaps": list(missing_gaps),
                },
            )

            # Merge missing gaps into state
            merged_gaps = list(state_gaps.union(db_gaps))
            return {"cumulative_gaps": merged_gaps}

        logger.debug("Gap validation passed: state matches DB")
        return {}

    except Exception as exc:
        logger.error(f"Gap validation failed: {exc}", exc_info=True)
        # Non-blocking: continue with state gaps if validation fails
        return {}


# Modify _build_graph() to add validation node (optional path)

def _build_graph(self) -> CompiledStateGraph[ConversationState]:
    """Build LangGraph StateGraph with gap validation."""
    graph = StateGraph(ConversationState)

    # ... existing nodes ...

    # NEW: Add gap validation node (runs only on resume)
    graph.add_node("validate_gaps", self._validate_gaps_node)

    # ... existing edges ...

    # Add validation edge: evaluate_answer → validate_gaps → update_memory
    # Only runs if state has parent_question_id (follow-up context)
    graph.add_conditional_edges(
        "evaluate_answer",
        lambda state: "validate_gaps" if state.get("parent_question_id") else "update_memory",
        {
            "validate_gaps": "validate_gaps",
            "update_memory": "update_memory",
        },
    )

    # Validation → Memory update
    graph.add_edge("validate_gaps", "update_memory")

    # ... rest of graph ...

    return graph.compile(checkpointer=self.checkpointer)
```

**Testing:**
```python
# tests/unit/application/workflows/test_interview_conversation_workflow.py

async def test_gap_validation_merges_missing_gaps():
    """Test that gap validation merges gaps from DB."""
    workflow = create_workflow_fixture()

    # Setup: DB has 3 gaps, state only has 2
    db_evaluation = create_evaluation_with_gaps([
        "async/await", "event loop", "callbacks"
    ])
    await save_evaluation_to_db(db_evaluation)

    state = create_state_with_gaps([
        "async/await", "event loop"
    ])  # Missing "callbacks"

    result = await workflow._validate_gaps_node(state)

    # Assert missing gap added
    assert "cumulative_gaps" in result
    assert "callbacks" in result["cumulative_gaps"]
    assert len(result["cumulative_gaps"]) == 3


async def test_gap_validation_skips_if_no_parent():
    """Test that validation skipped for main questions."""
    workflow = create_workflow_fixture()

    state = create_state_without_parent_question()

    result = await workflow._validate_gaps_node(state)

    # Assert no changes
    assert result == {}
```

---

### Task 3.2: Document Gap Strategy (1 hour)

**File:** `docs/gap-accumulation-strategy.md` (NEW)

**Content:**

```markdown
# Gap Accumulation Strategy

## Overview

Hybrid approach combining state-based accumulation (performance) with DB validation (correctness).

## Strategy Details

### Normal Flow (State-Based)
- Gaps accumulated in `ConversationState.cumulative_gaps` array
- Appended in `_decide_followup_node()` as new gaps detected
- Fast: Zero DB queries
- Checkpointed for persistence

### Resume Flow (DB Validation)
- On checkpoint resume, validate gaps against DB
- Query all evaluations for parent question
- Merge any missing gaps into state
- Log mismatches for monitoring

## Rationale

**Why Hybrid?**
- State-based: Fast for normal flow (99% of cases)
- DB validation: Safety net for checkpoint corruption/reset
- Best of both: Performance + reliability

**When Does Validation Run?**
- Only when `parent_question_id` present in state (follow-up context)
- Only when resuming from checkpoint (not on fresh start)
- Non-blocking: Continues if validation fails

## Performance Impact

- Normal flow: Zero overhead (state lookup only)
- Resume flow: One DB query per parent question
- Acceptable: Resumes are rare (<1% of flows)

## Testing Strategy

- Unit: Test gap merge logic with mock DB
- Integration: Test resume with corrupted state
- Load: Verify performance under concurrent resumes
```

---

### Task 3.3: Add Gap Mismatch Monitoring (30 min)

**File:** `src/application/workflows/interview_conversation_workflow.py`

**Changes:**

```python
# In _validate_gaps_node(), enhance logging for monitoring

if missing_gaps:
    logger.warning(
        f"Gap mismatch detected",
        extra={
            "interview_id": state["interview_id"],
            "parent_question_id": parent_question_id_str,
            "state_gaps": list(state_gaps),
            "db_gaps": list(db_gaps),
            "missing_gaps": list(missing_gaps),
            "mismatch_count": len(missing_gaps),
        },
    )

    # NEW: Emit metric for monitoring
    from ...infrastructure.observability.metrics import emit_counter
    emit_counter(
        "gap_validation.mismatch",
        value=len(missing_gaps),
        tags={
            "interview_id": state["interview_id"],
            "severity": "warning",
        },
    )
```

**Monitoring Alert:**
- Alert if `gap_validation.mismatch` > 10 events/hour
- Indicates checkpoint corruption or state bugs

---

### Task 3.4: Integration Test for Gap Consistency (1 hour)

**File:** `tests/integration/workflows/test_gap_accumulation.py` (NEW)

**Content:**

```python
"""Integration tests for gap accumulation consistency."""

async def test_gap_accumulation_normal_flow():
    """Test gaps accumulate correctly in normal flow."""
    workflow = create_workflow_fixture()
    thread_id = await start_workflow_session(workflow)

    # Answer 1: Generates gaps
    result1 = await workflow.process_answer(
        thread_id=thread_id,
        answer_text="Brief answer with gaps",
    )

    # Answer 2 (follow-up): Adds more gaps
    result2 = await workflow.process_answer(
        thread_id=thread_id,
        answer_text="Still missing concepts",
    )

    # Get state
    state = await workflow.get_workflow_state(thread_id)

    # Assert cumulative gaps
    assert "cumulative_gaps" in state
    assert len(state["cumulative_gaps"]) > 0
    assert "gap_concept_1" in state["cumulative_gaps"]
    assert "gap_concept_2" in state["cumulative_gaps"]


async def test_gap_validation_on_resume():
    """Test gap validation merges DB gaps after resume."""
    workflow = create_workflow_fixture()

    # Create interview with existing evaluations in DB
    interview_id, parent_q_id = await create_interview_with_gaps()

    # Start workflow (resume from checkpoint)
    thread_id = f"interview_{interview_id}"
    state = await workflow.get_workflow_state(thread_id)

    # Simulate corrupted state (missing gaps)
    state["cumulative_gaps"] = []  # Clear gaps

    # Process next answer (triggers validation)
    result = await workflow.process_answer(
        thread_id=thread_id,
        answer_text="Another answer",
    )

    # Get updated state
    new_state = await workflow.get_workflow_state(thread_id)

    # Assert gaps restored from DB
    assert len(new_state["cumulative_gaps"]) > 0


async def test_legacy_vs_workflow_gap_parity():
    """Test gap accumulation matches between legacy and workflow."""
    interview_id = create_test_interview()

    # Run legacy path
    legacy_gaps = await run_legacy_interview_and_get_gaps(interview_id)

    # Run workflow path
    workflow_gaps = await run_workflow_interview_and_get_gaps(interview_id)

    # Assert gap sets equal (order-independent)
    assert set(legacy_gaps) == set(workflow_gaps)
```

---

## Testing Strategy

### Unit Tests (3 new)
1. `test_gap_validation_merges_missing_gaps()` - Gap merge logic
2. `test_gap_validation_skips_if_no_parent()` - Validation gating
3. `test_gap_accumulation_in_decide_followup()` - State append logic

### Integration Tests (3 new)
1. `test_gap_accumulation_normal_flow()` - Normal flow accumulation
2. `test_gap_validation_on_resume()` - Resume validation
3. `test_legacy_vs_workflow_gap_parity()` - Parity check

**Total:** 6 new tests

## Acceptance Criteria

- [ ] **AC1:** Hybrid strategy documented in `docs/gap-accumulation-strategy.md`
- [ ] **AC2:** Gap validation node added to workflow graph
- [ ] **AC3:** Validation runs only when `parent_question_id` present
- [ ] **AC4:** Missing gaps merged from DB into state
- [ ] **AC5:** Gap mismatches logged with full context
- [ ] **AC6:** Monitoring metric emitted for mismatches
- [ ] **AC7:** All 6 tests passing
- [ ] **AC8:** Parity test shows identical gap sets between paths

## Rollout Checklist

- [ ] Code reviewed and approved
- [ ] All tests passing
- [ ] Documentation added to docs/
- [ ] Monitoring dashboard shows gap mismatch metric
- [ ] Alert configured for high mismatch rate
- [ ] Manual testing with checkpoint resume
- [ ] Performance tested (DB query overhead acceptable)

## Risks & Mitigation

### Risk 1: DB Query Overhead on Resume
**Impact:** Low | **Likelihood:** Low
**Mitigation:** Resumes are rare, one-time query acceptable

### Risk 2: Validation Logic Complexity
**Impact:** Medium | **Likelihood:** Low
**Mitigation:** Comprehensive unit tests, logging for debugging

### Risk 3: State-DB Divergence
**Impact:** Medium | **Likelihood:** Medium
**Mitigation:** Monitoring alerts, automated reconciliation

## Estimated Timeline

| Task | Effort | Completion |
|------|--------|------------|
| 3.1: Gap Validation Node | 2.5h | 75% |
| 3.2: Strategy Documentation | 1h | 20% |
| 3.3: Monitoring | 30min | 12% |
| 3.4: Integration Tests | 1h | 25% |

**Total:** 5 hours (Day 3)

## Next Phase

Proceed to **Phase 4: Polish & Edge Cases**
- State synchronization
- Retry logic
- Audio storage decision
- See [phase-04-polish.md](phase-04-polish.md)
