# Observability Guide

This guide explains how to set up and use LangSmith observability for the Elios AI Interview Service.

## Table of Contents

1. [Overview](#overview)
2. [LangSmith Setup](#langsmith-setup)
3. [PII Filtering](#pii-filtering)
4. [Cost Tracking](#cost-tracking)
5. [Metadata Tagging](#metadata-tagging)
6. [Monitoring & Debugging](#monitoring--debugging)
7. [Best Practices](#best-practices)

---

## Overview

The Elios AI Interview Service integrates with **LangSmith** for comprehensive observability of LLM operations:

- **Tracing**: Track every LLM call with full context (prompts, responses, latency)
- **PII Filtering**: Automatically redact sensitive information before sending traces
- **Cost Tracking**: Monitor token usage and calculate costs per interview
- **Metadata Tagging**: Organize traces by interview_id, candidate_id, skill, etc.
- **Debugging**: Inspect failed chains, compare prompt variations, analyze performance

### Architecture

```
LangChainAdapter (LLM calls)
    ↓
RunnableConfig (metadata + callbacks)
    ↓
PIIFilteringTracer (redacts PII)
    ↓
LangSmith API (stores filtered traces)
```

---

## LangSmith Setup

### 1. Create LangSmith Account

1. Go to [https://smith.langchain.com](https://smith.langchain.com)
2. Sign up for a free account
3. Create a new project (e.g., `elios-interviews-dev`)
4. Generate an API key from Settings → API Keys

### 2. Configure Environment Variables

Add to `.env` or `.env.local`:

```bash
# LangSmith Observability (Phase 4)
ENABLE_LANGSMITH=true  # Enable tracing
LANGCHAIN_TRACING_V2=true  # Use v2 protocol
LANGSMITH_API_KEY="lsv2_pt_..."  # Your API key from LangSmith
LANGCHAIN_PROJECT="elios-interviews-dev"  # Project name
LANGCHAIN_ENDPOINT="https://api.smith.langchain.com"  # API endpoint
LANGSMITH_FILTER_PII=true  # STRONGLY RECOMMENDED
LANGSMITH_SAMPLE_RATE=1.0  # 100% sampling (use 0.1 for 10% in production)
LANGSMITH_MAX_TRACE_SIZE_KB=1024  # Max trace size
```

### 3. Verify Setup

Run the application and check LangSmith dashboard:

```bash
python -m src.main
```

Make an LLM call (e.g., generate a question). You should see traces appear in your LangSmith project within 30 seconds.

---

## PII Filtering

### What Gets Filtered?

The `PIIFilteringTracer` automatically redacts:

| PII Type | Pattern | Example | Redacted As |
|----------|---------|---------|-------------|
| Email | `[a-z0-9._+-]+@[a-z0-9.-]+\.[a-z]{2,}` | `john.doe@example.com` | `[EMAIL_REDACTED]` |
| Phone (US) | `\d{3}[-.]?\d{3}[-.]?\d{4}` | `555-123-4567` | `[PHONE_REDACTED]` |
| SSN | `\d{3}-\d{2}-\d{4}` | `123-45-6789` | `[SSN_REDACTED]` |
| Credit Card | `\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}` | `1234-5678-9012-3456` | `[CC_REDACTED]` |
| Names (context) | `My name is [A-Z][a-z]+ [A-Z][a-z]+` | `My name is John Doe` | `My name is [NAME_REDACTED]` |
| Answer Text | (length-based) | `500-char answer` | `200 chars + [TRUNCATED]` |
| CV Text | (length-based) | `10KB CV` | `100 chars + [CV_REDACTED]` |

### What Gets Preserved?

- **UUIDs**: `interview_id`, `candidate_id`, `question_id` (non-PII identifiers)
- **Metadata**: `difficulty`, `skill`, `question_type` (non-sensitive)
- **Question Text**: Interview questions (assumed non-PII)
- **Scores**: Numeric evaluation scores

### Testing PII Filtering

Run unit tests:

```bash
pytest tests/unit/infrastructure/observability/test_langsmith_config.py -v
```

Example test case:

```python
def test_filter_multiple_pii():
    tracer = PIIFilteringTracer()

    text = """
    My name is Jane Doe.
    Email: jane.doe@company.com
    Phone: 555-987-6543
    """

    filtered = tracer._filter_pii(text)

    assert "Jane Doe" not in filtered
    assert "[EMAIL_REDACTED]" in filtered
    assert "[PHONE_REDACTED]" in filtered
```

### Disabling PII Filtering (NOT RECOMMENDED)

To disable PII filtering (e.g., in local development):

```bash
LANGSMITH_FILTER_PII=false
```

**Warning**: Traces will contain raw candidate data (emails, phone numbers, answers). Only disable in isolated dev environments.

---

## Cost Tracking

### Calculate Cost for a Single Interview

```python
from src.infrastructure.observability.cost_tracking import get_interview_cost
from uuid import UUID

interview_id = UUID("123e4567-e89b-12d3-a456-426614174000")

result = await get_interview_cost(
    interview_id=interview_id,
    langsmith_api_key="lsv2_pt_...",
    project_name="elios-interviews-prod",
)

print(f"Total Cost: ${result['total_cost_usd']}")
print(f"Total Tokens: {result['total_tokens']}")
print(f"Traces: {result['trace_count']}")
print(f"Model Breakdown: {result['model_breakdown']}")
```

**Output:**

```json
{
  "total_tokens": 12500,
  "input_tokens": 8000,
  "output_tokens": 4500,
  "total_cost_usd": 0.45,
  "model_breakdown": {
    "gpt-4": {"tokens": 10000, "cost": 0.39},
    "gpt-4-turbo": {"tokens": 2500, "cost": 0.06}
  },
  "trace_count": 15
}
```

### Get Daily Cost Summary

```python
from src.infrastructure.observability.cost_tracking import get_daily_cost_summary

result = await get_daily_cost_summary(
    langsmith_api_key="lsv2_pt_...",
    project_name="elios-interviews-prod",
    days=7,  # Last 7 days
)

print(f"Total Cost (7 days): ${result['total_cost_usd']}")
print(f"Interviews: {result['interviews_count']}")
print(f"Avg Cost/Interview: ${result['avg_cost_per_interview']}")
```

**Output:**

```json
{
  "start_date": "2025-11-10T00:00:00",
  "end_date": "2025-11-17T00:00:00",
  "total_cost_usd": 125.50,
  "total_tokens": 4500000,
  "total_traces": 450,
  "interviews_count": 100,
  "avg_cost_per_interview": 1.26,
  "model_breakdown": {
    "gpt-4": {"tokens": 3000000, "cost": 90.00},
    "gpt-4-turbo": {"tokens": 1500000, "cost": 35.50}
  }
}
```

### Pricing Table

Current token pricing (as of 2025):

| Model | Input (per 1K tokens) | Output (per 1K tokens) |
|-------|----------------------|------------------------|
| GPT-4 | $0.03 | $0.06 |
| GPT-4 Turbo | $0.01 | $0.03 |
| GPT-3.5 Turbo | $0.0005 | $0.0015 |
| Claude 3 Opus | $0.015 | $0.075 |
| Claude 3 Sonnet | $0.003 | $0.015 |
| Claude 3 Haiku | $0.00025 | $0.00125 |
| Llama 3 70B | $0.001 | $0.001 |

Update pricing in `src/infrastructure/observability/cost_tracking.py` if models change.

### Unit Tests

```bash
pytest tests/unit/infrastructure/observability/test_cost_tracking.py -v
```

---

## Metadata Tagging

### What is Metadata?

Metadata tags allow you to organize and filter traces in LangSmith. Every LLM call is tagged with:

- `interview_id`: UUID of the interview session
- `candidate_id`: UUID of the candidate
- `question_id`: UUID of the question being asked
- `skill`: Skill being evaluated (e.g., "Python", "SQL")
- `difficulty`: Question difficulty ("easy", "medium", "hard")
- `method`: LLM method name (e.g., "generate_question", "evaluate_answer")

### How It Works

The `LangChainAdapter` automatically adds metadata to all LLM calls:

```python
# In LangChainAdapter
config = self._create_config(
    context=context,  # Contains interview_id, candidate_id
    skill=skill,
    difficulty=difficulty,
    method="generate_question",
)

result = await self._chains["generate_question"].ainvoke(inputs, config=config)
```

### Querying by Metadata in LangSmith

**Filter traces by interview:**

```python
from langsmith import Client

client = Client(api_key="lsv2_pt_...")

runs = client.list_runs(
    project_name="elios-interviews-prod",
    filter={"metadata.interview_id": "123e4567-e89b-12d3-a456-426614174000"},
)

for run in runs:
    print(f"{run.name}: {run.total_tokens} tokens")
```

**Filter by skill:**

```python
runs = client.list_runs(
    project_name="elios-interviews-prod",
    filter={"metadata.skill": "Python"},
)
```

**Filter by difficulty:**

```python
runs = client.list_runs(
    project_name="elios-interviews-prod",
    filter={"metadata.difficulty": "hard"},
)
```

---

## Monitoring & Debugging

### LangSmith Dashboard Features

1. **Trace Timeline**: See all LLM calls in chronological order
2. **Latency Analysis**: Identify slow chains
3. **Token Usage**: Track consumption per trace
4. **Error Tracking**: Filter failed runs
5. **Prompt Comparison**: Compare different prompt versions side-by-side

### Common Use Cases

#### 1. Debug a Failed Interview

1. Go to LangSmith dashboard
2. Filter by `interview_id`
3. Look for red error icons
4. Click on failed trace → view full error stack
5. Inspect input/output to identify issue

#### 2. Optimize Prompt Performance

1. Filter by `method: "evaluate_answer"`
2. Sort by latency (descending)
3. Compare slow vs. fast traces
4. Identify common patterns in slow traces (e.g., long answer text)

#### 3. Monitor Daily Costs

```python
# Run this in a cron job (daily)
result = await get_daily_cost_summary(
    langsmith_api_key=settings.langsmith_api_key,
    project_name=settings.langchain_project,
    days=1,
)

if result["total_cost_usd"] > 50.0:
    send_alert(f"Daily cost exceeded $50: ${result['total_cost_usd']}")
```

#### 4. Compare Prompt Versions

1. Create two LangSmith projects: `elios-interviews-v1` and `elios-interviews-v2`
2. Update prompts in v2
3. Run same interview in both projects
4. Compare metrics (latency, token usage, evaluation scores)

### Workflow Visualization

Export workflow graphs to PNG:

```bash
python scripts/export_workflow_graphs.py
```

Output:

```
docs/diagrams/
├── adaptive_eval_simple_workflow.png
├── adaptive_eval_interrupt_workflow.png
├── adaptive_eval_simple_workflow.mmd
└── adaptive_eval_interrupt_workflow.mmd
```

Open `.mmd` files in [mermaid.live](https://mermaid.live/) for interactive editing.

---

## Best Practices

### 1. Separate Projects by Environment

Use different LangSmith projects for each environment:

- `elios-interviews-dev`: Local development
- `elios-interviews-staging`: Staging environment
- `elios-interviews-prod`: Production

Set via environment variable:

```bash
# .env.dev
LANGCHAIN_PROJECT="elios-interviews-dev"

# .env.prod
LANGCHAIN_PROJECT="elios-interviews-prod"
```

### 2. Enable PII Filtering in Production

**Always** enable PII filtering in production:

```bash
LANGSMITH_FILTER_PII=true
```

Only disable in isolated local development environments.

### 3. Use Sampling in High-Volume Production

To reduce costs, sample traces in production:

```bash
LANGSMITH_SAMPLE_RATE=0.1  # 10% sampling
```

This sends 1 out of every 10 traces to LangSmith.

### 4. Set Max Trace Size

Prevent huge traces from slowing down uploads:

```bash
LANGSMITH_MAX_TRACE_SIZE_KB=1024  # 1MB max
```

### 5. Monitor Costs Regularly

Set up daily cost monitoring:

```python
# Add to scheduled task (e.g., GitHub Actions, Airflow)
async def monitor_daily_costs():
    result = await get_daily_cost_summary(
        langsmith_api_key=settings.langsmith_api_key,
        project_name=settings.langchain_project,
        days=1,
    )

    log_cost_metrics(result)

    if result["total_cost_usd"] > COST_THRESHOLD:
        send_alert_to_slack(result)
```

### 6. Tag Critical Metadata

Always include these metadata fields:

```python
metadata = create_metadata_for_tracing(
    interview_id=interview_id,  # Essential for grouping
    candidate_id=candidate_id,  # Essential for privacy audits
    skill=skill,  # For filtering by topic
    difficulty=difficulty,  # For performance analysis
    method=method_name,  # For identifying slow methods
)
```

### 7. Review Traces Weekly

Schedule weekly trace reviews:

1. **Monday**: Review failed traces from previous week
2. **Wednesday**: Analyze high-latency traces
3. **Friday**: Check cost trends and optimize expensive chains

### 8. Test PII Filtering Before Production

Run PII filtering tests before deploying:

```bash
pytest tests/unit/infrastructure/observability/test_langsmith_config.py -v -k "test_filter"
```

Verify all PII patterns are caught:

- Emails
- Phone numbers
- SSNs
- Names
- CV text truncation

---

## Troubleshooting

### Traces Not Appearing in LangSmith

**Check:**

1. `ENABLE_LANGSMITH=true` in `.env`
2. `LANGCHAIN_TRACING_V2=true` in `.env`
3. Valid `LANGSMITH_API_KEY` (starts with `lsv2_pt_`)
4. Correct `LANGCHAIN_PROJECT` name (must exist in LangSmith)
5. Network connectivity to `https://api.smith.langchain.com`

**Debugging:**

```python
import os
print("LANGCHAIN_TRACING_V2:", os.getenv("LANGCHAIN_TRACING_V2"))
print("LANGCHAIN_API_KEY:", os.getenv("LANGCHAIN_API_KEY")[:10] + "...")
print("LANGCHAIN_PROJECT:", os.getenv("LANGCHAIN_PROJECT"))
```

### PII Leaking in Traces

**Check:**

1. `LANGSMITH_FILTER_PII=true` in `.env`
2. Verify `PIIFilteringTracer` is in callbacks list
3. Run PII filtering tests: `pytest tests/unit/infrastructure/observability/test_langsmith_config.py -v`

**Update PII patterns** if new patterns detected:

```python
# In langsmith_config.py
class PIIFilteringTracer(LangChainTracer):
    # Add new pattern
    PASSPORT_PATTERN = r'\b[A-Z]{1,2}\d{6,9}\b'

    def _filter_pii(self, text: str, field_name: str = "") -> str:
        # Add redaction
        text = re.sub(self.PASSPORT_PATTERN, "[PASSPORT_REDACTED]", text)
        return text
```

### Cost Calculation Errors

**Check:**

1. `langsmith` package installed: `pip install langsmith`
2. Valid API key with read permissions
3. Correct project name
4. Runs exist in LangSmith for the given interview_id

**Test cost calculation:**

```python
from src.infrastructure.observability.cost_tracking import calculate_cost_from_tokens

cost = calculate_cost_from_tokens("gpt-4", input_tokens=1000, output_tokens=500)
print(f"Cost: ${cost}")  # Should print: Cost: $0.06
```

---

## API Reference

### `PIIFilteringTracer`

```python
class PIIFilteringTracer(LangChainTracer):
    """LangChain tracer that filters PII before sending to LangSmith."""

    def __init__(
        self,
        *args,
        max_answer_length: int = 200,
        max_cv_length: int = 100,
        **kwargs,
    ):
        """Initialize PII filtering tracer.

        Args:
            max_answer_length: Max characters to keep from answer text
            max_cv_length: Max characters to keep from CV text
        """
```

### `create_metadata_for_tracing()`

```python
def create_metadata_for_tracing(
    interview_id: UUID | str | None = None,
    candidate_id: UUID | str | None = None,
    question_id: UUID | str | None = None,
    question_type: str | None = None,
    difficulty: str | None = None,
    skill: str | None = None,
    **extra: Any,
) -> Dict[str, Any]:
    """Create metadata dictionary for LangSmith tracing.

    Returns:
        Metadata dictionary safe for LangSmith
    """
```

### `calculate_cost_from_tokens()`

```python
def calculate_cost_from_tokens(
    model_name: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    total_tokens: Optional[int] = None,
) -> float:
    """Calculate cost in USD from token usage.

    Returns:
        Cost in USD (rounded to 4 decimal places)
    """
```

### `get_interview_cost()`

```python
async def get_interview_cost(
    interview_id: UUID,
    langsmith_api_key: str,
    project_name: str = "elios-interviews-prod",
) -> Dict[str, Any]:
    """Get token usage and cost for a specific interview session.

    Returns:
        Dict with keys: total_tokens, input_tokens, output_tokens,
        total_cost_usd, model_breakdown, trace_count
    """
```

---

## Further Reading

- [LangSmith Documentation](https://docs.smith.langchain.com/)
- [LangChain Tracing Guide](https://python.langchain.com/docs/langsmith/tracing)
- [LangSmith API Reference](https://api.smith.langchain.com/redoc)
- [Token Pricing Updates](https://openai.com/pricing)

---

## Support

For questions or issues:

1. Check this guide first
2. Review unit tests in `tests/unit/infrastructure/observability/`
3. Search LangSmith docs: [https://docs.smith.langchain.com/](https://docs.smith.langchain.com/)
4. File an issue in the project repository
