"""Unit tests for ABTestService."""

import pytest

from src.domain.services.ab_test_service import ABTestService


def test_select_variant_single():
    """Test selecting from single variant."""
    variants = [{"id": "v1", "traffic_percentage": 100}]

    selected = ABTestService.select_variant(variants)

    assert selected["id"] == "v1"


def test_select_variant_weighted_distribution():
    """Test weighted random selection distribution."""
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


def test_select_variant_50_50_split():
    """Test 50/50 traffic split."""
    variants = [
        {"id": "control", "traffic_percentage": 50},
        {"id": "variant_a", "traffic_percentage": 50},
    ]

    # Sample 1000 times
    selections = {"control": 0, "variant_a": 0}
    for _ in range(1000):
        selected = ABTestService.select_variant(variants)
        selections[selected["id"]] += 1

    # Verify ~50/50 distribution (±10% tolerance)
    assert 400 <= selections["control"] <= 600
    assert 400 <= selections["variant_a"] <= 600


def test_select_variant_three_way_split():
    """Test three-way traffic split."""
    variants = [
        {"id": "v1", "traffic_percentage": 20},
        {"id": "v2", "traffic_percentage": 30},
        {"id": "v3", "traffic_percentage": 50},
    ]

    # Sample 1000 times
    selections = {"v1": 0, "v2": 0, "v3": 0}
    for _ in range(1000):
        selected = ABTestService.select_variant(variants)
        selections[selected["id"]] += 1

    # Verify distribution (±10% tolerance)
    assert 100 <= selections["v1"] <= 300  # 20% target
    assert 200 <= selections["v2"] <= 400  # 30% target
    assert 400 <= selections["v3"] <= 600  # 50% target


def test_select_variant_normalizes_traffic():
    """Test traffic normalization when total != 100."""
    variants = [
        {"id": "v1", "traffic_percentage": 30},
        {"id": "v2", "traffic_percentage": 20},
    ]

    # Should normalize to 60/40 split
    selections = {"v1": 0, "v2": 0}
    for _ in range(1000):
        selected = ABTestService.select_variant(variants)
        selections[selected["id"]] += 1

    # Verify ~60/40 distribution (±10% tolerance)
    assert 500 <= selections["v1"] <= 700  # 60%
    assert 300 <= selections["v2"] <= 500  # 40%


def test_select_variant_empty_list():
    """Test error on empty variants list."""
    with pytest.raises(ValueError, match="Variants list cannot be empty"):
        ABTestService.select_variant([])


def test_select_variant_missing_traffic_percentage():
    """Test error when variant missing traffic_percentage."""
    variants = [{"id": "v1"}]

    with pytest.raises(ValueError, match="must have 'traffic_percentage' key"):
        ABTestService.select_variant(variants)


def test_select_variant_preserves_original_data():
    """Test that variant data is preserved."""
    variants = [
        {
            "id": "v1",
            "traffic_percentage": 50,
            "name": "Control",
            "metadata": {"created": "2024-01-01"},
        },
        {"id": "v2", "traffic_percentage": 50, "name": "Variant A"},
    ]

    selected = ABTestService.select_variant(variants)

    assert "id" in selected
    assert "traffic_percentage" in selected
    # Check original fields preserved
    if selected["id"] == "v1":
        assert selected["name"] == "Control"
        assert "metadata" in selected


def test_calculate_confidence_interval_95_percent():
    """Test 95% confidence interval calculation."""
    lower, upper = ABTestService.calculate_confidence_interval(
        conversions=95, total=100, confidence_level=0.95
    )

    # For 95/100 success rate, 95% CI should be ~(0.89, 0.98)
    assert 0.85 < lower < 0.90
    assert 0.97 < upper < 1.0


def test_calculate_confidence_interval_99_percent():
    """Test 99% confidence interval calculation."""
    lower, upper = ABTestService.calculate_confidence_interval(
        conversions=95, total=100, confidence_level=0.99
    )

    # 99% CI should be wider than 95% CI
    lower_95, upper_95 = ABTestService.calculate_confidence_interval(
        conversions=95, total=100, confidence_level=0.95
    )

    assert lower < lower_95  # Lower bound should be lower
    assert upper > upper_95  # Upper bound should be higher


