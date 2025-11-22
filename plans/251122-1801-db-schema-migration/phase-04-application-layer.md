# Phase 4: Application Layer

## Context Links

- **Parent Plan**: [plan.md](./plan.md)
- **Previous Phase**: [phase-03-adapters-layer.md](./phase-03-adapters-layer.md)
- **Next Phase**: [phase-05-infrastructure.md](./phase-05-infrastructure.md)
- **Dependencies**: Phase 3 (repositories updated)

---

## Overview

**Date**: 2025-11-22
**Priority**: 🟡 High
**Estimated Duration**: 1-2 hours
**Implementation Status**: ⏳ Pending
**Review Status**: ⏳ Pending

**Description**: Update use cases and DTOs to use new repository methods and domain models.

---

## Key Insights

- Use cases orchestrate domain logic + repository calls
- Must use new repository methods (`add_question_to_interview`, `get_current_question`)
- DTOs may need updates for API responses (no question_ids array)
- Keep use cases simple (single responsibility)

---

## Requirements

### Functional Requirements
- Update use cases to call new repository methods
- Create `CVSkill` entities in CV analysis use case
- Use junction table methods in interview planning
- Update DTOs for new response structure

### Non-Functional Requirements
- Maintain use case simplicity
- No breaking changes to public interfaces (if possible)
- Follow existing use case patterns

---

## Related Code Files

### Files to Modify
- `src/application/use_cases/analyze_cv.py`
- `src/application/use_cases/plan_interview.py`
- `src/application/use_cases/get_next_question.py`
- `src/application/dto/interview_dto.py` (optional)

---

## Implementation Steps

### Step 1: Update `analyze_cv.py` (20 mins)

```python
class AnalyzeCVUseCase:
    async def execute(self, cv_file_path: str, candidate_id: UUID) -> CVAnalysis:
        # Extract skills using CV analyzer port
        extracted_skills = await self.cv_analyzer.extract_skills(cv_file_path)

        # Create CV analysis
        cv_analysis = CVAnalysis(
            id=uuid4(),
            candidate_id=candidate_id,
            extracted_text=extracted_text,
            # ... other fields
        )
        await self.cv_repo.create(cv_analysis)

        # Create CVSkill entities and add to repository
        for skill_data in extracted_skills:
            cv_skill = CVSkill(
                id=uuid4(),
                cv_analysis_id=cv_analysis.id,
                skill_name=skill_data['name'],
                proficiency_level=ProficiencyLevel(skill_data.get('proficiency', 'intermediate')),
                years_of_experience=skill_data.get('years'),
                is_primary=skill_data.get('is_primary', False)
            )
            await self.cv_repo.add_skill(cv_skill)  # NEW METHOD

        return await self.cv_repo.get_by_id(cv_analysis.id)  # Fetch with skills
```

### Step 2: Update `plan_interview.py` (20 mins)

```python
class PlanInterviewUseCase:
    async def execute(self, interview_id: UUID, question_ids: list[UUID]) -> Interview:
        # Get interview
        interview = await self.interview_repo.get_by_id(interview_id)

        # Add questions to interview with sequence
        for idx, question_id in enumerate(question_ids):
            await self.interview_repo.add_question(  # NEW METHOD
                interview_id=interview_id,
                question_id=question_id,
                sequence_order=idx
            )

        # Update interview status
        interview.status = "PLANNED"
        await self.interview_repo.update(interview)

        return interview
```

### Step 3: Update `get_next_question.py` (15 mins)

```python
class GetNextQuestionUseCase:
    async def execute(self, interview_id: UUID) -> Question | None:
        # Get current question using new method
        question = await self.interview_repo.get_current_question(interview_id)  # NEW METHOD

        if question:
            # Mark as asked
            interview = await self.interview_repo.get_by_id(interview_id)
            await self.interview_repo.mark_question_asked(  # NEW METHOD
                interview_id=interview_id,
                sequence_order=interview.current_question_index
            )

        return question
```

### Step 4: Update DTOs (optional - 15 mins)

```python
# src/application/dto/interview_dto.py
class InterviewResponseDTO:
    id: UUID
    candidate_id: UUID
    status: str
    # REMOVE: question_ids (no longer stored as array)
    # ADD: total_questions, questions_asked (from junction table)
    total_questions: int
    questions_asked: int
```

---

## Todo List

- [ ] Update `analyze_cv.py`: Create CVSkill entities
- [ ] Update `plan_interview.py`: Use `add_question` method
- [ ] Update `get_next_question.py`: Use `get_current_question`
- [ ] Update DTOs if needed
- [ ] Run use case tests: `pytest tests/unit/application/`

---

## Success Criteria

- ✅ Use cases compile without errors
- ✅ Use cases call new repository methods correctly
- ✅ Unit tests pass
- ✅ No breaking changes to public APIs

---

## Next Steps

**On Success**: Proceed to [Phase 5: Infrastructure](./phase-05-infrastructure.md)
**On Failure**: Debug use case logic

---

**Phase Status**: ⏳ Pending
