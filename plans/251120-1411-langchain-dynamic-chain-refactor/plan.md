# Implementation Plan: LangChain Dynamic Chain Refactor (Option 1)

**Plan ID**: `251120-1411-langchain-dynamic-chain-refactor`
**Created**: 2025-11-20
**Status**: Draft
**Priority**: High
**Complexity**: Medium
**Estimated Duration**: 4-6 hours

---

## Executive Summary

**Goal**: Unify DB-managed and hardcoded prompt execution paths in `LangChainAdapter` using dynamic LCEL chain building.

**Current State**: Architectural inconsistency between DB and hardcoded prompt execution:
- **DB path**: Custom PromptTemplate → manual string → HumanMessage → direct `model.ainvoke()` → raw string output
- **Hardcoded path**: ChatPromptTemplate → LCEL chain → JsonOutputParser → dict output

**Target State**: Both paths use ChatPromptTemplate → LCEL chain → JsonOutputParser → consistent JSON dict output

**Impact**:
- ✅ Unified execution mechanism (no special-casing)
- ✅ DB prompts get full LCEL benefits (streaming, callbacks, tracing)
- ✅ Consistent output format (JSON dict)
- ✅ Better observability (LangSmith traces both paths)
- ✅ No breaking changes to public API

**Scope**: Refactor `generate_ideal_answer()` method only (1 of 12 LLMPort methods).

---

## Problem Statement

### Current Implementation Analysis

**File**: `src/adapters/llm/langchain_adapter.py` (Lines 218-296)

**DB Prompt Path** (`generate_ideal_answer()` when `prompt_repo` available):
```python
# 1. Load DB prompt template
prompt_template = await self.prompt_repo.get_active_prompt("ideal_answer_generation")

# 2. Render to string
prompt_text = prompt_template.get_prompt_text(**variables)  # Returns: "System\n\nUser prompt"

# 3. Wrap in HumanMessage
response = await self.model.ainvoke([HumanMessage(content=prompt_text)])

# 4. Extract raw string
output_text = response.content  # ❌ String output
```

**Hardcoded Path** (fallback when `prompt_repo=None`):
```python
# 1. Use pre-built ChatPromptTemplate
result = await self._chains["generate_ideal_answer"].ainvoke({...}, config=config)

# 2. Chain returns JSON dict
return result["answer_text"]  # ✅ Dict output
```

**Inconsistencies**:
1. **Different execution mechanisms**: Direct model invocation vs LCEL chain
2. **Different output types**: String vs JSON dict
3. **Missing LCEL features**: DB path loses streaming, callbacks, structured output parsing
4. **Code duplication**: Two separate code paths for same functionality

### Database Template JSON Schema

**From**: `src/domain/models/prompt_template.py`

```python
template_json = {
    "system": str,               # System message text
    "user_template": str,        # User message with {variables}
    "variables": list[str],      # Required variable names
    "constraints": str | None    # Optional constraint text (not in v1)
}
```

**Example**:
```json
{
    "system": "You are a test assistant.",
    "user_template": "Generate ideal answer for: {question_text}\nBackground: {summary}, Skills: {skills}, Experience: {experience}",
    "variables": ["question_text", "summary", "skills", "experience"]
}
```

### Hardcoded ChatPromptTemplate Structure

**From**: `src/adapters/llm/prompts/__init__.py` (Lines 81-100)

```python
IDEAL_ANSWER_PROMPT = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_INTERVIEWER),  # System message
    ("human", """Generate an ideal answer for this interview question.

Question: {question_text}

Context:
- Candidate background: {cv_summary}
- Target skill level: {skill_level}

Requirements:
- Length: 150-300 words
- Include: key concepts, practical examples, best practices
- Avoid: overly technical jargon without explanation

Return in JSON format:
{{
    "answer_text": "ideal answer here (150-300 words)"
}}""")
])
```

**Structure**:
- System message (from constant)
- Human message with variables
- Implicit JSON format instructions

