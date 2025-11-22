"""WebSocket test client for automated interview testing."""

import asyncio
import base64
import json
import logging
from datetime import datetime
from typing import Any
from uuid import UUID

import websockets
from websockets.exceptions import ConnectionClosed

logger = logging.getLogger(__name__)


class InterviewTestBot:
    """Automated test client for interview WebSocket sessions.

    Simulates candidate-side interactions: connect, receive questions,
    send answers, track state, handle errors.

    Usage:
        bot = InterviewTestBot(interview_id=uuid4())
        await bot.connect(ws_url="ws://localhost:8000/ws/interviews/{id}")
        question = await bot.wait_for_question()
        await bot.send_text_answer(question_id, "My answer")
        await bot.disconnect()
    """

    def __init__(
        self,
        interview_id: UUID,
        timeout: float = 30.0,
        enable_metrics: bool = True,
    ):
        """Initialize test bot.

        Args:
            interview_id: Interview UUID
            timeout: Default timeout for operations (seconds)
            enable_metrics: Track latency/state metrics
        """
        self.interview_id = interview_id
        self.timeout = timeout
        self.enable_metrics = enable_metrics

        # Connection state
        self.ws: websockets.WebSocketClientProtocol | None = None
        self.connected = False

        # Interview state
        self.current_status: str = "IDLE"
        self.current_question_id: UUID | None = None
        self.current_question_text: str | None = None
        self.questions_received = 0
        self.answers_sent = 0
        self.evaluations_received = 0
        self.follow_ups_received = 0

        # Metrics
        self.metrics = {
            "latency": {},  # msg_type → [latency_ms]
            "states": [],  # [(timestamp, state)]
            "errors": [],  # [(timestamp, error_code, message)]
        }

        # Message buffer (for async message handling)
        self._message_queue: asyncio.Queue = asyncio.Queue()
        self._receive_task: asyncio.Task | None = None

    async def connect(self, ws_url: str) -> None:
        """Connect to WebSocket server.

        Args:
            ws_url: WebSocket URL (e.g., ws://localhost:8000/ws/interviews/{id})

        Raises:
            ConnectionError: If connection fails
        """
        try:
            logger.info(f"Connecting to {ws_url}")
            start = datetime.utcnow()

            self.ws = await websockets.connect(
                ws_url,
                max_size=10 * 1024 * 1024,  # 10MB max message size
                ping_interval=20,  # Keep-alive ping every 20s
                ping_timeout=10,  # Timeout after 10s
            )

            self.connected = True
            latency = (datetime.utcnow() - start).total_seconds() * 1000
            self._track_metric("latency", "connect", latency)
            logger.info(f"Connected in {latency:.1f}ms")

            # Start background task to receive messages
            self._receive_task = asyncio.create_task(self._receive_loop())

        except Exception as e:
            logger.error(f"Connection failed: {e}")
            raise ConnectionError(f"Failed to connect to {ws_url}: {e}")

    async def disconnect(self) -> None:
        """Disconnect from WebSocket server."""
        if self._receive_task and not self._receive_task.done():
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass

        if self.ws:
            await self.ws.close()
            self.connected = False
            logger.info("Disconnected")

    async def send_text_answer(
        self,
        question_id: UUID,
        answer_text: str,
    ) -> None:
        """Send text answer for a question.

        Args:
            question_id: Question UUID
            answer_text: Answer text content

        Raises:
            ValueError: If not connected or answer is empty
        """
        if not self.connected or not self.ws:
            raise ValueError("Not connected to WebSocket")

        if not answer_text.strip():
            raise ValueError("Answer text cannot be empty")

        message = {
            "type": "text_answer",
            "question_id": str(question_id),
            "answer_text": answer_text,
        }

        start = datetime.utcnow()
        await self.ws.send(json.dumps(message))
        latency = (datetime.utcnow() - start).total_seconds() * 1000

        self.answers_sent += 1
        self._track_metric("latency", "send_answer", latency)
        logger.info(f"Sent answer (question={question_id}, len={len(answer_text)})")

    async def send_audio_chunk(
        self,
        question_id: UUID,
        audio_data: bytes,
        chunk_index: int,
        is_final: bool,
        audio_format: str = "webm",
    ) -> None:
        """Send audio chunk for voice answer.

        Args:
            question_id: Question UUID
            audio_data: Raw audio bytes
            chunk_index: Sequential chunk number
            is_final: Whether this is the last chunk
            audio_format: Audio format (webm, wav, mp3)
        """
        if not self.connected or not self.ws:
            raise ValueError("Not connected to WebSocket")

        encoded_audio = base64.b64encode(audio_data).decode("utf-8")

        message = {
            "type": "audio_chunk",
            "question_id": str(question_id),
            "audio_data": encoded_audio,
            "chunk_index": chunk_index,
            "is_final": is_final,
            "format": audio_format,
        }

        await self.ws.send(json.dumps(message))
        logger.info(
            f"Sent audio chunk (question={question_id}, "
            f"chunk={chunk_index}, final={is_final})"
        )

    async def wait_for_question(
        self,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Wait for question message from server.

        Args:
            timeout: Timeout in seconds (default: self.timeout)

        Returns:
            Question message dict

        Raises:
            TimeoutError: If timeout exceeded
            ValueError: If unexpected message type received
        """
        timeout = timeout or self.timeout
        message = await self._wait_for_message_type("question", timeout)

        # Update state
        self.current_question_id = UUID(message["question_id"])
        self.current_question_text = message["text"]
        self.current_status = "QUESTIONING"
        self.questions_received += 1
        self._track_state("QUESTIONING")

        logger.info(
            f"Received question #{message['index']}/{message['total']}: "
            f"{message['text'][:80]}..."
        )

        return message

    async def wait_for_evaluation(
        self,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Wait for evaluation message from server.

        Args:
            timeout: Timeout in seconds

        Returns:
            Evaluation message dict
        """
        timeout = timeout or self.timeout
        message = await self._wait_for_message_type("evaluation", timeout)

        # Update state
        self.current_status = "EVALUATING"
        self.evaluations_received += 1
        self._track_state("EVALUATING")

        logger.info(
            f"Received evaluation (score={message['score']:.1f}, "
            f"strengths={len(message.get('strengths', []))})"
        )

        return message

    async def wait_for_follow_up(
        self,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Wait for follow-up question message.

        Args:
            timeout: Timeout in seconds

        Returns:
            Follow-up question message dict
        """
        timeout = timeout or self.timeout
        message = await self._wait_for_message_type("follow_up_question", timeout)

        # Update state
        self.current_question_id = UUID(message["question_id"])
        self.current_question_text = message["text"]
        self.current_status = "FOLLOW_UP"
        self.follow_ups_received += 1
        self._track_state("FOLLOW_UP")

        logger.info(
            f"Received follow-up #{message['order_in_sequence']}: "
            f"{message['text'][:80]}..."
        )

        return message

    async def wait_for_completion(
        self,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Wait for interview completion message.

        Args:
            timeout: Timeout in seconds

        Returns:
            Completion message dict
        """
        timeout = timeout or self.timeout
        message = await self._wait_for_message_type("interview_complete", timeout)

        # Update state
        self.current_status = "COMPLETE"
        self._track_state("COMPLETE")

        logger.info(
            f"Interview complete (score={message['overall_score']:.1f}, "
            f"questions={message['total_questions']})"
        )

        return message

    async def wait_for_error(
        self,
        timeout: float = 5.0,
    ) -> dict[str, Any]:
        """Wait for error message (used in error test scenarios).

        Args:
            timeout: Short timeout (errors should arrive quickly)

        Returns:
            Error message dict
        """
        message = await self._wait_for_message_type("error", timeout)
        self._track_error(message["code"], message["message"])
        return message

    async def wait_for_next_question(
        self,
        timeout: float | None = None,
    ) -> tuple[str, dict[str, Any] | None]:
        """Wait for any question type (regular question or follow-up) or completion.

        This method accepts 'question', 'follow_up_question', and 'interview_complete'
        message types, making it suitable for QA loops that need to handle the full
        interview flow without cascading timeouts.

        Args:
            timeout: Timeout in seconds (defaults to self.timeout)

        Returns:
            Tuple of (message_type, message_dict) where:
            - message_type is "question", "follow_up", or "complete"
            - message_dict is None if message_type is "complete"

        Raises:
            TimeoutError: If timeout exceeded
            ValueError: If message is not question, follow-up, or completion
        """
        timeout = timeout or self.timeout
        start = datetime.utcnow()

        try:
            # Wait for message from queue
            message = await asyncio.wait_for(
                self._message_queue.get(), timeout=timeout
            )

            msg_type = message.get("type")

            # Accept question types
            if msg_type == "question":
                self.questions_received += 1
                self.current_question_id = UUID(message["question_id"])
                self.current_question_text = message["text"]

                logger.info(
                    f"Received question #{self.questions_received - 1}/"
                    f"{message.get('total_questions', '?')}: {message['text'][:50]}..."
                )

                # Track latency
                latency = (datetime.utcnow() - start).total_seconds() * 1000
                self._track_metric("latency", "wait_question", latency)

                return "question", message

            elif msg_type == "follow_up_question":
                self.follow_ups_received += 1
                self.current_question_id = UUID(message["question_id"])
                self.current_question_text = message["text"]

                logger.info(
                    f"Received follow-up #{self.follow_ups_received}: "
                    f"{message['text'][:50]}..."
                )

                # Track latency
                latency = (datetime.utcnow() - start).total_seconds() * 1000
                self._track_metric("latency", "wait_follow_up", latency)

                return "follow_up", message

            elif msg_type == "interview_complete":
                logger.info("Interview completed")

                # Track latency
                latency = (datetime.utcnow() - start).total_seconds() * 1000
                self._track_metric("latency", "wait_completion", latency)

                return "complete", message

            else:
                raise ValueError(
                    f"Expected 'question', 'follow_up_question', or 'interview_complete', "
                    f"got '{msg_type}'"
                )

        except asyncio.TimeoutError:
            raise TimeoutError(
                f"Timeout waiting for next question (waited {timeout}s)"
            )

    async def _wait_for_message_types(
        self,
        msg_types: list[str],
        timeout: float,
    ) -> dict[str, Any]:
        """Wait for any of multiple message types from queue.

        Args:
            msg_types: List of acceptable message types
            timeout: Timeout in seconds

        Returns:
            Message dict

        Raises:
            TimeoutError: If timeout exceeded
            ValueError: If message type not in expected types
        """
        start = datetime.utcnow()

        try:
            # Wait for message from queue
            message = await asyncio.wait_for(
                self._message_queue.get(), timeout=timeout
            )

            # Verify type is one of expected
            msg_type = message.get("type")
            if msg_type not in msg_types:
                raise ValueError(
                    f"Expected message type in {msg_types}, got '{msg_type}'"
                )

            # Track latency
            latency = (datetime.utcnow() - start).total_seconds() * 1000
            self._track_metric("latency", f"wait_any_{msg_type}", latency)

            return message

        except asyncio.TimeoutError:
            raise TimeoutError(
                f"Timeout waiting for any of {msg_types} (waited {timeout}s)"
            )

    async def _wait_for_message_type(
        self,
        msg_type: str,
        timeout: float,
    ) -> dict[str, Any]:
        """Wait for specific message type from queue.

        Args:
            msg_type: Expected message type
            timeout: Timeout in seconds

        Returns:
            Message dict

        Raises:
            TimeoutError: If timeout exceeded
            ValueError: If unexpected message type
        """
        start = datetime.utcnow()

        try:
            # Wait for message from queue
            message = await asyncio.wait_for(
                self._message_queue.get(), timeout=timeout
            )

            # Verify type
            if message.get("type") != msg_type:
                raise ValueError(
                    f"Expected message type '{msg_type}', "
                    f"got '{message.get('type')}'"
                )

            # Track latency
            latency = (datetime.utcnow() - start).total_seconds() * 1000
            self._track_metric("latency", f"wait_{msg_type}", latency)

            return message

        except asyncio.TimeoutError:
            raise TimeoutError(
                f"Timeout waiting for '{msg_type}' message " f"(waited {timeout}s)"
            )

    async def _receive_loop(self) -> None:
        """Background task to receive messages and queue them."""
        try:
            while self.connected and self.ws:
                try:
                    raw_message = await self.ws.recv()
                    message = json.loads(raw_message)

                    # Queue message for processing
                    await self._message_queue.put(message)

                    logger.debug(f"Received: {message.get('type')}")

                except ConnectionClosed:
                    logger.warning("Connection closed by server")
                    self.connected = False
                    break
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON received: {e}")
                    continue

        except asyncio.CancelledError:
            logger.debug("Receive loop cancelled")
        except Exception as e:
            logger.error(f"Error in receive loop: {e}")
            self.connected = False

    def _track_metric(
        self,
        metric_type: str,
        key: str,
        value: float,
    ) -> None:
        """Track metric (latency, state, etc.)."""
        if not self.enable_metrics:
            return

        if metric_type == "latency":
            if key not in self.metrics["latency"]:
                self.metrics["latency"][key] = []
            self.metrics["latency"][key].append(value)

    def _track_state(self, state: str) -> None:
        """Track state transition."""
        if not self.enable_metrics:
            return

        self.metrics["states"].append((datetime.utcnow(), state))

    def _track_error(self, code: str, message: str) -> None:
        """Track error."""
        if not self.enable_metrics:
            return

        self.metrics["errors"].append((datetime.utcnow(), code, message))

    def get_metrics(self) -> dict[str, Any]:
        """Get collected metrics.

        Returns:
            Metrics dict with latency, states, errors
        """
        return {
            "latency": {
                key: {
                    "count": len(values),
                    "avg": sum(values) / len(values) if values else 0,
                    "min": min(values) if values else 0,
                    "max": max(values) if values else 0,
                }
                for key, values in self.metrics["latency"].items()
            },
            "states": [
                {"timestamp": ts.isoformat(), "state": state}
                for ts, state in self.metrics["states"]
            ],
            "errors": [
                {"timestamp": ts.isoformat(), "code": code, "message": msg}
                for ts, code, msg in self.metrics["errors"]
            ],
            "summary": {
                "questions_received": self.questions_received,
                "answers_sent": self.answers_sent,
                "evaluations_received": self.evaluations_received,
                "follow_ups_received": self.follow_ups_received,
            },
        }

    def get_state(self) -> dict[str, Any]:
        """Get current bot state.

        Returns:
            State dict
        """
        return {
            "interview_id": str(self.interview_id),
            "connected": self.connected,
            "current_status": self.current_status,
            "current_question_id": (
                str(self.current_question_id) if self.current_question_id else None
            ),
            "questions_received": self.questions_received,
            "answers_sent": self.answers_sent,
        }
