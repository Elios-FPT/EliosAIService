# Voice Metrics Integration Plan

**Created**: 2025-12-10
**Status**: Planning
**Priority**: High
**Estimated Time**: 1-2 days

## Overview

Integrate voice metrics into answer evaluation to combine theoretical (LLM) and speaking (voice) scores. Currently, voice metrics are collected but not used in evaluation, and aggregate scoring has bugs.

## Goals

- Integrate `CombineEvaluationUseCase` into `EvaluateAnswerUseCase`
- Store `speaking_score` and `theoretical_score` in Evaluation entity
- Fix aggregate scoring in `CompleteInterviewUseCase`
- Update DTOs and API responses to include speaking scores
- Ensure voice metrics affect final answer scores (70% theoretical + 30% speaking)

## Current State Analysis

### Issues Found

1. **Voice metrics collected but not used**: `EvaluateAnswerUseCase` stores voice_metrics in Answer but doesn't use them for scoring
2. **CombineEvaluationUseCase exists but unused**: Has correct logic but never invoked
3. **Aggregate scoring broken**: Looks for non-existent `voice_metrics.get("overall_score")`
4. **Evaluation entity missing fields**: No `speaking_score` or `theoretical_score` fields

### Current Flow

```
STT Adapter → Voice Metrics → Answer Model (stored) → ❌ Not used in evaluation
                                                      → ❌ Aggregate scoring broken
```

### Target Flow

```
STT Adapter → Voice Metrics → CombineEvaluationUseCase → Evaluation Entity
                                                         → speaking_score
                                                         → theoretical_score
                                                         → final_score (combined)
```

## Implementation Phases

1. **[Phase 01: Update Evaluation Entity](phase-01-update-evaluation-entity.md)** - Add speaking_score and theoretical_score fields
   - Status: ✅ DONE
   - Progress: 100%
   - Completed: 2025-12-10 01:53:11

2. **[Phase 02: Integrate CombineEvaluationUseCase](phase-02-integrate-combine-evaluation.md)** - Use in EvaluateAnswerUseCase
   - Status: ✅ DONE
   - Progress: 100%
   - Completed: 2025-12-10 02:15:00

3. **[Phase 03: Fix Aggregate Scoring](phase-03-fix-aggregate-scoring.md)** - Fix CompleteInterviewUseCase
   - Status: ✅ DONE
   - Progress: 100%
   - Completed: 2025-12-10 02:30:00

4. **[Phase 04: Update DTOs and API](phase-04-update-dtos-api.md)** - Include speaking scores in responses
   - Status: ✅ DONE
   - Progress: 100%
   - Completed: 2025-12-10 02:37:32

4. **[Phase 04: Update DTOs and API](phase-04-update-dtos-api.md)** - Include speaking scores in responses
   - Status: Pending
   - Progress: 0%

5. **[Phase 05: Testing](phase-05-testing.md)** - Unit tests and integration tests
   - Status: Pending
   - Progress: 0%

## Key Decisions

- ✅ Use existing `CombineEvaluationUseCase` (70/30 split)
- ✅ Store both `theoretical_score` and `speaking_score` in Evaluation
- ✅ `final_score` = combined weighted score (not just LLM score)
- ✅ Text-only answers: 100% theoretical weight (no speaking score)

## Related Documentation

- [Codebase Summary](../docs/codebase-summary.md)
- [System Architecture](../docs/system-architecture.md)
- [Code Standards](../docs/code-standards.md)

