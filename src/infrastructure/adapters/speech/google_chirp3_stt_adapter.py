"""Google Cloud Speech-to-Text (Chirp 3) adapter implementation.

This adapter provides multilingual speech-to-text using Google's Chirp 3 model,
which supports 100+ languages with improved accuracy for accented speech.

Features:
- Batch transcription with voice metrics
- Streaming transcription (latency-tested for interview scenarios)
- Automatic language detection
- Comprehensive error handling with retry logic
"""

import asyncio
import logging
import os
import time
from pathlib import Path
from typing import Any

from google.api_core import client_options as client_options_lib
from google.api_core import exceptions as google_exceptions
from google.api_core import retry as google_retry
from google.cloud import speech_v2

from src.application.ports.speech_to_text_port import SpeechToTextPort

logger = logging.getLogger(__name__)


def _normalize_location(location: str) -> str:
    """Normalize location setting to full region name.

    Maps shorthand location values to full region names.
    Supports common aliases and full region names.

    Args:
        location: Location setting (us, us-central1, eu, asia, etc.)

    Returns:
        Normalized region name (e.g., "us" -> "us-central1")
    """
    # Map shorthand to full region names
    location_map = {
        # US regions
        "us": "us-central1",
        "us-central1": "us-central1",
        "us-central": "us-central1",
        "us-east1": "us-east1",
        "us-east4": "us-east4",
        "us-west1": "us-west1",
        "us-west2": "us-west2",
        "us-west3": "us-west3",
        "us-west4": "us-west4",
        # European regions
        "eu": "europe-west4",
        "europe": "europe-west4",
        "europe-west1": "europe-west1",
        "europe-west2": "europe-west2",
        "europe-west3": "europe-west3",
        "europe-west4": "europe-west4",
        "europe-west6": "europe-west6",
        "europe-west8": "europe-west8",
        "europe-west9": "europe-west9",
        "europe-central2": "europe-central2",
        "europe-north1": "europe-north1",
        # Asia Pacific regions
        "asia": "asia-southeast1",
        "asia-southeast1": "asia-southeast1",
        "asia-southeast2": "asia-southeast2",
        "asia-northeast1": "asia-northeast1",
        "asia-northeast2": "asia-northeast2",
        "asia-northeast3": "asia-northeast3",
        "asia-east1": "asia-east1",
        "asia-east2": "asia-east2",
        "asia-south1": "asia-south1",
        "asia-south2": "asia-south2",
        # Other regions
        "australia-southeast1": "australia-southeast1",
        "australia-southeast2": "australia-southeast2",
        "southamerica-east1": "southamerica-east1",
        "southamerica-west1": "southamerica-west1",
        "northamerica-northeast1": "northamerica-northeast1",
        "northamerica-northeast2": "northamerica-northeast2",
    }

    normalized = location_map.get(location.lower(), location.lower())
    return normalized


