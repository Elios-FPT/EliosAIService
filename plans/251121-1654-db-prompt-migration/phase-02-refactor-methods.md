# Phase 2: Refactor Single-Execution Methods

**Phase ID**: 02
**Plan**: 251121-1654-db-prompt-migration
**Estimated Effort**: 3-4 hours
**Complexity**: MEDIUM
**Status**: PENDING
**Depends On**: Phase 1 (Helper Methods)

---

## Objective

Refactor 9 LangChainAdapter methods to use DB prompts with fallback to PROMPT_REGISTRY. Apply standardized pattern from Phase 1 helpers.

**Principle Applied**: KISS (Keep It Simple, Stupid) - Use proven pattern consistently

---

## Method Migration Table

| # | Method | DB Prompt Name | Lines | Complexity | Notes |
|---|--------|----------------|-------|------------|-------|
| 1 | evaluate_answer | answer_evaluation | 141-199 | HIGH | Has followup_context logic |
| 2 | generate_rationale | rationale_generation | 334-345 | LOW | Simple chain call |
| 3 | detect_concept_gaps | gap_detection | 347-367 | LOW | Simple chain call |
| 4 | generate_followup_question | follow_up_generation | 369-410 | MEDIUM | Context formatting |
| 5 | generate_feedback_report | feedback_report | 201-224 | LOW | Simple chain call |
| 6 | summarize_cv | cv_summary | 226-235 | LOW | Simple chain call |
| 7 | extract_skills_from_text | skill_extraction | 237-255 | MEDIUM | Result transformation |
| 8 | generate_interview_recommendations | interview_recommendations | 412-429 | LOW | Simple chain call |
| 9 | generate_ideal_answer | ideal_answer_generation | 257-332 | DONE | Already migrated, ADD LOGGING |

**Total**: 9 methods, 8 to migrate + 1 to enhance

---

## Standard Refactoring Pattern

### Before (Hardcoded)
```python
async def example_method(self, arg: str) -> str:
    result = await self._chains["example_method"].ainvoke({
        "arg": arg,
    })
    return result["output"]
```

