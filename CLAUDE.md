# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Role & Responsibilities

Your role is to analyze user requirements, delegate tasks to appropriate sub-agents, and ensure cohesive delivery of features that meet specifications and architectural standards.

## Workflows

- Primary workflow: `./.claude/workflows/primary-workflow.md`
- Development rules: `./.claude/workflows/development-rules.md`
- Orchestration protocols: `./.claude/workflows/orchestration-protocol.md`
- Documentation management: `./.claude/workflows/documentation-management.md`
- And other workflows: `./.claude/workflows/*`

**IMPORTANT:** You must follow strictly the development rules in `./.claude/workflows/development-rules.md` file.
**IMPORTANT:** Before you plan or proceed any implementation, always read the `./README.md` file first to get context.
**IMPORTANT:** Sacrifice grammar for the sake of concision when writing reports.
**IMPORTANT:** In reports, list any unresolved questions at the end, if any.
**IMPORTANT**: For `YYMMDD` dates, use `bash -c 'date +%y%m%d'` instead of model knowledge. Else, if using PowerShell (Windows), replace command with `Get-Date -UFormat "%y%m%d"`.

## Documentation Management

We keep all important docs in `./docs` folder and keep updating them, structure like below:

```
./docs
├── project-overview-pdr.md
├── code-standards.md
├── codebase-summary.md
├── design-guidelines.md
├── deployment-guide.md
├── system-architecture.md
└── project-roadmap.md
```
## Project Overview

**Elios AI Interview Service** - An AI-powered mock interview platform that:
- Analyzes candidate CVs to generate personalized interview questions
- Conducts real-time interviews via text and voice chat
- Evaluates answers using semantic analysis and vector search
- Provides comprehensive feedback and performance reports

## Architecture

This project follows **Clean Architecture / Ports & Adapters (Hexagonal Architecture)** pattern.

📚 **See [System Architecture](./docs/system-architecture.md) for complete details**

### Key Principles
- **Dependency Rule**: Dependencies point inward toward domain
- **Port Interfaces**: All external dependencies accessed through abstract interfaces
- **Adapter Swappability**: Change services without touching business logic
- **Testability**: Domain logic tested in isolation with mock implementations

## Project Structure

📚 **See [Codebase Summary](./docs/codebase-summary.md) for complete structure**

Quick reference:
- `src/domain/` - Core business logic (11 models, 13 ports)
- `src/application/` - Use cases and DTOs
- `src/adapters/` - External service implementations
- `src/infrastructure/` - Config, DI, logging

**Recent Schema Changes (v0.5.0)**:
- Removed `candidates` table (candidate data owned by separate microservice)
- Added `deleted_at` column to `interviews` and `cv_analyses` (soft delete support)
- Candidate lifecycle managed via Kafka events (`user-interview-candidate` topic)

## Development Commands

