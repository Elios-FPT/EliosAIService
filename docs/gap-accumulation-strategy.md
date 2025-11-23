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

## Implementation

### Workflow Graph
```
evaluate_answer → [follow-up?] → validate_gaps → update_memory
                       ↓                  ↓
               [main question] ───────────┘
```

### Gap Validation Node
Location: `src/application/workflows/interview_conversation_workflow.py`

```python
async def _validate_gaps_node(self, state: ConversationState) -> dict[str, Any]:
    """Validate cumulative gaps against DB (resume safety check)."""
    # Skip if no parent question (main questions don't need validation)
    if not state.get("parent_question_id"):
        return {}

    # Query DB for all evaluations of parent question
    # Extract unresolved gaps from evaluations
    # Compare with state gaps
    # Merge missing gaps if found
    # Log mismatch for monitoring
```

### Conditional Edge Logic
```python
graph.add_conditional_edges(
    "evaluate_answer",
    lambda state: "validate_gaps" if state.get("parent_question_id") else "update_memory",
    {
        "validate_gaps": "validate_gaps",
        "update_memory": "update_memory",
    },
)
```

## Testing Strategy

### Unit Tests
- Test gap merge logic with mock DB
- Test validation skipped for main questions
- Test empty gaps handling

### Integration Tests
- Test resume with corrupted state
- Test gap accumulation in normal flow
- Test legacy vs workflow parity

### Load Tests
- Verify performance under concurrent resumes
- Monitor DB query overhead

## Monitoring

### Metrics
- `gap_validation.mismatch` - Count of gap mismatches detected
- `gap_validation.duration` - Time spent in validation

### Alerts
- Alert if `gap_validation.mismatch` > 10 events/hour
- Indicates checkpoint corruption or state bugs

### Logging
```python
logger.warning(
    f"Gap mismatch detected: {len(missing_gaps)} gaps missing from state",
    extra={
        "interview_id": state["interview_id"],
        "parent_question_id": parent_question_id_str,
        "state_gaps": list(state_gaps),
        "db_gaps": list(db_gaps),
        "missing_gaps": list(missing_gaps),
        "mismatch_count": len(missing_gaps),
    },
)
```

## Acceptance Criteria

- ✅ Hybrid strategy documented
- ✅ Gap validation node added to workflow graph
- ✅ Validation runs only when `parent_question_id` present
- ✅ Missing gaps merged from DB into state
- ✅ Gap mismatches logged with full context
- ✅ Non-blocking: Continues if validation fails

## Related Documents

- [System Architecture](./system-architecture.md) - Workflow architecture
- [Codebase Summary](./codebase-summary.md) - Code structure
- [Phase 3 Plan](../plans/251124-0452-workflow-legacy-parity/phase-03-gap-strategy.md) - Implementation plan
