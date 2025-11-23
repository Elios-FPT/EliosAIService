# Phase 2: Update `_evaluate_answer_node`

**Duration**: 2-3 hours
**File**: `src/application/workflows/interview_conversation_workflow.py`
**Lines**: Update `_evaluate_answer_node` (lines 288-397)
**Target Lines**: Replace lines 356-375 (evaluation creation logic)

## Overview

Replace placeholder evaluation logic with complete adaptive evaluation:
1. Detect follow-up vs main question from state
2. Build follow-up context if applicable
3. Detect gaps using `_detect_gaps_hybrid()`
4. Create `ConceptGap` objects
5. Calculate attempt number from state
6. Apply penalty using `evaluation.apply_penalty()`
7. Auto-resolve gaps using `evaluation.is_gap_resolved_by_criteria()`

## Current Code (Lines 356-375)

**Location**: Inside `_evaluate_answer_node()`, after LLM evaluation

```python
# Create Evaluation entity with all required fields
evaluation = Evaluation(
    answer_id=answer.id,
    question_id=UUID(state["current_question_id"] or ""),
    interview_id=UUID(state["interview_id"]),
    raw_score=evaluation_result.score,
    penalty=0.0,  # No penalty for now (workflow simplified)
    final_score=evaluation_result.score,
    similarity_score=evaluation_result.semantic_similarity,
    completeness=evaluation_result.completeness,
    relevance=evaluation_result.relevance,
    sentiment=evaluation_result.sentiment,
    reasoning=evaluation_result.reasoning,
    strengths=evaluation_result.strengths,
    weaknesses=evaluation_result.weaknesses,
    improvement_suggestions=evaluation_result.improvement_suggestions,
    attempt_number=1,  # Simplified for initial migration
    gaps=[],  # Gap detection can be added later
    evaluated_at=datetime.utcnow(),
)
await self.evaluation_repo.save(evaluation)
```

**Issues**:
- ❌ `penalty=0.0` (no attempt-based penalty)
- ❌ `final_score=evaluation_result.score` (penalty not applied)
- ❌ `attempt_number=1` (always 1)
- ❌ `gaps=[]` (no gap detection)
- ❌ No auto-resolution logic

---

## Target Code (Replacement)

**Replace lines 356-375** with:

```python
# Step 1: Detect follow-up vs main question from state
parent_question_id = state.get("parent_question_id")
is_followup = parent_question_id is not None
followup_count = state.get("followup_count", 0)

# Step 2: Calculate attempt number
if is_followup:
    attempt_number = followup_count  # 2 or 3
else:
    attempt_number = 1  # Main question

# Step 3: Build follow-up context if applicable
followup_context = None
if is_followup:
    followup_context = self._build_followup_context_from_state(state)
    if followup_context:
        logger.debug(
            f"Follow-up context: attempt={followup_context.attempt_number}, "
            f"prev_scores={followup_context.previous_scores}, "
            f"gaps={len(followup_context.cumulative_gaps)}"
        )

# Step 4: Detect gaps (if ideal_answer exists)
current_question_dict = state.get("current_question", {})
ideal_answer = current_question_dict.get("ideal_answer", "")

gaps_list: list[ConceptGap] = []
if ideal_answer:
    gaps_dict = await self._detect_gaps_hybrid(
        answer_text=answer_text,
        ideal_answer=ideal_answer,
        question_text=current_question_dict.get("text", ""),
    )

    # Step 5: Create ConceptGap objects
    gap_concepts = gaps_dict.get("concepts", [])
    if gap_concepts:
        logger.info(
            f"Gaps detected: {len(gap_concepts)} concepts",
            extra={"concepts": gap_concepts, "severity": gaps_dict.get("severity")}
        )

        for concept in gap_concepts:
            gap = ConceptGap(
                evaluation_id=answer.id,  # Temporary, will be updated after save
                concept=concept,
                severity=self._determine_gap_severity(concept, gaps_dict),
                resolved=False,
                created_at=datetime.utcnow(),
            )
            gaps_list.append(gap)
else:
    logger.debug("No ideal_answer, skipping gap detection")

# Step 6: Create Evaluation entity
evaluation = Evaluation(
    answer_id=answer.id,
    question_id=UUID(state["current_question_id"] or ""),
    interview_id=UUID(state["interview_id"]),
    raw_score=evaluation_result.score,
    penalty=0.0,  # Will be set by apply_penalty()
    final_score=evaluation_result.score,  # Will be recalculated by apply_penalty()
    similarity_score=evaluation_result.semantic_similarity,
    completeness=evaluation_result.completeness,
    relevance=evaluation_result.relevance,
    sentiment=evaluation_result.sentiment,
    reasoning=evaluation_result.reasoning,
    strengths=evaluation_result.strengths,
    weaknesses=evaluation_result.weaknesses,
    improvement_suggestions=evaluation_result.improvement_suggestions,
    attempt_number=attempt_number,
    parent_evaluation_id=(
        UUID(state["evaluations"][-1]["id"]) if is_followup and state.get("evaluations") else None
    ),
    gaps=gaps_list,
    evaluated_at=datetime.utcnow(),
)

# Step 7: Apply penalty based on attempt number
evaluation.apply_penalty(attempt_number)
logger.info(
    f"Penalty applied: attempt={attempt_number}, penalty={evaluation.penalty}, "
    f"raw_score={evaluation.raw_score:.1f}, final_score={evaluation.final_score:.1f}"
)

# Step 8: Check if gaps should be auto-resolved
if evaluation.is_gap_resolved_by_criteria():
    evaluation.resolve_gaps()
    logger.info(
        f"Gaps auto-resolved by criteria: completeness={evaluation.completeness:.2f}, "
        f"final_score={evaluation.final_score:.1f}, attempt={attempt_number}"
    )

# Step 9: Update gap evaluation_ids before save
for gap in evaluation.gaps:
    gap.evaluation_id = evaluation.id

# Step 10: Save evaluation
await self.evaluation_repo.save(evaluation)
```

