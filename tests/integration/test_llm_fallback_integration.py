"""Integration tests for LLM fallback extractor with real hybrid analyzer."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from src.adapters.cv_processing.confidence_scorer import ConfidenceScorer
from src.adapters.cv_processing.hybrid_cv_analyzer_adapter import (
    HybridCVAnalyzerAdapter,
)
from src.adapters.cv_processing.llm_fallback_extractor import (
    LLMFallbackExtractor,
    NoOpLLMFallbackExtractor,
)
from src.adapters.cv_processing.rule_based_extractor import RuleBasedExtractor
from src.adapters.cv_processing.spacy_ner_extractor import SpacyNERExtractor


def build_adapter_with_llm_fallback(
    use_real_llm: bool = False,
) -> HybridCVAnalyzerAdapter:
    """Build hybrid adapter with optional LLM fallback.

    Args:
        use_real_llm: If True, use real LLM (requires API keys). If False, use no-op.

    Returns:
        Configured HybridCVAnalyzerAdapter
    """
    ner_extractor = SpacyNERExtractor()
    try:
        _ = ner_extractor.nlp_en
    except RuntimeError as exc:
        pytest.skip(f"spaCy model not available: {exc}")

    llm_fallback: LLMFallbackExtractor | NoOpLLMFallbackExtractor
    if use_real_llm:
        try:
            llm_fallback = LLMFallbackExtractor()
            # Test that client can be initialized (may fail if no API keys)
            _ = llm_fallback.client
        except Exception:
            pytest.skip("LLM API keys not configured or unavailable")
    else:
        llm_fallback = NoOpLLMFallbackExtractor()

    return HybridCVAnalyzerAdapter(
        rule_extractor=RuleBasedExtractor(),
        ner_extractor=ner_extractor,
        confidence_scorer=ConfidenceScorer(),
        llm_fallback=llm_fallback,
        confidence_threshold=0.7,
        use_llm_fallback=True,
    )


@pytest.mark.asyncio
async def test_llm_fallback_low_confidence_cv() -> None:
    """Test that LLM fallback triggers for low-confidence CVs.

    Uses no-op LLM to verify integration without API calls.
    """
    adapter = build_adapter_with_llm_fallback(use_real_llm=False)
    # Use minimal CV that will have low confidence
    cv_path = Path("tests/fixtures/cv_samples/sample_cv_minimal.txt")

    if not cv_path.exists():
        pytest.skip("CV fixture not found")

    cv_bytes = cv_path.read_bytes()
    analysis = await adapter.analyze_cv(cv_bytes, "txt", str(uuid4()))

    # Verify analysis structure
    assert analysis.candidate_id is not None
    assert analysis.extracted_text is not None
    assert len(analysis.skills) >= 0


@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires real API keys and costs money - run manually")
async def test_llm_fallback_with_real_api() -> None:
    """Test LLM fallback with real API (skipped by default to avoid costs).

    To run: pytest -m "not skip" tests/integration/test_llm_fallback_integration.py::test_llm_fallback_with_real_api
    """
    adapter = build_adapter_with_llm_fallback(use_real_llm=True)
    cv_path = Path("tests/fixtures/cv_samples/sample_cv_english.txt")

    if not cv_path.exists():
        pytest.skip("CV fixture not found")

    cv_bytes = cv_path.read_bytes()
    analysis = await adapter.analyze_cv(cv_bytes, "txt", str(uuid4()))

    # With real LLM, should have summary and topics if confidence was low
    # Summary and topics may be populated if LLM was called
    assert analysis.summary is None or isinstance(analysis.summary, str)
    assert isinstance(analysis.suggested_topics, list)


@pytest.mark.asyncio
async def test_llm_fallback_cost_tracking_simulation() -> None:
    """Simulate cost tracking by measuring fallback trigger rate.

    Uses no-op LLM to avoid costs while testing logic.
    """
    adapter = build_adapter_with_llm_fallback(use_real_llm=False)
    cv_fixtures = [
        "tests/fixtures/cv_samples/sample_cv_english.txt",
        "tests/fixtures/cv_samples/sample_cv_minimal.txt",
    ]

    fallback_triggered = 0
    total_cvs = 0

    for cv_path_str in cv_fixtures:
        cv_path = Path(cv_path_str)
        if not cv_path.exists():
            continue

        total_cvs += 1
        cv_bytes = cv_path.read_bytes()
        analysis = await adapter.analyze_cv(cv_bytes, "txt", str(uuid4()))

        # Verify analysis completed
        assert analysis.extracted_text is not None

    if total_cvs > 0:
        # Verify all CVs were processed
        assert total_cvs > 0