---

## Target Architecture

### Dynamic Chain Building Helper

```python
def _get_or_build_chain(
    self,
    method_name: str,
    db_template_json: dict | None = None,
) -> Runnable:
    """Get or dynamically build LCEL chain for method.

    Args:
        method_name: LLMPort method name (e.g., "generate_ideal_answer")
        db_template_json: Optional DB template JSON (from PromptTemplate.template_json)

    Returns:
        Runnable chain (ChatPromptTemplate | model | JsonOutputParser)

    Logic:
        1. If db_template_json provided → Build ChatPromptTemplate from JSON
        2. Else → Return pre-built hardcoded chain from self._chains
    """

    if db_template_json:
        # Build ChatPromptTemplate dynamically from DB JSON
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", db_template_json["system"]),
            ("human", db_template_json["user_template"]),
        ])

        # Build chain: prompt | model | json_parser
        json_parser = JsonOutputParser()
        chain = prompt_template | self.model | json_parser

        return chain

    else:
        # Return pre-built hardcoded chain
        return self._chains[method_name]
```

### Refactored Execution Flow

```python
async def generate_ideal_answer(
    self,
    question_text: str,
    context: dict[str, Any],
) -> str:
    """Generate ideal answer using unified chain execution."""

    start_time = time.time()
    db_template_json = None
    prompt_template = None  # For logging

    # 1. Try to load DB prompt
    if self.prompt_repo:
        try:
            prompt_template = await self.prompt_repo.get_active_prompt(
                name="ideal_answer_generation"
            )
            if prompt_template:
                db_template_json = prompt_template.template_json
        except Exception:
            db_template_json = None  # Fallback to hardcoded

    # 2. Get or build chain (unified path)
    chain = self._get_or_build_chain("generate_ideal_answer", db_template_json)

    # 3. Prepare variables
    variables = {
        "question_text": question_text,
        "summary": context.get('summary', context.get('cv_summary', 'Not provided')),
        "skills": ', '.join(context.get('skills', [])[:5]) if context.get('skills') else 'Not specified',
        "experience": str(context.get('experience', 'Not specified')),
    }

    # 4. Create config with metadata
    config = self._create_config(
        context=context,
        method="generate_ideal_answer",
    )

    # 5. Execute chain (unified execution)
    try:
        result = await chain.ainvoke(variables, config=config)

        # 6. Extract answer (handle both dict outputs)
        output_text = result.get("answer_text") or result.get("answer")

        # 7. Log execution (if DB prompt)
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

    except Exception as e:
        # Log failed execution (if DB prompt)
        if prompt_template:
            await self._log_execution(
                prompt_template=prompt_template,
                context=context,
                input_variables=variables,
                output_text=None,
                start_time=start_time,
                success=False,
                error_message=str(e),
            )
        raise
```

**Key Changes**:
1. Single execution path (chain.ainvoke)
2. Dynamic chain building via helper method
3. Consistent JSON dict output
4. Execution logging captures chain metadata (not just model response)

---

## Implementation Phases

### Phase 1: Implement Helper Method (1-1.5 hours)

**File**: `src/adapters/llm/langchain_adapter.py`

**Tasks**:

1. **Add import for ChatPromptTemplate** (if not present)
   ```python
   from langchain_core.prompts import ChatPromptTemplate
   ```

2. **Implement `_get_or_build_chain()` helper**
   - Location: After `_build_chains()` method (around line 80)
   - Signature: `def _get_or_build_chain(self, method_name: str, db_template_json: dict | None = None) -> Runnable`
   - Logic:
     - If `db_template_json` → Build ChatPromptTemplate dynamically
     - Else → Return `self._chains[method_name]`
   - Return: Runnable chain

3. **Add validation**
   - Validate `db_template_json` has required keys: `system`, `user_template`
   - Raise ValueError if invalid

