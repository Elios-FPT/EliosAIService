"""Integration tests for LangChainAdapter with database-driven prompts.

End-to-end tests with real PostgreSQL database to verify:
- DB prompt loading and execution
- Execution logging and analytics
- A/B testing and version management
- Prompt rollback
"""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
import pytest_asyncio
from langchain_core.language_models import BaseChatModel

from src.infrastructure.adapters.llm.langchain_adapter import LangChainAdapter
from src.infrastructure.adapters.persistence.postgres_prompt_repository import PostgreSQLPromptRepository
from src.domain.models.question import DifficultyLevel, Question, QuestionType


@pytest_asyncio.fixture
async def prompt_repo(async_session):
    """Create PromptRepository with test DB."""
    return PostgreSQLPromptRepository(async_session)


@pytest_asyncio.fixture
async def adapter_with_db(prompt_repo):
    """Create LangChainAdapter with real DB and mock model."""
    # Use mock model to avoid OpenAI API calls in tests
    mock_model = MagicMock(spec=BaseChatModel)
    mock_model.model_name = "gpt-3.5-turbo"
    mock_model.ainvoke = AsyncMock(
        return_value={
            "score": 80.0,
            "feedback": "Test feedback",
            "strengths": ["Good structure"],
            "weaknesses": ["Missing depth"],
            "missing_concepts": [],
        }
    )

    return LangChainAdapter(model=mock_model, prompt_repository=prompt_repo)


@pytest_asyncio.fixture
async def seeded_prompt(prompt_repo):
    """Seed test prompt in DB."""
    prompt = await prompt_repo.create_initial_prompt(
        name="test_prompt",
        template_json={
            "system": "You are a test system.",
            "user_template": "Question: {question}\nAnswer: {answer}",
            "variables": ["question", "answer"],
        },
        created_by="test",
    )

    # Activate prompt
    await prompt_repo.activate_version(
        prompt_id=prompt.id,
        changed_by="test",
        reason="Test setup",
        traffic_percentage=100,
    )

    return prompt


@pytest.mark.asyncio
@pytest.mark.integration
async def test_full_cycle_evaluate_answer(
    adapter_with_db, prompt_repo, async_session
):
    """Test full cycle: seed prompt → execute → verify execution logged."""
    # Step 1: Use existing answer_evaluation prompt from migration 0013
    prompt = await prompt_repo.get_active_prompt("answer_evaluation")
    if not prompt:
        pytest.skip("Migration 0013 should have seeded answer_evaluation")

    # Step 2: Execute method
    question = Question(
        text="What is Python?",
        question_type=QuestionType.TECHNICAL,
        difficulty=DifficultyLevel.MEDIUM,
        skills=["Python"],
    )

    result = await adapter_with_db.evaluate_answer(
        question=question,
        answer_text="Python is a high-level programming language...",
        context={"interview_id": "test-integration-123"},
    )

    # Step 3: Verify execution
    assert result.score > 0

    # Step 4: Verify execution logged
    await async_session.commit()  # Flush execution logs

    analytics = await prompt_repo.get_analytics_summary("answer_evaluation")
    assert analytics is not None
    assert analytics["total_executions"] >= 1
    assert analytics["success_rate"] >= 0.0


@pytest.mark.asyncio
@pytest.mark.integration
async def test_ab_testing_weighted_selection(prompt_repo, adapter_with_db):
    """Test A/B testing: multiple active prompts with traffic split."""
    # Create v1 (50% traffic)
    v1 = await prompt_repo.create_initial_prompt(
        name="ab_test_prompt",
        template_json={
            "system": "Version 1",
            "user_template": "{input}",
            "variables": ["input"],
        },
        created_by="test",
    )
    await prompt_repo.activate_version(
        prompt_id=v1.id,
        changed_by="test",
        reason="A/B test v1",
        traffic_percentage=50,
        ab_test_group="control",
    )

    # Create v2 (50% traffic)
    v2 = await prompt_repo.create_new_version(
        name="ab_test_prompt",
        parent_version=1,
        template_json={
            "system": "Version 2",
            "user_template": "{input}",
            "variables": ["input"],
        },
        change_summary="Test variant",
        created_by="test",
    )
    await prompt_repo.activate_version(
        prompt_id=v2.id,
        changed_by="test",
        reason="A/B test v2",
        traffic_percentage=50,
        ab_test_group="variant",
    )

    # Execute 100 times and track version distribution
    version_counts = {1: 0, 2: 0}

    for _ in range(100):
        selected = await prompt_repo.get_active_prompt("ab_test_prompt")
        if selected:
            version_counts[selected.version] += 1

    # Should be roughly 50/50 (allow ±20% variance)
    assert 30 <= version_counts[1] <= 70
    assert 30 <= version_counts[2] <= 70


