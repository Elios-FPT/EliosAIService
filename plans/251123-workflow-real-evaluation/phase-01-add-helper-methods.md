# Phase 1: Add Helper Methods

**Duration**: 1-2 hours
**File**: `src/application/workflows/interview_conversation_workflow.py`
**Lines**: Add ~115 lines after `_complete_interview_node` (line 742)

## Overview

Port 4 helper methods from `ProcessAnswerAdaptiveUseCase` to `InterviewConversationWorkflow`:
1. `_detect_gaps_hybrid()` - Hybrid keyword + LLM gap detection
2. `_detect_keyword_gaps()` - Fast keyword-based gap detection
3. `_determine_gap_severity()` - Map LLM severity to GapSeverity enum
4. `_build_followup_context_from_state()` - Build FollowUpEvaluationContext from state (NEW)

## Method 1: `_detect_gaps_hybrid()`

**Purpose**: Detect concept gaps using hybrid approach (keyword + LLM)

**Reference**: `process_answer_adaptive.py` lines 294-320

**Location**: Add after `_complete_interview_node` (line 742)

**Implementation**:
```python
async def _detect_gaps_hybrid(
    self,
    answer_text: str,
    ideal_answer: str,
    question_text: str,
) -> dict[str, Any]:
    """Detect concept gaps using hybrid approach (keywords + LLM).

    Step 1: Fast keyword-based detection
    Step 2: If keywords found gaps, confirm with LLM

    Args:
        answer_text: Candidate's answer
        ideal_answer: Reference ideal answer
        question_text: The question asked

    Returns:
        Gaps dict with detected concepts and severity
        Format: {"concepts": [...], "confirmed": bool, "severity": str}
    """
    # Step 1: Keyword-based gap detection
    keyword_gaps = self._detect_keyword_gaps(answer_text, ideal_answer)

    # Step 2: If keywords detected gaps, confirm with LLM
    if keyword_gaps:
        llm_gaps = await self.llm.detect_concept_gaps(
            answer_text=answer_text,
            ideal_answer=ideal_answer,
            question_text=question_text,
            keyword_gaps=keyword_gaps,
        )
        return llm_gaps
    else:
        return {"concepts": [], "confirmed": False, "severity": "minor"}
```

**Error Handling**:
- No exceptions raised (returns empty dict on error)
- LLM call failures handled by adapter (returns empty gaps)

**Logging**:
```python
logger.debug(f"Gap detection: keyword_gaps={len(keyword_gaps)}")
if llm_gaps.get("confirmed"):
    logger.info(f"Gaps confirmed by LLM: {llm_gaps['concepts']}")
```

---

## Method 2: `_detect_keyword_gaps()`

**Purpose**: Fast keyword-based gap detection (pre-filter for LLM)

**Reference**: `process_answer_adaptive.py` lines 322-347

**Location**: Add after `_detect_gaps_hybrid()`

**Implementation**:
```python
def _detect_keyword_gaps(self, answer_text: str, ideal_answer: str) -> list[str]:
    """Fast keyword-based gap detection.

    Extracts words from ideal_answer that are missing in answer_text.
    Filters:
    - Word length > 3 chars
    - Not in stop words list
    - Case-insensitive

    Args:
        answer_text: Candidate's answer
        ideal_answer: Reference ideal answer

    Returns:
        List of missing words (empty if < 4 missing words)
    """
    stop_words = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
        "being", "have", "has", "had", "do", "does", "did", "will", "would",
        "should", "could", "may", "might", "must", "can", "this", "that",
        "these", "those",
    }

    # Extract words from ideal answer (>3 chars, not stop words)
    ideal_words = {
        word.lower().strip('.,!?;:"\'-')
        for word in ideal_answer.split()
        if len(word.strip('.,!?;:"\'-')) > 3
        and word.lower().strip('.,!?;:"\'-') not in stop_words
    }

    # Extract words from answer
    answer_words = {
        word.lower().strip('.,!?;:"\'-')
        for word in answer_text.split()
        if len(word.strip('.,!?;:"\'-')) > 3
        and word.lower().strip('.,!?;:"\'-') not in stop_words
    }

    # Find missing words
    missing = list(ideal_words - answer_words)

    # Return only if significant gaps (> 3 missing words)
    return missing if len(missing) > 3 else []
```

