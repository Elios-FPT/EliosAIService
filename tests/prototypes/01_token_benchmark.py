"""Phase 0 Task 1: Token Usage Benchmark
Compare token usage between Azure OpenAI adapter vs LangChain adapter.

This prototype validates the assumption that LangChain's token overhead is <40%.
"""

import asyncio
import os
import sys
from typing import Any

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from openai import AsyncAzureOpenAI


class LangChainPrototypeAdapter:
    """Minimal LangChain adapter for token benchmarking."""

    def __init__(self, api_key: str, model: str = "gpt-4"):
        self.llm = ChatOpenAI(
            api_key=api_key,
            model=model,
            temperature=0.7,
        )

    async def generate_question(
        self, skill: str, difficulty: str, context: dict[str, Any]
    ) -> tuple[str, int]:
        """Generate question using LangChain LCEL.

        Returns:
            Tuple of (question_text, total_tokens)
        """
        template = ChatPromptTemplate.from_messages([
            ("system", """You are an expert technical interviewer.
Generate a clear, relevant interview question based on the context provided."""),
            ("human", """
Generate a {difficulty} difficulty interview question to test: {skill}

Context:
- Candidate's background: {cv_summary}
- Previous topics covered: {covered_topics}
- Interview stage: {stage}

**IMPORTANT CONSTRAINTS**:
The question MUST be verbal/discussion-based. DO NOT generate questions that require:
- Writing code ("write a function", "implement", "create a class", "code a solution")
- Drawing diagrams ("draw", "sketch", "diagram", "visualize", "map out")
- Whiteboard exercises ("design on whiteboard", "show on board", "illustrate")
- Visual outputs ("create a flowchart", "design a schema visually")

Focus on conceptual understanding, best practices, trade-offs, and problem-solving approaches that can be explained verbally.

Return only the question text, no additional explanation.
""")
        ])

        chain = template | self.llm

        result = await chain.ainvoke({
            "skill": skill,
            "difficulty": difficulty,
            "cv_summary": context.get("cv_summary", "Not provided"),
            "covered_topics": context.get("covered_topics", []),
            "stage": context.get("stage", "early"),
        })

        # Extract token usage
        tokens = result.response_metadata.get("token_usage", {}).get("total_tokens", 0)

        return result.content, tokens


class AzurePrototypeAdapter:
    """Minimal Azure OpenAI adapter for token benchmarking."""

    def __init__(
        self,
        api_key: str,
        azure_endpoint: str,
        api_version: str,
        deployment_name: str,
    ):
        self.client = AsyncAzureOpenAI(
            api_key=api_key,
            api_version=api_version,
            azure_endpoint=azure_endpoint,
        )
        self.model = deployment_name
        self.temperature = 0.7

    async def generate_question(
        self, skill: str, difficulty: str, context: dict[str, Any]
    ) -> tuple[str, int]:
        """Generate question using Azure OpenAI.

        Returns:
            Tuple of (question_text, total_tokens)
        """
        system_prompt = """You are an expert technical interviewer.
        Generate a clear, relevant interview question based on the context provided."""

        user_prompt = f"""
        Generate a {difficulty} difficulty interview question to test: {skill}

        Context:
        - Candidate's background: {context.get('cv_summary', 'Not provided')}
        - Previous topics covered: {context.get('covered_topics', [])}
        - Interview stage: {context.get('stage', 'early')}

**IMPORTANT CONSTRAINTS**:
The question MUST be verbal/discussion-based. DO NOT generate questions that require:
- Writing code ("write a function", "implement", "create a class", "code a solution")
- Drawing diagrams ("draw", "sketch", "diagram", "visualize", "map out")
- Whiteboard exercises ("design on whiteboard", "show on board", "illustrate")
- Visual outputs ("create a flowchart", "design a schema visually")

Focus on conceptual understanding, best practices, trade-offs, and problem-solving approaches that can be explained verbally.

Return only the question text, no additional explanation.
"""

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=self.temperature,
        )

        content = response.choices[0].message.content or ""
        tokens = response.usage.total_tokens if response.usage else 0

        return content.strip(), tokens


