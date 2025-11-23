# Phase 2: Message Standardization

**Phase ID:** phase-02-message-standardization
**Parent Plan:** 251124-0452-workflow-legacy-parity
**Priority:** HIGH
**Estimated Effort:** 4-6 hours
**Owner:** TBD
**Status:** Not Started
**Depends On:** Phase 1 (Critical UX Fixes)

## Overview

Standardize WebSocket message formats between workflow and legacy paths to ensure:
1. Follow-up questions use distinct message type (`"follow_up_question"` not `"question"`)
2. All metadata fields included (parent_question_id, generated_reason, order_in_sequence)
3. Frontend can distinguish and style follow-ups differently from main questions
4. Client code works identically regardless of backend path

## Issues Addressed

### Issue #4: Different Message Type Names
**Source:** INCONSISTENCIES_ANALYSIS.md Line 152-201
**Impact:** MEDIUM - Frontend can't style follow-ups, missing metadata
**Priority:** P1

## Current State Analysis

### Legacy Message Format (session_orchestrator.py)

```python
# Main question
{
    "type": "question",
    "question_id": str(question.id),
    "text": question.text,
    "question_type": question.question_type,
    "difficulty": question.difficulty,
    "index": interview.current_question_index,
    "total": total_questions,
    "audio_data": audio_data,
}

# Follow-up question
{
    "type": "follow_up_question",  # ← DISTINCT TYPE
    "question_id": str(follow_up.id),
    "parent_question_id": str(parent_question_id),  # ← Metadata
    "text": follow_up.text,
    "generated_reason": follow_up.generated_reason,  # ← Metadata
    "order_in_sequence": follow_up.order_in_sequence,  # ← Metadata
    "audio_data": audio_data,
}
```

### Workflow Current Format (interview_handler.py - WRONG)

```python
# Both main and follow-up use same type
{
    "type": "question",  # ← NO DISTINCTION
    "question": result.get("question"),
    "question_id": result.get("question_id"),
    "has_more": result.get("has_more"),
    "audio_data": audio_data,  # Added in Phase 1
}
```

## Implementation Tasks

### Task 2.1: Add Question Type Detection (1.5 hours)

**File:** `src/adapters/api/websocket/interview_handler.py`

**Changes:**

```python
# Add helper method to detect question type

def _detect_question_type(
    self,
    question_dict: dict[str, Any],
) -> str:
    """Detect if question is main or follow-up from workflow result.

    Args:
        question_dict: Question dictionary from workflow state

    Returns:
        "question" for main questions, "follow_up_question" for follow-ups
    """
    # Check for follow-up indicators
    if question_dict.get("question_type") == "FOLLOW_UP":
        return "follow_up_question"

    # Check for parent_question_id presence (follow-ups only)
    if "parent_question_id" in question_dict and question_dict["parent_question_id"]:
        return "follow_up_question"

    # Check for follow-up metadata fields
    if "order_in_sequence" in question_dict:
        return "follow_up_question"

    # Default: main question
    return "question"


def _format_question_message(
    self,
    question_dict: dict[str, Any],
    question_id: str,
    has_more: bool,
    audio_data: str | None,
) -> dict[str, Any]:
    """Format question message based on type (main or follow-up).

    Args:
        question_dict: Question data from workflow
        question_id: Question ID string
        has_more: Whether more questions available
        audio_data: Base64 TTS audio

    Returns:
        Formatted message dict matching legacy format
    """
    msg_type = self._detect_question_type(question_dict)

    if msg_type == "follow_up_question":
        # Follow-up format (matches legacy)
        return {
            "type": "follow_up_question",
            "question_id": question_id,
            "parent_question_id": question_dict.get("parent_question_id"),
            "text": question_dict.get("text"),
            "generated_reason": question_dict.get("generated_reason"),
            "order_in_sequence": question_dict.get("order_in_sequence"),
            "audio_data": audio_data,
        }
    else:
        # Main question format (matches legacy)
        return {
            "type": "question",
            "question_id": question_id,
            "text": question_dict.get("text"),
            "question_type": question_dict.get("question_type"),
            "difficulty": question_dict.get("difficulty"),
            "index": question_dict.get("index", 0),  # From workflow state
            "total": question_dict.get("total", 0),  # From workflow state
            "audio_data": audio_data,
        }
```

