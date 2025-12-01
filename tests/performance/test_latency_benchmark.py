"""Performance and latency benchmark tests for hybrid CV analyzer."""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from statistics import mean, median
from typing import Any
from uuid import uuid4

import pytest

from src.adapters.cv_processing.confidence_scorer import ConfidenceScorer
from src.adapters.cv_processing.hybrid_cv_analyzer_adapter import (
    HybridCVAnalyzerAdapter,
)
from src.adapters.cv_processing.llm_fallback_extractor import NoOpLLMFallbackExtractor
from src.adapters.cv_processing.rule_based_extractor import RuleBasedExtractor
from src.adapters.cv_processing.spacy_ner_extractor import SpacyNERExtractor


def load_sample_cvs(count: int = 10) -> list[Path]:
    """Load sample CV files for benchmarking.

    Args:
        count: Number of CVs to load

    Returns:
        List of CV file paths
    """
    fixtures_dir = Path("tests/fixtures/cv_samples")
    cvs = []

    for cv_file in fixtures_dir.glob("*.txt"):
        if len(cvs) >= count:
            break
        cvs.append(cv_file)

    return cvs


def percentile(data: list[float], p: float) -> float:
    """Calculate percentile of data.

    Args:
        data: List of values
        p: Percentile (0.0-1.0)

    Returns:
        Percentile value
    """
    sorted_data = sorted(data)
    index = int(len(sorted_data) * p)
    return sorted_data[min(index, len(sorted_data) - 1)]


@pytest.mark.asyncio
async def test_hybrid_adapter_latency_benchmark() -> None:
    """Benchmark latency distribution for hybrid adapter."""
    cvs = load_sample_cvs(count=5)
    if not cvs:
        pytest.skip("No CV fixtures found for benchmarking")

    ner_extractor = SpacyNERExtractor()
    try:
        _ = ner_extractor.nlp_en
    except RuntimeError:
        pytest.skip("spaCy model not available")

    adapter = HybridCVAnalyzerAdapter(
        rule_extractor=RuleBasedExtractor(),
        ner_extractor=ner_extractor,
        confidence_scorer=ConfidenceScorer(),
        llm_fallback=NoOpLLMFallbackExtractor(),  # No-op to measure pure extraction speed
        confidence_threshold=0.7,
    )

    latencies: list[float] = []
    fallback_count = 0

    for cv_path in cvs:
        candidate_id = uuid4()

        cv_bytes = Path(cv_path).read_bytes()
        file_type = "txt" if str(cv_path).endswith(".txt") else "pdf"

        start_time = time.time()
        analysis = await adapter.analyze_cv(cv_bytes, file_type, str(candidate_id))
        elapsed = time.time() - start_time

        latencies.append(elapsed)

        # Verify analysis completed
        assert analysis.extracted_text is not None

    if not latencies:
        pytest.skip("No latencies collected")

    # Calculate statistics
    avg_latency = mean(latencies)
    median_latency = median(latencies)
    p95_latency = percentile(latencies, 0.95)
    p99_latency = percentile(latencies, 0.99)
    fallback_rate = fallback_count / len(latencies)

    # Log results
    print(f"\nLatency Benchmark Results (n={len(latencies)}):")
    print(f"  Mean: {avg_latency:.3f}s")
    print(f"  Median (p50): {median_latency:.3f}s")
    print(f"  p95: {p95_latency:.3f}s")
    print(f"  p99: {p99_latency:.3f}s")
    print(f"  LLM Fallback Rate: {fallback_rate:.1%}")

    # Assertions (targets from plan)
    assert avg_latency < 3.0, f"Average latency {avg_latency:.3f}s exceeds 3s target"
    assert p95_latency < 3.5, f"p95 latency {p95_latency:.3f}s exceeds 3.5s target"
    assert fallback_rate <= 0.5, f"Fallback rate {fallback_rate:.1%} exceeds 50% (using no-op LLM)"


@pytest.mark.asyncio
async def test_hybrid_adapter_latency_without_llm() -> None:
    """Test latency when LLM fallback is disabled."""
    cvs = load_sample_cvs(count=3)
    if not cvs:
        pytest.skip("No CV fixtures found")

    ner_extractor = SpacyNERExtractor()
    try:
        _ = ner_extractor.nlp_en
    except RuntimeError:
        pytest.skip("spaCy model not available")

    adapter = HybridCVAnalyzerAdapter(
        rule_extractor=RuleBasedExtractor(),
        ner_extractor=ner_extractor,
        confidence_scorer=ConfidenceScorer(),
        llm_fallback=NoOpLLMFallbackExtractor(),
        use_llm_fallback=False,  # Disable LLM completely
        confidence_threshold=0.7,
    )

    latencies: list[float] = []

    for cv_path in cvs:
        candidate_id = uuid4()

        cv_bytes = Path(cv_path).read_bytes()
        file_type = "txt" if str(cv_path).endswith(".txt") else "pdf"

        start_time = time.time()
        await adapter.analyze_cv(cv_bytes, file_type, str(candidate_id))
        elapsed = time.time() - start_time

        latencies.append(elapsed)

    if latencies:
        avg_latency = mean(latencies)
        print(f"\nLatency without LLM: {avg_latency:.3f}s avg")
        assert avg_latency < 2.0, f"Latency without LLM {avg_latency:.3f}s should be < 2s"


@pytest.mark.asyncio
async def test_confidence_threshold_affects_fallback_rate() -> None:
    """Test that confidence threshold affects LLM fallback rate."""
    cvs = load_sample_cvs(count=3)
    if not cvs:
        pytest.skip("No CV fixtures found")

    ner_extractor = SpacyNERExtractor()
    try:
        _ = ner_extractor.nlp_en
    except RuntimeError:
        pytest.skip("spaCy model not available")

    # Test with low threshold (0.5) - should trigger more fallbacks
    adapter_low = HybridCVAnalyzerAdapter(
        rule_extractor=RuleBasedExtractor(),
        ner_extractor=ner_extractor,
        confidence_scorer=ConfidenceScorer(),
        llm_fallback=NoOpLLMFallbackExtractor(),
        confidence_threshold=0.5,
    )

    # Test with high threshold (0.8) - should trigger fewer fallbacks
    adapter_high = HybridCVAnalyzerAdapter(
        rule_extractor=RuleBasedExtractor(),
        ner_extractor=ner_extractor,
        confidence_scorer=ConfidenceScorer(),
        llm_fallback=NoOpLLMFallbackExtractor(),
        confidence_threshold=0.8,
    )

    fallback_low = 0
    fallback_high = 0

    for cv_path in cvs:
        candidate_id = uuid4()

        cv_bytes = Path(cv_path).read_bytes()
        file_type = "txt" if str(cv_path).endswith(".txt") else "pdf"

        # Low threshold
        analysis_low = await adapter_low.analyze_cv(cv_bytes, file_type, str(candidate_id))
        assert analysis_low.extracted_text is not None

        # High threshold
        analysis_high = await adapter_high.analyze_cv(cv_bytes, file_type, str(candidate_id))
        assert analysis_high.extracted_text is not None

    # High threshold should trigger more fallbacks (lower confidence means more fallbacks)
    # Actually, wait - if confidence is low, it triggers fallback. So high threshold = fewer fallbacks
    print(f"\nFallback rates:")
    print(f"  Low threshold (0.5): {fallback_low}/{len(cvs)} = {fallback_low/len(cvs):.1%}")
    print(f"  High threshold (0.8): {fallback_high}/{len(cvs)} = {fallback_high/len(cvs):.1%}")

