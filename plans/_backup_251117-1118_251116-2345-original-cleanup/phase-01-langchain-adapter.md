# Phase 1: LangChain Adapter Layer

**Phase ID**: 251116-2345-P1
**Parent Plan**: [LangChain & LangGraph Integration](plan.md)
**Status**: Not Started
**Priority**: High
**Estimated Duration**: 1.5 weeks
**Risk Level**: Low

---

## Context

**Related Docs**:
- [Research: LangChain Adapters](research/researcher-01-langchain-adapters.md) - LCEL patterns, structured output, async integration
- [Current OpenAI Adapter](../../src/adapters/llm/openai_adapter.py) - 400+ lines manual prompt/JSON parsing
- [LLMPort Interface](../../src/domain/ports/llm_port.py) - 13 abstract methods to implement

**Dependencies**: None (can run in parallel with other work)

---

## Overview

**Date**: 2025-11-16
**Description**: Replace manual OpenAI prompt construction and JSON parsing with LangChain LCEL (Expression Language) chains. Implement `LangChainAdapter(LLMPort)` with structured output, multi-provider fallback, and retry logic.

**Implementation Status**: Not Started
**Review Status**: Not Reviewed

---

## Key Insights from Research

1. **LCEL Chains**: Use `prompt | model | parser` composition (async-first, composable)
2. **Structured Output**: `model.with_structured_output(Pydantic)` > `PydanticOutputParser` > manual JSON
3. **Fallbacks**: `primary.with_fallbacks([secondary, tertiary])` for auto provider switching
4. **Async FastAPI**: Use `ainvoke()` for single calls, `astream()` for WebSocket streaming
5. **Batch Calls**: `RunnableParallel` for concurrent independent LLM calls
6. **Clean Architecture**: LangChain ONLY in adapter layer, map Pydantic → domain models

---

## Requirements

### Functional Requirements
- Implement all 13 `LLMPort` methods using LangChain
- Support OpenAI (primary) and Anthropic Claude (optional fallback)
- Return domain models (not Pydantic) to preserve Clean Architecture
- Feature flag: `settings.use_langchain` (default: `false`)
- Backward compatible: existing tests pass with flag disabled

### Non-Functional Requirements
- 30% reduction in adapter boilerplate vs manual OpenAI implementation
- Async/await throughout (FastAPI compatible)
- Retry logic: exponential backoff (built-in to LangChain models)
- LangSmith tracing enabled in dev (optional in production)
- Token usage tracking per method call

---

## Architecture

### Layer Changes

**Adapter Layer**:
- **New**: `src/adapters/llm/langchain_adapter.py` (core implementation)
- **New**: `src/adapters/llm/prompts/` (prompt templates)
- **Modified**: DI container to inject LangChain adapter based on feature flag

**Infrastructure Layer**:
- **New**: `src/infrastructure/config/langchain_settings.py` (LangChain config)
- **Modified**: `src/infrastructure/config/settings.py` (add `use_langchain` flag)

### New Components

**1. Prompt Repository (Database-Backed)**:
```python
# src/adapters/llm/prompt_repository.py
class PromptRepository:
    def __init__(self, session: AsyncSession, cache_ttl: int = 300):
        self.session = session
        self.cache = {}  # In-memory cache (5-min TTL)
        self.fallback_prompts = PYTHON_FALLBACK_PROMPTS  # Safety net

    async def get_active_prompt(self, name: str) -> ChatPromptTemplate:
        """Fetch active prompt from DB, use cache/fallback if unavailable."""
        # 1. Check cache
        if name in self.cache and not self._cache_expired(name):
            return self.cache[name]

        # 2. Try database
        try:
            prompt = await self._fetch_from_db(name)
            self.cache[name] = (prompt, time.time())
            return prompt
        except Exception:
            # 3. Fallback to Python constant
            return self.fallback_prompts[name]
```

**2. LangChainAdapter Class**:
```python
class LangChainAdapter(LLMPort):
    def __init__(self, model: ChatLanguageModel, prompt_repo: PromptRepository):
        self.model = model
        self.prompt_repo = prompt_repo

    async def generate_question(self, context, skill, difficulty, exemplars):
        # Load prompt from database
        prompt = await self.prompt_repo.get_active_prompt("generate_question")

        # Build chain: prompt | model | parser
        chain = prompt | self.model | PydanticOutputParser(pydantic_object=QuestionOutput)

        # Execute
        result = await chain.ainvoke({
            "skill": skill,
            "difficulty": difficulty,
            "context": context,
            "exemplars": exemplars
        })

        # Log execution for analytics
        await self._log_prompt_execution("generate_question", result)

        return result.question_text
```

