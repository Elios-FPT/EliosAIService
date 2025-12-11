"""Audio storage service for uploading interview audio to external storage."""

import asyncio
import logging
from typing import Any, Callable

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

logger = logging.getLogger(__name__)


class AudioStorageService:
    """Service for uploading audio files to external storage API.

    Implements fire-and-forget pattern with retry logic for
    non-blocking audio uploads during interview sessions.
    """

    def __init__(self, base_url: str, timeout: float = 30.0):
        """Initialize audio storage service.

        Args:
            base_url: External storage API base URL
            timeout: Request timeout in seconds
        """
        self.base_url = base_url
        self.timeout = timeout

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.RequestError)),
        reraise=True,
    )
    async def upload_audio(
        self,
        audio_data: bytes,
        prefix: str,
        file_name: str,
    ) -> str:
        """Upload audio binary to external storage service.

        Args:
            audio_data: Raw audio bytes
            prefix: Storage path prefix (e.g., "interview-audio")
            file_name: Target filename (e.g., "{interview_id}_{seq}.wav")

        Returns:
            Audio file URL from responseData field

        Raises:
            httpx.HTTPStatusError: On HTTP error responses
            httpx.RequestError: On connection/timeout errors
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            files = {"file": (file_name, audio_data, "audio/wav")}
            response = await client.post(
                self.base_url,
                params={"keyPrefix": prefix, "fileName": file_name},
                files=files,
            )
            response.raise_for_status()

            result = response.json()
            audio_file_path = result.get("responseData", "")

            logger.info(
                f"Audio uploaded successfully: {audio_file_path}",
                extra={
                    "prefix": prefix,
                    "file_name": file_name,
                    "audio_size_bytes": len(audio_data),
                },
            )

            return audio_file_path

    def schedule_upload(
        self,
        audio_data: bytes,
        interview_id: str,
        sequence_number: int,
        callback: Callable[[str | None, Exception | None], None] | None = None,
    ) -> asyncio.Task[None]:
        """Schedule non-blocking audio upload.

        Fire-and-forget pattern - does not block caller.

        Args:
            audio_data: Raw audio bytes (already decoded from base64)
            interview_id: Interview UUID string
            sequence_number: Question sequence number
            callback: Optional callback(path, error) on completion

        Returns:
            asyncio.Task for the upload operation
        """
        async def _upload_task():
            file_name = f"{interview_id}_{sequence_number}.wav"
            try:
                path = await self.upload_audio(
                    audio_data=audio_data,
                    prefix="interview-audio",
                    file_name=file_name,
                )
                if callback:
                    callback(path, None)
            except Exception as exc:
                logger.error(
                    f"Audio upload failed after retries: {exc}",
                    extra={
                        "interview_id": interview_id,
                        "sequence_number": sequence_number,
                        "error": str(exc),
                    },
                    exc_info=True,
                )
                if callback:
                    callback(None, exc)

        return asyncio.create_task(_upload_task())
