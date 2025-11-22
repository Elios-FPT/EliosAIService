# Architecture Diagram: Cascading Timeout Fix

## System Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                          WebSocket Server                             │
│                                                                       │
│  Interview State Machine:                                            │
│  ┌─────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐             │
│  │PLANNING │→│QUESTIONING│→│EVALUATING│→│ COMPLETE │             │
│  └─────────┘  └──────────┘  └──────────┘  └──────────┘             │
│                     ↓             ↓                                   │
│                 question      evaluation                             │
│                 follow_up                                             │
└──────────────────────────────────────────────────────────────────────┘
                                  │
                                  │ WebSocket Messages
                                  ▼
┌──────────────────────────────────────────────────────────────────────┐
│                     InterviewTestBot (Client)                         │
│                                                                       │
│  ┌────────────────────────────────────────────────────────────┐     │
│  │ _receive_loop() [Background Task]                          │     │
│  │                                                             │     │
│  │  while connected:                                          │     │
│  │    raw_message = await ws.recv()                           │     │
│  │    message = json.loads(raw_message)                       │     │
│  │    await message_queue.put(message)  ← FIFO Queue         │     │
│  └────────────────────────────────────────────────────────────┘     │
│                                                                       │
│  ┌────────────────────────────────────────────────────────────┐     │
│  │ Message Queue (asyncio.Queue, unbounded)                   │     │
│  │                                                             │     │
│  │  [question] → [evaluation] → [follow_up] → [evaluation]... │     │
│  └────────────────────────────────────────────────────────────┘     │
│                               ▲                                       │
│                               │                                       │
│  ┌────────────────────────────┴───────────────────────────────┐     │
│  │ BEFORE: _wait_for_message_type(msg_type, timeout)          │     │
│  │                                                             │     │
│  │  message = await queue.get()  # timeout=5s                 │     │
│  │  if message["type"] != msg_type:                           │     │
│  │    raise ValueError  ← STRICT VALIDATION                   │     │
│  │  return message                                            │     │
│  └────────────────────────────────────────────────────────────┘     │
│                                                                       │
│  ┌────────────────────────────────────────────────────────────┐     │
│  │ AFTER: _wait_for_message_types(msg_types, timeout)         │     │
│  │                                                             │     │
│  │  message = await queue.get()  # timeout=5s                 │     │
│  │  if message["type"] not in msg_types:                      │     │
│  │    raise ValueError  ← FLEXIBLE VALIDATION                 │     │
│  │  return (actual_type, message)                             │     │
│  └────────────────────────────────────────────────────────────┘     │
└──────────────────────────────────────────────────────────────────────┘
                                  │
                                  │ Calls to
                                  ▼
┌──────────────────────────────────────────────────────────────────────┐
│                         TestRunner                                    │
│                                                                       │
│  ┌────────────────────────────────────────────────────────────┐     │
│  │ BEFORE: Cascading Try-Except (Lines 400-421)               │     │
│  │                                                             │     │
│  │  try:                                                      │     │
│  │    msg = await bot.wait_for_question(5s)                   │     │
│  │  except TimeoutError:                                      │     │
│  │    try:                                                    │     │
│  │      msg = await bot.wait_for_follow_up(5s)                │     │
│  │    except TimeoutError:                                    │     │
│  │      try:                                                  │     │
│  │        completion = await bot.wait_for_completion(5s)      │     │
│  │      except TimeoutError:                                  │     │
│  │        break                                               │     │
│  │                                                             │     │
│  │  Max timeout: 15s (5+5+5)                                  │     │
│  │  Issue: ValueError never reaches 2nd/3rd tier              │     │
│  └────────────────────────────────────────────────────────────┘     │
│                                                                       │
│  ┌────────────────────────────────────────────────────────────┐     │
│  │ AFTER: Simplified Cascade                                  │     │
│  │                                                             │     │
│  │  try:                                                      │     │
│  │    msg = await bot.wait_for_next_question(5s)              │     │
│  │    # Accepts ["question", "follow_up_question"]            │     │
│  │  except TimeoutError:                                      │     │
│  │    try:                                                    │     │
│  │      completion = await bot.wait_for_completion(5s)        │     │
│  │    except TimeoutError:                                    │     │
│  │      break                                                 │     │
│  │                                                             │     │
│  │  Max timeout: 10s (5+5)                                    │     │
│  │  Benefit: No ValueError on valid question types            │     │
│  └────────────────────────────────────────────────────────────┘     │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Message Type Flow

