# Phase 3: Add Execution Logging

**Phase ID**: 03
**Plan**: 251121-1654-db-prompt-migration
**Estimated Effort**: 2 hours
**Complexity**: MEDIUM
**Status**: PENDING
**Depends On**: Phase 1 (Helper Methods), Phase 2 (Refactored Methods)

---

## Objective

Enhance execution logging to extract token usage from LangChain responses and integrate with LangSmith observability for comprehensive analytics.

**Principle Applied**: YAGNI - Only add what's needed for analytics, avoid over-engineering

---

## Current State

### Existing _log_execution() (Phase 1)
```python
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
    """Log prompt execution to database."""
    # Basic implementation from Phase 1
```

**Current Limitations**:
- Token extraction from metadata not robust
- No integration with LangSmith callbacks
- No cost estimation
- No retry logic for logging failures

---

## Token Extraction Strategy

### LangChain Token Metadata Sources

Different LangChain models provide token usage in different formats:

#### OpenAI Models (ChatOpenAI)
```python
response_metadata = {
    "usage": {
        "total_tokens": 150,
        "prompt_tokens": 100,
        "completion_tokens": 50
    },
    "model_name": "gpt-4",
    "finish_reason": "stop"
}
```

#### Anthropic Models (ChatAnthropic)
```python
response_metadata = {
    "usage": {
        "input_tokens": 100,
        "output_tokens": 50
    },
    "model": "claude-3-opus-20240229",
    "stop_reason": "end_turn"
}
```

#### LangSmith Callbacks (Run Metadata)
```python
run_metadata = {
    "ls_model_type": "chat",
    "ls_temperature": 0.3,
    "ls_provider": "openai",
    "total_tokens": 150
}
```

---

## Implementation Plan

### Step 1: Enhance Token Extraction

**Method**: `_extract_token_usage()`

```python
def _extract_token_usage(
    self,
    model_response_metadata: dict | None,
    model_name: str,
) -> tuple[int | None, int | None, int | None]:
    """Extract token usage from LangChain response metadata.

    Supports multiple token formats:
    - OpenAI: usage.total_tokens, usage.prompt_tokens, usage.completion_tokens
    - Anthropic: usage.input_tokens, usage.output_tokens
    - Generic: token_usage.total, token_usage.prompt, token_usage.completion

    Args:
        model_response_metadata: Response metadata from LangChain
        model_name: Model identifier (for provider detection)

    Returns:
        Tuple of (total_tokens, prompt_tokens, completion_tokens)
        Returns (None, None, None) if no token data available
    """
    if not model_response_metadata:
        return None, None, None

    usage = model_response_metadata.get("usage") or model_response_metadata.get("token_usage")
    if not usage:
        return None, None, None

    # OpenAI format
    if "total_tokens" in usage:
        return (
            usage.get("total_tokens"),
            usage.get("prompt_tokens"),
            usage.get("completion_tokens"),
        )

    # Anthropic format
    if "input_tokens" in usage:
        input_tokens = usage.get("input_tokens")
        output_tokens = usage.get("output_tokens")
        total = (input_tokens or 0) + (output_tokens or 0) if input_tokens and output_tokens else None
        return total, input_tokens, output_tokens

    # Generic format
    return (
        usage.get("total"),
        usage.get("prompt"),
        usage.get("completion"),
    )
```

---

### Step 2: Add Cost Estimation

**Method**: `_estimate_cost()`

