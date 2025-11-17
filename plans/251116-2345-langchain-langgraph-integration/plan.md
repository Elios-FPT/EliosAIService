# LangChain & LangGraph Integration Plan

**Plan ID**: 251116-2345
**Created**: 2025-11-16
**Status**: Draft
**Priority**: High
**Estimated Duration**: 5-7 weeks (includes Phase 0 validation)

---

## Overview

Integrate **LangChain** (composable async LLM primitives) and **LangGraph** (state machine workflows) into Elios AI Interview Service to:
- Replace manual prompt/JSON parsing with declarative LCEL chains
- Migrate sequential question planning to parallel LangGraph workflows
- Add PostgreSQL checkpointing for crash recovery
- Enable WebSocket workflow streaming for real-time interview state
- Add LangSmith observability for debugging/cost tracking

**Architecture Impact**: Adapter & Application layers only (preserves Clean Architecture).

---

## Success Metrics

**Performance**:
- 3-5x faster question generation (parallel vs sequential LLM calls)
- 30% reduction in adapter boilerplate code (LCEL vs manual)

**Reliability**:
- Resume interview workflows on crash (PostgreSQL checkpointing)
- Multi-provider fallback (OpenAI → Claude → Llama) with zero manual retry logic

**Observability**:
- LangSmith traces for all LLM calls (interview_id tagged)
- Token cost tracking per interview session
- Visual workflow graphs for debugging

---

## Phase Summary

| Phase | Status | Progress | Est. Time | Risk |
|-------|--------|----------|-----------|------|
| [Phase 0: Prototypes & Benchmarks](phase-00-prototypes-benchmarks.md) | **COMPLETE** | 100% | 1 day | Low |
| [Phase 1: LangChain Adapter Layer](phase-01-langchain-adapter.md) | Not Started | 0% | 1.5 weeks | Low |
| [Phase 2: LangGraph Planning Workflow](phase-02-langgraph-planning.md) | Not Started | 0% | 2 weeks | Medium |
| [Phase 3A: Adaptive Workflow (Simple)](phase-03a-adaptive-workflow-simple.md) | Not Started | 0% | 1 week | Medium |
| [Phase 3B: WebSocket Interrupts](phase-03b-websocket-interrupts.md) | Not Started | 0% | 1 week | High |
| [Phase 4: Observability & Optimization](phase-04-observability.md) | Not Started | 0% | 1 week | Low |

---

## Implementation Strategy

**Phased Rollout**: Feature flags for gradual migration
- Phase 1: `USE_LANGCHAIN=true` (adapter swappable)
- Phase 2: `USE_LANGGRAPH_PLANNING=true` (planning workflow)
- Phase 3: `USE_LANGGRAPH_ADAPTIVE=true` (WebSocket workflow)
- Phase 4: `ENABLE_LANGSMITH=true` (production tracing)

**Backward Compatibility**: Existing tests MUST pass with feature flags disabled.

**Testing**: A/B test LangChain vs OpenAI adapter outputs for consistency.

---

## Architecture Changes

**Layers Modified**:
- **Adapter Layer**: New `LangChainAdapter(LLMPort)` implementation
- **Application Layer**: New `PlanningWorkflow`, `AdaptiveEvalWorkflow` classes
- **Infrastructure Layer**: LangSmith config, PostgreSQL checkpointer setup

**Unchanged**:
- **Domain Layer**: Zero LangChain imports (preserves Clean Architecture)
- **Ports**: `LLMPort` interface unchanged (adapter swappable)

---

## Risk Assessment

**Technical Risks**:
1. **LangGraph learning curve** - Mitigation: Start with simple planning workflow (Phase 2)
2. **PostgreSQL checkpointer performance** - Mitigation: Connection pooling, test with 1000+ checkpoints
3. **LangSmith PII exposure** - Mitigation: Filter candidate names/emails in metadata
4. **Cost increase from verbose prompts** - Mitigation: Benchmark token usage, optimize templates

**Rollback Plan**: Feature flags allow instant disable. Existing OpenAI adapter remains functional.

---

## User Decisions (APPROVED)

1. **Multi-LLM fallback**: ✅ Skip for now (defer to Phase 5)
2. **WebSocket timeout**: ✅ 10 minutes before checkpoint cleanup
3. **Cost tolerance**: ✅ +30% acceptable IF 3x faster, +40% triggers optimization, >50% reconsider

## Resolved via Phase 0

4. **Token cost impact**: Will be validated in Phase 0 benchmark
5. **Interrupt pattern viability**: Will be validated in Phase 0 prototype
6. **Performance gain**: Will be validated in Phase 0 baseline

## Architectural Decisions (Updated with Database Strategy)

7. **Prompt storage**: ✅ PostgreSQL JSONB + Python fallback (enables UI, A/B testing, analytics)
8. **Prompt caching**: ✅ In-memory (5-min TTL) for performance
9. **Checkpointer**: ✅ PostgreSQL (reuse existing engine, persistent)
10. **Mock strategy**: ✅ Integration tests (mock LangChain too brittle)
11. **Thread ID storage**: ✅ Separate `websocket_sessions` table (clean separation, analytics-ready)
12. **Session cleanup**: ✅ Background task (APScheduler, 5-min interval, 10-min idle timeout)

---

## Documentation

**New Docs**:
- `docs/langchain-integration-guide.md` - Developer guide
- `docs/langgraph-workflow-diagrams.md` - Visual StateGraph diagrams
- `plans/251116-2345-langchain-langgraph-integration/research/` - Research reports (2 files)

**Updated Docs**:
- `docs/system-architecture.md` - Add LangGraph workflows section
- `docs/codebase-summary.md` - Add new files to structure
- `CLAUDE.md` - Add LangChain/LangGraph development patterns

---

## Dependencies

**External Libraries**:
```python
# pyproject.toml additions
langchain = "^0.2.0"
langchain-openai = "^0.2.0"
langchain-anthropic = "^0.2.0"  # Optional
langgraph = "^0.2.0"
langgraph-checkpoint-postgres = "^0.2.0"
langsmith = "^0.1.0"  # Observability
```

**Database Schema Additions**:
- LangGraph auto-creates `checkpoints` table (no manual migrations)
- Manual: `prompt_templates` table (Phase 1) - UI-editable prompts with versioning
- Manual: `prompt_executions` table (Phase 1) - Analytics tracking
- Manual: `websocket_sessions` table (Phase 3B) - Session lifecycle management

---

## Phase 0 Completion Status

**Status**: COMPLETE (2025-11-17)
**Duration**: 1 day (estimated 3-4 days)
**Results**:
- Performance: PASS (5.8x speedup exceeds 3x target)
- Interrupt Pattern: PARTIAL PASS (core mechanism validated, state update needs refinement)
- Token Usage: PENDING (requires real API testing before Phase 1)

**Validation Report**: `reports/phase-00-validation-report.md`

## Next Steps

**BEFORE Phase 1 Start**:
1. ⚠️ **CRITICAL**: Run token benchmark with real OpenAI/Azure API (`tests/prototypes/01_token_benchmark.py`)
2. Verify token increase <40% (user tolerance threshold)
3. If >40%, spend 1 day optimizing prompts

**After Token Validation**:
1. Start Phase 1: LangChain adapter implementation
2. Set up LangSmith account for tracing (dev environment)
3. Configure PostgreSQL checkpointer on dev database
4. A/B test LangChain vs OpenAI adapter outputs

---

**Plan Status**: Phase 0 Complete - Awaiting Token Validation for Phase 1
**Blocked By**: Token benchmark needs real API credentials
**Blocking**: Phase 1-4 start (pending token validation)
