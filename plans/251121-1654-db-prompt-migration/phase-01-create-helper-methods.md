# Phase 1: Create Helper Methods

**Phase ID**: 01
**Plan**: 251121-1654-db-prompt-migration
**Estimated Effort**: 1 hour
**Complexity**: LOW
**Status**: PENDING

---

## Objective

Create reusable helper methods in LangChainAdapter to standardize DB prompt loading, eliminating code duplication across 12 methods.

**Principle Applied**: DRY (Don't Repeat Yourself)

---

## Current State Analysis

### Existing Pattern (generate_ideal_answer:268-287)
```python
async def generate_ideal_answer(...):
    start_time = time.time()
    prompt_template = None
    template_json = None
    cache_key = None

    if self.prompt_repo:
        try:
            prompt_template = await self.prompt_repo.get_active_prompt("ideal_answer_generation")
            if prompt_template:
                template_json = prompt_template.template_json
                cache_key = f"{prompt_template.name}:v{prompt_template.version}"
        except Exception as exc:
            logger.warning("Failed loading DB prompt: %s", exc)
            prompt_template = None
            template_json = None

    chain = self._get_or_build_chain("generate_ideal_answer", template_json, cache_key)
    # ... execute chain ...
```

**Issues**:
- 20 lines repeated in EVERY method
- Inconsistent error handling
- Manual cache key construction
- Execution logging not standardized

---

## Implementation Plan

### Step 1: Create `_load_prompt_from_db()` Helper

**Location**: `src/adapters/llm/langchain_adapter.py:119` (after `_get_or_build_chain`)

**Signature**:
```python
async def _load_prompt_from_db(
    self,
    prompt_name: str,
) -> tuple[PromptTemplate | None, dict | None, str | None]:
    """Load prompt from DB with fallback.

    Args:
        prompt_name: DB prompt identifier (e.g., "ideal_answer_generation")

    Returns:
        Tuple of (prompt_template, template_json, cache_key)
        Returns (None, None, None) if DB unavailable or prompt not found

    Example:
        prompt_template, template_json, cache_key = await self._load_prompt_from_db("answer_evaluation")
        chain = self._get_or_build_chain("evaluate_answer", template_json, cache_key)
    """
```

**Implementation**:
```python
async def _load_prompt_from_db(
    self,
    prompt_name: str,
) -> tuple[PromptTemplate | None, dict | None, str | None]:
    """Load prompt from DB with fallback."""
    if not self.prompt_repo:
        return None, None, None

    try:
        prompt_template = await self.prompt_repo.get_active_prompt(prompt_name)
        if not prompt_template:
            logger.info(
                "No active DB prompt for '%s', falling back to PROMPT_REGISTRY",
                prompt_name,
            )
            return None, None, None

        template_json = prompt_template.template_json
        cache_key = f"{prompt_template.name}:v{prompt_template.version}"
        return prompt_template, template_json, cache_key

    except Exception as exc:
        logger.warning(
            "Failed loading DB prompt for '%s': %s. Falling back to PROMPT_REGISTRY.",
            prompt_name,
            exc,
            exc_info=True,  # Include stack trace for debugging
        )
        return None, None, None
```

**Rationale**:
- Single source of truth for DB loading
- Consistent error handling (log warning, return None)
- Cache key standardized
- Returns PromptTemplate for execution logging

---

### Step 2: Enhance `_log_execution()` Helper

**Current Location**: Lines 562-617

**Current Issues**:
- No token extraction from LangChain callbacks
- Only called in generate_ideal_answer
- Missing model response metadata

**Enhancement**:
```python
async def _log_execution(
    self,
    prompt_template: PromptTemplate,  # Changed from raw fields
    context: dict[str, Any],
    input_variables: dict,
    output_text: str | None,
    start_time: float,
    success: bool,
    model_response_metadata: dict | None = None,  # NEW: LangChain metadata
    error_message: str | None = None,
) -> None:
    """Log prompt execution to database.

    Args:
        prompt_template: The PromptTemplate used (from _load_prompt_from_db)
        context: Execution context (interview_id, candidate_id)
        input_variables: Variables passed to prompt
        output_text: LLM output (None if failed)
        start_time: Start timestamp
        success: Whether execution succeeded
        model_response_metadata: LangChain response metadata (for token extraction)
        error_message: Error message if failed
    """
    try:
        latency_ms = int((time.time() - start_time) * 1000)

        # Extract tokens from LangChain metadata
        tokens_used = None
        prompt_tokens = None
        completion_tokens = None

        if model_response_metadata:
            usage = model_response_metadata.get("usage") or model_response_metadata.get("token_usage")
            if usage:
                tokens_used = usage.get("total_tokens")
                prompt_tokens = usage.get("prompt_tokens")
                completion_tokens = usage.get("completion_tokens")

        # Get model name from LangChain model
        model_name = getattr(self.model, 'model_name', getattr(self.model, 'model', 'unknown'))

        await self.prompt_repo.log_execution(
            prompt_template_id=prompt_template.id,
            execution_data={
                "interview_id": context.get("interview_id"),
                "candidate_id": context.get("candidate_id"),
                "input_variables": input_variables,
                "output_text": output_text[:10000] if output_text else None,  # Truncate
                "tokens_used": tokens_used,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "latency_ms": latency_ms,
                "model_name": model_name,
                "success": success,
                "error_message": error_message,
            },
        )
    except Exception as log_error:
        # Don't fail the main operation if logging fails
        logger.error(
            "Failed to log prompt execution for %s: %s",
            prompt_template.name,
            log_error,
            exc_info=True,
        )
```

**Rationale**:
- Extract tokens from LangChain response metadata
- Accept PromptTemplate directly (cleaner API)
- Fail gracefully if logging errors

---

### Step 3: Create Response Metadata Extractor

**Location**: After `_log_execution()` (around line 650)

**Purpose**: Extract metadata from LangChain response for logging

**Implementation**:
```python
def _extract_response_metadata(self, chain_response: Any) -> dict | None:
    """Extract metadata from LangChain chain response.

    LangChain responses may include token usage, model info in various formats.
    This method standardizes extraction across different model providers.

    Args:
        chain_response: Response from chain.ainvoke()

    Returns:
        Dict with keys: usage (token_usage), model_name, etc.
        None if no metadata available
    """
    # LangChain responses can be dict, AIMessage, or raw JSON
    if isinstance(chain_response, dict):
        # Direct dict response (JSON output parser)
        return chain_response.get("_metadata")

    # AIMessage (structured output)
    if hasattr(chain_response, "response_metadata"):
        return chain_response.response_metadata

    # Check for usage_metadata (newer LangChain versions)
    if hasattr(chain_response, "usage_metadata"):
        return {"usage": chain_response.usage_metadata}

    return None
```

**Usage Pattern**:
```python
result = await chain.ainvoke(variables, config)
metadata = self._extract_response_metadata(result)
await self._log_execution(prompt_template, context, variables, output, start_time, True, metadata)
```

---

## Refactored Method Template

**Standard Pattern** (to be applied in Phase 2):

```python
async def example_method(self, arg1: str, context: dict[str, Any]) -> str:
    """Method docstring."""
    start_time = time.time()

    # Step 1: Load DB prompt
    prompt_template, template_json, cache_key = await self._load_prompt_from_db("db_prompt_name")

    # Step 2: Get chain (DB or fallback)
    chain = self._get_or_build_chain("example_method", template_json, cache_key)

    # Step 3: Prepare variables
    variables = {
        "arg1": arg1,
        "context_field": context.get("field", "default"),
    }

    # Step 4: Create config with metadata
    config = self._create_config(context=context, method="example_method")

    # Step 5: Execute chain
    try:
        result = await chain.ainvoke(variables, config)
        metadata = self._extract_response_metadata(result)

        # Step 6: Log execution (if using DB prompt)
        if prompt_template:
            output_text = result.get("output_field")
            await self._log_execution(
                prompt_template=prompt_template,
                context=context,
                input_variables=variables,
                output_text=output_text,
                start_time=start_time,
                success=True,
                model_response_metadata=metadata,
            )

        return result["output_field"]

    except Exception as exc:
        # Log failure
        if prompt_template:
            await self._log_execution(
                prompt_template=prompt_template,
                context=context,
                input_variables=variables,
                output_text=None,
                start_time=start_time,
                success=False,
                error_message=str(exc),
            )
        raise
```

**Lines of Code**:
- Before: 20 lines per method (duplicated)
- After: 3 lines per method (helper calls)
- Savings: 17 lines × 12 methods = **204 lines reduced**

---

## Testing Requirements

### Unit Tests

**File**: `tests/unit/adapters/llm/test_langchain_adapter_helpers.py`

#### Test 1: `test_load_prompt_from_db_success`
```python
async def test_load_prompt_from_db_success(mock_prompt_repo):
    """Test successful DB prompt loading."""
    mock_prompt = PromptTemplate(
        id=uuid4(),
        name="test_prompt",
        version=2,
        template_json={"system": "...", "user_template": "..."},
        created_by="test",
    )
    mock_prompt_repo.get_active_prompt.return_value = mock_prompt

    adapter = LangChainAdapter(model=mock_model, prompt_repository=mock_prompt_repo)
    prompt_template, template_json, cache_key = await adapter._load_prompt_from_db("test_prompt")

    assert prompt_template == mock_prompt
    assert template_json == mock_prompt.template_json
    assert cache_key == "test_prompt:v2"
```

#### Test 2: `test_load_prompt_from_db_not_found`
```python
async def test_load_prompt_from_db_not_found(mock_prompt_repo):
    """Test DB prompt not found (fallback)."""
    mock_prompt_repo.get_active_prompt.return_value = None

    adapter = LangChainAdapter(model=mock_model, prompt_repository=mock_prompt_repo)
    prompt_template, template_json, cache_key = await adapter._load_prompt_from_db("missing_prompt")

    assert prompt_template is None
    assert template_json is None
    assert cache_key is None
```

#### Test 3: `test_load_prompt_from_db_exception`
```python
async def test_load_prompt_from_db_exception(mock_prompt_repo):
    """Test DB exception (fallback)."""
    mock_prompt_repo.get_active_prompt.side_effect = Exception("DB connection failed")

    adapter = LangChainAdapter(model=mock_model, prompt_repository=mock_prompt_repo)
    prompt_template, template_json, cache_key = await adapter._load_prompt_from_db("test_prompt")

    assert prompt_template is None  # Fallback
    assert template_json is None
    assert cache_key is None
```

#### Test 4: `test_log_execution_success`
```python
async def test_log_execution_success(mock_prompt_repo):
    """Test execution logging with token extraction."""
    prompt_template = PromptTemplate(id=uuid4(), name="test", version=1, ...)
    metadata = {
        "usage": {
            "total_tokens": 150,
            "prompt_tokens": 100,
            "completion_tokens": 50,
        }
    }

    adapter = LangChainAdapter(model=mock_model, prompt_repository=mock_prompt_repo)
    await adapter._log_execution(
        prompt_template=prompt_template,
        context={"interview_id": "test-123"},
        input_variables={"question": "What is Python?"},
        output_text="Python is...",
        start_time=time.time() - 1.5,  # 1.5s ago
        success=True,
        model_response_metadata=metadata,
    )

    # Verify log_execution called with correct data
    mock_prompt_repo.log_execution.assert_called_once()
    execution_data = mock_prompt_repo.log_execution.call_args[1]["execution_data"]
    assert execution_data["tokens_used"] == 150
    assert execution_data["latency_ms"] >= 1500  # ~1.5s
    assert execution_data["success"] is True
```

#### Test 5: `test_extract_response_metadata`
```python
def test_extract_response_metadata_dict():
    """Test metadata extraction from dict response."""
    response = {
        "output": "test",
        "_metadata": {"usage": {"total_tokens": 100}},
    }

    adapter = LangChainAdapter(model=mock_model)
    metadata = adapter._extract_response_metadata(response)

    assert metadata == {"usage": {"total_tokens": 100}}


def test_extract_response_metadata_none():
    """Test metadata extraction when unavailable."""
    response = {"output": "test"}  # No metadata

    adapter = LangChainAdapter(model=mock_model)
    metadata = adapter._extract_response_metadata(response)

    assert metadata is None
```

---

## Edge Cases

### Edge Case 1: prompt_repo is None
**Scenario**: Adapter initialized without PromptRepository (testing mode)
**Expected**: All methods fall back to PROMPT_REGISTRY
**Handling**: `_load_prompt_from_db` returns `(None, None, None)` immediately

### Edge Case 2: DB returns invalid template_json
**Scenario**: DB template missing "system" or "user_template" keys
**Expected**: Validation fails in `_get_or_build_chain` (lines 97-105), fallback to PROMPT_REGISTRY
**Handling**: Already implemented in `_get_or_build_chain`

### Edge Case 3: Execution logging fails
**Scenario**: DB connection lost during `log_execution()`
**Expected**: Method continues successfully (logging is non-critical)
**Handling**: Try-except in `_log_execution` catches all exceptions

### Edge Case 4: Token metadata unavailable
**Scenario**: LangChain model doesn't provide token usage
**Expected**: Log execution with `tokens_used=None`
**Handling**: `_extract_response_metadata` returns None gracefully

---

## Code Quality Checklist

- ✅ **DRY**: Single helper for DB loading (replaces 20-line blocks)
- ✅ **SOLID - Single Responsibility**: Each helper has ONE job
- ✅ **Error Handling**: All exceptions caught, logged, return None
- ✅ **Logging**: Consistent warning/error logs with context
- ✅ **Type Hints**: All methods fully typed
- ✅ **Docstrings**: Clear docstrings with examples
- ✅ **Backward Compatible**: Zero breaking changes

---

## Acceptance Criteria

### Functional
- [ ] `_load_prompt_from_db()` returns correct tuple
- [ ] Handles DB unavailable gracefully (returns None)
- [ ] Logs warnings on DB failures
- [ ] `_log_execution()` extracts tokens from metadata
- [ ] `_extract_response_metadata()` handles all response types

### Testing
- [ ] 5 unit tests pass
- [ ] Mock PromptRepository behaves correctly
- [ ] Edge cases covered (DB down, invalid template)

### Code Quality
- [ ] Passes `ruff check src/`
- [ ] Passes `black src/`
- [ ] Passes `mypy src/`
- [ ] Docstrings complete

---

## Files Modified

```
src/adapters/llm/langchain_adapter.py
  - Line ~119: Add _load_prompt_from_db() (after _get_or_build_chain)
  - Line ~562: Enhance _log_execution() (replace existing)
  - Line ~650: Add _extract_response_metadata()

tests/unit/adapters/llm/test_langchain_adapter_helpers.py (NEW FILE)
  - 5 unit tests for helper methods
```

---

## Next Phase

**Phase 2**: [Refactor Methods](./phase-02-refactor-methods.md)

Use new helpers to migrate 9 single-execution methods:
- evaluate_answer
- generate_rationale
- detect_concept_gaps
- generate_followup_question
- generate_feedback_report
- summarize_cv
- extract_skills_from_text
- generate_interview_recommendations
- generate_ideal_answer (add logging only)

---

**END OF PHASE 1**
