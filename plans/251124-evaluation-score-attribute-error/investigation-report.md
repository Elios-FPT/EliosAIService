# Investigation Report: AttributeError 'Evaluation' object has no attribute 'score'

**Date:** 2025-11-24
**Investigator:** Debug Agent
**Priority:** High
**Status:** Root Cause Identified

---

## Executive Summary

**Root Cause:** Schema mismatch between `AnswerEvaluation` (LLM response) and `Evaluation` (domain model). Mock analytics adapter attempts to access `.score` attribute that doesn't exist on `Evaluation` entities.

**Impact:**
- Mock analytics methods fail when processing Answer entities with Evaluation relationships
- Breaks interview statistics calculation and performance tracking
- Affects multiple features: interview summary, candidate performance history, skill analytics

**Solution Priority:**
1. **IMMEDIATE:** Fix mock analytics adapter to use `.final_score` instead of `.score`
2. **PREVENTIVE:** Add type checking to catch attribute mismatches
3. **VERIFICATION:** Add integration tests for analytics with real Evaluation entities

---

## Technical Analysis

### 1. Domain Model Structure

**AnswerEvaluation (Value Object)** - `src/domain/models/answer.py:10`
```python
class AnswerEvaluation(BaseModel):
    score: float = Field(ge=0.0, le=100.0)  # ✅ Has .score
    semantic_similarity: float
    completeness: float
    relevance: float
    ...
```

**Evaluation (Entity)** - `src/domain/models/evaluation.py:38`
```python
class Evaluation(BaseModel):
    id: UUID
    raw_score: float = Field(ge=0.0, le=100.0)    # ✅ Before penalty
    penalty: float = Field(ge=-15.0, le=0.0)      # ✅ Attempt penalty
    final_score: float = Field(ge=0.0, le=100.0)  # ✅ raw_score + penalty
    # ❌ NO .score ATTRIBUTE
    ...
```

**Key Difference:**
- `AnswerEvaluation` (temporary LLM response) → `.score`
- `Evaluation` (persisted entity with penalty system) → `.raw_score`, `.penalty`, `.final_score`

### 2. Error Locations (3 files affected)

#### A. Mock Analytics Adapter ⚠️ PRIMARY ISSUE
**File:** `src/adapters/mock/mock_analytics.py`

**Line 69-72:** `get_interview_analytics()`
```python
scores = [
    a.evaluation.score  # ❌ AttributeError: 'Evaluation' object has no attribute 'score'
    for a in answers
    if a.evaluation is not None
]
```

**Line 144:** `get_candidate_performance_history()`
```python
a.evaluation.score  # ❌ Same error
```

**Line 159:** `get_candidate_performance_history()`
```python
if answer.evaluation.score < 70.0:  # ❌ Same error
```

**Line 238:** `get_skill_analytics()`
```python
score = answer.evaluation.score  # ❌ Same error
```

#### B. Workflow State Management ✅ NO ISSUE (False alarm)
**File:** `src/application/workflows/interview_conversation_workflow.py`

**Line 620:** `_update_memory_node()`
```python
"score": state["evaluations"][-1]["final_score"]  # ✅ Correct - dict access
```

**Line 656:** `_decide_followup_node()`
```python
latest_eval_dict = state["evaluations"][-1]  # ✅ Correct - dict
evaluation = Evaluation(**latest_eval_dict)  # ✅ Reconstructs from dict
```

**Line 741:** `_generate_followup_question_node()`
```python
latest_eval = state["evaluations"][-1]  # ✅ Correct - dict access
```

**Analysis:** Workflow stores evaluations as dicts via `model_dump(mode="json")` at line 501. LangGraph checkpoint restoration preserves dict format (JSON serialization). NO object/dict confusion.

#### C. Test Files ⚠️ LEGACY ISSUE
**File:** `tests/unit/use_cases/test_process_answer_adaptive.py:171`
```python
assert answer.evaluation.score > 0  # ❌ Wrong attribute
```

### 3. Checkpoint Restoration Analysis

