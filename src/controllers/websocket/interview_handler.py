"""WebSocket handler for interview sessions (workflow-based)."""

import asyncio
import base64
import logging
from asyncio import Queue
from typing import Any
from uuid import UUID

from fastapi import WebSocket, WebSocketDisconnect
from psycopg import OperationalError as PsycopgOperationalError

from ...infrastructure.database.session import session_scope
from ...infrastructure.dependency_injection.container import Container, get_container
from ...domain.models.interview import InterviewStatus
from .connection_manager import manager
from .workflow_guard import execute_with_workflow_guard

logger = logging.getLogger(__name__)

# Per-session state for streaming audio
audio_streams: dict[UUID, Queue[bytes | None]] = {}
transcription_tasks: dict[UUID, asyncio.Task[Any]] = {}
audio_sequence_numbers: dict[UUID, int] = {}

# Per-session state for workflow (thread IDs)
workflow_threads: dict[UUID, str] = {}


async def handle_interview_websocket(
    websocket: WebSocket,
    interview_id: UUID,
) -> None:
    """WebSocket handler for interview session (workflow-based).

    Uses InterviewConversationWorkflow for all interview sessions.

    Protocol:
        Client → Server: { type: "text_answer", question_id: UUID, answer_text: str }
        Server → Client: { type: "evaluation", ... }
        Server → Client: { type: "question", ... }
        Server → Client: { type: "interview_complete", ... }

    Args:
        websocket: WebSocket connection
        interview_id: Interview UUID
    """
    # Connect
    await manager.connect(interview_id, websocket)

    try:
        container = get_container()
        await _handle_with_workflow(websocket, interview_id, container)

    except WebSocketDisconnect:
        manager.disconnect(interview_id)
        _cleanup_audio_resources(interview_id)
        _cleanup_workflow_resources(interview_id)
        logger.info(f"Client disconnected from interview {interview_id}")

    except ValueError as e:
        logger.error(f"State machine error for interview {interview_id}: {e}")
        await manager.send_message(
            interview_id,
            {"type": "error", "code": "INVALID_STATE", "message": str(e)},
        )
        _cleanup_audio_resources(interview_id)
        _cleanup_workflow_resources(interview_id)
        manager.disconnect(interview_id)

    except Exception as e:
        logger.error(f"WebSocket error for interview {interview_id}: {e}", exc_info=True)
        await manager.send_message(
            interview_id,
            {"type": "error", "code": "INTERNAL_ERROR", "message": str(e)},
        )
        _cleanup_audio_resources(interview_id)
        _cleanup_workflow_resources(interview_id)
        manager.disconnect(interview_id)


