# Phase 1: WebSocket Test Client Implementation

**Duration**: 2 days
**Deliverable**: `InterviewTestBot` class with full WebSocket lifecycle management

---

## Overview

Build async WebSocket client simulating candidate-side interview interactions. Client connects to server, receives questions, sends answers, tracks state, handles errors, collects metrics.

---

## File Structure

```
tests/bot/
├── __init__.py
├── test_bot_client.py              # InterviewTestBot class (main implementation)
├── websocket_types.py              # Type definitions for messages
└── test_bot_client_test.py         # Unit tests for bot
```

---

## Implementation Details

### 1. Core Client Class

**File**: `tests/bot/test_bot_client.py`

```python
"""WebSocket test client for automated interview testing."""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

import websockets
from websockets.exceptions import ConnectionClosed, WebSocketException

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
            "latency": {},      # msg_type → [latency_ms]
            "states": [],       # [(timestamp, state)]
            "errors": [],       # [(timestamp, error_code, message)]
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
                ping_interval=20,            # Keep-alive ping every 20s
                ping_timeout=10,             # Timeout after 10s
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

        import base64
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
                self._message_queue.get(),
                timeout=timeout
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
                f"Timeout waiting for '{msg_type}' message "
                f"(waited {timeout}s)"
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
```

---

## 2. Unit Tests

**File**: `tests/bot/test_bot_client_test.py`

```python
"""Unit tests for InterviewTestBot."""

import asyncio
import json
from uuid import uuid4

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from .test_bot_client import InterviewTestBot


@pytest_asyncio.fixture
async def mock_websocket():
    """Mock WebSocket connection."""
    ws = AsyncMock()
    ws.recv = AsyncMock()
    ws.send = AsyncMock()
    ws.close = AsyncMock()
    return ws


@pytest.mark.asyncio
async def test_bot_init():
    """Test bot initialization."""
    interview_id = uuid4()
    bot = InterviewTestBot(interview_id=interview_id, timeout=10.0)

    assert bot.interview_id == interview_id
    assert bot.timeout == 10.0
    assert not bot.connected
    assert bot.questions_received == 0
    assert bot.answers_sent == 0


@pytest.mark.asyncio
async def test_connect_success(mock_websocket):
    """Test successful WebSocket connection."""
    interview_id = uuid4()
    bot = InterviewTestBot(interview_id=interview_id)

    with patch("websockets.connect", return_value=mock_websocket):
        await bot.connect(f"ws://localhost:8000/ws/interviews/{interview_id}")

        assert bot.connected
        assert bot.ws is not None
        assert "connect" in bot.metrics["latency"]


@pytest.mark.asyncio
async def test_send_text_answer(mock_websocket):
    """Test sending text answer."""
    interview_id = uuid4()
    question_id = uuid4()
    bot = InterviewTestBot(interview_id=interview_id)

    # Mock connection
    bot.ws = mock_websocket
    bot.connected = True

    await bot.send_text_answer(question_id, "My answer text")

    # Verify message sent
    mock_websocket.send.assert_called_once()
    sent_data = json.loads(mock_websocket.send.call_args[0][0])

    assert sent_data["type"] == "text_answer"
    assert sent_data["question_id"] == str(question_id)
    assert sent_data["answer_text"] == "My answer text"
    assert bot.answers_sent == 1


@pytest.mark.asyncio
async def test_send_text_answer_not_connected():
    """Test sending answer when not connected raises error."""
    bot = InterviewTestBot(interview_id=uuid4())

    with pytest.raises(ValueError, match="Not connected"):
        await bot.send_text_answer(uuid4(), "Answer")


@pytest.mark.asyncio
async def test_wait_for_question(mock_websocket):
    """Test waiting for question message."""
    interview_id = uuid4()
    question_id = uuid4()
    bot = InterviewTestBot(interview_id=interview_id)

    # Mock WebSocket to return question message
    question_msg = {
        "type": "question",
        "question_id": str(question_id),
        "text": "What is Python?",
        "question_type": "TECHNICAL",
        "difficulty": "EASY",
        "index": 1,
        "total": 3,
    }

    # Queue message
    await bot._message_queue.put(question_msg)

    # Wait for question
    result = await bot.wait_for_question(timeout=1.0)

    assert result["type"] == "question"
    assert result["question_id"] == str(question_id)
    assert bot.current_question_id == question_id
    assert bot.current_status == "QUESTIONING"
    assert bot.questions_received == 1


@pytest.mark.asyncio
async def test_wait_for_question_timeout():
    """Test timeout when waiting for question."""
    bot = InterviewTestBot(interview_id=uuid4())

    with pytest.raises(TimeoutError, match="Timeout waiting"):
        await bot.wait_for_question(timeout=0.1)


@pytest.mark.asyncio
async def test_metrics_collection():
    """Test metrics collection."""
    bot = InterviewTestBot(interview_id=uuid4(), enable_metrics=True)

    # Track some metrics
    bot._track_metric("latency", "test_op", 100.5)
    bot._track_metric("latency", "test_op", 120.3)
    bot._track_state("QUESTIONING")
    bot._track_error("TEST_ERROR", "Test error message")

    metrics = bot.get_metrics()

    assert "latency" in metrics
    assert "test_op" in metrics["latency"]
    assert metrics["latency"]["test_op"]["count"] == 2
    assert metrics["latency"]["test_op"]["avg"] == pytest.approx(110.4)

    assert len(metrics["states"]) == 1
    assert metrics["states"][0]["state"] == "QUESTIONING"

    assert len(metrics["errors"]) == 1
    assert metrics["errors"][0]["code"] == "TEST_ERROR"


@pytest.mark.asyncio
async def test_get_state():
    """Test get_state returns current bot state."""
    interview_id = uuid4()
    bot = InterviewTestBot(interview_id=interview_id)

    state = bot.get_state()

    assert state["interview_id"] == str(interview_id)
    assert not state["connected"]
    assert state["current_status"] == "IDLE"
    assert state["questions_received"] == 0
```