**State Definition** (line 62):
```python
evaluations: list[dict[str, Any]]  # ✅ Declared as list of dicts
```

**Serialization** (line 501):
```python
"evaluations": state.get("evaluations", []) + [saved_evaluation.model_dump(mode="json")]
# ✅ Explicitly converts Evaluation → dict
```

**LangGraph Behavior:**
- Uses `AsyncPostgresSaver` with JSON serialization (PostgreSQL JSONB column)
- TypedDict annotations are for type hints only, NOT runtime deserialization
- Checkpoint restoration returns plain dicts, NOT Pydantic models
- **Conclusion:** User's hypothesis about checkpoint deserialization is INCORRECT

### 4. Data Flow Trace

```
LLM Adapter
    ↓
AnswerEvaluation (has .score)
    ↓
Workflow creates Evaluation entity (line 437-465)
    raw_score=llm_eval.score     ← Maps .score to .raw_score
    final_score=llm_eval.score   ← Initial value (recalculated by apply_penalty)
    ↓
Apply penalty (line 468)
    evaluation.apply_penalty(attempt_number)
    final_score = raw_score + penalty  ← Final score calculation
    ↓
Save to DB (line 491)
    saved_evaluation = await self.evaluation_repo.save(evaluation)
    ↓
Store in state as dict (line 501)
    saved_evaluation.model_dump(mode="json")
    ↓
Mock analytics retrieves Answer entities (via repo)
    answer.evaluation  ← Loaded from DB as Evaluation entity
    answer.evaluation.score  ← ❌ AttributeError
```

### 5. Why Mock Analytics Fails

**Reason:** Mock analytics receives `Answer` entities from repository with `evaluation` relationship loaded as `Evaluation` entity (NOT dict).

**Workflow state vs Repository entities:**
- Workflow state: evaluations stored as dicts (checkpoint serialization)
- Repository queries: evaluations loaded as Pydantic Evaluation entities

**Mock analytics calls repository:**
```python
async def get_interview_analytics(self, interview_id: UUID) -> dict[str, Any]:
    answers = await self.answer_repo.get_by_interview_id(interview_id)
    # answers[i].evaluation is Evaluation entity (NOT dict)
    scores = [a.evaluation.score for a in answers]  # ❌ Tries to access .score
```

---

## Code Locations Requiring Fixes

### 1. Mock Analytics Adapter (4 locations)

**File:** `src/adapters/mock/mock_analytics.py`

| Line | Method | Current Code | Fix |
|------|--------|-------------|-----|
| 69 | `get_interview_analytics()` | `a.evaluation.score` | `a.evaluation.final_score` |
| 144 | `get_candidate_performance_history()` | `a.evaluation.score` | `a.evaluation.final_score` |
| 159 | `get_candidate_performance_history()` | `answer.evaluation.score` | `answer.evaluation.final_score` |
| 238 | `get_skill_analytics()` | `answer.evaluation.score` | `answer.evaluation.final_score` |

### 2. Test Files (1 location)

**File:** `tests/unit/use_cases/test_process_answer_adaptive.py`

| Line | Current Code | Fix |
|------|-------------|-----|
| 171 | `answer.evaluation.score` | `answer.evaluation.final_score` |

---

## Recommended Fix Approach

### Option 1: Direct Attribute Replacement (Recommended ✅)
**Rationale:** Simple, type-safe, aligns with domain model.

**Changes:**
1. Replace all `.score` → `.final_score` in mock analytics
2. Update test assertions
3. Verify no other adapters access `.score`

**Pros:**
- Single source of truth (`final_score` accounts for penalties)
- Type-safe (mypy will catch future errors)
- Minimal changes (5 lines total)

**Cons:**
- None

### Option 2: Add Computed Property (Discouraged ❌)
```python
class Evaluation(BaseModel):
    @property
    def score(self) -> float:
        return self.final_score  # Alias for backward compatibility
```

**Pros:**
- Backward compatible with existing code

