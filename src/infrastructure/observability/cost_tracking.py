"""Cost tracking utilities for LLM token usage.

This module provides functions to calculate and track LLM costs based on token usage.
Integrates with LangSmith API to query token usage per interview session.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

logger = logging.getLogger(__name__)


# Token pricing (as of 2025, USD per 1K tokens)
TOKEN_PRICING = {
    "gpt-4": {"input": 0.03, "output": 0.06},
    "gpt-4-turbo": {"input": 0.01, "output": 0.03},
    "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
    "claude-3-opus": {"input": 0.015, "output": 0.075},
    "claude-3-sonnet": {"input": 0.003, "output": 0.015},
    "claude-3-haiku": {"input": 0.00025, "output": 0.00125},
    "llama-3-70b": {"input": 0.001, "output": 0.001},  # Open source (approx hosting cost)
}


def calculate_cost_from_tokens(
    model_name: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    total_tokens: Optional[int] = None,
) -> float:
    """Calculate cost in USD from token usage.

    Args:
        model_name: LLM model name (e.g., "gpt-4", "claude-3-sonnet")
        input_tokens: Number of input (prompt) tokens
        output_tokens: Number of output (completion) tokens
        total_tokens: Total tokens (used if input/output not available)

    Returns:
        Cost in USD (rounded to 4 decimal places)

    Example:
        >>> calculate_cost_from_tokens("gpt-4", input_tokens=1000, output_tokens=500)
        0.0600  # $0.06
    """
    # Normalize model name
    model_key = _normalize_model_name(model_name)

    # Get pricing
    pricing = TOKEN_PRICING.get(model_key)
    if not pricing:
        logger.warning(f"Unknown model '{model_name}', using gpt-4 pricing as default")
        pricing = TOKEN_PRICING["gpt-4"]

    # Calculate cost
    if total_tokens is not None and (input_tokens == 0 and output_tokens == 0):
        # Fallback: assume 70% input, 30% output (typical ratio)
        input_tokens = int(total_tokens * 0.7)
        output_tokens = int(total_tokens * 0.3)

    input_cost = (input_tokens / 1000) * pricing["input"]
    output_cost = (output_tokens / 1000) * pricing["output"]
    total_cost = input_cost + output_cost

    return round(total_cost, 4)


def _normalize_model_name(model_name: str) -> str:
    """Normalize model name to pricing key.

    Args:
        model_name: Raw model name from LLM provider

    Returns:
        Normalized key for TOKEN_PRICING dict

    Examples:
        "gpt-4-0613" → "gpt-4"
        "gpt-4-1106-preview" → "gpt-4-turbo"
        "claude-3-opus-20240229" → "claude-3-opus"
    """
    model_lower = model_name.lower()

    # GPT models
    if "gpt-4-turbo" in model_lower or "gpt-4-1106" in model_lower:
        return "gpt-4-turbo"
    elif "gpt-4" in model_lower:
        return "gpt-4"
    elif "gpt-3.5" in model_lower:
        return "gpt-3.5-turbo"

    # Claude models
    elif "claude-3-opus" in model_lower:
        return "claude-3-opus"
    elif "claude-3-sonnet" in model_lower:
        return "claude-3-sonnet"
    elif "claude-3-haiku" in model_lower:
        return "claude-3-haiku"

    # Llama models
    elif "llama" in model_lower and "70b" in model_lower:
        return "llama-3-70b"

    # Default to gpt-4 pricing
    return "gpt-4"


async def get_interview_cost(
    interview_id: UUID,
    langsmith_api_key: str,
    project_name: str = "elios-interviews-prod",
) -> Dict[str, Any]:
    """Get token usage and cost for a specific interview session.

    Queries LangSmith API for all traces tagged with interview_id.

    Args:
        interview_id: Interview UUID
        langsmith_api_key: LangSmith API key
        project_name: LangSmith project name

    Returns:
        Dict with keys:
            - total_tokens: int
            - input_tokens: int
            - output_tokens: int
            - total_cost_usd: float
            - model_breakdown: Dict[str, Dict] (cost per model)
            - trace_count: int

    Example:
        {
            "total_tokens": 12500,
            "input_tokens": 8000,
            "output_tokens": 4500,
            "total_cost_usd": 0.45,
            "model_breakdown": {
                "gpt-4": {"tokens": 12500, "cost": 0.45}
            },
            "trace_count": 15
        }
    """
    try:
        from langsmith import Client

        client = Client(api_key=langsmith_api_key)

        # Query runs with interview_id metadata
        runs = list(client.list_runs(
            project_name=project_name,
            filter={"metadata.interview_id": str(interview_id)},
        ))

        if not runs:
            logger.warning(f"No traces found for interview {interview_id}")
            return {
                "total_tokens": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "total_cost_usd": 0.0,
                "model_breakdown": {},
                "trace_count": 0,
            }

        # Aggregate token usage
        total_tokens = 0
        total_input = 0
        total_output = 0
        total_cost = 0.0
        model_breakdown: Dict[str, Dict[str, Any]] = {}

        for run in runs:
            # Get token counts
            run_tokens = getattr(run, "total_tokens", 0) or 0
            run_input = getattr(run, "prompt_tokens", 0) or 0
            run_output = getattr(run, "completion_tokens", 0) or 0

            total_tokens += run_tokens
            total_input += run_input
            total_output += run_output

            # Get model name
            model_name = "gpt-4"  # Default
            if hasattr(run, "extra") and isinstance(run.extra, dict):
                model_name = run.extra.get("invocation_params", {}).get("model_name", "gpt-4")

            # Calculate cost
            run_cost = calculate_cost_from_tokens(
                model_name,
                input_tokens=run_input,
                output_tokens=run_output,
                total_tokens=run_tokens,
            )
            total_cost += run_cost

            # Track per-model breakdown
            model_key = _normalize_model_name(model_name)
            if model_key not in model_breakdown:
                model_breakdown[model_key] = {"tokens": 0, "cost": 0.0}

            model_breakdown[model_key]["tokens"] += run_tokens
            model_breakdown[model_key]["cost"] = round(
                model_breakdown[model_key]["cost"] + run_cost, 4
            )

        return {
            "total_tokens": total_tokens,
            "input_tokens": total_input,
            "output_tokens": total_output,
            "total_cost_usd": round(total_cost, 4),
            "model_breakdown": model_breakdown,
            "trace_count": len(runs),
        }

    except ImportError:
        logger.error("langsmith package not installed. Run: pip install langsmith")
        return {
            "total_tokens": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_cost_usd": 0.0,
            "model_breakdown": {},
            "trace_count": 0,
            "error": "langsmith package not installed",
        }
    except Exception as e:
        logger.error(f"Failed to get interview cost: {e}")
        return {
            "total_tokens": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_cost_usd": 0.0,
            "model_breakdown": {},
            "trace_count": 0,
            "error": str(e),
        }


async def get_daily_cost_summary(
    langsmith_api_key: str,
    project_name: str = "elios-interviews-prod",
    days: int = 1,
) -> Dict[str, Any]:
    """Get cost summary for the last N days.

    Args:
        langsmith_api_key: LangSmith API key
        project_name: LangSmith project name
        days: Number of days to query (default: 1 = yesterday)

    Returns:
        Dict with keys:
            - start_date: str (ISO format)
            - end_date: str (ISO format)
            - total_cost_usd: float
            - total_tokens: int
            - total_traces: int
            - interviews_count: int
            - avg_cost_per_interview: float
            - model_breakdown: Dict[str, Dict]

    Example:
        {
            "start_date": "2025-11-16T00:00:00",
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
    """
    try:
        from langsmith import Client

        client = Client(api_key=langsmith_api_key)

        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        # Query runs in date range
        runs = list(client.list_runs(
            project_name=project_name,
            start_time=start_date,
            end_time=end_date,
        ))

        if not runs:
            return {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "total_cost_usd": 0.0,
                "total_tokens": 0,
                "total_traces": 0,
                "interviews_count": 0,
                "avg_cost_per_interview": 0.0,
                "model_breakdown": {},
            }

        # Aggregate data
        total_tokens = 0
        total_cost = 0.0
        model_breakdown: Dict[str, Dict[str, Any]] = {}
        interview_ids = set()

        for run in runs:
            # Track unique interviews
            if hasattr(run, "metadata") and isinstance(run.metadata, dict):
                interview_id = run.metadata.get("interview_id")
                if interview_id:
                    interview_ids.add(interview_id)

            # Get token counts
            run_tokens = getattr(run, "total_tokens", 0) or 0
            run_input = getattr(run, "prompt_tokens", 0) or 0
            run_output = getattr(run, "completion_tokens", 0) or 0

            total_tokens += run_tokens

            # Get model name
            model_name = "gpt-4"
            if hasattr(run, "extra") and isinstance(run.extra, dict):
                model_name = run.extra.get("invocation_params", {}).get("model_name", "gpt-4")

            # Calculate cost
            run_cost = calculate_cost_from_tokens(
                model_name,
                input_tokens=run_input,
                output_tokens=run_output,
                total_tokens=run_tokens,
            )
            total_cost += run_cost

            # Track per-model breakdown
            model_key = _normalize_model_name(model_name)
            if model_key not in model_breakdown:
                model_breakdown[model_key] = {"tokens": 0, "cost": 0.0}

            model_breakdown[model_key]["tokens"] += run_tokens
            model_breakdown[model_key]["cost"] = round(
                model_breakdown[model_key]["cost"] + run_cost, 4
            )

        interviews_count = len(interview_ids)
        avg_cost = total_cost / interviews_count if interviews_count > 0 else 0.0

        return {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "total_cost_usd": round(total_cost, 2),
            "total_tokens": total_tokens,
            "total_traces": len(runs),
            "interviews_count": interviews_count,
            "avg_cost_per_interview": round(avg_cost, 2),
            "model_breakdown": model_breakdown,
        }

    except ImportError:
        logger.error("langsmith package not installed")
        return {"error": "langsmith package not installed"}
    except Exception as e:
        logger.error(f"Failed to get daily cost summary: {e}")
        return {"error": str(e)}
