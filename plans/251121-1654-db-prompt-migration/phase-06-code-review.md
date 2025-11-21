# Phase 6: Code Review & Documentation

**Phase ID**: 06
**Plan**: 251121-1654-db-prompt-migration
**Estimated Effort**: 1 hour
**Complexity**: LOW
**Status**: PENDING
**Depends On**: Phases 1-5 (All implementation complete)

---

## Objective

Perform comprehensive self-review against architecture principles, code standards, security requirements, and update project documentation to reflect DB-driven prompt system.

**Principle Applied**: SOLID - Review ensures adherence to all principles

---

## Code Review Checklist

### 1. Clean Architecture Compliance

#### Domain Layer Integrity
- [ ] Domain models (PromptTemplate, PromptExecution) contain NO infrastructure dependencies
- [ ] Domain ports (PromptRepositoryPort) define interface contracts only
- [ ] No adapter logic leaked into domain layer

**Verification**:
```bash
# Check domain imports (should only import other domain modules)
rg "from src\.(adapters|infrastructure)" src/domain/
# Expected: No matches
```

---

#### Dependency Inversion
- [ ] LangChainAdapter depends on PromptRepositoryPort (interface), NOT PostgreSQLPromptRepository (concrete)
- [ ] Constructor injection: `__init__(self, model, prompt_repository: PromptRepositoryPort | None)`
- [ ] No direct database imports in adapter

**Verification**:
```python
# Check LangChainAdapter imports
rg "from src\.adapters\.persistence\.postgres" src/adapters/llm/langchain_adapter.py
# Expected: No matches (should only import PromptRepositoryPort from domain)
```

---

#### Adapter Layer Isolation
- [ ] LangChainAdapter is ONLY place DB prompt logic exists
- [ ] No DB prompt loading in domain services or use cases
- [ ] Fallback to PROMPT_REGISTRY preserves adapter boundary

**Verification**:
```bash
# Check for PromptRepository usage outside adapters
rg "PromptRepositoryPort" src/domain/services/ src/application/
# Expected: No matches (ports used only in adapters)
```

---

### 2. SOLID Principles

#### Single Responsibility Principle
- [ ] `_load_prompt_from_db()` does ONE thing: load prompt from DB
- [ ] `_log_execution()` does ONE thing: log execution to DB
- [ ] Each refactored method has ONE responsibility (execute chain + log)

**Review Points**:
- Helper methods <50 lines
- No mixed concerns (DB + business logic)
- Clear separation: load → execute → log

---

#### Open/Closed Principle
- [ ] Adding new prompts requires NO changes to LangChainAdapter code (only migration)
- [ ] New LLM methods follow same pattern (no adapter refactor needed)
- [ ] PROMPT_REGISTRY remains untouched (fallback preserved)

**Test**: Create new prompt without modifying adapter
```python
# Should work by only adding migration + PROMPT_REGISTRY entry
await adapter.new_method(..., context={})
```

---

#### Liskov Substitution Principle
- [ ] PostgreSQLPromptRepository fully implements PromptRepositoryPort
- [ ] Mock PromptRepository works identically in tests
- [ ] No violations of interface contract (e.g., unexpected exceptions)

**Verification**:
```bash
# Check all abstract methods implemented
python -c "
from src.domain.ports.prompt_repository_port import PromptRepositoryPort
from src.adapters.persistence.postgres_prompt_repository import PostgreSQLPromptRepository
import inspect

port_methods = {m for m in dir(PromptRepositoryPort) if not m.startswith('_')}
impl_methods = {m for m in dir(PostgreSQLPromptRepository) if not m.startswith('_')}
missing = port_methods - impl_methods
print(f'Missing methods: {missing}' if missing else 'All methods implemented ✅')
"
```

---

#### Interface Segregation Principle
- [ ] PromptRepositoryPort is focused (version control + analytics only)
- [ ] No god interface (LLMPort + PromptRepository NOT combined)
- [ ] Clients (LangChainAdapter) use only needed interface methods

**Review Points**:
- PromptRepositoryPort has ~13 methods (reasonable)
- Each method has clear, single purpose
- No unused methods in interface

---