async def _handle_with_workflow(
    websocket: WebSocket,
    interview_id: UUID,
    container: Container,
) -> None:
    """Handle interview with LangGraph workflow.

    Args:
        websocket: WebSocket connection
        interview_id: Interview UUID
        container: DI container
    """
    async with session_scope() as session:
        # Get candidate_id from interview
        interview_repo = container.interview_repository_port(session=session)
        interview = await interview_repo.get_by_id(interview_id)
        if not interview:
            await manager.send_message(
                interview_id,
                {"type": "error", "code": "INTERVIEW_NOT_FOUND", "message": "Interview not found"},
            )
            return

        # Create workflow
        workflow = await container.create_interview_conversation_workflow(session)

        # Start session with guard
        try:
            result = await execute_with_workflow_guard(
                "start_session",
                lambda: workflow.start_session(interview_id, interview.candidate_id),
                container.ensure_checkpointer_alive,
            )
        except PsycopgOperationalError as exc:
            logger.error(
                "Failed to start workflow for interview %s: %s",
                interview_id,
                exc,
            )
            await _notify_transient_failure(interview_id)
            _cleanup_audio_resources(interview_id)
            _cleanup_workflow_resources(interview_id)
            return

        # Store thread ID
        thread_id = result.get("thread_id")
        workflow_threads[interview_id] = thread_id

        # Reset audio sequence for new session
        audio_sequence_numbers[interview_id] = 0

        # Generate TTS audio for first question
        question_dict = result.get("question")
        question_text = question_dict.get("text", "") if question_dict else ""
        audio_data = await _generate_tts_audio(question_text, container)

        # Format and send first question
        message = _format_question_message(
            question_dict=question_dict,
            question_id=result.get("question_id"),
            has_more=result.get("has_more"),
            audio_data=audio_data,
        )
        await manager.send_message(interview_id, message)

        logger.info(
            f"Sent {message['type']}: {result.get('question_id')}",
            extra={
                "interview_id": str(interview_id),
                "question_id": result.get("question_id"),
                "type": message["type"],
            },
        )

        logger.info(f"Workflow session started for interview {interview_id}, thread: {thread_id}")

        # Listen for answers
        while True:
            data = await websocket.receive_json()
            message_type = data.get("type")

            if message_type == "text_answer":
                answer_text = data.get("answer_text", "")

                # Process answer through workflow with guard
                try:
                    result = await execute_with_workflow_guard(
                        "process_answer",
                        lambda: workflow.process_answer(
                            thread_id=thread_id,
                            answer_text=answer_text,
                            is_voice=False,
                        ),
                        container.ensure_checkpointer_alive,
                    )
                except PsycopgOperationalError as exc:
                    logger.error(
                        "process_answer failed for interview %s: %s",
                        interview_id,
                        exc,
                    )
                    await _notify_transient_failure(interview_id)
                    break

                # Send evaluation if present
                if "evaluation" in result and result["evaluation"]:
                    evaluation = result["evaluation"]
                    await manager.send_message(
                        interview_id,
                        {
                            "type": "evaluation",
                            "answer_id": evaluation["answer_id"],
                            "score": evaluation.get("score", evaluation.get("final_score")),
                            "feedback": evaluation.get("feedback"),
                            "strengths": evaluation.get("strengths", []),
                            "weaknesses": evaluation.get("weaknesses", []),
                            "gaps": evaluation.get("gaps"),
                            "theoretical_score": evaluation.get("theoretical_score"),
                            "speaking_score": evaluation.get("speaking_score"),
                        },
                    )
                    logger.info(
                        f"Sent evaluation for answer {evaluation['answer_id']}, "
                        f"score={evaluation.get('score', evaluation.get('final_score'))}"
                    )

                # Check if complete
                if result.get("complete"):
                    await manager.send_message(
                        interview_id,
                        {
                            "type": "interview_complete",
                            "interview_id": str(interview_id),
                            "status": result.get("final_status"),
                            "detailed_feedback": result.get("summary"),
                            "feedback_url": f"/api/ai/interviews/{interview_id}/summary",
                        },
                    )

                    # Log WebSocket address (ConnectionManager also logs, but this adds handler context)
                    try:
                        client_host = websocket.client.host if websocket.client else "unknown"
                        client_port = websocket.client.port if websocket.client else "unknown"
                        ws_path = websocket.url.path if hasattr(websocket, "url") and websocket.url else "unknown"
                        ws_url = f"ws://{client_host}:{client_port}{ws_path}"
                        logger.info(
                            f"Interview {interview_id} completed - feedback sent via WebSocket to {ws_url}",
                            extra={
                                "interview_id": str(interview_id),
                                "websocket_url": ws_url,
                                "websocket_host": client_host,
                                "websocket_port": str(client_port),
                                "delivery_method": "websocket",
                                "status": result.get("final_status"),
                            },
                        )
                    except Exception as e:
                        logger.info(
                            f"Interview {interview_id} completed - feedback sent via WebSocket (address unavailable: {e})",
                            extra={
                                "interview_id": str(interview_id),
                                "delivery_method": "websocket",
                                "status": result.get("final_status"),
                            },
                        )
                    break

                # Send next question (either follow-up or main question)
                if result.get("question"):
                    question_dict = result.get("question")
                    question_text = question_dict.get("text", "") if question_dict else ""
                    audio_data = await _generate_tts_audio(question_text, container)

                    # Format message based on type
                    message = _format_question_message(
                        question_dict=question_dict,
                        question_id=result.get("question_id"),
                        has_more=result.get("has_more"),
                        audio_data=audio_data,
                    )

                    await manager.send_message(interview_id, message)

                    logger.info(
                        f"Sent {message['type']}: {result.get('question_id')}",
                        extra={
                            "interview_id": str(interview_id),
                            "question_id": result.get("question_id"),
                            "type": message["type"],
                        },
                    )

            elif message_type == "audio_chunk":
                await handle_audio_chunk(interview_id, data, container)

            else:
                await manager.send_message(
                    interview_id,
                    {
                        "type": "error",
                        "code": "UNKNOWN_MESSAGE_TYPE",
                        "message": f"Unknown message type: {message_type}",
                    },
                )


