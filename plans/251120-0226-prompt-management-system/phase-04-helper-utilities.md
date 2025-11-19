# Phase 4: Helper Utilities

**Parent**: [Implementation Plan](./plan.md)
**Dependencies**: [Phase 2](./phase-02-domain-models.md)
**Created**: 2025-11-20
**Duration**: 1-2 days
**Priority**: Medium
**Status**: ✅ Complete

---

## Overview

Create domain services for JSON diff calculation and A/B testing traffic selection. Pure Python utilities with no external dependencies except DeepDiff.

**Goals**:
- ✅ JSON diff calculator with DeepDiff
- ✅ A/B testing weighted random selector
- ✅ Statistical confidence interval calculator

---

## Utility 1: JSON Diff Service

**File**: `src/domain/services/prompt_diff_service.py`

**Purpose**: Calculate diffs between prompt template versions.

**Implementation**:

```python
"""JSON diff calculation service."""

from deepdiff import DeepDiff


class PromptDiffService:
    """Service for calculating JSON diffs between prompt versions."""

    @staticmethod
    def calculate_diff(
        old_template_json: dict,
        new_template_json: dict,
    ) -> dict:
        """Calculate diff between two prompt templates.

        Args:
            old_template_json: Previous version content
            new_template_json: New version content

        Returns:
            Diff dictionary from DeepDiff
        """
        diff = DeepDiff(
            old_template_json,
            new_template_json,
            ignore_order=True,
            verbose_level=2,
        )

        return diff.to_dict() if diff else {}

    @staticmethod
    def get_human_readable_summary(diff: dict) -> str:
        """Convert diff to human-readable summary.

        Returns:
            Human-readable summary string
        """
        changes = []

        if "values_changed" in diff:
            for path, change in diff["values_changed"].items():
                field = path.split("'")[1] if "'" in path else path
                changes.append(f"Changed '{field}' field")

        if "iterable_item_added" in diff:
            changes.append(f"Added {len(diff['iterable_item_added'])} items")

        if "iterable_item_removed" in diff:
            changes.append(f"Removed {len(diff['iterable_item_removed'])} items")

        return ", ".join(changes) if changes else "No changes detected"
```

**Usage Example**:
```python
diff = PromptDiffService.calculate_diff(old_json, new_json)
summary = PromptDiffService.get_human_readable_summary(diff)
# Output: "Changed 'constraints' field, Added 1 items"
```

---

## Utility 2: A/B Test Service

**File**: `src/domain/services/ab_test_service.py`

**Purpose**: Weighted random selection and statistical analysis for A/B tests.

**Implementation**:

```python
"""A/B testing traffic selector service."""

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
        """
        # Validate total traffic
        total_traffic = sum(v["traffic_percentage"] for v in variants)
        if total_traffic != 100:
            # Normalize if not exactly 100
            for variant in variants:
                variant["traffic_percentage"] = (
                    variant["traffic_percentage"] / total_traffic * 100
                )

        # Weighted random choice
        choices = variants
        weights = [v["traffic_percentage"] for v in variants]

        selected = random.choices(choices, weights=weights, k=1)[0]
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
            confidence_level: Confidence level (default 95%)

        Returns:
            Tuple of (lower_bound, upper_bound)

        Uses Wilson score interval for better small-sample performance.
        """
        import math

        if total == 0:
            return (0.0, 0.0)

        z = 1.96 if confidence_level == 0.95 else 2.576  # 95% or 99%
        p_hat = conversions / total

        denominator = 1 + (z ** 2 / total)
        center = (p_hat + (z ** 2 / (2 * total))) / denominator
        margin = (z / denominator) * math.sqrt(
            (p_hat * (1 - p_hat) / total) + (z ** 2 / (4 * total ** 2))
        )

        lower = max(0.0, center - margin)
        upper = min(1.0, center + margin)

        return (lower, upper)
```

**Usage Example**:
```python
# Select variant
variants = [
    {"id": "v5", "traffic_percentage": 30},
    {"id": "v6", "traffic_percentage": 70},
]
selected = ABTestService.select_variant(variants)

# Calculate confidence interval for success rate
lower, upper = ABTestService.calculate_confidence_interval(
    conversions=950,  # Successful executions
    total=1000,       # Total executions
    confidence_level=0.95,
)
# Result: (0.936, 0.964) → 95% confident success rate is 93.6%-96.4%
```

