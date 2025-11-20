# Phase 6: LLM Integration (Optional)

**Parent**: [Implementation Plan](./plan.md)
**Dependencies**: [Phase 3](./phase-03-repository-layer.md)
**Created**: 2025-11-20
**Duration**: 2-3 days
**Priority**: Low (Optional)
**Status**: ✅ Complete

---

## Overview

**OPTIONAL PHASE**: Integrate prompt management with existing LLM adapters. Modify `OpenAIAdapter`, `LangChainAdapter`, and `ClaudeAdapter` to load prompts from DB and log executions.

**Goals**:
- ✅ LLM adapters load prompts from DB (not hardcoded)
- ✅ Every LLM call logged to `prompt_executions`
- ✅ Backward compatible (optional `prompt_repository` parameter)

**Why Optional**: Can deploy prompt management system without LLM integration. Existing hardcoded prompts continue to work.

---

## Migration Strategy

**Backward Compatible Approach**:
- Add `prompt_repository: PromptRepositoryPort | None = None` to adapter constructors
- If `prompt_repository is None` → use hardcoded prompts (current behavior)
- If `prompt_repository is not None` → use DB prompts (new behavior)

**Benefits**:
- Incremental rollout (method by method)
- No breaking changes to existing code
- Easy rollback

---

## LLM Adapter Modifications

### File: `src/adapters/llm/openai_adapter.py`

**Current**: Hardcoded prompts in methods

**New**: Load from DB, log executions

**Changes**:

```python
"""OpenAI LLM adapter with prompt management integration."""

import time
from typing import Any

from openai import AsyncOpenAI

from ...domain.ports.llm_port import LLMPort
from ...domain.ports.prompt_repository_port import PromptRepositoryPort


class OpenAIAdapter(LLMPort):
    """OpenAI adapter with DB-based prompt management."""

    def __init__(
        self,
        api_key: str,
        model: str,
        prompt_repository: PromptRepositoryPort | None = None,  # OPTIONAL
    ):
        """Initialize adapter with optional prompt repository."""
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
        self.prompt_repo = prompt_repository  # Can be None

    async def generate_question(
        self,
        context: dict[str, Any],
        skill: str,
        difficulty: str,
        exemplars: list[dict] | None = None,
    ) -> str:
        """Generate question using DB-managed prompt (if available)."""
        start_time = time.time()

        # NEW: Load prompt from DB (if repo available)
        if self.prompt_repo:
            prompt_template = await self.prompt_repo.get_active_prompt(
                name="question_generation"
            )

            if not prompt_template:
                raise ValueError("No active prompt found for 'question_generation'")

            prompt_text = prompt_template.get_prompt_text(
                skill=skill,
                difficulty=difficulty,
                cv_summary=context.get("cv_summary", "N/A"),
                exemplars="\n".join(str(e) for e in exemplars) if exemplars else "None",
            )
        else:
            # FALLBACK: Use hardcoded prompt (current behavior)
            prompt_text = self._build_hardcoded_question_prompt(
                skill, difficulty, context
            )

        # Execute LLM call
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt_text}],
                temperature=0.7,
            )

            output_text = response.choices[0].message.content.strip()

            # NEW: Log execution (if repo available)
            if self.prompt_repo and prompt_template:
                await self.prompt_repo.log_execution(
                    prompt_template_id=prompt_template.id,
                    execution_data={
                        "interview_id": context.get("interview_id"),
                        "candidate_id": context.get("candidate_id"),
                        "input_variables": {
                            "skill": skill,
                            "difficulty": difficulty,
                            "cv_summary": context.get("cv_summary"),
                        },
                        "output_text": output_text[:10000],  # Truncate
                        "tokens_used": response.usage.total_tokens,
                        "prompt_tokens": response.usage.prompt_tokens,
                        "completion_tokens": response.usage.completion_tokens,
                        "latency_ms": int((time.time() - start_time) * 1000),
                        "model_name": self.model,
                        "success": True,
                        "error_message": None,
                    },
                )

            return output_text

        except Exception as e:
            # NEW: Log failed execution (if repo available)
            if self.prompt_repo and prompt_template:
                await self.prompt_repo.log_execution(
                    prompt_template_id=prompt_template.id,
                    execution_data={
                        "interview_id": context.get("interview_id"),
                        "candidate_id": context.get("candidate_id"),
                        "input_variables": {"skill": skill, "difficulty": difficulty},
                        "output_text": None,
                        "latency_ms": int((time.time() - start_time) * 1000),
                        "model_name": self.model,
                        "success": False,
                        "error_message": str(e),
                    },
                )
            raise

    def _build_hardcoded_question_prompt(
        self, skill: str, difficulty: str, context: dict
    ) -> str:
        """FALLBACK: Build hardcoded prompt (current behavior)."""
        # ... existing hardcoded prompt logic
        return f"Generate question for {skill} at {difficulty} level..."
```

**Repeat Pattern** for all LLMPort methods:
- `evaluate_answer()`
- `generate_ideal_answer()`
- `generate_rationale()`
- `detect_gaps()`
- `generate_follow_up()`
- `generate_feedback_report()`

---

## Dependency Injection Updates

**File**: `src/infrastructure/dependency_injection/container.py`

**Changes**:

