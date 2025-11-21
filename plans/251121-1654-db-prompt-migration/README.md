# LangChainAdapter DB-Driven Prompt Migration Plan

**Plan ID**: `251121-1654-db-prompt-migration`
**Created**: 2025-11-21 16:54
**Status**: 📋 READY FOR IMPLEMENTATION
**Complexity**: MEDIUM
**Estimated Effort**: 8-12 hours

---

## 📄 Quick Links

- **[Main Plan](./plan.md)** - Executive summary, architecture, risks, success criteria
- **[Phase 1](./phase-01-create-helper-methods.md)** - Create helper methods (1 hour)
- **[Phase 2](./phase-02-refactor-methods.md)** - Refactor 9 methods (3-4 hours)
- **[Phase 3](./phase-03-add-execution-logging.md)** - Add execution logging (2 hours)
- **[Phase 4](./phase-04-create-migration.md)** - Create migration 0014 (1 hour)
- **[Phase 5](./phase-05-update-tests.md)** - Update tests (2-3 hours)
- **[Phase 6](./phase-06-code-review.md)** - Code review & docs (1 hour)

---

## 🎯 Objective

Migrate `LangChainAdapter` from hardcoded `PROMPT_REGISTRY` to database-driven prompts via `PromptRepositoryPort`. Enable version control, A/B testing, and prompt optimization without code deployments.

---

## 📊 Current State vs Target State

### Current State ❌
- 13 methods use hardcoded PROMPT_REGISTRY
- 1 method (generate_ideal_answer) has DB loading (partial)
- No execution logging (no analytics)
- 3 prompts missing from DB

### Target State ✅
- ALL 13 methods load DB prompts first
- Fallback to PROMPT_REGISTRY if DB fails
- Execution logging tracks tokens, latency, cost
- 10 prompts seeded in DB (7 existing + 3 new)

---

## 🏗️ Implementation Phases

| Phase | Description | Effort | Status |
|-------|-------------|--------|--------|
| **1** | Create Helper Methods | 1 hour | 📋 PENDING |
| **2** | Refactor 9 Methods | 3-4 hours | 📋 PENDING |
| **3** | Add Execution Logging | 2 hours | 📋 PENDING |
| **4** | Create Migration 0014 | 1 hour | 📋 PENDING |
| **5** | Update Tests | 2-3 hours | 📋 PENDING |
| **6** | Code Review & Docs | 1 hour | 📋 PENDING |

**Total**: 8-12 hours

---

## 🎬 Getting Started

### Prerequisites
1. Read [Main Plan](./plan.md) for context
2. Ensure PostgreSQL running (migration 0013 applied)
3. Verify test database exists

### Start Implementation

```bash
# Step 1: Create feature branch
git checkout -b feat/langchain-db-prompts

# Step 2: Start Phase 1
# Read: ./phase-01-create-helper-methods.md
# Implement: Create _load_prompt_from_db(), _log_execution() helpers

# Step 3: Run tests after each phase
pytest tests/unit/adapters/llm/ -v

# Step 4: Proceed through phases sequentially
# Phases 1-3 sequential, Phase 4 can run parallel

# Step 5: Final validation (Phase 6)
black src/ && ruff check src/ && mypy src/
pytest tests/ --cov --cov-report=html
```

---

## 📈 Progress Tracking

Update this section as implementation progresses:

### Phase Completion Status

- [ ] **Phase 1**: Helper Methods (PENDING)
- [ ] **Phase 2**: Refactor Methods (PENDING)
- [ ] **Phase 3**: Execution Logging (PENDING)
- [ ] **Phase 4**: Migration 0014 (PENDING)
- [ ] **Phase 5**: Update Tests (PENDING)
- [ ] **Phase 6**: Code Review (PENDING)

### Metrics

| Metric | Target | Actual | Status |
|--------|--------|--------|--------|
| Methods Migrated | 12/12 | 0/12 | 📋 PENDING |
| Tests Passing | 50/50 | 0/50 | 📋 PENDING |
| Test Coverage | >95% | 0% | 📋 PENDING |
| DB Overhead | <10ms | N/A | 📋 PENDING |

---

## 🚨 Risk Management

### High-Priority Risks

1. **Breaking Changes** (CRITICAL)
   - Mitigation: Zero signature changes, comprehensive tests
   - Rollback: Revert commit, use PROMPT_REGISTRY fallback