**Acceptance Criteria**:
- ✅ Helper method compiles without errors
- ✅ Returns Runnable chain for both DB and hardcoded paths
- ✅ Validates DB template JSON structure
- ✅ Type hints correct (mypy passes)

**Testing**:
```python
# Unit test
def test_get_or_build_chain_with_db_template():
    adapter = LangChainAdapter(model=mock_model)

    db_template = {
        "system": "Test system",
        "user_template": "Test user {var}",
        "variables": ["var"],
    }

    chain = adapter._get_or_build_chain("generate_ideal_answer", db_template)

    assert isinstance(chain, Runnable)
    # Verify chain structure

def test_get_or_build_chain_fallback():
    adapter = LangChainAdapter(model=mock_model)

    chain = adapter._get_or_build_chain("generate_ideal_answer", None)

    assert chain == adapter._chains["generate_ideal_answer"]
```

---

### Phase 2: Refactor `generate_ideal_answer()` (1.5-2 hours)

**File**: `src/adapters/llm/langchain_adapter.py`

**Tasks**:

1. **Replace DB path logic** (Lines 224-269)
   - Remove direct `model.ainvoke([HumanMessage(...)])` call
   - Replace with `chain.ainvoke(variables, config)`
   - Extract `template_json` from `prompt_template`

2. **Unify variable preparation**
   - Merge variable preparation from both paths
   - Map `cv_summary` → `summary` for DB template compatibility
   - Handle optional variables gracefully

3. **Update output extraction**
   - Change from `response.content` → `result.get("answer_text")`
   - Handle fallback keys: `answer_text` OR `answer`

4. **Keep execution logging intact**
   - Maintain `_log_execution()` calls
   - Update to log chain metadata (not just model response)

**Code Structure**:
```python
async def generate_ideal_answer(
    self,
    question_text: str,
    context: dict[str, Any],
) -> str:
    """Generate ideal answer using unified chain execution."""

    # Load DB template (if available)
    # Get or build chain
    # Prepare variables
    # Create config
    # Execute chain
    # Log execution
    # Return result
```

**Acceptance Criteria**:
- ✅ Both DB and hardcoded paths use `chain.ainvoke()`
- ✅ Output format consistent (JSON dict)
- ✅ Execution logging preserved
- ✅ No breaking changes to method signature
- ✅ Error handling preserved

---

### Phase 3: Update Execution Logging (1 hour)

**File**: `src/adapters/llm/langchain_adapter.py`

**Tasks**:

1. **Review `_log_execution()` method** (Lines 526-581)
   - Currently logs: `tokens_used`, `prompt_tokens`, `completion_tokens`, `latency_ms`, `model_name`
   - Check if chain execution provides token metadata

2. **Handle token metadata from chains**
   - **Option A**: Extract from `chain.ainvoke()` callback metadata
   - **Option B**: Access from `result.metadata` (if available)
   - **Option C**: Keep existing approach (may not capture chain-level tokens)

3. **Update logging documentation**
   - Document what metadata is captured from chain execution
   - Note any limitations (e.g., tokens may not be available from all chains)

**Acceptance Criteria**:
- ✅ Execution logs capture correct metadata
- ✅ Logs include chain execution details (not just model response)
- ✅ No errors when logging after chain execution

**Testing**:
```python
# Integration test
async def test_execution_logging_after_chain_refactor(async_session):
    repo = PostgreSQLPromptRepository(async_session)

    # Create and activate DB prompt
    prompt = await repo.create_initial_prompt(...)
    await repo.activate_version(prompt.id, ...)

    adapter = LangChainAdapter(model=mock_model, prompt_repository=repo)

    # Call method (triggers logging)
    await adapter.generate_ideal_answer("What is Python?", context)

    # Verify execution logged
    executions = await repo.get_executions(prompt.id)
    assert len(executions) == 1
    assert executions[0]["success"] == True
    # Verify metadata captured
```

---

### Phase 4: Update Integration Tests (1-1.5 hours)

