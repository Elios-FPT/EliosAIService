# Phase 01: DTOs & Request/Response Models

**Date:** 2025-11-22
**Status:** PENDING
**Priority:** HIGH
**Parent Plan:** [plan.md](./plan.md)

## Context

Define all Pydantic DTOs for prompt management API following existing naming conventions.
Must match domain model fields and support clean API contract.

**Dependencies:**
- [Domain Model](../../src/domain/models/prompt_template.py)
- [DTO Patterns](../../src/application/dto/interview_dto.py)
- [API Patterns Research](./research/researcher-01-api-patterns.md)

## Overview

Create 10 DTOs in new file `src/application/dto/prompt_dto.py`:
- **Request DTOs (5):** CreatePromptRequest, CreateVersionRequest, RollbackRequest, ActivatePromptRequest, AdjustTrafficRequest
- **Response DTOs (5):** PromptTemplateResponse, VersionHistoryResponse, AnalyticsSummaryResponse, AuditTrailResponse, PaginatedPromptsResponse

## Key Insights from Research

1. **Naming:** Suffix `Request` for inputs, `Response` for outputs
2. **Factory Method:** Response DTOs include `from_domain()` static method
3. **Type Hints:** Use `| None` for optional fields (Python 3.10+)
4. **Nested Structures:** Use `dict[str, Any]` or `list[str]` for complex types
5. **UUID Serialization:** Pydantic handles UUID automatically

## Requirements

### Request DTOs

1. **CreatePromptRequest** - Create initial prompt (v1)
   ```python
   - prompt_name: str
   - system_prompt: str
   - user_template: str
   - input_variables: list[str]
   - partial_variables: dict[str, Any] | None
   - output_parser_type: str
   - output_schema: dict[str, Any] | None
   - temperature: float
   - max_tokens: int
   - top_p: float
   - frequency_penalty: float
   - presence_penalty: float
   - created_by: str
   - notes: str | None
   ```

2. **CreateVersionRequest** - Create new version from parent
   ```python
   - parent_version: int
   - system_prompt: str
   - user_template: str
   - input_variables: list[str]
   - partial_variables: dict[str, Any] | None
   - output_parser_type: str
   - output_schema: dict[str, Any] | None
   - temperature: float
   - max_tokens: int
   - top_p: float
   - frequency_penalty: float
   - presence_penalty: float
   - change_summary: str
   - created_by: str
   - notes: str | None
   ```

3. **RollbackRequest** - Rollback to target version
   ```python
   - target_version: int
   - changed_by: str
   - reason: str
   ```

4. **ActivatePromptRequest** - Activate version
   ```python
   - changed_by: str
   - reason: str
   - traffic_percentage: int = 100
   - ab_test_group: str | None
   ```

5. **AdjustTrafficRequest** - Adjust A/B test traffic
   ```python
   - new_traffic_percentage: int
   - changed_by: str
   - reason: str
   ```

### Response DTOs

1. **PromptTemplateResponse** - Full prompt details
   ```python
   - id: UUID
   - prompt_name: str
   - version: int
   - is_active: bool
   - traffic_percentage: int
   - system_prompt: str
   - user_template: str
   - input_variables: list[str]
   - partial_variables: dict[str, Any]
   - output_parser_type: str
   - output_schema: dict[str, Any]
   - temperature: float
   - max_tokens: int
   - top_p: float
   - frequency_penalty: float
   - presence_penalty: float
   - created_at: datetime
   - updated_at: datetime
   - deleted_at: datetime | None

   @staticmethod
   from_domain(prompt: PromptTemplate) -> "PromptTemplateResponse"
   ```

2. **VersionHistoryResponse** - Version with diff
   ```python
   - version: int
   - created_at: datetime
   - created_by: str
   - change_summary: str
   - is_active: bool
   - traffic_percentage: int
   - diff: dict[str, Any] | None
   ```

3. **AnalyticsSummaryResponse** - Analytics metrics
   ```python
   - prompt_name: str
   - total_executions: int
   - avg_tokens_used: float
   - avg_latency_ms: float
   - success_rate: float
   - estimated_cost_usd: float
   - last_executed_at: datetime | None
   ```

4. **AuditTrailResponse** - Metadata change entry
   ```python
   - field_name: str
   - old_value: str
   - new_value: str
   - changed_by: str
   - changed_at: datetime
   - reason: str
   ```

