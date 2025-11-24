# Phase 5: LLM Adapters

**Parent**: [Implementation Plan](./plan.md)
**Created**: 2025-11-24
**Duration**: 1-2 hours
**Priority**: Medium
**Status**: ⏳ Pending

---

## Context Links

- [Parent Plan](./plan.md)
- [Phase 4: Application Layer](./phase-04-application-layer.md)
- [Current LangChain Adapter](../../src/adapters/llm/langchain_adapter.py)

---

## Overview

Update `langchain_adapter.py` to remove `candidate_id` and `tokens_used` from execution logging. Only update this adapter (not OpenAI or Azure adapters).

**Goals**:
- Update `log_execution()` calls in `langchain_adapter.py`
- Remove `candidate_id` parameter
- Remove `tokens_used` (use `prompt_tokens` + `completion_tokens`)
- Ensure execution logging works correctly

---

## Key Insights

- Only `langchain_adapter.py` needs updates
- Execution logging must match new schema
- Token calculation from prompt/completion tokens
- No changes to other adapters

---

## Requirements

### Functional Requirements
- Remove `candidate_id` from execution logging
- Remove `tokens_used` from execution logging
- Use `prompt_tokens` + `completion_tokens` for totals if needed
- Update all `log_execution()` calls

### Non-Functional Requirements
- Maintain logging functionality
- Keep error handling intact

---

## Architecture

### Execution Logging Changes

```
log_execution() call:
  - Remove: candidate_id parameter
  - Remove: tokens_used parameter
  - Keep: prompt_tokens, completion_tokens
  - Calculate total if needed: prompt_tokens + completion_tokens
```

### Adapter Scope

```
Update: langchain_adapter.py only
Skip: openai_adapter.py
Skip: azure_openai_adapter.py
```

---

## Related Code Files

**Modified Files**:
- `src/adapters/llm/langchain_adapter.py`

**Unchanged Files**:
- `src/adapters/llm/openai_adapter.py` (no changes)
- `src/adapters/llm/azure_openai_adapter.py` (no changes)

---

## Implementation Steps

### Step 1: Find log_execution() Calls

```bash
# Search for log_execution calls
grep -n "log_execution" src/adapters/llm/langchain_adapter.py
```

### Step 2: Update log_execution() Calls

```python
# Before
await self.prompt_repo.log_execution(
    prompt_template_id=prompt_template.id,
    execution_data={
        "interview_id": context.get("interview_id"),
        "candidate_id": context.get("candidate_id"),  # REMOVE
        "input_variables": variables,
        "output_text": result.get("output_text"),
        "tokens_used": metadata.get("total_tokens"),  # REMOVE
        "prompt_tokens": metadata.get("prompt_tokens"),
        "completion_tokens": metadata.get("completion_tokens"),
        ...
    }
)

# After
await self.prompt_repo.log_execution(
    prompt_template_id=prompt_template.id,
    execution_data={
        "interview_id": context.get("interview_id"),
        # candidate_id: REMOVED
        "input_variables": variables,
        "output_text": result.get("output_text"),
        # tokens_used: REMOVED
        "prompt_tokens": metadata.get("prompt_tokens"),
        "completion_tokens": metadata.get("completion_tokens"),
        ...
    }
)
```

### Step 3: Update _log_execution() Helper

```python
# If _log_execution() helper exists, update it
async def _log_execution(
    self,
    prompt_template: PromptTemplate,
    context: dict[str, Any],
    input_variables: dict,
    output_text: str | None,
    start_time: float,
    success: bool,
    model_response_metadata: dict | None = None,
    error_message: str | None = None,
) -> None:
    """Log execution to database."""
    # Remove candidate_id extraction
    # Remove tokens_used calculation

    execution_data = {
        "interview_id": context.get("interview_id"),
        # candidate_id: REMOVED
        "input_variables": input_variables,
        "output_text": output_text,
        "prompt_tokens": model_response_metadata.get("prompt_tokens") if model_response_metadata else None,
        "completion_tokens": model_response_metadata.get("completion_tokens") if model_response_metadata else None,
        # tokens_used: REMOVED
        "latency_ms": int((time.time() - start_time) * 1000),
        "model_name": model_response_metadata.get("model_name") if model_response_metadata else None,
        "success": success,
        "error_message": error_message,
    }

    await self.prompt_repo.log_execution(
        prompt_template_id=prompt_template.id,
        execution_data=execution_data,
    )
```

### Step 4: Update Tests

- Remove `candidate_id` from test fixtures
- Remove `tokens_used` from test assertions
- Update test expectations

---

## Todo List

- [ ] Find all `log_execution()` calls in `langchain_adapter.py`
- [ ] Update `log_execution()` calls (remove candidate_id, tokens_used)
- [ ] Update `_log_execution()` helper if exists
- [ ] Update adapter tests
- [ ] Verify execution logging works
- [ ] Test with real LLM calls

---

## Success Criteria

- ✅ All `log_execution()` calls updated
- ✅ No references to `candidate_id` or `tokens_used`
- ✅ Execution logging works correctly
- ✅ Tests updated and passing
- ✅ No changes to other adapters

---

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Missing log_execution calls | Low | Comprehensive search |
| Breaking execution logging | Medium | Test with real calls |
| Test failures | Low | Update tests systematically |

---

## Security Considerations

- No security impact
- Ensure execution logging still captures necessary data

---

## Next Steps

- Integration testing across all phases
- Verify end-to-end workflow
- Update documentation

---

## Notes

- **IMPORTANT**: Only update `langchain_adapter.py`
- Do NOT modify `openai_adapter.py` or `azure_openai_adapter.py`
- Execution logging must continue to work for analytics