---

## Line-by-Line Changes

### Before Line 356 (Add Logic)

**Location**: After line 343 (LLM evaluation call)

**Add** (before evaluation creation):
```python
# Detect follow-up vs main question
parent_question_id = state.get("parent_question_id")
is_followup = parent_question_id is not None
followup_count = state.get("followup_count", 0)

# Calculate attempt number
if is_followup:
    attempt_number = followup_count
else:
    attempt_number = 1

# Build follow-up context if applicable
followup_context = None
if is_followup:
    followup_context = self._build_followup_context_from_state(state)
    if followup_context:
        logger.debug(
            f"Follow-up context: attempt={followup_context.attempt_number}, "
            f"prev_scores={followup_context.previous_scores}, "
            f"gaps={len(followup_context.cumulative_gaps)}"
        )

# Detect gaps (if ideal_answer exists)
current_question_dict = state.get("current_question", {})
ideal_answer = current_question_dict.get("ideal_answer", "")

gaps_list: list[ConceptGap] = []
if ideal_answer:
    gaps_dict = await self._detect_gaps_hybrid(
        answer_text=answer_text,
        ideal_answer=ideal_answer,
        question_text=current_question_dict.get("text", ""),
    )

    # Create ConceptGap objects
    gap_concepts = gaps_dict.get("concepts", [])
    if gap_concepts:
        logger.info(
            f"Gaps detected: {len(gap_concepts)} concepts",
            extra={"concepts": gap_concepts, "severity": gaps_dict.get("severity")}
        )

        for concept in gap_concepts:
            gap = ConceptGap(
                evaluation_id=answer.id,  # Temporary
                concept=concept,
                severity=self._determine_gap_severity(concept, gaps_dict),
                resolved=False,
                created_at=datetime.utcnow(),
            )
            gaps_list.append(gap)
else:
    logger.debug("No ideal_answer, skipping gap detection")
```

### Line 356-372 (Replace)

**Old**:
```python
evaluation = Evaluation(
    ...
    penalty=0.0,  # No penalty for now
    final_score=evaluation_result.score,
    attempt_number=1,  # Simplified
    gaps=[],  # Gap detection can be added later
    evaluated_at=datetime.utcnow(),
)
```

