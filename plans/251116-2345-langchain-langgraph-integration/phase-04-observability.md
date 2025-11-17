# Phase 4: Observability & Optimization

**Phase ID**: 04
**Created**: 2025-11-16
**Priority**: Medium
**Estimated Duration**: 1 week
**Risk Level**: Low
**Implementation Status**: Not Started
**Review Status**: Pending

---

## Context Links

- **Parent Plan**: [plan.md](plan.md)
- **Dependencies**: Phase 1-3 (LangChain/LangGraph implemented)
- **Related Docs**:
  - [Research: LangChain Observability](research/researcher-01-langchain-adapters.md)
  - [Project Overview - Success Metrics](../../docs/project-overview-pdr.md#success-metrics)

---

## Overview

Add production-grade observability with LangSmith tracing, performance monitoring, and cost tracking for all LangChain/LangGraph workflows.

**Current Problem**:
- No visibility into LLM call chains (prompt → response → parsing)
- No token usage tracking per interview session
- Difficult to debug workflow failures (which node failed?)
- No cost attribution to candidates or interviews

**Solution**:
- LangSmith integration for automatic tracing
- Custom metadata tagging (interview_id, candidate_id)
- Cost dashboards and alerts
- Workflow visualization for debugging
- PII filtering for compliance

---

## Key Insights

**From Research**:
1. **Auto-Tracing**: LangSmith captures ALL LangChain/LangGraph calls (prompts, responses, tokens)
2. **Custom Metadata**: Tag traces with business context (interview_id, candidate_id, question_type)
3. **Cost Tracking**: Automatic token counting and cost calculation per trace
4. **Workflow Viz**: StateGraph execution visualized in UI (node-by-node)
5. **PII Filtering**: Callbacks to redact sensitive data before sending to LangSmith

---

## Requirements

### Functional Requirements
**FR1**: Enable LangSmith tracing in production with env vars
**FR2**: Tag all traces with interview_id, candidate_id, question_type
**FR3**: Filter PII (candidate names, emails, CV text) from traces
**FR4**: Track token usage and cost per interview session
**FR5**: Export workflow graphs for documentation
**FR6**: Alert on high error rates or costs

### Non-Functional Requirements
**NFR1**: Performance: Tracing overhead <10ms per LLM call
**NFR2**: Privacy: Zero PII leakage to LangSmith servers
**NFR3**: Cost: LangSmith free tier sufficient for dev (<10K traces/month)
**NFR4**: Reliability: Tracing failures don't break workflows

---

## Architecture

### LangSmith Integration Points
```
┌─────────────────────────────────────────────────┐
│ LangChain/LangGraph Calls                       │
│   ↓                                             │
│ [Tracing Callback Handler]                     │
│   ├─ Add metadata (interview_id, ...)          │
│   ├─ Filter PII (names, emails)                │
│   └─ Send to LangSmith API                     │
│       ↓                                         │
│ [LangSmith Cloud]                               │
│   ├─ Store traces (prompts, outputs, tokens)   │
│   ├─ Calculate costs (GPT-4: $0.03/1K tokens)  │
│   └─ Generate visualizations                   │
└─────────────────────────────────────────────────┘
```

### Configuration Strategy
```python
# .env.local (dev)
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_dev_key
LANGCHAIN_PROJECT=elios-interviews-dev

# .env.production
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_prod_key
LANGCHAIN_PROJECT=elios-interviews-prod
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com  # Optional custom endpoint
```

### Custom Metadata Tagging
```python
# src/adapters/llm/langchain_adapter.py
async def generate_question(self, context, skill, difficulty):
    with tracing_v2_enabled(
        metadata={
            "interview_id": str(context.get("interview_id")),
            "candidate_id": str(context.get("candidate_id")),
            "skill": skill,
            "difficulty": difficulty,
            "question_type": "technical"
        }
    ):
        result = await chain.ainvoke(...)
    return result
```

### PII Filtering Callback
```python
# src/infrastructure/observability/langsmith_config.py
from langchain.callbacks import LangChainTracer

class PIIFilteringTracer(LangChainTracer):
    def __init__(self):
        super().__init__()
        self.pii_patterns = [
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',  # emails
            r'\b\d{3}-\d{2}-\d{4}\b',  # SSN
        ]

    def _filter_pii(self, text: str) -> str:
        """Redact PII patterns from text."""
        for pattern in self.pii_patterns:
            text = re.sub(pattern, "[REDACTED]", text)
        return text

    def on_llm_start(self, serialized, prompts, **kwargs):
        prompts = [self._filter_pii(p) for p in prompts]
        super().on_llm_start(serialized, prompts, **kwargs)
```

---

## Related Code Files

### Existing Files to Modify
1. **`src/infrastructure/config/settings.py`**:
   - Add LangSmith settings:
     ```python
     enable_langsmith: bool = Field(default=False, env="ENABLE_LANGSMITH")
     langchain_tracing_v2: bool = Field(default=False, env="LANGCHAIN_TRACING_V2")
     langchain_api_key: str | None = Field(default=None, env="LANGCHAIN_API_KEY")
     langchain_project: str = Field(default="elios-interviews", env="LANGCHAIN_PROJECT")
     ```

2. **`src/adapters/llm/langchain_adapter.py`**:
   - Add metadata to all LLM calls
   - Pass `callbacks=[pii_filtering_tracer]`

3. **`src/application/workflows/planning_workflow.py`**:
   - Tag workflow invocations with interview_id

4. **`src/application/workflows/adaptive_eval_workflow.py`**:
   - Tag workflow invocations with interview_id, question_id

### New Files to Create
1. **`src/infrastructure/observability/langsmith_config.py`** (120 lines):
   - PIIFilteringTracer class
   - Setup function for callbacks
   - Cost calculation utilities

2. **`src/infrastructure/observability/metrics.py`** (80 lines):
   - Prometheus metrics for LLM calls
   - Token usage counters
   - Error rate gauges

3. **`docs/langgraph-workflow-diagrams.md`** (50 lines):
   - Export StateGraph visualizations
   - Embed images in documentation

4. **`scripts/export_workflow_graphs.py`** (60 lines):
   - Script to generate PNG diagrams from StateGraphs

---

## Implementation Steps

### Step 1: LangSmith Account Setup (1 day)
1. Create LangSmith account (free tier)
2. Generate API keys (dev + prod)
3. Create projects:
   - `elios-interviews-dev`
   - `elios-interviews-staging`
   - `elios-interviews-prod`
4. Test tracing with simple chain

### Step 2: Configuration (1 day)
1. Add settings to `settings.py`:
   ```python
   class Settings(BaseSettings):
       # LangSmith Observability
       enable_langsmith: bool = False
       langchain_tracing_v2: bool = False
       langchain_api_key: str | None = None
       langchain_project: str = "elios-interviews"
       langsmith_filter_pii: bool = True
   ```
2. Update `.env.example`:
   ```
   # LangSmith Observability (optional)
   ENABLE_LANGSMITH=false
   LANGCHAIN_TRACING_V2=false
   LANGCHAIN_API_KEY=your_api_key_here
   LANGCHAIN_PROJECT=elios-interviews-dev
   ```
3. Add to DI container initialization

### Step 3: PII Filtering (2 days)
1. Implement `PIIFilteringTracer`:
   - Regex patterns for emails, phone numbers, SSNs
   - Named entity recognition for person names (optional: spaCy)
   - Whitelist fields (interview_id, question_type OK to trace)
2. Unit tests for PII detection:
   - Test email redaction: "john.doe@example.com" → "[REDACTED]"
   - Test name redaction: "My name is John Doe" → "My name is [REDACTED]"
3. Integration test: Verify no PII in LangSmith traces

### Step 4: Metadata Tagging (1 day)
1. Add metadata to LangChain calls:
   ```python
   # In LangChainAdapter
   metadata = {
       "interview_id": str(context["interview_id"]),
       "candidate_id": str(context.get("candidate_id")),
       "question_type": context.get("question_type", "unknown"),
       "difficulty": difficulty,
       "skill": skill,
       "adapter_version": "1.0.0"
   }
   config = RunnableConfig(metadata=metadata)
   result = await chain.ainvoke(input, config=config)
   ```
2. Add metadata to workflows:
   ```python
   # In PlanningWorkflow
   thread_id = f"interview-{interview_id}"
   config = {"configurable": {"thread_id": thread_id}, "metadata": {...}}
   await app.ainvoke(initial_state, config=config)
   ```

### Step 5: Cost Tracking (1 day)
1. Query LangSmith API for token usage:
   ```python
   from langsmith import Client

   client = Client(api_key=settings.langchain_api_key)
   runs = client.list_runs(project_name="elios-interviews-prod", filter={
       "metadata.interview_id": str(interview_id)
   })
   total_tokens = sum(run.total_tokens for run in runs)
   total_cost = total_tokens * 0.00003  # GPT-4 pricing
   ```
2. Store cost in Interview metadata:
   ```python
   interview.metadata["llm_tokens"] = total_tokens
   interview.metadata["llm_cost_usd"] = round(total_cost, 4)
   ```
3. Dashboard query for daily costs

### Step 6: Workflow Visualization (1 day)
1. Export StateGraph as PNG:
   ```python
   # scripts/export_workflow_graphs.py
   from langgraph.graph import StateGraph
   from src.application.workflows.planning_workflow import create_graph

   graph = create_graph()
   png_bytes = graph.get_graph().draw_mermaid_png()
   with open("docs/images/planning-workflow.png", "wb") as f:
       f.write(png_bytes)
   ```
2. Add diagrams to documentation
3. Embed in LangSmith project description

### Step 7: Alerting (1 day)
1. Set up LangSmith alerts:
   - Error rate >5% in production
   - Daily cost >$50
   - Latency >10s for any LLM call
2. Integrate with Slack/email notifications
3. Test alert delivery

---

## Todo List

- [ ] Create LangSmith account and projects
- [ ] Generate API keys for dev/staging/prod
- [ ] Add LangSmith settings to `settings.py`
- [ ] Update `.env.example` with LangSmith vars
- [ ] Implement `PIIFilteringTracer` class
- [ ] Add PII regex patterns (email, phone, SSN)
- [ ] Write unit tests for PII filtering
- [ ] Add metadata tagging to LangChainAdapter
- [ ] Add metadata tagging to PlanningWorkflow
- [ ] Add metadata tagging to AdaptiveEvalWorkflow
- [ ] Implement cost tracking query function
- [ ] Store token/cost in Interview metadata
- [ ] Create workflow graph export script
- [ ] Generate PNG diagrams for all workflows
- [ ] Add diagrams to documentation
- [ ] Set up LangSmith alerts (error rate, cost, latency)
- [ ] Test alert delivery (Slack/email)
- [ ] Create cost dashboard (query LangSmith API)
- [ ] Document LangSmith setup in README

---

## Success Criteria

**Tracing**:
- ✅ All LLM calls visible in LangSmith UI
- ✅ Custom metadata (interview_id, candidate_id) tagged correctly
- ✅ Zero PII leakage (verified by manual audit)

**Cost Tracking**:
- ✅ Token usage and cost calculated per interview
- ✅ Daily cost dashboard functional
- ✅ Alerts trigger on cost thresholds

**Visualization**:
- ✅ Workflow graphs exported and documented
- ✅ LangSmith UI shows StateGraph execution

**Performance**:
- ✅ Tracing overhead <10ms per call (benchmark)

---

## Risk Assessment

### Technical Risks
1. **PII Leakage**:
   - Risk: Regex patterns miss edge cases, PII sent to LangSmith
   - Mitigation: Whitelist approach (only allow known safe fields), manual audits

2. **LangSmith API Limits**:
   - Risk: Free tier exhausted (10K traces/month)
   - Mitigation: Sampling (trace 10% of production calls), upgrade to paid tier

3. **Tracing Performance**:
   - Risk: Callback overhead slows LLM calls
   - Mitigation: Async callbacks, benchmark before/after

4. **Cost Explosion**:
   - Risk: LangChain verbose prompts increase token usage 2x
   - Mitigation: Monitor daily costs, optimize prompts, alerts at $50/day

### Rollback Plan
- Disable tracing: `ENABLE_LANGSMITH=false` (zero impact)
- No database changes required
- Metadata fields optional (backward compatible)

---

## Security Considerations

**PII Protection**:
- Never trace: candidate names, emails, CV full text, phone numbers
- Always trace: interview_id, question_type, difficulty, skill (non-PII)
- Redact: Answer text snippets (keep first 50 chars only)

**API Key Security**:
- Store LangSmith API keys in env vars (never commit)
- Rotate keys quarterly
- Use separate keys for dev/prod (principle of least privilege)

**Data Retention**:
- LangSmith retains traces for 14 days (free tier)
- Purge traces after interview completion (GDPR compliance)
- No production data in dev/staging projects

---

## Cost Analysis

### LangSmith Pricing
**Free Tier**: 10,000 traces/month
**Paid Tier**: $39/month for 50K traces, then $0.0005/trace

### Estimated Usage
- 100 interviews/day × 30 days = 3,000 interviews/month
- 5 questions/interview × 3 LLM calls/question = 15 calls/interview
- 3,000 × 15 = 45,000 traces/month
- **Cost**: Free tier insufficient, need paid tier ($39/month)

### Token Cost Impact
- Current: ~5,000 tokens/interview (GPT-4)
- With LangChain: ~7,000 tokens/interview (+40% verbose prompts)
- 3,000 interviews × 7,000 tokens = 21M tokens/month
- **Cost**: 21M × $0.00003 = $630/month (GPT-4)
- **Increase**: $630 - $450 = $180/month (+40%)

**Mitigation**:
- Optimize prompt templates (reduce verbosity)
- Switch to GPT-4-turbo ($0.01/1K vs $0.03/1K)
- A/B test: Measure quality vs cost trade-off

---

## Metrics & Dashboards

### Key Metrics
1. **Token Usage**:
   - Tokens per interview (avg, p50, p95)
   - Tokens by question type (technical vs behavioral)
   - Daily token consumption trend

2. **Cost**:
   - Cost per interview (USD)
   - Daily cost (USD)
   - Monthly cost projection

3. **Performance**:
   - LLM call latency (p50, p95, p99)
   - Workflow execution time (planning, adaptive eval)
   - Error rate by adapter (OpenAI vs Claude)

4. **Quality**:
   - Follow-up generation rate (% interviews with follow-ups)
   - Average follow-up count (0-3)
   - Combined evaluation score distribution

### Dashboard Queries (LangSmith API)
```python
# Example: Daily cost by interview
from langsmith import Client
from datetime import datetime, timedelta

client = Client(api_key=settings.langchain_api_key)
yesterday = datetime.now() - timedelta(days=1)

runs = client.list_runs(
    project_name="elios-interviews-prod",
    start_time=yesterday,
    filter={"metadata.interview_id": {"$exists": True}}
)

costs_by_interview = {}
for run in runs:
    interview_id = run.metadata.get("interview_id")
    cost = run.total_tokens * 0.00003
    costs_by_interview[interview_id] = costs_by_interview.get(interview_id, 0) + cost

print(f"Total interviews: {len(costs_by_interview)}")
print(f"Total cost: ${sum(costs_by_interview.values()):.2f}")
print(f"Avg cost/interview: ${sum(costs_by_interview.values()) / len(costs_by_interview):.2f}")
```

---

## Documentation Updates

### New Documentation
1. **`docs/langchain-integration-guide.md`**:
   - LangChain adapter usage guide
   - Prompt template management
   - Best practices for LCEL chains

2. **`docs/langgraph-workflow-diagrams.md`**:
   - Visual diagrams for all workflows
   - Node descriptions and state definitions
   - Conditional edge logic explanations

3. **`docs/observability-guide.md`**:
   - LangSmith setup instructions
   - PII filtering configuration
   - Cost tracking and alerts

### Updated Documentation
1. **`docs/system-architecture.md`**:
   - Add "LangChain/LangGraph Integration" section
   - Update "Scalability & Performance" with token cost analysis

2. **`docs/codebase-summary.md`**:
   - Add new files to structure (workflows/, observability/)
   - Update dependencies list

3. **`CLAUDE.md`**:
   - Add LangChain/LangGraph development patterns
   - Update "Working with the Codebase" section

---

## Next Steps

1. **Phase 3 Completion**: Ensure adaptive workflow tested
2. **LangSmith Signup**: Create account and projects
3. **Start Implementation**: Follow step-by-step (Step 1: Account setup)
4. **Documentation**: Write observability guide
5. **Training**: Team demo of LangSmith UI and features

---

**Dependencies**:
- Phase 1-3 (LangChain/LangGraph implemented)
- LangSmith account (free tier sufficient for dev)

**Blocking**:
- None (observability is final phase)
