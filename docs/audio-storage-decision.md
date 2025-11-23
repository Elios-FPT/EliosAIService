# Audio Storage Decision

## Overview

Decision document on whether to store `audio_file_path` in Answer entity for workflow path.

## Current State

### Answer Model
The `Answer` entity includes `audio_file_path` field (line 50 in `src/domain/models/answer.py`):

```python
class Answer(BaseModel):
    audio_file_path: str | None = None  # If voice answer
```

### Legacy Path
Stores audio files to disk and records path:
```python
answer = Answer(
    audio_file_path="/path/to/audio/file.wav",  # Stored on disk
    # ...
)
```

### Workflow Path
Currently does NOT store audio files:
```python
answer = Answer(
    audio_file_path=None,  # Not storing files
    # ...
)
```

## Analysis

### Use Cases for Stored Audio

1. **STT Answer Audio** (Candidate's voice answer)
   - Used for: Speech-to-text transcription
   - Status: Currently transcribed in real-time via streaming STT
   - Storage need: LOW (already transcribed to text)

2. **TTS Question Audio** (AI interviewer's voice)
   - Used for: Playing questions to candidate
   - Status: Generated inline, sent via WebSocket as base64
   - Storage need: LOW (can regenerate on demand)

3. **Audit/Review**
   - Used for: Reviewing interview recordings
   - Status: Not currently implemented
   - Storage need: MEDIUM (future feature)

4. **Voice Quality Analysis**
   - Used for: Analyzing speaking metrics
   - Status: Metrics extracted during STT, stored in `voice_metrics`
   - Storage need: LOW (metrics already captured)

## Decision

**DO NOT store audio files in workflow path (current approach is correct).**

### Rationale

1. **Real-Time Processing** - STT transcribes audio in real-time to text, no need to store raw audio
2. **TTS Regeneration** - Question audio can be regenerated from text on demand
3. **Storage Costs** - Audio files are large (~10MB per 5-min interview)
4. **Voice Metrics Captured** - Quality metrics already stored in `voice_metrics` dict
5. **Future-Proof** - If audit/review needed later, can add S3/R2 storage separately

### Exceptions

If audit/review requirements emerge:
- Store to object storage (S3/R2), not local filesystem
- Store URL/key instead of file path
- Implement separately from core interview flow
- Add retention policy (30-90 days)

## Implementation Status

### Workflow Path
✅ **Correct** - Does not store `audio_file_path`
```python
answer = Answer(
    text=transcribed_text,
    is_voice=True,
    audio_file_path=None,  # Correct: no storage
    voice_metrics=extracted_metrics,
)
```

### Legacy Path
⚠️ **Deprecated** - Stores files to local disk (not scalable)
```python
answer = Answer(
    audio_file_path="/tmp/audio/interview_123_q5.wav",  # Deprecated
)
```

## Parity Assessment

**No parity issue** - Legacy audio storage is deprecated feature, not a regression.

| Feature | Legacy | Workflow | Parity Status |
|---------|--------|----------|---------------|
| STT transcription | ✅ Stored audio, then transcribed | ✅ Real-time streaming STT | ✅ IMPROVED |
| TTS playback | ✅ Generated, stored, sent file path | ✅ Generated, sent base64 | ✅ EQUIVALENT |
| Voice metrics | ✅ Extracted from file | ✅ Extracted from stream | ✅ EQUIVALENT |
| Audio review/audit | ❌ Files stored but no UI | ❌ Not implemented | ✅ EQUIVALENT |

## Recommendation

**Workflow path is correct.** No action needed.

If future requirements demand audio storage:
1. Use object storage (Cloudflare R2, AWS S3)
2. Store URL/key in `audio_file_path`
3. Implement async upload (non-blocking)
4. Add retention policy
5. Update Answer model documentation

## Related Documents

- [System Architecture](./system-architecture.md) - Audio processing flow
- [Answer Model](../src/domain/models/answer.py) - Entity definition
- [Phase 4 Plan](../plans/251124-0452-workflow-legacy-parity/phase-04-polish.md) - Implementation plan
