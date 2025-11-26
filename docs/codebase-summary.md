# Codebase Summary

**Last Updated**: 2025-11-26
**Version**: 0.4.0 (Schema Redesign + LangChain/LangGraph Integration)
**Repository**: https://github.com/elios/elios-ai-service
**Branch**: feat/langchain-langgraph-integration

## Table of Contents

- [Overview](#overview)
- [Project Statistics](#project-statistics)
- [Project Structure](#project-structure)
- [Core Technologies](#core-technologies)
- [Recent Major Changes](#recent-major-changes)
- [Key Components](#key-components)
- [Entry Points](#entry-points)
- [Development Workflow](#development-workflow)
- [Implementation Status](#implementation-status)
- [Dependencies Overview](#dependencies-overview)
- [Related Documentation](#related-documentation)

## Overview

Elios AI Interview Service is Python-based AI-powered mock interview platform built with Clean Architecture principles (Hexagonal/Ports & Adapters pattern). Platform emphasizes separation of concerns, testability, flexibility through abstract interfaces and dependency injection. Integrates LangChain/LangGraph for workflow orchestration, OpenAI GPT-4 for NLP, Pinecone for vector-based semantic search, PostgreSQL for persistent storage.

**Recent Major Changes** (2025-11-26):
- **Schema Redesign (v0.4.0)**: Normalized database schema with junction tables + ENUMs
  - `cv_skills` table replaces JSONB array (proper relationships)
  - `interview_questions` junction table replaces question_ids array
  - ENUMs for type safety: `question_type_enum`, `difficulty_enum`, `proficiency_level_enum`
  - Decomposed `prompt_templates` into 11 editable columns for UI-based editing
  - Removed redundant columns (cv_file_path, metadata)
- **LangChain/LangGraph Integration (v0.3.0)**: LCEL chains, structured outputs, workflow orchestration with PostgreSQL checkpointing
- **Observability Module (v0.3.0)**: LangSmith tracing with PII filtering, cost tracking
- **Interview Test Bot**: Automated WebSocket testing framework with 8 mock + 5 real scenarios
- **Context-aware evaluation** with entity separation
- **Domain-Driven State Management** (migrated from WebSocket orchestrator)

## Project Statistics

**Code Metrics**:
- **Total Files**: 277 Python files
- **Total Tokens**: 924,593 tokens (3.86M chars)
- **Source Code Lines**: ~9,500 LOC production code
  - Domain: ~1,250 lines (+200 from v0.3.0)
  - Application: ~2,400 lines (+600 workflows)
  - Adapters: ~4,500 lines (+200 mappers/repos)
  - Infrastructure: ~750 lines (+150 observability)
- **Test Code Lines**: ~4,800 lines
- **Test Coverage**: 59% overall (354/601 tests passing after v0.4.0 migration)

**Top Files by Token Count**:
1. `backups/backup_before_redesign_20251122_191358.json` (182,036 tokens, 19.7%)
2. `alembic/versions/0002_insert_seed_data.py` (41,860 tokens, 4.5%)
3. `src/adapters/llm/langchain_adapter.py` (13,611 tokens, 1.5%)
4. `src/application/workflows/interview_conversation_workflow.py` (12,309 tokens, 1.3%)
5. `src/application/workflows/adaptive_eval_simple_workflow.py` (879 LOC)

**Migration Status**:
- **Database Migrations**: 15 total (0001 through 0015)
- **Latest Migration**: 0015_251122_redesign_schema.py (v0.4.0 schema redesign)
- **Migration Status**: All applied successfully ✅

## Project Structure

```
EliosAIService/
├── src/                          # Source code (Clean Architecture layers)
│   ├── domain/                   # Core business logic (no external dependencies)
│   │   ├── models/              # Domain entities (14 files, 3 NEW in v0.4.0)
│   │   │   ├── candidate.py     # Candidate entity
│   │   │   ├── interview.py     # Interview aggregate root (UPDATED: removed arrays)
│   │   │   ├── interview_question.py # Junction model (NEW v0.4.0)
│   │   │   ├── question.py      # Question value object (UPDATED: ENUMs)
│   │   │   ├── answer.py        # Answer entity
│   │   │   ├── follow_up_question.py  # Follow-up questions
│   │   │   ├── cv_analysis.py   # CV analysis entity (UPDATED: normalized skills)
│   │   │   ├── cv_skill.py      # Normalized skill entity (NEW v0.4.0)
│   │   │   ├── evaluation.py    # Context-aware evaluation
│   │   │   ├── prompt_template.py # Prompt template (NEW v0.4.0)
│   │   │   ├── prompt_execution.py # Prompt execution tracking
│   │   │   ├── prompt_metadata_change.py # Prompt version control
│   │   │   ├── adaptive_models.py # Adaptive evaluation models
│   │   │   └── error_codes.py   # Error code enumeration
│   │   ├── ports/               # Abstract interfaces (13 files)
│   │   │   ├── llm_port.py                      # LLM interface (12 methods)
│   │   │   ├── vector_search_port.py            # Vector DB interface
│   │   │   ├── cv_analyzer_port.py              # CV processing interface
│   │   │   ├── speech_to_text_port.py           # STT interface
│   │   │   ├── text_to_speech_port.py           # TTS interface
│   │   │   ├── analytics_port.py                # Analytics interface
│   │   │   ├── question_repository_port.py      # Question persistence
│   │   │   ├── candidate_repository_port.py     # Candidate persistence
│   │   │   ├── interview_repository_port.py     # Interview persistence (UPDATED)
│   │   │   ├── answer_repository_port.py        # Answer persistence
│   │   │   ├── cv_analysis_repository_port.py   # CV analysis persistence (UPDATED)
│   │   │   ├── follow_up_question_repository_port.py  # Follow-up persistence
│   │   │   └── evaluation_repository_port.py    # Evaluation persistence
│   │   └── services/            # Domain services (2 files)
│   │       ├── ab_test_service.py # A/B testing logic
│   │       └── prompt_diff_service.py # Prompt diff generation
│   ├── application/             # Use cases and orchestration
│   │   ├── dto/                 # Data Transfer Objects (7 files)
│   │   │   ├── interview_dto.py # Interview DTOs
│   │   │   ├── answer_dto.py    # Answer DTOs
│   │   │   ├── audio_dto.py     # Audio DTOs
│   │   │   ├── websocket_dto.py # WebSocket DTOs
│   │   │   ├── detailed_feedback_dto.py # Feedback DTOs
│   │   │   ├── interview_completion_dto.py # Completion DTOs
│   │   │   └── prompt_dto.py    # Prompt DTOs (NEW v0.4.0)
│   │   ├── use_cases/           # Application business flows (9 files)
│   │   │   ├── analyze_cv.py    # CV analysis workflow
│   │   │   ├── plan_interview.py # Interview planning
│   │   │   ├── get_next_question.py # Question retrieval
│   │   │   ├── process_answer_adaptive.py # Adaptive answer evaluation
│   │   │   ├── complete_interview.py # Interview finalization
│   │   │   ├── generate_summary.py # Summary generation
│   │   │   ├── follow_up_decision.py # Follow-up logic
│   │   │   ├── combine_evaluation.py # Evaluation merging
│   │   │   └── refresh_prompt_analytics.py # Analytics refresh
│   │   └── workflows/           # LangGraph workflow orchestration (6 files, NEW v0.3.0)
│   │       ├── base_workflow.py # Base workflow with checkpointing
│   │       ├── planning_workflow.py # Interview planning workflow (497 LOC)
│   │       ├── interview_conversation_workflow.py # QA workflow (1200+ LOC)
│   │       ├── adaptive_eval_simple_workflow.py # Simple evaluation (879 LOC)
│   │       └── adaptive_eval_interrupt_workflow.py # Interrupt-based evaluation
│   ├── adapters/                # External service implementations
│   │   ├── llm/                 # LLM provider adapters (7 files)
│   │   │   ├── langchain_adapter.py # LangChain LCEL adapter (NEW v0.3.0, 450+ LOC)
│   │   │   ├── langchain_models.py # Pydantic structured outputs (NEW v0.3.0)
│   │   │   ├── openai_adapter.py # OpenAI GPT-4 (DEPRECATED)
│   │   │   └── azure_openai_adapter.py # Azure OpenAI
│   │   ├── vector_db/           # Vector database adapters (2 files)
│   │   │   ├── pinecone_adapter.py # Pinecone implementation
│   │   │   └── chroma_adapter.py # ChromaDB implementation
│   │   ├── mock/                # Mock adapters for development (6 files)
│   │   │   ├── mock_llm_adapter.py
│   │   │   ├── mock_vector_search_adapter.py
│   │   │   ├── mock_stt_adapter.py
│   │   │   ├── mock_tts_adapter.py
│   │   │   ├── mock_cv_analyzer.py
│   │   │   └── mock_analytics.py
│   │   ├── persistence/         # Database adapters (12 files, UPDATED v0.4.0)
│   │   │   ├── models.py        # SQLAlchemy ORM models (UPDATED: new tables, ENUMs)
│   │   │   ├── mappers.py       # Domain ↔ DB conversion (UPDATED: new mappers)
│   │   │   ├── candidate_repository.py
│   │   │   ├── question_repository.py
│   │   │   ├── interview_repository.py (UPDATED: junction table methods)
│   │   │   ├── answer_repository.py
│   │   │   ├── cv_analysis_repository.py (UPDATED: skill management)
│   │   │   ├── follow_up_question_repository.py
│   │   │   ├── evaluation_repository.py
│   │   │   └── prompt_repository.py # Prompt versioning (NEW v0.3.0)
│   │   ├── speech/              # Speech service adapters (3 files)
│   │   │   ├── azure_stt_adapter.py # Azure Speech-to-Text
│   │   │   ├── azure_tts_adapter.py # Azure Text-to-Speech
│   │   │   └── azure_speech_adapter.py # Combined speech adapter
│   │   ├── cv_processing/       # CV processing adapters (7 files)
│   │   │   ├── hybrid_cv_analyzer_adapter.py # Main CV analyzer
│   │   │   ├── rule_based_extractor.py # Pattern-based extraction
│   │   │   ├── spacy_ner_extractor.py # NER extraction
│   │   │   ├── llm_fallback_extractor.py # LLM fallback
│   │   │   ├── skill_matcher.py # Skill matching
│   │   │   ├── confidence_scorer.py # Confidence scoring
│   │   │   └── cv_processing_adapter.py # Legacy adapter
│   │   └── api/                 # API layer (5 files)
│   │       ├── rest/            # REST endpoints (3 files)
│   │       │   ├── health_routes.py     # Health check
│   │       │   ├── interview_routes.py  # Interview CRUD
│   │       │   └── prompt_routes.py     # Prompt management (NEW v0.4.0)
│   │       └── websocket/       # WebSocket handlers (3 files)
│   │           ├── connection_manager.py # Connection pool
│   │           ├── session_orchestrator.py # Session state machine
│   │           └── interview_handler.py  # WebSocket handler
│   └── infrastructure/          # Cross-cutting concerns
│       ├── config/              # Configuration management (2 files)
│       │   ├── settings.py      # Pydantic settings
│       │   └── logging.yaml     # Logging configuration
│       ├── database/            # Database infrastructure (4 files)
│       │   ├── base.py          # SQLAlchemy base
│       │   ├── session.py       # Async session management
│       │   └── langgraph_checkpointer.py # LangGraph checkpointer (NEW v0.3.0)
│       ├── observability/       # Observability infrastructure (3 files, NEW v0.3.0)
│       │   ├── langsmith_config.py # LangSmith tracing with PII filtering
│       │   └── cost_tracking.py # LLM cost tracking
│       ├── background/          # Background jobs (2 files)
│       │   └── view_refresh_job.py # Analytics view refresh
│       └── dependency_injection/
│           └── container.py     # DI container
├── alembic/                     # Database migrations
│   └── versions/                # Migration scripts (15 migrations)
│       ├── 0001-0014_*.py       # Previous migrations
│       └── 0015_251122_redesign_schema.py (NEW v0.4.0 - Schema redesign)
├── tests/                       # Test suites
│   ├── unit/                    # Unit tests (200+ tests)
│   │   ├── domain/              # Domain model tests
│   │   ├── application/         # Use case & workflow tests
│   │   ├── adapters/            # Adapter tests
│   │   └── infrastructure/      # Infrastructure tests
│   ├── integration/             # Integration tests (30+ tests)
│   │   ├── api/                 # API integration tests
│   │   ├── adapters/            # Adapter integration tests
│   │   └── workflows/           # Workflow integration tests
│   ├── parity/                  # Parity tests (4 files, NEW v0.3.1)
│   │   ├── test_evaluation_parity.py
│   │   ├── test_followup_parity.py
│   │   ├── test_gap_parity.py
│   │   └── test_message_parity.py
│   ├── bot/                     # Interview test bot (15 files, NEW)
│   │   ├── test_bot_client.py   # WebSocket test client
│   │   ├── answer_generator.py  # Answer generation
│   │   ├── metrics_collector.py # Performance metrics
│   │   ├── assertion_validator.py # Assertion logic
│   │   ├── test_runner.py       # Test orchestration
│   │   ├── report_generator.py  # Report generation
│   │   ├── run_tests.py         # CLI entry point
│   │   ├── scenarios/           # Test scenarios
│   │   │   ├── mock_scenarios.yaml   # 8 mock tests (no cost)
│   │   │   └── real_scenarios.yaml   # 5 real tests (~$0.45)
│   │   └── fixtures/            # Test fixtures
│   │       ├── cvs/             # CV JSON files (5 files)
│   │       └── baselines/       # Performance baselines
│   ├── prototypes/              # Performance prototypes (3 files, NEW v0.3.0)
│   │   ├── 01_token_benchmark.py
│   │   ├── 02_interrupt_pattern.py
│   │   └── 03_performance_baseline.py
│   ├── performance/             # Performance tests
│   ├── validation/              # Validation suite
│   └── conftest.py              # Test fixtures
├── docs/                        # Project documentation
│   ├── project-overview-pdr.md
│   ├── codebase-summary.md     # This file
│   ├── code-standards.md
│   ├── system-architecture.md
│   ├── project-roadmap.md
│   ├── deployment-guide.md
│   ├── design-guidelines.md
│   ├── observability-guide.md  # NEW v0.3.0
│   └── migrations/
│       └── 0015-schema-redesign.md # NEW v0.4.0
├── backups/                     # Database backups before redesign
├── validation_reports/          # Validation reports
├── .env.example                # Environment variables template
├── .env.test.example           # Test environment template
├── pyproject.toml              # Project metadata & dependencies
├── CLAUDE.md                   # Claude Code instructions
├── README.md                   # Project overview
└── repomix-output.xml          # Codebase compaction

```

## Core Technologies

### Runtime & Language
- **Python**: 3.11+ (type hints, async/await)
- **Package Manager**: pip with pyproject.toml
- **Build System**: setuptools

### Web Framework
- **FastAPI**: 0.104.0+ (async REST API, WebSocket, OpenAPI)
- **Uvicorn**: 0.24.0+ (ASGI server)
- **Pydantic**: 2.5.0+ (data validation and settings)

### AI & Machine Learning
- **OpenAI**: 1.3.0+ (GPT-4 for NLP)
- **LangChain**: 0.3.11+ (LLM workflow orchestration) **NEW v0.3.0**
- **LangChain OpenAI**: 0.2.12+ **NEW v0.3.0**
- **LangGraph**: 0.2.59+ (State machine workflows) **NEW v0.3.0**
- **LangGraph Checkpoint Postgres**: 2.0.11+ **NEW v0.3.0**
- **LangSmith**: 0.2.3+ (Observability) **NEW v0.3.0**
- **spaCy**: 3.7.0+ (NLP text processing)

### Vector Database
- **Pinecone Client**: 3.0.0+ (semantic search)
- **ChromaDB**: Local vector database alternative

### Database & ORM
- **PostgreSQL**: 14+ (Neon cloud database)
- **SQLAlchemy**: 2.0.0+ with asyncio support
- **asyncpg**: 0.29.0+ (async PostgreSQL driver)
- **Alembic**: 1.13.0+ (database migrations)

### Development Tools
- **pytest**: 7.4.0+ (testing framework)
- **pytest-asyncio**: 0.21.0+ (async test support)
- **pytest-cov**: 4.1.0+ (coverage reporting)
- **ruff**: 0.1.6+ (fast Python linter)
- **black**: 23.11.0+ (code formatter)
- **mypy**: 1.7.0+ (static type checker)

## Recent Major Changes

### v0.4.0 - Schema Redesign (2025-11-22)

**Database Schema Changes**:
1. **Normalized `cv_skills` table** (replaces JSONB array):
   - Fields: `id`, `cv_analysis_id`, `skill_name`, `proficiency_level` (ENUM), `years_of_experience`, `is_primary`
   - ENUM `ProficiencyLevel`: BEGINNER, INTERMEDIATE, ADVANCED, EXPERT
   - Proper foreign key relationship to `cv_analyses`

2. **Junction `interview_questions` table** (replaces question_ids array):
   - Fields: `id`, `interview_id`, `question_id`, `sequence_order`, `asked_at`, `skipped`, `skip_reason`
   - Enables proper SQL queries with JOINs and ordering

3. **PostgreSQL ENUMs** for type safety:
   - `question_type_enum`: TECHNICAL, BEHAVIORAL, SITUATIONAL, PROBLEM_SOLVING, SYSTEM_DESIGN
   - `difficulty_enum`: EASY, MEDIUM, HARD, EXPERT
   - `proficiency_level_enum`: BEGINNER, INTERMEDIATE, ADVANCED, EXPERT

4. **Decomposed `prompt_templates` table** (11 editable columns):
   - Replaced single `template_json` JSONB column
   - Individual columns: `system_prompt`, `user_template`, `input_variables`, `output_schema`, `few_shot_examples`, `constraints`, `temperature`, `max_tokens`, `stop_sequences`, `model_specific_config`, `validation_rules`

5. **Removed redundant columns**:
   - `cv_file_path` moved to `Candidate` entity
   - `metadata` removed from `cv_analyses` (confidence data no longer stored)
   - `tags` removed from `questions` (no longer needed)

**Code Changes**:
- **Updated 3 domain models**: Interview, CVAnalysis, Question
- **NEW 3 domain models**: InterviewQuestion, CVSkill, PromptTemplate (decomposed)
- **Updated 2 mappers**: CVAnalysisMapper, InterviewMapper
- **NEW 2 mappers**: CVSkillMapper, InterviewQuestionMapper
- **Updated 2 repositories**: CVAnalysisRepository, InterviewRepository
- **Updated 5 use cases**: PlanInterviewUseCase, etc.
- **Updated 2 workflows**: PlanningWorkflow, InterviewConversationWorkflow

**Migration**: 0015_251122_redesign_schema.py (zero data loss, comprehensive backup)

### v0.3.0 - LangChain/LangGraph Integration (2025-11-15 → 2025-11-23)

**New Components**:
1. **LangChain LCEL Adapter** (453 LOC):
   - 12 LCEL chains (one per LLMPort method)
   - 9 Pydantic structured output models
   - RunnableParallel for batch operations (10x faster)
   - Database-driven prompt loading

2. **LangGraph Workflows** (3 workflows):
   - `PlanningWorkflow` (497 LOC): Interview planning with parallel question generation
   - `AdaptiveEvalSimpleWorkflow` (879 LOC): Context-aware evaluation
   - `InterviewConversationWorkflow` (1200+ LOC): Full QA orchestration

3. **PostgreSQL Checkpointing**: State persistence for crash recovery

4. **LangSmith Observability** (308 LOC):
   - PIIFilteringTracer with 5 redaction patterns
   - Cost tracking per interview
   - Metadata injection for trace filtering

5. **Cost Tracking Module** (371 LOC):
   - Interview-level cost aggregation
   - Daily cost summaries
   - Model-specific pricing

## Key Components

### 1. Domain Layer (Core Business Logic)

**Location**: `src/domain/`
**Responsibility**: Pure business logic with zero external dependencies

#### Models (14 files)
- **Interview** (UPDATED v0.4.0): Aggregate root, removed `question_ids`/`answer_ids` arrays
- **InterviewQuestion** (NEW v0.4.0): Junction model for interview-question relationships
- **CVAnalysis** (UPDATED v0.4.0): Removed `metadata`, skills now normalized
- **CVSkill** (NEW v0.4.0): Normalized skill entity with proficiency ENUM
- **Question** (UPDATED v0.4.0): ENUMs for type/difficulty, removed `tags`
- **PromptTemplate** (NEW v0.4.0): Decomposed template with 11 editable columns
- **Answer**, **Candidate**, **Evaluation**, **FollowUpQuestion**, etc.

#### Ports (13 files)
Abstract interfaces for external dependencies:
- **LLMPort** (12 methods): Question generation, answer evaluation, gap detection, etc.
- **VectorSearchPort**: Semantic search operations
- **Repository Ports** (9 total): Candidate, Interview (UPDATED), Question, Answer, CVAnalysis (UPDATED), Evaluation, FollowUpQuestion, PromptTemplate
- **Speech Ports**: STT, TTS
- **Analytics Port**

### 2. Application Layer (Use Cases & Workflows)

**Location**: `src/application/`

#### Use Cases (9 files)
- **PlanInterviewUseCase** (UPDATED v0.4.0): Uses junction table methods
- **AnalyzeCVUseCase**: CV analysis workflow
- **ProcessAnswerAdaptiveUseCase**: Adaptive answer evaluation
- **FollowUpDecisionUseCase**: Follow-up logic with break conditions
- **CombineEvaluationUseCase**: Evaluation merging
- **GenerateSummaryUseCase**: Comprehensive summary generation
- **CompleteInterviewUseCase**: Interview finalization
- **GetNextQuestionUseCase**: Question retrieval
- **RefreshPromptAnalyticsUseCase**: Analytics refresh

#### Workflows (6 files, NEW v0.3.0)
- **BaseWorkflow**: Common utilities for all workflows
- **PlanningWorkflow** (497 LOC): Interview planning with parallel generation
- **InterviewConversationWorkflow** (1200+ LOC): Full QA orchestration
- **AdaptiveEvalSimpleWorkflow** (879 LOC): Simple adaptive evaluation
- **AdaptiveEvalInterruptWorkflow**: Interrupt-based evaluation

### 3. Adapters Layer (External Integrations)

**Location**: `src/adapters/`

#### LLM Adapters (7 files)
- **LangChainAdapter** (NEW v0.3.0, 450+ LOC): Primary adapter with LCEL chains
- **LangChainModels** (NEW v0.3.0): 9 Pydantic structured output models
- **OpenAIAdapter** (DEPRECATED): Direct OpenAI API
- **AzureOpenAIAdapter**: Azure-hosted OpenAI
- **MockLLMAdapter**: Mock for development

#### Vector Database Adapters (2 files)
- **PineconeAdapter**: Serverless Pinecone
- **ChromaAdapter**: Local ChromaDB

#### Persistence Adapters (12 files)
- **models.py** (UPDATED v0.4.0): New tables (CVSkillModel, InterviewQuestionModel), ENUMs
- **mappers.py** (UPDATED v0.4.0): New mappers (CVSkillMapper, InterviewQuestionMapper)
- **interview_repository.py** (UPDATED v0.4.0): Junction table methods
- **cv_analysis_repository.py** (UPDATED v0.4.0): Skill management methods
- **prompt_repository.py** (NEW v0.3.0): Prompt versioning
- **candidate_repository.py**, **question_repository.py**, **answer_repository.py**, **evaluation_repository.py**, **follow_up_question_repository.py**

#### CV Processing Adapters (7 files)
- **HybridCVAnalyzerAdapter**: Main CV analyzer with 3-strategy pipeline
- **RuleBasedExtractor**: Pattern-based extraction
- **SpacyNERExtractor**: Named entity recognition
- **LLMFallbackExtractor**: LLM fallback
- **SkillMatcher**: Fuzzy skill matching
- **ConfidenceScorer**: Confidence scoring

#### Speech Adapters (3 files)
- **AzureSTTAdapter**: Azure Speech-to-Text
- **AzureTTSAdapter**: Azure Text-to-Speech
- **AzureSpeechAdapter**: Combined speech adapter

### 4. Infrastructure Layer (Cross-Cutting Concerns)

**Location**: `src/infrastructure/`

#### Configuration (2 files)
- **settings.py** (750 LOC): Pydantic Settings with 15+ config groups
- **logging.yaml**: Structured logging configuration

#### Database (4 files)
- **session.py**: Async SQLAlchemy session management
- **base.py**: SQLAlchemy base class
- **langgraph_checkpointer.py** (NEW v0.3.0): PostgreSQL checkpointer

#### Observability (3 files, NEW v0.3.0)
- **langsmith_config.py** (308 LOC): PII filtering tracer
- **cost_tracking.py** (371 LOC): Cost tracking module

#### Dependency Injection (1 file)
- **container.py** (400+ LOC): Central DI container

## Entry Points

### For Users
- **README.md**: Project overview and quick start
- **docs/project-overview-pdr.md**: Product requirements and roadmap

### For Developers
- **pyproject.toml**: Dependencies, scripts, tool configuration
- **CLAUDE.md**: Development instructions and architecture overview
- **src/main.py**: Application entry point (FastAPI app)

### For Testing
- **tests/**: Test suites (354/601 tests passing)
- **pytest.ini**: Test configuration
- **tests/conftest.py**: Shared test fixtures

## Development Workflow

### Local Development Setup

```bash
# 1. Clone repository
git clone https://github.com/elios/elios-ai-service.git
cd EliosAIService

# 2. Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows

# 3. Install dependencies
pip install -e ".[dev]"

# 4. Configure environment
cp .env.example .env.local
# Edit .env.local with API keys

# 5. Run migrations
alembic upgrade head

# 6. Start development server
python -m src.main
```

### Testing Strategy

**Unit Tests** (`tests/unit/`):
- Test domain logic in isolation
- Mock all ports
- Fast execution (milliseconds)
- 200+ tests

**Integration Tests** (`tests/integration/`):
- Test adapters with real services
- Use test environments
- 30+ tests

**Parity Tests** (`tests/parity/` - NEW v0.3.1):
- Ensure workflow-legacy parity
- Message format validation
- Follow-up behavior consistency
- 4 test files

**Performance Prototypes** (`tests/prototypes/` - NEW v0.3.0):
- Token usage benchmarks
- Interrupt pattern performance
- Workflow performance baselines
- 3 prototypes

## Implementation Status

### ✅ Complete (v0.4.0 Current)

**Phase 1 Foundation**:
- Domain models (14 entities)
- Repository ports (13 interfaces)
- PostgreSQL persistence (12 repositories)
- OpenAI + Azure OpenAI LLM adapters
- Pinecone + ChromaDB vector adapters
- Mock adapters (6 total)
- Database migrations (15 migrations)
- Configuration management
- Dependency injection container

**Phase 1.5 LangChain/LangGraph Integration** (v0.3.0):
- LangChain LCEL adapter with 12 chains
- Structured outputs with Pydantic models (9 schemas)
- LangGraph workflows (3 workflows)
- PostgreSQL checkpointing
- LangSmith observability with PII filtering
- Cost tracking module

**Phase 1.6 Schema Redesign** (v0.4.0):
- Normalized `cv_skills` table
- Junction `interview_questions` table
- PostgreSQL ENUMs for type safety
- Decomposed `prompt_templates` table
- Updated domain models, mappers, repositories
- Zero data loss migration

**Phase 1.7 Evaluation Enhancement**:
- Context-aware evaluation with entity separation
- Parent-child evaluation relationships
- Combined evaluation use case
- Evaluation repository and persistence

**Phase 1.8 State Management**:
- Domain-Driven State Management
- Interview state machine in domain layer
- State transition validation
- WebSocket orchestrator delegates to domain

### 🔄 In Progress

- CV processing refinement (HybridCVAnalyzerAdapter)
- Speech service integration (Azure STT/TTS)
- Advanced analytics
- Test coverage expansion (59% → 80%+)

### ⏳ Planned (Future Phases)

- Claude and Llama LLM adapters
- Weaviate vector adapter alternative
- Authentication & authorization
- Rate limiting
- Comprehensive E2E test suites
- Docker deployment
- CI/CD pipeline

## Dependencies Overview

### Production Dependencies (40+ packages)

**Core Framework**:
- fastapi>=0.104.0
- uvicorn[standard]>=0.24.0
- pydantic>=2.5.0
- pydantic-settings>=2.1.0

**LangChain/LangGraph Stack** (NEW v0.3.0):
- langchain>=0.3.11
- langchain-openai>=0.2.12
- langchain-core>=0.3.24
- langgraph>=0.2.59
- langgraph-checkpoint-postgres>=2.0.11
- langsmith>=0.2.3

**AI & Machine Learning**:
- openai>=1.3.0
- pinecone-client>=3.0.0
- chromadb
- spacy>=3.7.0

**Database & ORM**:
- sqlalchemy[asyncio]>=2.0.0
- asyncpg>=0.29.0
- alembic>=1.13.0

**Speech Services**:
- azure-cognitiveservices-speech

**Utilities**:
- python-multipart
- python-jose[cryptography]
- passlib[bcrypt]
- aiofiles

### Development Dependencies (9 packages)

**Testing**:
- pytest>=7.4.0
- pytest-asyncio>=0.21.0
- pytest-cov>=4.1.0
- pytest-mock>=3.12.0

**Code Quality**:
- ruff>=0.1.6
- black>=23.11.0
- mypy>=1.7.0

**Development**:
- ipython
- httpx

**Total Dependencies**: 50+ packages

## Related Documentation

- [Project Overview & PDR](./project-overview-pdr.md) - Product requirements and roadmap
- [System Architecture](./system-architecture.md) - Detailed architecture documentation
- [Code Standards](./code-standards.md) - Coding conventions and best practices
- [Project Roadmap](./project-roadmap.md) - Development timeline and milestones
- [Observability Guide](./observability-guide.md) - LangSmith tracing and cost tracking
- [Migration 0015 Docs](./migrations/0015-schema-redesign.md) - v0.4.0 schema redesign guide

---

**Document Status**: Living document, updated with each milestone
**Next Review**: After major architectural changes
**Maintainers**: Elios Development Team
