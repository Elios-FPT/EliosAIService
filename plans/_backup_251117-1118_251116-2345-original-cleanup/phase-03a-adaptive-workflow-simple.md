# Phase 3A: Adaptive Workflow (Simple - No Interrupts)

**Phase ID**: 03A
**Created**: 2025-11-16
**Priority**: High
**Estimated Duration**: 1 week
**Risk Level**: Medium (reduced from High)
**Implementation Status**: Not Started
**Review Status**: Approved

---

## Context Links

- **Parent Plan**: [plan.md](plan.md)
- **Dependencies**: Phase 1 (LangChain), Phase 2 (LangGraph basics)
- **Supersedes**: Original Phase 3 (split into 3A + 3B)
- **Next Phase**: [Phase 3B: WebSocket Interrupts](phase-03b-websocket-interrupts.md)

---

## Overview

**De-risked approach**: Build LangGraph workflow for adaptive evaluation WITHOUT interrupts first. Run complete evaluation loop in single invocation.

**Rationale**: Original Phase 3 too complex (interrupts + WebSocket + thread_id + refactor). Split reduces risk:
- **Phase 3A**: StateGraph logic only (Medium risk)
- **Phase 3B**: Add interrupts + WebSocket streaming (High risk)

**Current Problem**:
- Follow-up logic spread across 3 use cases (ProcessAnswerAdaptive, FollowUpDecision, CombineEvaluation)
- Break conditions buried in imperative code
- Hard to test/visualize complete evaluation flow

**Solution**:
- Single StateGraph that runs ALL follow-up iterations
- Conditional edges for break conditions (declarative)
- Keep existing WebSocket handler (no changes yet)
- Test with real interviews before adding interrupts

---

## Key Insights

**Simplified Flow**:
- Client sends answer → Server runs ENTIRE evaluation loop → Server returns final result
- No mid-loop interrupts (WebSocket not involved in workflow control)
- Follow-up questions generated but NOT sent until loop completes
- Phase 3B will add real-time streaming

**Benefits**:
- Easier to test (synchronous workflow)
- Validate StateGraph logic before WebSocket complexity
- Can deploy to production safely (no protocol changes)

---

## Requirements

### Functional Requirements
**FR1**: Evaluate answer with LLM (semantic analysis + gap detection)
**FR2**: Decide follow-up based on break conditions (max 3, similarity ≥0.8, no gaps)
**FR3**: Generate up to 3 follow-up questions in loop
**FR4**: Combine parent + child evaluations into COMBINED type
**FR5**: Return complete evaluation result to caller

### Non-Functional Requirements
**NFR1**: No WebSocket changes (backward compatible)
**NFR2**: Testable in isolation (mock LLM, run workflow end-to-end)
**NFR3**: Visual workflow (LangSmith shows all nodes/edges)
**NFR4**: Performance: <5s for full 3-iteration loop

---

## Architecture

### Workflow Flow (Complete in Single Invocation)
```
StateGraph (synchronous execution):
┌─────────────────────────────────────────────────┐
│ START (answer_text, question_id, interview_id) │
└────────────┬────────────────────────────────────┘
             ↓
    ┌─────────────────────┐
    │ load_context        │ ← Fetch interview, question, parent question
    └────────┬────────────┘
             ↓
    ┌─────────────────────┐
    │ evaluate_answer     │ ← LLM evaluation (similarity, gaps)
    └────────┬────────────┘
             ↓
    ┌─────────────────────┐
    │ store_answer        │ ← Save Answer + Evaluation to DB
    └────────┬────────────┘
             ↓
    ┌─────────────────────┐
    │ check_followup_need │ ← Break conditions check
    └────────┬────────────┘
             ↓
      CONDITIONAL EDGE:
      ┌──────────┬──────────┐
      │          │          │
  needs_followup=True    False
      ↓          │          ↓
┌───────────┐   │   ┌──────────────┐
│ generate_ │   │   │ combine_     │
│ followup  │   │   │ evaluations  │
└─────┬─────┘   │   └──────┬───────┘
      ↓         │          ↓
┌───────────┐   │        END
│ LOOP BACK │   │   (return combined)
│ to eval   │   │
│ (max 3)   │   │
└───────────┘   │
```

### State Definition
```python
# src/application/workflows/adaptive_eval_simple_workflow.py
class AdaptiveEvalSimpleState(TypedDict):
    # Input
    interview_id: UUID
    question_id: UUID
    answer_text: str

    # Context (loaded)
    interview: Interview | None
    question: Question | None
    parent_question_id: UUID | None

    # Loop tracking
    iteration: int  # 0, 1, 2, 3
    evaluations: list[Evaluation]  # All evaluations (parent + children)
    cumulative_gaps: list[str]

    # Output
    combined_evaluation: Evaluation | None
    followup_questions_generated: list[Question]  # For Phase 3B
    complete: bool
```

