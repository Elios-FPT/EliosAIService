# Phase 03: Version Management Endpoints

**Date:** 2025-11-22
**Status:** PENDING
**Priority:** HIGH
**Parent Plan:** [plan.md](./plan.md)
**Dependencies:** Phase 01 (DTOs), Phase 02 (DI Container)

## Context

Implement 6 REST endpoints for prompt version lifecycle: create, fork, rollback, history, retrieve.
Core CRUD operations for prompt templates.

**Related Files:**
- [Router Pattern](../../src/adapters/api/rest/interview_routes.py)
- [DTOs](../../src/application/dto/prompt_dto.py) (from Phase 01)
- [API Patterns Research](./research/researcher-01-api-patterns.md)

## Overview

Create `src/adapters/api/rest/prompt_routes.py` with APIRouter and 6 endpoints:

1. POST `/api/prompts` - Create initial prompt (v1)
2. POST `/api/prompts/{name}/versions` - Create new version from parent
3. POST `/api/prompts/{name}/rollback` - Rollback to target version
4. GET `/api/prompts/{name}/versions` - Get version history with diffs
5. GET `/api/prompts/{name}/versions/{version}` - Get specific version
6. GET `/api/prompts/{id}` - Get prompt by UUID

## Key Insights from Research

**Router Setup:**
- Prefix: `/prompts` (not `/api/prompts` - FastAPI app adds `/api`)
- Tags: `["Prompt Management"]`
- All async endpoints
- Session injection: `Depends(get_async_session)`
- Container access: `get_container()`