**Testing:**
```python
# tests/unit/adapters/api/websocket/test_interview_handler.py

def test_detect_question_type_main():
    """Test detection of main question."""
    handler = create_handler_fixture()

    question_dict = {
        "text": "Explain SOLID",
        "question_type": "TECHNICAL",
        "difficulty": "MEDIUM",
    }

    msg_type = handler._detect_question_type(question_dict)
    assert msg_type == "question"


def test_detect_question_type_followup():
    """Test detection of follow-up question."""
    handler = create_handler_fixture()

    question_dict = {
        "text": "Can you explain SOLID in more detail?",
        "question_type": "FOLLOW_UP",
        "parent_question_id": "abc123",
        "order_in_sequence": 1,
    }

    msg_type = handler._detect_question_type(question_dict)
    assert msg_type == "follow_up_question"


def test_format_question_message_main():
    """Test formatting main question message."""
    handler = create_handler_fixture()

    question_dict = {
        "text": "Explain SOLID",
        "question_type": "TECHNICAL",
        "difficulty": "MEDIUM",
        "index": 2,
        "total": 5,
    }

    message = handler._format_question_message(
        question_dict=question_dict,
        question_id="q123",
        has_more=True,
        audio_data="base64audio",
    )

    assert message["type"] == "question"
    assert message["question_id"] == "q123"
    assert message["text"] == "Explain SOLID"
    assert message["question_type"] == "TECHNICAL"
    assert message["difficulty"] == "MEDIUM"
    assert message["index"] == 2
    assert message["total"] == 5
    assert message["audio_data"] == "base64audio"


def test_format_question_message_followup():
    """Test formatting follow-up question message."""
    handler = create_handler_fixture()

    question_dict = {
        "text": "Can you explain SOLID in more detail?",
        "question_type": "FOLLOW_UP",
        "parent_question_id": "parent123",
        "generated_reason": "Gap detected: SOLID principles",
        "order_in_sequence": 2,
    }

    message = handler._format_question_message(
        question_dict=question_dict,
        question_id="followup456",
        has_more=True,
        audio_data="base64audio",
    )

    assert message["type"] == "follow_up_question"
    assert message["question_id"] == "followup456"
    assert message["parent_question_id"] == "parent123"
    assert message["text"] == "Can you explain SOLID in more detail?"
    assert message["generated_reason"] == "Gap detected: SOLID principles"
    assert message["order_in_sequence"] == 2
    assert message["audio_data"] == "base64audio"
```

---

### Task 2.2: Update Workflow to Include Metadata (2 hours)

**File:** `src/application/workflows/interview_conversation_workflow.py`

**Changes:**

```python
# In _generate_followup_node() (around line 700-712)

# Update current_question dict to include all metadata
return {
    "current_question_id": str(followup.id),
    "current_question": {
        "id": str(followup.id),
        "text": followup.text,
        "question_type": "FOLLOW_UP",  # ← Type indicator
        "ideal_answer": ideal_answer,
        "parent_question_id": str(parent_question_id),  # ← Metadata
        "generated_reason": followup.generated_reason,  # ← Metadata
        "order_in_sequence": followup.order_in_sequence,  # ← Metadata
    },
    "parent_question_id": str(parent_question_id),
    "followup_count": followup_count + 1,
    "needs_followup": False,
}


# In _next_question_or_complete_node() (around line 770-776)

# Add index and total to main question dict
return {
    "current_question_id": str(question.id),
    "current_question": {
        **question.model_dump(mode="json"),  # All question fields
        "index": interview.current_question_index,  # ← NEW
        "total": total,  # ← NEW
    },
    "parent_question_id": None,
    "followup_count": 0,
    "cumulative_gaps": [],
    "has_more_questions": has_more,
}


# In _start_session_node() (around line 267-269)

# Add index and total to first question
return {
    "current_question_id": str(question.id),
    "current_question": {
        **question.model_dump(mode="json"),
        "index": interview.current_question_index,  # ← NEW
        "total": total_questions,  # ← NEW
    },
    "messages": [],
    "has_more_questions": has_more,
    # ... rest of state
}
```

**Testing:**
```python
# tests/unit/application/workflows/test_interview_conversation_workflow.py

async def test_followup_question_includes_metadata():
    """Test that generated follow-up includes all metadata."""
    workflow = create_workflow_fixture()
    state = create_state_with_pending_followup()

    result = await workflow._generate_followup_node(state)

    question = result["current_question"]
    assert question["question_type"] == "FOLLOW_UP"
    assert "parent_question_id" in question
    assert "generated_reason" in question
    assert "order_in_sequence" in question
    assert question["order_in_sequence"] == state["followup_count"] + 1


async def test_main_question_includes_progress():
    """Test that main question includes index/total."""
    workflow = create_workflow_fixture()
    state = create_state_for_next_question()

    result = await workflow._next_question_or_complete_node(state)

    question = result["current_question"]
    assert "index" in question
    assert "total" in question
    assert question["index"] >= 0
    assert question["total"] > 0
```

