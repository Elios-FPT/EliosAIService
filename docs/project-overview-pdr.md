# Project Overview & Product Development Requirements (PDR)

**Project Name**: Elios AI Interview Service
**Version**: 0.4.0
**Last Updated**: 2025-11-26
**Status**: Active Development (Phase 1.5 Complete, v0.4.0 Schema Redesign Complete)
**Repository**: https://github.com/elios/elios-ai-service

## Executive Summary

Elios AI Interview Service is an AI-powered mock interview platform that helps candidates prepare for technical interviews through personalized CV analysis, adaptive question generation, real-time answer evaluation, and comprehensive feedback. The platform leverages Large Language Models (OpenAI GPT-4), vector databases (Pinecone), LangChain/LangGraph workflows, and advanced NLP techniques to deliver a realistic, intelligent interview experience.

**Major Update (v0.4.0)**: Database schema redesign with normalized tables (cv_skills, interview_questions), PostgreSQL ENUMs for type safety, and decomposed prompt templates for A/B testing.

**Previous Update (v0.3.0)**: Integration of LangChain Expression Language (LCEL) and LangGraph workflows with PostgreSQL checkpointing, LangSmith observability, and cost tracking.

## Project Purpose

### Vision
Transform interview preparation by providing accessible, intelligent, and personalized mock interview experiences that adapt to each candidate's unique skills, experience, and learning needs through advanced workflow orchestration and real-time observability.

### Mission
Empower candidates to confidently prepare for real interviews by:
- Analyzing their background and generating personalized interview questions
- Providing real-time feedback on their responses
- Identifying strengths and areas for improvement
- Offering actionable recommendations for skill development
- **NEW**: Tracking performance with cost-aware, privacy-preserving observability

### Value Proposition
- **Personalized Experience**: CV analysis drives customized question selection based on candidate's actual skills
- **Intelligent Evaluation**: AI-powered semantic analysis provides nuanced feedback beyond keyword matching
- **Comprehensive Feedback**: Detailed performance reports with specific improvement suggestions
- **Flexible Delivery**: Support for both text and voice-based interviews
- **Scalable Platform**: Clean Architecture + LangGraph workflows enable easy integration of new AI models and services
- **Production Observability**: LangSmith tracing with PII filtering and cost tracking per interview session
- **Crash Recovery**: PostgreSQL-backed checkpointing allows workflow resumption after failures

## Target Users

### Primary Users

#### 1. Job Seekers & Candidates
**Needs**: Practice interviews, receive feedback, build confidence, identify weak areas
**Pain Points**:
- Limited access to mock interview opportunities
- Lack of personalized feedback
- Generic interview prep doesn't match their background
- Expensive interview coaching services

**Solution**: AI interviewer that adapts to their CV, provides instant feedback, and offers unlimited practice sessions

#### 2. Students & Recent Graduates
**Needs**: Prepare for first job interviews, understand interview expectations, practice answering technical questions
**Pain Points**:
- No professional interview experience
- Unsure what employers look for
- Limited access to mentors for interview prep
- High stakes with limited opportunities

**Solution**: Safe practice environment with constructive feedback and learning resources

#### 3. Career Changers
**Needs**: Bridge skill gaps, demonstrate transferable skills, prepare for industry-specific questions
**Pain Points**:
- Unclear how to present career transition
- Difficulty articulating transferable skills
- Industry-specific terminology and practices
- Competing with candidates with direct experience

**Solution**: CV analysis highlights transferable skills and generates relevant questions for target role

### Secondary Users

#### 4. Recruiters & HR Professionals
**Needs**: Pre-screen candidates, assess technical competency, standardize evaluation
**Pain Points**:
- Time-consuming manual screening
- Inconsistent evaluation criteria
- Difficulty assessing soft skills remotely
- Need for objective candidate comparisons

**Solution**: Standardized interview format with consistent evaluation metrics

#### 5. Educational Institutions
**Needs**: Provide career services, prepare students for job market, measure program effectiveness
**Pain Points**:
- Limited career counseling resources
- Difficult to scale 1-on-1 interview prep
- Tracking student preparation progress
- Demonstrating program outcomes

**Solution**: Scalable platform for student interview preparation with progress tracking

## Key Features & Capabilities

### 1. Intelligent CV Analysis

**Core Functionality**:
- Extract text from multiple formats (PDF, DOC, DOCX)
- Identify technical and soft skills using NLP
- Determine experience level and education
- Generate semantic embeddings for matching
- Suggest appropriate difficulty levels
- Recommend interview topics

