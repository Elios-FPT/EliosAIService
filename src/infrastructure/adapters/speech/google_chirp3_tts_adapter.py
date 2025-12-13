"""Google Cloud Text-to-Speech (WaveNet / Chirp3HD) adapter implementation.

This adapter provides multilingual text-to-speech using Google's TTS service.

Initial implementation uses WaveNet voices for cost parity with Azure.
Chirp3HD premium voices can be enabled via configuration without changing
the domain layer.
"""

import logging
import os
from pathlib import Path
from typing import Any

from google.api_core import exceptions as google_exceptions
from google.cloud import texttospeech

from src.application.ports.text_to_speech_port import TextToSpeechPort

logger = logging.getLogger(__name__)


def _resolve_credentials_path(path: str) -> str:
    """Resolve relative credentials path to absolute path.

    If path is relative, resolve it relative to the project root (where pyproject.toml exists).
    If path is already absolute, return as-is.

    Args:
        path: Credentials file path (relative or absolute)

    Returns:
        Absolute path to credentials file
    """
    if os.path.isabs(path):
        return path

    # Find project root (directory containing pyproject.toml)
    current = Path(__file__).resolve()
    while current.parent != current:
        if (current / "pyproject.toml").exists():
            project_root = current
            break
        current = current.parent
    else:
        # Fallback: use current working directory
        project_root = Path.cwd()

    resolved = (project_root / path).resolve()
    return str(resolved)


class GoogleChirp3TTSAdapter(TextToSpeechPort):
    """Google Cloud Text-to-Speech implementation of TextToSpeechPort.

    Notes:
    - Audio format: 16kHz mono LINEAR16 (WAV-compatible) to match existing pipeline.
    - Speed: Directly mapped to Google's ``speaking_rate`` (0.25-4.0).
    """

    def __init__(
        self,
        project_id: str,
        credentials_path: str | None = None,
        voice_name: str = "",
    ):
        """Initialize Google TTS adapter.

        Args:
            project_id: Google Cloud project ID (logged for observability)
            credentials_path: Optional path to service account JSON
            voice_name: Full voice name, e.g. "en-US-Wavenet-D" or "en-US-Chirp3-HD-Charon"
        """
        self.project_id = project_id
        self.credentials_path = credentials_path
        self.voice_name = voice_name

        # For TTS we require an explicit credentials_path from settings to avoid
        # surprises with differing working directories and relative env paths.
        try:
            if not credentials_path:
                # Log env var for easier debugging if misconfigured
                logger.error(
                    "Google TTS credentials_path not provided. "
                    "GOOGLE_APPLICATION_CREDENTIALS=%s",
                    os.getenv("GOOGLE_APPLICATION_CREDENTIALS"),
                )
                raise FileNotFoundError(
                    "Google TTS credentials_path is not configured. "
                    "Set settings.google_application_credentials to an absolute "
                    "path for the service account JSON."
                )

            from google.oauth2 import service_account

            # Resolve relative paths to absolute (handles PyCharm/IDE working directory differences)
            resolved_path = _resolve_credentials_path(credentials_path)
            if not os.path.exists(resolved_path):
                raise FileNotFoundError(
                    f"Google TTS credentials file not found: {resolved_path} "
                    f"(original path: {credentials_path})"
                )

            credentials = service_account.Credentials.from_service_account_file(  # type: ignore[no-untyped-call]
                resolved_path
            )
            self.client = texttospeech.TextToSpeechClient(credentials=credentials)
        except Exception as exc:  # pragma: no cover - defensive guardrail
            logger.error("Failed to initialize Google TTS client: %s", exc)
            raise

        logger.info(
            "Initialized Google TTS adapter "
            f"(project_id=%s, voice_name=%s)",
            project_id,
            voice_name,
        )

    async def synthesize_speech(
        self,
        text: str,
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

        request = self._build_synthesize_request(
            text=text,
            voice_name=self.voice_name,
            speed=speed,
        )

        try:
            response = await self._call_synthesize_async(request)
        except google_exceptions.InvalidArgument as exc:
            logger.error(
                "Invalid TTS request for voice '%s': %s. "
                "Request voice params: name=%s, language_code=%s, model=%s",
                self.voice_name,
                exc,
                request.voice.name,
                request.voice.language_code,
                getattr(request.voice, "model", "NOT SET"),
            )
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

        audio_bytes = await self.synthesize_speech(text=text, speed=speed)

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
            gender = texttospeech.SsmlVoiceGender(voice.ssml_gender).name
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
    ) -> texttospeech.SynthesizeSpeechRequest:
        """Build SynthesizeSpeechRequest with LINEAR16 config."""
        # Clamp speed to Google allowed range (0.25 - 4.0)
        speaking_rate = min(max(speed, 0.25), 4.0)

        language_code = self._language_from_voice(voice_name)

        synthesis_input = texttospeech.SynthesisInput(text=text)

        # Voice name already contains model information (e.g., "en-US-Chirp3-HD-Achernar")
        # No separate model parameter needed - the model is part of the voice name
        voice_params = texttospeech.VoiceSelectionParams(
            language_code=language_code,
            name=voice_name,
        )
        logger.debug(
            "Using voice '%s' with language_code='%s'",
            voice_name,
            language_code,
        )
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.LINEAR16,
            sample_rate_hertz=16000,
            speaking_rate=speaking_rate,
        )

        return texttospeech.SynthesizeSpeechRequest(
            input=synthesis_input,
            voice=voice_params,
            audio_config=audio_config,
        )

    async def _call_synthesize_async(
        self,
        request: texttospeech.SynthesizeSpeechRequest,
    ) -> texttospeech.SynthesizeSpeechResponse:
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

    def _normalize_voice_name(self, voice_name: str) -> str:
        """Normalize voice name to full Google Cloud voice name format.

        If voice_name is a short name (doesn't contain language code pattern),
        use the configured voice_name instead.

        Args:
            voice_name: Voice name (may be short like "Achird" or full like "en-US-Chirp3-HD-Achernar")

        Returns:
            Full Google Cloud voice name (e.g., "en-US-Chirp3-HD-Achernar")
        """
        # Check if voice_name looks like a full Google Cloud voice name
        # Full names typically contain language code pattern like "en-US" or "xx-XX"
        if "-" in voice_name and len(voice_name.split("-")) >= 3:
            # Looks like a full name (e.g., "en-US-Chirp3-HD-Achernar")
            return voice_name

        # Short name provided - use voice_name which should be a full name
        logger.debug(
            "Short voice name '%s' provided, using voice_name '%s'",
            voice_name,
            self.voice_name,
        )
        return self.voice_name