---

### Task 2.3: Update Message Sending Logic (1.5 hours)

**File:** `src/adapters/api/websocket/interview_handler.py`

**Changes:**

```python
# Replace existing question sending (around line 154-178)

if result.get("question"):
    question_dict = result["question"]
    question_text = question_dict.get("text", "")

    # Generate TTS audio (from Phase 1)
    audio_data = await self._generate_tts_audio(
        text=question_text,
        container=self.container,
    )

    # Format message based on type
    message = self._format_question_message(
        question_dict=question_dict,
        question_id=result.get("question_id"),
        has_more=result.get("has_more"),
        audio_data=audio_data,
    )

    await manager.send_message(interview_id, message)

    logger.info(
        f"Sent {message['type']}: {result.get('question_id')}",
        extra={
            "interview_id": str(interview_id),
            "question_id": result.get("question_id"),
            "type": message["type"],
        },
    )
```

**Testing:**
```python
# tests/integration/api/websocket/test_interview_handler.py

async def test_main_question_format(websocket_client, interview_id):
    """Test main question message format matches legacy."""
    await websocket_client.send_json({
        "type": "start_session",
        "interview_id": str(interview_id),
    })

    msg = await websocket_client.receive_json()

    # Assert main question format
    assert msg["type"] == "question"
    assert "question_id" in msg
    assert "text" in msg
    assert "question_type" in msg
    assert "difficulty" in msg
    assert "index" in msg
    assert "total" in msg
    assert "audio_data" in msg


async def test_followup_question_format(websocket_client, interview_id):
    """Test follow-up question message format matches legacy."""
    # Start session and answer first question
    await start_and_answer_first_question(websocket_client, interview_id)

    # Answer with gaps to trigger follow-up
    await websocket_client.send_json({
        "type": "answer",
        "text": "Brief incomplete answer",
    })

    # Receive evaluation
    await websocket_client.receive_json()

    # Receive follow-up question
    followup_msg = await websocket_client.receive_json()

    # Assert follow-up format
    assert followup_msg["type"] == "follow_up_question"
    assert "question_id" in followup_msg
    assert "parent_question_id" in followup_msg
    assert "text" in followup_msg
    assert "generated_reason" in followup_msg
    assert "order_in_sequence" in followup_msg
    assert "audio_data" in followup_msg
```

---

### Task 2.4: Create Message Schema Validation (1 hour)

**File:** `tests/integration/test_message_schemas.py` (NEW)

**Changes:**

```python
"""WebSocket message schema validation tests.

Ensures all message types conform to documented schemas
and match between legacy and workflow paths.
"""
import pytest
from pydantic import BaseModel, Field, validator


class QuestionMessage(BaseModel):
    """Main question message schema."""
    type: str = Field(..., pattern="^question$")
    question_id: str
    text: str
    question_type: str
    difficulty: str
    index: int = Field(..., ge=0)
    total: int = Field(..., ge=1)
    audio_data: str | None


class FollowUpQuestionMessage(BaseModel):
    """Follow-up question message schema."""
    type: str = Field(..., pattern="^follow_up_question$")
    question_id: str
    parent_question_id: str
    text: str
    generated_reason: str
    order_in_sequence: int = Field(..., ge=1, le=3)
    audio_data: str | None


class EvaluationMessage(BaseModel):
    """Evaluation message schema."""
    type: str = Field(..., pattern="^evaluation$")
    answer_id: str
    score: float = Field(..., ge=0.0, le=100.0)
    feedback: str
    strengths: list[str]
    weaknesses: list[str]
    gaps: list[dict]


async def test_workflow_question_schema_valid(workflow_messages):
    """Test workflow main question matches schema."""
    question_msg = find_message_by_type(workflow_messages, "question")
    QuestionMessage(**question_msg)  # Will raise ValidationError if invalid


async def test_workflow_followup_schema_valid(workflow_messages):
    """Test workflow follow-up matches schema."""
    followup_msg = find_message_by_type(workflow_messages, "follow_up_question")
    if followup_msg:  # May not exist if no gaps
        FollowUpQuestionMessage(**followup_msg)


async def test_workflow_evaluation_schema_valid(workflow_messages):
    """Test workflow evaluation matches schema."""
    eval_msg = find_message_by_type(workflow_messages, "evaluation")
    EvaluationMessage(**eval_msg)


async def test_legacy_vs_workflow_message_schemas_match(
    legacy_messages, workflow_messages
):
    """Test that message schemas match between paths."""
    legacy_question = find_message_by_type(legacy_messages, "question")
    workflow_question = find_message_by_type(workflow_messages, "question")

    # Both must conform to same schema
    QuestionMessage(**legacy_question)
    QuestionMessage(**workflow_question)

    # Assert field equality (excluding dynamic values)
    assert legacy_question["type"] == workflow_question["type"]
    assert "question_id" in legacy_question and "question_id" in workflow_question
    assert "audio_data" in legacy_question and "audio_data" in workflow_question
```