**3. Pydantic Output Models**:
```python
class QuestionOutput(BaseModel):
    question_text: str
    reasoning: str

class EvaluationOutput(BaseModel):
    score: float
    feedback: str
    strengths: list[str]
    weaknesses: list[str]
    missing_concepts: list[str]
```

**3. Prompt Templates** (YAML or Python):
```yaml
# prompts/generate_question_v1.yaml
version: "1.0"
messages:
  - role: system
    content: "You are an expert technical interviewer..."
  - role: user
    content: "Generate a {difficulty} question for {skill}..."
```

---

## Related Code Files

### Existing Files to Modify
- `src/infrastructure/dependency_injection/container.py` (add LangChain factory)
- `src/infrastructure/config/settings.py` (add `use_langchain`, `langsmith_api_key`)
- `src/adapters/llm/__init__.py` (export LangChainAdapter)

### New Files to Create
- `src/adapters/llm/langchain_adapter.py` (~500 lines)
- `src/adapters/llm/prompts/generate_question.py`
- `src/adapters/llm/prompts/evaluate_answer.py`
- `src/adapters/llm/prompts/generate_ideal_answer.py`
- `src/adapters/llm/prompts/detect_gaps.py`
- `src/adapters/llm/prompts/generate_followup.py`
- `src/adapters/llm/prompts/generate_feedback_report.py`
- `src/adapters/llm/prompts/batch_prompts.py` (for batch methods)
- `src/infrastructure/config/langchain_settings.py` (~50 lines)
- `tests/unit/adapters/llm/test_langchain_adapter.py` (unit tests)
- `tests/integration/adapters/llm/test_langchain_integration.py` (integration tests)

---

## Implementation Steps

### Step 1: Setup Dependencies (1 day)
1. Add LangChain packages to `pyproject.toml`:
   ```toml
   langchain = "^0.2.0"
   langchain-openai = "^0.2.0"
   langchain-anthropic = "^0.2.0"
   langsmith = "^0.1.0"
   ```
2. Run `pip install -e ".[dev]"` to install
3. Update `.env.example` with LangChain config:
   ```env
   USE_LANGCHAIN=false
   LANGSMITH_API_KEY=
   ENABLE_LANGSMITH_TRACING=false
   ```

### Step 2: Create Configuration (1 day)
1. Create `src/infrastructure/config/langchain_settings.py`:
   - LangSmith tracing setup
   - Model configuration (temperature, max_tokens)
   - Retry settings
2. Update `src/infrastructure/config/settings.py`:
   - Add `use_langchain: bool = False`
   - Add `enable_langsmith: bool = False`
   - Add `langsmith_api_key: str | None = None`

### Step 3: Build Pydantic Output Models (1 day)
1. Create internal Pydantic models for LLM outputs:
   - `QuestionOutput`, `EvaluationOutput`, `IdealAnswerOutput`
   - `GapDetectionOutput`, `FollowUpOutput`, `RecommendationsOutput`
2. Add validation rules (score 0-100, non-empty lists, etc.)

### Step 4: Create Prompt Templates (2 days)
1. Extract prompts from `openai_adapter.py` into separate files
2. Convert to `ChatPromptTemplate.from_messages()` format
3. Create templates for 13 methods (1-2 hours each):
   - `generate_question` - With exemplar support
   - `evaluate_answer` - With follow-up context
   - `generate_ideal_answer`
   - `generate_rationale`
   - `detect_concept_gaps`
   - `generate_followup_question`
   - `generate_feedback_report`
   - `summarize_cv`
   - `extract_skills_from_text`
   - `generate_interview_recommendations`
   - `generate_questions_batch` (RunnableParallel)
   - `generate_ideal_answers_batch`
   - `generate_rationales_batch`

### Step 5: Implement LangChainAdapter (3 days)
1. Create `src/adapters/llm/langchain_adapter.py`
2. Implement constructor:
   - Accept `ChatLanguageModel` (injected by DI)
   - Build all LCEL chains in `_build_chains()`
3. Implement 13 LLMPort methods:
   - Load prompt template
   - Chain: `template | model.with_structured_output(Pydantic)`
   - Call: `result = await chain.ainvoke(context)`
   - Map: Pydantic → domain model
4. Add batch methods with `RunnableParallel`:
   ```python
   parallel_chain = RunnableParallel({
       f"q_{i}": question_chain
       for i in range(len(specs))
   })
   ```