**File**: `tests/integration/test_llm_prompt_integration.py`

**Tasks**:

1. **Update `test_langchain_adapter_with_prompt_repository()`** (Lines 210-260)
   - **Current assertion**: `assert result == "This is a test LangChain answer."`
   - **Problem**: After refactor, result may be from JSON dict
   - **Fix**: Update mock to return JSON dict structure

2. **Add new assertions**
   - Verify DB path returns JSON dict (not raw string)
   - Verify hardcoded fallback returns JSON dict
   - Assert output format consistency

3. **Update mock response structure**
   ```python
   # OLD mock
   mock_response.content = "This is a test LangChain answer."

   # NEW mock (return dict from JsonOutputParser)
   async def mock_ainvoke(*args, **kwargs):
       return {"answer_text": "This is a test LangChain answer."}
   ```

4. **Add regression test**
   - Test that both paths return identical structure
   - Test that execution logging works for both paths

**Acceptance Criteria**:
- ✅ All existing tests pass
- ✅ New assertions verify output format consistency
- ✅ Mock responses match new chain output structure
- ✅ No test failures due to refactor

**New Test Cases**:
```python
async def test_langchain_generate_ideal_answer_output_format(async_session):
    """Test both DB and hardcoded paths return consistent output format."""

    # Test DB path
    repo = PostgreSQLPromptRepository(async_session)
    prompt = await repo.create_initial_prompt(...)
    adapter_db = LangChainAdapter(model=mock_model, prompt_repository=repo)

    result_db = await adapter_db.generate_ideal_answer("Q?", context)
    assert isinstance(result_db, str)  # Still returns string (not dict)

    # Test hardcoded fallback
    adapter_fallback = LangChainAdapter(model=mock_model, prompt_repository=None)
    result_fallback = await adapter_fallback.generate_ideal_answer("Q?", context)
    assert isinstance(result_fallback, str)

    # Verify consistency (both return strings extracted from JSON dict)
```

---

### Phase 5: Update Documentation (30 minutes)

**Files to Update**:

1. **`plans/251120-0226-prompt-management-system/phase-06-llm-integration.md`**
   - Add section: "LangChain Adapter Refactor (Option 1 Implementation)"
   - Document dynamic chain building approach
   - Explain helper method pattern
   - Note benefits vs trade-offs

2. **Inline documentation** (`src/adapters/llm/langchain_adapter.py`)
   - Update module docstring
   - Add docstring to `_get_or_build_chain()`
   - Update `generate_ideal_answer()` docstring
   - Add comments explaining dynamic chain logic

**Documentation Content**:

```markdown
### LangChain Adapter Refactor (Option 1)

**Implemented**: 2025-11-20

**Change**: Unified DB and hardcoded prompt execution paths using dynamic LCEL chain building.

**Architecture**:
- **Helper Method**: `_get_or_build_chain(method_name, db_template_json)`
- **Execution**: Both paths use `ChatPromptTemplate | model | JsonOutputParser`
- **Output**: Consistent JSON dict format

**Benefits**:
- ✅ DB prompts get full LCEL features (streaming, callbacks, tracing)
- ✅ Consistent output format across paths
- ✅ Better observability (LangSmith traces both paths)
- ✅ Cleaner code (no special-casing)

**Implementation Details**:
- Dynamic ChatPromptTemplate built from DB JSON at runtime
- Pre-built chains used when DB prompt unavailable
- No breaking changes to public API

**Modified Method**: `generate_ideal_answer()` (1 of 12 LLMPort methods)

**Next Steps**: Apply pattern to remaining 11 methods (future work)
```

**Acceptance Criteria**:
- ✅ Phase 6 plan updated with implementation details
- ✅ Inline documentation clear and complete
- ✅ Architecture decision documented

---

## Testing Strategy

### Unit Tests

**Target**: `_get_or_build_chain()` helper method