### Server Sends "question"

```
Server                Bot (_receive_loop)         Queue                 Bot (wait_for_next_question)         TestRunner
  │                           │                     │                              │                              │
  │──────"question"──────────>│                     │                              │                              │
  │                           │                     │                              │                              │
  │                           │───put(message)─────>│                              │                              │
  │                           │                     │                              │                              │
  │                           │                     │<────queue.get()──────────────│                              │
  │                           │                     │                              │                              │
  │                           │                     │──────message─────────────────>│                              │
  │                           │                     │                              │                              │
  │                           │                     │                       Validate: "question" in                │
  │                           │                     │                       ["question", "follow_up"]              │
  │                           │                     │                              │                              │
  │                           │                     │                              ✓ PASS                         │
  │                           │                     │                              │                              │
  │                           │                     │                              │──────message────────────────>│
  │                           │                     │                              │                              │
  │                           │                     │                              │                        Process question
  │                           │                     │                              │                        Generate answer
```

---

### Server Sends "follow_up_question"

```
Server                Bot (_receive_loop)         Queue                 Bot (wait_for_next_question)         TestRunner
  │                           │                     │                              │                              │
  │────"follow_up"───────────>│                     │                              │                              │
  │                           │                     │                              │                              │
  │                           │───put(message)─────>│                              │                              │
  │                           │                     │                              │                              │
  │                           │                     │<────queue.get()──────────────│                              │
  │                           │                     │                              │                              │
  │                           │                     │──────message─────────────────>│                              │
  │                           │                     │                              │                              │
  │                           │                     │                       Validate: "follow_up" in              │
  │                           │                     │                       ["question", "follow_up"]              │
  │                           │                     │                              │                              │
  │                           │                     │                              ✓ PASS                         │
  │                           │                     │                              │                              │
  │                           │                     │                              │──────message────────────────>│
  │                           │                     │                              │                              │
  │                           │                     │                              │                        Process follow-up
  │                           │                     │                              │                        Generate answer
```

---

## BEFORE: ValueError Breaks Cascade

```
Server sends: "follow_up_question"

TestRunner                        Bot (wait_for_question)                    Queue
    │                                      │                                   │
    │────wait_for_question(5s)────────────>│                                   │
    │                                      │                                   │
    │                                      │<────get()───────────────────────┤│
    │                                      │                                   │
    │                                      │  Validate:                        │
    │                                      │  "question" == "follow_up"?       │
    │                                      │  NO! ❌                            │
    │                                      │                                   │
    │<─────ValueError─────────────────────│                                   │
    │                                                                          │
    │  ❌ Exception propagates                                                  │
    │  (never reaches wait_for_follow_up)                                      │
    │                                                                          │
    └──> TEST FAILS                                                            │
```

---

## AFTER: Flexible Validation Succeeds

```
Server sends: "follow_up_question"

TestRunner                     Bot (wait_for_next_question)                 Queue
    │                                      │                                   │
    │──wait_for_next_question(5s)─────────>│                                   │
    │                                      │                                   │
    │                                      │<────get()───────────────────────┤│
    │                                      │                                   │
    │                                      │  Validate:                        │
    │                                      │  "follow_up" in                   │
    │                                      │  ["question", "follow_up"]?       │
    │                                      │  YES! ✓                           │
    │                                      │                                   │
    │<─────("follow_up", message)──────────│                                   │
    │                                                                          │
    │  ✓ Process message                                                       │
    │  ✓ Generate answer                                                       │
    │  ✓ TEST CONTINUES                                                        │
```

---

## Class Hierarchy