**Cons:**
- Introduces duplicate attribute names (confusing)
- Hides penalty logic (`.score` vs `.final_score` semantic difference)
- Violates domain model clarity

---

## Verification Steps

### 1. Static Analysis
```bash
# Find all .score accesses on Evaluation
rg "evaluation\.score" --type py src/
rg "eval\.score" --type py src/
mypy src/adapters/mock/mock_analytics.py
```

### 2. Unit Tests
```bash
# Test mock analytics with real Evaluation entities
pytest tests/unit/adapters/test_mock_analytics.py -v
```

### 3. Integration Tests
```bash
# Test workflow end-to-end with analytics
pytest tests/integration/test_interview_workflow_analytics.py -v
```

### 4. Type Checking
```bash
mypy src/ --strict
```

---

## Preventive Measures

### 1. Add Type Annotations
```python
# mock_analytics.py
from src.domain.models.answer import Answer
from src.domain.models.evaluation import Evaluation

async def get_interview_analytics(self, interview_id: UUID) -> dict[str, Any]:
    answers: list[Answer] = await self.answer_repo.get_by_interview_id(interview_id)
    # mypy will catch a.evaluation.score error if Evaluation has no .score
```

### 2. Add Integration Test
```python
# tests/integration/test_mock_analytics_evaluation.py
async def test_analytics_with_evaluation_entity():
    """Ensure mock analytics works with Evaluation entities from repo."""
    # Create Answer with Evaluation relationship
    answer = Answer(...)
    answer.evaluation = Evaluation(
        raw_score=85.0,
        penalty=-5.0,
        final_score=80.0
    )
    await repo.save(answer)

    # Test analytics
    stats = await analytics.get_interview_analytics(interview_id)
    assert stats["avg_score"] == 80.0  # Should use final_score
```

### 3. Documentation Update
Add to `docs/code-standards.md`:
```markdown
## Domain Model: Evaluation Scoring

- `AnswerEvaluation.score` (LLM response) → temporary, no penalty
- `Evaluation.raw_score` (entity) → LLM score before penalty
- `Evaluation.final_score` (entity) → score after penalty (use this for analytics)

⚠️ **Never access** `evaluation.score` - attribute does not exist.
```

---

## Unresolved Questions

1. **Do real (non-mock) analytics adapters exist?** If yes, check for same error.
   - Search: `src/adapters/analytics/` or `src/adapters/monitoring/`

2. **Are there other places accessing Answer.evaluation.score?**
   - Already searched codebase - only found in docs/plans/tests
   - Need to verify WebSocket handlers and REST API responses

3. **Should penalty calculation be exposed in analytics?**
   - Current: Only `final_score` visible
   - Consider: Expose `raw_score` + `penalty` separately for transparency
   - Decision needed: Product requirement

4. **Is AnswerEvaluation still needed?**
   - Could consolidate: LLM adapter return Evaluation directly
   - Trade-off: Evaluation has DB-specific fields (id, created_at)
   - Keep separate: Clean separation between adapter response and domain entity

---

## Files Analyzed

1. ✅ `src/domain/models/evaluation.py` - Confirmed no `.score` attribute
2. ✅ `src/domain/models/answer.py` - Confirmed `AnswerEvaluation` has `.score`
3. ✅ `src/adapters/mock/mock_analytics.py` - Found 4 error locations
4. ✅ `src/application/workflows/interview_conversation_workflow.py` - Confirmed NO dict/object confusion
5. ✅ `tests/unit/use_cases/test_process_answer_adaptive.py` - Found 1 test error
6. ✅ `src/infrastructure/database/langgraph_checkpointer.py` - Confirmed JSON serialization

---

## Next Steps

1. ✅ **IMMEDIATE:** Fix mock analytics (5 lines)
2. ⏳ **SHORT-TERM:** Add integration test for analytics + Evaluation
3. ⏳ **MEDIUM-TERM:** Run mypy strict mode on adapters/
4. ⏳ **LONG-TERM:** Consider API response standardization (final_score vs score naming)

---

**Report End**
