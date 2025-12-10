"""Integration tests for HybridCVAnalyzerAdapter using real extractors."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from src.infrastructure.adapters.cv_processing.confidence_scorer import ConfidenceScorer
from src.infrastructure.adapters.cv_processing.hybrid_cv_analyzer_adapter import (
    HybridCVAnalyzerAdapter,
)
from src.infrastructure.adapters.cv_processing.rule_based_extractor import RuleBasedExtractor
from src.infrastructure.adapters.cv_processing.spacy_ner_extractor import SpacyNERExtractor


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
    cv_bytes = cv_path.read_bytes()

    analysis = await adapter.analyze_cv(cv_bytes, "txt", str(uuid4()))

    assert analysis.skills, "Expected skills extracted from English CV"
    assert analysis.summary is not None or len(analysis.skills) > 0


@pytest.mark.asyncio
async def test_hybrid_analyzer_vietnamese_cv_runs_with_fallback() -> None:
    adapter = build_real_adapter()
    cv_path = Path("tests/fixtures/cv_samples/sample_cv_vietnamese.txt")
    cv_bytes = cv_path.read_bytes()

    analysis = await adapter.analyze_cv(cv_bytes, "txt", str(uuid4()))

    assert analysis.summary is not None or len(analysis.skills) > 0