```
InterviewTestBot
├── Connection State
│   ├── ws: WebSocketClientProtocol | None
│   ├── connected: bool
│   └── _receive_task: asyncio.Task | None
│
├── Interview State
│   ├── current_status: str (IDLE, QUESTIONING, FOLLOW_UP, EVALUATING, COMPLETE)
│   ├── current_question_id: UUID | None
│   ├── current_question_text: str | None
│   ├── questions_received: int
│   ├── answers_sent: int
│   ├── evaluations_received: int
│   └── follow_ups_received: int
│
├── Message Queue
│   └── _message_queue: asyncio.Queue (unbounded FIFO)
│
├── Metrics
│   └── metrics: dict
│       ├── latency: dict[str, list[float]]
│       ├── states: list[tuple[datetime, str]]
│       └── errors: list[tuple[datetime, str, str]]
│
├── Background Tasks
│   └── _receive_loop() → Reads WebSocket, feeds queue
│
├── Internal Helpers
│   ├── _wait_for_message_type(msg_type, timeout) [OLD: Strict]
│   ├── _wait_for_message_types(msg_types, timeout) [NEW: Flexible] ← ADDED
│   ├── _track_metric(metric_type, key, value)
│   ├── _track_state(state)
│   └── _track_error(code, message)
│
└── Public API
    ├── connect(ws_url)
    ├── disconnect()
    ├── send_text_answer(question_id, answer_text)
    ├── send_audio_chunk(question_id, audio_data, ...)
    ├── wait_for_question(timeout) [Backward compatible]
    ├── wait_for_next_question(timeout) [NEW: Recommended] ← ADDED
    ├── wait_for_follow_up(timeout) [Backward compatible]
    ├── wait_for_evaluation(timeout)
    ├── wait_for_completion(timeout)
    ├── wait_for_error(timeout)
    ├── get_metrics()
    └── get_state()
```

---

## Method Call Stack

### BEFORE: Cascade Failure

```
TestRunner._run_websocket_qa()
  │
  ├─> bot.wait_for_question(timeout=5.0)
  │     │
  │     └─> bot._wait_for_message_type("question", 5.0)
  │           │
  │           ├─> asyncio.wait_for(queue.get(), 5.0)
  │           │     │
  │           │     └─> Returns: {"type": "follow_up_question", ...}
  │           │
  │           ├─> Validation: "question" == "follow_up_question"?
  │           │     │
  │           │     └─> NO! ❌
  │           │
  │           └─> raise ValueError(...)
  │                 │
  │                 └─> Propagates to TestRunner
  │                       │
  │                       └─> Outer try-except catches
  │                             │
  │                             └─> TEST FAILS
```

---

### AFTER: Flexible Success

```
TestRunner._run_websocket_qa()
  │
  ├─> bot.wait_for_next_question(timeout=5.0)
  │     │
  │     └─> bot._wait_for_message_types(["question", "follow_up_question"], 5.0)
  │           │
  │           ├─> asyncio.wait_for(queue.get(), 5.0)
  │           │     │
  │           │     └─> Returns: {"type": "follow_up_question", ...}
  │           │
  │           ├─> Validation: "follow_up_question" in ["question", "follow_up_question"]?
  │           │     │
  │           │     └─> YES! ✓
  │           │
  │           └─> return ("follow_up_question", message)
  │                 │
  │                 └─> Back to wait_for_next_question()
  │                       │
  │                       ├─> Update state (FOLLOW_UP)
  │                       ├─> Track metrics (follow_ups_received++)
  │                       ├─> Log message
  │                       │
  │                       └─> return message
  │                             │
  │                             └─> Back to TestRunner
  │                                   │
  │                                   ├─> Store in context["follow_ups"]
  │                                   ├─> Generate answer
  │                                   ├─> Send answer
  │                                   │
  │                                   └─> ✓ TEST CONTINUES
```

---

## Data Flow: Complete Interview

