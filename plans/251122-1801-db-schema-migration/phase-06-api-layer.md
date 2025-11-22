# Phase 6: API Layer

## Context Links

- **Parent Plan**: [plan.md](./plan.md)
- **Previous Phase**: [phase-05-infrastructure.md](./phase-05-infrastructure.md)
- **Next Phase**: [phase-07-testing.md](./phase-07-testing.md)
- **Dependencies**: Phases 2-5 complete

---

## Overview

**Date**: 2025-11-22
**Priority**: 🟡 High
**Estimated Duration**: 1-2 hours
**Implementation Status**: ⏳ Pending
**Review Status**: ⏳ Pending

**Description**: Update REST/WebSocket endpoints to work with new schema.

---

## Key Insights

- API responses should not expose `question_ids` array (no longer exists)
- Use DTOs to shape responses
- WebSocket handler must use `get_current_question` method
- Optional: Create prompt template editing endpoints (UI support)

---

## Related Code Files

### Files to Modify
- `src/adapters/api/rest/interview_routes.py`
- `src/adapters/api/websocket/interview_handler.py`

### Files to Create (Optional)
- `src/adapters/api/rest/prompt_template_routes.py`

---

## Implementation Steps

### Step 1: Update `interview_routes.py` (30 mins)

```python
@router.get("/api/interviews/{interview_id}")
async def get_interview(interview_id: UUID):
    """Get interview details."""
    interview = await interview_repo.get_by_id(interview_id)

    # Get questions via junction table
    interview_questions = await interview_repo.get_interview_questions(interview_id)

    return {
        "id": interview.id,
        "candidate_id": interview.candidate_id,
        "status": interview.status,
        # Instead of question_ids array:
        "total_questions": len(interview_questions),
        "questions_asked": sum(1 for iq in interview_questions if iq.asked_at is not None),
        "current_question_index": interview.current_question_index
    }
```

### Step 2: Update `interview_handler.py` (20 mins)

```python
class InterviewWebSocketHandler:
    async def get_next_question(self, interview_id: UUID):
        """Get next question for WebSocket client."""
        # Use new repository method
        question = await self.interview_repo.get_current_question(interview_id)

        if question:
            return {
                "type": "question",
                "data": {
                    "id": question.id,
                    "text": question.text,
                    "difficulty": question.difficulty.value
                }
            }
        else:
            return {"type": "interview_complete"}
```

### Step 3: Create `prompt_template_routes.py` (optional - 30 mins)

```python
@router.get("/api/prompts/{template_id}")
async def get_prompt_for_editing(template_id: UUID):
    """Get prompt template decomposed fields for UI editing."""
    template = await prompt_repo.get_by_id(template_id)

    return {
        "id": template.id,
        "name": template.name,
        "version": template.version,
        "system_prompt": template.system_prompt,
        "user_template": template.user_template,
        "input_variables": template.input_variables,
        "output_schema": template.output_schema,
        "temperature": float(template.temperature),
        "max_tokens": template.max_tokens
    }

@router.patch("/api/prompts/{template_id}")
async def update_prompt(template_id: UUID, request: PromptEditRequest):
    """Update prompt template (creates new version)."""
    # Update editable fields
    # DB automatically regenerates template_json
    pass
```

---

## Todo List

- [ ] Update `interview_routes.py`: Remove `question_ids` from responses
- [ ] Update `interview_handler.py`: Use `get_current_question`
- [ ] Create `prompt_template_routes.py` (optional)
- [ ] Run API tests: `pytest tests/integration/api/`

---

## Success Criteria

- ✅ REST endpoints return correct data
- ✅ WebSocket handler works
- ✅ No breaking API changes (or documented)
- ✅ API tests pass

---

## Next Steps

**On Success**: Proceed to [Phase 7: Testing](./phase-07-testing.md)

---

**Phase Status**: ⏳ Pending