### After (DB-Driven)
```python
async def example_method(self, arg: str, context: dict[str, Any]) -> str:
    start_time = time.time()

    # Load DB prompt
    prompt_template, template_json, cache_key = await self._load_prompt_from_db("db_prompt_name")

    # Get chain (DB or fallback)
    chain = self._get_or_build_chain("example_method", template_json, cache_key)

    # Execute
    variables = {"arg": arg}
    config = self._create_config(context=context, method="example_method")

    try:
        result = await chain.ainvoke(variables, config)
        metadata = self._extract_response_metadata(result)

        # Log if using DB prompt
        if prompt_template:
            await self._log_execution(
                prompt_template=prompt_template,
                context=context,
                input_variables=variables,
                output_text=result["output"],
                start_time=start_time,
                success=True,
                model_response_metadata=metadata,
            )

        return result["output"]

    except Exception as exc:
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

**Changes**:
- Add `context: dict[str, Any]` parameter (for logging)
- Add `start_time = time.time()` at start
- Replace direct `self._chains` with `_load_prompt_from_db()` + `_get_or_build_chain()`
- Add try-except for execution logging
- Extract metadata for token tracking

---

## Method 1: evaluate_answer

**Current Lines**: 141-199
**DB Prompt**: `answer_evaluation`
**Complexity**: HIGH (followup context formatting)

### Current Implementation Issues
- No DB loading
- No execution logging
- followup_context logic needs preservation

### Refactored Code

```python
async def evaluate_answer(
    self,
    question: Question,
    answer_text: str,
    context: dict[str, Any],
    followup_context: FollowUpEvaluationContext | None = None,
) -> AnswerEvaluation:
    """Evaluate a candidate's answer using LangChain."""
    start_time = time.time()

    # Load DB prompt
    prompt_template, template_json, cache_key = await self._load_prompt_from_db("answer_evaluation")

    # Get chain (DB or fallback)
    chain = self._get_or_build_chain("evaluate_answer", template_json, cache_key)

    # Format followup context (preserve existing logic)
    followup_section = ""
    if followup_context:
        followup_section = f"""
This is a follow-up question (attempt #{followup_context.attempt_number}).

Previous Evaluations:
{self._format_previous_evaluations(followup_context.previous_evaluations)}

Cumulative Gaps: {', '.join(followup_context.cumulative_gaps) if followup_context.cumulative_gaps else 'None'}

Apply attempt-based penalty:
- Attempt 2: Reduce score by 10% (gaps should be addressed)
- Attempt 3+: Reduce score by 20% (repeated failure to address gaps)
"""

    # Prepare variables
    variables = {
        "question_text": question.text,
        "difficulty": question.difficulty,
        "skill": question.skills[0] if question.skills else "General",
        "answer_text": answer_text,
        "followup_context": followup_section,
    }

    # Create config with metadata
    config = self._create_config(
        context=context,
        question_id=str(question.id) if question.id else None,
        difficulty=question.difficulty.value if hasattr(question.difficulty, 'value') else str(question.difficulty),
        skill=question.skills[0] if question.skills else "General",
        method="evaluate_answer",
    )

    # Execute chain
    try:
        result = await chain.ainvoke(variables, config)
        metadata = self._extract_response_metadata(result)

        # Log execution
        if prompt_template:
            await self._log_execution(
                prompt_template=prompt_template,
                context=context,
                input_variables=variables,
                output_text=str(result),  # JSON result
                start_time=start_time,
                success=True,
                model_response_metadata=metadata,
            )

        # Map to domain model (preserve existing logic)
        semantic_similarity = result.get("semantic_similarity", result["score"] / 100.0)
        completeness = result.get("completeness", result["score"] / 100.0)
        relevance = result.get("relevance", 1.0)

        return AnswerEvaluation(
            score=result["score"],
            semantic_similarity=max(0.0, min(1.0, semantic_similarity)),
            completeness=max(0.0, min(1.0, completeness)),
            relevance=max(0.0, min(1.0, relevance)),
            sentiment=result.get("sentiment"),
            reasoning=result.get("feedback"),
            strengths=result.get("strengths", []),
            weaknesses=result.get("weaknesses", []),
            improvement_suggestions=result.get("missing_concepts", []),
        )

    except Exception as exc:
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

**Changes**:
- Added DB prompt loading (lines 5-9)
- Added execution logging (lines 53-66, 87-96)
- Preserved followup_context logic (lines 12-28)
- Preserved domain model mapping (lines 69-85)

---

## Method 2: generate_rationale

**Current Lines**: 334-345
**DB Prompt**: `rationale_generation`
**Complexity**: LOW

### Refactored Code