**Implementation Status**: ✅ Domain models complete, 🔄 Adapters pending

**Technical Approach**:
- spaCy for NLP processing
- OpenAI GPT-4 for skill extraction and summarization
- OpenAI Embeddings (1536 dimensions) for semantic matching
- Pinecone for vector storage and similarity search

### 2. LangGraph Workflow Orchestration (NEW v0.3.0)

**Core Functionality**:
- **Planning Workflow**: Parallelized question generation with PostgreSQL checkpointing
- **Adaptive Evaluation Workflow**: Context-aware answer evaluation with follow-up decision logic
- **Performance Analysis Workflow**: Comprehensive feedback generation with gap tracking
- Crash recovery via database-backed state persistence
- Real-time workflow progress monitoring via LangSmith

**Implementation Status**: ✅ Complete (3 workflows implemented)

**Technical Approach**:
- LangGraph for state machine workflows
- LangChain LCEL for composable chains
- PostgreSQL checkpointing (AsyncPostgresSaver)
- RunnableParallel for batch LLM operations
- Pydantic structured outputs for type safety

**Workflows**:
1. **PlanningWorkflow** (497 lines):
   - Nodes: load_cv → calculate_count → prepare_specs → generate_batch → store_questions → update_interview
   - Parallel generation: Questions, ideal answers, rationales (up to 5 concurrent)
   - Checkpointed state: 14 fields including retry_count, errors
   - Recovery: Resume from any node after crash

2. **AdaptiveEvalSimpleWorkflow** (879 lines):
   - Nodes: load_context → evaluate_answer → store_answer → check_followup → generate_followup OR finalize
   - Break conditions: max 3 iterations, similarity ≥ 0.8, no gaps
   - Gap accumulation across iterations
   - Seamless integration with existing use cases

3. **Performance Analysis** (future Phase 3B):
   - Aggregate interview results with LangGraph
   - Generate recommendations via LLM chains
   - Track cost per workflow execution

### 3. LangSmith Observability & Cost Tracking (NEW v0.3.0)

**Core Functionality**:
- **Tracing**: All LLM calls traced to LangSmith with PII filtering
- **Cost Tracking**: Token usage and cost per interview session
- **PII Filtering**: Automatic redaction of emails, phone numbers, SSNs, credit cards, names
- **Metadata Tagging**: interview_id, candidate_id, question_id, difficulty, skill
- **Daily Summaries**: Cost breakdown by model, interview count, average cost per session

**Implementation Status**: ✅ Complete (langsmith_config.py, cost_tracking.py)

**Technical Approach**:
- PIIFilteringTracer (LangChainTracer subclass)
- Regex-based PII detection (5 patterns)
- Text truncation (answers: 200 chars, CVs: 100 chars)
- LangSmith client for cost queries
- Per-model pricing configuration

**Privacy Features**:
- Email → `[EMAIL_REDACTED]`
- Phone → `[PHONE_REDACTED]`
- SSN → `[SSN_REDACTED]`
- Credit Card → `[CC_REDACTED]`
- "My name is John Doe" → "My name is [NAME_REDACTED]"
- Answer text truncated to 200 chars
- CV text truncated to 100 chars

**Cost Tracking**:
```python
# Per interview cost
{
    "total_tokens": 12500,
    "input_tokens": 8000,
    "output_tokens": 4500,
    "total_cost_usd": 0.45,
    "model_breakdown": {
        "gpt-4": {"tokens": 12500, "cost": 0.45}
    },
    "trace_count": 15
}

# Daily summary
{
    "total_cost_usd": 125.50,
    "interviews_count": 100,
    "avg_cost_per_interview": 1.26,
    "model_breakdown": {...}
}
```

### 4. LangChain LCEL Adapter (NEW v0.3.0)

**Core Functionality**:
- All 12 LLMPort methods implemented as LCEL chains
- Structured outputs via Pydantic models (9 schemas)
- Batch operations via RunnableParallel
- Metadata injection for tracing
- Callback support for PII filtering

**Implementation Status**: ✅ Complete (langchain_adapter.py, 453 lines)