5. **PaginatedPromptsResponse** - List with pagination
   ```python
   - prompts: list[PromptTemplateResponse]
   - total: int
   - page: int
   - page_size: int
   - has_next: bool
   ```

## Architecture

**File Structure:**
```
src/application/dto/
├── interview_dto.py (existing)
├── answer_dto.py (existing)
└── prompt_dto.py (NEW)
```

**Design Decisions:**
1. Keep all prompt DTOs in single file for cohesion
2. Separate nested structures (VersionHistoryResponse) for clarity
3. Use factory method pattern for domain entity conversion
4. Validate constraints in Pydantic (temperature range, traffic_percentage 0-100)

## Implementation Steps

1. **Create DTO file** (`src/application/dto/prompt_dto.py`)
   - Add module docstring
   - Import dependencies (BaseModel, UUID, datetime, Decimal, Any)

2. **Define Request DTOs**
   - CreatePromptRequest with field validators (temperature 0-2, traffic 0-100)
   - CreateVersionRequest (same structure + change_summary)
   - RollbackRequest (minimal fields)
   - ActivatePromptRequest (with default traffic_percentage=100)
   - AdjustTrafficRequest (validates 0-100 range)

3. **Define Response DTOs**
   - PromptTemplateResponse with `from_domain()` factory
   - VersionHistoryResponse (no factory, constructed from dict)
   - AnalyticsSummaryResponse (constructed from materialized view dict)
   - AuditTrailResponse (constructed from audit trail dict)
   - PaginatedPromptsResponse (wrapper with pagination metadata)

4. **Add Pydantic validators**
   - Temperature: 0.0-2.0 using `Field(ge=0.0, le=2.0)`
   - Traffic percentage: 0-100 using `Field(ge=0, le=100)`
   - Max tokens: 1-100000 using `Field(ge=1, le=100000)`

5. **Add docstrings**
   - Class docstring for each DTO explaining purpose
   - Example payloads in docstrings

6. **Test DTO serialization**
   - Create unit tests for from_domain() conversion
   - Test Pydantic validation (invalid temperature, traffic)
   - Test JSON serialization/deserialization

## Todo List

- [ ] Create `src/application/dto/prompt_dto.py`
- [ ] Define 5 Request DTOs with Pydantic validators
- [ ] Define 5 Response DTOs with `from_domain()` factory
- [ ] Add field validators for temperature, traffic_percentage, max_tokens
- [ ] Add comprehensive docstrings with examples
- [ ] Create unit tests for DTO validation
- [ ] Test `from_domain()` conversion with PromptTemplate instances
- [ ] Test JSON serialization edge cases (Decimal, UUID, datetime)
- [ ] Verify Pydantic Field constraints enforce ranges
- [ ] Update imports in `src/application/dto/__init__.py`

## Success Criteria

- ✅ All 10 DTOs defined with correct field types
- ✅ `from_domain()` factory method converts PromptTemplate to PromptTemplateResponse
- ✅ Pydantic validators enforce temperature (0-2), traffic (0-100), max_tokens (1-100000)
- ✅ Unit tests pass for validation edge cases
- ✅ JSON serialization handles UUID, datetime, Decimal correctly
- ✅ No circular import issues with domain models
- ✅ Docstrings include example payloads

## Risk Assessment

**Low Risk:**
- Pydantic models straightforward (similar to existing DTOs)
- No database or external dependencies

**Medium Risk:**
- Decimal to float conversion in `from_domain()` (precision loss)
- Large `output_schema` JSON serialization performance
- Nested `partial_variables` dict validation

**Mitigation:**
- Use `float()` conversion for Decimal fields explicitly
- Test with large output_schema payloads
- Use `dict[str, Any]` for flexible validation

## Security Considerations

1. **Input Validation:** Pydantic automatically validates types and constraints
2. **SQL Injection:** Not applicable (no raw SQL in DTOs)
3. **XSS:** Escape `system_prompt` and `user_template` in UI (not API concern)
4. **PII Leakage:** Avoid logging `created_by`, `changed_by` fields

## Related Code Files

- `src/application/dto/interview_dto.py` - Existing DTO patterns
- `src/domain/models/prompt_template.py` - Domain model to convert from
- `src/adapters/api/rest/interview_routes.py` - Router patterns

## Next Steps

1. Implement all DTOs in `prompt_dto.py`
2. Create unit tests in `tests/application/dto/test_prompt_dto.py`
3. Validate JSON serialization with FastAPI test client
4. Proceed to Phase 02: DI Container Registration
