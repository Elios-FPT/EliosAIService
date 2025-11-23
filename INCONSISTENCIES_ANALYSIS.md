# Inconsistencies Between Legacy and LangGraph Code Paths

**Analysis Date:** 2025-11-24
**Status:** For Future Fix (Detection Only)

## Overview

This document analyzes behavioral inconsistencies between the legacy session_orchestrator approach and the new LangGraph workflow (InterviewConversationWorkflow) to identify issues that need to be addressed in future iterations.

---

## Critical Issues

### 1. **Missing Evaluation Feedback in WebSocket Messages** ⚠️ HIGH PRIORITY

**Location:**
- Legacy: `session_orchestrator._handle_main_question_answer()` → `_send_evaluation()`
- Workflow: `interview_handler.py:150-152` (TODO comment)

**Issue:**
The LangGraph workflow path **does not send evaluation feedback** to the client after processing an answer.

**Legacy Behavior (session_orchestrator.py:301-302):**
```python
# Send evaluation
await self._send_evaluation(answer, evaluation)
```

**Workflow Behavior (interview_handler.py:149-152):**
```python
# Send evaluation
# Note: Workflow doesn't return evaluation details in process_answer
# Evaluation is handled internally, so we skip this for now
# TODO: Consider returning evaluation result for client display
```

**Impact:**
- Clients using the workflow path receive **no immediate feedback** on answer quality
- No scores, strengths, weaknesses, or improvement suggestions displayed
- Poor UX compared to legacy path

**Fix Required:**
1. Add evaluation data to workflow's `process_answer()` return value
2. Send evaluation message in interview_handler similar to legacy path
3. Format: `{"type": "evaluation", "answer_id": ..., "score": ..., "feedback": ..., "strengths": ..., "weaknesses": ..., "gaps": ...}`

---

### 2. **Follow-Up Decision Logic Differences** ⚠️ MEDIUM PRIORITY

**Location:**
- Legacy: `FollowUpDecisionUseCase.execute()`
- Workflow: `_decide_followup_node()`

**Issue:**
Different break conditions and evaluation criteria between paths.

#### Break Condition Comparison:

| Condition | Legacy (FollowUpDecisionUseCase) | Workflow (_decide_followup_node) |
|-----------|----------------------------------|----------------------------------|
| Max follow-ups | `follow_up_count >= 3` | `followup_count >= 3` ✅ |
| High quality | `evaluation.is_adaptive_complete()` (uses `similarity_score >= 0.8` OR no gaps) | `final_score >= 80.0` ❌ |
| No gaps | Checked via `is_adaptive_complete()` | `len(unresolved_gaps) == 0` ✅ |

**Discrepancy:**

**Legacy uses `is_adaptive_complete()` method:**
```python
# domain/models/evaluation.py:143-155
def is_adaptive_complete(self) -> bool:
    """Check if answer meets adaptive completion criteria.

    Completion criteria:
    - similarity_score >= 0.8 OR
    - no unresolved gaps (has_gaps() returns False)
    """
    if self.similarity_score is not None and self.similarity_score >= 0.8:
        return True
    return not self.has_gaps()
```

**Workflow uses hardcoded threshold:**
```python
# interview_conversation_workflow.py:563
if latest_eval["final_score"] >= 80.0:
    logger.info(f"Score sufficient: {latest_eval['final_score']}")
    return {"needs_followup": False, "followup_reason": "Score sufficient"}
```

**Impact:**
- **Semantic similarity ignored** in workflow path (only checks `final_score`)
- Legacy: Answer with `similarity_score=0.85` → No follow-up (complete)
- Workflow: Same answer with `final_score=75` → Follow-up generated (incomplete)
- **Inconsistent behavior** for candidates with same answers

**Fix Required:**
1. Workflow should use `evaluation.is_adaptive_complete()` method
2. Add similarity_score to workflow state and evaluation dicts
3. Align decision logic exactly with FollowUpDecisionUseCase

---

### 3. **Missing `candidate_id` Field in Answer Entity** ⚠️ LOW PRIORITY

**Location:**
- Legacy: `ProcessAnswerAdaptiveUseCase.execute()` includes `candidate_id`
- Workflow: `_evaluate_answer_node()` missing `candidate_id`

**Issue:**
Answer entity created differently in both paths.