**LCEL Patterns**:
```python
# Simple chain: prompt | model | json_parser
chains["evaluate_answer"] = prompt_template | self.model | json_parser

# Batch chain with parallel execution
parallel_chains = {
    f"q_{i}": self._chains["generate_questions_batch"].ainvoke(input)
    for i, input in enumerate(question_specs)
}
results = await RunnableParallel(**parallel_chains).ainvoke({})

# With metadata
config = RunnableConfig(
    metadata={"interview_id": str(interview_id), "skill": skill},
    callbacks=self.callbacks  # PII filtering tracer
)
result = await chain.ainvoke(input, config=config)
```

**Structured Output Models**:
- CVSummaryOutput, SkillExtractionOutput
- EvaluationOutput, GapDetectionOutput
- FollowUpOutput, FeedbackReportOutput
- IdealAnswerOutput, RationaleOutput, RecommendationsOutput

### 5. Adaptive Question Generation & Follow-Up System

**Core Functionality**:
- Exemplar-based question generation using vector search
- Dynamic question creation with similar question inspiration
- Difficulty progression throughout interview
- Coverage of multiple skills and topics
- **Context-aware follow-up questions** based on detected knowledge gaps
- **Adaptive evaluation** with parent-child relationship tracking
- **Break conditions** for follow-up loops (max 3, similarity ≥0.8, no gaps)

**Implementation Status**: ✅ Complete (Phase 1 + Phase 4 Adaptive Answers)

**Technical Approach**:
- PostgreSQL question bank with metadata
- Vector similarity search retrieves 3 exemplar questions
- Exemplars filtered by question_type, difficulty (similarity >0.5)
- LLM generates NEW questions inspired by exemplars
- Questions stored with embeddings for future exemplar searches
- Graceful fallback: Generate without exemplars if search fails
- **NEW**: Evaluation entity with parent-child relationships (PARENT_QUESTION, FOLLOW_UP, COMBINED)
- **NEW**: FollowUpDecisionUseCase implements break conditions and gap accumulation
- **NEW**: CombineEvaluationUseCase merges parent + follow-up evaluations

### 6. Real-Time Answer Evaluation

**Core Functionality**:
- Semantic similarity scoring
- Completeness and relevance assessment
- Confidence and sentiment analysis
- Strength and weakness identification
- Improvement suggestions
- Multi-dimensional scoring (0-100 scale)

**Implementation Status**: ✅ Domain models complete, ✅ LLM adapter implemented

**Technical Approach**:
- OpenAI GPT-4 for answer evaluation
- Structured JSON output for consistent scoring
- Vector embeddings for semantic similarity
- Multi-factor evaluation criteria

### 7. Comprehensive Feedback Generation

**Core Functionality**:
- Overall performance summary
- Skill-specific breakdown
- Question-by-question analysis
- Actionable improvement recommendations
- Performance trends over multiple interviews
- Strengths and growth areas

**Implementation Status**: ✅ Domain models complete, 🔄 Analytics adapters pending

**Technical Approach**:
- Aggregated scoring across interview
- LLM-generated narrative feedback
- Historical performance tracking
- Visualization-ready metrics

### 8. Voice Interview Support (Planned)

**Core Functionality**:
- Speech-to-text for candidate answers
- Text-to-speech for question delivery
- Multi-language support (EN, VI)
- Natural conversation flow
- Audio quality handling

**Implementation Status**: 🔄 Ports defined, ⏳ Adapters pending

**Technical Approach**:
- Azure Speech-to-Text API
- Microsoft Edge TTS
- Real-time audio streaming
- Transcript storage

### 9. Multi-Channel Interview Delivery

**Core Functionality**:
- REST API for CRUD operations
- WebSocket for real-time chat
- Async operations for responsiveness
- Session management
- Progress tracking

**Implementation Status**: 🔄 Health check only, ⏳ Full API pending

**Technical Approach**:
- FastAPI framework
- WebSocket protocol
- Async/await patterns
- JWT authentication (planned)

## Technical Requirements

### Functional Requirements

**FR1: CV Upload and Analysis**
- Support PDF, DOC, and DOCX file formats
- Extract structured information (skills, experience, education)
- Generate semantic embeddings
- Store analysis results in database
- Link analysis to candidate profile

**FR2: Interview Session Management**
- Create interview sessions linked to CV analysis
- Select appropriate questions based on CV
- Track interview progress and state
- Support interview pause/resume
- Store complete interview history

**FR3: Question Presentation**
- Retrieve questions from database
- Apply semantic matching for relevance
- Present questions with metadata
- Support text and voice delivery
- Track question order and timing

**FR4: Answer Collection and Evaluation**
- Accept text and voice answers
- Perform real-time evaluation
- Calculate multi-dimensional scores
- Store answers with evaluations
- Link answers to questions

