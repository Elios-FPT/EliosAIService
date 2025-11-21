# Phase 5: Update Tests

**Phase ID**: 05
**Plan**: 251121-1654-db-prompt-migration
**Estimated Effort**: 2-3 hours
**Complexity**: MEDIUM
**Status**: PENDING
**Depends On**: Phase 1 (Helpers), Phase 2 (Refactored Methods), Phase 3 (Logging), Phase 4 (Migration)

---

## Objective

Create comprehensive test coverage for DB-driven prompt loading, fallback behavior, execution logging, and analytics to ensure system reliability and backward compatibility.

**Principle Applied**: SOLID - Testing as documentation (tests define expected behavior)

---

## Test Structure

```
tests/
├── unit/
│   └── adapters/
│       └── llm/
│           ├── test_langchain_adapter_helpers.py (Phase 1)
│           ├── test_langchain_adapter_db_prompts.py (Phase 2)
│           └── test_execution_logging.py (Phase 3)
└── integration/
    └── adapters/
        └── llm/
            └── test_langchain_adapter_db_integration.py (NEW)
```

**Total Tests**: ~35 tests across 4 files

---

## Unit Tests (Fast, No DB)

### File 1: test_langchain_adapter_helpers.py

**Purpose**: Test helper methods from Phase 1

#### Tests (5 total):
1. `test_load_prompt_from_db_success` - DB returns prompt
2. `test_load_prompt_from_db_not_found` - DB returns None (fallback)
3. `test_load_prompt_from_db_exception` - DB throws exception (fallback)
4. `test_load_prompt_from_db_no_repo` - prompt_repo is None (fallback)
5. `test_log_execution_success` - Successful execution logging

**Already documented in Phase 1**

---

### File 2: test_langchain_adapter_db_prompts.py

**Purpose**: Test refactored methods from Phase 2 use DB prompts

#### Test Template (Per Method)

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from src.adapters.llm.langchain_adapter import LangChainAdapter
from src.domain.models.prompt_template import PromptTemplate