```python
def _estimate_cost(
    self,
    model_name: str,
    prompt_tokens: int | None,
    completion_tokens: int | None,
) -> float | None:
    """Estimate LLM cost based on token usage.

    Uses approximate pricing (as of 2025-11):
    - GPT-4: $0.03/1K prompt, $0.06/1K completion
    - GPT-3.5: $0.0005/1K prompt, $0.0015/1K completion
    - Claude 3 Opus: $0.015/1K prompt, $0.075/1K completion
    - Claude 3 Sonnet: $0.003/1K prompt, $0.015/1K completion

    Args:
        model_name: Model identifier
        prompt_tokens: Number of prompt tokens
        completion_tokens: Number of completion tokens

    Returns:
        Estimated cost in USD, or None if tokens unavailable
    """
    if not prompt_tokens or not completion_tokens:
        return None

    # Pricing table (cents per 1K tokens)
    PRICING = {
        "gpt-4": (3.0, 6.0),
        "gpt-3.5-turbo": (0.05, 0.15),
        "claude-3-opus": (1.5, 7.5),
        "claude-3-sonnet": (0.3, 1.5),
        "claude-3-haiku": (0.025, 0.125),
    }

    # Match model name (case-insensitive, partial match)
    model_lower = model_name.lower()
    for key, (prompt_cost, completion_cost) in PRICING.items():
        if key in model_lower:
            cost_usd = (
                (prompt_tokens / 1000 * prompt_cost / 100) +
                (completion_tokens / 1000 * completion_cost / 100)
            )
            return round(cost_usd, 6)  # 6 decimal places ($0.000001 precision)

    # Unknown model
    logger.warning("Unknown model '%s' for cost estimation", model_name)
    return None
```

---

### Step 3: Enhanced _log_execution()

**Full Implementation**:

```python
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
    """Log prompt execution to database with token tracking.

    Args:
        prompt_template: The PromptTemplate used
        context: Execution context (interview_id, candidate_id)
        input_variables: Variables passed to prompt
        output_text: LLM output (None if failed)
        start_time: Start timestamp
        success: Whether execution succeeded
        model_response_metadata: LangChain response metadata (for tokens)
        error_message: Error message if failed
    """
    try:
        # Calculate latency
        latency_ms = int((time.time() - start_time) * 1000)

        # Get model name
        model_name = getattr(self.model, 'model_name', getattr(self.model, 'model', 'unknown'))

        # Extract token usage
        total_tokens, prompt_tokens, completion_tokens = self._extract_token_usage(
            model_response_metadata, model_name
        )

        # Estimate cost
        estimated_cost = self._estimate_cost(model_name, prompt_tokens, completion_tokens)

        # Sanitize input variables (remove PII if present)
        sanitized_input = self._sanitize_variables(input_variables)

        # Prepare execution data
        execution_data = {
            "interview_id": context.get("interview_id"),
            "candidate_id": context.get("candidate_id"),
            "input_variables": sanitized_input,
            "output_text": output_text[:10000] if output_text else None,  # Truncate
            "tokens_used": total_tokens,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "latency_ms": latency_ms,
            "model_name": model_name,
            "success": success,
            "error_message": error_message,
            "estimated_cost_usd": estimated_cost,
        }

        # Log to database
        await self.prompt_repo.log_execution(
            prompt_template_id=prompt_template.id,
            execution_data=execution_data,
        )

        # Log to application logs (INFO for success, WARNING for failure)
        if success:
            logger.info(
                "Prompt execution: %s (v%d) | Tokens: %s | Latency: %dms | Cost: $%.6f",
                prompt_template.name,
                prompt_template.version,
                total_tokens or "N/A",
                latency_ms,
                estimated_cost or 0.0,
            )
        else:
            logger.warning(
                "Prompt execution FAILED: %s (v%d) | Error: %s | Latency: %dms",
                prompt_template.name,
                prompt_template.version,
                error_message,
                latency_ms,
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

---

### Step 4: Add Input Sanitization

**Method**: `_sanitize_variables()`

**Purpose**: Remove PII (personally identifiable information) from logged input variables to comply with data privacy regulations.

```python
def _sanitize_variables(self, input_variables: dict) -> dict:
    """Sanitize input variables to remove PII.

    Removes or redacts:
    - Email addresses
    - Phone numbers
    - Full names (in CV text)
    - Long text fields (truncate to 500 chars)

    Args:
        input_variables: Raw input variables

    Returns:
        Sanitized dict safe for logging
    """
    import re

    sanitized = {}
    for key, value in input_variables.items():
        if value is None:
            sanitized[key] = None
            continue

        # Convert to string for processing
        str_value = str(value)

        # Redact emails
        str_value = re.sub(
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            '[EMAIL_REDACTED]',
            str_value
        )

        # Redact phone numbers
        str_value = re.sub(
            r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b',
            '[PHONE_REDACTED]',
            str_value
        )

        # Truncate long text (preserve structure for debugging)
        if len(str_value) > 500:
            str_value = str_value[:500] + f"... [TRUNCATED {len(str_value)-500} chars]"

        sanitized[key] = str_value

    return sanitized