---

## Implementation Steps

### Step 1: Create PromptDiffService (3-4 hours)
- [x] Create `src/domain/services/prompt_diff_service.py`
- [x] Implement `calculate_diff()` method
- [x] Implement `get_human_readable_summary()` method
- [x] Implement `has_significant_changes()` method
- [x] Write unit tests (20 tests)
- [x] Add `deepdiff` to dependencies

### Step 2: Create ABTestService (2-3 hours)
- [x] Create `src/domain/services/ab_test_service.py`
- [x] Implement `select_variant()` method
- [x] Implement `calculate_confidence_interval()` method
- [x] Write unit tests (21 tests)

---

## Testing

### Unit Tests

**File**: `tests/unit/domain/test_prompt_diff_service.py`

```python
def test_calculate_diff():
    """Test JSON diff calculation."""
    old = {
        "system": "Old system",
        "variables": ["skill"]
    }
    new = {
        "system": "New system",
        "variables": ["skill", "difficulty"]
    }

    diff = PromptDiffService.calculate_diff(old, new)

    assert "values_changed" in diff
    assert "iterable_item_added" in diff

def test_get_human_readable_summary():
    """Test human-readable summary."""
    diff = {
        "values_changed": {
            "root['system']": {
                "old_value": "Old",
                "new_value": "New"
            }
        },
        "iterable_item_added": {
            "root['variables'][1]": "difficulty"
        }
    }

    summary = PromptDiffService.get_human_readable_summary(diff)
    assert "Changed 'system' field" in summary
    assert "Added 1 items" in summary
```

**File**: `tests/unit/domain/test_ab_test_service.py`

```python
def test_select_variant_weighted():
    """Test weighted random selection."""
    variants = [
        {"id": "v1", "traffic_percentage": 25},
        {"id": "v2", "traffic_percentage": 75},
    ]

    # Sample 1000 times
    selections = {"v1": 0, "v2": 0}
    for _ in range(1000):
        selected = ABTestService.select_variant(variants)
        selections[selected["id"]] += 1

    # Verify ~25/75 distribution (±10% tolerance)
    assert 150 <= selections["v1"] <= 350
    assert 650 <= selections["v2"] <= 850

def test_calculate_confidence_interval():
    """Test confidence interval calculation."""
    lower, upper = ABTestService.calculate_confidence_interval(
        conversions=95,
        total=100,
        confidence_level=0.95,
    )

    # For 95/100 success rate, 95% CI should be ~(0.89, 0.98)
    assert 0.85 < lower < 0.90
    assert 0.97 < upper < 1.0
```

---

## Success Criteria

- ✅ `PromptDiffService.calculate_diff()` works with DeepDiff
- ✅ `PromptDiffService.get_human_readable_summary()` generates readable output
- ✅ `ABTestService.select_variant()` distributes traffic correctly (±10%)
- ✅ `ABTestService.calculate_confidence_interval()` calculates Wilson score
- ✅ Unit tests passing (>90% coverage)
- ✅ `deepdiff` dependency added to `pyproject.toml`

---

## Dependencies

**Update**: `pyproject.toml`

```toml
dependencies = [
    # ... existing deps
    "deepdiff>=6.7.0",  # JSON diff calculation
]
```

---

## Related Files

**New Files**:
- `src/domain/services/prompt_diff_service.py`
- `src/domain/services/ab_test_service.py`
- `tests/unit/domain/test_prompt_diff_service.py`
- `tests/unit/domain/test_ab_test_service.py`

**Modified Files**:
- `pyproject.toml` (add deepdiff dependency)

---

## Next Phase

→ [Phase 5: Background Jobs](./phase-05-background-jobs.md)

**Blockers**: None (independent of other phases)

---

## Notes

- DeepDiff uses `ignore_order=True` for lists (order doesn't matter)
- Wilson score interval better than normal approximation for small samples
- `select_variant()` normalizes traffic if total != 100%

---

**Phase Status**: Ready to implement
**Last Updated**: 2025-11-20