**FR5: Feedback Generation**
- Aggregate interview results
- Generate comprehensive reports
- Provide actionable recommendations
- Calculate skill-specific scores
- Compare against benchmarks

**FR6: Data Persistence**
- Store candidates, interviews, questions, answers
- Maintain CV analysis results
- Track evaluation history
- Support efficient querying
- Ensure data integrity

**FR7: External Service Integration**
- Connect to LLM providers (OpenAI, Claude, Llama)
- Integrate vector databases (Pinecone, Weaviate, ChromaDB)
- Utilize speech services (Azure STT, Edge TTS)
- Support service provider switching

**FR8: Workflow Orchestration (NEW v0.3.0)**
- Execute LangGraph workflows with checkpointing
- Resume workflows after crashes
- Track workflow state transitions
- Log workflow execution traces
- Support parallel LLM operations

**FR9: Observability & Cost Management (NEW v0.3.0)**
- Trace all LLM calls to LangSmith
- Filter PII from traces automatically
- Calculate cost per interview session
- Generate daily cost summaries
- Tag traces with contextual metadata

**Ops Note – Neon Checkpointer (NEW v0.4.1)**
LangGraph workflows now emit structured `checkpointer_*` logs that report endpoint type, retry counts, and seconds since the previous retry. Operators **must** deploy with direct Neon endpoints (no `-pooler`) and keep `DB_POOL_RECYCLE_SECONDS ≤ 240` to avoid the 5-minute idle shutdown on the free tier. See `docs/deployment-guide.md` for the full checklist.

**Ops Note – Workflow Resilience (NEW v0.4.1)**
Interview WebSocket flows use a workflow execution guard that auto-retries psycopg `OperationalError`s, surfaces `system_error` messages with `action=retry`, and stores deterministic thread IDs (`interview_<uuid>`) so checkpoints can resume after reconnects. Docs in `docs/deployment-guide.md` now list the `system_error` contract for frontend teams.

**FR10: Normalized Skill Management (NEW v0.4.0)**
- Store CV skills in dedicated table with foreign keys
- Track proficiency levels (BEGINNER, INTERMEDIATE, ADVANCED, EXPERT)
- Record years_of_experience per skill
- Mark primary skills for interview focus
- Support skill-level filtering and querying

**FR11: Junction Table Query Patterns (NEW v0.4.0)**
- Query interview questions with sequence ordering
- Add/remove questions from interviews dynamically
- Track question order in interview flow
- Support question reordering without array manipulation
- Enable efficient pagination of interview questions

**FR12: ENUM Type Safety (NEW v0.4.0)**
- Enforce question types at database level (TECHNICAL, BEHAVIORAL, SITUATIONAL)
- Validate difficulty levels (EASY, MEDIUM, HARD)
- Ensure proficiency level consistency
- Prevent invalid enum values in application layer
- Support enum value migrations

### Non-Functional Requirements

**NFR1: Performance**
- CV analysis completion < 30 seconds
- Question generation < 3 seconds
- Answer evaluation < 5 seconds
- Support 100+ concurrent interviews
- Database query response < 100ms

**NFR2: Scalability**
- Horizontal scaling for API servers
- Async processing for I/O operations
- Efficient vector search (< 50ms)
- Connection pooling for databases
- Stateless interview sessions

**NFR3: Reliability**
- 99.5% uptime target
- Graceful degradation if services fail
- Data backup and recovery
- Transaction integrity
- Error logging and monitoring
- **NEW**: Workflow crash recovery via checkpointing

**NFR4: Security**
- Secure API key management
- PII data encryption at rest
- HTTPS for all communications
- Input validation and sanitization
- SQL injection prevention
- Rate limiting
- **NEW**: PII filtering in observability traces

**NFR5: Maintainability**
- Clean Architecture for loose coupling
- Comprehensive documentation
- Type hints throughout codebase
- Unit test coverage > 80%
- Code follows PEP 8 standards

**NFR6: Usability**
- Intuitive API design
- Clear error messages
- Comprehensive API documentation
- Interactive Swagger UI
- Reasonable response times

**NFR7: Flexibility**
- Swappable LLM providers
- Swappable vector databases
- Configurable via environment variables
- Support for multiple languages
- Extensible architecture

**NFR8: Cost Efficiency (NEW v0.3.0)**
- Track LLM token usage per interview
- Calculate cost per session
- Monitor daily/monthly spending
- Optimize prompt design for token efficiency
- Support model selection based on cost/quality tradeoff