def _get_regional_endpoint(location: str) -> tuple[str | None, str]:
    """Map location setting to regional API endpoint and normalized location.

    For regional models like chirp_3, both the API client endpoint and
    recognizer location must match the region.

    Args:
        location: Location setting (us, asia-northeast1, etc.)

    Returns:
        Tuple of (regional API endpoint string, normalized location)
        Returns (None, "global") to use default global endpoint
    """
    normalized_location = _normalize_location(location)

    # Map normalized location to regional endpoints
    # Format: {region}-speech.googleapis.com
    location_to_endpoint = {
        # US regions
        "us-central1": "us-central1-speech.googleapis.com",
        "us-east1": "us-east1-speech.googleapis.com",
        "us-east4": "us-east4-speech.googleapis.com",
        "us-west1": "us-west1-speech.googleapis.com",
        "us-west2": "us-west2-speech.googleapis.com",
        "us-west3": "us-west3-speech.googleapis.com",
        "us-west4": "us-west4-speech.googleapis.com",
        # European regions
        "europe-west1": "europe-west1-speech.googleapis.com",
        "europe-west2": "europe-west2-speech.googleapis.com",
        "europe-west3": "europe-west3-speech.googleapis.com",
        "europe-west4": "europe-west4-speech.googleapis.com",
        "europe-west6": "europe-west6-speech.googleapis.com",
        "europe-west8": "europe-west8-speech.googleapis.com",
        "europe-west9": "europe-west9-speech.googleapis.com",
        "europe-central2": "europe-central2-speech.googleapis.com",
        "europe-north1": "europe-north1-speech.googleapis.com",
        # Asia Pacific regions
        "asia-southeast1": "asia-southeast1-speech.googleapis.com",
        "asia-southeast2": "asia-southeast2-speech.googleapis.com",
        "asia-northeast1": "asia-northeast1-speech.googleapis.com",
        "asia-northeast2": "asia-northeast2-speech.googleapis.com",
        "asia-northeast3": "asia-northeast3-speech.googleapis.com",
        "asia-east1": "asia-east1-speech.googleapis.com",
        "asia-east2": "asia-east2-speech.googleapis.com",
        "asia-south1": "asia-south1-speech.googleapis.com",
        "asia-south2": "asia-south2-speech.googleapis.com",
        # Other regions
        "australia-southeast1": "australia-southeast1-speech.googleapis.com",
        "australia-southeast2": "australia-southeast2-speech.googleapis.com",
        "southamerica-east1": "southamerica-east1-speech.googleapis.com",
        "southamerica-west1": "southamerica-west1-speech.googleapis.com",
        "northamerica-northeast1": "northamerica-northeast1-speech.googleapis.com",
        "northamerica-northeast2": "northamerica-northeast2-speech.googleapis.com",
    }

    endpoint = location_to_endpoint.get(normalized_location)
    if endpoint:
        return endpoint, normalized_location
    else:
        # Unknown location, use global
        return None, "global"


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


