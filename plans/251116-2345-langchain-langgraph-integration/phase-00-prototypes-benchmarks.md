# Phase 0: Prototypes & Benchmarks

**Phase ID**: 00
**Created**: 2025-11-16
**Priority**: Critical (Validates Assumptions)
**Estimated Duration**: 3-4 days
**Risk Level**: Low
**Implementation Status**: Not Started
**Review Status**: Approved

---

## Context Links

- **Parent Plan**: [plan.md](plan.md)
- **Dependencies**: None (prerequisite for Phase 1)
- **Blocks**: Phase 1-4 (must validate assumptions first)

---

## Overview

**Validate critical assumptions** before committing to full implementation via targeted prototypes and benchmarks.

**Problem**: Plan assumes +40% token cost and LangGraph interrupts work as expected. Must verify BEFORE building full adapters.

**Solution**: Build minimal prototypes to measure actual costs and validate interrupt patterns.

---

## User Decisions Applied

1. **Multi-LLM Fallback**: Skip for now (defer to Phase 5)
2. **WebSocket Timeout**: 10 minutes before checkpoint cleanup
3. **Cost Tolerance**:
   - +30% acceptable IF 3x performance gain
   - +40% triggers prompt optimization sprint
   - >50% → reconsider LangChain entirely

---

## Objectives

### Objective 1: Token Usage Benchmark
**Validate**: LangChain token increase is <40%

**Method**: Build minimal LangChain prototype, compare tokens with current Azure adapter

**Acceptance Criteria**:
- ✅ Token increase <30%: Proceed with confidence
- ⚠️ Token increase 30-40%: Proceed with optimization plan
- ❌ Token increase >40%: Optimize prompts OR reconsider LangChain

### Objective 2: Interrupt Pattern Prototype
**Validate**: LangGraph human-in-loop interrupts work with WebSocket flow

**Method**: Build 2-node StateGraph with interrupt, simulate WebSocket message cycle

**Acceptance Criteria**:
- ✅ Interrupt pauses workflow correctly
- ✅ Resume continues from interrupt point
- ✅ State persists across pause/resume

### Objective 3: Performance Baseline
**Validate**: Parallel execution achieves 3x speedup

**Method**: Time sequential vs parallel question generation (mock LLM)

**Acceptance Criteria**:
- ✅ Parallel execution ≥3x faster than sequential

---

## Implementation Tasks

### Task 1: Token Usage Benchmark (1 day)

**Scope**: Compare current Azure adapter vs LangChain adapter for identical operations

**Steps**:
1. Create minimal `LangChainPrototypeAdapter`:
   ```python
   # tests/prototypes/langchain_token_benchmark.py
   from langchain.prompts import ChatPromptTemplate
   from langchain_openai import ChatOpenAI

   class LangChainPrototypeAdapter:
       def __init__(self, api_key: str):
           self.llm = ChatOpenAI(api_key=api_key, model="gpt-4")

       async def generate_question_prototype(self, skill: str, difficulty: str):
           template = ChatPromptTemplate.from_messages([
               ("system", "You are an interview question generator."),
               ("human", "Generate a {difficulty} question about {skill}.")
           ])
           chain = template | self.llm
           result = await chain.ainvoke({"skill": skill, "difficulty": difficulty})
           return result.content
   ```

2. Run side-by-side comparison:
   ```python
   # Benchmark script
   test_cases = [
       ("Python", "medium"),
       ("FastAPI", "hard"),
       ("PostgreSQL", "easy"),
   ]

   azure_tokens = []
   langchain_tokens = []

   for skill, difficulty in test_cases:
       # Current Azure adapter
       azure_response = await azure_adapter.generate_question({"skill": skill}, skill, difficulty)
       azure_tokens.append(azure_response.usage.total_tokens)

       # LangChain prototype
       langchain_response = await langchain_prototype.generate_question_prototype(skill, difficulty)
       langchain_tokens.append(langchain_response.response_metadata["token_usage"]["total_tokens"])

   azure_avg = sum(azure_tokens) / len(azure_tokens)
   langchain_avg = sum(langchain_tokens) / len(langchain_tokens)
   increase_pct = ((langchain_avg - azure_avg) / azure_avg) * 100

   print(f"Azure avg tokens: {azure_avg}")
   print(f"LangChain avg tokens: {langchain_avg}")
   print(f"Increase: {increase_pct:.1f}%")
   ```