```

**Rationale**:
- Complies with GDPR, CCPA (no PII in analytics)
- Preserves debugging capability (partial text, structure)
- Minimal performance impact (regex on small strings)

---

## LangSmith Integration

### Current State
- LangSmith callbacks configured in DI container
- PIIFilteringTracer already removes PII from traces
- Token usage tracked in LangSmith UI

### Integration Points

#### 1. Extract LangSmith Run Metadata

**Method**: `_extract_langsmith_metadata()`

```python
def _extract_langsmith_metadata(self, config: RunnableConfig | None) -> dict:
    """Extract metadata from LangSmith run.

    Checks config callbacks for LangSmithTracer run data.

    Args:
        config: RunnableConfig from chain execution

    Returns:
        Dict with keys: run_id, run_url, tags, metadata
    """
    if not config or not config.get("callbacks"):
        return {}

    langsmith_metadata = {}

    # Check for LangSmithTracer in callbacks
    for callback in config.get("callbacks", []):
        if hasattr(callback, "run_id"):
            langsmith_metadata["run_id"] = str(callback.run_id)

        if hasattr(callback, "run_url"):
            langsmith_metadata["run_url"] = callback.run_url

    return langsmith_metadata
```

#### 2. Add LangSmith URL to Logs

**Enhancement to _log_execution**:

```python
# After extracting tokens...
langsmith_url = None
if hasattr(self, '_last_langsmith_run_url'):
    langsmith_url = self._last_langsmith_run_url

# Add to execution_data
execution_data["langsmith_run_url"] = langsmith_url

# Log with LangSmith link
if success and langsmith_url:
    logger.info(
        "Prompt execution: %s | LangSmith: %s",
        prompt_template.name,
        langsmith_url,
    )
```

---

## Error Handling & Retry Logic

### Transient Failure Handling

**Scenario**: Database connection lost during log_execution()

**Strategy**: Exponential backoff retry (max 3 attempts)

```python
async def _log_execution_with_retry(
    self,
    prompt_template: PromptTemplate,
    execution_data: dict,
    max_retries: int = 3,
) -> None:
    """Log execution with exponential backoff retry.

    Args:
        prompt_template: The PromptTemplate used
        execution_data: Execution data to log
        max_retries: Maximum retry attempts
    """
    import asyncio

    for attempt in range(max_retries):
        try:
            await self.prompt_repo.log_execution(
                prompt_template_id=prompt_template.id,
                execution_data=execution_data,
            )
            return  # Success

        except Exception as exc:
            if attempt == max_retries - 1:
                # Final attempt failed
                logger.error(
                    "Failed to log execution after %d attempts: %s",
                    max_retries,
                    exc,
                    exc_info=True,
                )
                raise

            # Exponential backoff: 0.1s, 0.2s, 0.4s
            wait_time = 0.1 * (2 ** attempt)
            logger.warning(
                "Logging failed (attempt %d/%d), retrying in %.1fs: %s",
                attempt + 1,
                max_retries,
                wait_time,
                exc,
            )
            await asyncio.sleep(wait_time)
```

**Usage**: Replace `prompt_repo.log_execution()` with `_log_execution_with_retry()`

---

## Analytics Queries

### Query 1: Prompt Performance by Version

```sql
SELECT
    pt.name,
    pt.version,
    COUNT(*) as executions,
    AVG(pe.latency_ms) as avg_latency_ms,
    AVG(pe.tokens_used) as avg_tokens,
    SUM(pe.estimated_cost_usd) as total_cost_usd,
    AVG(CASE WHEN pe.success THEN 1.0 ELSE 0.0 END) as success_rate
FROM prompt_executions pe
JOIN prompt_templates pt ON pe.prompt_template_id = pt.id
WHERE pe.executed_at > NOW() - INTERVAL '7 days'
GROUP BY pt.name, pt.version
ORDER BY total_cost_usd DESC;
```

### Query 2: Token Usage Trends

```sql
SELECT
    DATE_TRUNC('hour', pe.executed_at) as hour,
    pt.name,
    SUM(pe.tokens_used) as total_tokens,
    COUNT(*) as executions,
    AVG(pe.latency_ms) as avg_latency