#### Dependency Inversion Principle
- [ ] High-level policy (LangChainAdapter) depends on abstraction (PromptRepositoryPort)
- [ ] Low-level details (PostgreSQL) pluggable via DI container
- [ ] Can swap PostgreSQL for MongoDB without changing adapter

**Verification**:
```python
# Test with different repository implementation
from tests.mocks import MockPromptRepository

adapter = LangChainAdapter(model, prompt_repository=MockPromptRepository())
# Should work identically (interface compliance)
```

---

### 3. Security Review

#### PII Handling
- [ ] `_sanitize_variables()` removes emails, phones from logs
- [ ] CV text truncated to 500 chars in logs (no full CV content)
- [ ] Candidate names NOT logged (use candidate_id instead)

**Verification**:
```python
# Test sanitization
test_input = {
    "cv_text": "John Doe, john.doe@example.com, (555) 123-4567",
    "question": "What is Python?"
}
sanitized = adapter._sanitize_variables(test_input)
assert "john.doe@example.com" not in str(sanitized)
assert "[EMAIL_REDACTED]" in str(sanitized)
assert "(555) 123-4567" not in str(sanitized)
```

---

#### SQL Injection Prevention
- [ ] All DB queries use parameterized queries (SQLAlchemy ORM)
- [ ] No raw SQL with string interpolation
- [ ] Alembic migrations use `sa.text()` with parameters

**Verification**:
```bash
# Check for SQL injection risks
rg "execute\(f\"|execute\(\"[^:]*{" alembic/versions/ src/adapters/persistence/
# Expected: No matches (should use parameterized queries)
```

---

#### Secrets Management
- [ ] No API keys in logs (input_variables sanitized)
- [ ] No database passwords in code (env vars only)
- [ ] LangSmith API key NOT in execution logs

**Verification**:
```bash
# Check for hardcoded secrets
rg "api_key\s*=\s*['\"]" src/
# Expected: No matches
```

---

#### Error Message Exposure
- [ ] Error messages don't leak internal system details
- [ ] Stack traces NOT logged to prompt_executions (error_message only)
- [ ] User-facing errors sanitized (no SQL errors exposed)

**Review Points**:
- Exception messages truncated to 500 chars
- No full stack traces in DB logs
- Detailed logs only in application logger (not DB)

---

### 4. Performance Review

#### Database Query Optimization
- [ ] `get_active_prompt()` uses index on (name, is_active)
- [ ] `log_execution()` is async (no blocking)
- [ ] Batch logging NOT needed (individual executions fine)

**Verification**:
```sql
-- Check indexes exist
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'prompt_templates'
AND indexdef LIKE '%name%is_active%';
-- Expected: Index exists
```

---

#### Caching Strategy
- [ ] `_db_chain_cache` bounded (no memory leaks)
- [ ] Cache key includes version (`prompt_name:vN`)
- [ ] Cache invalidated on prompt update (version change)

**Review Points**:
- Cache stores chains, NOT raw prompts (chains reusable)
- No cache expiration needed (version changes trigger new cache entry)
- Max cache size: ~50 chains (13 methods × ~4 versions)

---

