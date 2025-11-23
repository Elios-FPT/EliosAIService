# Documentation Update Report: Workflow-Legacy Parity

**Report ID**: 251124-docs-specialist-to-implementation-team-documentation-update
**Date**: 2025-11-24
**From**: Documentation Specialist
**To**: Implementation Team
**Subject**: Documentation updates for Phase 1-2 workflow-legacy parity implementation

## Executive Summary

Updated technical documentation to reflect Phase 1-2 changes from workflow-legacy parity implementation. Two files modified: `system-architecture.md` (WebSocket protocol + workflow evaluation flow) and `codebase-summary.md` (helper functions).

**Files Updated**:
- `docs/system-architecture.md` (3 sections modified)
- `docs/codebase-summary.md` (2 sections modified)

**Documentation Scope**: WebSocket API contract changes, evaluation return flow, TTS integration, message formatting logic.

---

## Changes Made

### 1. WebSocket API Message Schemas (system-architecture.md)

**Section**: WebSocket API → Protocol
**Lines Modified**: 1758-1796

**Changes**:

#### Main Question Message
Added new fields:
- `index`: Question index in sequence (e.g., 0, 1, 2)
- `total`: Total questions planned (e.g., 5)
- `audio_data`: Base64-encoded TTS audio (Phase 1)

```json
{
  "type": "question",
  "index": 0,              // NEW
  "total": 5,              // NEW
  "audio_data": "base64_encoded_tts_audio"  // NEW
}
```

#### Follow-up Question Message (NEW)
Distinct message type with follow-up metadata:
- `type`: "follow_up_question" (Phase 2 - standardization)
- `parent_question_id`: Links to main question
- `generated_reason`: Why follow-up was generated
- `order_in_sequence`: 1st, 2nd, 3rd follow-up
- `audio_data`: Base64-encoded TTS audio

```json
{
  "type": "follow_up_question",  // NEW: Distinct type
  "parent_question_id": "uuid",  // NEW
  "generated_reason": "Candidate missed key concept: X",  // NEW
  "order_in_sequence": 1,        // NEW
  "audio_data": "base64_encoded_tts_audio"
}
```

#### Evaluation Message
Added `gaps` field:
- Array of concept gaps (concept, severity, resolved)
- Used for follow-up generation

```json
{
  "type": "evaluation",
  "gaps": [                // NEW
    {
      "concept": "Error handling",
      "severity": "MODERATE",
      "resolved": false
    }
  ]
}
```

---

### 2. WebSocket Features List (system-architecture.md)

**Section**: WebSocket API → Features
**Lines Modified**: 1822-1839

**Changes**:
- Updated feature descriptions to reflect Phase 1-2 changes
- Added "Workflow Path Changes" subsection documenting parity fixes:
  - Evaluation feedback sent after answer processing (Phase 1)
  - TTS audio generated for all questions (Phase 1)
  - Follow-up decisions use domain method `is_adaptive_complete()` (Phase 1)
  - Message formats standardized (Phase 2)

**New Section**:
```markdown
**Workflow Path Changes** (v0.3.0 - Legacy Parity):
- Evaluation feedback sent after answer processing (Phase 1)
- TTS audio generated for all questions (main + follow-up, Phase 1)
- Follow-up decisions use domain method `is_adaptive_complete()` (Phase 1)
- Message formats standardized (Phase 2):
  - Main questions: `type: "question"` with `index`, `total`, `audio_data`
  - Follow-ups: `type: "follow_up_question"` with `parent_question_id`, `generated_reason`, `order_in_sequence`
```

---

### 3. InterviewConversationWorkflow Evaluation Flow (system-architecture.md)

**Section**: LangGraph Workflow Architecture → NEW subsection
**Lines Added**: 2415-2550 (135 lines)

**New Subsection**: "InterviewConversationWorkflow: Evaluation Flow"

**Content**:

#### Evaluation Return Pattern Diagram
ASCII diagram showing flow from WebSocket handler → workflow → evaluation node → extraction helper → response.

**Key Components**:
1. `_handle_with_workflow`: Receives answer, calls `process_answer()`
2. `process_answer()`: Resumes from checkpoint, executes workflow nodes
3. `_evaluate_answer_node`: Creates Answer/Evaluation entities, saves to DB
4. `_extract_latest_evaluation`: Extracts evaluation from state, formats as dict
5. WebSocket handler: Sends evaluation message, generates TTS, formats question message

#### Architecture Decisions (AD-1, AD-4)
Documented:
- **AD-1**: Evaluation returned in response (not state) - avoids state bloat
- **AD-4**: Follow-up decision uses `is_adaptive_complete()` domain method

#### TTS Integration
Code example + explanation:
- Location: `interview_handler.py` (presentation layer)
- Rationale: TTS is presentation concern, keep workflow domain-focused
- Implementation: `_generate_tts_audio()` helper function

```python
async def _generate_tts_audio(text: str, container: Container) -> str | None:
    """Generate TTS audio and encode as base64."""
    tts = container.text_to_speech_port()
    audio_bytes = await tts.synthesize_speech(text)
    return base64.b64encode(audio_bytes).decode("utf-8")
```

#### Message Formatting (Phase 2)
Code examples for:
- `_detect_question_type()`: Identify main vs follow-up
- `_format_question_message()`: Format WebSocket message based on type

**Helper Functions Documented**:
- `_detect_question_type()`: Identify main vs follow-up from question dict
- `_format_question_message()`: Format WebSocket message based on type
- `_generate_tts_audio()`: Generate TTS audio, return base64 string (Phase 1)
- `_extract_latest_evaluation()`: Extract evaluation from workflow state (Phase 1)

