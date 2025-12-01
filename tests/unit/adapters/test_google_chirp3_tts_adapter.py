"""Unit tests for GoogleChirp3TTSAdapter."""

import os
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from google.api_core import exceptions as google_exceptions
from google.cloud import texttospeech_v1

from src.adapters.speech.google_chirp3_tts_adapter import GoogleChirp3TTSAdapter


@pytest.fixture
def adapter() -> GoogleChirp3TTSAdapter:
    """Create adapter instance with mocked client."""
    with patch("google.cloud.texttospeech_v1.TextToSpeechClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        return GoogleChirp3TTSAdapter(
            project_id="test-project",
            voice_type="WaveNet",
            default_voice="en-US-Wavenet-D",
        )


class TestGoogleChirp3TTSAdapter:
    """Test suite for GoogleChirp3TTSAdapter."""

    @pytest.mark.asyncio
    async def test_synthesize_speech_success(self, adapter: GoogleChirp3TTSAdapter) -> None:
        """Synthesize speech returns audio bytes on success."""
        mock_response = texttospeech_v1.SynthesizeSpeechResponse(
            audio_content=b"fake-audio"
        )

        async def fake_call(request: Any) -> texttospeech_v1.SynthesizeSpeechResponse:
            assert isinstance(request, texttospeech_v1.SynthesizeSpeechRequest)
            return mock_response

        adapter._call_synthesize_async = fake_call  # type: ignore[assignment]

        result = await adapter.synthesize_speech(
            text="Hello world",
            voice="en-US-Wavenet-D",
            speed=1.0,
        )

        assert result == b"fake-audio"

    @pytest.mark.asyncio
    async def test_synthesize_speech_empty_text_raises(self, adapter: GoogleChirp3TTSAdapter) -> None:
        """Empty text should raise ValueError."""
        with pytest.raises(ValueError, match="Text cannot be empty"):
            await adapter.synthesize_speech("", voice="en-US-Wavenet-D", speed=1.0)

    @pytest.mark.asyncio
    async def test_synthesize_speech_invalid_request_error(self, adapter: GoogleChirp3TTSAdapter) -> None:
        """InvalidArgument from Google should be mapped to ValueError."""

        async def fake_call(request: Any) -> texttospeech_v1.SynthesizeSpeechResponse:
            raise google_exceptions.InvalidArgument("bad request")

        adapter._call_synthesize_async = fake_call  # type: ignore[assignment]

        with pytest.raises(ValueError, match="Invalid TTS request"):
            await adapter.synthesize_speech("text", voice="en-US-Wavenet-D", speed=1.0)

    @pytest.mark.asyncio
    async def test_synthesize_speech_quota_exceeded_error(self, adapter: GoogleChirp3TTSAdapter) -> None:
        """ResourceExhausted should be mapped to RuntimeError."""

        async def fake_call(request: Any) -> texttospeech_v1.SynthesizeSpeechResponse:
            raise google_exceptions.ResourceExhausted("quota")

        adapter._call_synthesize_async = fake_call  # type: ignore[assignment]

        with pytest.raises(RuntimeError, match="quota"):
            await adapter.synthesize_speech("text", voice="en-US-Wavenet-D", speed=1.0)

    @pytest.mark.asyncio
    async def test_synthesize_speech_api_error(self, adapter: GoogleChirp3TTSAdapter) -> None:
        """Generic GoogleAPICallError should be mapped to RuntimeError."""

        async def fake_call(request: Any) -> texttospeech_v1.SynthesizeSpeechResponse:
            raise google_exceptions.GoogleAPICallError("api-error")

        adapter._call_synthesize_async = fake_call  # type: ignore[assignment]

        with pytest.raises(RuntimeError, match="api-error"):
            await adapter.synthesize_speech("text", voice="en-US-Wavenet-D", speed=1.0)

    @pytest.mark.asyncio
    async def test_synthesize_speech_empty_audio_raises(self, adapter: GoogleChirp3TTSAdapter) -> None:
        """Empty audio_content from Google should raise."""
        mock_response = texttospeech_v1.SynthesizeSpeechResponse(audio_content=b"")

        async def fake_call(request: Any) -> texttospeech_v1.SynthesizeSpeechResponse:
            return mock_response

        adapter._call_synthesize_async = fake_call  # type: ignore[assignment]

        with pytest.raises(RuntimeError, match="empty audio"):
            await adapter.synthesize_speech("text", voice="en-US-Wavenet-D", speed=1.0)

    @pytest.mark.asyncio
    async def test_save_speech_to_file_writes_bytes(self, tmp_path: Path, adapter: GoogleChirp3TTSAdapter) -> None:
        """save_speech_to_file should write a WAV file and return its path."""
        async def fake_synthesize(*_: Any, **__: Any) -> bytes:
            return b"audio-bytes"

        adapter.synthesize_speech = fake_synthesize  # type: ignore[assignment]

        output_path = tmp_path / "audio.wav"
        result_path = await adapter.save_speech_to_file(
            text="hello",
            output_path=str(output_path),
            voice="en-US-Wavenet-D",
            speed=1.0,
        )

        assert result_path == str(output_path)
        assert output_path.exists()
        assert output_path.read_bytes() == b"audio-bytes"

    @pytest.mark.asyncio
    async def test_save_speech_to_file_empty_path_raises(self, adapter: GoogleChirp3TTSAdapter) -> None:
        """Empty output path should raise ValueError."""
        with pytest.raises(ValueError, match="Output path cannot be empty"):
            await adapter.save_speech_to_file("text", "", voice="en-US-Wavenet-D", speed=1.0)

    def test_get_available_voices_filters_by_voice_type(self, adapter: GoogleChirp3TTSAdapter) -> None:
        """get_available_voices should filter catalog by configured voice_type."""
        # Prepare mocked voices
        voice_wavenet = texttospeech_v1.Voice(
            name="en-US-Wavenet-D",
            language_codes=["en-US"],
            ssml_gender=texttospeech_v1.SsmlVoiceGender.MALE,
        )
        voice_chirp = texttospeech_v1.Voice(
            name="en-US-Chirp3-HD-Charon",
            language_codes=["en-US"],
            ssml_gender=texttospeech_v1.SsmlVoiceGender.MALE,
        )

        class Response:
            def __init__(self, voices: list[texttospeech_v1.Voice]) -> None:
                self.voices = voices

        adapter.client.list_voices = MagicMock(return_value=Response([voice_wavenet, voice_chirp]))  # type: ignore[assignment]

        # When voice_type is WaveNet, only WaveNet voices should be returned
        adapter.voice_type = "WaveNet"
        voices = pytest.run_in_loop(adapter.get_available_voices())  # type: ignore[attr-defined]
        assert any(v["name"] == "en-US-Wavenet-D" for v in voices)
        assert all("Wavenet" in v["name"] for v in voices)

    def test_language_from_voice_parsing(self, adapter: GoogleChirp3TTSAdapter) -> None:
        """_language_from_voice should parse BCP-47 code from voice name."""
        assert adapter._language_from_voice("en-US-Wavenet-D") == "en-US"
        assert adapter._language_from_voice("vi-VN-Chirp3-HD-A") == "vi-VN"
        assert adapter._language_from_voice("invalid") == "en-US"


