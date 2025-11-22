# Phase 7: Testing

## Context Links

- **Parent Plan**: [plan.md](./plan.md)
- **Previous Phases**: Phases 2-6 (all code updated)
- **Next Phase**: [phase-08-documentation.md](./phase-08-documentation.md)
- **Dependencies**: All code changes complete

---

## Overview

**Date**: 2025-11-22
**Priority**: 🔴 Critical
**Estimated Duration**: 2-3 hours
**Implementation Status**: ⏳ Pending
**Review Status**: ⏳ Pending

**Description**: Update/create tests for all layers. Ensure >85% coverage maintained.

---

## Key Insights

- Must test new domain models (`CVSkill`, `InterviewQuestion`)
- Repository tests must validate JOIN queries
- Use case tests must verify new method calls
- Integration tests ensure end-to-end functionality
- Coverage must remain >85%

---

## Related Code Files

### Files to Create (New Tests)
- `tests/unit/domain/test_cv_skill.py`
- `tests/unit/domain/test_interview_question.py`

### Files to Update (Existing Tests)
- `tests/unit/domain/test_cv_analysis.py`
- `tests/unit/domain/test_question.py` (test ENUMs)
- `tests/unit/domain/test_interview.py`
- `tests/integration/adapters/persistence/test_cv_analysis_repository.py`
- `tests/integration/adapters/persistence/test_interview_repository.py`
- `tests/integration/adapters/persistence/test_question_repository.py`
- `tests/unit/application/use_cases/test_analyze_cv.py`
- `tests/unit/application/use_cases/test_plan_interview.py`
- `tests/integration/api/test_interview_routes.py`

---

## Implementation Steps

### Step 1: Create Domain Model Tests (30 mins)

```python
# tests/unit/domain/test_cv_skill.py
def test_cv_skill_creation():
    skill = CVSkill(
        id=uuid4(),
        cv_analysis_id=uuid4(),
        skill_name="Python",
        proficiency_level=ProficiencyLevel.ADVANCED,
        years_of_experience=3.5,
        is_primary=True
    )
    assert skill.is_expert() == False
    assert skill.has_experience(2.0) == True

# tests/unit/domain/test_interview_question.py
def test_interview_question_mark_asked():
    iq = InterviewQuestion(
        id=uuid4(),
        interview_id=uuid4(),
        question_id=uuid4(),
        sequence_order=0
    )
    iq.mark_asked()
    assert iq.is_asked() == True
```

### Step 2: Update Repository Tests (45 mins)

```python
# tests/integration/adapters/persistence/test_cv_analysis_repository.py
async def test_get_cv_analysis_with_skills():
    # Create CV analysis
    cv = await cv_repo.create(cv_analysis)

    # Add skills
    skill1 = CVSkill(cv_analysis_id=cv.id, skill_name="Python", proficiency_level=ProficiencyLevel.EXPERT)
    await cv_repo.add_skill(skill1)

    # Fetch with skills
    result = await cv_repo.get_by_id(cv.id)
    assert len(result.skills) == 1
    assert result.skills[0].skill_name == "Python"

# tests/integration/adapters/persistence/test_interview_repository.py
async def test_add_question_to_interview():
    # Add question
    iq = await interview_repo.add_question(interview_id, question_id, sequence_order=0)
    assert iq.sequence_order == 0

    # Get current question
    question = await interview_repo.get_current_question(interview_id)
    assert question is not None
```

### Step 3: Update Use Case Tests (30 mins)

```python
# tests/unit/application/use_cases/test_analyze_cv.py
async def test_analyze_cv_creates_skills(mocker):
    # Mock cv_repo.add_skill
    mock_add_skill = mocker.patch.object(cv_repo, 'add_skill')

    # Execute use case
    result = await use_case.execute(cv_file_path, candidate_id)

    # Verify add_skill called
    assert mock_add_skill.called
```

### Step 4: Update API Tests (30 mins)

```python
# tests/integration/api/test_interview_routes.py
async def test_get_interview_returns_question_counts(client):
    # Create interview with questions
    # ...

    response = await client.get(f"/api/interviews/{interview_id}")
    assert response.status_code == 200
    data = response.json()
    assert "total_questions" in data
    assert "questions_asked" in data
    # Should NOT have question_ids array
    assert "question_ids" not in data
```

### Step 5: Run Full Test Suite (15 mins)

```bash
# Run all tests with coverage
pytest --cov=src --cov-report=html --cov-report=term -v

# Check coverage report
# Expected: >85% coverage maintained
```

---

## Todo List

- [ ] Create `test_cv_skill.py`
- [ ] Create `test_interview_question.py`
- [ ] Update domain model tests (3 files)
- [ ] Update repository tests (3 files)
- [ ] Update use case tests (2 files)
- [ ] Update API tests (1 file)
- [ ] Run full test suite
- [ ] Verify coverage >85%
- [ ] Fix any failing tests

---

## Success Criteria

- ✅ All tests passing
- ✅ Coverage >85% maintained
- ✅ New models fully tested
- ✅ Repository JOIN queries tested
- ✅ No regression in existing functionality

---

## Next Steps

**On Success**: Proceed to [Phase 8: Documentation](./phase-08-documentation.md)
**On Failure**: Debug failing tests, improve coverage

---

**Phase Status**: ⏳ Pending
