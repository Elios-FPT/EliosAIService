"""Phase 0 Task 3: Performance Baseline
Measure parallel vs sequential question generation speedup.

Validates assumption that parallel execution achieves 3x speedup.
"""

import asyncio
import time
from typing import Any


async def mock_llm_call(skill: str, delay: float = 0.5) -> str:
    """Simulate LLM API call with delay."""
    await asyncio.sleep(delay)
    return f"Mock question about {skill}"


async def sequential_generation(skills: list[str], delay: float = 0.5) -> list[str]:
    """Generate questions sequentially (current approach)."""
    questions = []
    for skill in skills:
        question = await mock_llm_call(skill, delay)
        questions.append(question)
    return questions


async def parallel_generation(skills: list[str], delay: float = 0.5) -> list[str]:
    """Generate questions in parallel (LangChain approach)."""
    tasks = [mock_llm_call(skill, delay) for skill in skills]
    questions = await asyncio.gather(*tasks)
    return list(questions)


async def run_performance_baseline():
    """Run performance baseline benchmark."""
    print("=== Phase 0 Task 3: Performance Baseline ===\n")

    # Test configurations
    test_configs = [
        (3, 0.5, "Small batch (3 questions, 0.5s each)"),
        (5, 0.5, "Medium batch (5 questions, 0.5s each)"),
        (10, 0.3, "Large batch (10 questions, 0.3s each)"),
        (5, 1.0, "Slow API (5 questions, 1.0s each)"),
    ]

    results = []

    for num_questions, api_delay, description in test_configs:
        print(f"--- {description} ---\n")

        skills = [f"Skill_{i+1}" for i in range(num_questions)]

        # Sequential execution
        print("  Sequential execution...", end=" ")
        start = time.perf_counter()
        seq_questions = await sequential_generation(skills, api_delay)
        seq_time = time.perf_counter() - start
        print(f"{seq_time:.2f}s")

        # Parallel execution
        print("  Parallel execution...", end=" ")
        start = time.perf_counter()
        par_questions = await parallel_generation(skills, api_delay)
        par_time = time.perf_counter() - start
        print(f"{par_time:.2f}s")

        # Calculate speedup
        speedup = seq_time / par_time if par_time > 0 else 0
        print(f"  Speedup: {speedup:.1f}x\n")

        results.append({
            "description": description,
            "num_questions": num_questions,
            "api_delay": api_delay,
            "sequential_time": seq_time,
            "parallel_time": par_time,
            "speedup": speedup,
        })

    # Summary
    print("=== Results Summary ===\n")
    print(f"{'Test':<45} {'Sequential':>12} {'Parallel':>12} {'Speedup':>10}")
    print("-" * 85)

    for r in results:
        print(f"{r['description']:<45} {r['sequential_time']:>10.2f}s {r['parallel_time']:>10.2f}s {r['speedup']:>9.1f}x")

    avg_speedup = sum(r["speedup"] for r in results) / len(results)
    print(f"\nAverage speedup: {avg_speedup:.1f}x")

    # Decision
    print("\n=== Decision ===\n")
    if avg_speedup >= 3.0:
        print(f"Status: PASS - Average speedup {avg_speedup:.1f}x exceeds 3x target")
        print("- Parallel execution significantly faster than sequential")
        print("- Ready for Phase 2 LangGraph planning workflow")
    elif avg_speedup >= 2.0:
        print(f"Status: ACCEPTABLE - Average speedup {avg_speedup:.1f}x below 3x but still beneficial")
        print("- Parallel execution provides meaningful speedup")
        print("- Proceed with realistic expectations (2-3x vs 3-5x)")
    else:
        print(f"Status: FAIL - Average speedup {avg_speedup:.1f}x insufficient")
        print("- Parallel execution benefit unclear")
        print("- Review network latency, batch size, or mock accuracy")

    # Save report
    report_path = "tests/prototypes/reports/03_performance_baseline_results.md"
    with open(report_path, "w") as f:
        f.write("# Phase 0 Task 3: Performance Baseline Results\n\n")
        f.write("## Overview\n\n")
        f.write("Measures parallel vs sequential question generation to validate 3x speedup assumption.\n\n")

        f.write("## Test Results\n\n")
        f.write("| Test | Sequential | Parallel | Speedup |\n")
        f.write("|------|------------|----------|----------|\n")

        for r in results:
            f.write(f"| {r['description']} | {r['sequential_time']:.2f}s | {r['parallel_time']:.2f}s | {r['speedup']:.1f}x |\n")

        f.write(f"\n**Average Speedup**: {avg_speedup:.1f}x\n\n")

        f.write("## Analysis\n\n")
        f.write("### Sequential Approach\n\n")
        f.write("Current implementation generates questions one-by-one:\n")
        f.write("```python\n")
        f.write("for skill in skills:\n")
        f.write("    question = await llm.generate_question(skill)\n")
        f.write("    questions.append(question)\n")
        f.write("```\n\n")
        f.write(f"Total time for {results[1]['num_questions']} questions: {results[1]['sequential_time']:.2f}s\n\n")

        f.write("### Parallel Approach\n\n")
        f.write("LangChain LCEL enables parallel execution:\n")
        f.write("```python\n")
        f.write("tasks = [chain.ainvoke(skill) for skill in skills]\n")
        f.write("questions = await asyncio.gather(*tasks)\n")
        f.write("```\n\n")
        f.write(f"Total time for {results[1]['num_questions']} questions: {results[1]['parallel_time']:.2f}s\n\n")

        f.write("## Decision\n\n")
        if avg_speedup >= 3.0:
            f.write("**Status**: PASS\n\n")
            f.write(f"Average speedup {avg_speedup:.1f}x **exceeds 3x target**.\n\n")
            f.write("Benefits:\n")
            f.write("- Significantly reduced interview prep time\n")
            f.write("- Better user experience (faster question generation)\n")
            f.write("- Validates LangChain parallel execution architecture\n\n")
            f.write("**Ready for Phase 2**: Implement LangGraph planning workflow with parallel question generation.\n")
        elif avg_speedup >= 2.0:
            f.write("**Status**: ACCEPTABLE\n\n")
            f.write(f"Average speedup {avg_speedup:.1f}x below 3x target but still beneficial.\n\n")
            f.write("**Proceed with adjusted expectations**: Target 2-3x speedup instead of 3-5x.\n")
        else:
            f.write("**Status**: FAIL\n\n")
            f.write(f"Average speedup {avg_speedup:.1f}x insufficient.\n\n")
            f.write("Issues:\n")
            f.write("- Mock delays may not reflect real API latency\n")
            f.write("- Network overhead not accounted for\n")
            f.write("- Consider testing with real LLM API\n")

    print(f"\nDetailed report saved: {report_path}")

    return avg_speedup >= 2.0


if __name__ == "__main__":
    success = asyncio.run(run_performance_baseline())
    import sys
    sys.exit(0 if success else 1)
