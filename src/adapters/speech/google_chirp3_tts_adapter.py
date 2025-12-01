"""Google Cloud Text-to-Speech (WaveNet / Chirp3HD) adapter implementation.

This adapter provides multilingual text-to-speech using Google's TTS service.

Initial implementation uses WaveNet voices for cost parity with Azure.
Chirp3HD premium voices can be enabled via configuration without changing
the domain layer.
"""

import logging
import os
from typing import Any, Iterable

from google.api_core import exceptions as google_exceptions
from google.cloud import texttospeech_v1

from ...domain.ports.text_to_speech_port import TextToSpeechPort

logger = logging.getLogger(__name__)


class GoogleChirp3TTSAdapter(TextToSpeechPort):
    """Google Cloud Text-to-Speech implementation of TextToSpeechPort.

    Notes:
    - Audio format: 16kHz mono LINEAR16 (WAV-compatible) to match existing pipeline.
    - Speed: Directly mapped to Google's ``speaking_rate`` (0.25-4.0).
    - Voices:
        - Default type: WaveNet (cost-effective, high quality)
        - Optional premium: Chirp3HD (higher quality, higher cost)
    """

    def __init__(
        self,
        project_id: str,
        voice_type: str = "WaveNet",
        default_voice: str = "en-US-Wavenet-D",
    ):
        """Initialize Google TTS adapter.

        Args:
            project_id: Google Cloud project ID (logged for observability)
            voice_type: Preferred voice family ("WaveNet" or "Chirp3HD")
            default_voice: Default full voice name, e.g. "en-US-Wavenet-D"
        """
        self.project_id = project_id
        self.voice_type = voice_type
        self.default_voice = default_voice

        # Client uses ADC / service account env managed by infrastructure.
        self.client = texttospeech_v1.TextToSpeechClient()

        logger.info(
            "Initialized Google TTS adapter "
            f"(project_id=%s, voice_type=%s, default_voice=%s)",
            project_id,
            voice_type,
            default_voice,
        )

    async def synthesize_speech(
        self,
        text: str,
        voice: str = "en-US-AriaNeural",
        speed: float = 1.0,
    ) -> bytes:
        """Convert text to speech audio using Google Text-to-Speech.

        Args:
            text: Text to synthesize
            voice: Voice name (e.g., "en-US-Wavenet-D")
            speed: Speaking rate multiplier (0.5-2.0, default 1.0)

        Returns:
            WAV-compatible LINEAR16 audio bytes
        """
        if not text or not text.strip():
            raise ValueError("Text cannot be empty")

        # Use configured default if caller passes empty/None
        selected_voice = voice or self.default_voice

        request = self._build_synthesize_request(
            text=text,
            voice_name=selected_voice,
            speed=speed,
        )

        try:
            response = await self._call_synthesize_async(request)
        except google_exceptions.InvalidArgument as exc:
            logger.error("Invalid TTS request: %s", exc)
            raise ValueError(f"Invalid TTS request: {exc}") from exc
        except google_exceptions.ResourceExhausted as exc:
            logger.error("TTS quota exceeded: %s", exc)
            raise RuntimeError(f"Google TTS quota exceeded: {exc}") from exc
        except google_exceptions.GoogleAPICallError as exc:
            logger.error("Google TTS API call failed: %s", exc)
            raise RuntimeError(f"TTS synthesis failed: {exc}") from exc

        audio = response.audio_content
        if not audio:
            logger.error("Google TTS returned empty audio content")
            raise RuntimeError("TTS synthesis failed: empty audio")

        return audio

    async def save_speech_to_file(
        self,
        text: str,
        output_path: str,
        voice: str = "en-US-AriaNeural",
        speed: float = 1.0,
    ) -> str:
        """Convert text to speech and save audio to file.

        Returns:
            Path to saved audio file.
        """
        if not output_path:
            raise ValueError("Output path cannot be empty")

        # Ensure directory exists
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)

        audio_bytes = await self.synthesize_speech(text=text, voice=voice, speed=speed)

        with open(output_path, "wb") as f:
            f.write(audio_bytes)

        return output_path

    async def get_available_voices(self) -> list[dict[str, Any]]:
        """Return catalog of available voices filtered by configured type."""
        try:
            response = self.client.list_voices(request={})
        except google_exceptions.GoogleAPICallError as exc:
            logger.error("Failed to list Google TTS voices: %s", exc)
            raise RuntimeError(f"Failed to list TTS voices: {exc}") from exc

        voices: list[dict[str, Any]] = []
        desired_prefix = self._voice_prefix()

        for voice in response.voices:
            # voice.name examples:
            # - "en-US-Wavenet-D"
            # - "en-US-Chirp3-HD-Charon"
            name = voice.name
            if desired_prefix and desired_prefix not in name:
                continue

            locale = voice.language_codes[0] if voice.language_codes else "en-US"
            gender = texttospeech_v1.SsmlVoiceGender(voice.ssml_gender).name
            voice_type = self._infer_voice_type(name)

            voices.append(
                {
                    "name": name,
                    "locale": locale,
                    "gender": gender,
                    "voice_type": voice_type,
                }
            )

        return voices

    def _build_synthesize_request(
        self,
        text: str,
        voice_name: str,
        speed: float,
    ) -> texttospeech_v1.SynthesizeSpeechRequest:
        """Build SynthesizeSpeechRequest with LINEAR16 config."""
        # Clamp speed to Google allowed range (0.25 - 4.0)
        speaking_rate = min(max(speed, 0.25), 4.0)

        language_code = self._language_from_voice(voice_name)

        synthesis_input = texttospeech_v1.SynthesisInput(text=text)
        voice_params = texttospeech_v1.VoiceSelectionParams(
            language_code=language_code,
            name=voice_name,
        )
        audio_config = texttospeech_v1.AudioConfig(
            audio_encoding=texttospeech_v1.AudioEncoding.LINEAR16,
            sample_rate_hertz=16000,
            speaking_rate=speaking_rate,
        )

        return texttospeech_v1.SynthesizeSpeechRequest(
            input=synthesis_input,
            voice=voice_params,
            audio_config=audio_config,
        )

    async def _call_synthesize_async(
        self,
        request: texttospeech_v1.SynthesizeSpeechRequest,
    ) -> texttospeech_v1.SynthesizeSpeechResponse:
        """Async wrapper around sync Google TTS client for compatibility."""
        import asyncio

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.client.synthesize_speech, request)

    def _language_from_voice(self, voice_name: str) -> str:
        """Extract BCP-47 language code from Google voice name."""
        # Expected formats:
        # - "en-US-Wavenet-D"
        # - "en-US-Chirp3-HD-Charon"
        parts = voice_name.split("-")
        if len(parts) >= 2:
            return f"{parts[0]}-{parts[1]}"
        return "en-US"

    def _voice_prefix(self) -> str:
        """Return prefix substring used to filter voices by type."""
        if self.voice_type == "Chirp3HD":
            return "Chirp3"
        if self.voice_type == "WaveNet":
            return "Wavenet"
        # Unknown / any type -> no filtering
        return ""

    def _infer_voice_type(self, voice_name: str) -> str:
        """Infer high-level voice type from Google voice name."""
        if "Chirp3" in voice_name:
            return "Chirp3HD"
        if "Wavenet" in voice_name or "WaveNet" in voice_name:
            return "WaveNet"
        return "Standard"