---

## Testing Strategy

### Unit Tests (6 new tests)
1. `test_detect_question_type_main()` - Main question detection
2. `test_detect_question_type_followup()` - Follow-up detection
3. `test_format_question_message_main()` - Main question formatting
4. `test_format_question_message_followup()` - Follow-up formatting
5. `test_followup_question_includes_metadata()` - Workflow metadata
6. `test_main_question_includes_progress()` - Index/total fields

### Integration Tests (2 new tests)
1. `test_main_question_format()` - End-to-end main question
2. `test_followup_question_format()` - End-to-end follow-up

### Schema Validation Tests (4 new tests)
1. `test_workflow_question_schema_valid()` - Main question schema
2. `test_workflow_followup_schema_valid()` - Follow-up schema
3. `test_workflow_evaluation_schema_valid()` - Evaluation schema
4. `test_legacy_vs_workflow_message_schemas_match()` - Parity check

**Total:** 12 new tests

## Acceptance Criteria

- [ ] **AC1:** Follow-up questions use `"type": "follow_up_question"` (not `"question"`)
- [ ] **AC2:** Follow-up messages include parent_question_id, generated_reason, order_in_sequence
- [ ] **AC3:** Main questions include index, total fields
- [ ] **AC4:** All question messages include audio_data field
- [ ] **AC5:** Message detection logic distinguishes main vs follow-up correctly
- [ ] **AC6:** All 12 schema validation tests pass
- [ ] **AC7:** Parity test shows identical message schemas between paths
- [ ] **AC8:** Frontend can style follow-ups differently (verify manually)

## Rollout Checklist

- [ ] Code reviewed and approved
- [ ] All 12 tests passing
- [ ] Manual testing with frontend client
- [ ] WebSocket API documentation updated with schemas
- [ ] Frontend team notified of message format changes
- [ ] Migration guide for existing clients (if needed)
- [ ] Monitoring dashboard shows message type distribution

## Dependencies

### Upstream
- **Phase 1** must be complete (TTS audio generation required)

### Downstream
- Frontend may need updates if currently parsing generic `"question"` type
- Documentation updates required for API consumers

## Risks & Mitigation

### Risk 1: Frontend Breaking Changes
**Impact:** High | **Likelihood:** Medium
**Description:** Existing frontend may expect `"type": "question"` for all questions
**Mitigation:**
- Check frontend code for hardcoded "question" type
- Add backwards compatibility flag if needed
- Gradual rollout with monitoring

### Risk 2: Metadata Missing in Edge Cases
**Impact:** Medium | **Likelihood:** Low
**Description:** Workflow state may not always include metadata fields
**Mitigation:**
- Add default values in `_format_question_message()`
- Log warnings for missing metadata
- Validate workflow state schema in tests

### Risk 3: Message Size Increase
**Impact:** Low | **Likelihood:** Low
**Description:** Additional metadata increases message payload
**Mitigation:**
- Monitor WebSocket message sizes
- Consider compression for large payloads
- Profile network usage in production

## Estimated Timeline

| Task | Effort | Start | End |
|------|--------|-------|-----|
| 2.1: Question Type Detection | 1.5h | Day 2 09:00 | Day 2 10:30 |
| 2.2: Workflow Metadata | 2h | Day 2 10:30 | Day 2 12:30 |
| Lunch | - | Day 2 12:30 | Day 2 13:30 |
| 2.3: Message Sending Update | 1.5h | Day 2 13:30 | Day 2 15:00 |
| 2.4: Schema Validation Tests | 1h | Day 2 15:00 | Day 2 16:00 |
| Buffer | 1h | Day 2 16:00 | Day 2 17:00 |

**Total:** 6 hours (1 day)

## Success Metrics

- **Message Type Accuracy:** 100% of follow-ups use correct type
- **Metadata Completeness:** 100% of follow-ups include all 3 metadata fields
- **Schema Validation Pass Rate:** 100% (12/12 tests)
- **Frontend Compatibility:** Zero frontend errors after rollout
- **Zero Regressions:** No existing functionality broken

## Next Phase

Once Phase 2 complete:
- Proceed to **Phase 3: Gap Strategy Alignment**
- Decide DB-query vs state-based gap accumulation
- Implement unified gap tracking logic
- See [phase-03-gap-strategy.md](phase-03-gap-strategy.md)
