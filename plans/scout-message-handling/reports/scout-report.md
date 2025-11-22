# Test Bot Message Handling Architecture Scout Report

## Executive Summary

Completed comprehensive codebase scout of the test bot message handling architecture. Discovered complete WebSocket message flow from server to test client, identified all message types, message queue implementation, current wait methods, and cascading timeout issues in the QA loop logic.

## MESSAGE FLOW: Server → WebSocket → Bot → Test Runner

Server (session_orchestrator.py) → ConnectionManager → InterviewTestBot._receive_loop()
→ Message Queue (asyncio.Queue) → InterviewTestBot.wait_for_X() → TestRunner._run_websocket_qa()

## MESSAGE TYPES (websocket_dto.py:1-168)

CLIENT → SERVER:
- text_answer (22-27): {type, question_id, answer_text}
- audio_chunk (30-50): {type, audio_data, chunk_index, is_final, format, question_id}
- get_next_question (53-56): DEPRECATED
- request_retry (59-64): {type, failed_message_type, error_code}

SERVER → CLIENT:
- question (72-83): Main question with audio
- follow_up_question (86-96): Follow-up probe
- evaluation (99-124): Answer assessment
- voice_metrics (127-135): Voice quality
- transcription (138-144): STT result
- interview_complete (147-154): End of interview
- error (157-167): Error response

## MESSAGE QUEUE (test_bot_client.py:69)

Type: asyncio.Queue (FIFO, unbounded)
Reception: _receive_loop() at lines 364-389
- Background task (spawned at connect(), line 98)
- Receives: await ws.recv() → json.loads() → queue.put()
- Cleanup: disconnect() cancels task (lines 106-111)

## WAIT METHODS (test_bot_client.py:320-362)

Base: _wait_for_message_type(msg_type, timeout)
- Dequeue with timeout: asyncio.wait_for(queue.get(), timeout)
- Validate type: if message.get('type') != msg_type: raise ValueError
- Return message dict

Specialized (all use base method):
- wait_for_question() → 'question' (189-220)
- wait_for_evaluation() → 'evaluation' (222-247)
- wait_for_follow_up() → 'follow_up_question' (249-276)
- wait_for_completion() → 'interview_complete' (278-302)
- wait_for_error() → 'error', 5s timeout (304-318)

## TIMEOUT CONFIGURATION (config.py:95-117)

- question_timeout_sec: 5.0
- follow_up_timeout_sec: 5.0
- completion_timeout_sec: 5.0
- evaluation_timeout_sec: 10.0 (longest)
- interview_timeout_sec: 30.0 (overall)

## CRITICAL ISSUE: CASCADING TIMEOUTS (test_runner.py:400-421)

for i in range(expected_questions + buffer):
  try:
    message = await bot.wait_for_question(5s)
  except TimeoutError:
    try:
      message = await bot.wait_for_follow_up(5s)
    except TimeoutError:
      try:
        completion = await bot.wait_for_completion(5s)
        break
      except TimeoutError:
        break

PROBLEMS:
1. Total wait time if all timeout: 15 seconds
2. No state sync with server - bot doesn't know which message is coming
3. Cannot distinguish: delayed vs error vs network issue
4. Evaluation wait (10s at line 446-448) has NO FALLBACK
5. If cascades consumed time, evaluation will timeout and test fails
6. No retry logic

## SERVER-SIDE MESSAGE SENDING (session_orchestrator.py)

start_session() (75-137): sends 'question'
handle_answer() (139-168): routes based on state
_send_evaluation() (667-684): sends 'evaluation'
_send_next_main_question() (539-612): sends 'question'
_generate_and_send_followup() (450-537): sends 'follow_up_question'
_complete_interview() (614-665): sends 'interview_complete'
_send_error() (696-709): sends 'error'

All use: manager.send_message() → websocket.send_json()
Manager: connection_manager.py lines 39-48

## KEY FILE LOCATIONS

Test Bot Client:
- tests/bot/test_bot_client.py (17-468)
  - Message queue: 69
  - _receive_loop: 364-389
  - _wait_for_message_type: 320-362
  - wait_for_* methods: 189-318

Test Runner QA Loop:
- tests/bot/test_runner.py (352-462)
  - Cascading timeout logic: 400-421 ← CRITICAL
  - Evaluation wait: 446-448

Server WebSocket:
- interview_handler.py: 23-116
- connection_manager.py: 39-48
- session_orchestrator.py: 38-957

Message Definitions:
- src/application/dto/websocket_dto.py: 1-168

Configuration:
- tests/bot/config.py: 95-133

## IDENTIFIED ISSUES

Critical:
- Cascading Timeout Logic (test_runner.py:400-421): 15s wasted, no state sync
- Evaluation No Fallback (test_runner.py:446-448): Will timeout if cascades consume time
- Message Ordering Assumptions: No out-of-order handling

Design Limitations:
- Strict Type Validation: ValueError on unexpected type, no filtering
- No Retry Logic: Timeout = test failure
- Global Timeouts: No adaptive based on LLM latency

## RECOMMENDED FIXES

Option 1 (RECOMMENDED): Message Type Filtering
- Accept list of expected types in _wait_for_message_type()
- Drain queue until finding expected type
- Buffer unexpected messages for later

Option 2: State-Aware Waiting
- Query server state before waiting
- Only expect messages state machine allows

Option 3: Timeout Aggregation
- Calculate time budget per iteration
- Distribute timeout across waits
- Fail immediately if budget exceeded

Option 4: Message Buffering
- Implement message buffer keyed by type
- Check buffer before queue.get()

## UNRESOLVED QUESTIONS

1. Message Loss Detection: How detect if server-sent message was dropped?
2. Server Latency: Should timeout account for LLM processing time?
3. Out-of-Order: Can server send follow_up before evaluation?
4. Cascade Intent: Exit immediately on timeout or try alternatives?
5. Buffer Size: Why qa_loop_buffer=10?

---
Scout Complete: All message types, timeouts, wait methods, and cascading issues mapped with line numbers.