### Step 6: Multi-Provider Fallback (1 day)
1. Implement fallback chain:
   ```python
   primary = ChatOpenAI(api_key=..., max_retries=0)
   fallback = ChatAnthropic(api_key=..., max_retries=0)
   model = primary.with_fallbacks([fallback])
   ```
2. Configure via `settings.enable_fallback`, `settings.fallback_provider`

### Step 7: DI Container Integration (1 day)
1. Update `src/infrastructure/dependency_injection/container.py`:
   ```python
   def configure_llm_port(settings: Settings) -> LLMPort:
       if settings.use_langchain:
           model = ChatOpenAI(api_key=settings.openai_api_key)
           return LangChainAdapter(model)
       else:
           return OpenAIAdapter(...)  # Existing
   ```

### Step 8: Testing (2 days)
1. Unit tests (`test_langchain_adapter.py`):
   - Mock `ChatLanguageModel` responses
   - Test all 13 methods return domain models
   - Test Pydantic → domain mapping
2. Integration tests (`test_langchain_integration.py`):
   - Use real OpenAI API (small test cases)
   - A/B test: LangChain vs OpenAI adapter (same inputs → same outputs)
3. Run existing test suite with `USE_LANGCHAIN=true` (must pass)

### Step 9: LangSmith Integration (1 day)
1. Enable tracing in dev:
   ```python
   if settings.enable_langsmith:
       os.environ["LANGCHAIN_TRACING_V2"] = "true"
       os.environ["LANGCHAIN_API_KEY"] = settings.langsmith_api_key
   ```
2. Add metadata tagging:
   ```python
   metadata = {"interview_id": interview.id, "method": "generate_question"}
   await chain.ainvoke(context, config={"metadata": metadata})
   ```
3. Verify traces appear in LangSmith UI

### Step 10: Documentation (1 day)
1. Create `docs/langchain-integration-guide.md`:
   - Developer guide for using LangChain adapter
   - How to add new prompt templates
   - How to enable/disable feature flag
2. Update `CLAUDE.md` with LangChain patterns
3. Add inline docstrings to all methods

---

## Todo List

- [ ] Add LangChain dependencies to `pyproject.toml`
- [ ] Create `langchain_settings.py` configuration
- [ ] Add feature flags to `settings.py`
- [ ] Create Pydantic output models (10 total)
- [ ] Extract prompt templates from OpenAI adapter
- [ ] Implement `LangChainAdapter.__init__()` and `_build_chains()`
- [ ] Implement 13 LLMPort methods with LCEL chains
- [ ] Add multi-provider fallback (OpenAI → Claude)
- [ ] Update DI container factory
- [ ] Write unit tests (mock model responses)
- [ ] Write integration tests (real API calls)
- [ ] A/B test: LangChain vs OpenAI outputs
- [ ] Enable LangSmith tracing in dev
- [ ] Add metadata tagging for traces
- [ ] Document usage in `docs/langchain-integration-guide.md`
- [ ] Update `CLAUDE.md` with patterns
- [ ] Run full test suite with feature flag enabled

---

## Success Criteria

**Measurable Outcomes**:
- All 13 `LLMPort` methods implemented with LangChain
- Existing test suite passes with `USE_LANGCHAIN=true` (100% backward compatibility)
- 30% reduction in adapter code lines (500 vs 400+ in OpenAI adapter)
- LangSmith traces visible for all LLM calls (dev environment)
- A/B test: LangChain outputs match OpenAI adapter outputs (>95% similarity)
- Token usage tracked per method call
- Feature flag allows instant rollback

---

## Risk Assessment

**Technical Risks**:
1. **Pydantic → Domain mapping bugs** - Mitigation: Strict validation in tests
2. **Token cost increase from verbose prompts** - Mitigation: Benchmark before/after
3. **LangChain API breaking changes** - Mitigation: Pin versions in `pyproject.toml`

**Low Risk**: No domain layer changes, feature flag allows instant disable.

---

## Security Considerations

1. **API Key Management**: LangSmith API key in `.env.local` (not committed)
2. **PII in Traces**: Filter candidate names/emails in metadata
3. **Prompt Injection**: Validate user inputs before passing to LLM
4. **Rate Limiting**: LangChain models have built-in retry + backoff

---

## Next Steps

1. Review research report: `research/researcher-01-langchain-adapters.md`
2. Set up LangSmith account (free tier: 5K traces/month)
3. Start Step 1: Add dependencies
4. After completion: Proceed to Phase 2 (LangGraph Planning Workflow)

---

**Dependencies**: None
**Blocks**: Phase 2 (optional - can run in parallel)
**Follow-up Work**: Phase 2 uses LangChain adapter in LangGraph workflows