**Performance**:
- Time complexity: O(n + m) where n, m = word counts
- Expected time: < 10ms for typical answers (100-500 words)

**Edge Cases**:
- Empty `ideal_answer`: Returns `[]`
- Empty `answer_text`: Returns all ideal words (if > 3)
- Punctuation handling: Stripped before comparison

---

## Method 3: `_determine_gap_severity()`

**Purpose**: Map LLM severity string to GapSeverity enum

**Reference**: `process_answer_adaptive.py` lines 364-380

**Location**: Add after `_detect_keyword_gaps()`

**Implementation**:
```python
def _determine_gap_severity(
    self,
    concept: str,
    gaps_dict: dict[str, Any],
) -> GapSeverity:
    """Determine gap severity from LLM response.

    Maps LLM severity string to GapSeverity enum.
    Defaults to MODERATE if invalid/missing.

    Args:
        concept: The missing concept (unused, for signature compatibility)
        gaps_dict: Gaps dictionary from LLM
            Format: {"severity": "minor" | "moderate" | "major", ...}

    Returns:
        GapSeverity enum value
    """
    severity_str = gaps_dict.get("severity", "moderate")
    try:
        return GapSeverity(severity_str.lower())
    except ValueError:
        logger.warning(f"Invalid severity '{severity_str}', defaulting to MODERATE")
        return GapSeverity.MODERATE
```

**Error Handling**:
- Invalid severity string: Defaults to `GapSeverity.MODERATE`
- Missing severity key: Defaults to `GapSeverity.MODERATE`

---

## Method 4: `_build_followup_context_from_state()` (NEW)

**Purpose**: Build FollowUpEvaluationContext from workflow state (no DB queries)

**Reference**: Adapted from `process_answer_adaptive.py` lines 397-462

**Location**: Add after `_determine_gap_severity()`

**Key Differences from Original**:
- **Original**: Queries DB for answers, evaluations, follow-ups
- **New**: Extracts data from `ConversationState`

**Implementation**:
```python
def _build_followup_context_from_state(
    self,
    state: ConversationState,
) -> FollowUpEvaluationContext | None:
    """Build follow-up evaluation context from workflow state.

    Extracts previous evaluations, gaps, and scores from state
    (no database queries).

    Args:
        state: Current conversation state

    Returns:
        FollowUpEvaluationContext if follow-up question, None if main question
    """
    # Check if this is a follow-up question
    parent_question_id = state.get("parent_question_id")
    if not parent_question_id:
        return None  # Main question, no context needed

    # Extract IDs
    current_q_id = state.get("current_question_id")
    if not current_q_id:
        logger.warning("No current_question_id in state for follow-up context")
        return None

    # Get follow-up count (attempt number)
    followup_count = state.get("followup_count", 0)
    attempt_number = followup_count  # 2 or 3

    # Extract previous evaluations from state
    evaluations_dicts = state.get("evaluations", [])
    previous_evaluations: list[Evaluation] = []

    for eval_dict in evaluations_dicts:
        try:
            # Filter evaluations for current question chain
            eval_q_id = eval_dict.get("question_id")
            if eval_q_id in [parent_question_id, current_q_id]:
                evaluation = Evaluation(**eval_dict)
                previous_evaluations.append(evaluation)
        except Exception as exc:
            logger.warning(f"Failed to parse evaluation from state: {exc}")
            continue

    # Sort by created_at
    previous_evaluations.sort(key=lambda e: e.created_at)

    # Extract cumulative gaps from state
    gap_concepts = state.get("cumulative_gaps", [])
    cumulative_gaps: list[ConceptGap] = []

    # Create ConceptGap objects from concepts
    for concept in gap_concepts:
        # Use first evaluation ID as placeholder (will be updated)
        eval_id = previous_evaluations[0].id if previous_evaluations else uuid4()
        gap = ConceptGap(
            evaluation_id=eval_id,
            concept=concept,
            severity=GapSeverity.MODERATE,  # Default severity
            resolved=False,
            created_at=datetime.utcnow(),
        )
        cumulative_gaps.append(gap)

    # Extract ideal_answer from current_question in state
    current_question = state.get("current_question", {})
    ideal_answer = current_question.get("ideal_answer", "")

    if not ideal_answer:
        logger.warning("No ideal_answer in state for follow-up context")

    # Extract previous scores
    previous_scores = [e.final_score for e in previous_evaluations]

    # Build context
    try:
        context = FollowUpEvaluationContext(
            parent_question_id=UUID(parent_question_id),
            follow_up_question_id=UUID(current_q_id),
            attempt_number=attempt_number,
            previous_evaluations=previous_evaluations,
            cumulative_gaps=cumulative_gaps,
            previous_scores=previous_scores,
            parent_ideal_answer=ideal_answer,
        )

        logger.debug(
            f"Follow-up context built: attempt={attempt_number}, "
            f"prev_evals={len(previous_evaluations)}, gaps={len(cumulative_gaps)}"
        )

        return context

    except Exception as exc:
        logger.error(f"Failed to build follow-up context: {exc}", exc_info=True)
        return None
```