#### Parity Status
- ✅ Phase 1 Complete: Evaluation feedback, TTS audio, follow-up decision logic
- ✅ Phase 2 Complete: Message standardization, metadata fields
- ⚠️ Phase 3 Pending: Gap accumulation strategy alignment
- ⚠️ Phase 4 Pending: State sync, retry logic, audio file path storage
- ⚠️ Phase 5 Pending: Parity tests, production rollout

---

### 4. Codebase Summary: WebSocket Handler (codebase-summary.md)

**Section**: Project Structure → adapters/api/websocket
**Lines Modified**: 137-145

**Changes**:
- Updated `interview_handler.py` description to reflect dual path support
- Added inline comments documenting 4 new helper functions (Phase 1-2)

**Before**:
```
└── interview_handler.py  # Simplified WebSocket I/O handler
```

**After**:
```
└── interview_handler.py  # WebSocket handler (workflow + legacy paths)
    # NEW helpers (Phase 1-2):
    # - _generate_tts_audio(): TTS synthesis + base64 encoding
    # - _extract_latest_evaluation(): Extract eval from workflow state
    # - _detect_question_type(): Identify main vs follow-up
    # - _format_question_message(): Format WebSocket message by type
```

---

### 5. Codebase Summary: Workflow Files (codebase-summary.md)

**Section**: Project Structure → application/workflows
**Lines Modified**: 92-102

**Changes**:
- Updated file count from 5 to 6 files
- Added `interview_conversation_workflow.py` entry with inline documentation

**Added Entry**:
```
├── interview_conversation_workflow.py # Conversation/QA workflow (NEW v0.3.0)
│   # Replaces session_orchestrator for answer evaluation + follow-ups
│   # - process_answer() returns evaluation dict (Phase 1)
│   # - _extract_latest_evaluation() helper (Phase 1)
│   # - Uses is_adaptive_complete() for follow-up decisions
```

**Section**: Key Components → Workflows
**Lines Modified**: 361-370

**Added Description**:
```markdown
**InterviewConversationWorkflow** (`interview_conversation_workflow.py`) (NEW v0.3.0):
- Conversation/QA phase workflow (replaces session_orchestrator)
- State: interview_id, messages, current_question, evaluations, followup_count, cumulative_gaps
- Nodes: evaluate_answer, update_memory, decide_followup, generate_followup, get_next_question, complete_interview
- Phase 1-2 features:
  - Returns evaluation dict in process_answer() response
  - _extract_latest_evaluation() helper extracts from state
  - Uses is_adaptive_complete() domain method for follow-up decisions
  - Supports main + follow-up question metadata (index, total, parent_question_id, etc.)
- Edges: conditional routing based on follow-up needs + question availability
```

---

## Documentation Coverage

### API Contract Changes (Phase 1-2)

**WebSocket Message Schemas**:
- ✅ Main question message format (`type: "question"`)
- ✅ Follow-up question message format (`type: "follow_up_question"`)
- ✅ Evaluation message format (with `gaps` field)
- ✅ Metadata fields documented (index, total, parent_question_id, generated_reason, order_in_sequence)
- ✅ TTS audio field (`audio_data`)

**Workflow Architecture**:
- ✅ Evaluation return flow diagram
- ✅ TTS integration point
- ✅ Message formatting logic
- ✅ Architecture decisions (AD-1, AD-4)
- ✅ Helper functions documented

**Codebase Structure**:
- ✅ `interview_handler.py` helper functions
- ✅ `interview_conversation_workflow.py` entry added
- ✅ Workflow description with Phase 1-2 features

---

## Files Not Updated

**Rationale for exclusion**:

1. **project-overview-pdr.md**: No product requirements changed, only implementation details
2. **code-standards.md**: No new coding patterns introduced, existing standards followed
3. **design-guidelines.md**: No design changes
4. **deployment-guide.md**: No deployment changes
5. **project-roadmap.md**: Phase tracking handled in plan.md

---

## Verification Checklist

- ✅ WebSocket message schemas reflect Phase 1-2 changes
- ✅ New message types documented (follow_up_question)
- ✅ Metadata fields documented (index, total, parent_question_id, etc.)
- ✅ TTS audio field documented
- ✅ Evaluation return flow documented with diagram
- ✅ TTS integration point documented
- ✅ Message formatting logic documented
- ✅ Helper functions documented in both files
- ✅ Architecture decisions documented (AD-1, AD-4)
- ✅ Parity status documented

---

## Unresolved Questions

None. All Phase 1-2 changes fully documented.

---

## Recommendations

1. **Frontend Verification**: Share updated WebSocket schemas with frontend team for contract validation
2. **API Versioning**: Consider versioning WebSocket API if breaking changes expected in Phase 3+
3. **Test Documentation**: Document parity tests in separate testing guide (Phase 5)
4. **Gap Strategy**: Document Phase 3 gap accumulation strategy decision in architecture docs once finalized

---

## Appendix: Files Modified

### system-architecture.md
- Lines 1758-1796: WebSocket message schemas
- Lines 1822-1839: WebSocket features list
- Lines 2415-2550: InterviewConversationWorkflow evaluation flow (NEW section)

### codebase-summary.md
- Lines 92-102: Workflow files list (interview_conversation_workflow.py added)
- Lines 137-145: WebSocket handler helper functions
- Lines 361-370: InterviewConversationWorkflow description (NEW entry)

**Total Lines Added/Modified**: ~180 lines across 2 files

---

**Report Status**: ✅ Complete
**Next Action**: Share with implementation team for review