def _detect_question_type(question_dict: dict[str, Any]) -> str:
    """Detect if question is main or follow-up from workflow result.

    Args:
        question_dict: Question dictionary from workflow state

    Returns:
        "question" for main questions, "follow_up_question" for follow-ups
    """
    # Check for follow-up indicators
    if question_dict.get("question_type") == "FOLLOW_UP":
        return "follow_up_question"

    # Check for parent_question_id presence (follow-ups only)
    if "parent_question_id" in question_dict and question_dict["parent_question_id"]:
        return "follow_up_question"

    # Check for follow-up metadata fields
    if "order_in_sequence" in question_dict:
        return "follow_up_question"

    # Default: main question
    return "question"


def _format_question_message(
    question_dict: dict[str, Any],
    question_id: str,
    has_more: bool,
    audio_data: str | None,
) -> dict[str, Any]:
    """Format question message based on type (main or follow-up).

    Args:
        question_dict: Question data from workflow
        question_id: Question ID string
        has_more: Whether more questions available
        audio_data: Base64 TTS audio

    Returns:
        Formatted message dict matching legacy format
    """
    msg_type = _detect_question_type(question_dict)

    if msg_type == "follow_up_question":
        # Follow-up format (matches legacy)
        return {
            "type": "follow_up_question",
            "question_id": question_id,
            "parent_question_id": question_dict.get("parent_question_id"),
            "text": question_dict.get("text"),
            "generated_reason": question_dict.get("generated_reason"),
            "order_in_sequence": question_dict.get("order_in_sequence"),
            "audio_data": audio_data,
        }
    else:
        # Main question format (matches legacy)
        return {
            "type": "question",
            "question_id": question_id,
            "text": question_dict.get("text"),
            "question_type": question_dict.get("question_type"),
            "difficulty": question_dict.get("difficulty"),
            "index": question_dict.get("index", 0),
            "total": question_dict.get("total", 0),
            "audio_data": audio_data,
        }


async def _generate_tts_audio(
    text: str,
    container: Container,
) -> str | None:
    """Generate TTS audio and encode as base64.

    Args:
        text: Text to synthesize
        container: DI container for TTS adapter

    Returns:
        Base64-encoded audio data, or None if generation fails
    """
    try:
        import time
        start = time.perf_counter()
        tts = container.text_to_speech_port()
        audio_bytes = await tts.synthesize_speech(text)
        duration_ms = (time.perf_counter() - start) * 1000
        audio_data = base64.b64encode(audio_bytes).decode("utf-8")
        logger.info(
            f"[TIMING] tts_generation: {duration_ms:.2f}ms",
            extra={"phase": "tts_generation", "duration_ms": duration_ms, "audio_bytes": len(audio_bytes)},
        )
        logger.debug(f"Generated TTS audio: {len(audio_bytes)} bytes")
        return audio_data
    except Exception as exc:
        logger.error(f"TTS generation failed: {exc}", exc_info=True)
        return None  # Non-blocking failure


def _cleanup_audio_resources(interview_id: UUID) -> None:
    """Clean up audio streaming resources for a session.

    Args:
        interview_id: Interview UUID
    """
    # Cancel any pending transcription tasks
    if interview_id in transcription_tasks:
        task = transcription_tasks.pop(interview_id)
        if not task.done():
            task.cancel()

    # Clear audio streams
    audio_streams.pop(interview_id, None)

    # Clear sequence number
    audio_sequence_numbers.pop(interview_id, None)

    logger.debug(f"Cleaned up audio resources for interview {interview_id}")


def _cleanup_workflow_resources(interview_id: UUID) -> None:
    """Clean up workflow resources for a session.

    Args:
        interview_id: Interview UUID
    """
    # Remove workflow thread ID
    workflow_threads.pop(interview_id, None)

    logger.debug(f"Cleaned up workflow resources for interview {interview_id}")


async def _notify_transient_failure(interview_id: UUID) -> None:
    """Notify client about transient DB issues."""
    await manager.send_message(
        interview_id,
        {
            "type": "system_error",
            "code": "DB_CONNECTION",
            "action": "retry",
            "message": "Temporary database hiccup. Please retry.",
        },
    )


