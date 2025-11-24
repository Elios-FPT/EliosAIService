"""Performance and cost metrics collection for test bot."""

import logging
from datetime import datetime
from typing import Any
from uuid import UUID

logger = logging.getLogger(__name__)


class MetricsCollector:
    """Track performance and cost metrics across test runs."""

    def __init__(self):
        """Initialize metrics collector."""
        self.metrics = {
            "latency": {},  # Message type → [latency_ms]
            "tokens": {},  # Interview ID → token count
            "cost": {},  # Interview ID → cost (USD)
            "errors": [],  # Error list
            "states": [],  # State transitions
        }

    def track_message_latency(self, msg_type: str, latency_ms: float) -> None:
        """Track WebSocket message latency.

        Args:
            msg_type: Message type (connect, send_answer, wait_question, etc.)
            latency_ms: Latency in milliseconds
        """
        if msg_type not in self.metrics["latency"]:
            self.metrics["latency"][msg_type] = []

        self.metrics["latency"][msg_type].append(latency_ms)
        logger.debug(f"Latency tracked: {msg_type} = {latency_ms:.1f}ms")

    def track_llm_call(
        self, interview_id: UUID, tokens: int, cost: float
    ) -> None:
        """Track LLM usage.

        Args:
            interview_id: Interview UUID
            tokens: Token count
            cost: Cost in USD
        """
        interview_str = str(interview_id)

        if interview_str not in self.metrics["tokens"]:
            self.metrics["tokens"][interview_str] = 0
            self.metrics["cost"][interview_str] = 0.0

        self.metrics["tokens"][interview_str] += tokens
        self.metrics["cost"][interview_str] += cost

        logger.debug(
            f"LLM tracked: interview={interview_id}, "
            f"tokens={tokens}, cost=${cost:.4f}"
        )

    def track_state_transition(
        self, from_state: str, to_state: str, timestamp: datetime | None = None
    ) -> None:
        """Track interview state transitions.

        Args:
            from_state: Previous state
            to_state: New state
            timestamp: Transition timestamp (default: now)
        """
        timestamp = timestamp or datetime.utcnow()

        self.metrics["states"].append(
            {
                "timestamp": timestamp.isoformat(),
                "from_state": from_state,
                "to_state": to_state,
            }
        )

        logger.debug(f"State transition: {from_state} → {to_state}")

    def track_error(
        self, error_code: str, message: str, recoverable: bool
    ) -> None:
        """Track errors.

        Args:
            error_code: Error code (e.g., TIMEOUT, CONNECTION_FAILED)
            message: Error message
            recoverable: Whether error was recoverable
        """
        self.metrics["errors"].append(
            {
                "timestamp": datetime.utcnow().isoformat(),
                "code": error_code,
                "message": message,
                "recoverable": recoverable,
            }
        )

        logger.warning(
            f"Error tracked: {error_code} - {message} "
            f"(recoverable={recoverable})"
        )

    def merge(self, bot_metrics: dict[str, Any]) -> None:
        """Merge bot metrics into collector.

        Args:
            bot_metrics: Metrics from InterviewTestBot.get_metrics()
        """
        # Merge latency
        if "latency" in bot_metrics:
            for msg_type, stats in bot_metrics["latency"].items():
                if msg_type not in self.metrics["latency"]:
                    self.metrics["latency"][msg_type] = []

                # Extract individual latency values (not aggregated stats)
                # Note: bot_metrics.latency contains aggregated stats,
                # so we'll store the avg for now
                if isinstance(stats, dict) and "avg" in stats:
                    # Store avg as single value (simplified)
                    self.metrics["latency"][msg_type].append(stats["avg"])

        # Merge states
        if "states" in bot_metrics:
            self.metrics["states"].extend(bot_metrics["states"])

        # Merge errors
        if "errors" in bot_metrics:
            self.metrics["errors"].extend(bot_metrics["errors"])

    def get_summary(self) -> dict[str, Any]:
        """Aggregate metrics into summary.

        Returns:
            Summary dict with aggregated metrics
        """
        def avg(values: list[float]) -> float:
            return sum(values) / len(values) if values else 0.0

        return {
            "total_tests": len(self.metrics["tokens"]),
            "total_cost_usd": sum(self.metrics["cost"].values()),
            "total_tokens": sum(self.metrics["tokens"].values()),
            "avg_latency_ms": (
                avg(
                    [
                        val
                        for values in self.metrics["latency"].values()
                        for val in (
                            values if isinstance(values, list) else [values]
                        )
                    ]
                )
            ),
            "total_errors": len(self.metrics["errors"]),
            "recoverable_errors": sum(
                1 for e in self.metrics["errors"] if e.get("recoverable")
            ),
            "state_transition_count": len(self.metrics["states"]),
            "latency_breakdown": {
                msg_type: {
                    "count": len(values),
                    "avg": avg(values),
                    "min": min(values) if values else 0,
                    "max": max(values) if values else 0,
                }
                for msg_type, values in self.metrics["latency"].items()
            },
        }

    def reset(self) -> None:
        """Reset all metrics."""
        self.metrics = {
            "latency": {},
            "tokens": {},
            "cost": {},
            "errors": [],
            "states": [],
        }
        logger.info("Metrics reset")
