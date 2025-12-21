"""Integration tests for LLMCVAnalyzerAdapter."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from src.infrastructure.adapters.cv_processing.llm_cv_analyzer_adapter import LLMCVAnalyzerAdapter
from src.infrastructure.dependency_injection.container import get_container


@pytest.mark.integration
@pytest.mark.asyncio
async def test_llm_analyzer_english_cv() -> None:
    """Test LLM analyzer with real English CV."""
    container = get_container()
    adapter = container.cv_analyzer_port()

    cv_path = Path("tests/fixtures/cv_samples/sample_cv_english.txt")
    if not cv_path.exists():
        pytest.skip("CV fixture not found")

    cv_bytes = cv_path.read_bytes()
    analysis = await adapter.analyze_cv(cv_bytes, "txt", str(uuid4()))

    assert analysis.skills, "Expected skills extracted from CV"
    assert analysis.summary, "Expected summary generated"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_di_container_returns_llm_adapter() -> None:
    """Test DI container returns LLMCVAnalyzerAdapter."""
    container = get_container()
    adapter = container.cv_analyzer_port()

    assert isinstance(adapter, LLMCVAnalyzerAdapter)
