# Phase 04: Update DTOs and API

**Duration**: 1-2 hours
**Priority**: Medium
**Dependencies**: Phase 02
**Status**: ✅ DONE
**Completed**: 2025-12-10 02:37:32

## Objective

Update DTOs and API responses to include speaking_score and theoretical_score breakdown.

## Current State

- `EvaluationMessage` DTO has `speaking_score` field but it's always None
- API responses don't show speaking score breakdown

## Changes Required

### 1. Update EvaluateAnswerOutput DTO

**File**: `src/application/dto/interview/evaluate_answer_dto.py`

Ensure evaluation payload includes:
- `theoretical_score`
- `speaking_score`
- `final_score` (combined)

### 2. Update EvaluationMessage DTO

**File**: `src/application/dto/websocket_dto.py`

Already has fields, but ensure they're populated:
- `theoretical_score` (currently optional)
- `speaking_score` (currently optional)

### 3. Update Workflow Response

**File**: `src/application/workflows/interview_conversation_workflow.py`

Ensure evaluation dict includes speaking scores when sending to client.

### 4. Update REST API Responses

**File**: `src/adapters/api/rest/interview_routes.py` (if exists)

Include speaking scores in evaluation responses.

## Testing

- DTO validation tests
- API response format tests
- WebSocket message format tests

## Success Criteria

- API responses include theoretical_score and speaking_score
- WebSocket messages include score breakdown
- DTOs validate correctly

