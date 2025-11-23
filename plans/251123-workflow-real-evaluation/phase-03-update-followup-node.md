# Phase 3: Update `_generate_followup_node`

**Duration**: 30 minutes - 1 hour
**File**: `src/application/workflows/interview_conversation_workflow.py`
**Lines**: Update `_generate_followup_node` (lines 518-622)
**Target Lines**: Add ideal_answer to state (lines 605-614)

## Overview

Ensure `ideal_answer` is passed in workflow state when generating follow-up questions. This enables gap detection in Phase 2.

**Problem**: Currently, `_generate_followup_node` returns `current_question` dict without `ideal_answer`:
```python
# Line 607-612 (CURRENT)
"current_question": {
    "id": str(followup.id),
    "text": followup.text,
    "question_type": "FOLLOW_UP",
},
```

**Solution**: Add `ideal_answer` from parent question to state.

---

## Current Code (Lines 605-614)

**Location**: Inside `_generate_followup_node()`, return statement

```python
return {
    "current_question_id": str(followup.id),
    "current_question": {
        "id": str(followup.id),
        "text": followup.text,
        "question_type": "FOLLOW_UP",
    },
    "parent_question_id": str(parent_question_id),
    "followup_count": followup_count + 1,
    "needs_followup": False,  # Reset for next cycle
}
```

**Issue**: `ideal_answer` missing from `current_question` dict.

---

## Target Code (Replacement)

**Replace lines 605-614** with:

```python
# Extract ideal_answer from parent question (already in state)
parent_question_dict = state.get("current_question", {})
ideal_answer = parent_question_dict.get("ideal_answer", "")

return {
    "current_question_id": str(followup.id),
    "current_question": {
        "id": str(followup.id),
        "text": followup.text,
        "question_type": "FOLLOW_UP",
        "ideal_answer": ideal_answer,  # NEW: Pass parent's ideal_answer
    },
    "parent_question_id": str(parent_question_id),
    "followup_count": followup_count + 1,
    "needs_followup": False,  # Reset for next cycle
}
```

---

## Alternative: Get from Question Repository

**If ideal_answer not in state**, fallback to querying parent question:

```python
# Extract ideal_answer from parent question
parent_question_dict = state.get("current_question", {})
ideal_answer = parent_question_dict.get("ideal_answer")

# Fallback: Query parent question if not in state
if not ideal_answer:
    parent_question_obj = await self.question_repo.get_by_id(parent_question_id)
    if parent_question_obj:
        ideal_answer = parent_question_obj.ideal_answer or ""
        logger.debug(f"Fetched ideal_answer from repository for parent {parent_question_id}")
    else:
        ideal_answer = ""
        logger.warning(f"Parent question {parent_question_id} not found, no ideal_answer")

return {
    "current_question_id": str(followup.id),
    "current_question": {
        "id": str(followup.id),
        "text": followup.text,
        "question_type": "FOLLOW_UP",
        "ideal_answer": ideal_answer,  # NEW
    },
    "parent_question_id": str(parent_question_id),
    "followup_count": followup_count + 1,
    "needs_followup": False,
}
```

**Recommendation**: Use state-based approach (simpler, no DB query).

---

## Line-by-Line Changes

### Before Line 605 (Add Logic)

**Location**: After line 594 (`await self.interview_repo.update(interview)`)

**Add** (before return statement):
```python
# Extract ideal_answer from parent question (in state)
parent_question_dict = state.get("current_question", {})
ideal_answer = parent_question_dict.get("ideal_answer", "")

if not ideal_answer:
    logger.warning(
        f"No ideal_answer in state for parent question {parent_question_id}, "
        f"gap detection will be skipped"
    )
```

### Lines 607-612 (Update)

**Old**:
```python
"current_question": {
    "id": str(followup.id),
    "text": followup.text,
    "question_type": "FOLLOW_UP",
},
```

**New**:
```python
"current_question": {
    "id": str(followup.id),
    "text": followup.text,
    "question_type": "FOLLOW_UP",
    "ideal_answer": ideal_answer,  # NEW: From parent question
},
```

---

## State Flow Diagram

### Current Flow (Missing ideal_answer)

```
_start_session_node
  ↓
  state["current_question"] = {
      "id": "...",
      "text": "...",
      "ideal_answer": "...",  # ✅ Set from Question entity
  }
  ↓
_evaluate_answer_node
  ↓ (gaps detected)
_generate_followup_node
  ↓
  state["current_question"] = {
      "id": "...",
      "text": "...",
      "question_type": "FOLLOW_UP",
      # ❌ ideal_answer MISSING
  }
  ↓
_evaluate_answer_node
  ↓
  ideal_answer = current_question.get("ideal_answer", "")  # ❌ Empty string
  # Gap detection skipped
```

### Target Flow (ideal_answer Preserved)

```
_start_session_node
  ↓
  state["current_question"] = {
      "ideal_answer": "async/await handles promises...",  # ✅
  }
  ↓
_evaluate_answer_node (gaps detected)
  ↓
_generate_followup_node
  ↓
  # Extract from state
  ideal_answer = state["current_question"]["ideal_answer"]  # ✅
  ↓
  state["current_question"] = {
      "id": "followup-123",
      "text": "Can you elaborate on promises?",
      "question_type": "FOLLOW_UP",
      "ideal_answer": "async/await handles promises...",  # ✅ Preserved
  }
  ↓
_evaluate_answer_node
  ↓
  ideal_answer = current_question.get("ideal_answer", "")  # ✅ Has value
  gaps_dict = await self._detect_gaps_hybrid(...)  # ✅ Gap detection runs
```

