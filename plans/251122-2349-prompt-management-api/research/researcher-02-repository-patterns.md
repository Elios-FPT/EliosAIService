# Repository Implementation Patterns Research

## Overview
Elios uses clean architecture with repository pattern via **Ports & Adapters**. All repositories follow consistent patterns with async/await, transaction management, and domain/DB model mapping.

## Repository Architecture Pattern

### Port Interface (Abstract Contract)
Located in `src/domain/ports/`, defines what operations are available. Example: `PromptRepositoryPort` (ABC with abstractmethods).

### Adapter Implementation
Located in `src/adapters/persistence/`, implements the port interface using SQLAlchemy ORM.

**Example Structure:**
```
PromptRepositoryPort (abstract)
  ↓ implements
PostgreSQLPromptRepository (concrete adapter)
  ├─ __init__(self, session: AsyncSession)
  ├─ async methods (create, read, update, delete)
  └─ internal _helpers for complex operations
```

## Session Management Pattern

All repositories receive `AsyncSession` via constructor injection:
```python
def __init__(self, session: AsyncSession):
    self.session = session
```

Session lifetime managed by **DI container** (not repository responsibility).

## SQLAlchemy Model Structure

### PromptTemplateModel Example
Located in `src/adapters/persistence/models.py`:

**Decomposed Schema** (normalized from JSONB):
```python
class PromptTemplateModel(Base):
    id: Mapped[UUID]
    prompt_name: Mapped[str]
    version: Mapped[int]
    is_active: Mapped[bool]
    traffic_percentage: Mapped[int]

    # Decomposed fields (formerly nested in template_json)
    system_prompt: Mapped[str]
    user_template: Mapped[str]
    input_variables: Mapped[list[str]]
    partial_variables: Mapped[dict]
    output_parser_type: Mapped[str]
    output_schema: Mapped[dict]

    # Model parameters
    temperature: Mapped[Decimal]
    max_tokens: Mapped[int]
    top_p: Mapped[Decimal]
    frequency_penalty: Mapped[Decimal]
    presence_penalty: Mapped[Decimal]

    # Audit
    template_json_legacy: Mapped[dict]  # Store original
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]
    deleted_at: Mapped[datetime | None]  # Soft delete
```

**Key Features:**
- Composite primary key: (prompt_name, version)
- Soft delete via `deleted_at`
- Stores both decomposed + legacy JSON for backward compat

### Related Models
- `PromptExecutionModel` - Logs execution metrics (tokens, latency, cost)
- `PromptMetadataChangeModel` - Audit trail for activation/deactivation
- `PromptAnalyticsSummaryModel` - Materialized view for analytics

## Transaction Handling

### Standard Commit Pattern
```python
async def save(self, entity):
    db_model = Mapper.to_db_model(entity)
    self.session.add(db_model)
    await self.session.commit()        # Atomic transaction
    await self.session.refresh(db_model)  # Refresh to get DB-generated values
    return Mapper.to_domain(db_model)
```

### Nested Transactions (for A/B Testing)
```python
async with self.session.begin_nested():  # Savepoint
    # Deactivate other versions
    # Activate target version
    # Log metadata changes
await self.session.commit()  # Atomic - all or nothing
```

**Pattern:** Nested transactions for complex multi-step operations maintaining atomicity.

## Mapper Layer (Domain ↔ DB)

Located in `src/adapters/persistence/mappers.py`:

```python
class PromptTemplateMapper:
    @staticmethod
    def to_db_model(domain: PromptTemplate) -> PromptTemplateModel:
        """Domain → DB model"""
        return PromptTemplateModel(
            id=domain.id,
            prompt_name=domain.prompt_name,
            # ... map fields
        )

    @staticmethod
    def to_domain(db: PromptTemplateModel) -> PromptTemplate:
        """DB model → Domain"""
        return PromptTemplate(
            id=db.id,
            prompt_name=db.prompt_name,
            # ... map fields
        )
```

**Benefit:** Decouples domain logic from database representation.

## PromptRepositoryPort Implementation Status

**FULLY IMPLEMENTED:** `PostgreSQLPromptRepository` provides:

### Version Management
- `create_initial_prompt()` - Create v1 (decomposes template_json)
- `create_new_version()` - Fork from parent version
- `rollback_to_version()` - Immutable rollback (creates new version)
- `get_version_history()` - Chronological with diffs via DeepDiff

### Activation & A/B Testing
- `activate_version()` - Atomic activation (deactivates others if traffic=100)
- `adjust_ab_traffic()` - Update traffic percentage mid-test

### Retrieval
- `get_active_prompt(name)` - Weighted random selection for A/B testing
- `get_by_id()`, `get_version()` - Direct lookups
- `get_audit_trail()` - Metadata change history

### Analytics
- `log_execution()` - Record execution metrics
- `get_analytics_summary()` - Query materialized view (aggregated stats)

## Error Handling

**Validation in Repository:**
```python
# In create_initial_prompt()
existing = await self.session.execute(...)
if existing:
    raise ValueError(f"Prompt '{name}' already exists")

# In activate_version()
if not 0 <= traffic_percentage <= 100:
    raise ValueError("traffic_percentage must be between 0 and 100")
```

**Pattern:** Raise `ValueError` for domain violations (caught/mapped by use cases).

## Use Case vs Direct Repository Access

### Current Pattern (Confirmed)
**Direct repository access from adapters/routes** (not wrapped by use case layer):

```python
# In src/adapters/api/rest/prompt_routes.py (hypothetical)
@router.post("/prompts")
async def create_prompt(request: CreatePromptRequest,
                        prompt_repo: PromptRepositoryPort):
    prompt = await prompt_repo.create_initial_prompt(...)
    return prompt
```

**No intermediate use case layer** - routes directly call repository methods.

### Transaction Scope
- Each repository method = one transaction
- No multi-step use cases requiring cross-repository coordination (yet)

## Comparison with Other Repositories

**Similar pattern in `QuestionRepositoryPort`:**
```python
class PostgreSQLQuestionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save(question: Question) -> Question:
        db_model = QuestionMapper.to_db_model(question)
        self.session.add(db_model)
        await self.session.commit()
        await self.session.refresh(db_model)
        return QuestionMapper.to_domain(db_model)
```

All repositories follow same pattern: **DI injection → mapper → transaction → refresh**.

## Key Takeaways

1. **Port-based abstraction** allows easy swapping (e.g., PostgreSQL → MongoDB)
2. **Async-first design** with proper session management via DI
3. **Mapper layer** decouples domain from persistence details
4. **Atomic transactions** for consistency (standard commits + nested for multi-step)
5. **No use case wrapper layer** - routes directly call repository methods
6. **Decomposed schema pattern** - normalize JSONB into separate columns for queryability
7. **Soft deletes** via `deleted_at` for audit trails
8. **Audit logging** in separate `_metadata_change` table for compliance

## Implementation for Prompt Management API

✅ **PromptRepositoryPort fully implemented** - no additional port definition needed
✅ **PostgreSQLPromptRepository ready** - all CRUD + version control + analytics methods
✅ **Models + Mappers defined** - PromptTemplateModel, PromptExecutionModel, etc.
⚠️ **DI container registration** - ensure PromptRepositoryPort bound to PostgreSQLPromptRepository
⚠️ **Use case wrapper consideration** - recommend creating use case layer if multi-step workflows emerge