async def _stream_transcription(
    interview_id: UUID,
    question_id: UUID,
    container: Container,
) -> None:
    """Background task: consume audio stream and send transcriptions.

    Args:
        interview_id: Interview UUID
        question_id: Question UUID
        container: DI container
    """
    try:
        stt = container.speech_to_text_port()
        audio_queue = audio_streams[interview_id]

        # Collect chunks from queue
        chunks = []
        while True:
            chunk = await audio_queue.get()
            if chunk is None:  # End signal (sentinel value)
                break
            chunks.append(chunk)

        # Assemble complete audio
        complete_audio = b"".join(chunks)
        logger.info(
            f"Assembled {len(chunks)} chunks ({len(complete_audio)} bytes) "
            f"for interview {interview_id}"
        )

        # Upload audio to external storage (non-blocking)
        audio_storage = container.audio_storage_service()
        if audio_storage:
            seq = audio_sequence_numbers.get(interview_id, 0)
            audio_sequence_numbers[interview_id] = seq + 1
            audio_storage.schedule_upload(
                audio_data=complete_audio,
                interview_id=str(interview_id),
                sequence_number=seq,
            )
            logger.info(f"Scheduled audio upload for interview {interview_id}, seq={seq}")

        # Transcribe using batch transcription for accurate voice metrics
        # Batch transcription provides word timestamps for accurate duration/WPM calculation
        result = await stt.transcribe_audio(complete_audio, language="en-US")

        # Send final transcription to client
        await manager.send_message(
            interview_id,
            {
                "type": "transcription",
                "text": result["text"],
                "is_final": True,
                "confidence": result.get("voice_metrics", {}).get("confidence_score", 0.0),
            },
        )

        # Send voice metrics to client
        voice_metrics = result.get("voice_metrics", {})
        await manager.send_message(
            interview_id,
            {
                "type": "voice_metrics",
                **voice_metrics,
                "real_time": False,
            },
        )

        logger.info(f"Sent transcription and voice metrics for interview {interview_id}")

        # Route voice answer to workflow
        thread_id = workflow_threads.get(interview_id)
        if thread_id:
            logger.info(
                f"Processing voice answer via workflow: '{result['text']}' "
                f"(interview {interview_id}, question {question_id})"
            )
            async with session_scope() as session:
                workflow = await container.create_interview_conversation_workflow(session=session)
                workflow_result = await workflow.process_answer(
                    thread_id=thread_id,
                    answer_text=result["text"],
                    is_voice=True,
                    voice_metrics=result.get("voice_metrics", {}),
                )

                # Send evaluation if present
                if "evaluation" in workflow_result and workflow_result["evaluation"]:
                    evaluation = workflow_result["evaluation"]
                    await manager.send_message(
                        interview_id,
                        {
                            "type": "evaluation",
                            "answer_id": evaluation["answer_id"],
                            "score": evaluation.get("score", evaluation.get("final_score")),
                            "feedback": evaluation.get("feedback"),
                            "strengths": evaluation.get("strengths", []),
                            "weaknesses": evaluation.get("weaknesses", []),
                            "gaps": evaluation.get("gaps"),
                            "theoretical_score": evaluation.get("theoretical_score"),
                            "speaking_score": evaluation.get("speaking_score"),
                        },
                    )
                    logger.info(
                        f"Sent evaluation for voice answer {evaluation['answer_id']}, "
                        f"score={evaluation.get('score', evaluation.get('final_score'))}"
                    )

                # Check if complete
                if workflow_result.get("complete"):
                    # Get WebSocket client address for logging
                    # Note: websocket is not directly available here, but ConnectionManager will log it
                    await manager.send_message(
                        interview_id,
                        {
                            "type": "interview_complete",
                            "interview_id": str(interview_id),
                            "status": workflow_result.get("final_status"),
                            "detailed_feedback": workflow_result.get("summary"),
                            "feedback_url": f"/api/ai/interviews/{interview_id}/summary",
                        },
                    )

                    logger.info(
                        f"Interview {interview_id} completed (voice answer) - feedback sent via WebSocket",
                        extra={
                            "interview_id": str(interview_id),
                            "delivery_method": "websocket",
                            "answer_type": "voice",
                            "status": workflow_result.get("final_status"),
                        },
                    )
                    return

                # Send next question (either follow-up or main question)
                if workflow_result.get("question"):
                    question_dict = workflow_result.get("question")
                    question_text = question_dict.get("text", "") if question_dict else ""
                    audio_data = await _generate_tts_audio(question_text, container)

                    # Format message based on type
                    message = _format_question_message(
                        question_dict=question_dict,
                        question_id=workflow_result.get("question_id"),
                        has_more=workflow_result.get("has_more"),
                        audio_data=audio_data,
                    )

                    await manager.send_message(interview_id, message)

                    logger.info(
                        f"Sent {message['type']}: {workflow_result.get('question_id')}",
                        extra={
                            "interview_id": str(interview_id),
                            "question_id": workflow_result.get("question_id"),
                            "type": message["type"],
                        },
                    )
                return
        else:
            logger.warning(
                f"No workflow thread found for interview {interview_id} - "
                f"cannot process voice answer"
            )

    except Exception as e:
        logger.error(
            f"Error in transcription stream for interview {interview_id}: {e}",
            exc_info=True,
        )
        await manager.send_message(
            interview_id,
            {
                "type": "error",
                "code": "TRANSCRIPTION_ERROR",
                "message": f"Failed to transcribe audio: {str(e)}",
            },
        )


