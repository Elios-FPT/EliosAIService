"""Unit tests for AudioStorageService.

Tests cover:
- Happy path: successful upload with mocked httpx
- Retry logic: failures followed by success
- Callback execution: success and error callbacks
- Error handling: HTTP errors, request errors, timeout
- Task scheduling: asyncio task creation and execution
"""

import asyncio
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import HTTPStatusError, RequestError, Response

from src.infrastructure.services.audio_storage_service import AudioStorageService


@pytest.fixture
def audio_storage_service() -> AudioStorageService:
    """Create AudioStorageService instance with test config."""
    return AudioStorageService(
        base_url="https://storage.example.com/upload",
        timeout=5.0,
    )


@pytest.fixture
def sample_audio_data() -> bytes:
    """Sample audio bytes for testing."""
    return b"fake_audio_data_wav_content"


@pytest.fixture
def interview_id() -> str:
    """Sample interview ID."""
    return "test-interview-123"


@pytest.fixture
def sequence_number() -> int:
    """Sample sequence number."""
    return 1


class TestUploadAudioHappyPath:
    """Test upload_audio() success scenarios."""

    @pytest.mark.asyncio
    async def test_upload_audio_success(
        self,
        audio_storage_service: AudioStorageService,
        sample_audio_data: bytes,
    ):
        """Test successful audio upload returns correct file path."""
        expected_path = "/audio/interview-123_1.wav"

        with patch("src.infrastructure.services.audio_storage_service.httpx.AsyncClient") as mock_client_class:
            # Mock the AsyncClient context manager
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Mock the response
            mock_response = MagicMock(spec=Response)
            mock_response.json.return_value = {"responseData": expected_path}
            mock_response.raise_for_status = MagicMock()
            mock_client.post.return_value = mock_response

            # Execute
            result = await audio_storage_service.upload_audio(
                audio_data=sample_audio_data,
                prefix="interview-audio",
                file_name="interview-123_1.wav",
            )

            # Assert
            assert result == expected_path
            mock_client.post.assert_called_once()
            call_args = mock_client.post.call_args
            assert call_args[0][0] == "https://storage.example.com/upload"
            assert call_args[1]["params"]["prefix"] == "interview-audio"
            assert call_args[1]["params"]["file_name"] == "interview-123_1.wav"

    @pytest.mark.asyncio
    async def test_upload_audio_includes_file_in_request(
        self,
        audio_storage_service: AudioStorageService,
        sample_audio_data: bytes,
    ):
        """Test that audio data is included in request as multipart file."""
        with patch("src.infrastructure.services.audio_storage_service.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            mock_response = MagicMock(spec=Response)
            mock_response.json.return_value = {"responseData": "/path/to/audio.wav"}
            mock_response.raise_for_status = MagicMock()
            mock_client.post.return_value = mock_response

            await audio_storage_service.upload_audio(
                audio_data=sample_audio_data,
                prefix="interview-audio",
                file_name="test.wav",
            )

            # Verify files parameter contains audio data
            call_args = mock_client.post.call_args
            files = call_args[1]["files"]
            assert "file" in files
            file_tuple = files["file"]
            assert file_tuple[0] == "test.wav"  # filename
            assert file_tuple[1] == sample_audio_data  # audio bytes
            assert file_tuple[2] == "audio/wav"  # content type

    @pytest.mark.asyncio
    async def test_upload_audio_respects_timeout(
        self,
        audio_storage_service: AudioStorageService,
        sample_audio_data: bytes,
    ):
        """Test that configured timeout is passed to AsyncClient."""
        custom_timeout = 10.0
        service = AudioStorageService(
            base_url="https://storage.example.com/upload",
            timeout=custom_timeout,
        )

        with patch("src.infrastructure.services.audio_storage_service.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            mock_response = MagicMock(spec=Response)
            mock_response.json.return_value = {"responseData": "/audio.wav"}
            mock_response.raise_for_status = MagicMock()
            mock_client.post.return_value = mock_response

            await service.upload_audio(
                audio_data=sample_audio_data,
                prefix="interview-audio",
                file_name="test.wav",
            )

            # Verify timeout was passed to AsyncClient
            mock_client_class.assert_called_once_with(timeout=custom_timeout)


class TestUploadAudioRetryLogic:
    """Test retry behavior on transient failures."""

    @pytest.mark.asyncio
    async def test_retry_on_http_status_error_then_success(
        self,
        audio_storage_service: AudioStorageService,
        sample_audio_data: bytes,
    ):
        """Test that service retries on HTTPStatusError and succeeds on third attempt."""
        expected_path = "/audio/success.wav"

        with patch("src.infrastructure.services.audio_storage_service.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Mock: fail twice with HTTPStatusError, succeed on 3rd attempt
            failure_response = MagicMock(spec=Response)
            failure_response.status_code = 500
            failure_response.raise_for_status.side_effect = HTTPStatusError(
                "Server Error",
                request=MagicMock(),
                response=failure_response,
            )

            success_response = MagicMock(spec=Response)
            success_response.json.return_value = {"responseData": expected_path}
            success_response.raise_for_status = MagicMock()

            # Set up side effects: fail twice, then succeed
            mock_client.post.side_effect = [
                failure_response,
                failure_response,
                success_response,
            ]

            # Execute - should retry and eventually succeed
            result = await audio_storage_service.upload_audio(
                audio_data=sample_audio_data,
                prefix="interview-audio",
                file_name="test.wav",
            )

            # Assert
            assert result == expected_path
            assert mock_client.post.call_count == 3

    @pytest.mark.asyncio
    async def test_retry_on_request_error_then_success(
        self,
        audio_storage_service: AudioStorageService,
        sample_audio_data: bytes,
    ):
        """Test that service retries on RequestError (connection/timeout) and succeeds."""
        expected_path = "/audio/success.wav"

        with patch("src.infrastructure.services.audio_storage_service.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Mock: fail once with RequestError, succeed on 2nd attempt
            mock_client.post.side_effect = [
                RequestError("Connection timeout"),
                MagicMock(
                    spec=Response,
                    json=MagicMock(return_value={"responseData": expected_path}),
                    raise_for_status=MagicMock(),
                ),
            ]

            # Execute
            result = await audio_storage_service.upload_audio(
                audio_data=sample_audio_data,
                prefix="interview-audio",
                file_name="test.wav",
            )

            # Assert
            assert result == expected_path
            assert mock_client.post.call_count == 2

    @pytest.mark.asyncio
    async def test_failure_after_max_retries(
        self,
        audio_storage_service: AudioStorageService,
        sample_audio_data: bytes,
    ):
        """Test that service raises exception after 3 failed attempts."""
        with patch("src.infrastructure.services.audio_storage_service.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Mock: always fail
            failure_response = MagicMock(spec=Response)
            failure_response.status_code = 503
            failure_response.raise_for_status.side_effect = HTTPStatusError(
                "Service Unavailable",
                request=MagicMock(),
                response=failure_response,
            )
            mock_client.post.return_value = failure_response

            # Execute and expect exception
            with pytest.raises(HTTPStatusError):
                await audio_storage_service.upload_audio(
                    audio_data=sample_audio_data,
                    prefix="interview-audio",
                    file_name="test.wav",
                )

            # Should attempt exactly 3 times (stop_after_attempt=3)
            assert mock_client.post.call_count == 3

    @pytest.mark.asyncio
    async def test_exponential_backoff_wait_times(
        self,
        audio_storage_service: AudioStorageService,
        sample_audio_data: bytes,
    ):
        """Test that retry uses exponential backoff with correct min/max bounds."""
        # This is implicit in tenacity configuration (multiplier=1, min=1, max=10)
        # Verify the decorator is configured correctly by checking retry spec
        import inspect
        from tenacity import Retrying

        # Get upload_audio method
        method = audio_storage_service.upload_audio

        # Check that tenacity retry decorator is applied
        assert hasattr(method, "retry")
        retry_obj = method.retry

        # Verify stop condition: stop_after_attempt(3)
        assert retry_obj.stop.max_attempt_number == 3

        # Verify wait condition: wait_exponential with bounds
        # min=1, max=10, multiplier=1
        assert hasattr(retry_obj.wait, "multiplier")
        assert retry_obj.wait.multiplier == 1
        assert retry_obj.wait.min == 1
        assert retry_obj.wait.max == 10


class TestScheduleUploadCallback:
    """Test schedule_upload() callback execution."""

    @pytest.mark.asyncio
    async def test_schedule_upload_creates_asyncio_task(
        self,
        audio_storage_service: AudioStorageService,
        sample_audio_data: bytes,
        interview_id: str,
        sequence_number: int,
    ):
        """Test that schedule_upload returns asyncio.Task."""
        callback = MagicMock()

        with patch.object(
            audio_storage_service,
            "upload_audio",
            new_callable=AsyncMock,
            return_value="/audio/path.wav",
        ):
            task = audio_storage_service.schedule_upload(
                audio_data=sample_audio_data,
                interview_id=interview_id,
                sequence_number=sequence_number,
                callback=callback,
            )

            assert isinstance(task, asyncio.Task)
            # Await task completion
            await task

    @pytest.mark.asyncio
    async def test_schedule_upload_calls_callback_on_success(
        self,
        audio_storage_service: AudioStorageService,
        sample_audio_data: bytes,
        interview_id: str,
        sequence_number: int,
    ):
        """Test that callback is called with path and None error on success."""
        expected_path = "/audio/test-interview-123_1.wav"
        callback = MagicMock()

        with patch.object(
            audio_storage_service,
            "upload_audio",
            new_callable=AsyncMock,
            return_value=expected_path,
        ):
            task = audio_storage_service.schedule_upload(
                audio_data=sample_audio_data,
                interview_id=interview_id,
                sequence_number=sequence_number,
                callback=callback,
            )

            # Wait for task to complete
            await task

            # Verify callback was called with success
            callback.assert_called_once_with(expected_path, None)

    @pytest.mark.asyncio
    async def test_schedule_upload_calls_callback_on_error(
        self,
        audio_storage_service: AudioStorageService,
        sample_audio_data: bytes,
        interview_id: str,
        sequence_number: int,
    ):
        """Test that callback is called with None path and exception on error."""
        test_error = Exception("Upload failed")
        callback = MagicMock()

        with patch.object(
            audio_storage_service,
            "upload_audio",
            new_callable=AsyncMock,
            side_effect=test_error,
        ):
            task = audio_storage_service.schedule_upload(
                audio_data=sample_audio_data,
                interview_id=interview_id,
                sequence_number=sequence_number,
                callback=callback,
            )

            # Wait for task to complete
            await task

            # Verify callback was called with error
            callback.assert_called_once()
            call_args = callback.call_args[0]
            assert call_args[0] is None  # path
            assert isinstance(call_args[1], Exception)
            assert str(call_args[1]) == "Upload failed"

    @pytest.mark.asyncio
    async def test_schedule_upload_without_callback(
        self,
        audio_storage_service: AudioStorageService,
        sample_audio_data: bytes,
        interview_id: str,
        sequence_number: int,
    ):
        """Test that schedule_upload works without callback."""
        with patch.object(
            audio_storage_service,
            "upload_audio",
            new_callable=AsyncMock,
            return_value="/audio/path.wav",
        ):
            task = audio_storage_service.schedule_upload(
                audio_data=sample_audio_data,
                interview_id=interview_id,
                sequence_number=sequence_number,
                callback=None,
            )

            # Should not raise any errors
            result = await task
            assert result is None

    @pytest.mark.asyncio
    async def test_schedule_upload_creates_correct_filename(
        self,
        audio_storage_service: AudioStorageService,
        sample_audio_data: bytes,
        interview_id: str,
        sequence_number: int,
    ):
        """Test that schedule_upload uses interview_id and sequence_number in filename."""
        callback = MagicMock()

        with patch.object(
            audio_storage_service,
            "upload_audio",
            new_callable=AsyncMock,
            return_value="/audio/path.wav",
        ) as mock_upload:
            task = audio_storage_service.schedule_upload(
                audio_data=sample_audio_data,
                interview_id=interview_id,
                sequence_number=sequence_number,
                callback=callback,
            )

            await task

            # Verify upload_audio was called with correct filename
            mock_upload.assert_called_once()
            call_args = mock_upload.call_args
            expected_filename = f"{interview_id}_{sequence_number}.wav"
            assert call_args[1]["file_name"] == expected_filename

    @pytest.mark.asyncio
    async def test_schedule_upload_fire_and_forget(
        self,
        audio_storage_service: AudioStorageService,
        sample_audio_data: bytes,
        interview_id: str,
        sequence_number: int,
    ):
        """Test that schedule_upload returns immediately (fire-and-forget)."""
        callback = MagicMock()
        call_count = 0

        async def slow_upload(*args, **kwargs):
            nonlocal call_count
            await asyncio.sleep(0.1)  # Simulate slow upload
            call_count += 1
            return "/audio/path.wav"

        with patch.object(
            audio_storage_service,
            "upload_audio",
            new_callable=AsyncMock,
            side_effect=slow_upload,
        ):
            # schedule_upload should return immediately
            task = audio_storage_service.schedule_upload(
                audio_data=sample_audio_data,
                interview_id=interview_id,
                sequence_number=sequence_number,
                callback=callback,
            )

            # Task created but not yet awaited - upload should not have completed
            assert call_count == 0
            assert not task.done()

            # Now await the task
            await task
            assert call_count == 1


class TestUploadAudioErrorHandling:
    """Test error handling in upload_audio()."""

    @pytest.mark.asyncio
    async def test_http_status_error_propagated(
        self,
        audio_storage_service: AudioStorageService,
        sample_audio_data: bytes,
    ):
        """Test that HTTPStatusError is raised and propagated after retries."""
        with patch("src.infrastructure.services.audio_storage_service.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            error_response = MagicMock(spec=Response)
            error_response.status_code = 404
            mock_client.post.side_effect = HTTPStatusError(
                "Not Found",
                request=MagicMock(),
                response=error_response,
            )

            with pytest.raises(HTTPStatusError):
                await audio_storage_service.upload_audio(
                    audio_data=sample_audio_data,
                    prefix="interview-audio",
                    file_name="test.wav",
                )

    @pytest.mark.asyncio
    async def test_request_error_propagated(
        self,
        audio_storage_service: AudioStorageService,
        sample_audio_data: bytes,
    ):
        """Test that RequestError is raised after retries."""
        with patch("src.infrastructure.services.audio_storage_service.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            mock_client.post.side_effect = RequestError("Connection failed")

            with pytest.raises(RequestError):
                await audio_storage_service.upload_audio(
                    audio_data=sample_audio_data,
                    prefix="interview-audio",
                    file_name="test.wav",
                )

    @pytest.mark.asyncio
    async def test_other_exceptions_not_retried(
        self,
        audio_storage_service: AudioStorageService,
        sample_audio_data: bytes,
    ):
        """Test that non-retryable exceptions are raised immediately."""
        with patch("src.infrastructure.services.audio_storage_service.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # ValueError is not in retry_if_exception_type
            mock_client.post.side_effect = ValueError("Invalid data")

            # Should raise immediately without retries
            with pytest.raises(ValueError):
                await audio_storage_service.upload_audio(
                    audio_data=sample_audio_data,
                    prefix="interview-audio",
                    file_name="test.wav",
                )

            # Should only call once (no retries for non-retryable errors)
            assert mock_client.post.call_count == 1

    @pytest.mark.asyncio
    async def test_empty_response_data_field(
        self,
        audio_storage_service: AudioStorageService,
        sample_audio_data: bytes,
    ):
        """Test handling of empty responseData in response."""
        with patch("src.infrastructure.services.audio_storage_service.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            mock_response = MagicMock(spec=Response)
            mock_response.json.return_value = {"responseData": ""}
            mock_response.raise_for_status = MagicMock()
            mock_client.post.return_value = mock_response

            # Should return empty string (no validation of response content)
            result = await audio_storage_service.upload_audio(
                audio_data=sample_audio_data,
                prefix="interview-audio",
                file_name="test.wav",
            )

            assert result == ""


class TestIntegration:
    """Integration-level tests for AudioStorageService."""

    @pytest.mark.asyncio
    async def test_full_workflow_success(
        self,
        audio_storage_service: AudioStorageService,
        sample_audio_data: bytes,
        interview_id: str,
        sequence_number: int,
    ):
        """Test complete workflow: schedule -> upload -> callback."""
        callback_results = []

        def capture_callback(path, error):
            callback_results.append((path, error))

        with patch.object(
            audio_storage_service,
            "upload_audio",
            new_callable=AsyncMock,
            return_value="/audio/interview-123_1.wav",
        ):
            task = audio_storage_service.schedule_upload(
                audio_data=sample_audio_data,
                interview_id=interview_id,
                sequence_number=sequence_number,
                callback=capture_callback,
            )

            # Wait for completion
            await task

            # Verify callback was called
            assert len(callback_results) == 1
            assert callback_results[0] == ("/audio/interview-123_1.wav", None)

    @pytest.mark.asyncio
    async def test_multiple_concurrent_uploads(
        self,
        audio_storage_service: AudioStorageService,
        sample_audio_data: bytes,
        interview_id: str,
    ):
        """Test concurrent upload scheduling."""
        callback_count = 0

        def increment_callback(path, error):
            nonlocal callback_count
            callback_count += 1

        with patch.object(
            audio_storage_service,
            "upload_audio",
            new_callable=AsyncMock,
            return_value="/audio/path.wav",
        ):
            # Schedule multiple uploads
            tasks = []
            for i in range(5):
                task = audio_storage_service.schedule_upload(
                    audio_data=sample_audio_data,
                    interview_id=interview_id,
                    sequence_number=i,
                    callback=increment_callback,
                )
                tasks.append(task)

            # Wait for all to complete
            await asyncio.gather(*tasks)

            # All callbacks should have been called
            assert callback_count == 5