**New**:
```python
evaluation = Evaluation(
    ...
    penalty=0.0,  # Will be set by apply_penalty()
    final_score=evaluation_result.score,  # Will be recalculated
    attempt_number=attempt_number,  # From state
    parent_evaluation_id=(
        UUID(state["evaluations"][-1]["id"]) if is_followup and state.get("evaluations") else None
    ),
    gaps=gaps_list,  # From gap detection
    evaluated_at=datetime.utcnow(),
)

# Apply penalty based on attempt number
evaluation.apply_penalty(attempt_number)
logger.info(
    f"Penalty applied: attempt={attempt_number}, penalty={evaluation.penalty}, "
    f"raw_score={evaluation.raw_score:.1f}, final_score={evaluation.final_score:.1f}"
)

# Check if gaps should be auto-resolved
if evaluation.is_gap_resolved_by_criteria():
    evaluation.resolve_gaps()
    logger.info(
        f"Gaps auto-resolved by criteria: completeness={evaluation.completeness:.2f}, "
        f"final_score={evaluation.final_score:.1f}, attempt={attempt_number}"
    )

# Update gap evaluation_ids before save
for gap in evaluation.gaps:
    gap.evaluation_id = evaluation.id
```

### Line 373-375 (Keep)

**Keep**:
```python
await self.evaluation_repo.save(evaluation)
```

---

## Updated Method Signature (No Changes)

**Method**: `_evaluate_answer_node(self, state: ConversationState) -> dict[str, Any]`

**No changes to signature** - only internal logic updates.

---

## State Data Dependencies

**Required State Fields** (must exist):
- ✅ `current_question`: `dict[str, Any]` (has `ideal_answer`, `text`)
- ✅ `current_question_id`: `str`
- ✅ `interview_id`: `str`
- ✅ `pending_answer_text`: `str`
- ✅ `parent_question_id`: `str | None` (for follow-up detection)
- ✅ `followup_count`: `int` (for attempt number)
- ✅ `evaluations`: `list[dict[str, Any]]` (for parent_evaluation_id)

**Missing Data Handling**:
- `ideal_answer` missing: Skip gap detection (log warning)
- `parent_question_id` is `None`: Main question (attempt = 1)
- `evaluations` empty: `parent_evaluation_id = None`

---

## LLM Adapter Call (No Changes)

**Line 339-343** (UNCHANGED):
```python
evaluation_result = await self.llm.evaluate_answer(
    question=question,
    answer_text=answer_text,
    context=context,
)
```

**Note**: Follow-up context is NOT passed to LLM in this workflow (simplified).
If needed in future, add:
```python
evaluation_result = await self.llm.evaluate_answer(
    question=question,
    answer_text=answer_text,
    context=context,
    followup_context=followup_context,  # NEW
)
```

---

## Error Handling

### Gap Detection Errors

**Scenario**: LLM call fails in `_detect_gaps_hybrid()`
**Handling**: Returns `{"concepts": [], "confirmed": False}`
**Impact**: `gaps_list = []` (no gaps detected)

### Context Building Errors

**Scenario**: `_build_followup_context_from_state()` returns `None`
**Handling**: `followup_context = None`, log warning
**Impact**: No context passed to LLM (evaluation proceeds normally)

### Penalty Application Errors

**Scenario**: `attempt_number` out of range (e.g., 4)
**Handling**: `evaluation.apply_penalty()` raises `ValueError`
**Impact**: Exception propagates to `except` block at line 392
**Log**: `"evaluate_answer_node failed: Invalid attempt_number: 4"`

**Prevention**:
```python
# Clamp attempt_number to valid range
attempt_number = max(1, min(3, attempt_number))
```

---

## Logging Updates

**Add** (strategic logging points):

1. **Follow-up detection** (before gap detection):
```python
logger.debug(f"Question type: {'follow-up' if is_followup else 'main'}, attempt={attempt_number}")
```

2. **Gap detection result** (after `_detect_gaps_hybrid()`):
```python
if gap_concepts:
    logger.info(
        f"Gaps detected: {len(gap_concepts)} concepts",
        extra={"concepts": gap_concepts, "severity": gaps_dict.get("severity")}
    )
```

3. **Penalty application** (after `apply_penalty()`):
```python
logger.info(
    f"Penalty applied: attempt={attempt_number}, penalty={evaluation.penalty}, "
    f"raw_score={evaluation.raw_score:.1f}, final_score={evaluation.final_score:.1f}"
)
```

4. **Auto-resolution** (after `resolve_gaps()`):
```python
logger.info(
    f"Gaps auto-resolved by criteria: completeness={evaluation.completeness:.2f}, "
    f"final_score={evaluation.final_score:.1f}, attempt={attempt_number}"
)
```

---

## Testing Strategy (Manual)

### Test Case 1: Main Question (Attempt 1)