class TestEvaluateAnswerDB:
    """Test evaluate_answer with DB prompt loading."""

    @pytest.fixture
    def mock_prompt_template(self):
        """Create mock prompt template."""
        return PromptTemplate(
            id=uuid4(),
            name="answer_evaluation",
            version=2,
            template_json={
                "system": "You are an expert evaluator.",
                "user_template": "Question: {question_text}\nAnswer: {answer_text}"
            },
            created_by="test",
        )

    @pytest.fixture
    def mock_prompt_repo(self, mock_prompt_template):
        """Mock PromptRepository."""
        repo = AsyncMock()
        repo.get_active_prompt.return_value = mock_prompt_template
        repo.log_execution.return_value = None
        return repo

    @pytest.fixture
    def mock_model(self):
        """Mock LangChain model."""
        model = MagicMock()
        model.model_name = "gpt-4"
        model.ainvoke = AsyncMock(return_value={
            "score": 85.0,
            "feedback": "Good answer",
            "strengths": ["Clear explanation"],
            "weaknesses": ["Missing examples"],
            "missing_concepts": ["Error handling"]
        })
        return model

    @pytest.mark.asyncio
    async def test_evaluate_answer_with_db_prompt(
        self, mock_prompt_repo, mock_model, mock_prompt_template
    ):
        """Test evaluate_answer loads DB prompt and logs execution."""
        # Setup
        adapter = LangChainAdapter(
            model=mock_model,
            prompt_repository=mock_prompt_repo
        )

        question = MagicMock()
        question.text = "What is Python?"
        question.difficulty = "MEDIUM"
        question.skills = ["Python"]
        question.id = uuid4()

        # Execute
        result = await adapter.evaluate_answer(
            question=question,
            answer_text="Python is a programming language...",
            context={"interview_id": "test-123"}
        )

        # Assertions
        assert result.score == 85.0
        assert result.reasoning == "Good answer"
        assert "Clear explanation" in result.strengths

        # Verify DB prompt loaded
        mock_prompt_repo.get_active_prompt.assert_called_once_with("answer_evaluation")

        # Verify execution logged
        mock_prompt_repo.log_execution.assert_called_once()
        log_call = mock_prompt_repo.log_execution.call_args
        assert log_call[1]["prompt_template_id"] == mock_prompt_template.id
        assert log_call[1]["execution_data"]["success"] is True

    @pytest.mark.asyncio
    async def test_evaluate_answer_fallback_to_registry(
        self, mock_prompt_repo, mock_model
    ):
        """Test evaluate_answer falls back to PROMPT_REGISTRY when DB fails."""
        # Simulate DB failure
        mock_prompt_repo.get_active_prompt.return_value = None

        # Setup adapter
        adapter = LangChainAdapter(
            model=mock_model,
            prompt_repository=mock_prompt_repo
        )

        question = MagicMock()
        question.text = "What is Python?"
        question.difficulty = "MEDIUM"
        question.skills = ["Python"]
        question.id = uuid4()

        # Execute (should still work with PROMPT_REGISTRY)
        result = await adapter.evaluate_answer(
            question=question,
            answer_text="Python is a programming language...",
            context={}
        )

        # Should still work
        assert result.score == 85.0

        # No execution logging (no DB prompt)
        mock_prompt_repo.log_execution.assert_not_called()

    @pytest.mark.asyncio
    async def test_evaluate_answer_db_exception_fallback(
        self, mock_prompt_repo, mock_model
    ):
        """Test evaluate_answer handles DB exception gracefully."""
        # Simulate DB exception
        mock_prompt_repo.get_active_prompt.side_effect = Exception("DB connection lost")

        # Setup adapter
        adapter = LangChainAdapter(
            model=mock_model,
            prompt_repository=mock_prompt_repo
        )

        question = MagicMock()
        question.text = "What is Python?"
        question.difficulty = "MEDIUM"
        question.skills = ["Python"]
        question.id = uuid4()

        # Execute (should fall back gracefully)
        result = await adapter.evaluate_answer(
            question=question,
            answer_text="Python is a programming language...",
            context={}
        )

        # Should still work with PROMPT_REGISTRY
        assert result.score == 85.0

    @pytest.mark.asyncio
    async def test_evaluate_answer_execution_failure_logged(
        self, mock_prompt_repo, mock_model, mock_prompt_template
    ):
        """Test evaluate_answer logs execution failure."""
        # Simulate chain execution failure
        mock_model.ainvoke.side_effect = Exception("LLM timeout")

        # Setup adapter
        adapter = LangChainAdapter(
            model=mock_model,
            prompt_repository=mock_prompt_repo
        )

        question = MagicMock()
        question.text = "What is Python?"
        question.difficulty = "MEDIUM"
        question.skills = ["Python"]
        question.id = uuid4()

        # Execute (should raise exception)
        with pytest.raises(Exception, match="LLM timeout"):
            await adapter.evaluate_answer(
                question=question,
                answer_text="Python is...",
                context={"interview_id": "test-123"}
            )

        # Verify failure logged
        mock_prompt_repo.log_execution.assert_called_once()
        log_call = mock_prompt_repo.log_execution.call_args
        assert log_call[1]["execution_data"]["success"] is False
        assert "LLM timeout" in log_call[1]["execution_data"]["error_message"]