3. Document results:
   - Token counts per operation
   - Percentage increase
   - Cost impact projection ($0.03/1K tokens for GPT-4)

**Output**: `reports/token-benchmark-results.md`

**Decision Point**:
- If increase >40% → spend 1 day optimizing prompts, re-test
- If still >40% → document risk, proceed cautiously OR abort

---

### Task 2: Interrupt Pattern Prototype (1 day)

**Scope**: Minimal StateGraph with human-in-loop interrupt, test pause/resume

**Steps**:
1. Create minimal workflow:
   ```python
   # tests/prototypes/interrupt_pattern_prototype.py
   from langgraph.graph import StateGraph
   from langgraph.checkpoint.memory import MemorySaver
   from typing import TypedDict

   class InterruptState(TypedDict):
       question: str
       answer: str | None
       evaluation: str | None

   def ask_question_node(state: InterruptState):
       return {"question": "What is Clean Architecture?"}

   def wait_for_answer_node(state: InterruptState):
       # INTERRUPT HERE - wait for external input
       from langgraph.graph import interrupt
       user_answer = interrupt("Waiting for user answer...")
       return {"answer": user_answer}

   def evaluate_answer_node(state: InterruptState):
       return {"evaluation": f"Answer '{state['answer']}' is correct!"}

   # Build graph
   graph = StateGraph(InterruptState)
   graph.add_node("ask", ask_question_node)
   graph.add_node("wait", wait_for_answer_node)
   graph.add_node("evaluate", evaluate_answer_node)

   graph.add_edge("ask", "wait")
   graph.add_edge("wait", "evaluate")
   graph.set_entry_point("ask")
   graph.set_finish_point("evaluate")

   checkpointer = MemorySaver()
   app = graph.compile(checkpointer=checkpointer, interrupt_before=["wait"])
   ```

2. Test interrupt/resume cycle:
   ```python
   # Test script
   thread_id = "test-thread-001"
   config = {"configurable": {"thread_id": thread_id}}

   # First invocation - should pause at interrupt
   print("=== First invocation ===")
   result1 = await app.ainvoke({"question": "", "answer": None, "evaluation": None}, config)
   print(f"State after interrupt: {result1}")
   # Expected: {"question": "What is Clean Architecture?", "answer": None, "evaluation": None}

   # Simulate WebSocket message received
   print("\n=== Resume with answer ===")
   result2 = await app.ainvoke({"answer": "Hexagonal Architecture"}, config)
   print(f"Final state: {result2}")
   # Expected: {"question": "...", "answer": "Hexagonal Architecture", "evaluation": "Answer '...' is correct!"}
   ```

3. Verify checkpoint persistence:
   ```python
   # Retrieve state from checkpoint
   state = await app.aget_state(config)
   print(f"Checkpoint state: {state.values}")
   print(f"Next node: {state.next}")  # Should be "wait" or "evaluate"
   ```

**Output**: `reports/interrupt-pattern-validation.md`

**Decision Point**:
- If interrupts work → Proceed to Phase 3
- If interrupts fail → Document issue, escalate to LangGraph community

---

### Task 3: Performance Baseline (1 day)

**Scope**: Measure sequential vs parallel execution speedup

**Steps**:
1. Mock LLM calls (deterministic timing):
   ```python
   # tests/prototypes/performance_benchmark.py
   import asyncio
   import time

   async def mock_llm_call(delay: float = 1.0):
       """Simulates LLM call with 1s latency."""
       await asyncio.sleep(delay)
       return "Mock response"

   # Sequential execution (current)
   async def sequential_generation(n: int = 5):
       start = time.time()
       for i in range(n):
           await mock_llm_call()  # Question
           await mock_llm_call()  # Ideal answer
           await mock_llm_call()  # Rationale
       elapsed = time.time() - start
       print(f"Sequential ({n} questions): {elapsed:.2f}s")
       return elapsed

   # Parallel execution (LangGraph)
   async def parallel_generation(n: int = 5):
       start = time.time()

       # Generate all questions in parallel
       questions = await asyncio.gather(*[mock_llm_call() for _ in range(n)])
       answers = await asyncio.gather(*[mock_llm_call() for _ in range(n)])
       rationales = await asyncio.gather(*[mock_llm_call() for _ in range(n)])

       elapsed = time.time() - start
       print(f"Parallel ({n} questions): {elapsed:.2f}s")
       return elapsed

   # Benchmark
   seq_time = await sequential_generation(5)  # Expected: ~15s (5 × 3 × 1s)
   par_time = await parallel_generation(5)    # Expected: ~3s (3 batches × 1s)
   speedup = seq_time / par_time
   print(f"Speedup: {speedup:.1f}x")
   ```

