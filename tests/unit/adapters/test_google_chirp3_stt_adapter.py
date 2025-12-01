"""Unit tests for Google Chirp 3 STT adapter."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from google.api_core import exceptions as google_exceptions

from src.adapters.speech.google_chirp3_stt_adapter import GoogleChirp3STTAdapter


@pytest.fixture
def adapter():
    """Create adapter instance for testing."""
    with patch("google.cloud.speech_v2.SpeechClient"):
        return GoogleChirp3STTAdapter(
            project_id="test-project",
            credentials_path=None,
            model="chirp_3",
        )


@pytest.fixture
def mock_google_response():
    """Create mock Google API response."""
    # Create mock word with end_offset
    mock_word = Mock()
    mock_word.end_offset.total_seconds.return_value = 2.5

    # Create mock alternative
    mock_alternative = Mock()
    mock_alternative.transcript = "Hello world"
    mock_alternative.confidence = 0.95
    mock_alternative.words = [mock_word]

    # Create mock result
    mock_result = Mock()
    mock_result.alternatives = [mock_alternative]
    mock_result.language_code = "en-US"

    # Create mock response
    mock_response = Mock()
    mock_response.results = [mock_result]

    return mock_response


class TestGoogleChirp3STTAdapter:
    """Test suite for GoogleChirp3STTAdapter."""

    def test_init_with_credentials_path(self):
        """Test adapter initialization with credentials path."""
        with patch("google.cloud.speech_v2.SpeechClient") as mock_client:
            with patch("google.oauth2.service_account.Credentials") as mock_creds:
                adapter = GoogleChirp3STTAdapter(
                    project_id="test-project",
                    credentials_path="/path/to/creds.json",
                    model="chirp_3",
                    language="vi-VN",
                )

                assert adapter.project_id == "test-project"
                assert adapter.model == "chirp_3"
                assert adapter.default_language == "vi-VN"
                mock_creds.from_service_account_file.assert_called_once()

    def test_init_with_adc(self):
        """Test adapter initialization with Application Default Credentials."""
        with patch("google.cloud.speech_v2.SpeechClient") as mock_client:
            adapter = GoogleChirp3STTAdapter(
                project_id="test-project",
                credentials_path=None,
            )

            assert adapter.project_id == "test-project"
            assert adapter.credentials_path is None
            mock_client.assert_called_once()

    @pytest.mark.asyncio
    async def test_transcribe_audio_success(self, adapter, mock_google_response):
        """Test successful transcription with voice metrics."""
        # Mock API call
        adapter._call_api_with_retry = Mock(return_value=mock_google_response)

        # Test
        audio_bytes = b"fake_audio_data"
        result = await adapter.transcribe_audio(audio_bytes, language="en-US")

        # Assertions
        assert result["text"] == "Hello world"
        assert 0.0 <= result["voice_metrics"]["intonation_score"] <= 1.0
        assert 0.0 <= result["voice_metrics"]["fluency_score"] <= 1.0
        assert result["voice_metrics"]["confidence_score"] == 0.95
        assert result["metadata"]["duration_seconds"] == 2.5
        assert isinstance(result["voice_metrics"]["speaking_rate_wpm"], int)

    @pytest.mark.asyncio
    async def test_transcribe_audio_no_speech(self, adapter):
        """Test transcription with no speech detected."""
        # Mock empty response
        mock_response = Mock()
        mock_response.results = []

        adapter._call_api_with_retry = Mock(return_value=mock_response)

        # Test
        with pytest.raises(ValueError, match="No speech detected"):
            await adapter.transcribe_audio(b"audio", language="en-US")

    @pytest.mark.asyncio
    async def test_transcribe_audio_invalid_argument(self, adapter):
        """Test transcription with invalid audio format."""
        adapter._call_api_with_retry = Mock(
            side_effect=google_exceptions.InvalidArgument("Invalid format")
        )

        with pytest.raises(ValueError, match="Invalid audio format"):
            await adapter.transcribe_audio(b"invalid", language="en-US")

    @pytest.mark.asyncio
    async def test_transcribe_audio_quota_exceeded(self, adapter):
        """Test transcription with quota exceeded error."""
        adapter._call_api_with_retry = Mock(
            side_effect=google_exceptions.ResourceExhausted("Quota exceeded")
        )

        with pytest.raises(ValueError, match="quota exceeded"):
            await adapter.transcribe_audio(b"audio", language="en-US")

    @pytest.mark.asyncio
    async def test_transcribe_audio_timeout(self, adapter):
        """Test transcription with API timeout."""
        adapter._call_api_with_retry = Mock(
            side_effect=google_exceptions.DeadlineExceeded("Timeout")
        )

        with pytest.raises(ValueError, match="timeout"):
            await adapter.transcribe_audio(b"audio", language="en-US")

    def test_calculate_voice_metrics_optimal_speaking_rate(self, adapter):
        """Test voice metrics calculation with optimal speaking rate (120-180 WPM)."""
        # 150 WPM = optimal
        transcript = " ".join(["word"] * 25)  # 25 words
        duration = 10.0  # 25 words / 10s * 60 = 150 WPM

        metrics = adapter._calculate_voice_metrics(
            confidence=0.9,
            transcript=transcript,
            duration_seconds=duration,
        )

        assert metrics["speaking_rate_wpm"] == 150
        assert metrics["fluency_score"] >= 0.9  # High fluency for optimal rate
        assert metrics["confidence_score"] == 0.9
        assert 0.0 <= metrics["intonation_score"] <= 1.0

    def test_calculate_voice_metrics_slow_speaking_rate(self, adapter):
        """Test voice metrics with slow speaking rate (<120 WPM)."""
        # 100 WPM = slightly slow
        transcript = " ".join(["word"] * 10)
        duration = 6.0  # 10 words / 6s * 60 = 100 WPM

        metrics = adapter._calculate_voice_metrics(
            confidence=0.8,
            transcript=transcript,
            duration_seconds=duration,
        )

        assert metrics["speaking_rate_wpm"] == 100
        assert 0.7 <= metrics["fluency_score"] < 0.9  # Moderate fluency

    def test_calculate_voice_metrics_fast_speaking_rate(self, adapter):
        """Test voice metrics with fast speaking rate (>180 WPM)."""
        # 200 WPM = slightly fast
        transcript = " ".join(["word"] * 40)
        duration = 12.0  # 40 words / 12s * 60 = 200 WPM

        metrics = adapter._calculate_voice_metrics(
            confidence=0.85,
            transcript=transcript,
            duration_seconds=duration,
        )

        assert metrics["speaking_rate_wpm"] == 200
        assert 0.7 <= metrics["fluency_score"] < 0.9  # Moderate fluency

    def test_calculate_voice_metrics_very_fast(self, adapter):
        """Test voice metrics with very fast speaking rate (>220 WPM)."""
        # 250 WPM = too fast
        transcript = " ".join(["word"] * 50)
        duration = 12.0  # 50 / 12 * 60 = 250 WPM

        metrics = adapter._calculate_voice_metrics(
            confidence=0.7,
            transcript=transcript,
            duration_seconds=duration,
        )

        assert metrics["speaking_rate_wpm"] == 250
        assert metrics["fluency_score"] == 0.5  # Low fluency for very fast

    def test_calculate_voice_metrics_error_handling(self, adapter):
        """Test voice metrics calculation with errors returns safe defaults."""
        # Trigger error with invalid duration
        metrics = adapter._calculate_voice_metrics(
            confidence=None,  # Will cause error
            transcript="test",
            duration_seconds=0,
        )

        # Should return defaults
        assert metrics["intonation_score"] == 0.7
        assert metrics["fluency_score"] == 0.7
        assert metrics["confidence_score"] == 0.7
        assert metrics["speaking_rate_wpm"] == 150

    @pytest.mark.asyncio
    async def test_transcribe_stream_success(self, adapter, mock_google_response):
        """Test successful streaming transcription."""
        # Mock streaming response
        mock_google_response.results[0].is_final = True

        def mock_streaming_recognize(requests):
            yield mock_google_response

        adapter.client.streaming_recognize = Mock(side_effect=mock_streaming_recognize)

        # Test
        audio_stream = b"audio_stream_data"
        result = await adapter.transcribe_stream(audio_stream, language="en-US")

        # Assertions
        assert result["text"] == "Hello world"
        assert "streaming_latency_seconds" in result["metadata"]
        assert result["metadata"]["streaming_latency_seconds"] >= 0  # Can be 0 in mocked tests

    @pytest.mark.asyncio
    async def test_transcribe_stream_no_final_result(self, adapter):
        """Test streaming with no final result."""

        def mock_streaming_recognize(requests):
            # Return only interim results (no final)
            mock_result = Mock()
            mock_result.is_final = False
            mock_result.alternatives = [Mock(transcript="interim")]

            mock_response = Mock()
            mock_response.results = [mock_result]

            yield mock_response

        adapter.client.streaming_recognize = Mock(side_effect=mock_streaming_recognize)

        with pytest.raises(ValueError, match="No final result"):
            await adapter.transcribe_stream(b"audio", language="en-US")

    @pytest.mark.asyncio
    async def test_detect_language_success(self, adapter, mock_google_response):
        """Test successful language detection."""
        mock_google_response.results[0].language_code = "vi-VN"
        adapter.client.recognize = Mock(return_value=mock_google_response)

        # Test
        detected = await adapter.detect_language(b"audio_data")

        # Assertions
        assert detected == "vi-VN"

    @pytest.mark.asyncio
    async def test_detect_language_no_results(self, adapter):
        """Test language detection with no results."""
        mock_response = Mock()
        mock_response.results = []

        adapter.client.recognize = Mock(return_value=mock_response)

        # Test
        detected = await adapter.detect_language(b"audio_data")

        # Should return None gracefully
        assert detected is None

    @pytest.mark.asyncio
    async def test_detect_language_api_error(self, adapter):
        """Test language detection with API error."""
        adapter.client.recognize = Mock(
            side_effect=google_exceptions.GoogleAPICallError("API error")
        )

        # Test
        detected = await adapter.detect_language(b"audio_data")

        # Should return None gracefully
        assert detected is None

    def test_call_api_with_retry_decorator(self, adapter):
        """Test that API calls use retry decorator."""
        # Check that _call_api_with_retry has retry decorator
        assert hasattr(adapter._call_api_with_retry, "__wrapped__")