**Legacy (process_answer_adaptive.py:138-147):**
```python
answer = Answer(
    interview_id=interview_id,
    question_id=answer_question_id,  # Use parent question ID for follow-ups
    candidate_id=interview.candidate_id,  # ✅ INCLUDED
    text=answer_text,
    is_voice=bool(audio_file_path),
    audio_file_path=audio_file_path,
    voice_metrics=voice_metrics,
    created_at=datetime.utcnow(),
)
```

**Workflow (interview_conversation_workflow.py:356-363):**
```python
answer = Answer(
    interview_id=interview_id,
    question_id=answer_question_id,  # Use parent question ID for follow-ups
    text=answer_text,
    is_voice=state.get("is_voice_answer", False),
    voice_metrics=state.get("voice_metrics"),
    created_at=datetime.utcnow(),
)
# ❌ Missing: candidate_id, audio_file_path, duration_seconds
```

**Note:** Checked `src/domain/models/answer.py` - Answer model **does NOT have `candidate_id` field**. This appears to be a legacy comment error.

**Impact:**
- Actually **NO IMPACT** - Answer model doesn't have candidate_id field
- But missing `audio_file_path` and `duration_seconds` fields could be an issue

**Fix Required:**
1. Verify if `audio_file_path` should be stored (currently only in legacy path)
2. Consider adding `duration_seconds` tracking for analytics

---

### 4. **Different Message Type Names for Follow-Up Questions** ⚠️ LOW PRIORITY

**Location:**
- Legacy: `session_orchestrator._generate_and_send_followup()`
- Workflow: WebSocket handler message formatting

**Issue:**
Different WebSocket message type identifiers for follow-up questions.

**Legacy (session_orchestrator.py:522-532):**
```python
await self._send_message(
    {
        "type": "follow_up_question",  # ✅ Specific type
        "question_id": str(follow_up.id),
        "parent_question_id": str(parent_question_id),
        "text": follow_up.text,
        "generated_reason": follow_up.generated_reason,
        "order_in_sequence": follow_up.order_in_sequence,
        "audio_data": audio_data,
    }
)
```

**Workflow (interview_handler.py:168-178):**
```python
await manager.send_message(
    interview_id,
    {
        "type": "question",  # ❌ Generic type (same as main question)
        "question": result.get("question"),
        "question_id": result.get("question_id"),
        "has_more": result.get("has_more"),
    },
)
```

**Impact:**
- Clients can't distinguish between main questions and follow-ups in workflow path
- Missing metadata: `parent_question_id`, `generated_reason`, `order_in_sequence`
- No TTS audio data in workflow path
- **Frontend UI can't show different styling** for follow-ups

**Fix Required:**
1. Workflow should detect follow-up vs main question from result
2. Send `"type": "follow_up_question"` with full metadata
3. Generate TTS audio for follow-ups in workflow path
4. Include all fields from legacy format for consistency

---

### 5. **TTS Audio Generation Missing in Workflow Path** ⚠️ MEDIUM PRIORITY

**Location:**
- Legacy: All question sends include `audio_data` field
- Workflow: No TTS audio generation

**Issue:**
Workflow path doesn't generate Text-to-Speech audio for questions.

**Legacy (session_orchestrator.py:518-520):**
```python
tts = self.container.text_to_speech_port()
audio_bytes = await tts.synthesize_speech(follow_up.text)
audio_data = base64.b64encode(audio_bytes).decode("utf-8")
```

**Workflow:**
No TTS generation - questions sent without audio data.

**Impact:**
- Voice-enabled interviews broken in workflow path
- Accessibility issue for visually impaired candidates
- Feature regression from legacy implementation

**Fix Required:**
1. Add TTS generation to workflow nodes or handler
2. Include `audio_data` in all question messages
3. Consider caching TTS audio for performance

---

### 6. **Gap Accumulation Strategy Differences** ⚠️ LOW PRIORITY

**Location:**
- Legacy: `FollowUpDecisionUseCase._accumulate_gaps()`
- Workflow: `_decide_followup_node()`

**Issue:**
Different strategies for accumulating gaps across follow-up attempts.