def test_calculate_confidence_interval_perfect_success():
    """Test confidence interval for 100% success rate."""
    lower, upper = ABTestService.calculate_confidence_interval(
        conversions=100, total=100, confidence_level=0.95
    )

    # Upper bound should be 1.0 (use approx for floating-point precision)
    assert upper == pytest.approx(1.0)
    # Lower bound should be high but not 1.0
    assert 0.95 < lower < 1.0


def test_calculate_confidence_interval_zero_success():
    """Test confidence interval for 0% success rate."""
    lower, upper = ABTestService.calculate_confidence_interval(
        conversions=0, total=100, confidence_level=0.95
    )

    # Lower bound should be 0.0
    assert lower == 0.0
    # Upper bound should be low but not 0.0
    assert 0.0 < upper < 0.05


def test_calculate_confidence_interval_zero_total():
    """Test confidence interval with zero total."""
    lower, upper = ABTestService.calculate_confidence_interval(
        conversions=0, total=0, confidence_level=0.95
    )

    assert lower == 0.0
    assert upper == 0.0


def test_calculate_confidence_interval_small_sample():
    """Test confidence interval with small sample size."""
    lower, upper = ABTestService.calculate_confidence_interval(
        conversions=5, total=10, confidence_level=0.95
    )

    # 50% success with n=10, interval should be wide
    assert lower < 0.5
    assert upper > 0.5
    # Interval should be at least 0.3 wide
    assert (upper - lower) > 0.3


def test_calculate_confidence_interval_large_sample():
    """Test confidence interval with large sample size."""
    lower, upper = ABTestService.calculate_confidence_interval(
        conversions=500, total=1000, confidence_level=0.95
    )

    # 50% success with n=1000, interval should be narrow
    assert 0.45 < lower < 0.50
    assert 0.50 < upper < 0.55
    # Interval should be less than 0.1 wide
    assert (upper - lower) < 0.1


def test_calculate_confidence_interval_invalid_conversions_negative():
    """Test error on negative conversions."""
    with pytest.raises(ValueError, match="Conversions must be non-negative"):
        ABTestService.calculate_confidence_interval(
            conversions=-1, total=100, confidence_level=0.95
        )


def test_calculate_confidence_interval_invalid_total_negative():
    """Test error on negative total."""
    with pytest.raises(ValueError, match="Total must be non-negative"):
        ABTestService.calculate_confidence_interval(
            conversions=50, total=-100, confidence_level=0.95
        )


def test_calculate_confidence_interval_invalid_conversions_exceed_total():
    """Test error when conversions exceed total."""
    with pytest.raises(ValueError, match="Conversions cannot exceed total"):
        ABTestService.calculate_confidence_interval(
            conversions=150, total=100, confidence_level=0.95
        )


def test_calculate_confidence_interval_invalid_confidence_level_too_low():
    """Test error on invalid confidence level (too low)."""
    with pytest.raises(ValueError, match="Confidence level must be between 0 and 1"):
        ABTestService.calculate_confidence_interval(
            conversions=50, total=100, confidence_level=0.0
        )


def test_calculate_confidence_interval_invalid_confidence_level_too_high():
    """Test error on invalid confidence level (too high)."""
    with pytest.raises(ValueError, match="Confidence level must be between 0 and 1"):
        ABTestService.calculate_confidence_interval(
            conversions=50, total=100, confidence_level=1.0
        )


def test_calculate_confidence_interval_bounds():
    """Test confidence interval stays within [0, 1] bounds."""
    # Test various scenarios
    test_cases = [
        (0, 10),
        (10, 10),
        (5, 10),
        (0, 100),
        (100, 100),
        (50, 100),
        (1, 1000),
        (999, 1000),
    ]

    for conversions, total in test_cases:
        lower, upper = ABTestService.calculate_confidence_interval(
            conversions=conversions, total=total, confidence_level=0.95
        )

        assert 0.0 <= lower <= 1.0, f"Lower bound out of range for {conversions}/{total}"
        assert 0.0 <= upper <= 1.0, f"Upper bound out of range for {conversions}/{total}"
        assert lower <= upper, f"Lower > upper for {conversions}/{total}"