@pytest.mark.asyncio
@pytest.mark.integration
async def test_prompt_rollback(prompt_repo, adapter_with_db):
    """Test rollback to previous prompt version."""
    # Create v1
    v1 = await prompt_repo.create_initial_prompt(
        name="rollback_test",
        template_json={
            "system": "v1",
            "user_template": "{input}",
            "variables": ["input"],
        },
        created_by="test",
    )
    await prompt_repo.activate_version(
        v1.id, "test", "Initial", traffic_percentage=100
    )

    # Create v2 (bad version)
    v2 = await prompt_repo.create_new_version(
        name="rollback_test",
        parent_version=1,
        template_json={
            "system": "v2 BAD",
            "user_template": "{input}",
            "variables": ["input"],
        },
        change_summary="Bad update",
        created_by="test",
    )
    await prompt_repo.activate_version(
        v2.id, "test", "Deploy v2", traffic_percentage=100
    )

    # Verify v2 active
    active = await prompt_repo.get_active_prompt("rollback_test")
    assert active is not None
    assert active.version == 2

    # Rollback to v1
    rolled_back = await prompt_repo.rollback_to_version(
        name="rollback_test",
        target_version=1,
        changed_by="test",
        reason="v2 caused issues",
    )

    # Activate rollback version
    await prompt_repo.activate_version(
        rolled_back.id, "test", "Rollback to v1", traffic_percentage=100
    )

    # Verify v3 active (rollback creates new version)
    active = await prompt_repo.get_active_prompt("rollback_test")
    assert active is not None
    assert active.version == 3
    # Verify content matches v1
    assert active.template_json["system"] == "v1"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_analytics_summary(prompt_repo, adapter_with_db, async_session):
    """Test analytics summary after multiple executions."""
    # Use existing rationale_generation prompt from migration 0013
    prompt = await prompt_repo.get_active_prompt("rationale_generation")
    if not prompt:
        pytest.skip("Migration 0013 should have seeded rationale_generation")

    # Update mock to return rationale format
    adapter_with_db.model.ainvoke = AsyncMock(
        return_value={"rationale_text": "Test rationale"}
    )

    # Execute multiple times
    for i in range(5):
        await adapter_with_db.generate_rationale(
            question_text="What is Python?",
            ideal_answer="Python is...",
            context={"interview_id": f"test-{i}"},
        )

    await async_session.commit()

    # Get analytics
    analytics = await prompt_repo.get_analytics_summary("rationale_generation")

    assert analytics is not None
    assert analytics["total_executions"] >= 5
    assert analytics["avg_latency_ms"] > 0
    assert analytics["success_rate"] >= 0.8  # At least 80% success


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.performance
async def test_db_overhead_benchmark(prompt_repo, adapter_with_db):
    """Benchmark DB prompt loading overhead vs PROMPT_REGISTRY fallback."""
    import time

    # Update mock to return consistent response
    adapter_with_db.model.ainvoke = AsyncMock(
        return_value={"rationale_text": "Test rationale"}
    )

    # Test with DB
    db_times = []
    for _ in range(50):
        start = time.perf_counter()
        await adapter_with_db.generate_rationale(
            question_text="Test question",
            ideal_answer="Test answer",
            context={},
        )
        db_times.append((time.perf_counter() - start) * 1000)  # ms

    # Test with fallback (disable DB)
    adapter_with_db.prompt_repo = None
    fallback_times = []
    for _ in range(50):
        start = time.perf_counter()
        await adapter_with_db.generate_rationale(
            question_text="Test question",
            ideal_answer="Test answer",
            context={},
        )
        fallback_times.append((time.perf_counter() - start) * 1000)

    # Calculate stats
    import statistics

    db_avg = statistics.mean(db_times)
    fallback_avg = statistics.mean(fallback_times)
    overhead = db_avg - fallback_avg

    print(f"\n=== Performance Benchmark ===")
    print(f"DB Avg: {db_avg:.2f}ms")
    print(f"Fallback Avg: {fallback_avg:.2f}ms")
    print(f"Overhead: {overhead:.2f}ms ({overhead/db_avg*100:.1f}%)")

    # Assert overhead < 10ms target
    assert overhead < 10, f"DB overhead {overhead:.2f}ms exceeds 10ms target"