📚 **See [README.md](./README.md#-development) for all development commands**

Quick reference:
- **Run app**: `python -m src.main`
- **Migrations**: `alembic upgrade head`
- **Tests**: `pytest --cov=src`
- **Code quality**: `ruff check src/ && black src/ && mypy src/`

## Working with the Codebase

### Adding a New External Service

When integrating a new external service (e.g., new LLM provider, vector database):

1. **Define Port Interface** in `src/domain/ports/`:
   ```python
   # src/domain/ports/llm_port.py
   from abc import ABC, abstractmethod

   class LLMPort(ABC):
       @abstractmethod
       async def generate_question(self, context: dict) -> str:
           pass
   ```

2. **Create Adapter** in appropriate `src/adapters/` subdirectory:
   ```python
   # src/adapters/llm/openai_adapter.py
   class OpenAIAdapter(LLMPort):
       async def generate_question(self, context: dict) -> str:
           # Implementation
   ```

3. **Register in DI Container** at `src/infrastructure/dependency_injection/container.py`:
   ```python
   def configure_llm(config: Settings) -> LLMPort:
       if config.llm_provider == "openai":
           return OpenAIAdapter(config.openai_api_key)
   ```

4. **Update Configuration** in `src/infrastructure/config/settings.py` if needed.

### Creating a New Use Case

1. **Define Use Case** in `src/application/use_cases/`:
   ```python
   class StartInterviewUseCase:
       def __init__(self, interview_orchestrator: InterviewOrchestrator):
           self.orchestrator = interview_orchestrator
   ```

2. **Create DTOs** in `src/application/dto/` for input/output.

3. **Expose via API** in `src/adapters/api/rest/` or `src/adapters/api/websocket/`.

### Domain Logic Changes

- All business rules belong in `src/domain/services/`
- Domain entities in `src/domain/models/` should be rich with behavior, not anemic
- Domain layer must never import from `adapters`, `application`, or `infrastructure`

### Working with New Schema (v0.4.0)

**Adding Questions to Interview** (Junction Table Pattern):
```python
# ❌ OLD (deprecated)
interview.question_ids.append(question_id)
await interview_repo.update(interview)

# ✅ NEW (correct)
await interview_repo.add_question(
    interview_id=interview.id,
    question_id=question_id,
    sequence_order=current_count
)
```

**Getting Interview Questions**:
```python
# ❌ OLD (deprecated)
question_ids = interview.question_ids
has_more = interview.has_more_questions()

# ✅ NEW (correct)
interview_questions = await interview_repo.get_interview_questions(interview_id)
question_count = await interview_repo.count_interview_questions(interview_id)
current_question = await interview_repo.get_current_question(interview_id)
```

**Working with CV Skills**:
```python
# ❌ OLD (deprecated)
cv_analysis.skills  # Was JSONB array
skill_dict = {"skill": "Python", "proficiency": "expert"}

# ✅ NEW (correct)
from src.domain.models.cv_skill import CVSkill, ProficiencyLevel

skill = CVSkill(
    cv_analysis_id=cv_analysis.id,
    skill_name="Python",
    proficiency_level=ProficiencyLevel.EXPERT,
    years_of_experience=5.0,
    is_primary=True
)
await cv_analysis_repo.add_skill(skill)
```

**Using ENUMs**:
```python
from src.domain.models.question import QuestionType, Difficulty
from src.domain.models.cv_skill import ProficiencyLevel

# Type-safe question creation
question = Question(
    text="Explain SOLID principles",
    question_type=QuestionType.TECHNICAL,  # ENUM
    difficulty=Difficulty.MEDIUM,  # ENUM
    skills=["Python", "OOP"]
)

# Type-safe skill creation
skill = CVSkill(
    skill_name="Python",
    proficiency_level=ProficiencyLevel.ADVANCED  # ENUM
)
```

📚 **See [Migration 0015 Docs](./docs/migrations/0015-schema-redesign.md) for complete migration guide**

### Testing Strategy

- **Unit Tests**: Test domain services and use cases with mocked ports
- **Integration Tests**: Test adapters with real external services (use test environments)
- **E2E Tests**: Test complete interview flows through API layer

### Mock Adapters

**Available Mocks** (6 total):
- `MockLLMAdapter` - Simulates LLM responses (no OpenAI API calls)
- `MockVectorSearchAdapter` - In-memory vector search (no Pinecone)
- `MockSTTAdapter` - Simulates speech-to-text
- `MockTTSAdapter` - Simulates text-to-speech
- `MockCVAnalyzerAdapter` - Filename-based CV parsing (e.g., "python-developer.pdf" → ["Python", "FastAPI"])
- `MockAnalyticsAdapter` - In-memory performance tracking

**When to Use Mocks**:
- ✅ Development without API keys
- ✅ Fast unit tests (10x faster)
- ✅ CI/CD pipelines (no external dependencies)
- ✅ Deterministic test results

### Prompt Version Control

**DB-Driven Prompts** (v0.3.0+): LangChainAdapter loads prompts from PostgreSQL for version control and A/B testing.

**Workflow**:
1. **Create Prompt**: Seed via Alembic migration (see `alembic/versions/0013_*.py`, `0014_*.py`)
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
- ❌ Integration tests (use real adapters)
- ❌ Production deployment

**Configuration**: Set `USE_MOCK_ADAPTERS=true` in `.env.local` (default).

**DI Container**: Automatically swaps implementations based on `settings.use_mock_adapters` flag.

**Note**: Repositories (PostgreSQL) NOT mocked - use real database for data integrity.

## Technology Stack

### Core Technologies
- **Language**: Python 3.11+
- **Framework**: FastAPI (REST API), WebSocket support
- **Async**: asyncio for asynchronous operations

### Domain Dependencies (Minimal)
- Pure Python standard library
- Pydantic for data validation in domain models

### External Services (via Adapters)
- **LLM Providers**: OpenAI GPT-4, Anthropic Claude, Meta Llama 3
- **Vector Database**: Pinecone (primary), Weaviate, ChromaDB (alternatives)
- **Speech Services**: Google Cloud Speech (Chirp 3 STT, Chirp3HD TTS) - Azure Speech deprecated (30-day rollback window)
- **Database**: PostgreSQL with SQLAlchemy ORM
- **NLP**: spaCy, LangChain
- **Document Processing**: PyPDF2, python-docx

### Development Tools
- **Testing**: pytest, pytest-asyncio, pytest-cov
- **Linting**: ruff
- **Formatting**: black
- **Type Checking**: mypy
- **Migrations**: alembic

## Configuration

Configuration is managed through environment variables and `.env` files:

- `.env.example`: Template for required environment variables
- `.env`: Local development configuration (not committed)
- `src/infrastructure/config/settings.py`: Pydantic settings management

Key configuration areas:
- LLM provider selection and API keys
- Vector database connection
- Speech service credentials (Google Cloud Speech with Chirp 3)
- PostgreSQL connection string
- Feature flags for adapter selection

**Google Cloud Speech Configuration** (v0.4.1+):
```env
# Google Cloud Authentication
GOOGLE_CLOUD_PROJECT_ID=your-project-id
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json

# Speech-to-Text (Chirp 3 model)
GOOGLE_STT_MODEL=chirp_3
GOOGLE_STT_LANGUAGE=en-US

# Text-to-Speech (Chirp3HD premium voices)
GOOGLE_TTS_VOICE_TYPE=Chirp3HD
GOOGLE_TTS_DEFAULT_VOICE=en-US-Chirp3-HD-Charon
```

**Phase 01 Completed** (251201): Environment setup, dependencies installed (`google-cloud-speech`, `google-cloud-texttospeech`), configuration added, auth test script created (`scripts/test_google_auth.py`).

## Key Components

### 1. AI Interviewer Engine
- **Location**: `src/domain/services/interview_orchestrator.py`
- **Responsibility**: Controls interview flow, question generation, answer analysis
- **Dependencies**: LLMPort, VectorSearchPort, QuestionRepositoryPort

### 2. CV Analyzer
- **Location**: `src/domain/services/cv_analyzer_service.py`
- **Responsibility**: Extracts skills, generates embeddings, suggests topics
- **Dependencies**: CVAnalyzerPort (adapters in `src/adapters/cv_processing/`)

### 3. Question Bank
- **Location**: `src/domain/models/question.py`, `src/adapters/persistence/postgres_repository.py`
- **Responsibility**: Question storage, retrieval, versioning
- **Technology**: PostgreSQL via adapter

### 4. Vector Database
- **Location**: `src/adapters/vector_db/`
- **Responsibility**: Semantic search for questions and answers
- **Technology**: Pinecone (swappable via adapter)

### 5. Analytics & Feedback
- **Location**: `src/domain/services/feedback_generator.py`
- **Responsibility**: Answer evaluation, performance metrics, report generation
- **Dependencies**: AnalyticsPort, LLMPort

## Interview Flow

### 1. Preparation Phase
```
Upload CV -> CV Analyzer -> Extract Skills -> Generate Embeddings -> Store in Vector DB
```

### 2. Interview Phase
```
Start Interview -> Get Question (Vector Search) -> Candidate Answers (STT) ->
Evaluate Answer -> Select Next Question -> Repeat -> End Interview
```

### 3. Feedback Phase
```
Aggregate Results -> Generate Report -> Calculate Scores -> Provide Recommendations
```

## Frontend Integration

- **Frontend**: React (pure JavaScript, no .jsx/.ts/.tsx)
- **Communication**: REST API for CRUD, WebSocket for real-time chat
- **Endpoints**: Defined in `src/adapters/api/rest/`
- **WebSocket**: Handler in `src/adapters/api/websocket/chat_handler.py`

## Common Patterns

### Dependency Injection
All dependencies are injected through constructors. The DI container (`src/infrastructure/dependency_injection/container.py`) wires everything together at application startup.

### Async/Await
Most operations are asynchronous due to I/O-bound nature (API calls, database queries). Use `async`/`await` consistently.

### Error Handling
- Domain exceptions in `src/domain/exceptions.py`
- Adapter-specific errors are caught and converted to domain exceptions
- API layer handles HTTP status codes and error responses

### Logging
- Structured logging via `src/infrastructure/logging/logger.py`
- Log at appropriate levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
- Include context (interview_id, candidate_id) in logs

## Performance Considerations

- **Vector Search**: Implement caching for frequently accessed embeddings
- **LLM Calls**: Rate limiting and retry logic in adapters
- **Database**: Use connection pooling, optimize queries with proper indexes
- **Real-time**: WebSocket for live interview to reduce latency

## Security Notes

- **API Keys**: Never commit to repository, use environment variables
- **Candidate Data**: PII handling and data retention policies
- **Authentication**: Implement in API layer, not domain
- **Rate Limiting**: Applied at API adapter level