---

## 3. Integration Test (Manual)

**File**: `tests/bot/manual_integration_test.py` (for manual testing only)

```python
"""Manual integration test for InterviewTestBot.

Run this manually to test against real server:
    python -m tests.bot.manual_integration_test
"""

import asyncio
import os
from uuid import uuid4

from .test_bot_client import InterviewTestBot


async def main():
    """Manual test against local server."""
    # Prerequisites:
    # 1. Server running at localhost:8000
    # 2. Interview created via API
    # 3. CV uploaded and planned

    interview_id = uuid4()  # Replace with real interview ID
    ws_url = f"ws://localhost:8000/ws/interviews/{interview_id}"

    bot = InterviewTestBot(interview_id=interview_id)

    try:
        # Connect
        print(f"Connecting to {ws_url}...")
        await bot.connect(ws_url)
        print("Connected!")

        # Wait for first question
        print("Waiting for question...")
        question = await bot.wait_for_question()
        print(f"Q: {question['text']}")

        # Send answer
        answer = "Python is a high-level programming language."
        print(f"A: {answer}")
        await bot.send_text_answer(
            question_id=uuid4(question["question_id"]),
            answer_text=answer
        )

        # Wait for evaluation
        print("Waiting for evaluation...")
        evaluation = await bot.wait_for_evaluation()
        print(f"Score: {evaluation['score']:.1f}")

        # Continue until complete...
        # (Add more question/answer cycles as needed)

    finally:
        await bot.disconnect()
        print("\nMetrics:")
        print(bot.get_metrics())


if __name__ == "__main__":
    asyncio.run(main())
```

---

## Testing Strategy

### Unit Tests
- ✅ Bot initialization
- ✅ Connect success/failure
- ✅ Send text answer (valid/invalid)
- ✅ Wait for question (success/timeout)
- ✅ Wait for evaluation
- ✅ Wait for follow-up
- ✅ Wait for completion
- ✅ Metrics collection
- ✅ State tracking

### Integration Tests (Phase 3)
- Connect to real server
- Full interview flow (3 questions)
- Error handling (invalid message, timeout)
- Reconnect logic

---

## Acceptance Criteria

- [ ] `InterviewTestBot` class implemented with all methods
- [ ] Async/await patterns followed (no blocking operations)
- [ ] Unit tests pass (>90% coverage)
- [ ] Metrics collection working (latency, states, errors)
- [ ] Error handling comprehensive (timeout, connection drop, invalid message)
- [ ] Logging clear and informative
- [ ] Type hints complete
- [ ] Docstrings for all public methods
- [ ] Manual integration test successful (against local server)

---

## Unresolved Questions

1. **WebSocket Reconnect Logic**: Should bot auto-reconnect on connection drop?
   - **Decision**: No for MVP (fail fast), add in v2 if needed

2. **Message Ordering**: Can messages arrive out-of-order?
   - **Assumption**: No, WebSocket guarantees order (TCP)
   - **Mitigation**: Add sequence number validation if issues arise

3. **Large Message Handling**: Max message size?
   - **Current**: 10MB limit in client config
   - **Server**: Check server WebSocket config

4. **Ping/Pong Keep-Alive**: Required?
   - **Current**: Enabled (20s interval, 10s timeout)
   - **Reason**: Prevent idle connection timeout

---

## Dependencies

**Python Packages**:
- `websockets>=12.0` - WebSocket client
- `pytest>=7.4.0` - Testing
- `pytest-asyncio>=0.21.0` - Async test support
- `pytest-mock>=3.12.0` - Mocking utilities

**Install**:
```bash
pip install websockets pytest pytest-asyncio pytest-mock
```

---

## Timeline

**Day 1**:
- AM: Implement `InterviewTestBot` core methods (connect, send, wait)
- PM: Implement metrics collection + state tracking

**Day 2**:
- AM: Write unit tests (9+ tests)
- PM: Manual integration test + refinement
