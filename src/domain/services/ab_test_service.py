"""A/B testing traffic selector service."""

import math
import random


class ABTestService:
    """Service for weighted random selection in A/B tests."""

    @staticmethod
    def select_variant(variants: list[dict]) -> dict:
        """Select variant using weighted random selection.

        Args:
            variants: List of variant dicts with 'traffic_percentage' key

        Returns:
            Selected variant

        Raises:
            ValueError: If variants list is empty or missing traffic_percentage
        """
        if not variants:
            raise ValueError("Variants list cannot be empty")

        # Validate all variants have traffic_percentage
        for variant in variants:
            if "traffic_percentage" not in variant:
                raise ValueError("All variants must have 'traffic_percentage' key")

        # Validate total traffic
        total_traffic = sum(v["traffic_percentage"] for v in variants)
        if total_traffic != 100:
            # Normalize if not exactly 100
            for variant in variants:
                variant["traffic_percentage"] = (
                    variant["traffic_percentage"] / total_traffic * 100
                )

        # Weighted random choice
        weights = [v["traffic_percentage"] for v in variants]
        selected = random.choices(variants, weights=weights, k=1)[0]
        return selected

    @staticmethod
    def calculate_confidence_interval(
        conversions: int,
        total: int,
        confidence_level: float = 0.95,
    ) -> tuple[float, float]:
        """Calculate binomial confidence interval for A/B test.

        Args:
            conversions: Number of successful outcomes
            total: Total sample size
            confidence_level: Confidence level (0.95 for 95%, 0.99 for 99%)

        Returns:
            Tuple of (lower_bound, upper_bound)

        Raises:
            ValueError: If inputs are invalid

        Uses Wilson score interval for better small-sample performance.
        """
        if total < 0:
            raise ValueError("Total must be non-negative")
        if conversions < 0:
            raise ValueError("Conversions must be non-negative")
        if conversions > total:
            raise ValueError("Conversions cannot exceed total")
        if not 0 < confidence_level < 1:
            raise ValueError("Confidence level must be between 0 and 1")

        if total == 0:
            return (0.0, 0.0)

        # Z-score for confidence level
        z = 1.96 if confidence_level == 0.95 else 2.576  # 95% or 99%
        p_hat = conversions / total

        # Wilson score interval formula
        denominator = 1 + (z**2 / total)
        center = (p_hat + (z**2 / (2 * total))) / denominator
        margin = (z / denominator) * math.sqrt(
            (p_hat * (1 - p_hat) / total) + (z**2 / (4 * total**2))
        )

        lower = max(0.0, center - margin)
        upper = min(1.0, center + margin)

        return (lower, upper)