async def run_benchmark():
    """Run token usage benchmark."""
    print("=== Phase 0 Task 1: Token Usage Benchmark ===\n")

    # Load config
    from dotenv import load_dotenv
    load_dotenv(".env.local")

    openai_key = os.getenv("OPENAI_API_KEY")
    azure_key = os.getenv("AZURE_OPENAI_API_KEY")
    azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    azure_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
    azure_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4")

    # Test cases
    test_cases = [
        ("Python", "medium", {
            "cv_summary": "3 years Python backend development",
            "covered_topics": ["OOP basics"],
            "stage": "early"
        }),
        ("FastAPI", "hard", {
            "cv_summary": "FastAPI microservices experience",
            "covered_topics": ["async/await", "dependency injection"],
            "stage": "middle"
        }),
        ("PostgreSQL", "easy", {
            "cv_summary": "SQL database experience",
            "covered_topics": [],
            "stage": "early"
        }),
        ("System Design", "hard", {
            "cv_summary": "5 years full-stack development",
            "covered_topics": ["scalability", "caching"],
            "stage": "late"
        }),
        ("Testing", "medium", {
            "cv_summary": "pytest experience with CI/CD",
            "covered_topics": ["unit tests"],
            "stage": "middle"
        }),
    ]

    # Initialize adapters
    azure_tokens = []
    langchain_tokens = []
    questions_azure = []
    questions_langchain = []

    print("Test Configuration:")
    print(f"- Model: GPT-4")
    print(f"- Test cases: {len(test_cases)}")
    print(f"- Temperature: 0.7\n")

    # Run Azure benchmark if configured
    if azure_key and azure_endpoint:
        print("--- Running Azure OpenAI Benchmark ---")
        azure_adapter = AzurePrototypeAdapter(
            api_key=azure_key,
            azure_endpoint=azure_endpoint,
            api_version=azure_version,
            deployment_name=azure_deployment,
        )

        for i, (skill, difficulty, context) in enumerate(test_cases, 1):
            print(f"  [{i}/{len(test_cases)}] {skill} ({difficulty})...", end=" ")
            try:
                question, tokens = await azure_adapter.generate_question(
                    skill, difficulty, context
                )
                azure_tokens.append(tokens)
                questions_azure.append(question)
                print(f"{tokens} tokens")
            except Exception as e:
                print(f"ERROR: {e}")
                azure_tokens.append(0)
                questions_azure.append("")

        print()

    # Run LangChain benchmark
    if openai_key:
        print("--- Running LangChain Benchmark ---")
        langchain_adapter = LangChainPrototypeAdapter(
            api_key=openai_key,
            model="gpt-4",
        )

        for i, (skill, difficulty, context) in enumerate(test_cases, 1):
            print(f"  [{i}/{len(test_cases)}] {skill} ({difficulty})...", end=" ")
            try:
                question, tokens = await langchain_adapter.generate_question(
                    skill, difficulty, context
                )
                langchain_tokens.append(tokens)
                questions_langchain.append(question)
                print(f"{tokens} tokens")
            except Exception as e:
                print(f"ERROR: {e}")
                langchain_tokens.append(0)
                questions_langchain.append("")

        print()

    # Calculate statistics
    print("=== Results ===\n")

    if azure_tokens and langchain_tokens:
        azure_avg = sum(azure_tokens) / len(azure_tokens) if azure_tokens else 0
        langchain_avg = sum(langchain_tokens) / len(langchain_tokens) if langchain_tokens else 0
        increase_pct = ((langchain_avg - azure_avg) / azure_avg) * 100 if azure_avg > 0 else 0

        print(f"Azure OpenAI:")
        print(f"  Average tokens: {azure_avg:.1f}")
        print(f"  Total tokens: {sum(azure_tokens)}")
        print(f"  Min/Max: {min(azure_tokens)}/{max(azure_tokens)}\n")

        print(f"LangChain:")
        print(f"  Average tokens: {langchain_avg:.1f}")
        print(f"  Total tokens: {sum(langchain_tokens)}")
        print(f"  Min/Max: {min(langchain_tokens)}/{max(langchain_tokens)}\n")

        print(f"Comparison:")
        print(f"  Token increase: {increase_pct:+.1f}%")
        print(f"  Cost impact (GPT-4 @ $0.03/1K): ${(langchain_avg - azure_avg) * 0.03 / 1000:.4f} per question\n")

        # Decision
        print("=== Decision ===\n")
        if increase_pct < 0:
            print(f"UNEXPECTED: LangChain uses {abs(increase_pct):.1f}% FEWER tokens than Azure")
            print("Status: PROCEED WITH CONFIDENCE")
        elif increase_pct <= 30:
            print(f"Token increase {increase_pct:.1f}% is within acceptable range (<30%)")
            print("Status: PROCEED WITH CONFIDENCE")
        elif increase_pct <= 40:
            print(f"Token increase {increase_pct:.1f}% triggers optimization threshold (30-40%)")
            print("Status: PROCEED WITH OPTIMIZATION PLAN")
        else:
            print(f"Token increase {increase_pct:.1f}% EXCEEDS tolerance (>40%)")
            print("Status: OPTIMIZE PROMPTS OR RECONSIDER LANGCHAIN")

    elif langchain_tokens:
        langchain_avg = sum(langchain_tokens) / len(langchain_tokens) if langchain_tokens else 0
        print(f"LangChain only:")
        print(f"  Average tokens: {langchain_avg:.1f}")
        print(f"  Total tokens: {sum(langchain_tokens)}")
        print(f"  Min/Max: {min(langchain_tokens)}/{max(langchain_tokens)}\n")
        print("Note: Azure comparison unavailable (missing credentials)")

    else:
        print("ERROR: No benchmarks completed. Check API credentials.")
        return

    # Save detailed report
    report_path = "tests/prototypes/reports/01_token_benchmark_results.md"
    with open(report_path, "w") as f:
        f.write("# Phase 0 Task 1: Token Usage Benchmark Results\n\n")
        f.write(f"**Date**: {asyncio.get_event_loop().time()}\n")
        f.write(f"**Model**: GPT-4\n")
        f.write(f"**Temperature**: 0.7\n")
        f.write(f"**Test Cases**: {len(test_cases)}\n\n")

        f.write("## Test Cases\n\n")
        for i, (skill, difficulty, context) in enumerate(test_cases, 1):
            f.write(f"{i}. **{skill}** ({difficulty})\n")
            f.write(f"   - Context: {context['cv_summary']}\n")
            f.write(f"   - Covered: {context['covered_topics']}\n\n")

        if azure_tokens:
            f.write("## Azure OpenAI Results\n\n")
            f.write(f"- Average tokens: {azure_avg:.1f}\n")
            f.write(f"- Total tokens: {sum(azure_tokens)}\n")
            f.write(f"- Min/Max: {min(azure_tokens)}/{max(azure_tokens)}\n\n")

        if langchain_tokens:
            f.write("## LangChain Results\n\n")
            f.write(f"- Average tokens: {langchain_avg:.1f}\n")
            f.write(f"- Total tokens: {sum(langchain_tokens)}\n")
            f.write(f"- Min/Max: {min(langchain_tokens)}/{max(langchain_tokens)}\n\n")

        if azure_tokens and langchain_tokens:
            f.write("## Comparison\n\n")
            f.write(f"- **Token increase**: {increase_pct:+.1f}%\n")
            f.write(f"- **Cost impact**: ${(langchain_avg - azure_avg) * 0.03 / 1000:.4f} per question\n")
            f.write(f"- **Annual cost (10K questions)**: ${(langchain_avg - azure_avg) * 0.03 * 10:.2f}\n\n")

            f.write("## Decision\n\n")
            if increase_pct <= 30:
                f.write(f"**Status**: PROCEED WITH CONFIDENCE\n\n")
                f.write(f"Token increase {increase_pct:.1f}% is within acceptable range (<30%).\n")
            elif increase_pct <= 40:
                f.write(f"**Status**: PROCEED WITH OPTIMIZATION PLAN\n\n")
                f.write(f"Token increase {increase_pct:.1f}% triggers optimization threshold (30-40%).\n")
                f.write(f"Recommendation: Spend 1 day optimizing prompts before Phase 1.\n")
            else:
                f.write(f"**Status**: OPTIMIZE OR RECONSIDER\n\n")
                f.write(f"Token increase {increase_pct:.1f}% EXCEEDS tolerance (>40%).\n")
                f.write(f"Recommendation: Optimize prompts aggressively OR reconsider LangChain adoption.\n")

    print(f"\nDetailed report saved: {report_path}")


if __name__ == "__main__":
    asyncio.run(run_benchmark())