```python
async def generate_rationale(
    self,
    question_text: str,
    ideal_answer: str,
    context: dict[str, Any] | None = None,
) -> str:
    """Generate rationale explaining why answer is ideal."""
    start_time = time.time()
    context = context or {}

    # Load DB prompt
    prompt_template, template_json, cache_key = await self._load_prompt_from_db("rationale_generation")

    # Get chain
    chain = self._get_or_build_chain("generate_rationale", template_json, cache_key)

    # Prepare variables
    variables = {
        "question_text": question_text,
        "ideal_answer": ideal_answer,
    }

    # Execute
    try:
        result = await chain.ainvoke(variables)
        metadata = self._extract_response_metadata(result)

        # Log execution
        if prompt_template:
            await self._log_execution(
                prompt_template=prompt_template,
                context=context,
                input_variables=variables,
                output_text=result["rationale_text"],
                start_time=start_time,
                success=True,
                model_response_metadata=metadata,
            )

        return result["rationale_text"]

    except Exception as exc:
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

**Changes**:
- Added `context` parameter (optional for backward compatibility)
- Added DB loading + logging
- Preserved output format

---

## Method 3: detect_concept_gaps

**Current Lines**: 347-367
**DB Prompt**: `gap_detection`
**Complexity**: LOW

### Refactored Code

```python
async def detect_concept_gaps(
    self,
    answer_text: str,
    ideal_answer: str,
    question_text: str,
    keyword_gaps: list[str],
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Detect missing concepts in answer using LLM."""
    start_time = time.time()
    context = context or {}

    # Load DB prompt
    prompt_template, template_json, cache_key = await self._load_prompt_from_db("gap_detection")

    # Get chain
    chain = self._get_or_build_chain("detect_concept_gaps", template_json, cache_key)

    # Prepare variables
    variables = {
        "question_text": question_text,
        "ideal_answer": ideal_answer,
        "answer_text": answer_text,
        "keyword_gaps": ", ".join(keyword_gaps),
    }

    # Execute
    try:
        result = await chain.ainvoke(variables)
        metadata = self._extract_response_metadata(result)

        # Log execution
        if prompt_template:
            await self._log_execution(
                prompt_template=prompt_template,
                context=context,
                input_variables=variables,
                output_text=str(result),
                start_time=start_time,
                success=True,
                model_response_metadata=metadata,
            )

        return {
            "concepts": result.get("concepts", []),
            "keywords": result.get("keywords", []),
            "confirmed": result.get("confirmed", False),
            "severity": result.get("severity", "minor"),
        }

    except Exception as exc:
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

---

## Method 4: generate_followup_question

**Current Lines**: 369-410
**DB Prompt**: `follow_up_generation`
**Complexity**: MEDIUM (context formatting)

### Refactored Code

```python
async def generate_followup_question(
    self,
    parent_question: str,
    answer_text: str,
    missing_concepts: list[str],
    severity: str,
    order: int,
    context: dict[str, Any] | None = None,
    cumulative_gaps: list[str] | None = None,
    previous_follow_ups: list[dict[str, Any]] | None = None,
) -> str:
    """Generate targeted follow-up question."""
    start_time = time.time()
    context = context or {}

    # Load DB prompt
    prompt_template, template_json, cache_key = await self._load_prompt_from_db("follow_up_generation")

    # Get chain
    chain = self._get_or_build_chain("generate_followup_question", template_json, cache_key)

    # Format cumulative context (preserve existing logic)
    cumulative_context = ""
    if cumulative_gaps:
        cumulative_context = f"Cumulative Gaps (all attempts): {', '.join(cumulative_gaps)}"

    # Format previous follow-ups
    previous_context = ""
    if previous_follow_ups:
        previous_context = "Previous Follow-ups:\n"
        for i, fu in enumerate(previous_follow_ups, 1):
            previous_context += f"{i}. Q: {fu.get('question', '')}\n"
            previous_context += f"   A: {fu.get('answer', '')[:100]}...\n"

    # Prepare variables
    variables = {
        "parent_question": parent_question,
        "answer_text": answer_text,
        "missing_concepts": ", ".join(missing_concepts),
        "severity": severity,
        "order": order,
        "cumulative_context": cumulative_context,
        "previous_followups": previous_context,
    }

    # Create config with metadata
    config = self._create_config(
        context=context,
        method="generate_followup_question",
        severity=severity,
        order=order,
    )

    # Execute
    try:
        result = await chain.ainvoke(variables, config)
        metadata = self._extract_response_metadata(result)

        # Log execution
        if prompt_template:
            await self._log_execution(
                prompt_template=prompt_template,
                context=context,
                input_variables=variables,
                output_text=result["question_text"],
                start_time=start_time,
                success=True,
                model_response_metadata=metadata,
            )

        return result["question_text"]

    except Exception as exc:
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

---

## Methods 5-8: Simple Migrations (Similar Pattern)

### Method 5: generate_feedback_report
- **DB Prompt**: `feedback_report`
- **Changes**: Add DB loading, logging, preserve QA formatting

### Method 6: summarize_cv
- **DB Prompt**: `cv_summary`
- **Changes**: Add DB loading, logging (NEEDS MIGRATION 0014)

### Method 7: extract_skills_from_text
- **DB Prompt**: `skill_extraction`
- **Changes**: Add DB loading, logging, preserve result transformation (NEEDS MIGRATION 0014)

### Method 8: generate_interview_recommendations
- **DB Prompt**: `interview_recommendations`
- **Changes**: Add DB loading, logging (NEEDS MIGRATION 0014)

**NOTE**: Methods 6-8 require Phase 4 (Migration 0014) to seed DB prompts first.

---

## Method 9: generate_ideal_answer (Enhancement Only)

**Current Status**: Already has DB loading (lines 268-287)
**Action**: ADD execution logging ONLY

### Changes Required

**Current Code** (lines 305-332):
```python
try:
    result = await chain.ainvoke(variables, config=config)
except Exception as exc:
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

output_text = result.get("answer_text") or result.get("answer")

if prompt_template:
    await self._log_execution(
        prompt_template=prompt_template,
        context=context,
        input_variables=variables,
        output_text=output_text,
        start_time=start_time,
        success=True,
    )

return output_text
```

**Enhanced Code**:
```python
try:
    result = await chain.ainvoke(variables, config=config)
    metadata = self._extract_response_metadata(result)  # ADD THIS

    output_text = result.get("answer_text") or result.get("answer")

    if prompt_template:
        await self._log_execution(
            prompt_template=prompt_template,
            context=context,
            input_variables=variables,
            output_text=output_text,
            start_time=start_time,
            success=True,
            model_response_metadata=metadata,  # ADD THIS
        )

    return output_text

except Exception as exc:
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

**Changes**:
- Extract metadata after successful execution
- Pass metadata to `_log_execution()`
- Move success logging INSIDE try block (before return)

---

## Backward Compatibility Considerations

### Breaking Changes: NONE
- All method signatures unchanged (context parameter added as optional)
- Return types unchanged
- Error behavior unchanged (same exceptions)

### Non-Breaking Changes
- Methods now accept optional `context` parameter for logging
- Execution metrics now tracked in DB (transparent to callers)

### Migration Path for Callers
**Before**:
```python
result = await adapter.generate_rationale(question, ideal_answer)
```

**After (still works)**:
```python
result = await adapter.generate_rationale(question, ideal_answer)
```

**After (with logging)**:
```python
result = await adapter.generate_rationale(
    question,
    ideal_answer,
    context={"interview_id": "123", "candidate_id": "456"}
)
```

---

## Testing Requirements

### Unit Tests per Method

**File**: `tests/unit/adapters/llm/test_langchain_adapter_db_prompts.py`

#### Test Template
```python
async def test_METHOD_NAME_with_db_prompt(mock_prompt_repo, mock_model):
    """Test METHOD_NAME loads DB prompt and logs execution."""
    # Setup DB prompt
    mock_prompt = create_mock_prompt("DB_PROMPT_NAME")
    mock_prompt_repo.get_active_prompt.return_value = mock_prompt

    # Setup model response
    mock_model.ainvoke.return_value = {"expected_output": "test"}

    # Execute
    adapter = LangChainAdapter(model=mock_model, prompt_repository=mock_prompt_repo)
    result = await adapter.METHOD_NAME(..., context={"interview_id": "123"})

    # Assertions
    assert result == "expected_output"
    mock_prompt_repo.get_active_prompt.assert_called_once_with("DB_PROMPT_NAME")
    mock_prompt_repo.log_execution.assert_called_once()


async def test_METHOD_NAME_fallback_to_registry(mock_prompt_repo, mock_model):
    """Test METHOD_NAME falls back to PROMPT_REGISTRY when DB fails."""
    # Simulate DB failure
    mock_prompt_repo.get_active_prompt.return_value = None

    # Execute
    adapter = LangChainAdapter(model=mock_model, prompt_repository=mock_prompt_repo)
    result = await adapter.METHOD_NAME(...)

    # Should still work (using PROMPT_REGISTRY)
    assert result == "expected_output"
    mock_prompt_repo.log_execution.assert_not_called()  # No logging without DB prompt
```

**Total Tests**: 9 methods × 2 tests = **18 unit tests**

---

## Integration Tests

**File**: `tests/integration/test_langchain_adapter_db_integration.py`

### Test Scenario 1: End-to-End with Real DB
```python
async def test_evaluate_answer_with_postgres(db_session, real_model):
    """Test evaluate_answer with real PostgreSQL prompt repository."""
    # Seed test prompt
    prompt_repo = PostgreSQLPromptRepository(db_session)
    await prompt_repo.create_initial_prompt(
        name="answer_evaluation",
        template_json={...},
        created_by="test",
    )
    await prompt_repo.activate_version(...)

    # Execute
    adapter = LangChainAdapter(model=real_model, prompt_repository=prompt_repo)
    result = await adapter.evaluate_answer(
        question=test_question,
        answer_text="Test answer",
        context={"interview_id": "test-123"},
    )

    # Verify execution logged
    analytics = await prompt_repo.get_analytics_summary("answer_evaluation")
    assert analytics["total_executions"] == 1
    assert analytics["success_rate"] == 1.0
```

---

## Performance Benchmarks

### Metrics to Track
- **DB Overhead**: Latency increase from DB prompt loading
- **Cache Hit Rate**: % of chain cache hits
- **Token Usage**: Compare DB prompts vs PROMPT_REGISTRY

### Benchmark Script
```python
# scripts/benchmark_db_prompts.py
async def benchmark_method(adapter, method_name, iterations=100):
    """Benchmark method with DB vs fallback."""
    # Test with DB
    start = time.time()
    for _ in range(iterations):
        await getattr(adapter, method_name)(...)
    db_time = time.time() - start

    # Test with fallback (disable DB)
    adapter.prompt_repo = None
    start = time.time()
    for _ in range(iterations):
        await getattr(adapter, method_name)(...)
    fallback_time = time.time() - start

    print(f"{method_name}:")
    print(f"  DB: {db_time/iterations*1000:.2f}ms per call")
    print(f"  Fallback: {fallback_time/iterations*1000:.2f}ms per call")
    print(f"  Overhead: {(db_time-fallback_time)/iterations*1000:.2f}ms")
```

**Target**: <10ms overhead per call

---

## Acceptance Criteria

### Functional
- [ ] All 9 methods load DB prompts first
- [ ] Fallback to PROMPT_REGISTRY if DB unavailable
- [ ] Execution logging tracks tokens, latency, success
- [ ] Zero breaking changes (backward compatible)

### Testing
- [ ] 18 unit tests pass (DB + fallback scenarios)
- [ ] Integration tests pass with real PostgreSQL
- [ ] Performance overhead <10ms per call

### Code Quality
- [ ] Passes `ruff check src/`
- [ ] Passes `black src/`
- [ ] Passes `mypy src/`
- [ ] Test coverage >90% on refactored methods

---

## Files Modified

```
src/adapters/llm/langchain_adapter.py
  - Lines 141-199: Refactor evaluate_answer
  - Lines 334-345: Refactor generate_rationale
  - Lines 347-367: Refactor detect_concept_gaps
  - Lines 369-410: Refactor generate_followup_question
  - Lines 201-224: Refactor generate_feedback_report
  - Lines 226-235: Refactor summarize_cv
  - Lines 237-255: Refactor extract_skills_from_text
  - Lines 412-429: Refactor generate_interview_recommendations
  - Lines 305-332: Enhance generate_ideal_answer (logging only)

tests/unit/adapters/llm/test_langchain_adapter_db_prompts.py (NEW)
  - 18 unit tests

tests/integration/test_langchain_adapter_db_integration.py (NEW)
  - End-to-end integration tests
```

---

## Next Phase

**Phase 3**: [Add Execution Logging](./phase-03-add-execution-logging.md)

Enhance `_log_execution()` to extract tokens from LangChain callbacks and integrate with LangSmith tracing.

**Phase 4**: [Create Migration 0014](./phase-04-create-migration.md)

Seed 3 missing DB prompts (cv_summary, skill_extraction, interview_recommendations) before testing methods 6-8.

---

**END OF PHASE 2**