```

#### Apply Template to All 9 Methods

**Test Class Structure**:
1. `TestEvaluateAnswerDB` (4 tests)
2. `TestGenerateRationaleDB` (4 tests)
3. `TestDetectConceptGapsDB` (4 tests)
4. `TestGenerateFollowupQuestionDB` (4 tests)
5. `TestGenerateFeedbackReportDB` (4 tests)
6. `TestSummarizeCVDB` (4 tests)
7. `TestExtractSkillsDB` (4 tests)
8. `TestGenerateRecommendationsDB` (4 tests)
9. `TestGenerateIdealAnswerDB` (2 tests - already has DB loading, only test logging enhancement)

**Total**: 34 unit tests

---

### File 3: test_execution_logging.py

**Purpose**: Test execution logging from Phase 3

#### Tests (6 total):
1. `test_extract_token_usage_openai` - OpenAI token format
2. `test_extract_token_usage_anthropic` - Anthropic token format
3. `test_extract_token_usage_missing` - No token data
4. `test_estimate_cost_gpt4` - GPT-4 pricing
5. `test_estimate_cost_unknown_model` - Unknown model returns None
6. `test_sanitize_variables_pii` - Email/phone redaction

**Already documented in Phase 3**

---

## Integration Tests (Slow, Real DB)

### File 4: test_langchain_adapter_db_integration.py

**Purpose**: End-to-end tests with real PostgreSQL database

#### Test Setup

```python
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from langchain_openai import ChatOpenAI

from src.adapters.llm.langchain_adapter import LangChainAdapter
from src.adapters.persistence.postgres_prompt_repository import PostgreSQLPromptRepository
from src.domain.models.question import Question
from tests.fixtures.database import get_test_db_url


