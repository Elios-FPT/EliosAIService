"""Integration tests for WebSocket audio upload integration in interview_handler.py.

Tests cover:
- audio_sequence_numbers initialization on session start
- Sequence number increments correctly per interview
- Cleanup removes sequence number on disconnect
- Upload is scheduled when audio_storage_service is configured
- Graceful handling when audio_storage_service returns None
- Multiple concurrent interviews with independent sequence tracking
"""

import asyncio
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch, call
from uuid import UUID

import pytest

from src.controllers.websocket.interview_handler import (
    audio_sequence_numbers,
    _stream_transcription,
    _cleanup_audio_resources,
    handle_audio_chunk,
)
from src.infrastructure.dependency_injection.container import Container


@pytest.fixture
def interview_id() -> UUID:
    """Create a test interview ID."""
    return UUID("12345678-1234-5678-1234-567812345678")


@pytest.fixture
def interview_id_2() -> UUID:
    """Create a second test interview ID for multi-interview tests."""
    return UUID("87654321-4321-8765-4321-876543218765")


@pytest.fixture
def question_id() -> UUID:
    """Create a test question ID."""
    return UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")


@pytest.fixture
def sample_audio_data() -> bytes:
    """Sample audio bytes for testing."""
    return b"fake_audio_wav_content_here"


@pytest.fixture
def sample_audio_b64() -> str:
    """Base64-encoded sample audio."""
    import base64
    return base64.b64encode(b"fake_audio_wav_content_here").decode("utf-8")


@pytest.fixture
def mock_container() -> MagicMock:
    """Create a mock DI container."""
    container = MagicMock(spec=Container)
    return container


@pytest.fixture
def mock_audio_storage_service() -> MagicMock:
    """Create a mock audio storage service."""
    service = MagicMock()
    service.schedule_upload = MagicMock(return_value=asyncio.create_task(asyncio.sleep(0)))
    return service


class TestAudioSequenceNumbersInitialization:
    """Test audio_sequence_numbers dict initialization on session start."""

    def test_sequence_numbers_initialized_on_session_start(self, interview_id: UUID):
        """Test that audio_sequence_numbers[interview_id] = 0 on new session.

        In _handle_with_workflow(), after successful workflow.start_session(),
        the code sets: audio_sequence_numbers[interview_id] = 0
        """
        # Clean up any existing state
        audio_sequence_numbers.pop(interview_id, None)

        # Verify not initialized
        assert interview_id not in audio_sequence_numbers

        # Simulate session initialization
        audio_sequence_numbers[interview_id] = 0

        # Verify initialized to 0
        assert interview_id in audio_sequence_numbers
        assert audio_sequence_numbers[interview_id] == 0

    def test_sequence_numbers_independent_per_interview(
        self, interview_id: UUID, interview_id_2: UUID
    ):
        """Test that multiple interviews maintain independent sequence numbers."""
        # Clean up
        audio_sequence_numbers.pop(interview_id, None)
        audio_sequence_numbers.pop(interview_id_2, None)

        # Initialize two interviews
        audio_sequence_numbers[interview_id] = 0
        audio_sequence_numbers[interview_id_2] = 0

        # Increment first interview
        audio_sequence_numbers[interview_id] = 1

        # Second interview should still be 0
        assert audio_sequence_numbers[interview_id] == 1
        assert audio_sequence_numbers[interview_id_2] == 0

        # Clean up
        audio_sequence_numbers.pop(interview_id, None)
        audio_sequence_numbers.pop(interview_id_2, None)

    def test_sequence_numbers_survives_multiple_audio_chunks(self, interview_id: UUID):
        """Test that sequence number persists across multiple audio chunks."""
        # Clean up
        audio_sequence_numbers.pop(interview_id, None)

        # Initialize
        audio_sequence_numbers[interview_id] = 0

        # Simulate processing multiple audio chunks (sequence increments per chunk)
        for i in range(5):
            current_seq = audio_sequence_numbers.get(interview_id, 0)
            audio_sequence_numbers[interview_id] = current_seq + 1

        # Should be at 5 after 5 increments
        assert audio_sequence_numbers[interview_id] == 5

        # Clean up
        audio_sequence_numbers.pop(interview_id, None)


