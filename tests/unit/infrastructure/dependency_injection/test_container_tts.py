"""Unit tests for Container.start_tts_adapter() method."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.infrastructure.config.settings import Settings
from src.infrastructure.dependency_injection.container import Container


@pytest.fixture
def mock_settings():
    """Create mock settings."""
    settings = MagicMock(spec=Settings)
    settings.use_mock_tts = True
    settings.google_cloud_project_id = "test-project"
    settings.google_application_credentials = None
    settings.google_tts_voice_name = "en-US-Chirp3-HD-Charon"
    return settings


@pytest.fixture
def container(mock_settings):
    """Create Container instance with mock settings."""
    return Container(mock_settings)


class TestStartTTSAdapter:
    """Test suite for Container.start_tts_adapter() method."""

    @pytest.mark.asyncio
    async def test_start_tts_adapter_with_mock_tts_success(self, container):
        """Test start_tts_adapter() succeeds with mock TTS adapter."""
        # Execute
        await container.start_tts_adapter()

        # Verify TTS adapter was initialized
        assert container._tts_port is not None
        # Verify it's a mock adapter (no pre-warm call)
        from src.infrastructure.adapters.mock.mock_tts_adapter import MockTTSAdapter
        assert isinstance(container._tts_port, MockTTSAdapter)

    @pytest.mark.asyncio
    async def test_start_tts_adapter_with_real_tts_success(self, container):
        """Test start_tts_adapter() succeeds with real TTS adapter and pre-warm."""
        # Configure for real TTS
        container.settings.use_mock_tts = False
        container.settings.google_application_credentials = "/path/to/credentials.json"

        # Mock Google TTS adapter
        mock_tts = AsyncMock()
        mock_tts.synthesize_speech = AsyncMock(return_value=b"test-audio")

        with patch(
            "src.infrastructure.adapters.speech.google_chirp3_tts_adapter.GoogleChirp3TTSAdapter"
        ) as mock_adapter_cls:
            mock_adapter_cls.return_value = mock_tts

            # Execute
            await container.start_tts_adapter()

            # Verify TTS adapter was initialized
            assert container._tts_port is not None
            # Verify pre-warm was called
            mock_tts.synthesize_speech.assert_called_once_with("test", speed=1.0)

    @pytest.mark.asyncio
    async def test_start_tts_adapter_prewarm_failure_non_blocking(self, container):
        """Test start_tts_adapter() continues if pre-warm fails (non-blocking)."""
        # Configure for real TTS
        container.settings.use_mock_tts = False
        container.settings.google_application_credentials = "/path/to/credentials.json"

        # Mock Google TTS adapter with pre-warm failure
        mock_tts = AsyncMock()
        mock_tts.synthesize_speech = AsyncMock(side_effect=Exception("Network error"))

        with patch(
            "src.infrastructure.adapters.speech.google_chirp3_tts_adapter.GoogleChirp3TTSAdapter"
        ) as mock_adapter_cls:
            mock_adapter_cls.return_value = mock_tts

            # Execute (should not raise)
            await container.start_tts_adapter()

            # Verify TTS adapter was still initialized despite pre-warm failure
            assert container._tts_port is not None
            # Verify pre-warm was attempted
            mock_tts.synthesize_speech.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_tts_adapter_init_failure_non_blocking(self, container):
        """Test start_tts_adapter() handles initialization failure gracefully."""
        # Configure for real TTS with invalid credentials
        container.settings.use_mock_tts = False
        container.settings.google_application_credentials = "/invalid/path.json"

        # Mock Google TTS adapter to raise on initialization
        with patch(
            "src.infrastructure.adapters.speech.google_chirp3_tts_adapter.GoogleChirp3TTSAdapter",
            side_effect=FileNotFoundError("Credentials file not found"),
        ):
            # Execute (should not raise, should log warning)
            await container.start_tts_adapter()

            # Verify TTS adapter was not initialized
            assert container._tts_port is None

    @pytest.mark.asyncio
    async def test_start_tts_adapter_idempotent(self, container):
        """Test start_tts_adapter() can be called multiple times safely."""
        # Execute first time
        await container.start_tts_adapter()
        first_port = container._tts_port

        # Execute second time
        await container.start_tts_adapter()
        second_port = container._tts_port

        # Verify same instance (idempotent)
        assert first_port is second_port