#### Token Tracking Overhead
- [ ] Token extraction <1ms (simple dict lookups)
- [ ] No LLM calls for token tracking (metadata only)
- [ ] Logging async (doesn't block chain execution)

**Benchmark**:
```python
# scripts/benchmark_token_extraction.py
import time

metadata = {"usage": {"total_tokens": 150, "prompt_tokens": 100, "completion_tokens": 50}}

start = time.perf_counter()
for _ in range(10000):
    adapter._extract_token_usage(metadata, "gpt-4")
elapsed = (time.perf_counter() - start) * 1000

print(f"Token extraction: {elapsed/10000:.4f}ms per call")
# Expected: <0.01ms per call
```

---

### 5. Code Quality Standards

#### Type Hints
- [ ] All methods fully typed (parameters + return types)
- [ ] No `Any` types except dict contents (context, variables)
- [ ] Optional types explicit (`| None`, not `Optional[]`)

**Verification**:
```bash
# Run mypy type checking
mypy src/adapters/llm/langchain_adapter.py
# Expected: No errors
```

---

#### Docstrings
- [ ] All public methods have docstrings (Google style)
- [ ] Docstrings include Args, Returns, Raises
- [ ] Examples provided for complex methods

**Review Points**:
- 100% docstring coverage on public methods
- Private helpers (_methods) have brief docstrings
- Examples for `_load_prompt_from_db()`, `_log_execution()`

---

#### Code Linting
- [ ] Passes `ruff check src/` (no errors)
- [ ] Passes `black src/` (formatted)
- [ ] No unused imports or variables

**Run Checks**:
```bash
# Run all quality checks
black src/adapters/llm/langchain_adapter.py
ruff check src/adapters/llm/langchain_adapter.py --fix
mypy src/adapters/llm/langchain_adapter.py

# Expected: All pass ✅
```

---

#### Line Length & Complexity
- [ ] Max line length: 100 chars (black default)
- [ ] No methods >100 lines (largest: ~80 lines)
- [ ] Cyclomatic complexity <10 per method

**Check Complexity**:
```bash
# Install radon
pip install radon

# Check complexity
radon cc src/adapters/llm/langchain_adapter.py -a
# Expected: Average complexity A-B (low)
```

---

### 6. Testing Coverage

#### Coverage Metrics
- [ ] >95% line coverage on langchain_adapter.py
- [ ] >90% branch coverage (all fallback paths tested)
- [ ] 100% coverage on helper methods (_load_prompt_from_db, _log_execution)

**Run Coverage**:
```bash
pytest tests/unit/adapters/llm/ \
    --cov=src/adapters/llm/langchain_adapter \
    --cov-report=term-missing \
    --cov-report=html

# Expected: >95% coverage
```

---

#### Test Quality
- [ ] All tests isolated (no shared state)
- [ ] Mock dependencies properly (PromptRepository, LLM model)
- [ ] Integration tests use test database (not dev/prod)

**Review Points**:
- Fixtures properly scoped (function, class, module)
- No sleeps in tests (use mock time.time())
- Assertions specific (not just `assert result`)

---

### 7. Error Handling Review

#### Exception Handling
- [ ] All DB exceptions caught and logged (no crashes)
- [ ] Fallback to PROMPT_REGISTRY on ANY DB error
- [ ] Execution logging failures don't break main operation

**Review Points**:
- Try-except blocks in ALL DB operations
- Logging uses `exc_info=True` (stack traces in logs)
- Re-raise exceptions AFTER logging (if critical)

---

#### Retry Logic
- [ ] `_log_execution_with_retry()` has max 3 attempts
- [ ] Exponential backoff (0.1s, 0.2s, 0.4s)
- [ ] Transient errors retried (connection lost), logic errors NOT retried

**Test**:
```python
# Simulate transient failure
mock_repo.log_execution.side_effect = [
    Exception("Connection lost"),  # Retry
    Exception("Connection lost"),  # Retry
    None  # Success
]
await adapter._log_execution_with_retry(...)
assert mock_repo.log_execution.call_count == 3
```

---

## Documentation Updates

### Update 1: CLAUDE.md

**Section**: Working with the Codebase → Prompt Management

**Add**:
```markdown
### Prompt Version Control

**DB-Driven Prompts** (v0.3.0+): LangChainAdapter loads prompts from PostgreSQL for version control and A/B testing.

**Workflow**:
1. **Create Prompt**: Seed via Alembic migration (see `alembic/versions/0013_*.py`)
2. **Update Prompt**: Create new version via PromptRepositoryPort
3. **A/B Test**: Activate multiple versions with traffic split
4. **Rollback**: Revert to previous version (immutable versioning)

**Fallback**: If DB unavailable, methods fall back to PROMPT_REGISTRY (hardcoded prompts).

**Analytics**: All executions logged to `prompt_executions` table (tokens, latency, cost).

**Example**:
```python
# Adapter automatically loads from DB
result = await adapter.evaluate_answer(
    question=question,
    answer_text="...",
    context={"interview_id": "123"}  # Required for logging
)

# Check analytics
analytics = await prompt_repo.get_analytics_summary("answer_evaluation")
print(f"Avg tokens: {analytics['avg_tokens_used']}")
```

**Migration Guide**: See `plans/251121-1654-db-prompt-migration/plan.md`
```

---

### Update 2: docs/system-architecture.md

**Section**: Adapters Layer → LLM Adapters

**Add**:
```markdown
#### LangChainAdapter - DB-Driven Prompts

**Prompt Loading Strategy**:
1. Load active prompt from DB (via PromptRepositoryPort)
2. Build LangChain LCEL chain from DB template
3. Cache chain (keyed by `prompt_name:vN`)
4. Execute chain with input variables
5. Log execution (tokens, latency, cost) to DB

**Fallback Mechanism**:
- If DB unavailable: Use PROMPT_REGISTRY (hardcoded prompts)
- If invalid template: Fallback + log warning
- If logging fails: Continue execution (logging non-critical)

**Execution Logging**:
- **Tracked Metrics**: tokens_used, latency_ms, model_name, success, cost_usd
- **Analytics View**: `prompt_analytics_summary` (materialized view)
- **PII Protection**: Input variables sanitized (emails/phones redacted)

**Performance**:
- **DB Overhead**: <10ms per execution (cached chains)
- **Cache Hit Rate**: >90% (version-based caching)
- **Logging Latency**: <5ms (async, non-blocking)
```

---

### Update 3: docs/code-standards.md

**Section**: LangChain LCEL Chain Patterns

**Add**:
```markdown
#### DB-Driven Prompt Loading

**Pattern** (Standard across all LangChainAdapter methods):

```python
async def method_name(self, arg: str, context: dict[str, Any]) -> ReturnType:
    """Method docstring."""
    start_time = time.time()

    # 1. Load DB prompt
    prompt_template, template_json, cache_key = await self._load_prompt_from_db("db_prompt_name")

    # 2. Get chain (DB or fallback)
    chain = self._get_or_build_chain("method_name", template_json, cache_key)

    # 3. Prepare variables
    variables = {"arg": arg}
    config = self._create_config(context=context, method="method_name")

    # 4. Execute chain
    try:
        result = await chain.ainvoke(variables, config)
        metadata = self._extract_response_metadata(result)

        # 5. Log execution
        if prompt_template:
            await self._log_execution(
                prompt_template=prompt_template,
                context=context,
                input_variables=variables,
                output_text=result["output_field"],
                start_time=start_time,
                success=True,
                model_response_metadata=metadata,
            )

        return result["output_field"]

    except Exception as exc:
        if prompt_template:
            await self._log_execution(
                prompt_template=prompt_template,
                context=context,
                input_variables=variables,
                output_text=None,
                start_time=start_time,
                success=False,
                error_message=str(exc),
            )
        raise
```

**Key Points**:
- Always pass `context` parameter (for logging)
- Handle exceptions gracefully (log failure, then raise)
- Extract metadata for token tracking
- Fallback automatic (no error handling needed in method)
```

---

### Update 4: README.md

**Section**: Key Features

**Add**:
```markdown
- **Prompt Version Control**: Database-driven prompts with version history, A/B testing, and rollback support
```

**Section**: Configuration

**Add**:
```markdown
### Prompt Management (Optional)

Enable DB-driven prompts for version control and analytics:

```env
# Prompt repository (requires PostgreSQL)
ENABLE_PROMPT_VERSIONING=true  # Default: true
```

If disabled, LangChainAdapter falls back to hardcoded PROMPT_REGISTRY.
```

---

## Rollback Procedure

### Emergency Rollback (Production Issues)

**Scenario**: DB prompt system causing production failures

**Steps**:

1. **Immediate**: Disable DB prompts (env var)
```bash
# .env.production
ENABLE_PROMPT_VERSIONING=false

# Restart service
systemctl restart elios-ai-service
```

2. **Revert Code** (if needed)
```bash
# Revert to commit before Phase 1
git revert <commit-hash>
git push origin main

# Deploy previous version
./deploy.sh production
```

3. **Database Rollback** (if needed)
```bash
# Rollback migration 0014 (remove 3 new prompts)
alembic downgrade -1

# Verify 7 prompts remain
psql -c "SELECT COUNT(*) FROM prompt_templates;"
# Expected: 7
```

4. **Verify Service**
```bash
# Check logs for errors
tail -f /var/log/elios/app.log | grep -i "prompt"

# Test interview flow
curl -X POST http://localhost:8000/api/interviews/test
```

---

## Performance Benchmark Report

**Run After Implementation**:

```bash
python scripts/benchmark_db_prompts.py
```

**Expected Output**:
```
=== DB Prompt Performance Benchmark ===
Method: evaluate_answer
  DB: 45.2ms per call (avg 50 iterations)
  Fallback: 38.1ms per call
  Overhead: 7.1ms (15.7%)

Method: generate_rationale
  DB: 32.5ms per call
  Fallback: 28.3ms per call
  Overhead: 4.2ms (14.8%)

=== Overall ===
Average DB Overhead: 5.8ms (12.5%)
Target: <10ms ✅

=== Cache Performance ===
Cache Hit Rate: 94.2%
Cache Size: 12 chains (of 13 max)

=== Token Tracking ===
Token Extraction: 0.008ms per call
Cost Estimation: 0.012ms per call
PII Sanitization: 1.2ms per call

✅ All performance targets met
```

**Acceptance**: Overhead <10ms, cache hit rate >90%

---

## Sign-off Checklist

### Architecture
- [ ] Clean Architecture compliance verified (domain isolated)
- [ ] SOLID principles followed (all 5 principles)
- [ ] Dependency Inversion: adapters depend on ports

### Security
- [ ] PII sanitization tested (emails/phones redacted)
- [ ] No SQL injection risks (parameterized queries)
- [ ] No secrets in logs (API keys sanitized)

### Performance
- [ ] DB overhead <10ms (benchmark passed)
- [ ] Cache hit rate >90%
- [ ] Token extraction <1ms

### Testing
- [ ] >95% unit test coverage
- [ ] >80% integration test coverage
- [ ] All 50 tests pass

### Code Quality
- [ ] Passes ruff, black, mypy (no errors)
- [ ] All methods documented (docstrings)
- [ ] Line length <100 chars, complexity <10

### Documentation
- [ ] CLAUDE.md updated (prompt management workflow)
- [ ] system-architecture.md updated (DB-driven prompts)
- [ ] code-standards.md updated (DB loading pattern)
- [ ] README.md updated (configuration)

---

## Final Verification

**Run Full Test Suite**:
```bash
# Code quality
black src/ && ruff check src/ --fix && mypy src/

# Unit tests
pytest tests/unit/ --cov=src --cov-report=html

# Integration tests
pytest tests/integration/ -m integration

# Performance benchmarks
python scripts/benchmark_db_prompts.py

# Expected: All pass ✅
```

---

## Post-Implementation Monitoring

**Week 1**: Monitor production metrics
- DB prompt usage rate (target: >95%)
- Fallback rate (target: <1%)
- Execution logging errors (target: <0.1%)
- Average latency (target: <50ms)

**Alerts** (set up in monitoring system):
- ⚠️ DB fallback rate >5%
- ⚠️ Execution logging failure rate >1%
- 🔥 Average latency >100ms
- 🔥 Error rate >5%

---

## Acceptance Criteria

### Code Review
- [ ] All 7 review sections completed (Architecture, SOLID, Security, Performance, Code Quality, Testing, Error Handling)
- [ ] No critical issues found
- [ ] All acceptance criteria met

### Documentation
- [ ] 4 documentation files updated (CLAUDE.md, system-architecture.md, code-standards.md, README.md)
- [ ] Prompt management workflow documented
- [ ] Rollback procedure documented

### Performance
- [ ] Benchmark report generated
- [ ] All performance targets met (overhead <10ms)

### Sign-off
- [ ] All checklist items completed
- [ ] Full test suite passes
- [ ] Ready for production deployment

---

**END OF PHASE 6**

---

**END OF PLAN: 251121-1654-db-prompt-migration**

**Status**: READY FOR IMPLEMENTATION

**Next Steps**:
1. Review plan with team
2. Begin Phase 1: Create Helper Methods
3. Update plan.md status as phases complete
4. Create pull request after Phase 6

**Estimated Total Effort**: 8-12 hours (across 6 phases)