**Error Handling**:
- Missing `parent_question_id`: Returns `None` (main question)
- Invalid evaluation dicts: Skips with warning log
- Missing `ideal_answer`: Logs warning, uses empty string
- Context creation failure: Returns `None`, logs error

**Performance**:
- No DB queries (all data from state)
- Time complexity: O(n) where n = number of evaluations
- Expected time: < 5ms

---

## Import Updates

**Add to imports** (after line 23):
```python
from ...domain.models.evaluation import ConceptGap, GapSeverity, FollowUpEvaluationContext
```

**Additional imports needed** (if not already present):
```python
from typing import Any
from uuid import UUID, uuid4
from datetime import datetime
```

---

## Testing Strategy (Manual)

Since tests are skipped per user request, manual verification:

### 1. Test `_detect_keyword_gaps()`

**Test Case 1: Significant gaps**
```python
ideal = "Event loop handles asynchronous tasks using callbacks and promises"
answer = "Event loop handles tasks"
# Expected: ["asynchronous", "callbacks", "promises"] (or similar)
```

**Test Case 2: No gaps**
```python
ideal = "Event loop handles async tasks"
answer = "Event loop manages async operations"
# Expected: [] (< 4 missing words)
```

### 2. Test `_detect_gaps_hybrid()`

**Test Case: LLM confirmation**
```python
# Requires LLM call - verify logs:
# - "Gap detection: keyword_gaps=3"
# - "Gaps confirmed by LLM: ['async', 'callback']"
```

### 3. Test `_build_followup_context_from_state()`

**Test Case 1: Main question**
```python
state = {"parent_question_id": None, ...}
context = workflow._build_followup_context_from_state(state)
# Expected: None
```

**Test Case 2: Follow-up question**
```python
state = {
    "parent_question_id": "uuid-123",
    "current_question_id": "uuid-456",
    "followup_count": 2,
    "evaluations": [{"question_id": "uuid-123", ...}],
    "cumulative_gaps": ["async", "callback"],
    "current_question": {"ideal_answer": "..."},
}
context = workflow._build_followup_context_from_state(state)
# Expected: FollowUpEvaluationContext with attempt_number=2, 2 gaps
```

---

## Success Criteria

✅ All 4 methods added without syntax errors
✅ Imports added correctly
✅ No runtime errors when called with valid state
✅ Logging statements present
✅ Error handling for edge cases
✅ Type hints match domain models

---

## Code Review Checklist

- [ ] Stop words list matches reference (38 words)
- [ ] Keyword threshold is > 3 (not >= 3)
- [ ] `_build_followup_context_from_state` returns `None` for main questions
- [ ] UUID conversion handles string IDs from state
- [ ] Evaluation dict parsing uses try/except
- [ ] Gap severity defaults to MODERATE on error
- [ ] All methods have docstrings
- [ ] Logging uses appropriate levels (DEBUG/INFO/WARNING/ERROR)

---

## Next Phase

After Phase 1 completion, proceed to:
- **Phase 2**: Update `_evaluate_answer_node` to use new helper methods