```
┌─────────────────────────────────────────────────────────────────────────┐
│ Iteration 1: Regular Question                                           │
├─────────────────────────────────────────────────────────────────────────┤
│ Server → "question" → Queue → wait_for_next_question() → ✓ Success      │
│ TestRunner → Generate answer → Send → wait_for_evaluation() → ✓ Success │
└─────────────────────────────────────────────────────────────────────────┘
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Iteration 2: Follow-Up Question                                         │
├─────────────────────────────────────────────────────────────────────────┤
│ Server → "follow_up" → Queue → wait_for_next_question() → ✓ Success     │
│ TestRunner → Generate answer → Send → wait_for_evaluation() → ✓ Success │
└─────────────────────────────────────────────────────────────────────────┘
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Iteration 3: Regular Question                                           │
├─────────────────────────────────────────────────────────────────────────┤
│ Server → "question" → Queue → wait_for_next_question() → ✓ Success      │
│ TestRunner → Generate answer → Send → wait_for_evaluation() → ✓ Success │
└─────────────────────────────────────────────────────────────────────────┘
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Iteration 4: Completion                                                 │
├─────────────────────────────────────────────────────────────────────────┤
│ Server → "interview_complete" → Queue                                   │
│ wait_for_next_question() → TimeoutError (5s, no question)               │
│ wait_for_completion() → ✓ Success (receives completion)                 │
│ TestRunner → Store summary → Break loop → ✓ TEST COMPLETE               │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Configuration Flow

```
BotConfig (YAML/Env)
  │
  ├─> timeouts:
  │     ├─> question_timeout_sec: 5.0
  │     ├─> follow_up_timeout_sec: 5.0 [DEPRECATED]
  │     ├─> evaluation_timeout_sec: 10.0
  │     └─> completion_timeout_sec: 5.0
  │
  └─> Used by TestRunner:
        │
        ├─> wait_for_next_question(timeout=config.timeouts.question_timeout_sec)
        ├─> wait_for_evaluation(timeout=config.timeouts.evaluation_timeout_sec)
        └─> wait_for_completion(timeout=config.timeouts.completion_timeout_sec)
```

**Note**: `follow_up_timeout_sec` no longer used (both question types use `question_timeout_sec`)

---

## State Transitions

```
Bot State Machine:

  IDLE
    │
    │ connect()
    ▼
  CONNECTED
    │
    │ wait_for_next_question() receives "question"
    ▼
  QUESTIONING
    │
    │ send_text_answer()
    ▼
  ANSWERING
    │
    │ wait_for_evaluation()
    ▼
  EVALUATING
    │
    ├─> wait_for_next_question() receives "follow_up_question"
    │     ▼
    │   FOLLOW_UP
    │     │
    │     │ send_text_answer()
    │     ▼
    │   ANSWERING → EVALUATING (loop back)
    │
    └─> wait_for_completion() receives "interview_complete"
          ▼
        COMPLETE
          │
          │ disconnect()
          ▼
        DISCONNECTED
```

---

## Metrics Tracking Flow

```
Message Received
  │
  ├─> _receive_loop() puts in queue
  │
  └─> _wait_for_message_types() reads from queue
        │
        ├─> Calculate latency: (now - start) * 1000 ms
        │
        ├─> _track_metric("latency", f"wait_{msg_type}", latency)
        │     │
        │     └─> Appends to metrics["latency"][f"wait_{msg_type}"]
        │
        └─> Return (msg_type, message)
              │
              └─> wait_for_next_question() updates state
                    │
                    ├─> If "question": questions_received++
                    ├─> If "follow_up": follow_ups_received++
                    │
                    └─> _track_state(state)
                          │
                          └─> Appends to metrics["states"]
```

**Result**: Accurate latency metrics per message type + state transition history

---

## Summary: Architectural Changes

### Added Components
1. `_wait_for_message_types()` - Flexible validation helper
2. `wait_for_next_question()` - Unified question waiting API

### Modified Components
1. `TestRunner._run_websocket_qa()` - Simplified cascade logic

### Unchanged Components
1. `_receive_loop()` - Background task (no changes)
2. `_message_queue` - Queue architecture (no changes)
3. All existing wait_for_*() methods - Backward compatible
4. Metrics tracking - Same mechanism, clearer data

### Deprecated Components
1. `follow_up_timeout_sec` config - Use `question_timeout_sec` instead

### Benefits
- **Simplified architecture**: 2-tier cascade vs 3-tier
- **Clearer semantics**: "next question" (any type) vs "question" (strict type)
- **Better metrics**: True latencies vs timeout-polluted data
- **Future-proof**: Easy to add new question types (just add to list)