**Error Handling:**
- 404: Prompt not found, version not found
- 400: Validation errors (parent version doesn't exist, invalid rollback target)
- 201: Resource created (POST endpoints)
- 200: Resource retrieved (GET endpoints)

## Requirements

### Endpoint Specifications

#### 1. Create Initial Prompt
```python
@router.post("", response_model=PromptTemplateResponse, status_code=201)
async def create_initial_prompt(
    request: CreatePromptRequest,
    session: AsyncSession = Depends(get_async_session)
)
```
**Logic:**
- Call `prompt_repo.create_initial_prompt(name, template_json, created_by, notes)`
- Return PromptTemplateResponse.from_domain(prompt)
- Handle ValueError (prompt already exists) → 400

#### 2. Create New Version
```python
@router.post("/{name}/versions", response_model=PromptTemplateResponse, status_code=201)
async def create_new_version(
    name: str,
    request: CreateVersionRequest,
    session: AsyncSession = Depends(get_async_session)
)
```
**Logic:**
- Build template_json from request fields
- Call `prompt_repo.create_new_version(name, parent_version, template_json, ...)`
- Return PromptTemplateResponse.from_domain(prompt)
- Handle ValueError (parent not found) → 400

#### 3. Rollback to Version
```python
@router.post("/{name}/rollback", response_model=PromptTemplateResponse, status_code=201)
async def rollback_prompt(
    name: str,
    request: RollbackRequest,
    session: AsyncSession = Depends(get_async_session)
)
```
**Logic:**
- Call `prompt_repo.rollback_to_version(name, target_version, changed_by, reason)`
- Return PromptTemplateResponse.from_domain(prompt)
- Handle ValueError (target version not found) → 400

#### 4. Get Version History
```python
@router.get("/{name}/versions", response_model=list[VersionHistoryResponse])
async def get_version_history(
    name: str,
    session: AsyncSession = Depends(get_async_session)
)
```
**Logic:**
- Call `prompt_repo.get_version_history(name)`
- Return list of VersionHistoryResponse (construct from dict)
- Return [] if prompt doesn't exist (not 404)

#### 5. Get Specific Version
```python
@router.get("/{name}/versions/{version}", response_model=PromptTemplateResponse)
async def get_specific_version(
    name: str,
    version: int,
    session: AsyncSession = Depends(get_async_session)
)
```
**Logic:**
- Call `prompt_repo.get_version(name, version)`
- Return PromptTemplateResponse.from_domain(prompt)
- Raise 404 if not found

#### 6. Get Prompt by ID
```python
@router.get("/{prompt_id}", response_model=PromptTemplateResponse)
async def get_prompt_by_id(
    prompt_id: UUID,
    session: AsyncSession = Depends(get_async_session)
)
```
**Logic:**
- Call `prompt_repo.get_by_id(prompt_id)`
- Return PromptTemplateResponse.from_domain(prompt)
- Raise 404 if not found

## Architecture

**File Structure:**
```
src/adapters/api/rest/
├── __init__.py (existing)
├── interview_routes.py (existing)
├── health_routes.py (existing)
└── prompt_routes.py (NEW)
```

**Design Decisions:**
1. **template_json Construction:** Build from request DTO fields (decomposed schema pattern)
2. **Error Messages:** Include prompt name/version in error detail for debugging
3. **Validation:** Let repository layer raise ValueError for business rules
4. **History Endpoint:** Return empty list (not 404) if prompt doesn't exist

## Implementation Steps

1. **Create Router File** (`src/adapters/api/rest/prompt_routes.py`)
   - Add module docstring
   - Import dependencies (FastAPI, HTTPException, UUID, PromptRepositoryPort, DTOs)
   - Create APIRouter with prefix="/prompts", tags=["Prompt Management"]

2. **Implement POST /prompts** (Create Initial)
   - Parse CreatePromptRequest
   - Build template_json dict from DTO fields
   - Call repository.create_initial_prompt()
   - Return 201 with PromptTemplateResponse
   - Handle ValueError → 400

3. **Implement POST /{name}/versions** (Create Version)
   - Parse CreateVersionRequest
   - Build template_json dict
   - Call repository.create_new_version()
   - Return 201 with PromptTemplateResponse
   - Handle ValueError → 400

4. **Implement POST /{name}/rollback** (Rollback)
   - Parse RollbackRequest
   - Call repository.rollback_to_version()
   - Return 201 with PromptTemplateResponse
   - Handle ValueError → 400

5. **Implement GET /{name}/versions** (History)
   - Call repository.get_version_history()
   - Convert list[dict] to list[VersionHistoryResponse]
   - Return 200 with list (empty if not found)

6. **Implement GET /{name}/versions/{version}** (Specific Version)
   - Call repository.get_version()
   - Return 200 with PromptTemplateResponse
   - Raise 404 if None

7. **Implement GET /{id}** (By UUID)
   - Call repository.get_by_id()
   - Return 200 with PromptTemplateResponse
   - Raise 404 if None

8. **Register Router in Main App**
   - Import prompt_routes in src/main.py or src/adapters/api/rest/__init__.py
   - Add `app.include_router(prompt_routes.router, prefix="/api")`

## Todo List

- [ ] Create `src/adapters/api/rest/prompt_routes.py`
- [ ] Add APIRouter configuration (prefix, tags)
- [ ] Implement POST /prompts (create initial)
- [ ] Implement POST /{name}/versions (create version)
- [ ] Implement POST /{name}/rollback (rollback)
- [ ] Implement GET /{name}/versions (history)
- [ ] Implement GET /{name}/versions/{version} (specific version)
- [ ] Implement GET /{id} (by UUID)
- [ ] Add comprehensive docstrings to each endpoint
- [ ] Register router in main app
- [ ] Test all endpoints with FastAPI TestClient
- [ ] Verify error handling (404, 400 cases)

## Success Criteria

- ✅ All 6 endpoints respond correctly with valid input
- ✅ 404 returned for missing prompts/versions
- ✅ 400 returned for business rule violations (ValueError)
- ✅ 201 status for POST operations
- ✅ template_json correctly constructed from DTO fields
- ✅ PromptTemplateResponse.from_domain() works correctly
- ✅ Version history includes diffs
- ✅ OpenAPI docs auto-generated correctly

## Risk Assessment

**Medium Risk:**
- template_json construction complexity (many fields)
- Version history diff display performance with large histories

**Mitigation:**
- Helper function to build template_json from DTO
- Repository layer already handles diff computation

## Security Considerations

1. **Input Validation:** Pydantic DTOs validate all inputs
2. **SQL Injection:** Repository uses parameterized queries
3. **Path Traversal:** Prompt names validated by repository (no file paths)
4. **DoS:** Rate limiting recommended for history endpoint

## Next Steps

1. Implement all 6 endpoints in prompt_routes.py
2. Test with FastAPI TestClient
3. Verify OpenAPI docs correct
4. Proceed to Phase 04: Activation & A/B Testing Endpoints