1. Test with DB template JSON → Returns dynamic chain
2. Test with `None` → Returns hardcoded chain
3. Test with invalid JSON → Raises ValueError
4. Test chain structure (verify prompt | model | parser)

### Integration Tests

**Target**: `generate_ideal_answer()` refactored method

1. Test DB prompt path → Executes chain, returns string, logs execution
2. Test hardcoded fallback → Executes chain, returns string
3. Test output format consistency → Both paths return same type
4. Test error handling → Invalid variables raise ValueError
5. Test execution logging → Metadata captured correctly

### Regression Tests

**Target**: Existing functionality

1. All existing tests pass without modification (except mock updates)
2. No breaking changes to public API
3. OpenAI adapter unaffected
4. Azure OpenAI adapter unaffected

---

## Success Criteria

### Functional
- ✅ Both DB and hardcoded paths return JSON dict structure
- ✅ DB prompts get full LCEL chain execution (streaming, callbacks, tracing)
- ✅ Execution logging captures correct metadata
- ✅ Output format consistent across paths
- ✅ No breaking changes to public API

### Code Quality
- ✅ Helper method follows code standards (type hints, docstrings)
- ✅ Refactored method cleaner (reduced duplication)
- ✅ Error handling preserved
- ✅ Logging preserved

### Testing
- ✅ All existing tests pass
- ✅ New unit tests for helper method
- ✅ Updated integration tests verify consistency
- ✅ Test coverage maintained (>80%)

### Documentation
- ✅ Phase 6 plan updated with implementation details
- ✅ Inline documentation complete
- ✅ Architecture decision documented

---

## Rollout Plan

### Development
1. **Phase 1**: Implement helper method (develop + test)
2. **Phase 2**: Refactor `generate_ideal_answer()` (develop + test)
3. **Phase 3**: Update execution logging (develop + test)
4. **Phase 4**: Update integration tests (verify + regression)
5. **Phase 5**: Update documentation

### Testing
1. Run unit tests: `pytest tests/unit/adapters/test_langchain_adapter.py -v`
2. Run integration tests: `pytest tests/integration/test_llm_prompt_integration.py -v`
3. Run full test suite: `pytest --cov=src/adapters/llm`
4. Verify coverage: >80%

### Deployment
1. Create feature branch: `feature/langchain-dynamic-chain-refactor`
2. Commit changes with conventional commits
3. Push and create PR
4. Code review (verify no breaking changes)
5. Merge to main

---

## Risk Assessment

### Risks

1. **Chain output format mismatch**
   - **Risk**: Dynamic chain returns different dict structure than hardcoded
   - **Mitigation**: Test output format explicitly, handle fallback keys
   - **Impact**: Medium

2. **Token metadata loss**
   - **Risk**: Chain execution may not provide token counts for logging
   - **Mitigation**: Document limitation, accept "best-effort" logging
   - **Impact**: Low (logging non-critical)

3. **Performance overhead**
   - **Risk**: Dynamic chain building adds latency
   - **Mitigation**: Build chain once, cache if needed
   - **Impact**: Low (<5ms)

4. **Breaking changes to tests**
   - **Risk**: Mock responses need updates
   - **Mitigation**: Update mocks incrementally, verify regressions
   - **Impact**: Low (test-only)

### Mitigation Strategy

- **Incremental implementation**: Phase by phase
- **Comprehensive testing**: Unit + integration + regression
- **Fallback preservation**: Hardcoded prompts still work
- **Documentation**: Clear architecture decision record

---

## Constraints

### Must Not Change
- ❌ `openai_adapter.py` (out of scope)
- ❌ `azure_openai_adapter.py` (out of scope)
- ❌ `src/domain/models/prompt_template.py` (DB schema)
- ❌ Public API signatures (no breaking changes)

### Must Preserve
- ✅ Backward compatibility (prompt_repository optional)
- ✅ Hardcoded prompts as fallback
- ✅ Execution logging functionality
- ✅ Error handling behavior

