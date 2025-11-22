# API Patterns & Architecture Research

## 1. Router Setup Patterns

**Location:** `src/adapters/api/rest/interview_routes.py`

Router configured as `APIRouter(prefix="/interviews", tags=["Interviews"])` with standardized patterns:

```python
# Pattern 1: GET with UUID path parameter
@router.get("/{interview_id}", response_model=InterviewResponse, summary="...")
async def get_interview(interview_id: UUID, session: AsyncSession = Depends(get_async_session)):
    # Explicit 404 handling with HTTPException
    if not interview:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"...")

# Pattern 2: POST with request body
@router.post("/plan", response_model=PlanningStatusResponse, status_code=status.HTTP_202_ACCEPTED)
async def plan_interview(request: PlanInterviewRequest, session: AsyncSession = Depends(...)):
    # Feature flag routing between implementations
    if settings.use_langgraph_planning:
        # Route A: LangGraph workflow
    else:
        # Route B: Use case

# Pattern 3: PUT for state transitions
@router.put("/{interview_id}/start", response_model=InterviewResponse)
async def start_interview(interview_id: UUID, session: AsyncSession = Depends(...)):
    interview.start()  # Domain method
    await interview_repo.update(interview)
```

**Key traits:**
- All async functions
- `response_model=DTOClass` for type safety
- Explicit status codes (202 for async operations, 404, 400)
- Session dependency injection via `Depends(get_async_session)`
- Summary docstrings with Args/Returns/Raises sections

## 2. DTO Naming Conventions

**Location:** `src/application/dto/interview_dto.py`, `answer_dto.py`

**Naming pattern:** `{Entity}{RequestOrResponse}`

```python
# Request DTOs (suffix: Request)
class PlanInterviewRequest(BaseModel):
    cv_analysis_id: UUID
    candidate_id: UUID

class SubmitAnswerRequest(BaseModel):
    question_id: UUID
    answer_text: str
    audio_file_path: str | None = None

# Response DTOs (suffix: Response)
class InterviewResponse(BaseModel):
    id: UUID
    candidate_id: UUID
    status: str
    # ... other fields

    @staticmethod
    def from_domain(interview: Any, base_url: str, ...) -> "InterviewResponse":
        """Convert domain entity to DTO."""
        return InterviewResponse(...)

class AnswerEvaluationResponse(BaseModel):
    answer_id: UUID
    score: float
    feedback: str
```

**Conventions:**
- Use Pydantic `BaseModel` for all DTOs
- Response DTOs include `from_domain()` factory method for entity conversion
- Optional fields use `| None` syntax (Python 3.10+)
- Dict/list types: `dict[str, Any]`, `list[str]`

## 3. Dependency Injection Setup

**Location:** `src/infrastructure/dependency_injection/container.py`

**Pattern: Container with lazy-initialized singletons**

```python
class Container:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._llm_port: LLMPort | None = None  # Lazy init

    def llm_port(self) -> LLMPort:
        """Get LLM port, init once, cache thereafter."""
        if self._llm_port is None:
            if self.settings.use_mock_llm:
                self._llm_port = MockLLMAdapter()
            elif self.settings.use_langchain:
                self._llm_port = self._create_langchain_adapter()
            # ...
        return self._llm_port

    # Session-specific repositories (new instance each call)
    def interview_repository_port(self, session: AsyncSession) -> InterviewRepositoryPort:
        return PostgreSQLInterviewRepository(session)
```

**Registration patterns:**
- **Singletons** (no session): `llm_port()`, `vector_search_port()`, `cv_analyzer_port()`
- **Session-scoped**: Repository ports receive `AsyncSession` parameter
- **Feature flags** control implementation selection
- **Mock adapters** priority: Use mocks first if enabled, then LangChain, then concrete
- **Async methods**: `get_checkpointer()` is async for LangGraph initialization

**Usage in routes:**
```python
container = get_container()
interview_repo = container.interview_repository_port(session)
interview = await interview_repo.get_by_id(interview_id)
```

## 4. Error Handling Patterns

**HTTPException with explicit status codes:**

```python
# 404 Not Found
raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Interview {id} not found")

# 400 Bad Request (validation/state errors)
raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

# 500 Internal Server (file operations, external failures)
raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error: {str(e)}")
```

**Patterns:**
- Always catch domain exceptions (`ValueError`) and convert to 400
- Use `from e` for exception chaining
- Include context in detail message (e.g., interview_id, CV analysis ID)
- Return clear, user-friendly messages

## 5. Common Request/Response Patterns

**Status codes by operation type:**
- `POST` with async work: `202 ACCEPTED` (e.g., `/plan` for interview planning)
- `GET` with data: `200 OK` (implicit)
- `PUT` for state transitions: `200 OK` with updated resource
- Missing resource: `404 NOT FOUND`

**Response structure:**
```python
# Detailed response with nested data
class InterviewSummaryResponse(BaseModel):
    interview_id: str
    overall_score: float
    question_summaries: list[dict[str, Any]]  # Complex nested
    gap_progression: dict[str, Any]
    strengths: list[str]

# Status polling response
class PlanningStatusResponse(BaseModel):
    interview_id: UUID
    status: str  # PREPARING, READY, IN_PROGRESS
    planned_question_count: int | None
    plan_metadata: dict[str, Any] | None
    message: str
    ws_url: str  # Include actionable URLs
```

**Pagination/Filtering:** Not yet implemented in codebase; consider for future extensions.

## 6. Code Examples

**Complete endpoint with error handling:**
```python
@router.get("/{interview_id}", response_model=InterviewResponse)
async def get_interview(interview_id: UUID, session: AsyncSession = Depends(get_async_session)):
    container = get_container()
    interview_repo = container.interview_repository_port(session)
    interview = await interview_repo.get_by_id(interview_id)

    if not interview:
        raise HTTPException(status_code=404, detail=f"Interview {interview_id} not found")

    question_count = await interview_repo.count_interview_questions(interview_id)
    settings = get_settings()
    return InterviewResponse.from_domain(interview, settings.ws_base_url, question_count)
```

**Complex request with feature flag routing:**
```python
@router.post("/plan", response_model=PlanningStatusResponse, status_code=202)
async def plan_interview(request: PlanInterviewRequest, session: AsyncSession = Depends(...)):
    container = get_container()
    settings = get_settings()

    if settings.use_langgraph_planning:
        checkpointer = await container.get_checkpointer()
        workflow = PlanningWorkflow(checkpointer=checkpointer, ...)
        result = await workflow.execute(cv_analysis_id=request.cv_analysis_id, ...)
    else:
        use_case = PlanInterviewUseCase(...)
        interview = await use_case.execute(...)

    return PlanningStatusResponse(interview_id=interview.id, ...)
```

---

## Summary Table

| Aspect | Pattern |
|--------|---------|
| **Route prefix** | `/interviews` |
| **Request suffix** | `Request` |
| **Response suffix** | `Response` |
| **DTO conversion** | `from_domain()` static method |
| **Dependency source** | `get_container()` singleton |
| **Session injection** | `Depends(get_async_session)` |
| **404 handling** | Explicit `HTTPException` with detail |
| **400 handling** | Domain exception catch + convert |
| **Async** | All route handlers async/await |
| **Status codes** | 202 for async, 404/400 for errors |