```python
def configure_llm_adapter(
    settings: Settings,
    prompt_repository: PromptRepositoryPort | None = None,  # OPTIONAL
) -> LLMPort:
    """Configure LLM adapter with optional prompt repository."""

    if settings.llm_provider == "openai":
        return OpenAIAdapter(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            prompt_repository=prompt_repository,  # Can be None
        )
    elif settings.llm_provider == "claude":
        return ClaudeAdapter(
            api_key=settings.claude_api_key,
            model=settings.claude_model,
            prompt_repository=prompt_repository,
        )
    # ... other providers


def configure_prompt_repository(session: AsyncSession) -> PromptRepositoryPort:
    """Configure prompt repository."""
    return PostgreSQLPromptRepository(session=session)


# Usage in container setup
async def setup_container(session: AsyncSession) -> Container:
    """Setup DI container with dependencies."""
    settings = get_settings()

    # Create prompt repository
    prompt_repo = configure_prompt_repository(session)

    # Create LLM adapter with prompt repository
    llm_adapter = configure_llm_adapter(
        settings=settings,
        prompt_repository=prompt_repo,  # Enable DB prompts
    )

    return Container(
        llm_adapter=llm_adapter,
        prompt_repository=prompt_repo,
        # ... other dependencies
    )
```

---

## Implementation Steps

### Step 1: Modify OpenAIAdapter (1 day)
- [ ] Add `prompt_repository` parameter to `__init__`
- [ ] Modify `generate_question()` with DB loading + logging
- [ ] Modify `evaluate_answer()` with DB loading + logging
- [ ] Modify remaining 5 methods
- [ ] Keep `_build_hardcoded_*()` methods as fallback

### Step 2: Modify LangChainAdapter (1 day)
- [ ] Same pattern as OpenAIAdapter
- [ ] Update all LangChain LCEL chains

### Step 3: Modify ClaudeAdapter (Optional, 1 day)
- [ ] Same pattern as OpenAIAdapter

### Step 4: Update DI Container (2-3 hours)
- [ ] Add `configure_prompt_repository()` method
- [ ] Modify `configure_llm_adapter()` to accept `prompt_repository`
- [ ] Wire dependencies in `setup_container()`

### Step 5: Integration Testing (1 day)
- [ ] Test LLM adapters with DB prompts
- [ ] Test execution logging
- [ ] Test fallback to hardcoded prompts (when `prompt_repo=None`)
- [ ] Verify analytics aggregation

---

## Testing

### Integration Tests

**File**: `tests/integration/test_llm_adapter_prompt_integration.py`

```python
async def test_generate_question_uses_db_prompt(db_session, openai_adapter):
    """Test LLM adapter loads prompt from DB."""
    # Seed prompt
    repo = PostgreSQLPromptRepository(db_session)
    prompt = await repo.create_initial_prompt(
        name="question_generation",
        template_json={
            "system": "Test system",
            "user_template": "Generate for {skill}",
            "variables": ["skill", "difficulty", "cv_summary", "exemplars"],
        },
        created_by="test",
    )
    await repo.activate_version(prompt.id, "test", "Test", traffic_percentage=100)

    # Call adapter (should use DB prompt)
    question = await openai_adapter.generate_question(
        context={"interview_id": uuid4()},
        skill="Python",
        difficulty="medium",
    )

    assert question  # Got response

    # Verify execution logged
    analytics = await repo.get_analytics_summary("question_generation")
    assert analytics["versions"][0]["total_executions"] == 1

async def test_fallback_to_hardcoded_prompt():
    """Test adapter uses hardcoded prompt when repo is None."""
    adapter = OpenAIAdapter(
        api_key="test-key",
        model="gpt-4",
        prompt_repository=None,  # No DB prompts
    )

    # Should use hardcoded prompt
    question = await adapter.generate_question(
        context={},
        skill="Python",
        difficulty="medium",
    )

    assert question  # Got response (using hardcoded prompt)
```

---

## Rollout Plan

**Phase 6A: Enable for 1 Method** (Day 1)
- Integrate `generate_question()` only
- Deploy to staging
- Monitor analytics, verify logging
- Verify A/B testing works

**Phase 6B: Enable for All Methods** (Day 2-3)
- Integrate remaining 6 methods
- Deploy to staging
- Full integration testing
- Monitor performance

**Phase 6C: Production Rollout** (Day 4)
- Deploy to production
- Monitor analytics dashboard
- Verify no regressions

**Rollback**: Set `prompt_repository=None` in DI container (reverts to hardcoded prompts)

---

## Success Criteria

- ✅ All LLM adapters support `prompt_repository` parameter
- ✅ DB prompts loaded and rendered correctly
- ✅ Executions logged to `prompt_executions` table
- ✅ Analytics aggregation working (materialized view)
- ✅ Backward compatible (hardcoded prompts work when `repo=None`)
- ✅ No performance regression (<10ms overhead for DB loading)

---

## Related Files

**Modified Files**:
- `src/adapters/llm/openai_adapter.py` (add DB loading + logging)
- `src/adapters/llm/langchain_adapter.py` (add DB loading + logging)
- `src/adapters/llm/claude_adapter.py` (optional)
- `src/infrastructure/dependency_injection/container.py` (wire prompt_repository)

**New Files**:
- `tests/integration/test_llm_adapter_prompt_integration.py`

---

## Performance Impact

**Expected Overhead**:
- DB query to load prompt: ~5ms (cached)
- Prompt rendering: ~1ms
- Execution logging: ~5ms (async INSERT)
- **Total**: ~10ms per LLM call

**Mitigation**:
- Cache active prompts in memory (TTL 5 minutes)
- Batch execution logging (every 10 executions)

---

## Notes

- This phase is **OPTIONAL** - prompt management works without LLM integration
- Existing hardcoded prompts continue to work (backward compatible)
- Can enable per-method (incremental rollout)
- Recommended: Start with 1 method, verify analytics, then roll out to all methods

---

**Phase Status**: Optional (can skip if not ready)
**Last Updated**: 2025-11-20
