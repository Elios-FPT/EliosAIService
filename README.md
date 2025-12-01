# Elios AI Interview Service

**AI-Powered Mock Interview Platform** with CV analysis, semantic question generation, and real-time feedback.

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)
[![LangChain](https://img.shields.io/badge/LangChain-0.3+-orange.svg)](https://python.langchain.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Test Coverage](https://img.shields.io/badge/Coverage-59%25-yellow.svg)]()

---

## Overview

Elios AI Interview Service delivers intelligent mock interview experiences by analyzing candidate CVs, generating personalized questions via vector search and LLMs, conducting real-time interviews through WebSocket, and providing comprehensive feedback with adaptive follow-up questions.

**Version**: v0.4.0 (Database Schema Redesign)
**Branch**: `feat/langchain-langgraph-integration`

### Key Features

**Core Capabilities**:
- **CV Analysis**: Extract skills, experience, education from PDFs/DOCX
- **Semantic Question Generation**: Vector search with LLM exemplar-based generation
- **Adaptive Interviews**: Follow-up questions based on gap detection
- **Real-Time Evaluation**: Multi-dimensional answer scoring with feedback
- **Voice Support**: Azure Speech-to-Text & Text-to-Speech integration
- **Comprehensive Reports**: Aggregate metrics, gap progression, LLM recommendations
- **Prompt Version Control**: Database-driven prompts with version history, A/B testing, and rollback support

**NEW - v0.4.0 Schema Redesign**:
- **Normalized Skills**: cv_skills table replaces JSONB array
- **Junction Tables**: interview_questions replaces question_ids array
- **PostgreSQL ENUMs**: QuestionType, Difficulty, ProficiencyLevel for type safety
- **Decomposed Prompts**: prompt_templates split for A/B testing & versioning

**LangChain/LangGraph Integration** (v0.3.0):
- **LCEL Chains**: Structured outputs with Pydantic models
- **Workflow Orchestration**: Planning, adaptive evaluation
- **PostgreSQL Checkpointing**: Stateful workflows with recovery
- **LangSmith Observability**: PII-filtered tracing, cost tracking

### Technology Stack

- **Backend**: Python 3.11+, FastAPI, Pydantic
- **AI/ML**: LangChain/LangGraph, OpenAI GPT-4, Pinecone Vector DB
- **Database**: PostgreSQL (Neon), SQLAlchemy 2.0 (async)
- **Architecture**: Clean Architecture (Hexagonal/Ports & Adapters)
- **Testing**: pytest, pytest-asyncio (354/601 tests passing, 59% coverage)

## Prompt Management API

Manage LLM prompt templates with version control, A/B testing, rollback, and analytics.

### Endpoints

**Version Management:**
- `POST /api/prompts` - Create initial prompt (v1)
- `POST /api/prompts/{name}/versions` - Create new version (optional `parent_version` for lineage)
- `PATCH /api/prompts/{prompt_id}/draft` - Update draft prompt version content
- `POST /api/prompts/{name}/rollback` - Rollback to target version
- `GET /api/prompts/{name}/versions` - Get version history with diffs
- `GET /api/prompts/{name}/versions/{version}` - Get specific version
- `GET /api/prompts/{prompt_id}` - Get prompt by UUID

**Activation & A/B Testing:**
- `PATCH /api/prompts/{prompt_id}/activate` - Activate version (204 No Content)
- `PATCH /api/prompts/{prompt_id}/traffic` - Adjust A/B test traffic (204 No Content)
- `GET /api/prompts/{name}/active` - Get active prompt (with A/B weighted selection)

**Analytics & Audit:**
- `GET /api/prompts/{name}/analytics` - View analytics summary
- `GET /api/prompts/{name}/audit-trail` - View change history
- `GET /api/prompts` - List all prompts (paginated, filterable)
- `DELETE /api/prompts/{prompt_id}` - Soft delete prompt (204 No Content)

### Usage Example

```python
import httpx

# Create initial prompt
response = await client.post("/api/ai/prompts", json={
    "prompt_name": "answer_evaluation",
    "system_prompt": "You are an expert interviewer...",
    "user_template": "Evaluate this answer: {answer}",
    "input_variables": ["answer"],
    "temperature": 0.7,
    "max_tokens": 2000,
    "top_p": 0.9,
    "frequency_penalty": 0.0,
    "presence_penalty": 0.0,
    "created_by": "admin",
})
prompt = response.json()

# Activate for production
await client.patch(f"/api/ai/prompts/{prompt['id']}/activate", json={
    "changed_by": "admin",
    "reason": "Deploy v1 to production",
    "traffic_percentage": 100
})
```

### A/B Testing Workflow

1. Create v2 with improved prompt
2. Activate v2 with traffic=20% (gradual rollout)
3. Monitor analytics for success rate, cost
4. Increase traffic to 50%, 75%, 100% based on results
5. Rollback if v2 underperforms

### Main flows

#### 1. Preparation Phase (Scan CV & Generate Topics)

```mermaid
sequenceDiagram
    actor Candidate
    participant ChatUI as Chat UI / Frontend
    participant CVAnalyzer as 📄 CV Analyzer Component
    participant VectorDB as 🧠 Vector Database
    participant AIEngine as 🤖 AI Interviewer Engine

    Candidate->>ChatUI: Upload CV file
    ChatUI->>CVAnalyzer: Send CV for analysis
    CVAnalyzer->>VectorDB: Generate & store CV embeddings
    VectorDB-->>CVAnalyzer: Confirm embeddings stored
    CVAnalyzer-->>ChatUI: Return extracted skills & suggested topics
    ChatUI-->>Candidate: Display preparation summary
    ChatUI->>AIEngine: Notify readiness (skills, topics)
    AIEngine-->>ChatUI: Acknowledged
```

#### 2. Interview Phase (Real-time Q&A)

```mermaid
sequenceDiagram
    actor Candidate
    participant ChatUI as Chat UI / Frontend
    participant AIEngine as 🤖 AI Interviewer Engine
    participant VectorDB as 🧠 Vector Database
    participant QBank as 📚 Question Bank Service
    participant STT as 🎤 Speech-to-Text
    participant TTS as 🗣️ Text-to-Speech
    participant Analytics as 📊 Analytics & Feedback Service

    %% --- Start Interview ---
    Candidate->>ChatUI: Start interview
    ChatUI->>AIEngine: Request first question
    AIEngine->>VectorDB: Query similar question embeddings (based on CV topics)
    VectorDB-->>AIEngine: Return question candidates
    AIEngine->>QBank: Fetch selected question
    QBank-->>AIEngine: Return question details
    AIEngine-->>ChatUI: Send question text
    ChatUI-->>TTS: Convert question text to speech
    TTS-->>Candidate: Play AI voice question

    %% --- Candidate answers ---
    Candidate->>STT: Speak answer
    STT-->>AIEngine: Send transcript text
    AIEngine->>VectorDB: Compare answer embeddings & evaluate quality
    VectorDB-->>AIEngine: Return similarity & semantic score
    AIEngine->>Analytics: Send answer evaluation (score, sentiment, reasoning)
    Analytics-->>AIEngine: Acknowledged

    alt More questions remain
        AIEngine->>VectorDB: Retrieve next suitable question
        VectorDB-->>AIEngine: Return next question candidate
        AIEngine-->>ChatUI: Send next question
        ChatUI-->>TTS: Convert to speech & play
        TTS-->>Candidate: Play next question
    else Interview finished
        AIEngine-->>ChatUI: Notify interview end
    end

```

#### 3. Final Stage (Evaluation & Reporting)

```mermaid
sequenceDiagram
    actor Candidate
    participant ChatUI as Chat UI / Frontend
    participant AIEngine as 🤖 AI Interviewer Engine
    participant Analytics as 📊 Analytics & Feedback Service

    AIEngine->>Analytics: Send final interview summary (scores, metrics, transcript)
    Analytics->>Analytics: Aggregate results & generate report
    Analytics-->>AIEngine: Acknowledged

    AIEngine-->>ChatUI: Notify interview completion
    ChatUI->>Analytics: Request final feedback report
    Analytics-->>ChatUI: Return detailed feedback & improvement suggestions
    ChatUI-->>Candidate: Display performance summary & insights

```

---

## 🏗️ Architecture

This project follows **Clean Architecture** (Hexagonal/Ports & Adapters): Domain Layer (pure business logic) → Application Layer (use cases) → Adapters Layer (external services) → Infrastructure Layer (config, DI).

📚 **[Full Architecture Details →](docs/system-architecture.md)**

---

## 🚀 Quick Start

### ⚡ 5-Minute Setup

**Just want to run it?** Copy and paste these commands:

```bash
# Setup environment and install dependencies
python -m venv venv && venv\Scripts\activate && pip install -e ".[dev]"

# Configure and run migrations
cp .env.example .env.local && alembic upgrade head

# Start the server
python -m src.main
```

Then visit: **http://localhost:8000/docs**

⚠️ **Note**: Edit `.env.local` with your API keys before full functionality works.

---

## 🐳 Docker Setup

### Quick Start with Docker

**Prerequisites:**
- Docker and Docker Compose installed
- External PostgreSQL database (connection string required)

**Steps:**

1. **Create environment file**
   ```bash
   cp .env.docker.example .env
   ```

2. **Edit `.env` file** - Set at minimum:
   ```env
   DATABASE_URL=postgresql://user:password@host:5432/elios_interviews
   # Add API keys if not using mocks
   OPENAI_API_KEY=sk-your-key-here
   PINECONE_API_KEY=your-key-here
   ```

3. **Build and start services**
   ```bash
   docker-compose up -d
   ```

4. **Run database migrations**
   ```bash
   docker-compose run migrate
   ```

5. **Access the application**
   - API: http://localhost:8000
   - API Docs: http://localhost:8000/docs

### Docker Environment Variables

The Docker image includes **default environment variables** baked into the Dockerfile, so you only need to override what's necessary:

**Required:**
- `DATABASE_URL` - External PostgreSQL connection string

**Optional (only if not using mocks):**
- `OPENAI_API_KEY` - OpenAI API key
- `PINECONE_API_KEY` - Pinecone API key
- `AZURE_SPEECH_KEY` - Azure Speech Services key
- Other API keys as needed

**Environment Variable Precedence:**
1. `docker-compose.yml` `environment:` section (highest priority)
2. `.env` file
3. Dockerfile `ENV` statements (defaults)

**Example minimal `.env` file:**
```env
# Required
DATABASE_URL=postgresql://user:pass@host:5432/dbname

# Optional - only if not using mocks
OPENAI_API_KEY=sk-...
PINECONE_API_KEY=...
ENVIRONMENT=production
DEBUG=false
```

All other configuration (ports, timeouts, feature flags, etc.) uses sensible defaults from the Dockerfile.

### Docker Commands

```bash
# Build the image
docker-compose build

# Start services
docker-compose up -d

# View logs
docker-compose logs -f app

# Run migrations
docker-compose run migrate

# Stop services
docker-compose down

# Rebuild after code changes
docker-compose up -d --build
```

### Development vs Production

- **Development**: Use mock adapters (default), set `ENVIRONMENT=development`, `DEBUG=true`
- **Production**: Use real services, set `ENVIRONMENT=production`, `DEBUG=false`, provide all API keys

---

### 📋 Detailed Setup Instructions

#### Prerequisites

- Python 3.11 or higher
- pip (Python package manager)
- PostgreSQL database (or Neon account)
- OpenAI API key
- Pinecone API key
- Google Cloud account with Speech API enabled (or use mock adapters)

#### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/elios/elios-ai-service.git
   cd EliosAIService
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv

   # Windows
   venv\Scripts\activate

   # Linux/macOS
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -e ".[dev]"
   ```

4. **Configure environment variables**

   **Prompt Management (Optional)**:

   Enable DB-driven prompts for version control and analytics:

   ```env
   # Prompt repository (requires PostgreSQL)
   ENABLE_PROMPT_VERSIONING=true  # Default: true
   ```

   If disabled, LangChainAdapter falls back to hardcoded PROMPT_REGISTRY.
   ```bash
   cp .env.example .env.local
   ```

   Edit `.env.local` with your credentials:
   ```env
   # Database
   DATABASE_URL=postgresql://user:password@host:5432/elios_interviews

   # LLM Provider
   LLM_PROVIDER=openai
   OPENAI_API_KEY=sk-your-api-key-here
   OPENAI_MODEL=gpt-4

   # Vector Database
   VECTOR_DB_PROVIDER=pinecone
   PINECONE_API_KEY=your-pinecone-api-key
   PINECONE_INDEX_NAME=elios-questions

   # Google Cloud Speech (Chirp 3) - NEW v0.4.1
   GOOGLE_CLOUD_PROJECT_ID=your-project-id
   GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json
   GOOGLE_STT_MODEL=chirp_3
   GOOGLE_TTS_VOICE_NAME=en-US-Chirp3-HD-Charon
   ```

5. **Run database migrations**
   ```bash
   alembic upgrade head
   ```

6. **Verify database setup**
   ```bash
   python scripts/verify_db.py
   ```

7. **Start the server**
   ```bash
   python -m src.main
   ```

   Server runs at: http://localhost:8000

   API Documentation: http://localhost:8000/docs

---

## 📖 Documentation

### For Users
- **[Project Overview & PDR](docs/project-overview-pdr.md)** - Product requirements, features, and roadmap
- **[Database Setup Guide](DATABASE_SETUP.md)** - Comprehensive database configuration
- **[Environment Setup Guide](ENV_SETUP.md)** - Environment configuration best practices

### For Developers
- **[System Architecture](docs/system-architecture.md)** - Detailed architecture documentation
- **[Codebase Summary](docs/codebase-summary.md)** - Project structure and tech stack
- **[Code Standards](docs/code-standards.md)** - Coding conventions and best practices
- **[CLAUDE.md](CLAUDE.md)** - Development guidelines for AI assistants

---

## 🧪 Development

### Mock Adapters for Testing

**Mock adapters** simulate external services without API costs or network latency. Enabled by default in development.

**Available Mocks** (6 total):
- `MockLLMAdapter` - Simulates OpenAI/LLM responses
- `MockVectorSearchAdapter` - In-memory vector search
- `MockSTTAdapter` - Simulates speech-to-text
- `MockTTSAdapter` - Simulates text-to-speech
- `MockCVAnalyzerAdapter` - Filename-based CV parsing
- `MockAnalyticsAdapter` - In-memory performance tracking

**Configuration**:
```env
# .env.local
USE_MOCK_ADAPTERS=true   # Use mocks (default, fast tests)
USE_MOCK_ADAPTERS=false  # Use real services (requires API keys)
```

**Benefits**:
- Tests run 10x faster (~5s vs ~30s)
- No API costs during development
- No network dependency
- Deterministic test results

**Note**: Repositories (PostgreSQL) intentionally NOT mocked - use real database for data integrity tests.

### Running Tests

```bash
# Run all tests (with mocks enabled by default)
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test types
pytest tests/unit/         # Unit tests only
pytest tests/integration/  # Integration tests only
pytest tests/e2e/          # End-to-end tests only

# Test with real adapters (requires API keys)
USE_MOCK_ADAPTERS=false pytest
```

### Interview Test Bot

Automated testing framework for interview WebSocket protocol with two execution modes:

**Test Modes**:
- **Mock Tests** (8 scenarios, $0 cost): Insert pre-defined data via SQL → Test WebSocket QA phase only
- **Real Tests** (5 scenarios, ~$0.45 cost): Full API flow (CV upload → plan interview → WebSocket QA → save feedback)

**Setup Test Environment**:
```bash
# 1. Copy test configuration template
cp .env.test.example .env.test

# 2. Edit .env.test with test database and settings
# IMPORTANT: Ensure ENVIRONMENT=test is set (required for main app to load .env.test)

# 3. Create test database
createdb elios_test

# 4. Run migrations on test database
ENVIRONMENT=test alembic upgrade head

# 5. Start server with test configuration
python -m src.main
# Server will automatically load .env.test because ENVIRONMENT=test
```

**Run Tests**:
```bash
# Run all tests (server must be running with ENVIRONMENT=test)
python -m tests.bot.run_tests --scenarios all

# Run only mock tests (no API costs, SQL data insertion)
python -m tests.bot.run_tests --scenarios mock

# Run only real tests (with OpenAI API, full flow)
python -m tests.bot.run_tests --scenarios real

# Run single scenario
python -m tests.bot.run_tests --scenario mock_001_basic_flow
```

**Configuration Details**:
- `.env.test` - Test environment configuration (separate DB, mock settings, API keys)
- `ENVIRONMENT=test` - Critical variable that tells main app to load `.env.test`
- Test isolation: Separate test database prevents contaminating dev/prod data
- Mock adapter control: `USE_MOCK_ADAPTERS=true/false` in `.env.test`

**Features**:
- WebSocket client simulating candidate interactions
- Mock tests: DB helper for direct SQL insertion (skip API calls)
- Real tests: Full API integration testing
- Performance metrics tracking (latency, tokens, cost)
- JSON/HTML reports with baseline comparison
- Answer generation with quality levels (good/average/weak)

**Structure**:
- `tests/bot/test_bot_client.py` - WebSocket test client
- `tests/bot/test_runner.py` - Test orchestration (mock vs real execution)
- `tests/bot/db_helper.py` - SQL insertion helper for mock tests
- `tests/bot/scenarios/` - Test scenario definitions (YAML)
- `tests/bot/fixtures/` - CV fixtures and baselines
- `tests/bot/run_tests.py` - CLI entry point

### Code Quality

```bash
# Format code
black src/

# Lint code
ruff check src/
ruff check --fix src/  # Auto-fix issues

# Type checking
mypy src/

# Run all checks
black src/ && ruff check src/ && mypy src/
```

### Database Operations

```bash
# Create new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# View migration history
alembic history

# Verify database
python scripts/verify_db.py
```

---

## 🎯 Usage Example

### 1. Create a Candidate

```python
import httpx

async with httpx.AsyncClient() as client:
    response = await client.post(
        "http://localhost:8000/api/candidates",
        json={
            "name": "John Doe",
            "email": "john.doe@example.com"
        }
    )
    candidate = response.json()
    print(f"Created candidate: {candidate['id']}")
```

### 2. Upload and Analyze CV

```python
async with httpx.AsyncClient() as client:
    with open("resume.pdf", "rb") as cv_file:
        response = await client.post(
            "http://localhost:8000/api/cv/upload",
            files={"file": cv_file},
            data={"candidate_id": candidate['id']}
        )
    cv_analysis = response.json()
    print(f"Skills found: {cv_analysis['skills']}")
```

### 3. Start Interview

```python
async with httpx.AsyncClient() as client:
    response = await client.post(
        "http://localhost:8000/api/interviews",
        json={
            "candidate_id": candidate['id'],
            "cv_analysis_id": cv_analysis['id']
        }
    )
    interview = response.json()
    # v0.4.0: Uses junction table interview_questions (not question_ids array)
    # Access questions via /api/interviews/{id}/questions endpoint
    print(f"Interview created: {interview['id']}")
```

### 4. Submit Answer

```python
async with httpx.AsyncClient() as client:
    # Get current question from interview
    question_response = await client.get(
        f"http://localhost:8000/api/interviews/{interview['id']}/current-question"
    )
    current_question = question_response.json()

    response = await client.post(
        f"http://localhost:8000/api/interviews/{interview['id']}/answers",
        json={
            "question_id": current_question['id'],
            "answer_text": "My answer here..."
        }
    )
    evaluation = response.json()
    print(f"Score: {evaluation['score']}/100")
    print(f"Feedback: {evaluation['feedback']}")
```

---

## 📦 Project Structure

```
EliosAIService/
├── src/
│   ├── domain/              # Core business logic (11 models, 13 ports)
│   ├── application/         # Use cases & workflows (8 use cases, 3 workflows)
│   ├── adapters/            # External service implementations (20+ adapters)
│   └── infrastructure/      # Config, DI, database, observability
├── alembic/                 # Database migrations (15 migrations)
├── docs/                    # Documentation (8 comprehensive guides)
└── tests/                   # Test suites (354/601 passing, 59% coverage)
```

📚 **[Complete Structure →](docs/codebase-summary.md)**

## ✨ What's New in v0.4.0

### Database Schema Redesign

**Normalized Tables**:
- `cv_skills` table with proficiency_level, years_of_experience, is_primary fields
- `interview_questions` junction table with sequence_order tracking
- PostgreSQL ENUMs for type safety (QuestionType, Difficulty, ProficiencyLevel)

**Breaking Changes**:
```python
# ❌ OLD (v0.3.0 and earlier)
interview.question_ids  # JSONB array
cv_analysis.skills      # JSONB array

# ✅ NEW (v0.4.0+)
await interview_repo.get_interview_questions(interview_id)  # Junction table
await cv_analysis_repo.get_skills(cv_analysis_id)          # Normalized table
```

**Migration**: See `docs/migrations/0015-schema-redesign.md` for complete guide.

📚 **[Full v0.4.0 Changes →](docs/migrations/0015-schema-redesign.md)**

---

## 🔧 Configuration

Configuration is managed through environment variables with the following priority:

1. `.env.local` (highest priority, gitignored)
2. `.env` (can be committed, template)
3. System environment variables
4. Pydantic defaults

### Key Configuration Sections

- **Application**: Name, version, environment
- **LLM Provider**: OpenAI, Claude, or Llama configuration
- **Vector Database**: Pinecone, Weaviate, or ChromaDB settings
- **PostgreSQL**: Database connection and credentials
- **Speech Services**: Azure STT, Edge TTS (planned)
- **Interview Settings**: Question count, scoring, timeouts
- **Database Pooling**: `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_POOL_TIMEOUT`, `DB_POOL_RECYCLE_SECONDS` let you tune SQLAlchemy's connection pool for serverless Postgres providers (defaults keep Neon free tier under its 5-minute idle timeout). Sessions are now short-lived and acquired per request via `session_scope()` / FastAPI dependencies to avoid stale connections.

See [ENV_SETUP.md](ENV_SETUP.md) for detailed configuration guide.

---

## 🤝 Contributing

We welcome contributions! Please see our contributing guidelines (coming soon).

### Development Workflow

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes following our [Code Standards](docs/code-standards.md)
4. Run tests and quality checks
5. Commit using [Conventional Commits](https://www.conventionalcommits.org/)
6. Push to your branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

### Commit Message Format

```
<type>(<scope>): <subject>

Examples:
feat(domain): add Interview aggregate with state management
fix(persistence): handle NULL metadata in answer mapper
docs: update API documentation for CV upload endpoint
```

---

## 🗺️ Roadmap

### Phase 1: Foundation (v0.1.0 - v0.2.1) - COMPLETE ✅
- ✅ Domain models (8 entities) and ports (13 interfaces)
- ✅ PostgreSQL persistence layer (7 repositories)
- ✅ OpenAI & Azure OpenAI LLM adapters
- ✅ Pinecone & ChromaDB vector adapters
- ✅ Azure Speech services (STT/TTS)
- ✅ Database migrations
- ✅ REST API implementation (5 endpoints)
- ✅ WebSocket real-time protocol
- ✅ Domain-driven state management
- ✅ Context-aware evaluation with follow-ups
- ✅ Session orchestrator (state machine)

### Phase 2: Core Features (v0.2.0 - v0.5.0)
- ⏳ Voice interview support
- ⏳ Advanced question generation
- ⏳ Interview analytics
- ⏳ Performance benchmarks
- ⏳ Frontend integration

### Phase 3: Intelligence Enhancement (v0.6.0 - v0.8.0)
- ⏳ Multi-LLM support (Claude, Llama)
- ⏳ Behavioral question analysis
- ⏳ Personality insights
- ⏳ Skill gap analysis

### Phase 4: Scale & Polish (v0.9.0 - v1.0.0)
- ⏳ Multi-language support
- ⏳ Team/organization features
- ⏳ Mobile app support
- ⏳ Production deployment

See [Project Overview & PDR](docs/project-overview-pdr.md) for detailed roadmap.

---

## 📊 Current Status

**Version**: 0.4.0 (Database Schema Redesign Complete)
**Test Coverage**: 59% (354/601 tests passing)
**Branch**: `feat/langchain-langgraph-integration`

**Implemented** ✅:
- Clean Architecture with Clean Code principles
- v0.4.0 normalized schema (cv_skills, interview_questions tables, PostgreSQL ENUMs)
- Domain models (11 entities) + Repository ports (13 interfaces)
- LangChain LCEL adapter + LangGraph workflows (Planning, AdaptiveEvaluation)
- PostgreSQL persistence with async SQLAlchemy 2.0
- OpenAI GPT-4 + Azure OpenAI adapters
- Pinecone vector search + ChromaDB local alternative
- Mock adapters (6 total) for development
- REST API (5 endpoints) + WebSocket real-time protocol
- LangSmith observability with PII filtering
- Prompt version control & A/B testing
- Database migrations (15 total, Alembic)

**In Progress** 🔄:
- CV processing adapters (spaCy, PyPDF2) - 40%
- Test coverage expansion (target: 80%) - 59%

**Planned** ⏳:
- Authentication & authorization (OAuth 2.0, JWT)
- Rate limiting & API quotas
- Docker deployment + CI/CD
- Production optimization & monitoring

---

## 🛡️ Security

- API keys stored in environment variables (never committed)
- SQL injection prevention via parameterized queries
- Input validation with Pydantic
- HTTPS enforcement (production)
- Data encryption at rest (Neon built-in)
- GDPR compliance considerations

Report security vulnerabilities to: security@elios.ai

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **OpenAI** for GPT-4 and Embeddings API
- **Pinecone** for vector database
- **FastAPI** for the excellent web framework
- **Neon** for serverless PostgreSQL
- **Pydantic** for data validation
- **SQLAlchemy** for ORM

---

## 📞 Contact

- **Website**: https://elios.ai
- **Email**: contact@elios.ai
- **Issues**: [GitHub Issues](https://github.com/elios/elios-ai-service/issues)
- **Discussions**: [GitHub Discussions](https://github.com/elios/elios-ai-service/discussions)

---

## ⭐ Support

If you find this project helpful, please consider giving it a star on GitHub! It helps others discover the project and motivates continued development.

---

**Built with ❤️ using Clean Architecture principles**