2. **DB Unavailable** (HIGH)
   - Mitigation: Automatic fallback to PROMPT_REGISTRY
   - Monitoring: Alert if fallback rate >5%

3. **Performance Degradation** (MEDIUM)
   - Mitigation: Chain caching, <10ms overhead target
   - Monitoring: Benchmark before/after

---

## ✅ Acceptance Criteria

### Functional
- [ ] ALL 13 methods load DB prompts first
- [ ] Fallback to PROMPT_REGISTRY on DB failure
- [ ] Execution logging tracks tokens, latency, cost
- [ ] 3 missing prompts seeded (migration 0014)
- [ ] Zero breaking changes

### Performance
- [ ] DB overhead <10ms per call
- [ ] Cache hit rate >90%
- [ ] No memory leaks

### Testing
- [ ] >95% unit test coverage
- [ ] >80% integration test coverage
- [ ] 50 tests pass

### Code Quality
- [ ] Passes ruff, black, mypy
- [ ] Clean Architecture compliance
- [ ] SOLID principles followed

---

## 📚 Architecture Principles

### Clean Architecture
- **Domain Layer**: PromptRepositoryPort (interface only)
- **Adapter Layer**: LangChainAdapter uses port interface
- **Dependency Inversion**: Adapters depend on abstractions

### SOLID Principles
- **Single Responsibility**: Each helper has ONE job
- **Open/Closed**: Add prompts via migration (no code changes)
- **Liskov Substitution**: PostgreSQL & Mock repos interchangeable
- **Interface Segregation**: PromptRepositoryPort focused
- **Dependency Inversion**: LangChainAdapter injects PromptRepositoryPort

### YAGNI, KISS, DRY
- **YAGNI**: Only migrate existing methods (no future features)
- **KISS**: Reuse proven pattern (generate_ideal_answer:268-287)
- **DRY**: Centralize DB loading in helper (17 lines → 3 lines per method)

---

## 🛠️ Tooling

### Code Quality
```bash
# Format code
black src/

# Lint code
ruff check src/ --fix

# Type check
mypy src/
```

### Testing
```bash
# Unit tests (fast, mock DB)
pytest tests/unit/ -v

# Integration tests (real DB)
pytest tests/integration/ -m integration

# Coverage report
pytest --cov=src --cov-report=html
```

### Performance
```bash
# Benchmark DB overhead
python scripts/benchmark_db_prompts.py
```

---

## 📖 Documentation Updates

Files to update after implementation:

- [ ] `CLAUDE.md` - Prompt management workflow
- [ ] `docs/system-architecture.md` - DB-driven prompts section
- [ ] `docs/code-standards.md` - DB loading pattern
- [ ] `README.md` - Configuration section

---

## 🤝 Contributing

### Before Implementation
1. Read [Main Plan](./plan.md) thoroughly
2. Review architecture principles (Clean Architecture, SOLID)
3. Understand fallback mechanism (DB → PROMPT_REGISTRY)

### During Implementation
1. Follow phases sequentially (1→2→3→5→6, Phase 4 parallel)
2. Run tests after each phase
3. Update progress tracking in this README

### After Implementation
1. Complete Phase 6 code review
2. Update documentation
3. Run full test suite + benchmarks
4. Create pull request with plan link

---

## 📞 Questions & Support

**Plan Author**: Claude Code (AI Planner)
**Review Date**: 2025-11-21
**Plan Version**: 1.0

**For Questions**:
1. Review [Main Plan](./plan.md) first
2. Check phase-specific documents
3. Consult architecture docs (`docs/system-architecture.md`)

---

## 🗂️ File Structure

```
plans/251121-1654-db-prompt-migration/
├── README.md (THIS FILE)
├── plan.md (Main plan - start here)
├── phase-01-create-helper-methods.md
├── phase-02-refactor-methods.md
├── phase-03-add-execution-logging.md
├── phase-04-create-migration.md
├── phase-05-update-tests.md
└── phase-06-code-review.md
```

**Total Plan Size**: ~140KB (7 markdown files)

---

**Status Legend**:
- 📋 PENDING - Not started
- 🚧 IN PROGRESS - Currently implementing
- ✅ COMPLETED - Phase finished
- ⚠️ BLOCKED - Waiting on dependency
- ❌ FAILED - Implementation failed (see notes)

---

**Last Updated**: 2025-11-21 17:06

**Next Action**: Begin Phase 1 - Create Helper Methods