**NFR9: Privacy Compliance (NEW v0.3.0)**
- Automatic PII redaction in traces
- Configurable PII filtering rules
- Audit trail for data access
- GDPR compliance for observability data
- Minimal data retention in external services

## Architecture Overview

### Pattern: Clean Architecture (Hexagonal/Ports & Adapters)

```
┌─────────────────────────────────────────────────────┐
│           Infrastructure Layer                       │
│  (Config, Database, Logging, DI Container,          │
│   Observability: LangSmith, Cost Tracking)          │
└─────────────────────────────────────────────────────┘
                        ↑
┌─────────────────────────────────────────────────────┐
│             Adapters Layer                           │
│  (LLM [LangChain LCEL], VectorDB, Speech, CV,      │
│   API, DB Repositories)                             │
└─────────────────────────────────────────────────────┘
                        ↑
┌─────────────────────────────────────────────────────┐
│           Application Layer                          │
│  (Use Cases, DTOs, Workflows [LangGraph])           │
└─────────────────────────────────────────────────────┘
                        ↑
┌─────────────────────────────────────────────────────┐
│             Domain Layer                             │
│   (Models, Services, Ports - Pure Business Logic)  │
└─────────────────────────────────────────────────────┘
```

**Key Benefits**:
- ✅ **Technology Independence**: Domain logic unaffected by framework/tool changes
- ✅ **Testability**: Domain can be tested in complete isolation
- ✅ **Flexibility**: Easy to swap external services (OpenAI → Claude → Llama)
- ✅ **Maintainability**: Clear separation of concerns and responsibilities
- ✅ **Team Scalability**: Teams can work on different layers independently
- ✅ **NEW**: Workflow orchestration decoupled from business logic via LangGraph
- ✅ **NEW**: Observability injected via callbacks, not hardcoded

## Technology Stack

### Core Technologies
- **Language**: Python 3.11+
- **Framework**: FastAPI (REST API & WebSocket)
- **Async Runtime**: asyncio for non-blocking I/O
- **Validation**: Pydantic 2.x for data models and settings
- **Type Checking**: mypy for static type analysis

### NEW: LangChain/LangGraph Stack (v0.3.0)
- **langchain-core**: LCEL chains, runnables, callbacks
- **langchain-openai**: ChatOpenAI integration
- **langgraph**: StateGraph workflows
- **langgraph-checkpoint-postgres**: PostgreSQL checkpointing
- **langsmith**: Tracing and observability
- **langchain-community**: Additional integrations

### Domain Layer (Minimal Dependencies)
- Pure Python standard library
- Pydantic for data validation
- Python type hints

### External Services (via Adapters)

**LLM Providers**:
- OpenAI GPT-4 (primary) ✅
- Azure OpenAI (enterprise alternative) ✅
- **NEW**: LangChain LCEL adapter for unified interface ✅
- Anthropic Claude (planned) ⏳
- Meta Llama 3 (planned) ⏳

**Vector Databases**:
- Pinecone (primary, serverless) ✅
- ChromaDB (local dev, in-memory) ✅
- Weaviate (alternative) ⏳

**Speech Services**:
- Azure Speech-to-Text ✅
- Azure Text-to-Speech ✅
- Microsoft Edge TTS (fallback) ⏳
- Google Speech (alternative) ⏳

**Database**:
- PostgreSQL 14+ with async support ✅
- SQLAlchemy 2.0+ (async) ✅
- Alembic for migrations ✅
- asyncpg driver ✅
- **NEW**: PostgreSQL for workflow checkpointing ✅

**NLP & Document Processing**:
- spaCy for text processing ⏳
- LangChain for workflow orchestration ✅
- PyPDF2 for PDF parsing ⏳
- python-docx for DOCX parsing ⏳

**Observability (NEW v0.3.0)**:
- LangSmith for tracing ✅
- Custom cost tracking module ✅
- PII filtering tracer ✅

### Development Tools
- **Testing**: pytest, pytest-asyncio, pytest-cov
- **Linting**: ruff (fast Python linter)
- **Formatting**: black (code formatter)
- **Type Checking**: mypy
- **Database Migrations**: Alembic

### Infrastructure
- **Configuration**: Pydantic Settings with .env files
- **Dependency Injection**: Custom container
- **Logging**: Structured logging (planned)
- **Deployment**: Docker containers (planned)

## Success Metrics