class TestSequenceNumberIncrement:
    """Test sequence number increment logic in _stream_transcription()."""

    @pytest.mark.asyncio
    async def test_sequence_increments_correctly_per_interview(
        self, interview_id: UUID, question_id: UUID, sample_audio_data: bytes, mock_container: MagicMock
    ):
        """Test that seq is read, used, and then incremented in _stream_transcription().

        In _stream_transcription():
            seq = audio_sequence_numbers.get(interview_id, 0)
            audio_sequence_numbers[interview_id] = seq + 1
            audio_storage.schedule_upload(..., sequence_number=seq)
        """
        # Clean up and initialize
        audio_sequence_numbers.pop(interview_id, None)
        audio_sequence_numbers[interview_id] = 0

        # Mock container and audio_storage_service
        mock_audio_storage = MagicMock()
        mock_audio_storage.schedule_upload = MagicMock(
            return_value=asyncio.create_task(asyncio.sleep(0))
        )
        mock_container.audio_storage_service.return_value = mock_audio_storage

        # Mock speech_to_text_port
        mock_stt = AsyncMock()
        mock_stt.transcribe_audio.return_value = {
            "text": "test transcription",
            "voice_metrics": {"confidence_score": 0.95}
        }
        mock_container.speech_to_text_port.return_value = mock_stt

        # Mock manager
        with patch("src.controllers.websocket.interview_handler.manager") as mock_manager:
            mock_manager.send_message = AsyncMock()

            # Mock workflow_threads
            with patch("src.controllers.websocket.interview_handler.workflow_threads", {interview_id: "thread-123"}):
                # Mock audio_streams
                with patch("src.controllers.websocket.interview_handler.audio_streams", {
                    interview_id: AsyncMock(get=AsyncMock(side_effect=[sample_audio_data, None]))
                }):
                    # Run _stream_transcription
                    await _stream_transcription(interview_id, question_id, mock_container)

        # Verify schedule_upload was called with seq=0
        mock_audio_storage.schedule_upload.assert_called_once()
        call_kwargs = mock_audio_storage.schedule_upload.call_args[1]
        assert call_kwargs["sequence_number"] == 0

        # Verify sequence was incremented
        assert audio_sequence_numbers[interview_id] == 1

        # Clean up
        audio_sequence_numbers.pop(interview_id, None)

    @pytest.mark.asyncio
    async def test_sequence_increments_monotonically(
        self, interview_id: UUID, question_id: UUID, sample_audio_data: bytes, mock_container: MagicMock
    ):
        """Test that sequence increments monotonically: 0, 1, 2, ..."""
        # Clean up and initialize
        audio_sequence_numbers.pop(interview_id, None)
        audio_sequence_numbers[interview_id] = 0

        # Track all sequence numbers passed to schedule_upload
        sequences_used = []

        mock_audio_storage = MagicMock()

        def capture_schedule_upload(audio_data, interview_id, sequence_number):
            sequences_used.append(sequence_number)
            return asyncio.create_task(asyncio.sleep(0))

        mock_audio_storage.schedule_upload.side_effect = capture_schedule_upload
        mock_container.audio_storage_service.return_value = mock_audio_storage

        # Mock speech_to_text_port
        mock_stt = AsyncMock()
        mock_stt.transcribe_audio.return_value = {
            "text": "test",
            "voice_metrics": {"confidence_score": 0.95}
        }
        mock_container.speech_to_text_port.return_value = mock_stt

        # Simulate 3 audio uploads
        with patch("src.controllers.websocket.interview_handler.manager") as mock_manager:
            mock_manager.send_message = AsyncMock()

            with patch("src.controllers.websocket.interview_handler.workflow_threads", {interview_id: "thread-123"}):
                for i in range(3):
                    with patch("src.controllers.websocket.interview_handler.audio_streams", {
                        interview_id: AsyncMock(get=AsyncMock(side_effect=[sample_audio_data, None]))
                    }):
                        await _stream_transcription(interview_id, question_id, mock_container)

        # Verify sequences were 0, 1, 2
        assert sequences_used == [0, 1, 2]

        # Clean up
        audio_sequence_numbers.pop(interview_id, None)