---

## Verification (Manual Testing)

### Test Case: Follow-Up Question

**Setup**:
1. Start interview with question that has `ideal_answer`
2. Trigger follow-up (low score or gaps detected)

**Expected State After `_generate_followup_node`**:
```python
state["current_question"] = {
    "id": "followup-uuid",
    "text": "Can you elaborate on XYZ?",
    "question_type": "FOLLOW_UP",
    "ideal_answer": "Original parent ideal answer...",  # ✅ Must be present
}
```

**Verify Logs**:
```
# If ideal_answer exists:
DEBUG: Extracted ideal_answer from state for follow-up generation

# If ideal_answer missing (warning):
WARNING: No ideal_answer in state for parent question uuid-123, gap detection will be skipped
```

**Next Evaluation Cycle**:
```python
# In _evaluate_answer_node
ideal_answer = current_question.get("ideal_answer", "")
assert ideal_answer != ""  # ✅ Should have value
```

---

## Edge Cases

### Case 1: Parent Question Has No ideal_answer

**Scenario**: Technical question without ideal_answer field

**State**:
```python
state["current_question"] = {
    "ideal_answer": "",  # Empty
}
```

**Expected**:
- Follow-up inherits empty `ideal_answer`
- Gap detection skipped in next evaluation

**Log**:
```
WARNING: No ideal_answer in state for parent question uuid-123
```

### Case 2: State Corrupted (current_question Missing)

**Scenario**: State missing `current_question` dict

**State**:
```python
state["current_question"] = None
```

**Expected**:
- `ideal_answer = ""`
- Warning logged

**Log**:
```
WARNING: No current_question in state, follow-up will have no ideal_answer
```

**Code**:
```python
parent_question_dict = state.get("current_question", {})
if not parent_question_dict:
    logger.warning("No current_question in state, follow-up will have no ideal_answer")
    ideal_answer = ""
else:
    ideal_answer = parent_question_dict.get("ideal_answer", "")
```

---

## Initial Question Loading

**Verify**: `_start_session_node` already loads `ideal_answer` from Question entity.

**Location**: Lines 252-268

**Code** (EXISTING):
```python
question = await self.question_repo.get_by_id(current_iq.question_id)
...
return {
    "current_question": question.model_dump(mode="json"),  # ✅ Includes ideal_answer
    ...
}
```

**Verification**:
```python
# Check Question.model_dump() output
question = Question(
    id=uuid4(),
    text="Explain async/await",
    ideal_answer="async/await handles promises with cleaner syntax",
    ...
)

dumped = question.model_dump(mode="json")
assert "ideal_answer" in dumped  # ✅ Should be present
```

**Note**: If `Question.ideal_answer` is `None`, it will be serialized as `null` in JSON.
Handle in `_generate_followup_node`:
```python
ideal_answer = parent_question_dict.get("ideal_answer") or ""
```

---

## Success Criteria

✅ **State Update**:
- `current_question["ideal_answer"]` set when generating follow-up
- Value extracted from `state["current_question"]["ideal_answer"]`

✅ **Logging**:
- Debug log when ideal_answer extracted successfully
- Warning log when ideal_answer missing

✅ **Backward Compatibility**:
- No changes to node signature
- No changes to state schema

✅ **Gap Detection Enabled**:
- Next evaluation cycle can detect gaps (Phase 2)

---

## Code Review Checklist

- [ ] `ideal_answer` extracted from `state["current_question"]`
- [ ] Fallback to empty string if missing (`or ""`)
- [ ] Warning logged if `ideal_answer` is empty
- [ ] `current_question` dict updated with `ideal_answer` key
- [ ] No DB queries added (state-based only)
- [ ] Type hints preserved (`dict[str, Any]`)

---

## Alternative Approaches (Not Recommended)

### Approach 1: Store ideal_answer Separately in State

**Idea**: Add `parent_ideal_answer: str` to `ConversationState`

**Issues**:
- Requires state schema change
- Duplicates data (already in `current_question`)
- More complex state management

### Approach 2: Query Parent Question in _evaluate_answer_node

**Idea**: Fetch parent question in evaluation node if follow-up

**Issues**:
- Adds DB query to hot path (every evaluation)
- Slower (100-200ms overhead)
- Violates "state-based context" principle

**Recommendation**: Use state-based approach (Phase 3 plan).

---

## Integration with Phase 2

**Phase 2 Code** (in `_evaluate_answer_node`):
```python
# Extract ideal_answer from state
current_question_dict = state.get("current_question", {})
ideal_answer = current_question_dict.get("ideal_answer", "")

if ideal_answer:
    gaps_dict = await self._detect_gaps_hybrid(...)  # ✅ Runs
else:
    logger.debug("No ideal_answer, skipping gap detection")
    gaps_list = []  # ✅ Skipped
```

**Phase 3 Ensures**:
- `ideal_answer` present in state for follow-ups
- Gap detection runs for follow-up answers
- No DB queries needed in Phase 2

---

## Completion

After Phase 3 completion:
- ✅ All 3 phases implemented
- ✅ Real answer evaluation enabled
- ✅ Gap detection working
- ✅ Attempt-based penalties applied
- ✅ Auto-resolution criteria enforced

**Ready for Production**: Test with real interview flow.
