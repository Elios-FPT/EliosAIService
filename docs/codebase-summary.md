# Codebase Summary

**Last Updated**: 2025-11-22
**Version**: 0.4.0 (Schema Redesign - Normalized DB + ENUMs)
**Repository**: https://github.com/elios/elios-ai-service

## Table of Contents

- [Overview](#overview)
- [Project Structure](#project-structure)
- [Core Technologies](#core-technologies)
- [Key Components](#key-components)
- [Entry Points](#entry-points)
- [Development Workflow](#development-workflow)
- [Development Principles](#development-principles)
- [Implementation Status](#implementation-status)
- [File Statistics](#file-statistics)
- [Dependencies Overview](#dependencies-overview)
- [Performance Considerations](#performance-considerations)
- [Security Measures](#security-measures)
- [Deployment](#deployment)
- [Related Documentation](#related-documentation)
- [External Resources](#external-resources)

## Overview

Elios AI Interview Service is Python-based AI-powered mock interview platform built with Clean Architecture principles (Hexagonal/Ports & Adapters pattern). Platform emphasizes separation of concerns, testability, flexibility through abstract interfaces and dependency injection. Integrates LangChain/LangGraph for workflow orchestration, OpenAI GPT-4 for NLP, Pinecone for vector-based semantic search, PostgreSQL for persistent storage.

**Recent Major Changes** (2025-11-22):
- **Schema Redesign (v0.4.0 - NEW)**: Normalized database schema with junction tables + ENUMs
  - `cv_skills` table replaces JSONB array (proper relationships)
  - `interview_questions` junction table replaces question_ids array
  - ENUMs for type safety: `question_type_enum`, `difficulty_enum`, `proficiency_level_enum`
  - Decomposed `prompt_templates` into 11 editable columns
  - Removed redundant columns (cv_file_path moved to Candidate, metadata removed)
- **Interview Test Bot**: Automated WebSocket testing framework with 8 mock + 5 real scenarios
- **LangChain/LangGraph Integration**: LCEL chains, structured outputs, workflow orchestration
- **Observability Module**: LangSmith tracing with PII filtering, cost tracking
- **Context-aware evaluation** with entity separation
- **Domain-Driven State Management** (migrated from WebSocket orchestrator)

## Project Structure

```
EliosAIService/
├── src/                          # Source code (Clean Architecture layers)
│   ├── domain/                   # Core business logic (no external dependencies)
│   │   ├── models/              # Domain entities (11 files - 3 NEW)
│   │   │   ├── __init__.py
│   │   │   ├── candidate.py     # Candidate entity
│   │   │   ├── interview.py     # Interview aggregate root (UPDATED: removed question_ids, answer_ids)
│   │   │   ├── interview_question.py # Junction model (NEW)
│   │   │   ├── question.py      # Question value object (UPDATED: ENUMs, new types)
│   │   │   ├── answer.py        # Answer entity (UPDATED: removed candidate_id)
│   │   │   ├── follow_up_question.py  # Follow-up question for adaptive interviews
│   │   │   ├── cv_analysis.py   # CV analysis entity (UPDATED: removed metadata, cv_file_path)
│   │   │   ├── cv_skill.py      # Normalized skill entity (NEW)
│   │   │   ├── evaluation.py    # Evaluation entity with context separation
│   │   │   ├── prompt_template.py # Prompt template (NEW - decomposed from JSONB)
│   │   │   └── error_codes.py   # Error code enumeration
│   │   └── ports/               # Abstract interfaces (13 files)
│   │       ├── llm_port.py                      # LLM interface
│   │       ├── vector_search_port.py            # Vector DB interface
│   │       ├── cv_analyzer_port.py              # CV processing interface
│   │       ├── speech_to_text_port.py           # STT interface
│   │       ├── text_to_speech_port.py           # TTS interface
│   │       ├── analytics_port.py                # Analytics interface
│   │       ├── question_repository_port.py      # Question persistence
│   │       ├── candidate_repository_port.py     # Candidate persistence
│   │       ├── interview_repository_port.py     # Interview persistence
│   │       ├── answer_repository_port.py        # Answer persistence
│   │       ├── cv_analysis_repository_port.py   # CV analysis persistence
│   │       ├── follow_up_question_repository_port.py  # Follow-up persistence
│   │       └── evaluation_repository_port.py    # Evaluation persistence
│   ├── application/             # Use cases and orchestration
│   │   ├── dto/                 # Data Transfer Objects (6 files)
│   │   │   ├── interview_dto.py # Interview DTOs (incl. PlanningStatusResponse w/ ws_url)
│   │   │   ├── answer_dto.py    # Answer request/response DTOs
│   │   │   ├── audio_dto.py     # Audio processing DTOs
│   │   │   ├── websocket_dto.py # WebSocket message DTOs
│   │   │   ├── detailed_feedback_dto.py # Detailed feedback DTOs
│   │   │   └── prompt_dto.py    # Prompt template DTOs (NEW v0.4.0)
│   │   ├── use_cases/           # Application business flows (8 files)
│   │   │   ├── analyze_cv.py    # CV analysis workflow
│   │   │   ├── plan_interview.py # Interview planning with adaptive questions
│   │   │   ├── get_next_question.py # Retrieve next question
│   │   │   ├── process_answer_adaptive.py # Adaptive answer evaluation
│   │   │   ├── complete_interview.py # Finalize interview session
│   │   │   ├── generate_summary.py # Interview summary generation
│   │   │   ├── follow_up_decision.py # Follow-up decision logic
│   │   │   └── combine_evaluation.py # Combine evaluations
│   │   └── workflows/           # LangGraph workflow orchestration (NEW - 5 files)
│   │       ├── __init__.py
│   │       ├── base_workflow.py # Base workflow with LangGraph checkpointing
│   │       ├── planning_workflow.py # Interview planning workflow
│   │       ├── adaptive_eval_simple_workflow.py # Simple adaptive evaluation
│   │       └── adaptive_eval_interrupt_workflow.py # Interrupt-based evaluation
│   ├── adapters/                # External service implementations
│   │   ├── llm/                 # LLM provider adapters (NEW: LangChain)
│   │   │   ├── __init__.py
│   │   │   ├── openai_adapter.py # OpenAI GPT-4 implementation
│   │   │   ├── azure_openai_adapter.py # Azure OpenAI implementation
│   │   │   ├── langchain_adapter.py # LangChain LCEL adapter (NEW)
│   │   │   ├── langchain_models.py # Pydantic models for structured output (NEW)
│   │   │   └── prompts/         # Prompt templates (NEW)
│   │   │       └── __init__.py
│   │   ├── vector_db/           # Vector database adapters
│   │   │   ├── pinecone_adapter.py # Pinecone implementation
│   │   │   └── chroma_adapter.py # ChromaDB implementation
│   │   ├── mock/                # Mock adapters for development (6 total)
│   │   │   ├── mock_llm_adapter.py
│   │   │   ├── mock_vector_search_adapter.py
│   │   │   ├── mock_stt_adapter.py
│   │   │   ├── mock_tts_adapter.py
│   │   │   ├── mock_cv_analyzer.py
│   │   │   └── mock_analytics.py
│   │   ├── persistence/         # Database adapters (10 files)
│   │   │   ├── models.py        # SQLAlchemy ORM models
│   │   │   ├── mappers.py       # Domain ↔ DB model conversion
│   │   │   ├── candidate_repository.py
│   │   │   ├── question_repository.py
│   │   │   ├── interview_repository.py
│   │   │   ├── answer_repository.py
│   │   │   ├── cv_analysis_repository.py
│   │   │   ├── follow_up_question_repository.py
│   │   │   └── evaluation_repository.py  # Evaluation persistence
│   │   ├── speech/              # Speech service adapters
│   │   │   ├── azure_stt_adapter.py # Azure Speech-to-Text
│   │   │   └── azure_tts_adapter.py # Azure Text-to-Speech
│   │   ├── cv_processing/       # CV processing adapters
│   │   │   └── cv_processing_adapter.py
│   │   └── api/                 # API layer
│   │       ├── rest/            # REST endpoints (3 files)
│   │       │   ├── health_routes.py     # Health check endpoint
│   │       │   ├── interview_routes.py  # Interview CRUD endpoints
│   │       │   └── prompt_routes.py     # Prompt management endpoints (NEW v0.4.0)
│   │       └── websocket/       # WebSocket handlers (3 files)
│   │           ├── connection_manager.py # WebSocket connection pool
│   │           ├── session_orchestrator.py # Session orchestrator (delegated to domain)
│   │           └── interview_handler.py  # Simplified WebSocket I/O handler
│   └── infrastructure/          # Cross-cutting concerns
│       ├── config/              # Configuration management
│       │   └── settings.py      # Pydantic settings
│       ├── database/            # Database infrastructure
│       │   ├── base.py          # SQLAlchemy base class
│       │   ├── session.py       # Async session management
│       │   └── langgraph_checkpointer.py # LangGraph PostgreSQL checkpointer (NEW)
│       ├── observability/       # Observability infrastructure (NEW - 3 files)
│       │   ├── __init__.py
│       │   ├── langsmith_config.py # LangSmith tracing with PII filtering
│       │   └── cost_tracking.py # LLM cost tracking and monitoring
│       └── dependency_injection/
│           └── container.py     # DI container
├── alembic/                     # Database migrations
│   └── versions/                # Migration scripts (15 migrations)
│       ├── 0001_create_tables.py
│       ├── 0002_insert_seed_data.py
│       ├── 0003_create_evaluations_tables.py
│       ├── 0004_clear_data_and_seed_candidates_vi.py
│       ├── 0005_seed_questions_vi.py
│       ├── 0006_seed_cv_analyses_vi.py
│       ├── 0007_seed_interviews_vi.py
│       ├── 0008_seed_answers_vi.py
│       ├── 0009_seed_followup_questions_vi.py
│       ├── 0010_create_prompt_templates_table.py
│       ├── 0011_create_prompt_metadata_changes.py
│       ├── 0012_create_prompt_executions.py
│       ├── 0013_seed_prompt_templates.py
│       ├── 0014_seed_more_prompt_templates.py
│       └── 0015_251122_redesign_schema.py (NEW - Schema Redesign)
├── tests/                       # Test suites
│   ├── unit/                    # Unit tests (200+ tests)
│   │   ├── domain/              # Domain model tests
│   │   ├── application/         # Use case & workflow tests
│   │   ├── adapters/            # Adapter tests
│   │   └── infrastructure/      # Infrastructure tests
│   ├── integration/             # Integration tests
│   │   ├── api/                 # API integration tests
│   │   └── workflows/           # Workflow integration tests
│   ├── bot/                     # Interview test bot (NEW)
│   │   ├── test_bot_client.py   # WebSocket test client
│   │   ├── answer_generator.py  # Answer generation (good/average/weak)
│   │   ├── metrics_collector.py # Performance and cost metrics
│   │   ├── assertion_validator.py # Assertion evaluation logic
│   │   ├── test_runner.py       # Test orchestration
│   │   ├── report_generator.py  # JSON/HTML report generation
│   │   ├── run_tests.py         # CLI entry point
│   │   ├── scenarios/           # YAML test scenario definitions
│   │   │   ├── mock_scenarios.yaml   # 8 mock tests (no cost)
│   │   │   └── real_scenarios.yaml   # 5 real tests (~$0.45)
│   │   └── fixtures/            # Test fixtures
│   │       ├── cvs/             # CV JSON files (5 files)
│   │       └── baselines/       # Performance baselines
│   ├── prototypes/              # Performance prototypes (NEW)
│   │   ├── 01_token_benchmark.py
│   │   ├── 02_interrupt_pattern.py
│   │   ├── 03_performance_baseline.py
│   │   └── reports/
│   └── conftest.py              # Test fixtures
├── docs/                        # Project documentation
│   ├── project-overview-pdr.md
│   ├── codebase-summary.md     # This file
│   ├── code-standards.md
│   ├── system-architecture.md
│   ├── project-roadmap.md
│   └── observability-guide.md  # Observability documentation (NEW)
├── .env.example                # Environment variables template
├── pyproject.toml              # Project metadata & dependencies
├── CLAUDE.md                   # Claude Code instructions
└── README.md                   # Project overview
```

## Core Technologies

### Runtime & Language
- **Python**: 3.11+ (type hints, async/await)
- **Package Manager**: pip with pyproject.toml
- **Build System**: setuptools
- **License**: MIT

### Web Framework
- **FastAPI**: 0.104.0+ (async REST API, WebSocket, OpenAPI)
- **Uvicorn**: 0.24.0+ (ASGI server with standard extras)
- **Pydantic**: 2.5.0+ (data validation and settings)
- **Pydantic Settings**: 2.1.0+ (environment variable management)

### AI & Machine Learning
- **OpenAI**: 1.3.0+ (GPT-4 for NLP, embeddings, evaluation)
- **LangChain**: 0.2.0+ (LLM workflow orchestration with LCEL chains) **NEW**
- **LangChain OpenAI**: 0.2.0+ (OpenAI integration for LangChain) **NEW**
- **LangChain Anthropic**: 0.2.0+ (Anthropic Claude integration) **NEW**
- **LangGraph**: 0.2.0+ (State machine workflows for LLMs) **NEW**
- **LangGraph Checkpoint Postgres**: 0.2.0+ (PostgreSQL checkpointing) **NEW**
- **LangSmith**: 0.1.0+ (Observability and tracing) **NEW**
- **Anthropic**: 0.7.0+ (Claude support - planned)
- **spaCy**: 3.7.0+ (NLP text processing - planned)

### Vector Database
- **Pinecone Client**: 3.0.0+ (semantic search, embeddings storage)
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
- **pytest-mock**: 3.12.0+ (mocking utilities)
- **ruff**: 0.1.6+ (fast Python linter)
- **black**: 23.11.0+ (code formatter)
- **mypy**: 1.7.0+ (static type checker)

## Key Components

### 1. Domain Layer (Core Business Logic)

**Location**: `src/domain/`
**Responsibility**: Pure business logic with zero external dependencies

#### Models (`src/domain/models/`)

**Interview** (`interview.py` - UPDATED):
- **Domain-Driven State Management** (migrated from WebSocket orchestrator)
- Aggregate root controlling interview lifecycle
- States: IDLE, QUESTIONING, EVALUATING, REVIEWING, COMPLETED
- Methods: `transition_to()`, `can_transition_to()`, `validate_state_transition()`
- **BREAKING CHANGES**: Removed `question_ids`, `answer_ids` arrays
  - Use `InterviewRepository.get_interview_questions()` instead
  - Removed methods: `has_more_questions()`, `get_current_question_id()`
- Progress tracking via junction table queries

**InterviewQuestion** (`interview_question.py` - NEW):
- Junction model for interview-question relationships
- Fields: `interview_id`, `question_id`, `sequence_order`, `asked_at`, `skipped`, `skip_reason`
- Replaces array-based question tracking
- Enables proper SQL queries with JOINs and ordering

**CVSkill** (`cv_skill.py` - NEW):
- Normalized skill entity (replaces JSONB array)
- Fields: `cv_analysis_id`, `skill_name`, `proficiency_level` (ENUM), `years_of_experience`, `is_primary`
- ENUM `ProficiencyLevel`: BEGINNER, INTERMEDIATE, ADVANCED, EXPERT
- Proper foreign key relationship to CVAnalysis

**Evaluation** (`evaluation.py`):
- **Context-aware evaluation entity** with parent/child separation
- Types: PARENT_QUESTION, FOLLOW_UP, COMBINED
- Fields: `parent_evaluation`, `child_evaluations`, `context_type`
- Methods: `add_child_evaluation()`, `get_combined_score()`, `has_children()`

**Answer** (`answer.py`):
- Entity containing candidate responses
- Includes evaluation results (scores, feedback)
- Methods: `evaluate()`, `is_evaluated()`, `get_score()`, `has_gaps()`, `is_adaptive_complete()`
- Support for both text and voice answers

**Question** (`question.py` - UPDATED):
- Value object representing interview questions
- **ENUM QuestionType**: TECHNICAL, BEHAVIORAL, SITUATIONAL, **PROBLEM_SOLVING** (NEW), **SYSTEM_DESIGN** (NEW)
- **ENUM Difficulty**: EASY, MEDIUM, HARD, **EXPERT** (NEW)
- **REMOVED**: `tags` column (no longer needed)
- Methods: `has_skill()`, `is_suitable_for_difficulty()`, `has_ideal_answer()`
- Supports semantic search via embeddings

**CVAnalysis** (`cv_analysis.py` - UPDATED):
- Entity storing structured CV analysis
- **BREAKING CHANGES**:
  - Removed `metadata` field (confidence data no longer stored)
  - Removed `cv_file_path` (moved to Candidate entity)
  - `skills` is now list of `CVSkill` entities (not JSONB)
- Methods: `add_skill()` (NEW), `get_primary_skills()` (NEW), `get_skills_by_proficiency()` (NEW), `has_skill()`, `get_top_skills()`, `is_experienced()`

**PromptTemplate** (`prompt_template.py` - NEW):
- Prompt template with decomposed editable fields
- **11 editable columns**: `system_prompt`, `user_template`, `input_variables`, `output_schema`, `few_shot_examples`, `constraints`, `temperature`, `max_tokens`, `stop_sequences`, `model_specific_config`, `validation_rules`
- Replaces `template_json` JSONB column
- Enables UI-based prompt editing and A/B testing

**Candidate** (`candidate.py` - 41 lines):
- Rich domain model for interview candidates
- Methods: `update_cv()`, `has_cv()`
- Fields: id, name, email, cv_file_path, timestamps

**FollowUpQuestion** (`follow_up_question.py`):
- Entity for adaptive follow-up questions
- Fields: `parent_question_id`, `order`, `context`
- Methods: `is_first_follow_up()`, `is_second_follow_up()`, `is_third_follow_up()`

### 2. Application Layer (Use Cases & Workflows)

**Location**: `src/application/`
**Responsibility**: Orchestrate domain objects to accomplish business flows

#### Workflows (`application/workflows/` - **NEW**)

**BaseWorkflow** (`base_workflow.py`):
- Base class for all LangGraph workflows
- PostgreSQL checkpointing integration
- Thread-based state management
- Methods: `compile()`, `invoke()`, `get_state()`, `update_state()`

**PlanningWorkflow** (`planning_workflow.py`):
- Interview planning workflow with LangGraph
- State: cv_analysis, question_count, questions, embeddings
- Nodes: analyze_cv, generate_questions, store_embeddings
- Edges: conditional routing based on question count

**AdaptiveEvalSimpleWorkflow** (`adaptive_eval_simple_workflow.py`):
- Simple adaptive evaluation without interrupts
- State: question, answer, evaluation, follow_ups
- Nodes: evaluate_answer, decide_follow_up, generate_follow_up
- Edges: conditional based on gap detection

**AdaptiveEvalInterruptWorkflow** (`adaptive_eval_interrupt_workflow.py`):
- Interrupt-based adaptive evaluation (human-in-loop)
- State: question, answer, evaluation, follow_ups, interrupt_data
- Nodes: evaluate_answer, wait_for_decision, generate_follow_up
- Interrupts: Before follow-up generation for human approval
- Edges: conditional with interrupt handling

#### Use Cases (`application/use_cases/`)

**CombineEvaluationUseCase** (`combine_evaluation.py`):
```python
Workflow:
1. Fetch parent evaluation (main question answer)
2. Fetch all child evaluations (follow-up answers)
3. Calculate combined metrics:
   ├─ average_score = weighted avg of all scores
   ├─ gap_resolution = tracking gaps filled through follow-ups
   └─ overall_improvement = comparing first vs last answer
4. Create COMBINED evaluation entity
→ Returns: Evaluation with context_type=COMBINED
```

**ProcessAnswerAdaptiveUseCase** (`process_answer_adaptive.py`):
```python
Workflow:
1. Retrieve interview and question
2. Evaluate answer using LLM (context-aware)
3. Detect knowledge gaps
4. Create Answer entity with evaluation
5. Create Evaluation entity (PARENT_QUESTION or FOLLOW_UP)
6. Store answer and evaluation in repositories
7. Update interview state
→ Returns: Answer entity + has_more flag
```

**FollowUpDecisionUseCase** (`follow_up_decision.py`):
```python
Workflow:
1. Count existing follow-ups for parent question
2. Check break conditions:
   ├─ follow_up_count >= 3 → Exit
   ├─ similarity_score >= 0.8 → Exit
   └─ no gaps detected → Exit
3. Accumulate gaps from previous follow-ups
4. Return decision dict with needs_followup flag
→ Returns: decision dict (needs_followup, reason, count, cumulative_gaps)
```

**GenerateSummaryUseCase** (`generate_summary.py` - 376 lines):
```python
Workflow:
1. Fetch all answers for interview
2. Calculate aggregate metrics:
   ├─ overall_score = 70% theoretical + 30% speaking
   ├─ theoretical_score = avg(similarity_scores)
   ├─ speaking_score = avg(voice_metrics.overall_quality)
   └─ defaults: speaking=85 if no voice answers
3. Analyze gap progression:
   ├─ Count answers with follow-ups
   ├─ Identify gaps_filled (confirmed→False after follow-up)
   ├─ Identify gaps_remaining (still confirmed=True)
   └─ Build progression dict
4. Generate LLM recommendations:
   ├─ Pass evaluations, scores, gaps to LLM
   └─ Returns: strengths, weaknesses, study_topics, technique_tips
5. Build final summary dict (9 fields)
→ Returns: dict with all metrics + LLM recommendations
```

**PlanInterviewUseCase** (`plan_interview.py` - 381 lines):
```python
Workflow:
1. Load CV analysis
2. Calculate n (2-5) based on skill diversity
3. Create Interview entity (status=IDLE)
4. FOR each question:
   ├─ Build search query (skill + difficulty + experience)
   ├─ Find 3 exemplar questions (vector search with filters)
   ├─ Generate question with exemplars (LLM)
   ├─ Generate ideal answer + rationale
   ├─ Store question in DB
   └─ Store question embedding in vector DB (non-blocking)
5. Transition interview to QUESTIONING state
→ Returns: Interview entity
```

### 3. Adapters Layer (External Integrations)

**Location**: `src/adapters/`
**Responsibility**: Implement domain ports with concrete technologies

#### LLM Adapters (`adapters/llm/` - **NEW: LangChain**)

**LangChainAdapter** (`langchain_adapter.py` - **NEW** 400+ lines):
- Implements `LLMPort` interface using LangChain LCEL chains
- Structured outputs via Pydantic models
- Features:
  - 12 LCEL chains (one per LLMPort method)
  - JSON output parsing with schema validation
  - LangSmith tracing with PII filtering
  - Cost tracking integration
  - Configurable callbacks
  - Async operations
  - Context-aware question generation
  - Multi-dimensional answer evaluation

**LangChain Models** (`langchain_models.py` - **NEW**):
- Pydantic models for structured LLM outputs
- Models: CVSummaryOutput, SkillExtractionOutput, EvaluationOutput, FollowUpOutput, GapDetectionOutput, IdealAnswerOutput, RationaleOutput, FeedbackReportOutput, RecommendationsOutput
- Type-safe LLM responses with schema validation

**Prompts** (`prompts/__init__.py` - **NEW**):
- Centralized prompt registry
- ChatPromptTemplate definitions for all LLM operations
- Prompt versioning and management

**OpenAIAdapter** (`openai_adapter.py` - 400+ lines):
- Implements `LLMPort` interface using direct OpenAI API
- Uses OpenAI GPT-4 for all LLM operations
- Enhanced JSON extraction from markdown responses
- Features:
  - Structured JSON output for evaluations
  - Configurable model and temperature
  - Async operations
  - Context-aware question generation
  - Multi-dimensional answer evaluation
  - JSON extraction with `extract_json_from_markdown()`

**AzureOpenAIAdapter** (`azure_openai_adapter.py`):
- Azure-hosted OpenAI GPT-4 implementation
- Same features as OpenAIAdapter
- Region-specific deployment configuration

#### Vector Database Adapters (`adapters/vector_db/`)

**PineconeAdapter** (`pinecone_adapter.py`):
- Implements `VectorSearchPort` interface
- Serverless Pinecone with 1536 dimensions (OpenAI embeddings)
- Features: Auto-creates index, cosine similarity search, metadata filtering

**ChromaAdapter** (`chroma_adapter.py`):
- Local vector database implementation
- In-memory or persistent storage
- Good for development and testing

#### Persistence Adapters (`adapters/persistence/`)

**Interview Repository** (`interview_repository.py` - UPDATED):
- **NEW Junction Table Methods**:
  - `get_interview_questions(interview_id)` - Get all questions with sequence order
  - `add_question(interview_id, question_id, sequence_order)` - Add question to interview
  - `get_current_question(interview_id)` - Get current unanswered question
  - `mark_question_asked(interview_question_id, asked_at)` - Mark question as asked
  - `count_interview_questions(interview_id)` - Count total questions
  - `skip_question(interview_question_id, reason)` - Mark question as skipped
- Replaces array-based question management

**CVAnalysis Repository** (`cv_analysis_repository.py` - UPDATED):
- **NEW Skill Management Methods**:
  - `add_skill(cv_skill)` - Add skill to CV analysis
  - `remove_skill(skill_id)` - Remove skill from CV
  - `get_skills_by_proficiency(cv_analysis_id, level)` - Filter by proficiency
  - `get_primary_skills(cv_analysis_id)` - Get primary skills only
- Uses eager loading (selectinload) for skills relationship

**Evaluation Repository** (`evaluation_repository.py`):
- Stores context-aware evaluations
- Supports parent-child relationships
- Queries: `get_by_parent_question()`, `get_by_type()`, `get_combined()`

**Database Models** (`models.py` - UPDATED):
- SQLAlchemy 2.0 async models with **new tables**:
  - **CVSkillModel** (NEW) - Normalized skills table
  - **InterviewQuestionModel** (NEW) - Junction table
  - **PromptTemplateModel** (UPDATED) - 11 decomposed columns
- **ENUMs**: `question_type_enum`, `difficulty_enum`, `proficiency_level_enum`
- Tables: CandidateModel, InterviewModel (updated), QuestionModel (updated), AnswerModel (updated), CVAnalysisModel (updated), FollowUpQuestionModel, EvaluationModel
- Features: UUID PKs, timestamps, foreign keys, indexes, **junction constraints**, JSONB columns (reduced usage)

**Mappers** (`mappers.py` - UPDATED):
- Bidirectional conversion: Domain models ↔ Database models
- **NEW**: CVSkillMapper, InterviewQuestionMapper
- **UPDATED**: CVAnalysisMapper (eager loads skills), InterviewMapper (no arrays)
- Classes: CandidateMapper, InterviewMapper, QuestionMapper, AnswerMapper, CVAnalysisMapper, CVSkillMapper (NEW), InterviewQuestionMapper (NEW), FollowUpQuestionMapper, EvaluationMapper, PromptTemplateMapper (NEW)

#### Speech Adapters (`adapters/speech/`)

**AzureSTTAdapter** (`azure_stt_adapter.py`):
- Azure Speech-to-Text implementation
- Supports streaming recognition
- Language detection

**AzureTTSAdapter** (`azure_tts_adapter.py`):
- Azure Text-to-Speech implementation
- Multiple voice options
- SSML support for prosody control

#### CV Processing Adapters (`adapters/cv_processing/`)

**CVProcessingAdapter** (`cv_processing_adapter.py`):
- PDF and DOCX parsing
- Skill extraction using NLP
- Education and experience analysis

### 4. Infrastructure Layer (Cross-Cutting Concerns)

**Location**: `src/infrastructure/`
**Responsibility**: Application bootstrap, configuration, utilities

#### Observability (`infrastructure/observability/` - **NEW**)

**LangSmith Config** (`langsmith_config.py` - **NEW**):
- PIIFilteringTracer for privacy-preserving observability
- Redacts: emails, phones, SSNs, credit cards, names, CV text
- Preserves: UUIDs, question metadata, difficulty, skills
- LangSmith tracing integration
- Functions: `enable_tracing()`, `create_metadata_for_tracing()`, `get_pii_filtering_tracer()`

**Cost Tracking** (`cost_tracking.py` - **NEW**):
- LLM API cost tracking and monitoring
- Token usage tracking (input/output/total)
- Cost calculation based on model pricing
- Usage aggregation by: model, operation, date
- Functions: `track_llm_call()`, `get_total_cost()`, `get_usage_by_model()`, `reset_tracking()`

#### Configuration (`infrastructure/config/`)

**Settings** (`settings.py` - 200+ lines):
- Pydantic Settings for type-safe configuration
- **NEW**: LangChain/LangSmith configuration
- **NEW**: Observability settings (PII filtering, cost tracking)
- Azure Speech service configuration
- ChromaDB configuration
- Configuration groups: Application, API, LLM Provider, Vector DB, PostgreSQL, Speech Services, File Storage, Interview, Logging, **Observability (NEW)**
- Special features: `async_database_url` property, environment detection methods

#### Database (`infrastructure/database/`)

**LangGraph Checkpointer** (`langgraph_checkpointer.py` - **NEW**):
- PostgreSQL checkpointer for LangGraph workflows
- Async checkpointing with SQLAlchemy
- State persistence for workflow interrupts
- Functions: `setup()`, `get_tuple()`, `put()`, `list()`

**Session Management** (`session.py` - 129 lines):
- Async SQLAlchemy 2.0 session factory
- Features: Global engine, session factory, connection pooling, automatic rollback
- Functions: `create_engine()`, `init_db()`, `close_db()`, `get_async_session()`, `get_engine()`

#### Dependency Injection (`infrastructure/dependency_injection/`)

**Container** (`container.py` - 400+ lines):
- Central DI container for all dependencies
- **NEW**: LangChain adapter injection
- **NEW**: Workflow injection (planning, adaptive eval)
- **NEW**: Observability components injection
- Evaluation repository injection
- Speech service adapters injection
- Configuration-driven implementation selection
- Methods: `llm_port()`, `vector_search_port()`, repository methods, speech service methods, **workflow methods (NEW)**, **observability methods (NEW)**

## Entry Points

### For Users
- **README.md**: Project overview and quick start
- **docs/project-overview-pdr.md**: Product requirements and roadmap

### For Developers
- **pyproject.toml**: Dependencies, scripts, tool configuration
- **CLAUDE.md**: Development instructions and architecture overview
- **src/main.py**: Application entry point (FastAPI app)

### For Testing
- **tests/**: Test suites (200+ tests)
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
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -e ".[dev]"

# 4. Configure environment
cp .env.example .env.local
# Edit .env.local with API keys (OpenAI, Pinecone, LangSmith)

# 5. Run migrations
alembic upgrade head

# 6. Start development server
python src/main.py
```

### Testing Strategy

**Unit Tests** (`tests/unit/`):
- Test domain logic in isolation
- Mock all ports
- Fast execution (milliseconds)
- 200+ tests, 85%+ coverage

**Integration Tests** (`tests/integration/`):
- Test adapters with real services
- Use test environments for external APIs
- Verify port implementations
- Workflow integration tests

**Performance Prototypes** (`tests/prototypes/` - **NEW**):
- Token usage benchmarks
- Interrupt pattern performance
- Workflow performance baselines

## Development Principles

### Clean Architecture

**Dependency Rule**: Dependencies point inward
- Domain → No dependencies
- Application → Domain only
- Adapters → Domain + Application
- Infrastructure → All layers

**Port-Adapter Pattern**:
- All external dependencies behind abstract interfaces
- Easy to swap implementations
- Domain logic remains pure

### Domain-Driven State Management

State management moved from WebSocket orchestrator to domain layer:
- Interview aggregate root owns state transitions
- State machine validates transitions: IDLE → QUESTIONING → EVALUATING → REVIEWING → COMPLETED
- Business rules enforced at domain level
- WebSocket orchestrator delegates state management to domain

### LangChain/LangGraph Patterns **NEW**

**LCEL Chains**:
- Composable chains for LLM operations
- Structured outputs with Pydantic models
- Automatic prompt + model + parser composition

**Workflow Architecture**:
- LangGraph state machines for complex flows
- PostgreSQL checkpointing for persistence
- Interrupt patterns for human-in-loop
- Conditional routing based on state

**Observability**:
- LangSmith tracing with PII filtering
- Cost tracking for all LLM calls
- Metadata-enriched traces for debugging

### Code Standards

**Python Style**:
- PEP 8 compliance
- Type hints throughout
- Docstrings for all public APIs
- Line length: 100 characters

**Architecture**:
- Rich domain models (not anemic)
- Async-first design
- Repository pattern for data access
- Dependency injection for flexibility

## Implementation Status

### ✅ Complete (v0.4.0 Current)

**Phase 1 Foundation**:
- Domain models (8 entities including Evaluation)
- Repository ports (13 interfaces)
- PostgreSQL persistence (10 repositories)
- OpenAI + Azure OpenAI LLM adapters
- Pinecone + ChromaDB vector adapters
- Mock adapters (6 total)
- Database migrations (Alembic + async support)
- Configuration management
- Dependency injection container

**Phase 2 LangChain/LangGraph Integration** (**NEW - COMPLETE**):
- LangChain LCEL adapter with 12 chains
- Structured outputs with Pydantic models
- Prompt registry and management
- LangGraph workflows (planning, adaptive eval)
- PostgreSQL checkpointing for workflows
- Interrupt patterns for human-in-loop

**Phase 3 Observability Module** (**NEW - COMPLETE**):
- LangSmith tracing with PII filtering
- Cost tracking and monitoring
- Token usage aggregation
- Privacy-preserving observability

**Phase 4 Evaluation Enhancement**:
- Context-aware evaluation with entity separation
- Parent-child evaluation relationships
- Combined evaluation use case
- Evaluation repository and persistence

**Phase 5 State Management**:
- Domain-Driven State Management
- Interview state machine in domain layer
- State transition validation
- WebSocket orchestrator delegates to domain

**Phase 6 Schema Redesign (v0.4.0 - NEW)**:
- Normalized database schema with junction tables
- `cv_skills` table replaces JSONB array
- `interview_questions` junction table replaces arrays
- PostgreSQL ENUMs for type safety (question_type, difficulty, proficiency_level)
- Decomposed `prompt_templates` into 11 editable columns
- Removed redundant columns (metadata, deprecated fields)
- Updated 3 domain models, 2 mappers, 2 repositories
- Updated 5 use cases, 2 workflows, REST/WebSocket APIs
- Database migration 0015 with zero data loss
- 354/601 tests passing (59% - test updates in progress)

**Use Cases**:
- AnalyzeCV, PlanInterview, GetNextQuestion
- ProcessAnswerAdaptive, CompleteInterview
- GenerateSummary, FollowUpDecision
- CombineEvaluation

**API Layer**:
- REST API (health + interview endpoints)
- WebSocket handler (real-time interview sessions)
- DTOs (5 files: interview, answer, audio, websocket, detailed_feedback)

### 🔄 In Progress

- Speech service integration (Azure STT/TTS)
- CV processing refinement
- Advanced analytics

### ⏳ Planned (Future Phases)

- Claude and Llama LLM adapters
- Weaviate vector adapter alternative
- Authentication & authorization
- Rate limiting
- Comprehensive E2E test suites
- Docker deployment
- CI/CD pipeline

## File Statistics

**Total Python Files**: ~106 files
**Domain Layer**: 24 files (11 models + 13 ports) - **3 new models**
**Application Layer**: 19 files (8 use cases + 5 DTOs + 5 workflows + __init__)
**Adapters Layer**: 42 files (LLM w/ LangChain, vector DB, 6 mocks, persistence w/ new mappers, API, speech, CV)
**Infrastructure Layer**: 12 files (config, database w/ checkpointer, DI, observability)
**Tests**: 354/601 passing (59% after migration) - 29 test files
**Migrations**: 15 Alembic migrations (+5 from v0.3.0)

**Lines of Code**:
- Domain: ~1050 lines (+200 for new models)
- Application: ~1800 lines (+600 for workflows)
- Adapters: ~4200 lines (+200 for new mappers)
- Infrastructure: ~600 lines (+150 for observability)
- Total: ~7650 lines production code (+450 from v0.3.0)
- Tests: ~4200 lines

## Dependencies Overview

### Production Dependencies (30+ packages)
Core framework, **LangChain/LangGraph** (**NEW**), LLM providers, vector DB, database, speech services, document processing, utilities

**NEW Dependencies**:
- `langchain>=0.2.0` - LLM workflow orchestration
- `langchain-openai>=0.2.0` - OpenAI integration
- `langchain-anthropic>=0.2.0` - Anthropic Claude integration
- `langgraph>=0.2.0` - State machine workflows
- `langgraph-checkpoint-postgres>=0.2.0` - PostgreSQL checkpointing
- `langsmith>=0.1.0` - Observability and tracing

### Development Dependencies (9 packages)
Testing, linting, formatting, type checking, development tools

**Total Dependencies**: 40+ packages (+10 from LangChain ecosystem)

## Performance Considerations

### Async Operations
- All I/O operations are async (database, API calls)
- Non-blocking request handling
- Concurrent interview sessions supported

### Database Optimization
- Async SQLAlchemy with asyncpg driver
- Connection pooling (configurable)
- Indexed columns for frequent queries
- Efficient ORM query patterns
- **NEW**: LangGraph checkpointing for workflow state

### Scalability
- Stateless API design (state in domain + checkpointer, not WebSocket)
- Horizontal scaling ready
- Database connection pooling
- Async request handling
- **NEW**: Workflow state persistence for recovery

### Observability **NEW**
- LangSmith tracing with minimal overhead
- PII filtering prevents sensitive data leakage
- Cost tracking for budget monitoring
- Token usage analysis for optimization

## Security Measures

### Implemented ✅
- Environment variables for secrets
- .env.local gitignored
- SQL injection prevention (parameterized queries)
- Input validation via Pydantic
- **NEW**: PII filtering in traces (emails, phones, SSNs, names)
- **NEW**: CV text redaction in logs
- **NEW**: Answer truncation (200 chars max in traces)

### Planned ⏳
- JWT authentication
- Rate limiting per user
- API key rotation
- Encryption at rest
- HTTPS enforcement
- CORS configuration
- Security headers

## Deployment

### Current Setup
- Development: Local Python + PostgreSQL (Neon cloud)
- Configuration: .env.local files
- Database: Neon serverless PostgreSQL
- **NEW**: LangSmith tracing (optional, for observability)

### Planned
- Docker containerization
- Docker Compose for local development
- Kubernetes for production
- Environment-specific configurations
- CI/CD with GitHub Actions
- Monitoring and logging (via LangSmith)
- Health checks and readiness probes

## Related Documentation

- [Project Overview & PDR](./project-overview-pdr.md) - Product requirements and roadmap
- [System Architecture](./system-architecture.md) - Detailed architecture documentation
- [Code Standards](./code-standards.md) - Coding conventions and best practices
- [Project Roadmap](./project-roadmap.md) - Development timeline and milestones
- [Observability Guide](./observability-guide.md) - **NEW** - LangSmith tracing and cost tracking

## External Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [SQLAlchemy 2.0 Documentation](https://docs.sqlalchemy.org/en/20/)
- [OpenAI API Reference](https://platform.openai.com/docs/)
- [Pinecone Documentation](https://docs.pinecone.io/)
- [LangChain Documentation](https://python.langchain.com/) **NEW**
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/) **NEW**
- [LangSmith Documentation](https://docs.smith.langchain.com/) **NEW**
- [Clean Architecture Guide](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)

---

**Document Status**: Living document, updated with each milestone
**Next Review**: After major architectural changes
**Maintainers**: Elios Development Team