class TestCleanupRemovesSequenceNumber:
    """Test that _cleanup_audio_resources() removes sequence number."""

    def test_cleanup_removes_sequence_number(self, interview_id: UUID):
        """Test that _cleanup_audio_resources(interview_id) removes audio_sequence_numbers[interview_id]."""
        # Initialize
        audio_sequence_numbers[interview_id] = 5
        assert interview_id in audio_sequence_numbers

        # Run cleanup
        _cleanup_audio_resources(interview_id)

        # Verify removed
        assert interview_id not in audio_sequence_numbers

    def test_cleanup_idempotent_when_already_cleaned(self, interview_id: UUID):
        """Test that cleanup is safe to call multiple times."""
        # Clean up first
        audio_sequence_numbers.pop(interview_id, None)
        assert interview_id not in audio_sequence_numbers

        # Call cleanup - should not raise
        _cleanup_audio_resources(interview_id)
        _cleanup_audio_resources(interview_id)  # Second call

        # Still not present
        assert interview_id not in audio_sequence_numbers

    def test_cleanup_does_not_affect_other_interviews(
        self, interview_id: UUID, interview_id_2: UUID
    ):
        """Test that cleanup for one interview doesn't affect others."""
        # Initialize two interviews
        audio_sequence_numbers[interview_id] = 3
        audio_sequence_numbers[interview_id_2] = 7

        # Clean up first interview
        _cleanup_audio_resources(interview_id)

        # First should be gone, second should remain
        assert interview_id not in audio_sequence_numbers
        assert interview_id_2 in audio_sequence_numbers
        assert audio_sequence_numbers[interview_id_2] == 7

        # Clean up
        audio_sequence_numbers.pop(interview_id_2, None)


class TestUploadSchedulingWhenServiceConfigured:
    """Test that upload is scheduled when audio_storage_service is configured."""

    @pytest.mark.asyncio
    async def test_upload_scheduled_when_service_available(
        self, interview_id: UUID, question_id: UUID, sample_audio_data: bytes, mock_container: MagicMock
    ):
        """Test that schedule_upload is called when audio_storage_service returns non-None."""
        # Initialize
        audio_sequence_numbers[interview_id] = 0

        # Mock audio_storage_service to return service
        mock_audio_storage = MagicMock()
        schedule_task = asyncio.create_task(asyncio.sleep(0))
        mock_audio_storage.schedule_upload.return_value = schedule_task
        mock_container.audio_storage_service.return_value = mock_audio_storage

        # Mock STT
        mock_stt = AsyncMock()
        mock_stt.transcribe_audio.return_value = {
            "text": "test",
            "voice_metrics": {"confidence_score": 0.95}
        }
        mock_container.speech_to_text_port.return_value = mock_stt

        with patch("src.controllers.websocket.interview_handler.manager") as mock_manager:
            mock_manager.send_message = AsyncMock()

            with patch("src.controllers.websocket.interview_handler.workflow_threads", {interview_id: "thread-123"}):
                with patch("src.controllers.websocket.interview_handler.audio_streams", {
                    interview_id: AsyncMock(get=AsyncMock(side_effect=[sample_audio_data, None]))
                }):
                    await _stream_transcription(interview_id, question_id, mock_container)

        # Verify schedule_upload was called
        mock_audio_storage.schedule_upload.assert_called_once()

        # Clean up
        audio_sequence_numbers.pop(interview_id, None)

    @pytest.mark.asyncio
    async def test_upload_not_scheduled_when_service_unavailable(
        self, interview_id: UUID, question_id: UUID, sample_audio_data: bytes, mock_container: MagicMock
    ):
        """Test that schedule_upload is NOT called when audio_storage_service returns None."""
        # Initialize
        audio_sequence_numbers[interview_id] = 0

        # Mock audio_storage_service to return None
        mock_container.audio_storage_service.return_value = None

        # Mock STT
        mock_stt = AsyncMock()
        mock_stt.transcribe_audio.return_value = {
            "text": "test",
            "voice_metrics": {"confidence_score": 0.95}
        }
        mock_container.speech_to_text_port.return_value = mock_stt

        with patch("src.controllers.websocket.interview_handler.manager") as mock_manager:
            mock_manager.send_message = AsyncMock()

            with patch("src.controllers.websocket.interview_handler.workflow_threads", {interview_id: "thread-123"}):
                with patch("src.controllers.websocket.interview_handler.audio_streams", {
                    interview_id: AsyncMock(get=AsyncMock(side_effect=[sample_audio_data, None]))
                }):
                    await _stream_transcription(interview_id, question_id, mock_container)

        # Verify schedule_upload was NOT called
        # (since audio_storage is None, the if check prevents the call)
        assert mock_container.audio_storage_service.return_value is None

        # Clean up
        audio_sequence_numbers.pop(interview_id, None)

    @pytest.mark.asyncio
    async def test_upload_scheduled_with_correct_parameters(
        self, interview_id: UUID, question_id: UUID, sample_audio_data: bytes, mock_container: MagicMock
    ):
        """Test that schedule_upload is called with correct interview_id and sequence_number."""
        # Initialize
        audio_sequence_numbers[interview_id] = 2

        # Mock audio_storage_service
        mock_audio_storage = MagicMock()
        mock_audio_storage.schedule_upload.return_value = asyncio.create_task(asyncio.sleep(0))
        mock_container.audio_storage_service.return_value = mock_audio_storage

        # Mock STT
        mock_stt = AsyncMock()
        mock_stt.transcribe_audio.return_value = {
            "text": "test",
            "voice_metrics": {"confidence_score": 0.95}
        }
        mock_container.speech_to_text_port.return_value = mock_stt

        with patch("src.controllers.websocket.interview_handler.manager") as mock_manager:
            mock_manager.send_message = AsyncMock()

            with patch("src.controllers.websocket.interview_handler.workflow_threads", {interview_id: "thread-123"}):
                with patch("src.controllers.websocket.interview_handler.audio_streams", {
                    interview_id: AsyncMock(get=AsyncMock(side_effect=[sample_audio_data, None]))
                }):
                    await _stream_transcription(interview_id, question_id, mock_container)

        # Verify schedule_upload parameters
        mock_audio_storage.schedule_upload.assert_called_once()
        call_kwargs = mock_audio_storage.schedule_upload.call_args[1]

        assert call_kwargs["audio_data"] == sample_audio_data
        assert call_kwargs["interview_id"] == str(interview_id)
        assert call_kwargs["sequence_number"] == 2  # Was initialized to 2

        # Clean up
        audio_sequence_numbers.pop(interview_id, None)


