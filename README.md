# Elios AI Interview Service

**AI-Powered Mock Interview Platform** with CV analysis, semantic question generation, real-time feedback, and comprehensive interview analytics.

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)
[![LangChain](https://img.shields.io/badge/LangChain-0.3+-orange.svg)](https://python.langchain.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Test Coverage](https://img.shields.io/badge/Coverage-59%25-yellow.svg)]()

---

## Overview

Elios AI Interview Service delivers intelligent mock interview experiences by analyzing candidate CVs, generating personalized questions, conducting real-time interviews via WebSocket, evaluating answers with feedback analysis, and providing comprehensive performance reports.

**Version**: v0.5.0 (Phase-04 Use Case Extraction + Feedback System)
**Branch**: `feat/get-feedback`
**Last Updated**: 2025-12-08

### Key Features

- **CV Analysis**: Extract skills, experience, education from PDFs/DOCX
- **Semantic Question Generation**: Vector search + LLM for personalized questions
- **Real-Time Interview**: WebSocket-based interactive Q&A with voice support
- **Unified Answer Evaluation (Phase-04)**: 46% faster with single LLM call
- **Thin Orchestrator Pattern (Phase-04)**: 8 interview + 6 planning use cases
- **Feedback System**: Comprehensive performance reports with recommendations
- **Interview History**: Track and analyze multiple interview sessions
- **LangGraph Workflows**: State machine orchestration with PostgreSQL checkpointing
- **Observability**: LangSmith tracing with PII filtering and cost tracking

---

## Quick Start

### 5-Minute Setup

```bash
# Setup environment
python -m venv venv && venv\Scripts\activate && pip install -e ".[dev]"

# Configure
cp .env.example .env.local && alembic upgrade head

# Run
python -m src.main
```

Visit: **http://localhost:8000/docs**

### Docker Setup

```bash
cp .env.docker.example .env
docker-compose up -d
docker-compose run migrate
```

Access API: http://localhost:8000

---

## Technology Stack

- **Backend**: Python 3.11+, FastAPI, Pydantic, asyncio
- **AI/ML**: LangChain/LangGraph, OpenAI GPT-4, Pinecone Vector DB
- **Database**: PostgreSQL with SQLAlchemy 2.0 async
- **Speech**: Google Cloud Speech (Chirp 3 STT/TTS)
- **Messaging**: Kafka for event-driven architecture
- **Observability**: LangSmith + custom cost tracking
- **Testing**: pytest, 59% coverage (354/601 tests passing)

---

## Architecture

**Clean Architecture** (Hexagonal/Ports & Adapters) with layers:
- **Domain**: Pure business logic (33 files: 17 models, 14 ports, 2 services)
- **Application**: 20 use cases + 3 thin orchestrator workflows (57 files)
- **Adapters**: External service implementations (51 files, 20+ adapters)
- **Infrastructure**: Config, DI, database, observability (8 files)

**Phase-04 Pattern**: Thin orchestrators (30-50 LOC) delegating to focused use cases
**Performance**: Unified LLM analysis - 46% latency reduction

📚 **[Full Architecture Details →](docs/system-architecture.md)**

---

## Development

### Setup Environment

```bash
# Clone and setup
git clone https://github.com/elios/elios-ai-service.git
cd EliosAIService
python -m venv venv && source venv/bin/activate  # Linux/macOS

# Install dependencies
pip install -e ".[dev]"

# Configure
cp .env.example .env.local
# Edit .env.local with API keys (OpenAI, Pinecone, etc.)

# Run migrations
alembic upgrade head

# Start server
python -m src.main
```

### Testing

```bash
pytest                    # Run all tests
pytest --cov=src        # With coverage report
pytest tests/unit/      # Unit tests only
```

**Mock Adapters**: Enabled by default for fast tests without API costs.

### Code Quality

```bash
black src/           # Format
ruff check src/      # Lint
mypy src/            # Type check
```

---

## API Usage

### Upload CV & Analyze

```python
async with httpx.AsyncClient() as client:
    response = await client.post(
        "http://localhost:8000/api/ai/interviews/cv/upload",
        files={"file": open("resume.pdf", "rb")}
    )
    cv_analysis = response.json()
```

### Start Interview

```python
response = await client.post(
    "http://localhost:8000/api/interviews",
    json={"candidate_id": "...", "cv_analysis_id": "..."}
)
interview = response.json()
```

### Get Interview History

```python
response = await client.get(
    f"http://localhost:8000/api/interviews/users/{candidate_id}/history",
    params={"limit": 10, "offset": 0}
)
history = response.json()
```

---

## Documentation

### For Users
- **[Project Overview & PDR](docs/project-overview-pdr.md)** - Features, roadmap, requirements
- **[Deployment Guide](docs/deployment-guide.md)** - Production setup

### For Developers
- **[System Architecture](docs/system-architecture.md)** - Design patterns & layers
- **[Codebase Summary](docs/codebase-summary.md)** - Project structure & tech stack
- **[Code Standards](docs/code-standards.md)** - Conventions & best practices
- **[CLAUDE.md](CLAUDE.md)** - AI-assisted development guidelines

---

## What's New in v0.5.0

**Feedback System** (Phases 01-06 Complete):
- Domain models: FeedbackRequest, FeedbackResponse, FeedbackResult
- Repository layer with type-safe mappers
- AnalyzeFeedbackUseCase with exponential backoff retry
- REST endpoints: POST/GET feedback analysis
- Kafka integration: FEEDBACK_COMPLETED, TOKEN_DELTA events
- Interview history by user ID

**Optimizations**:
- Follow-up generation optimization with timing logs
- LLM call optimization
- DB hit reduction

**Database Schema (v0.4.0)**:
- Normalized `cv_skills` table (replaces JSONB array)
- `interview_questions` junction table (replaces question_ids array)
- PostgreSQL ENUMs for type safety (QuestionType, Difficulty, ProficiencyLevel)
- Decomposed prompt templates for A/B testing

---

## Project Structure

```
EliosAIService/
├── src/
│   ├── domain/           # 17 models, 14 ports
│   ├── application/      # 8 use cases, 3 workflows
│   ├── adapters/         # 20+ external service implementations
│   └── infrastructure/   # Config, DI, database, observability
├── alembic/              # Database migrations (15 total)
├── docs/                 # Comprehensive documentation
└── tests/                # Test suites (354/601 passing)
```

📚 **[Complete Structure →](docs/codebase-summary.md)**

---

## Recent Changes

**Recent Commits** (Last 6):
1. `23f9050` - Optimize follow-up generation, add timing logs
2. `d8488e7` - Optimize LLM call, DB hit
3. `2223f49` - feat: get interview history by user id
4. `12290aa` - fix: missing database session at get_history_feedback()
5. `e4107f9` - feat: deduct user's tokens when trigger planning interview
6. `f75b4cf` - fix: wrong date format cause saving cv analysis error

---

## Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Follow [Code Standards](docs/code-standards.md)
4. Run tests and quality checks
5. Commit with [Conventional Commits](https://www.conventionalcommits.org/)
6. Submit Pull Request

---

## Roadmap

### Phase 1: Foundation (v0.1.0 - v0.2.1) - ✅ COMPLETE
- ✅ Domain models, repository ports, REST API, WebSocket protocol
- ✅ LangChain/LangGraph workflows with PostgreSQL checkpointing
- ✅ Mock adapters, comprehensive testing framework

### Phase 1.5: Schema Redesign (v0.4.0) - ✅ COMPLETE
- ✅ Normalized schema (cv_skills, interview_questions)
- ✅ PostgreSQL ENUMs for type safety
- ✅ Decomposed prompt templates

### Phase 1.6: Feedback System (v0.5.0) - ✅ COMPLETE
- ✅ Feedback domain models and repository
- ✅ Feedback analysis use case with retry logic
- ✅ REST API endpoints and Kafka integration
- ✅ Interview history by user ID

### Phase 2: Core Features (v0.6.0+)
- Voice interview enhancement
- Advanced analytics dashboard
- Multi-language support
- Production optimization

---

## Security

- API keys in environment variables (never committed)
- SQL injection prevention via parameterized queries
- Input validation with Pydantic
- PII filtering in observability traces
- HTTPS enforcement (production)

---

## Support

- **Issues**: [GitHub Issues](https://github.com/elios/elios-ai-service/issues)
- **Discussions**: [GitHub Discussions](https://github.com/elios/elios-ai-service/discussions)
- **Email**: contact@elios.ai

---

**Built with Clean Architecture + LangChain/LangGraph + ❤️**