class GoogleChirp3STTAdapter(SpeechToTextPort):
    """Google Cloud Speech-to-Text implementation using Chirp 3 model.

    Provides multilingual transcription (100+ languages) with voice metrics
    derived from Google confidence scores and speaking rate analysis.

    Voice Metrics Mapping:
    - confidence_score: Direct from Google API
    - intonation_score: Estimated from confidence + duration
    - fluency_score: Calculated from speaking rate (WPM analysis)
    - speaking_rate_wpm: Words per minute (domain-specific optimal range)
    """

    def __init__(
        self,
        project_id: str,
        credentials_path: str | None = None,
        model: str = "chirp_3",
        location: str = "us",
        language: str = "en-US",
    ):
        """Initialize Google Chirp 3 STT adapter.

        Args:
            project_id: Google Cloud project ID
            credentials_path: Path to service account JSON (None for ADC)
            model: STT model name (chirp_3, short, long, latest_long)
            location: Google Cloud region (us, asia-northeast1, etc.)
                     For regional models like chirp_3, this determines both the API endpoint
                     and the recognizer location (must match).
            language: Default language code (e.g., "en-US")
        """
        self.project_id = project_id
        self.credentials_path = credentials_path
        self.model = model
        self.location = location
        self.default_language = language

        # Get regional endpoint and normalized location
        # For regional models like chirp_3, both endpoint and recognizer location must match
        regional_endpoint, recognizer_location = _get_regional_endpoint(location)

        # Create recognizer resource name with appropriate location
        # Must match the API endpoint region when using regional endpoints
        self.recognizer = f"projects/{project_id}/locations/{recognizer_location}/recognizers/_"

        client_options = None
        if regional_endpoint:
            client_options = client_options_lib.ClientOptions(api_endpoint=regional_endpoint)
            logger.debug(
                f"Using regional endpoint: {regional_endpoint} "
                f"with recognizer location: {recognizer_location}"
            )

        # Initialize client (uses ADC or credentials_path)
        if credentials_path:
            from google.oauth2 import service_account

            # Resolve relative paths to absolute (handles PyCharm/IDE working directory differences)
            resolved_path = _resolve_credentials_path(credentials_path)
            if not os.path.exists(resolved_path):
                raise FileNotFoundError(
                    f"Google STT credentials file not found: {resolved_path} "
                    f"(original path: {credentials_path})"
                )

            credentials = service_account.Credentials.from_service_account_file(  # type: ignore[no-untyped-call]
                resolved_path
            )
            if client_options:
                self.client = speech_v2.SpeechClient(credentials=credentials, client_options=client_options)
            else:
                self.client = speech_v2.SpeechClient(credentials=credentials)
        else:
            if client_options:
                self.client = speech_v2.SpeechClient(client_options=client_options)  # Uses ADC with regional endpoint
            else:
                self.client = speech_v2.SpeechClient()  # Uses ADC with default endpoint

        logger.info(
            f"Initialized Google Chirp 3 STT adapter (model={model}, location={location}, language={language})"
        )

    async def transcribe_audio(
        self,
        audio_bytes: bytes,
        language: str = "en-US",
    ) -> dict[str, Any]:
        """Transcribe audio bytes to text with voice metrics.

        Args:
            audio_bytes: Audio data (WAV/PCM format, 16kHz mono)
            language: Language code (e.g., "en-US", "vi-VN")

        Returns:
            {
                "text": str,
                "voice_metrics": {
                    "intonation_score": float,
                    "fluency_score": float,
                    "confidence_score": float,
                    "speaking_rate_wpm": int,
                },
                "metadata": {
                    "duration_seconds": float,
                    "audio_format": str,
                }
            }

        Raises:
            ValueError: If no speech detected or transcription fails
        """
        # Run sync Google API in thread pool (no async support in v2 SDK)
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            self._transcribe_sync,
            audio_bytes,
            language,
        )

        return result

    def _transcribe_sync(
        self,
        audio_bytes: bytes,
        language: str,
    ) -> dict[str, Any]:
        """Synchronous transcription using Google Speech-to-Text API v2.

        Args:
            audio_bytes: Audio data as bytes
            language: Language code

        Returns:
            Dict with text, voice_metrics, and metadata

        Raises:
            ValueError: If transcription fails or no speech detected
        """
        try:
            # Build request
            request = speech_v2.RecognizeRequest(
                recognizer=self.recognizer,
                config=speech_v2.RecognitionConfig(
                    auto_decoding_config=speech_v2.AutoDetectDecodingConfig(),
                    model=self.model,
                    language_codes=[language],
                    features=speech_v2.RecognitionFeatures(
                        enable_word_time_offsets=True,
                        # Note: enable_word_confidence not supported by chirp_3 model
                    ),
                ),
                content=audio_bytes,
            )

            # Call API with retry
            response = self._call_api_with_retry(request)

            # Extract results
            if not response.results:
                logger.warning("No speech detected in audio")
                raise ValueError("No speech detected in audio")

            # Get best alternative
            result = response.results[0]
            alternative = result.alternatives[0]

            text = alternative.transcript
            confidence = alternative.confidence

            # Calculate duration from word timestamps (accurate for voice metrics)
            if alternative.words:
                duration_seconds = alternative.words[-1].end_offset.total_seconds()
                logger.debug(
                    f"Using word timestamps for duration: {duration_seconds:.2f}s "
                    f"(from {len(alternative.words)} words)"
                )
            else:
                # Fallback: estimate duration from audio size
                # Assume 16kHz mono PCM (32000 bytes/sec)
                duration_seconds = len(audio_bytes) / 32000.0
                logger.warning(
                    f"No word timestamps available, using estimated duration: {duration_seconds:.2f}s"
                )

            # Calculate voice metrics with accurate duration
            voice_metrics = self._calculate_voice_metrics(
                confidence=confidence,
                transcript=text,
                duration_seconds=duration_seconds,
            )

            logger.info(
                f"Transcribed {len(text)} chars, "
                f"duration={duration_seconds:.2f}s (accurate), "
                f"confidence={confidence:.3f}, "
                f"WPM={voice_metrics['speaking_rate_wpm']}"
            )

            return {
                "text": text,
                "voice_metrics": voice_metrics,
                "metadata": {
                    "duration_seconds": duration_seconds,
                    "audio_format": "wav",
                },
            }

        except google_exceptions.InvalidArgument as e:
            logger.error(f"Invalid request: {e}")
            raise ValueError(f"Invalid audio format or language: {e}") from e

        except google_exceptions.ResourceExhausted as e:
            logger.error(f"Quota exceeded: {e}")
            raise ValueError(f"Google Cloud quota exceeded: {e}") from e

        except google_exceptions.DeadlineExceeded as e:
            logger.error(f"API timeout: {e}")
            raise ValueError(f"Transcription timeout: {e}") from e

        except google_exceptions.GoogleAPICallError as e:
            logger.error(f"Google API call failed: {e}")
            raise ValueError(f"Speech recognition failed: {e}") from e

        except Exception as e:
            logger.error(f"Transcription error: {e}")
            raise

    def _calculate_voice_metrics(
        self, confidence: float, transcript: str, duration_seconds: float
    ) -> dict[str, Any]:
        """Calculate voice quality metrics from Google transcription results.

        Maps Google confidence scores to voice metrics required by domain.
        Uses speaking rate analysis for fluency calculation.

        Args:
            confidence: Google confidence score (0-1)
            transcript: Transcribed text
            duration_seconds: Audio duration

        Returns:
            Dict with intonation, fluency, confidence scores and speaking rate
        """
        try:
            # Intonation score (pitch variance estimation)
            # Higher confidence + longer speech = better intonation
            # Formula inherited from Azure adapter for consistency
            intonation_score = min(confidence + (duration_seconds / 30.0) * 0.1, 1.0)

            # Fluency score based on speaking rate
            word_count = len(transcript.split())
            speaking_rate_wpm = (
                int((word_count / duration_seconds) * 60) if duration_seconds > 0 else 0
            )

            # Optimal speaking rate: 120-180 WPM (interview context)
            if 120 <= speaking_rate_wpm <= 180:
                fluency_score = 0.9 + (confidence * 0.1)  # High fluency
            elif 90 <= speaking_rate_wpm < 120:
                # Slightly slow
                fluency_score = 0.7 + ((speaking_rate_wpm - 90) / 30.0) * 0.2
            elif 180 < speaking_rate_wpm <= 220:
                # Slightly fast
                fluency_score = 0.7 + ((220 - speaking_rate_wpm) / 40.0) * 0.2
            else:
                # Too slow (<90 WPM) or too fast (>220 WPM)
                fluency_score = 0.5

            # Clamp scores to [0, 1]
            intonation_score = max(0.0, min(intonation_score, 1.0))
            fluency_score = max(0.0, min(fluency_score, 1.0))
            confidence_score = max(0.0, min(confidence, 1.0))

            return {
                "intonation_score": round(intonation_score, 3),
                "fluency_score": round(fluency_score, 3),
                "confidence_score": round(confidence_score, 3),
                "speaking_rate_wpm": speaking_rate_wpm,
            }

        except Exception as e:
            logger.warning(f"Error calculating voice metrics, using defaults: {e}")
            # Return safe defaults if calculation fails
            return {
                "intonation_score": 0.7,
                "fluency_score": 0.7,
                "confidence_score": 0.7,
                "speaking_rate_wpm": 150,
            }

    async def transcribe_stream(
        self,
        audio_stream: bytes,
        language: str = "en-US",
    ) -> dict[str, Any]:
        """Transcribe streaming audio to text with voice metrics.

        WARNING: Chirp 3 processes in larger chunks, may not be suitable
        for true real-time use. Tested with interview-length responses
        (2-5 minutes). If latency >5s, fallback to standard Google model.

        Args:
            audio_stream: Audio data stream
            language: Language code

        Returns:
            Same dict structure as transcribe_audio()

        Raises:
            ValueError: If streaming transcription fails
        """
        # Run sync streaming API in thread pool
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            self._transcribe_stream_sync,
            audio_stream,
            language,
        )

        return result

    def _transcribe_stream_sync(
        self,
        audio_stream: bytes,
        language: str,
    ) -> dict[str, Any]:
        """Synchronous streaming transcription.

        Args:
            audio_stream: Audio data stream
            language: Language code

        Returns:
            Dict with text, voice_metrics, and metadata

        Raises:
            ValueError: If streaming fails
        """
        try:
            start_time = time.time()

            # Build streaming config
            # Note: chirp_3 doesn't support word timestamps in streaming requests
            streaming_config = speech_v2.StreamingRecognitionConfig(
                config=speech_v2.RecognitionConfig(
                    auto_decoding_config=speech_v2.AutoDetectDecodingConfig(),
                    model=self.model,
                    language_codes=[language],
                    # Note: enable_word_time_offsets not supported by chirp_3 in streaming
                    # Note: enable_word_confidence not supported by chirp_3 model
                ),
                streaming_features=speech_v2.StreamingRecognitionFeatures(
                    interim_results=True,  # Get partial results
                ),
            )

            # Create request generator
            def request_generator():  # type: ignore[no-untyped-def]
                # First request with config
                yield speech_v2.StreamingRecognizeRequest(
                    recognizer=self.recognizer,
                    streaming_config=streaming_config,
                )
                # Second request with audio
                yield speech_v2.StreamingRecognizeRequest(audio=audio_stream)

            # Call streaming API
            responses = self.client.streaming_recognize(requests=request_generator())  # type: ignore[no-untyped-call]

            # Process responses
            final_result = None

            for response in responses:
                if not response.results:
                    continue

                result = response.results[0]

                if result.is_final:
                    final_result = result
                    break  # Stop after final result
                else:
                    # Log interim results
                    logger.debug(f"Interim: {result.alternatives[0].transcript}")

            # Calculate latency
            latency = time.time() - start_time
            logger.info(f"Streaming latency: {latency:.2f}s")

            if not final_result:
                raise ValueError("No final result from streaming recognition")

            # Extract final result
            alternative = final_result.alternatives[0]
            text = alternative.transcript
            confidence = alternative.confidence

            # Calculate duration
            # Note: chirp_3 doesn't provide word timestamps in streaming, so use fallback
            # Estimate duration from audio size (assume 16kHz mono PCM: 32000 bytes/sec)
            duration_seconds = len(audio_stream) / 32000.0

            # Calculate voice metrics
            voice_metrics = self._calculate_voice_metrics(
                confidence=confidence,
                transcript=text,
                duration_seconds=duration_seconds,
            )

            # Add latency to metadata for monitoring
            return {
                "text": text,
                "voice_metrics": voice_metrics,
                "metadata": {
                    "duration_seconds": duration_seconds,
                    "audio_format": "wav",
                    "streaming_latency_seconds": latency,  # For monitoring
                },
            }

        except google_exceptions.GoogleAPICallError as e:
            logger.error(f"Streaming API call failed: {e}")
            raise ValueError(f"Streaming recognition failed: {e}") from e

        except Exception as e:
            logger.error(f"Streaming transcription error: {e}")
            raise

    async def detect_language(
        self,
        audio_bytes: bytes,
    ) -> str | None:
        """Detect language from audio bytes using Google auto-detection.

        Args:
            audio_bytes: Audio data as bytes

        Returns:
            Detected language code (e.g., "en-US") or None if detection fails
        """
        # Run sync API in thread pool
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            self._detect_language_sync,
            audio_bytes,
        )

        return result

    def _detect_language_sync(
        self,
        audio_bytes: bytes,
    ) -> str | None:
        """Synchronous language detection.

        Args:
            audio_bytes: Audio data as bytes

        Returns:
            Detected language code or None
        """
        try:
            # Build request with multiple candidate languages
            candidate_languages = [
                "en-US",
                "vi-VN",
                "zh-CN",
                "ja-JP",
                "ko-KR",  # Top 5
                "fr-FR",
                "de-DE",
                "es-ES",
                "it-IT",
                "pt-BR",  # Next 5
            ]

            request = speech_v2.RecognizeRequest(
                recognizer=self.recognizer,
                config=speech_v2.RecognitionConfig(
                    auto_decoding_config=speech_v2.AutoDetectDecodingConfig(),
                    model=self.model,
                    language_codes=candidate_languages,
                ),
                content=audio_bytes,
            )

            # Call API
            response = self.client.recognize(request=request)

            # Extract detected language
            if response.results:
                result = response.results[0]
                detected_language = result.language_code
                logger.info(f"Detected language: {detected_language}")
                return detected_language
            else:
                logger.warning("Language detection failed, no results")
                return None

        except google_exceptions.GoogleAPICallError as e:
            logger.error(f"Language detection API call failed: {e}")
            return None

        except Exception as e:
            logger.error(f"Language detection error: {e}")
            return None

    @google_retry.Retry(
        predicate=google_retry.if_transient_error,
        initial=1.0,
        maximum=10.0,
        multiplier=2.0,
    )
    def _call_api_with_retry(self, request: speech_v2.RecognizeRequest) -> Any:
        """Call Google API with exponential backoff retry.

        Args:
            request: RecognizeRequest to send

        Returns:
            RecognizeResponse from API

        Raises:
            google_exceptions.GoogleAPICallError: If all retries fail
        """
        return self.client.recognize(request=request)
