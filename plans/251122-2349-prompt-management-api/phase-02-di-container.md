# Phase 02: DI Container Registration

**Date:** 2025-11-22
**Status:** PENDING
**Priority:** HIGH
**Parent Plan:** [plan.md](./plan.md)
**Dependencies:** Phase 01 (DTOs not strictly required, but recommended)

## Context

Register `PromptRepositoryPort` in dependency injection container to enable route access.
Currently missing from `src/infrastructure/dependency_injection/container.py`.

**Related Files:**
- [DI Container](../../src/infrastructure/dependency_injection/container.py)
- [Repository Implementation](../../src/adapters/persistence/postgres_repository.py)
- [Repository Patterns Research](./research/researcher-02-repository-patterns.md)

## Overview

Add `prompt_repository_port()` method to Container class following session-scoped pattern
used by other repositories (InterviewRepository, QuestionRepository, etc.).

## Key Insights from Research

1. **Session-Scoped Pattern:** Repositories receive AsyncSession in constructor
2. **Method Naming:** `{entity}_repository_port()` convention
3. **Return Type:** Port interface (not concrete class)
4. **Instantiation:** New instance per call (not singleton)
5. **No Feature Flags:** PromptRepository has no mock adapter (use real PostgreSQL)

## Requirements

### Method Signature
```python
def prompt_repository_port(self, session: AsyncSession) -> PromptRepositoryPort:
    """Get PromptRepositoryPort instance."""
    return PostgreSQLPromptRepository(session)
```

### Import Additions
```python
from src.domain.ports.prompt_repository_port import PromptRepositoryPort
from src.adapters.persistence.postgres_repository import PostgreSQLPromptRepository
```

## Architecture

**Design Decisions:**
1. **No Mock Adapter:** Prompt management critical infrastructure - always use real DB
2. **Session-Scoped:** New repo instance per request (matches existing pattern)
3. **No Caching:** Repository methods handle their own query optimization

## Implementation Steps

1. **Add Imports**
   - Import PromptRepositoryPort from domain/ports
   - Import PostgreSQLPromptRepository from adapters/persistence

2. **Add Method to Container Class**
   - Add `prompt_repository_port(session: AsyncSession)` method
   - Follow naming convention of existing repository methods
   - Return PostgreSQLPromptRepository instance

3. **Verify Registration**
   - Test that method can be called from routes
   - Ensure session injection works correctly

## Related Code Files

```python
# src/infrastructure/dependency_injection/container.py
class Container:
    # ... existing methods ...

    def interview_repository_port(self, session: AsyncSession) -> InterviewRepositoryPort:
        return PostgreSQLInterviewRepository(session)

    def question_repository_port(self, session: AsyncSession) -> QuestionRepositoryPort:
        return PostgreSQLQuestionRepository(session)

    # ADD THIS:
    def prompt_repository_port(self, session: AsyncSession) -> PromptRepositoryPort:
        return PostgreSQLPromptRepository(session)
```

## Todo List

- [ ] Add import for PromptRepositoryPort
- [ ] Add import for PostgreSQLPromptRepository
- [ ] Add `prompt_repository_port()` method to Container class
- [ ] Test method can be called with AsyncSession
- [ ] Verify return type annotation correct

## Success Criteria

- ✅ Method added to Container class
- ✅ Correct imports added
- ✅ Return type PromptRepositoryPort (not concrete class)
- ✅ Session parameter AsyncSession type
- ✅ No breaking changes to existing container methods
- ✅ Can instantiate from routes: `container.prompt_repository_port(session)`

## Risk Assessment

**Low Risk:**
- Trivial change (3 lines of code)
- Follows established pattern exactly
- No configuration or feature flags needed

## Security Considerations

None - DI container registration has no security implications.

## Next Steps

1. Implement changes to container.py
2. Test instantiation in Python REPL
3. Proceed to Phase 03: Version Management Endpoints