**Setup**:
```python
state = {
    "parent_question_id": None,  # Main question
    "followup_count": 0,
    "current_question": {
        "text": "Explain async/await",
        "ideal_answer": "async/await handles promises with cleaner syntax",
    },
    "pending_answer_text": "async/await is for asynchronous code",
    ...
}
```

**Expected**:
- `attempt_number = 1`
- `penalty = 0.0`
- `final_score = raw_score`
- Gaps detected if answer incomplete

**Verify Logs**:
```
DEBUG: Question type: main, attempt=1
INFO: Gaps detected: 2 concepts
INFO: Penalty applied: attempt=1, penalty=0.0, raw_score=75.0, final_score=75.0
```

### Test Case 2: First Follow-Up (Attempt 2)

**Setup**:
```python
state = {
    "parent_question_id": "uuid-123",  # Follow-up
    "followup_count": 2,
    "current_question": {
        "text": "Can you elaborate on promises?",
        "ideal_answer": "async/await handles promises...",
    },
    "evaluations": [
        {"id": "uuid-456", "final_score": 65.0, ...}
    ],
    "pending_answer_text": "Promises represent eventual completion",
    ...
}
```

**Expected**:
- `attempt_number = 2`
- `penalty = -5.0`
- `final_score = raw_score - 5.0`
- `parent_evaluation_id = uuid-456`

**Verify Logs**:
```
DEBUG: Question type: follow-up, attempt=2
DEBUG: Follow-up context: attempt=2, prev_scores=[65.0], gaps=1
INFO: Penalty applied: attempt=2, penalty=-5.0, raw_score=80.0, final_score=75.0
```

### Test Case 3: Auto-Resolution (Criteria Met)

**Setup**:
```python
state = {
    "parent_question_id": "uuid-123",
    "followup_count": 3,  # Third attempt
    "current_question": {"ideal_answer": "...", ...},
    "pending_answer_text": "Good answer",
    ...
}
```

**LLM Returns**: `completeness=0.85`

**Expected**:
- `attempt_number = 3`
- `penalty = -15.0`
- Gaps auto-resolved (criteria: completeness >= 0.8)

**Verify Logs**:
```
INFO: Gaps auto-resolved by criteria: completeness=0.85, final_score=70.0, attempt=3
```

### Test Case 4: No Ideal Answer

**Setup**:
```python
state = {
    "current_question": {
        "text": "Tell me about yourself",
        "ideal_answer": "",  # No ideal answer
    },
    "pending_answer_text": "I am a software engineer",
    ...
}
```

**Expected**:
- `gaps_list = []`
- No gap detection performed

**Verify Logs**:
```
DEBUG: No ideal_answer, skipping gap detection
```

---

## Success Criteria

✅ **Gap Detection**:
- `_detect_gaps_hybrid()` called when `ideal_answer` exists
- `ConceptGap` objects created with correct severity
- Gaps skipped when `ideal_answer` is empty

✅ **Attempt Detection**:
- Main question: `attempt_number = 1`
- Follow-up: `attempt_number = followup_count`

✅ **Penalty Application**:
- Attempt 1: `penalty = 0.0`, `final_score = raw_score`
- Attempt 2: `penalty = -5.0`, `final_score = raw_score - 5.0`
- Attempt 3: `penalty = -15.0`, `final_score = raw_score - 15.0`

✅ **Auto-Resolution**:
- Gaps resolved when `completeness >= 0.8`
- Gaps resolved when `final_score >= 80`
- Gaps resolved when `attempt_number == 3`

✅ **State Updates**:
- `parent_evaluation_id` set for follow-ups
- `gaps` populated from gap detection

---

## Code Review Checklist

- [ ] `attempt_number` calculated from `followup_count` (not hardcoded)
- [ ] `penalty` applied using `evaluation.apply_penalty()`
- [ ] `final_score` recalculated after penalty
- [ ] `gaps_list` created from `_detect_gaps_hybrid()` result
- [ ] `parent_evaluation_id` extracted from `state["evaluations"][-1]["id"]`
- [ ] Auto-resolution called: `evaluation.is_gap_resolved_by_criteria()`
- [ ] Gap `evaluation_id` updated before save
- [ ] Logging statements at INFO/DEBUG levels
- [ ] Error handling preserves existing try/except block
- [ ] No changes to LLM adapter call signature

---

## Next Phase

After Phase 2 completion, proceed to:
- **Phase 3**: Update `_generate_followup_node` to pass `ideal_answer` in state
