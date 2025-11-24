"""Integration tests for HybridCVAnalyzerAdapter using real extractors."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from src.adapters.cv_processing.confidence_scorer import ConfidenceScorer
from src.adapters.cv_processing.hybrid_cv_analyzer_adapter import (
    HybridCVAnalyzerAdapter,
)
from src.adapters.cv_processing.rule_based_extractor import RuleBasedExtractor
from src.adapters.cv_processing.spacy_ner_extractor import SpacyNERExtractor


def build_real_adapter() -> HybridCVAnalyzerAdapter:
    ner_extractor = SpacyNERExtractor()
    # Access English model early so we can skip cleanly if missing
    try:
        _ = ner_extractor.nlp_en
    except RuntimeError as exc:  # pragma: no cover - skip condition
        pytest.skip(str(exc))

    return HybridCVAnalyzerAdapter(
        rule_extractor=RuleBasedExtractor(),
        ner_extractor=ner_extractor,
        confidence_scorer=ConfidenceScorer(),
    )


@pytest.mark.asyncio
async def test_hybrid_analyzer_english_cv_full_pipeline() -> None:
    adapter = build_real_adapter()
    cv_path = Path("tests/fixtures/cv_samples/sample_cv_english.txt")

    analysis = await adapter.analyze_cv(str(cv_path), uuid4())

    assert analysis.skills, "Expected skills extracted from English CV"
    assert analysis.extracted_text


@pytest.mark.asyncio
async def test_hybrid_analyzer_vietnamese_cv_runs_with_fallback() -> None:
    adapter = build_real_adapter()
    cv_path = Path("tests/fixtures/cv_samples/sample_cv_vietnamese.txt")

    analysis = await adapter.analyze_cv(str(cv_path), uuid4())

    assert analysis.extracted_text