2. Test with real LLM (GPT-4 turbo):
   ```python
   # Real benchmark (1-2 test runs to minimize cost)
   async def real_llm_call():
       response = await openai_client.chat.completions.create(
           model="gpt-4-turbo",
           messages=[{"role": "user", "content": "Say hello"}]
       )
       return response

   # Time sequential vs parallel (1 question only to save cost)
   seq_real = await sequential_generation(n=1)
   par_real = await parallel_generation(n=1)
   ```

**Output**: `reports/performance-benchmark-results.md`

**Decision Point**:
- If speedup <3x → Investigate bottleneck (network? rate limits?)
- If speedup ≥3x → Validate assumption, proceed

---

## Deliverables

### Reports (3)
1. **`reports/token-benchmark-results.md`**:
   - Azure vs LangChain token comparison
   - Percentage increase calculation
   - Cost impact projection
   - Recommendation (proceed/optimize/abort)

2. **`reports/interrupt-pattern-validation.md`**:
   - Prototype code
   - Test results (pause/resume successful?)
   - Checkpoint persistence verified
   - Integration notes for Phase 3

3. **`reports/performance-benchmark-results.md`**:
   - Sequential vs parallel timing
   - Speedup calculation
   - Real LLM test results
   - Bottleneck analysis (if any)

### Code (3 prototypes)
1. **`tests/prototypes/langchain_token_benchmark.py`**
2. **`tests/prototypes/interrupt_pattern_prototype.py`**
3. **`tests/prototypes/performance_benchmark.py`**

---

## Success Criteria

**Token Usage**:
- ✅ Increase ≤30% → Proceed with confidence
- ⚠️ Increase 30-40% → Proceed with optimization plan
- ❌ Increase >40% → Optimize OR reconsider

**Interrupt Pattern**:
- ✅ Pause/resume works correctly
- ✅ State persists in checkpoint
- ✅ Compatible with WebSocket flow

**Performance**:
- ✅ Parallel execution ≥3x faster
- ✅ Real LLM test confirms mock results

**Go/No-Go Decision**:
- **GO**: All 3 criteria met → Proceed to Phase 1
- **CONDITIONAL GO**: 2/3 met → Address failures, re-test
- **NO-GO**: <2 met → Abort or redesign approach

---

## Timeline

**Day 1**: Token benchmark + analysis
**Day 2**: Interrupt pattern prototype + testing
**Day 3**: Performance benchmark (mock + real)
**Day 4**: Buffer (document results, present to team)

**Total**: 3-4 days

---

## Risk Mitigation

**Risk 1: Token increase >40%**
- Mitigation: Optimize prompt templates (remove verbosity)
- Fallback: Use GPT-4-turbo ($0.01/1K vs $0.03/1K)

**Risk 2: Interrupts don't work as expected**
- Mitigation: Consult LangGraph docs/examples
- Fallback: Phase 3A approach (no interrupts, batch evaluation)

**Risk 3: Parallel execution bottlenecked**
- Mitigation: Investigate rate limits, connection pooling
- Fallback: Reduce parallelism (2 batches instead of 3)

---

## Next Steps After Phase 0

**If All Tests Pass**:
1. Update Phase 1 plan with actual token costs
2. Proceed to Phase 1 implementation
3. Archive prototypes as reference code

**If Token Increase >40%**:
1. Optimize prompts (1-day sprint)
2. Re-benchmark
3. Document final cost projection

**If Interrupts Fail**:
1. Update Phase 3 to use 3A approach (no interrupts)
2. Defer interrupts to Phase 5 (future enhancement)

---

**Phase Status**: Ready to Start
**Blocks**: Phase 1-4 (must complete first)
**Estimated Completion**: 2025-11-20