### Break Conditions (Conditional Edge)
```python
def should_generate_followup(state: AdaptiveEvalSimpleState) -> str:
    """Decide: loop back OR combine evaluations."""

    # Max iterations reached
    if state["iteration"] >= 3:
        return "combine_evaluations"

    # High quality answer
    latest_eval = state["evaluations"][-1]
    if latest_eval.similarity_score >= 0.8:
        return "combine_evaluations"

    # No gaps detected
    if not latest_eval.gaps or not latest_eval.gaps.confirmed:
        return "combine_evaluations"

    # Need follow-up
    return "generate_followup"
```

---

## Related Code Files

### Existing Files to Modify
1. **`src/adapters/api/websocket/interview_handler.py`**:
   - Update `handle_text_answer()` to call workflow
   - Keep existing WebSocket protocol (no changes)
   - Return combined evaluation when workflow completes

2. **`src/infrastructure/dependency_injection/container.py`**:
   - Add `adaptive_eval_simple_workflow()` method

3. **`src/infrastructure/config/settings.py`**:
   - Add `use_langgraph_adaptive_simple: bool = False`

### New Files to Create
1. **`src/application/workflows/adaptive_eval_simple_workflow.py`** (300 lines):
   - `AdaptiveEvalSimpleState` TypedDict
   - `AdaptiveEvalSimpleWorkflow` class
   - 6 nodes: load_context, evaluate_answer, store_answer, check_followup, generate_followup, combine
   - Conditional edge function

2. **`tests/unit/application/workflows/test_adaptive_eval_simple.py`** (250 lines):
   - Test each node with mocks
   - Test break conditions (all 3 scenarios)
   - Test max iteration limit

3. **`tests/integration/workflows/test_adaptive_eval_simple_integration.py`** (150 lines):
   - End-to-end test with real DB
   - Test 0, 1, 2, 3 iteration scenarios

---

## Implementation Steps

### Step 1: Define State & Workflow Class (1 day)
1. Create `AdaptiveEvalSimpleState` TypedDict
2. Create `AdaptiveEvalSimpleWorkflow` class skeleton
3. Add to DI container

### Step 2: Implement Core Nodes (2 days)
1. **load_context_node**: Fetch interview, question, parent from repos
2. **evaluate_answer_node**: Call `ProcessAnswerAdaptiveUseCase.execute()`
3. **store_answer_node**: Save Answer + Evaluation to DB
4. **check_followup_node**: Update iteration counter, check break conditions
5. **generate_followup_node**: Call `LLMPort.generate_followup_question()`
6. **combine_evaluations_node**: Call `CombineEvaluationUseCase`

### Step 3: Build StateGraph (1 day)
1. Add all nodes to graph
2. Add conditional edge on `check_followup_node`
3. Add loop-back edge: `generate_followup` → `evaluate_answer` (updates question_id)
4. Compile graph with checkpointer (optional for Phase 3A)

### Step 4: Integration with WebSocket Handler (1 day)
1. Update handler to call workflow:
   ```python
   async def handle_text_answer(self, message: dict):
       result = await self.adaptive_workflow.execute(
           interview_id=self.interview_id,
           question_id=message["question_id"],
           answer_text=message["answer_text"]
       )

       # Send combined evaluation
       await self.websocket.send_json({
           "type": "evaluation_complete",
           "evaluation": result["combined_evaluation"].to_dict(),
           "followup_questions": [q.to_dict() for q in result["followup_questions_generated"]]
       })
   ```
2. Feature flag: `if settings.use_langgraph_adaptive_simple`

### Step 5: Testing (2 days)
1. Unit tests for each node
2. Integration test: Run full workflow with real DB
3. Test break conditions:
   - Max 3 iterations
   - Similarity ≥0.8 on iteration 1
   - No gaps on iteration 2

---

## Success Criteria

**Functional**:
- ✅ Complete evaluation loop runs (0-3 iterations)
- ✅ Break conditions work correctly
- ✅ Combined evaluation generated
- ✅ No regression vs current implementation

**Non-Functional**:
- ✅ <5s for 3-iteration loop
- ✅ Visual workflow in LangSmith
- ✅ Feature flag allows rollback

---

## Differences from Original Phase 3

| Aspect | Original Phase 3 | Phase 3A (Simple) |
|--------|------------------|-------------------|
| Interrupts | ✅ Human-in-loop | ❌ No interrupts (Phase 3B) |
| WebSocket Streaming | ✅ Real-time events | ❌ Batch response |
| Thread ID Persistence | ✅ Resume on disconnect | ❌ Not needed (Phase 3B) |
| Orchestrator Refactor | ✅ Replace entirely | ⚠️ Coexist (feature flag) |
| Risk Level | High | Medium |
| Duration | 2 weeks | 1 week |

---

## Next Steps

**After Phase 3A Completion**:
1. Validate workflow with real interviews (staging)
2. Measure performance vs current implementation
3. If successful → Proceed to Phase 3B (add interrupts)
4. If issues → Fix before adding complexity

---

**Phase Status**: Ready to Start (after Phase 0-2)
**Dependencies**: Phase 1, Phase 2
**Blocks**: Phase 3B