async def handle_audio_chunk(interview_id: UUID, data: dict[str, Any], container: Container) -> None:
    """Handle audio chunk from client with real-time streaming STT.

    Implements real-time audio streaming:
    1. First chunk: Initialize audio queue and background transcription task
    2. Intermediate chunks: Add to queue for streaming processing
    3. Final chunk: Signal end of stream, wait for transcription completion

    Args:
        interview_id: Interview UUID
        data: Message data with audio chunk (audio_data, chunk_index, is_final, question_id)
        container: DI container
    """
    try:
        # Extract message fields
        audio_data_b64 = data.get("audio_data")
        chunk_index = data.get("chunk_index", 0)
        is_final = data.get("is_final", False)
        question_id_str = data.get("question_id")

        if not audio_data_b64:
            logger.error(f"Audio chunk missing audio_data for interview {interview_id}")
            await manager.send_message(
                interview_id,
                {
                    "type": "error",
                    "code": "INVALID_AUDIO_CHUNK",
                    "message": "Missing audio_data field",
                },
            )
            return

        if not question_id_str:
            logger.error(f"Audio chunk missing question_id for interview {interview_id}")
            await manager.send_message(
                interview_id,
                {
                    "type": "error",
                    "code": "INVALID_AUDIO_CHUNK",
                    "message": "Missing question_id field",
                },
            )
            return

        question_id = UUID(question_id_str)

        # Decode audio chunk from base64
        try:
            audio_chunk = base64.b64decode(audio_data_b64)
        except Exception as e:
            logger.error(f"Failed to decode audio chunk: {e}")
            await manager.send_message(
                interview_id,
                {
                    "type": "error",
                    "code": "INVALID_AUDIO_DATA",
                    "message": "Failed to decode base64 audio data",
                },
            )
            return

        # Initialize streaming on first chunk
        if interview_id not in audio_streams:
            logger.info(
                f"Initializing audio stream for interview {interview_id}, "
                f"question {question_id}"
            )
            audio_streams[interview_id] = Queue()

            # Start background transcription task
            task = asyncio.create_task(_stream_transcription(interview_id, question_id, container))
            transcription_tasks[interview_id] = task

        # Feed chunk to stream
        await audio_streams[interview_id].put(audio_chunk)
        logger.debug(f"Added audio chunk {chunk_index} to stream for interview {interview_id}")

        if is_final:
            logger.info(
                f"Received final audio chunk for interview {interview_id}, "
                f"signaling end of stream"
            )
            # Signal end of stream
            await audio_streams[interview_id].put(None)  # sentinel value

            # Wait for transcription to complete
            await transcription_tasks[interview_id]

            # Cleanup
            audio_streams.pop(interview_id, None)
            transcription_tasks.pop(interview_id, None)
            logger.info(f"Audio stream completed for interview {interview_id}")

    except Exception as e:
        logger.error(
            f"Error handling audio chunk for interview {interview_id}: {e}",
            exc_info=True,
        )
        await manager.send_message(
            interview_id,
            {
                "type": "error",
                "code": "AUDIO_PROCESSING_ERROR",
                "message": f"Failed to process audio chunk: {str(e)}",
            },
        )