### User Engagement Metrics
- Number of active candidates
- Interviews completed per week
- Average interview duration
- User retention rate (30-day)
- Repeat interview sessions

### Performance Metrics
- CV analysis accuracy (skill extraction)
- Question relevance score (user feedback)
- Answer evaluation accuracy (vs human raters)
- Platform response times
- API availability (uptime %)

### Quality Metrics
- User satisfaction score (CSAT)
- Net Promoter Score (NPS)
- Feedback usefulness rating
- Candidate improvement over time
- Interview preparation confidence increase

### Technical Metrics
- Test coverage > 80%
- API response time < 200ms (p95)
- Database query time < 100ms (p95)
- LLM API success rate > 99%
- System uptime > 99.5%
- **NEW**: Workflow crash recovery rate > 95%
- **NEW**: Average cost per interview < $2.00
- **NEW**: PII filtering accuracy > 99%

### Business Metrics
- User acquisition cost
- Conversion rate (free → paid)
- Revenue per user
- Churn rate
- Customer lifetime value
- **NEW**: Cost per interview vs industry benchmark
- **NEW**: Observability coverage (% of LLM calls traced)

## Project Roadmap

### Phase 1: Foundation (v0.1.0 - v0.2.1) - ✅ COMPLETE
**Status**: ✅ Complete (100%)
**Timeline**: 2 months (2025-10-01 → 2025-11-14)

**Completed**:
- ✅ Domain models (8 entities: Candidate, Interview, Question, Answer, CVAnalysis, Evaluation, ErrorCodes, FollowUpQuestion)
- ✅ Repository ports (13 interfaces including EvaluationRepositoryPort, FollowUpQuestionRepositoryPort)
- ✅ PostgreSQL persistence layer (7 repositories)
- ✅ OpenAI & Azure OpenAI LLM adapters
- ✅ Pinecone & ChromaDB vector database adapters
- ✅ Azure Speech services (STT, TTS adapters)
- ✅ Mock adapters (6 total: LLM, STT, TTS, VectorSearch, CVAnalyzer, Analytics)
- ✅ Database migrations with Alembic
- ✅ Use cases (8 total: AnalyzeCV, PlanInterview, GetNextQuestion, ProcessAnswerAdaptive, FollowUpDecision, CombineEvaluation, GenerateSummary, CompleteInterview)
- ✅ DTOs (interview, answer, websocket, audio)
- ✅ Configuration management
- ✅ Dependency injection container
- ✅ REST API (5 interview endpoints)
- ✅ WebSocket handler with session orchestrator (state machine pattern)
- ✅ Domain-driven state management (Interview state machine)
- ✅ Context-aware evaluation with follow-up questions
- ✅ Comprehensive interview summary generation

### Phase 1.5: LangChain/LangGraph Integration (v0.3.0) - ✅ COMPLETE
**Status**: ✅ Complete (100%)
**Timeline**: 1 week (2025-11-13 → 2025-11-20)

**Completed**:
- ✅ LangChain LCEL adapter (453 lines, 12 LLMPort methods)
- ✅ Pydantic structured output models (9 schemas)
- ✅ LangGraph PlanningWorkflow (497 lines, PostgreSQL checkpointing)
- ✅ LangGraph AdaptiveEvalSimpleWorkflow (879 lines, follow-up decision logic)
- ✅ LangSmith observability with PII filtering (langsmith_config.py, 308 lines)
- ✅ Cost tracking module (cost_tracking.py, 371 lines)
- ✅ Workflow base class (base_workflow.py, 88 lines)
- ✅ Dependencies updated: +6 LangChain packages
- ✅ Tests: 100% coverage on observability, 90%+ on workflows

**Architectural Improvements**:
- ✅ Workflow orchestration layer added to application layer
- ✅ LCEL chains replace imperative LLM calls
- ✅ Observability injected via callbacks, not hardcoded
- ✅ PostgreSQL checkpointing for crash recovery
- ✅ Metadata tagging for trace filtering

**In Progress**:
- 🔄 CV processing adapters (spaCy, document parsing)

**Deferred to Phase 2**:
- ⏳ Authentication & authorization
- ⏳ Rate limiting
- ⏳ Comprehensive integration testing
- ⏳ Enhanced API documentation (Swagger)
- ⏳ Docker deployment scripts

### Phase 2: Core Features (v0.3.0 - v0.5.0)
**Timeline**: 3-4 months

