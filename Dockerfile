FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip, setuptools, and wheel first (faster package resolution)
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Copy only dependency files first (for better layer caching)
# This layer will be cached unless dependency files change
COPY pyproject.toml ./
COPY requirements/ ./requirements/

# Install Python dependencies using pip cache mount (requires BuildKit)
# Cache mount significantly speeds up subsequent builds
# Fallback: if BuildKit is not available, remove --mount flag
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir \
    --prefer-binary \
    -r requirements/base.txt

# Copy application source code (this layer cached if only source changes)
COPY src/ ./src/
COPY alembic.ini ./
COPY alembic/ ./alembic/
COPY README.md ./

# Copy test bot directory (for running tests inside container)
# Copy tests directory structure needed for bot
COPY tests/__init__.py ./tests/__init__.py
COPY tests/conftest.py ./tests/conftest.py
COPY tests/bot/ ./tests/bot/

# Install the package in editable mode (only after copying src)
# This is fast since dependencies are already installed
RUN pip install --no-cache-dir -e .

# Download spaCy models (required for CV processing)
# English model is required, Vietnamese is optional (will fallback to English if unavailable)
RUN python -m spacy download en_core_web_sm
RUN python -m spacy download vi_core_news_sm || echo "Warning: Vietnamese model (vi_core_news_sm) download failed - will use English model as fallback"

# Set default environment variables (can be overridden in docker-compose)
# Application
ENV APP_NAME="Elios AI Interview Service"
ENV APP_VERSION=0.1.0
ENV ENVIRONMENT=production
ENV DEBUG=false
ENV API_HOST=0.0.0.0
ENV API_PORT=8000
ENV API_PREFIX=/api

# LLM Provider
ENV LLM_PROVIDER=openai
ENV OPENAI_MODEL=gpt-4
ENV OPENAI_TEMPERATURE=0.7
ENV OPENAI_EMBEDDING_MODEL=text-embedding-3-small
ENV AZURE_OPENAI_API_VERSION="2024-02-15-preview"
ENV AZURE_OPENAI_ENDPOINT=https://aiportalapi.stu-platform.live/jpe
ENV AZURE_OPENAI_DEPLOYMENT_NAME=GPT-4o-mini
ENV AZURE_DEPLOYMENT_NAME=GPT-4o-mini
ENV USE_AZURE_OPENAI=true
ENV ANTHROPIC_MODEL=claude-3-sonnet-20240229

# Vector Database
ENV VECTOR_DB_PROVIDER=pinecone
ENV PINECONE_ENVIRONMENT=us-east-1
ENV PINECONE_INDEX_NAME=elios-interviews

# PostgreSQL Configuration (non-sensitive defaults)
ENV POSTGRES_HOST=localhost
ENV POSTGRES_PORT=5432
ENV POSTGRES_USER=elios
ENV POSTGRES_DB=elios_interviews

# Interview Configuration
ENV MAX_QUESTIONS_PER_INTERVIEW=10
ENV MIN_PASSING_SCORE=60.0
ENV QUESTION_TIMEOUT_SECONDS=300

# Logging
ENV LOG_LEVEL=INFO
ENV LOG_FORMAT=json

# WebSocket Configuration
ENV WS_HOST=localhost
ENV WS_PORT=8000
ENV WS_BASE_URL=ws://localhost:8000

# LangChain Integration
ENV USE_LANGCHAIN=true
ENV LANGCHAIN_TEMPERATURE=0.7
ENV LANGCHAIN_MAX_TOKENS=2000
ENV LANGCHAIN_ENABLE_FALLBACK=false
ENV LANGCHAIN_FALLBACK_PROVIDER=anthropic

# Mock Adapters (for development/testing)
ENV USE_MOCK_LLM=false
ENV USE_MOCK_VECTOR_SEARCH=true
ENV USE_MOCK_CV_ANALYZER=false
ENV USE_MOCK_STT=false
ENV USE_MOCK_TTS=false
ENV USE_MOCK_ANALYTICS=true
ENV USE_MOCK_EVENT_PUBLISHER=false

# Hybrid CV Analyzer Configuration
ENV HYBRID_CONFIDENCE_THRESHOLD=0.7
ENV HYBRID_ENABLE_LLM_FALLBACK=true
ENV HYBRID_SKILL_PATTERNS_PATH=./src/adapters/cv_processing/skill_patterns.json

# Kafka Configuration
ENV KAFKA_BOOTSTRAP_SERVERS=localhost:9094
ENV KAFKA_INTERVIEW_TOPIC=interview-user-interview

# spaCy Model Configuration
ENV SPACY_MODEL_EN=en_core_web_sm
ENV SPACY_MODEL_VI=vi_core_news_sm

# Expose port
EXPOSE 8000

# Default command
CMD ["python", "-m", "src.main"]