### Technical Constraints
- Python 3.11+
- LangChain 0.1.x
- Clean Architecture patterns
- Async/await throughout

---

## Unresolved Questions

1. **Token Metadata from Chains**
   - **Question**: Does `chain.ainvoke()` provide token counts in result/metadata?
   - **Resolution**: Investigate during Phase 3, document "best-effort" approach
   - **Blocker**: No (can implement Phase 1-2 without answer)

2. **Output Key Variability**
   - **Question**: Should we standardize on `answer_text` vs `answer` key?
   - **Resolution**: Handle both keys with fallback (`result.get("answer_text") or result.get("answer")`)
   - **Blocker**: No (implement fallback logic)

3. **Chain Caching**
   - **Question**: Should we cache dynamically-built chains for performance?
   - **Resolution**: Not in v1 (premature optimization), revisit if latency issue
   - **Blocker**: No (build per invocation acceptable)

4. **Apply to Other Methods?**
   - **Question**: Should we refactor all 12 methods or just `generate_ideal_answer()`?
   - **Resolution**: Only `generate_ideal_answer()` in this plan (other methods in future work)
   - **Blocker**: No (scoped to 1 method)

---

## Related Documents

- **Parent Plan**: `plans/251120-0226-prompt-management-system/phase-06-llm-integration.md`
- **Code Standards**: `docs/code-standards.md` (LCEL Chain Patterns section)
- **Architecture**: `docs/system-architecture.md`
- **Domain Model**: `src/domain/models/prompt_template.py`

---

## Appendix: Code Snippets

### A. Current DB Path (Before Refactor)

```python
# Lines 236-269 (simplified)
if prompt_template:
    # Manual string rendering
    prompt_text = prompt_template.get_prompt_text(
        question_text=question_text,
        summary=context.get('summary', 'Not provided'),
        skills=', '.join(context.get('skills', [])),
        experience=str(context.get('experience')),
    )

    # Direct model invocation (bypass chain)
    response = await self.model.ainvoke([HumanMessage(content=prompt_text)])
    output_text = response.content  # String output

    await self._log_execution(...)
    return output_text
```

### B. Target Unified Path (After Refactor)

```python
# Unified execution
chain = self._get_or_build_chain("generate_ideal_answer", db_template_json)

variables = {
    "question_text": question_text,
    "summary": context.get('summary', 'Not provided'),
    "skills": ', '.join(context.get('skills', [])),
    "experience": str(context.get('experience')),
}

config = self._create_config(context, method="generate_ideal_answer")

result = await chain.ainvoke(variables, config=config)  # JSON dict output
output_text = result.get("answer_text") or result.get("answer")

await self._log_execution(...)
return output_text
```

### C. Helper Method Signature

```python
def _get_or_build_chain(
    self,
    method_name: str,
    db_template_json: dict | None = None,
) -> Runnable:
    """Get or dynamically build LCEL chain for method.

    Args:
        method_name: LLMPort method name (e.g., "generate_ideal_answer")
        db_template_json: Optional DB template JSON (schema: {system, user_template, variables})

    Returns:
        Runnable chain (ChatPromptTemplate | model | JsonOutputParser)

    Raises:
        ValueError: If db_template_json invalid structure
    """
    if db_template_json:
        # Validate JSON structure
        if "system" not in db_template_json or "user_template" not in db_template_json:
            raise ValueError("Invalid template_json: missing 'system' or 'user_template'")

        # Build dynamic chain
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", db_template_json["system"]),
            ("human", db_template_json["user_template"]),
        ])

        json_parser = JsonOutputParser()
        chain = prompt_template | self.model | json_parser

        return chain
    else:
        # Return pre-built hardcoded chain
        return self._chains[method_name]
```

---

**Plan Status**: Draft
**Ready for Implementation**: Yes
**Blockers**: None
**Next Action**: Begin Phase 1 (Implement Helper Method)