**Features**:
- Voice interview support (Azure STT, Edge TTS)
- Advanced question generation
- Interview history and analytics
- Performance benchmarks
- Multiple difficulty levels
- Frontend integration

### Phase 3: Intelligence Enhancement (v0.6.0 - v0.8.0)
**Timeline**: 3-4 months

**Features**:
- Multi-LLM support (Claude, Llama)
- Behavioral question analysis
- Personality insights
- Interview strategy recommendations
- Skill gap analysis
- Learning resource recommendations

### Phase 4: Scale & Polish (v0.9.0 - v1.0.0)
**Timeline**: 2-3 months

**Features**:
- Multi-language support (Vietnamese, English)
- Team/organization features
- Advanced analytics dashboard
- Mobile app support
- Performance optimization
- Production deployment

## Risk Management

### Technical Risks

**Risk 1: LLM API Availability**
- **Impact**: High (service unavailable)
- **Likelihood**: Low
- **Mitigation**: Multi-provider support, fallback mechanisms, caching, retry logic

**Risk 2: Vector Database Performance**
- **Impact**: Medium (slow question matching)
- **Likelihood**: Medium
- **Mitigation**: Caching, query optimization, indexing strategies, alternative providers

**Risk 3: Data Privacy & Security**
- **Impact**: Critical (legal liability)
- **Likelihood**: Low
- **Mitigation**: Encryption, access controls, GDPR compliance, security audits, **NEW**: PII filtering in observability

**Risk 4: Evaluation Accuracy**
- **Impact**: High (poor user experience)
- **Likelihood**: Medium
- **Mitigation**: Multiple evaluation methods, human validation, continuous improvement, user feedback loops

**Risk 5: Cost Overruns (NEW v0.3.0)**
- **Impact**: Medium (budget exceeded)
- **Likelihood**: Medium
- **Mitigation**: Cost tracking per interview, model selection optimization, prompt engineering, caching strategies

**Risk 6: Workflow Crashes (NEW v0.3.0)**
- **Impact**: Medium (incomplete interviews)
- **Likelihood**: Low
- **Mitigation**: PostgreSQL checkpointing, automatic recovery, graceful degradation

### Business Risks

**Risk 7: User Adoption**
- **Impact**: High (product viability)
- **Likelihood**: Medium
- **Mitigation**: User research, beta testing, iterative improvements, marketing strategy

**Risk 8: Competition**
- **Impact**: Medium (market share)
- **Likelihood**: Medium
- **Mitigation**: Unique value proposition, quality focus, rapid innovation

## Constraints & Assumptions

### Technical Constraints
- Python 3.11+ required
- PostgreSQL 14+ required
- API keys for OpenAI and Pinecone
- Internet connectivity for external services
- Async-compatible libraries only

### Operational Constraints
- API rate limits (OpenAI, Pinecone)
- Cloud service costs
- Data storage limits
- Processing time for CV analysis
- **NEW**: LangSmith trace retention limits

### Design Constraints
- Clean Architecture pattern (no exceptions)
- Domain layer has zero external dependencies
- All external services behind ports
- Async-first design
- RESTful API conventions

### Assumptions
- Users have CV in standard formats
- Interview answers are text-based initially
- Users speak English or Vietnamese
- Internet connectivity is stable
- External APIs are generally available
- **NEW**: PostgreSQL available for checkpointing
- **NEW**: LangSmith service uptime > 99%

## Compliance & Standards

### Data Protection
- GDPR compliance for EU users
- Data retention policies
- Right to deletion
- Data export capability
- Consent management
- **NEW**: PII filtering in observability traces
- **NEW**: Minimal data retention in LangSmith (7 days)