@pytest_asyncio.fixture
async def db_session():
    """Create test database session."""
    engine = create_async_engine(get_test_db_url(), echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        yield session
        await session.rollback()

    await engine.dispose()


@pytest_asyncio.fixture
async def prompt_repo(db_session):
    """Create PromptRepository with test DB."""
    return PostgreSQLPromptRepository(db_session)


@pytest_asyncio.fixture
async def adapter_with_db(prompt_repo):
    """Create LangChainAdapter with real DB and mock model."""
    # Use mock model to avoid OpenAI API calls in tests
    from unittest.mock import AsyncMock, MagicMock

    mock_model = MagicMock()
    mock_model.model_name = "gpt-3.5-turbo"
    mock_model.ainvoke = AsyncMock(return_value={
        "score": 80.0,
        "feedback": "Test feedback",
        "strengths": ["Good structure"],
        "weaknesses": ["Missing depth"],
        "missing_concepts": []
    })

    return LangChainAdapter(
        model=mock_model,
        prompt_repository=prompt_repo
    )


@pytest_asyncio.fixture
async def seeded_prompt(prompt_repo):
    """Seed test prompt in DB."""
    prompt = await prompt_repo.create_initial_prompt(
        name="test_prompt",
        template_json={
            "system": "You are a test system.",
            "user_template": "Question: {question}\nAnswer: {answer}"
        },
        created_by="test",
    )

    # Activate prompt
    await prompt_repo.activate_version(
        prompt_id=prompt.id,
        changed_by="test",
        reason="Test setup",
        traffic_percentage=100
    )

    return prompt
```

---

#### Integration Test 1: Full Cycle (Seed → Execute → Verify Logging)

```python
@pytest.mark.asyncio
@pytest.mark.integration
async def test_full_cycle_evaluate_answer(
    adapter_with_db, prompt_repo, db_session
):
    """Test full cycle: seed prompt → execute → verify execution logged."""

    # Step 1: Seed prompt (use existing answer_evaluation from migration 0013)
    prompt = await prompt_repo.get_active_prompt("answer_evaluation")
    assert prompt is not None, "Migration 0013 should have seeded answer_evaluation"

    # Step 2: Execute method
    question = Question(
        text="What is Python?",
        difficulty="MEDIUM",
        skills=["Python"],
        question_type="TECHNICAL"
    )

    result = await adapter_with_db.evaluate_answer(
        question=question,
        answer_text="Python is a high-level programming language...",
        context={"interview_id": "test-integration-123"}
    )

    # Step 3: Verify execution
    assert result.score > 0

    # Step 4: Verify execution logged
    await db_session.commit()  # Flush execution logs

    analytics = await prompt_repo.get_analytics_summary("answer_evaluation")
    assert analytics is not None
    assert analytics["total_executions"] >= 1
    assert analytics["success_rate"] >= 0.0
```

---

#### Integration Test 2: A/B Testing (Multiple Active Prompts)

```python
@pytest.mark.asyncio
@pytest.mark.integration
async def test_ab_testing_weighted_selection(prompt_repo, adapter_with_db):
    """Test A/B testing: multiple active prompts with traffic split."""

    # Create v1 (50% traffic)
    v1 = await prompt_repo.create_initial_prompt(
        name="ab_test_prompt",
        template_json={"system": "Version 1", "user_template": "{input}"},
        created_by="test",
    )
    await prompt_repo.activate_version(
        prompt_id=v1.id,
        changed_by="test",
        reason="A/B test v1",
        traffic_percentage=50,
        ab_test_group="control"
    )

    # Create v2 (50% traffic)
    v2 = await prompt_repo.create_new_version(
        name="ab_test_prompt",
        parent_version=1,
        template_json={"system": "Version 2", "user_template": "{input}"},
        change_summary="Test variant",
        created_by="test",
    )
    await prompt_repo.activate_version(
        prompt_id=v2.id,
        changed_by="test",
        reason="A/B test v2",
        traffic_percentage=50,
        ab_test_group="variant"
    )

    # Execute 100 times and track version distribution
    version_counts = {1: 0, 2: 0}

    for _ in range(100):
        selected = await prompt_repo.get_active_prompt("ab_test_prompt")
        version_counts[selected.version] += 1

    # Should be roughly 50/50 (allow ±20% variance)
    assert 30 <= version_counts[1] <= 70
    assert 30 <= version_counts[2] <= 70
```

---

#### Integration Test 3: Prompt Version Rollback

```python
@pytest.mark.asyncio
@pytest.mark.integration
async def test_prompt_rollback(prompt_repo, adapter_with_db):
    """Test rollback to previous prompt version."""

    # Create v1
    v1 = await prompt_repo.create_initial_prompt(
        name="rollback_test",
        template_json={"system": "v1", "user_template": "{input}"},
        created_by="test",
    )
    await prompt_repo.activate_version(v1.id, "test", "Initial", traffic_percentage=100)

    # Create v2 (bad version)
    v2 = await prompt_repo.create_new_version(
        name="rollback_test",
        parent_version=1,
        template_json={"system": "v2 BAD", "user_template": "{input}"},
        change_summary="Bad update",
        created_by="test",
    )
    await prompt_repo.activate_version(v2.id, "test", "Deploy v2", traffic_percentage=100)

    # Verify v2 active
    active = await prompt_repo.get_active_prompt("rollback_test")
    assert active.version == 2

    # Rollback to v1
    rolled_back = await prompt_repo.rollback_to_version(
        name="rollback_test",
        target_version=1,
        changed_by="test",
        reason="v2 caused issues"
    )

    # Activate rollback version
    await prompt_repo.activate_version(
        rolled_back.id, "test", "Rollback to v1", traffic_percentage=100
    )

    # Verify v3 active (rollback creates new version)
    active = await prompt_repo.get_active_prompt("rollback_test")
    assert active.version == 3
    assert active.template_json == v1.template_json  # Same content as v1
```

---

#### Integration Test 4: Analytics Tracking

```python
@pytest.mark.asyncio
@pytest.mark.integration
async def test_analytics_summary(prompt_repo, adapter_with_db, db_session):
    """Test analytics summary after multiple executions."""

    # Execute multiple times
    for i in range(5):
        await adapter_with_db.generate_rationale(
            question_text="What is Python?",
            ideal_answer="Python is...",
            context={"interview_id": f"test-{i}"}
        )

    await db_session.commit()

    # Get analytics
    analytics = await prompt_repo.get_analytics_summary("rationale_generation")

    assert analytics is not None
    assert analytics["total_executions"] >= 5
    assert analytics["avg_latency_ms"] > 0
    assert analytics["success_rate"] >= 0.8  # At least 80% success
```

---

## Performance Tests

### Test 5: DB Overhead Benchmark

```python
@pytest.mark.asyncio
@pytest.mark.performance
async def test_db_overhead_benchmark(prompt_repo, adapter_with_db):
    """Benchmark DB prompt loading overhead vs PROMPT_REGISTRY fallback."""
    import time

    # Test with DB
    db_times = []
    for _ in range(50):
        start = time.perf_counter()
        await adapter_with_db.generate_rationale(
            question_text="Test question",
            ideal_answer="Test answer",
            context={}
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
            context={}
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
```

---

## Test Coverage Requirements

### Coverage Targets
- **Unit Tests**: >95% coverage on refactored methods
- **Integration Tests**: >80% coverage on DB interactions
- **Overall**: >90% coverage on langchain_adapter.py

### Run Coverage Report

```bash
# Run all tests with coverage
pytest tests/unit/adapters/llm/ tests/integration/adapters/llm/ \
    --cov=src/adapters/llm/langchain_adapter \
    --cov-report=html \
    --cov-report=term-missing

# View report
open htmlcov/index.html
```

---

## Test Execution Strategy

### Local Development
```bash
# Run fast unit tests only (mock DB)
pytest tests/unit/ -v

# Run integration tests (requires PostgreSQL)
pytest tests/integration/ -v -m integration

# Run performance tests
pytest tests/ -v -m performance
```

### CI/CD Pipeline
```yaml
# .github/workflows/test.yml
test:
  runs-on: ubuntu-latest
  services:
    postgres:
      image: postgres:15
      env:
        POSTGRES_PASSWORD: test
      options: >-
        --health-cmd pg_isready
        --health-interval 10s
        --health-timeout 5s
        --health-retries 5

  steps:
    - uses: actions/checkout@v3
    - uses: actions/setup-python@v4

    - name: Install dependencies
      run: pip install -e ".[dev]"

    - name: Run migrations
      run: alembic upgrade head

    - name: Run unit tests
      run: pytest tests/unit/ --cov --cov-report=xml

    - name: Run integration tests
      run: pytest tests/integration/ -m integration

    - name: Upload coverage
      uses: codecov/codecov-action@v3
```

---

## Acceptance Criteria

### Unit Tests
- [ ] 34 unit tests pass (DB loading + fallback)
- [ ] All 9 refactored methods tested (4 scenarios each)
- [ ] Mock PromptRepository behaves correctly
- [ ] Execution logging verified

### Integration Tests
- [ ] 5 integration tests pass with real PostgreSQL
- [ ] Full cycle (seed → execute → verify) works
- [ ] A/B testing (weighted selection) works
- [ ] Prompt rollback works
- [ ] Analytics tracking works

### Performance
- [ ] DB overhead <10ms (benchmark test passes)
- [ ] No memory leaks (cache bounded)

### Coverage
- [ ] >95% unit test coverage
- [ ] >80% integration test coverage
- [ ] >90% overall coverage on langchain_adapter.py

---

## Files Created

```
tests/unit/adapters/llm/test_langchain_adapter_helpers.py
  - 5 tests for Phase 1 helpers

tests/unit/adapters/llm/test_langchain_adapter_db_prompts.py (NEW)
  - 34 tests for Phase 2 refactored methods

tests/unit/adapters/llm/test_execution_logging.py
  - 6 tests for Phase 3 logging

tests/integration/adapters/llm/test_langchain_adapter_db_integration.py (NEW)
  - 5 integration tests

tests/fixtures/database.py (NEW)
  - Test database fixtures
```

**Total**: ~50 tests

---

## Next Phase

**Phase 6**: [Code Review & Documentation](./phase-06-code-review.md)

Self-review against Clean Architecture, SOLID principles, security standards, and update documentation.

---

**END OF PHASE 5**