**Legacy (follow_up_decision.py:128-165):**
```python
async def _accumulate_gaps(
    self,
    follow_ups: list[Any],
    latest_evaluation: Evaluation,
) -> list[str]:
    """Accumulate concept gaps from all follow-up answers."""
    all_gaps = set()

    # Add gaps from latest evaluation
    for gap in latest_evaluation.gaps:
        if not gap.resolved:
            all_gaps.add(gap.concept)

    # Add gaps from previous follow-up evaluations
    for follow_up in follow_ups:
        follow_up_answers = await self.answer_repo.get_by_question_id(follow_up.id)
        for answer in follow_up_answers:
            if answer.evaluation_id:
                evaluation = await self.evaluation_repo.get_by_id(answer.evaluation_id)
                if evaluation:
                    for gap in evaluation.gaps:
                        if not gap.resolved:
                            all_gaps.add(gap.concept)

    return list(all_gaps)
```

**Workflow (interview_conversation_workflow.py:575-580):**
```python
# Accumulate gaps from all evaluations in this cycle
cumulative = state.get("cumulative_gaps", [])
for gap in unresolved_gaps:
    concept = gap.get("concept")
    if concept and concept not in cumulative:
        cumulative.append(concept)
```

**Discrepancy:**
- Legacy: **Queries database** to load ALL previous follow-up evaluations
- Workflow: **Uses state only** (in-memory gaps from current cycle)
- Legacy: More comprehensive, catches gaps from earlier attempts
- Workflow: Faster, but may miss gaps if state is lost/reset

**Impact:**
- Workflow may generate duplicate follow-ups for same gaps
- Inconsistent gap tracking across reconnections (if checkpoint resumed)
- Legacy has better gap history tracking

**Fix Required:**
1. Decide on single strategy (DB query vs state-based)
2. If state-based: Ensure checkpoint preserves full gap history
3. If DB-based: Implement same query logic in workflow

---

## Minor Issues

### 7. **State Initialization Differences**

**Legacy:** Fresh state loaded from DB on each operation (stateless)
**Workflow:** Stateful with checkpointed state (may contain stale data)

**Potential Issue:**
- Workflow state may not reflect latest DB changes if external updates occur
- Example: Admin manually updates interview status → workflow state out of sync

**Fix Required:**
- Add state validation/refresh logic for critical fields
- Reload interview entity from DB at key decision points

---

### 8. **Error Handling and Retry Logic**

**Legacy:** Simple try-catch with immediate error propagation
**Workflow:** Has retry_count in state but not fully utilized

**Issue:**
- Workflow tracks `retry_count` but doesn't implement retry strategy
- Legacy throws errors immediately, workflow may silently fail

**Fix Required:**
- Implement proper retry logic for transient failures
- Add exponential backoff for LLM API calls
- Define max retry thresholds

---

### 9. **Conversation History Management**

**Legacy:** No conversation history tracking
**Workflow:** Maintains conversation memory with truncation (10 messages)

**Difference:**
- Workflow has **better context** for follow-up generation
- Legacy generates follow-ups without previous Q&A context
- This is actually an **improvement** in workflow, not an issue

**Note:** This is a positive difference - keep workflow behavior.

---

## Recommendations

### Immediate Fixes (High Priority)
1. ✅ **Add evaluation feedback to workflow WebSocket messages**
2. ✅ **Align follow-up decision logic with `is_adaptive_complete()` method**
3. ✅ **Add TTS audio generation to workflow path**

### Short-term Fixes (Medium Priority)
4. ✅ **Standardize WebSocket message types for follow-ups**
5. ✅ **Implement gap accumulation strategy (DB vs state-based)**
6. ⚠️ **Add state validation/refresh for critical fields**

### Long-term Improvements (Low Priority)
7. 🔄 **Unify evaluation logic into single shared service**
8. 🔄 **Create integration tests comparing both paths**
9. 🔄 **Document expected behavior as "golden standard"**
10. 🔄 **Gradually deprecate legacy path once workflow is stable**

---

## Testing Strategy

To verify fixes:

1. **Create parallel test suite** running same interview through both paths
2. **Compare outputs:**
   - Evaluation scores and feedback
   - Follow-up generation decisions
   - WebSocket message sequences
   - Gap tracking across multiple attempts
3. **Automated regression tests** to prevent future divergence
4. **Load testing** to verify workflow checkpointing under concurrent users

---

## Conclusion

The LangGraph workflow implementation is **functionally similar** to the legacy approach but has **several critical UX regressions**:

- Missing evaluation feedback messages
- No TTS audio generation
- Simplified follow-up decision logic (ignores similarity score)
- Different WebSocket message formats

These issues should be addressed before enabling the workflow path for production traffic. The workflow's conversation memory feature is a **positive improvement** that should be retained.

**Priority:** Focus on evaluation feedback and TTS audio first, as these directly impact user experience.