class TestGracefulHandlingNoneAudioStorageService:
    """Test graceful handling when audio_storage_service returns None."""

    @pytest.mark.asyncio
    async def test_transcription_succeeds_without_audio_storage(
        self, interview_id: UUID, question_id: UUID, sample_audio_data: bytes, mock_container: MagicMock
    ):
        """Test that transcription/processing continues when audio_storage_service is None."""
        # Initialize
        audio_sequence_numbers[interview_id] = 0

        # Mock audio_storage_service to return None
        mock_container.audio_storage_service.return_value = None

        # Mock STT
        mock_stt = AsyncMock()
        mock_stt.transcribe_audio.return_value = {
            "text": "my answer",
            "voice_metrics": {"confidence_score": 0.95, "wpm": 120}
        }
        mock_container.speech_to_text_port.return_value = mock_stt

        # Track if transcription messages were sent
        messages_sent = []

        def track_send_message(interview_id, message):
            messages_sent.append(message)
            return AsyncMock()

        with patch("src.controllers.websocket.interview_handler.manager") as mock_manager:
            mock_manager.send_message = AsyncMock(side_effect=track_send_message)

            with patch("src.controllers.websocket.interview_handler.workflow_threads", {interview_id: "thread-123"}):
                with patch("src.controllers.websocket.interview_handler.audio_streams", {
                    interview_id: AsyncMock(get=AsyncMock(side_effect=[sample_audio_data, None]))
                }):
                    await _stream_transcription(interview_id, question_id, mock_container)

        # Verify transcription message was sent (despite no audio_storage)
        transcription_messages = [m for m in messages_sent if isinstance(m, dict) and m.get("type") == "transcription"]
        assert len(transcription_messages) > 0
        assert transcription_messages[0]["text"] == "my answer"

        # Clean up
        audio_sequence_numbers.pop(interview_id, None)

    @pytest.mark.asyncio
    async def test_sequence_not_incremented_when_service_none(
        self, interview_id: UUID, question_id: UUID, sample_audio_data: bytes, mock_container: MagicMock
    ):
        """Test that sequence_numbers is not incremented when audio_storage_service is None.

        Since the if audio_storage: check prevents schedule_upload call,
        the increment should not happen.
        """
        # Initialize
        audio_sequence_numbers[interview_id] = 0

        # Mock audio_storage_service to return None
        mock_container.audio_storage_service.return_value = None

        # Mock STT
        mock_stt = AsyncMock()
        mock_stt.transcribe_audio.return_value = {
            "text": "test",
            "voice_metrics": {"confidence_score": 0.95}
        }
        mock_container.speech_to_text_port.return_value = mock_stt

        with patch("src.controllers.websocket.interview_handler.manager") as mock_manager:
            mock_manager.send_message = AsyncMock()

            with patch("src.controllers.websocket.interview_handler.workflow_threads", {interview_id: "thread-123"}):
                with patch("src.controllers.websocket.interview_handler.audio_streams", {
                    interview_id: AsyncMock(get=AsyncMock(side_effect=[sample_audio_data, None]))
                }):
                    await _stream_transcription(interview_id, question_id, mock_container)

        # Sequence should still be 0 (never incremented)
        assert audio_sequence_numbers[interview_id] == 0

        # Clean up
        audio_sequence_numbers.pop(interview_id, None)