### Code Standards
- PEP 8 Python style guide
- Type hints throughout
- Docstrings for all public APIs
- Clean Architecture principles
- SOLID principles
- DRY (Don't Repeat Yourself)

### Testing Standards
- Unit test coverage > 80%
- Integration tests for external services
- E2E tests for critical flows
- Performance benchmarks
- Security testing

### Documentation Standards
- Comprehensive README
- API documentation (OpenAPI/Swagger)
- Architecture documentation
- Code examples
- Setup guides

## Glossary

- **CV Analysis**: Structured extraction of skills, experience, and education from candidate resumes
- **Vector Embedding**: Numerical representation of text in high-dimensional space for semantic similarity
- **Semantic Search**: Finding relevant content based on meaning rather than keywords
- **Port**: Abstract interface defining contract for external dependencies (Hexagonal Architecture)
- **Adapter**: Concrete implementation of a port for specific technology
- **Domain Model**: Business entity with behavior (not just data)
- **Use Case**: Application-specific business flow orchestrating domain objects
- **Aggregate Root**: Entity that controls access to related entities (Interview)
- **Repository**: Pattern for abstracting data access
- **LLM**: Large Language Model (GPT-4, Claude, etc.)
- **STT**: Speech-to-Text conversion
- **TTS**: Text-to-Speech synthesis
- **PII**: Personally Identifiable Information
- **LCEL**: LangChain Expression Language (composable chains)
- **LangGraph**: State machine workflow framework
- **Checkpointing**: Saving workflow state for crash recovery
- **Observability**: Monitoring and tracing system behavior
- **PII Filtering**: Automatic redaction of sensitive data

## References

### Internal Documentation
- [System Architecture](./system-architecture.md)
- [Codebase Summary](./codebase-summary.md)
- [Code Standards](./code-standards.md)
- [API Documentation](./system-architecture.md#api-architecture)
- [Database Setup Guide](../DATABASE_SETUP.md)

### External Resources
- [Clean Architecture](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)
- [Hexagonal Architecture](https://alistair.cockburn.us/hexagonal-architecture/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [OpenAI API Reference](https://platform.openai.com/docs/)
- [Pinecone Documentation](https://docs.pinecone.io/)
- [LangChain Documentation](https://python.langchain.com/)
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [LangSmith Documentation](https://docs.smith.langchain.com/)

## Appendices

### Appendix A: Database Schema Summary (v0.4.0)

**Core Tables** (7 main tables):
- `candidates` - User profiles
- `cv_analyses` - CV analysis results
- `cv_skills` - Normalized skill storage (NEW v0.4.0)
- `interviews` - Interview sessions
- `interview_questions` - Junction table (NEW v0.4.0)
- `questions` - Question bank
- `answers` - Candidate responses

**Workflow & Observability**:
- `checkpoints` - LangGraph workflow state (v0.3.0)
- `prompt_templates` - Decomposed prompt versioning (v0.4.0)
- `prompt_executions` - LLM execution tracking

**Schema Features**:
- Foreign key relationships for referential integrity
- B-tree indexes on frequently queried columns
- PostgreSQL ENUMs (QuestionType, Difficulty, ProficiencyLevel) - v0.4.0
- JSONB columns for flexible metadata (answers, evaluations)
- Composite indexes for junction table queries (interview_id, sequence_order)

**Migration**: 15 Alembic migrations total (0001-0015)

### Appendix B: API Endpoint Summary
- `/health` - Health check
- `/api/ai/cv/upload` - Upload and analyze CV
- `/api/ai/interviews` - Interview CRUD
- `/api/ai/questions` - Question management
- `/api/ws/interviews/{id}` - WebSocket chat

### Appendix C: Development Setup Summary
1. Install Python 3.11+
2. Create virtual environment
3. Install dependencies: `pip install -e ".[dev]"`
4. Configure .env file with API keys
5. Run database migrations: `alembic upgrade head`
6. Start server: `python src/main.py`

### Appendix D: LangChain/LangGraph Integration (NEW v0.3.0)
- **Workflows**: 3 implemented (planning, adaptive eval, performance)
- **Checkpointing**: PostgreSQL-backed state persistence
- **Observability**: LangSmith tracing with PII filtering
- **Cost Tracking**: Per-interview and daily summaries
- **Dependencies**: +6 LangChain packages (langchain-core, langgraph, langsmith, etc.)
- **Code Size**: +1,700 lines (workflows + observability)
- **Test Coverage**: 100% on observability, 90%+ on workflows

## Unresolved Questions

1. **Pricing Model**: Freemium vs subscription vs usage-based?
2. **Interview Length**: Optimal number of questions per session?
3. **Evaluation Calibration**: How to ensure consistent scoring across different LLMs?
4. **Multi-Language Priority**: Which languages to support first after English?
5. **Mobile Strategy**: Native apps vs responsive web?
6. **Team Features**: B2B offering for companies and schools?
7. **Certification**: Provide certificates of completion or proficiency?
8. **NEW**: Cost Optimization: Target cost per interview and model selection strategy?
9. **NEW**: Trace Retention: How long to retain LangSmith traces?
10. **NEW**: Workflow Recovery SLA: Acceptable downtime during crash recovery?

---

**Document Status**: Living document, updated with each milestone
**Next Review**: After Phase 2 completion
**Maintainers**: Elios Development Team
