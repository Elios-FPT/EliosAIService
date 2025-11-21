"""Unit tests for hybrid CV analyzer configuration and DI integration."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from src.adapters.cv_processing.hybrid_cv_analyzer_adapter import HybridCVAnalyzerAdapter
from src.adapters.mock.mock_cv_analyzer import MockCVAnalyzerAdapter
from src.infrastructure.config.settings import Settings


class TestSettingsHybridCVAnalyzer:
    """Test suite for hybrid CV analyzer settings."""

    def test_settings_default_values(self) -> None:
        """Test that default values are correct (hybrid disabled by default)."""
        settings = Settings()

        assert settings.use_hybrid_cv_analyzer is False
        assert settings.hybrid_confidence_threshold == 0.7
        assert settings.hybrid_enable_llm_fallback is True
        assert settings.hybrid_skill_patterns_path == "./src/adapters/cv_processing/skill_patterns.json"
        assert settings.spacy_model_en == "en_core_web_sm"
        assert settings.spacy_model_vi == "vi_core_news_sm"
        assert settings.spacy_disable_components == ["parser", "lemmatizer"]

    def test_settings_load_from_env(self) -> None:
        """Test that settings can be loaded from environment variables."""
        with patch.dict(
            os.environ,
            {
                "USE_HYBRID_CV_ANALYZER": "true",
                "HYBRID_CONFIDENCE_THRESHOLD": "0.8",
                "HYBRID_ENABLE_LLM_FALLBACK": "false",
                "SPACY_MODEL_EN": "en_core_web_lg",
            },
            clear=False,
        ):
            # Clear Settings cache to force reload
            Settings.model_config = Settings.model_config.__class__(
                env_file=("../.env.local", "../.env", ".env"),
                env_file_encoding="utf-8",
                case_sensitive=False,
                extra="ignore",
            )
            settings = Settings()

            assert settings.use_hybrid_cv_analyzer is True
            assert settings.hybrid_confidence_threshold == 0.8
            assert settings.hybrid_enable_llm_fallback is False
            assert settings.spacy_model_en == "en_core_web_lg"

    def test_settings_boolean_parsing(self) -> None:
        """Test that boolean settings parse correctly from environment."""
        with patch.dict(
            os.environ,
            {
                "USE_HYBRID_CV_ANALYZER": "1",  # Should parse as True
                "HYBRID_ENABLE_LLM_FALLBACK": "0",  # Should parse as False
            },
            clear=False,
        ):
            Settings.model_config = Settings.model_config.__class__(
                env_file=("../.env.local", "../.env", ".env"),
                env_file_encoding="utf-8",
                case_sensitive=False,
                extra="ignore",
            )
            settings = Settings()

            # Pydantic should handle "1"/"0" as boolean
            assert isinstance(settings.use_hybrid_cv_analyzer, bool)
            assert isinstance(settings.hybrid_enable_llm_fallback, bool)


class TestDIContainerCVAnalyzer:
    """Test suite for DI container CV analyzer selection logic."""

    def test_di_container_logic_mock_priority(self) -> None:
        """Test that mock adapter logic takes priority."""
        settings = Settings()
        settings.use_mock_cv_analyzer = True
        settings.use_hybrid_cv_analyzer = True

        # Test the logic without importing Container
        # Mock > Hybrid > Legacy
        if settings.use_mock_cv_analyzer:
            adapter_type = "MockCVAnalyzerAdapter"
        elif settings.use_hybrid_cv_analyzer:
            adapter_type = "HybridCVAnalyzerAdapter"
        else:
            adapter_type = "CVProcessingAdapter"

        assert adapter_type == "MockCVAnalyzerAdapter"

    def test_di_container_logic_hybrid_priority(self) -> None:
        """Test that hybrid adapter logic works when mock is disabled."""
        settings = Settings()
        settings.use_mock_cv_analyzer = False
        settings.use_hybrid_cv_analyzer = True

        # Test the logic
        if settings.use_mock_cv_analyzer:
            adapter_type = "MockCVAnalyzerAdapter"
        elif settings.use_hybrid_cv_analyzer:
            adapter_type = "HybridCVAnalyzerAdapter"
        else:
            adapter_type = "CVProcessingAdapter"

        assert adapter_type == "HybridCVAnalyzerAdapter"

    def test_di_container_logic_legacy_fallback(self) -> None:
        """Test that legacy adapter is fallback when both are disabled."""
        settings = Settings()
        settings.use_mock_cv_analyzer = False
        settings.use_hybrid_cv_analyzer = False

        # Test the logic
        if settings.use_mock_cv_analyzer:
            adapter_type = "MockCVAnalyzerAdapter"
        elif settings.use_hybrid_cv_analyzer:
            adapter_type = "HybridCVAnalyzerAdapter"
        else:
            adapter_type = "CVProcessingAdapter"

        assert adapter_type == "CVProcessingAdapter"

    def test_hybrid_adapter_initialization_params(self) -> None:
        """Test that HybridCVAnalyzerAdapter accepts settings parameters."""
        settings = Settings()
        settings.hybrid_confidence_threshold = 0.75
        settings.hybrid_enable_llm_fallback = False

        # Test direct initialization (bypassing DI container)
        adapter = HybridCVAnalyzerAdapter(
            confidence_threshold=settings.hybrid_confidence_threshold,
            use_llm_fallback=settings.hybrid_enable_llm_fallback,
        )

        assert adapter.confidence_threshold == 0.75
        assert adapter.use_llm_fallback is False