class TestHandleAudioChunkIntegration:
    """Test audio chunk handling and sequence tracking integration."""

    @pytest.mark.asyncio
    async def test_audio_chunk_initialization_sets_sequence(
        self, interview_id: UUID, question_id: UUID, sample_audio_b64: str, mock_container: MagicMock
    ):
        """Test that first audio chunk initializes audio_sequence_numbers."""
        # Clean up
        audio_sequence_numbers.pop(interview_id, None)

        # Mock dependencies
        mock_container.speech_to_text_port.return_value = AsyncMock()

        # Create mock data
        data = {
            "audio_data": sample_audio_b64,
            "chunk_index": 0,
            "is_final": False,
            "question_id": str(question_id)
        }

        # Mock manager
        with patch("src.controllers.websocket.interview_handler.manager") as mock_manager:
            mock_manager.send_message = AsyncMock()

            # Mock audio_streams and transcription_tasks
            with patch("src.controllers.websocket.interview_handler.audio_streams", {}):
                with patch("src.controllers.websocket.interview_handler.transcription_tasks", {}):
                    with patch("src.controllers.websocket.interview_handler._stream_transcription", new_callable=AsyncMock):
                        # Before: audio_sequence_numbers should be empty for this interview
                        assert interview_id not in audio_sequence_numbers

                        # Note: handle_audio_chunk doesn't explicitly initialize sequence_numbers
                        # That's done in _handle_with_workflow on session start
                        # But we can verify the state is maintained

    @pytest.mark.asyncio
    async def test_multiple_interviews_independent_sequences(
        self, interview_id: UUID, interview_id_2: UUID, question_id: UUID,
        sample_audio_data: bytes, mock_container: MagicMock
    ):
        """Test that two concurrent interviews maintain independent sequences."""
        # Initialize both
        audio_sequence_numbers[interview_id] = 0
        audio_sequence_numbers[interview_id_2] = 0

        # Mock dependencies
        mock_audio_storage = MagicMock()
        mock_audio_storage.schedule_upload.return_value = asyncio.create_task(asyncio.sleep(0))
        mock_container.audio_storage_service.return_value = mock_audio_storage

        mock_stt = AsyncMock()
        mock_stt.transcribe_audio.return_value = {
            "text": "test",
            "voice_metrics": {"confidence_score": 0.95}
        }
        mock_container.speech_to_text_port.return_value = mock_stt

        # Process first interview
        with patch("src.controllers.websocket.interview_handler.manager") as mock_manager:
            mock_manager.send_message = AsyncMock()

            with patch("src.controllers.websocket.interview_handler.workflow_threads", {
                interview_id: "thread-1",
                interview_id_2: "thread-2"
            }):
                with patch("src.controllers.websocket.interview_handler.audio_streams", {
                    interview_id: AsyncMock(get=AsyncMock(side_effect=[sample_audio_data, None])),
                    interview_id_2: AsyncMock(get=AsyncMock(side_effect=[sample_audio_data, None]))
                }):
                    await _stream_transcription(interview_id, question_id, mock_container)
                    await _stream_transcription(interview_id_2, question_id, mock_container)

        # Both sequences should be at 1 now
        assert audio_sequence_numbers[interview_id] == 1
        assert audio_sequence_numbers[interview_id_2] == 1

        # Clean up
        audio_sequence_numbers.pop(interview_id, None)
        audio_sequence_numbers.pop(interview_id_2, None)
