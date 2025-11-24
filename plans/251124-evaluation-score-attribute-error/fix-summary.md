# Quick Fix Summary: Evaluation.score AttributeError

**Issue:** Mock analytics tries to access `.score` on `Evaluation` entity (doesn't exist)
**Correct Attribute:** `.final_score` (includes penalty calculation)

---

## Required Changes (5 lines)

### 1. Mock Analytics Adapter
**File:** `src/adapters/mock/mock_analytics.py`

**Line 69:**
```python
# ❌ BEFORE
scores = [a.evaluation.score for a in answers if a.evaluation is not None]

# ✅ AFTER
scores = [a.evaluation.final_score for a in answers if a.evaluation is not None]
```

**Line 144:**
```python
# ❌ BEFORE
a.evaluation.score

# ✅ AFTER
a.evaluation.final_score
```

**Line 159:**
```python
# ❌ BEFORE
if answer.evaluation.score < 70.0:

# ✅ AFTER
if answer.evaluation.final_score < 70.0:
```

**Line 238:**
```python
# ❌ BEFORE
score = answer.evaluation.score

# ✅ AFTER
score = answer.evaluation.final_score
```

### 2. Test File
**File:** `tests/unit/use_cases/test_process_answer_adaptive.py`

**Line 171:**
```python
# ❌ BEFORE
assert answer.evaluation.score > 0

# ✅ AFTER
assert answer.evaluation.final_score > 0
```

---

## Verification Commands

```bash
# 1. Find remaining .score accesses
rg "evaluation\.score" --type py src/

# 2. Run tests
pytest tests/unit/adapters/test_mock_analytics.py -v
pytest tests/unit/use_cases/test_process_answer_adaptive.py -v

# 3. Type check
mypy src/adapters/mock/mock_analytics.py
```

---

## Why This Error Occurred

**Domain Model Design:**
- `AnswerEvaluation` (LLM response) → `.score` (temporary value)
- `Evaluation` (entity) → `.raw_score` + `.penalty` → `.final_score`

**Mock analytics was written before penalty system existed**, accessing old `.score` attribute.

**Root cause:** Schema evolution without adapter update.

---

## Prevention

Add to pre-commit checks:
```bash
# Catch invalid Evaluation attribute access
rg "evaluation\.score[^_]" src/ && echo "ERROR: Use .final_score instead" && exit 1
```
