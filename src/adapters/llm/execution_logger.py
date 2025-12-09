import logging
import time
from typing import Any

from ...domain.models.prompt_template import PromptTemplate

logger = logging.getLogger(__name__)


class ExecutionLogger:
    """Static helpers for logging prompt executions and extracting metadata."""

    @staticmethod
    async def log_execution(
        prompt_repo: Any,
        prompt_template: PromptTemplate,
        context: dict[str, Any],
        input_variables: dict,
        output_text: str | None,
        start_time: float,
        success: bool,
        model: Any,
        model_response_metadata: dict | None = None,
        error_message: str | None = None,
    ) -> None:
        if not prompt_repo:
            return

        try:
            latency_ms = int((time.time() - start_time) * 1000)
            model_name = ExecutionLogger._get_model_name(model, model_response_metadata)
            total_tokens, prompt_tokens, completion_tokens = ExecutionLogger._extract_token_usage(
                model_response_metadata, model_name
            )
            estimated_cost = ExecutionLogger._estimate_cost(model_name, prompt_tokens, completion_tokens)
            sanitized_input = ExecutionLogger._sanitize_variables(input_variables)

            execution_data = {
                "interview_id": context.get("interview_id"),
                "input_variables": sanitized_input,
                "output_text": output_text[:10000] if output_text else None,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "latency_ms": latency_ms,
                "model_name": model_name,
                "success": success,
                "error_message": error_message,
            }

            await prompt_repo.log_execution(
                prompt_template_id=prompt_template.id,
                execution_data=execution_data,
            )

            if success:
                logger.info(
                    "Prompt execution: %s (v%d) | Tokens: %s | Latency: %dms | Cost: $%.6f",
                    prompt_template.prompt_name,
                    prompt_template.version,
                    total_tokens or "N/A",
                    latency_ms,
                    estimated_cost or 0.0,
                )
            else:
                logger.warning(
                    "Prompt execution FAILED: %s (v%d) | Error: %s | Latency: %dms",
                    prompt_template.prompt_name,
                    prompt_template.version,
                    error_message,
                    latency_ms,
                )

        except Exception as log_error:
            logger.error(
                "Failed to log prompt execution for %s: %s",
                prompt_template.prompt_name,
                log_error,
                exc_info=True,
            )

    @staticmethod
    def extract_response_metadata(chain_response: Any) -> dict | None:
        if isinstance(chain_response, dict):
            return chain_response.get("_metadata")

        if hasattr(chain_response, "response_metadata"):
            return chain_response.response_metadata

        if hasattr(chain_response, "usage_metadata"):
            return {"usage": chain_response.usage_metadata}

        return None

    @staticmethod
    def _get_model_name(model: Any, model_response_metadata: dict[str, Any] | None = None) -> str:
        if model_response_metadata:
            model_name = model_response_metadata.get("model_name") or model_response_metadata.get("model")
            if model_name:
                return model_name

        if hasattr(model, "model_name"):
            return model.model_name
        if hasattr(model, "model"):
            return model.model
        if hasattr(model, "model_id"):
            return model.model_id

        if hasattr(model, "__dict__"):
            model_dict = model.__dict__
            if "model_name" in model_dict:
                return model_dict["model_name"]
            if "model" in model_dict:
                return model_dict["model"]

        return type(model).__name__

    @staticmethod
    def _extract_token_usage(
        model_response_metadata: dict | None,
        model_name: str,
    ) -> tuple[int | None, int | None, int | None]:
        if not model_response_metadata:
            logger.debug("No model_response_metadata provided for token extraction")
            return None, None, None

        token_usage = None
        usage = None

        if "token_usage" in model_response_metadata:
            token_usage = model_response_metadata["token_usage"]
        if "usage" in model_response_metadata:
            usage = model_response_metadata["usage"]
        elif isinstance(model_response_metadata.get("response_metadata"), dict):
            nested_meta = model_response_metadata["response_metadata"]
            token_usage = nested_meta.get("token_usage") or token_usage
            usage = nested_meta.get("usage") or usage

        if token_usage and isinstance(token_usage, dict):
            if "prompt_tokens" in token_usage or "completion_tokens" in token_usage:
                return (
                    token_usage.get("total_tokens"),
                    token_usage.get("prompt_tokens"),
                    token_usage.get("completion_tokens"),
                )

        if usage and isinstance(usage, dict):
            if "input_tokens" in usage:
                input_tokens = usage.get("input_tokens")
                output_tokens = usage.get("output_tokens")
                total = (
                    (input_tokens or 0) + (output_tokens or 0)
                    if input_tokens is not None and output_tokens is not None
                    else usage.get("total_tokens")
                )
                return total, input_tokens, output_tokens

            if "prompt_tokens" in usage or "completion_tokens" in usage:
                return (
                    usage.get("total_tokens"),
                    usage.get("prompt_tokens"),
                    usage.get("completion_tokens"),
                )

            if "total" in usage or "prompt" in usage or "completion" in usage:
                return (
                    usage.get("total"),
                    usage.get("prompt"),
                    usage.get("completion"),
                )

        logger.debug(f"No usage data found in metadata. Keys: {list(model_response_metadata.keys())}")
        return None, None, None

    @staticmethod
    def _estimate_cost(
        model_name: str,
        prompt_tokens: int | None,
        completion_tokens: int | None,
    ) -> float | None:
        if not prompt_tokens or not completion_tokens:
            return None

        pricing = {
            "gpt-4": (3.0, 6.0),
            "gpt-3.5-turbo": (0.05, 0.15),
            "claude-3-opus": (1.5, 7.5),
            "claude-3-sonnet": (0.3, 1.5),
            "claude-3-haiku": (0.025, 0.125),
        }

        model_lower = model_name.lower()
        for key, (prompt_cost, completion_cost) in pricing.items():
            if key in model_lower:
                cost_usd = (prompt_tokens / 1000 * prompt_cost / 100) + (
                    completion_tokens / 1000 * completion_cost / 100
                )
                return round(cost_usd, 6)

        logger.warning("Unknown model '%s' for cost estimation", model_name)
        return None

    @staticmethod
    def _sanitize_variables(input_variables: dict) -> dict:
        import re

        sanitized = {}
        for key, value in input_variables.items():
            if value is None:
                sanitized[key] = None
                continue

            str_value = str(value)
            str_value = re.sub(
                r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
                "[EMAIL_REDACTED]",
                str_value,
            )
            str_value = re.sub(
                r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b",
                "[PHONE_REDACTED]",
                str_value,
            )
            if len(str_value) > 500:
                str_value = str_value[:500] + f"... [TRUNCATED {len(str_value)-500} chars]"

            sanitized[key] = str_value

        return sanitized