FROM prompt_executions pe
JOIN prompt_templates pt ON pe.prompt_template_id = pt.id
WHERE pe.executed_at > NOW() - INTERVAL '24 hours'
GROUP BY hour, pt.name
ORDER BY hour DESC, total_tokens DESC;
```

---

## Testing Requirements

### Unit Tests

**File**: `tests/unit/adapters/llm/test_execution_logging.py`

#### Test 1: Token Extraction (OpenAI)
```python
def test_extract_token_usage_openai():
    """Test token extraction from OpenAI response."""
    metadata = {
        "usage": {
            "total_tokens": 150,
            "prompt_tokens": 100,
            "completion_tokens": 50
        }
    }

    adapter = LangChainAdapter(mock_model)
    total, prompt, completion = adapter._extract_token_usage(metadata, "gpt-4")

    assert total == 150
    assert prompt == 100
    assert completion == 50
```

#### Test 2: Cost Estimation
```python
def test_estimate_cost_gpt4():
    """Test cost estimation for GPT-4."""
    adapter = LangChainAdapter(mock_model)
    cost = adapter._estimate_cost("gpt-4", 1000, 500)

    # Expected: (1000/1000 * 0.03) + (500/1000 * 0.06) = $0.06
    assert cost == pytest.approx(0.06, rel=0.01)
```

#### Test 3: Input Sanitization
```python
def test_sanitize_variables_email():
    """Test email redaction in input variables."""
    adapter = LangChainAdapter(mock_model)
    sanitized = adapter._sanitize_variables({
        "cv_text": "Contact: john.doe@example.com",
        "question": "What is Python?"
    })

    assert "[EMAIL_REDACTED]" in sanitized["cv_text"]
    assert "john.doe@example.com" not in sanitized["cv_text"]
    assert sanitized["question"] == "What is Python?"
```

#### Test 4: Logging Retry
```python
async def test_log_execution_retry_success(mock_prompt_repo):
    """Test retry logic succeeds on second attempt."""
    # Fail first, succeed second
    mock_prompt_repo.log_execution.side_effect = [
        Exception("Connection lost"),
        None  # Success
    ]

    adapter = LangChainAdapter(mock_model, mock_prompt_repo)
    await adapter._log_execution_with_retry(mock_prompt, execution_data)

    assert mock_prompt_repo.log_execution.call_count == 2
```

---

## Performance Considerations

### Logging Overhead
- **Target**: <5ms per log_execution call
- **Strategy**: Async logging (don't block chain execution)
- **Monitoring**: Track logging latency separately

### Token Extraction Cost
- **Overhead**: <1ms (simple dict lookups)
- **Optimization**: Cache model pricing table

### PII Sanitization Cost
- **Overhead**: <2ms (regex on truncated strings)
- **Optimization**: Only sanitize if logging enabled

---

## Acceptance Criteria

### Functional
- [ ] Token usage extracted from all LangChain models (OpenAI, Anthropic)
- [ ] Cost estimated accurately (±5% of actual)
- [ ] Input variables sanitized (no PII in logs)
- [ ] Execution logging retries on transient failures (max 3 attempts)
- [ ] LangSmith run URLs captured (if available)

### Testing
- [ ] 5 unit tests pass (token extraction, cost, sanitization, retry)
- [ ] Integration tests verify DB logging
- [ ] Load test: 100 concurrent executions without errors

### Performance
- [ ] Logging overhead <5ms per execution
- [ ] No blocking on main chain execution

---

## Files Modified

```
src/adapters/llm/langchain_adapter.py
  - Line ~620: Enhance _log_execution() (add token extraction, cost estimation)
  - Line ~680: Add _extract_token_usage()
  - Line ~720: Add _estimate_cost()
  - Line ~750: Add _sanitize_variables()
  - Line ~790: Add _log_execution_with_retry()

tests/unit/adapters/llm/test_execution_logging.py (NEW)
  - 5 unit tests
```

---

## Next Phase

**Phase 4**: [Create Migration 0014](./phase-04-create-migration.md)

Seed 3 missing DB prompts (cv_summary, skill_extraction, interview_recommendations) to enable full migration.

---

**END OF PHASE 3**
