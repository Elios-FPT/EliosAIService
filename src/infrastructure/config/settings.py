"""Application settings using Pydantic."""

import os
import re
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# Load environment-specific configuration before Settings class initialization
# This allows ENVIRONMENT variable to determine which .env file to load
def _load_environment_config() -> None:
    """Load environment-specific .env file based on ENVIRONMENT variable.

    Priority:
    1. ENVIRONMENT=test → .env.test (for test isolation)
    2. ENVIRONMENT=production → .env (for production)
    3. Default → .env.local (for local development)
    """
    load_dotenv()
    environment = os.getenv("ENVIRONMENT", "development").lower()

    # Determine which .env file to load
    if environment == "test":
        env_file = Path(__file__).parent.parent.parent.parent / ".env.test"
        if env_file.exists():
            load_dotenv(env_file, override=True)
            print(f"[OK] Loaded test configuration from: {env_file}")
        else:
            print(f"[WARN] ENVIRONMENT=test but .env.test not found at {env_file}")
    elif environment == "production":
        env_file = Path(__file__).parent.parent.parent.parent / ".env"
        if env_file.exists():
            load_dotenv(env_file)
            print(f"[OK] Loaded production configuration from: {env_file}")
    else:
        # Development: try .env.local first, fallback to .env
        env_local = Path(__file__).parent.parent.parent.parent / ".env.local"
        env_default = Path(__file__).parent.parent.parent.parent / ".env"

        if env_local.exists():
            load_dotenv(env_local)
            print(f"[OK] Loaded development configuration from: {env_local}")
        elif env_default.exists():
            load_dotenv(env_default)
            print(f"[OK] Loaded development configuration from: {env_default}")


# Load configuration before Settings class is initialized
_load_environment_config()


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    This uses Pydantic for validation and type safety.
    """

    # Application
    app_name: str = "Elios AI Interview Service"
    app_version: str = "0.1.0"
    environment: str = "development"  # development, staging, production
    debug: bool = True

    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_prefix: str = "/api"

    # LLM Provider Selection
    llm_provider: str = "openai"  # openai, claude, llama

    # OpenAI Configuration
    openai_api_key: str | None = None
    openai_model: str = "gpt-4"
    openai_temperature: float = 0.7
    openai_embedding_model: str = "text-embedding-3-small"
    openai_embedding_api_key: str | None = None

    # Azure OpenAI Configuration (alternative to standard OpenAI)
    azure_openai_api_key: str | None = None
    azure_openai_endpoint: str | None = None  # e.g., "https://your-resource.openai.azure.com/"
    azure_openai_api_version: str = "2024-02-15-preview"
    azure_openai_deployment_name: str | None = None  # Deployment name, not model name
    use_azure_openai: bool = False  # Flag to enable Azure OpenAI

    # Anthropic Claude Configuration (alternative)
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-3-sonnet-20240229"

    # Vector Database Selection
    vector_db_provider: str = "pinecone"  # pinecone, weaviate, chroma

    # Pinecone Configuration
    pinecone_api_key: str | None = None
    pinecone_environment: str = "us-east-1"
    pinecone_index_name: str = "elios-interviews"

    # PostgreSQL Configuration
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "elios"
    postgres_password: str = ""
    postgres_db: str = "elios_interviews"
    database_url: str | None = None  # Full DATABASE_URL from environment

    @property
    def async_database_url(self) -> str:
        """Generate async PostgreSQL connection URL.

        Converts postgresql:// to postgresql+asyncpg:// for async support.
        Strips out sslmode and channel_binding parameters (not supported by asyncpg).
        If DATABASE_URL is set in environment, use that; otherwise construct from parts.

        Note: For Neon and other cloud PostgreSQL providers, asyncpg handles SSL
        automatically - no explicit SSL parameters needed.
        """
        # First check if DATABASE_URL is provided directly
        db_url = self.database_url or os.getenv("DATABASE_URL")

        if db_url:
            # Convert postgresql:// to postgresql+asyncpg://
            db_url = re.sub(r"^postgresql:", "postgresql+asyncpg:", db_url)

            # Strip out SSL parameters that asyncpg doesn't support in URL format
            # asyncpg handles SSL automatically for cloud providers like Neon
            db_url = re.sub(r"\?sslmode=[^&]*", "", db_url)  # Remove sslmode param
            db_url = re.sub(r"&sslmode=[^&]*", "", db_url)  # Remove if not first param
            db_url = re.sub(r"\?channel_binding=[^&]*", "", db_url)  # Remove channel_binding
            db_url = re.sub(r"&channel_binding=[^&]*", "", db_url)  # Remove if not first param
            db_url = re.sub(r"\?&", "?", db_url)  # Clean up malformed query string
            db_url = re.sub(r"\?$", "", db_url)  # Remove trailing ?

            return db_url

        # Otherwise construct from individual parts
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # Speech Services (Azure Speech SDK)
    azure_speech_key: str | None = None
    azure_speech_region: str = "eastus"
    azure_speech_language: str = "en-US"
    azure_speech_voice: str = "en-US-AriaNeural"
    azure_speech_cache_size: int = 128  # LRU cache size for TTS

    # File Storage
    upload_dir: str = "./uploads"
    cv_dir: str = "./uploads/cvs"
    audio_dir: str = "./uploads/audio"

    # Interview Configuration
    max_questions_per_interview: int = 10
    min_passing_score: float = 60.0
    question_timeout_seconds: int = 300  # 5 minutes per question

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"  # json or text

    # CORS
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | list[str]) -> list[str]:
        """Parse CORS origins from environment variable.

        Handles both comma-separated string and list formats.
        Strips whitespace from each origin.

        Args:
            v: Either a comma-separated string or a list of strings

        Returns:
            List of origin strings with whitespace stripped
        """
        if isinstance(v, str):
            # Split by comma and strip whitespace
            origins = [origin.strip() for origin in v.split(",") if origin.strip()]
            return origins
        elif isinstance(v, list):
            # Already a list, just strip whitespace from each item
            return [
                origin.strip() if isinstance(origin, str) else str(origin).strip() for origin in v
            ]
        return v

    # WebSocket Configuration
    ws_host: str = "localhost"
    ws_port: int = 8000
    ws_base_url: str = "ws://localhost:8000"

    # LangChain Integration (Phase 1)
    use_langchain: bool = False  # Feature flag to enable LangChain adapter
    langchain_temperature: float = 0.7  # Default temperature for LangChain models
    langchain_max_tokens: int = 2000  # Max tokens per LLM call
    langchain_enable_fallback: bool = False  # Multi-provider fallback
    langchain_fallback_provider: str = "anthropic"  # claude fallback

    # LangSmith Observability (Phase 4)
    enable_langsmith: bool = False  # Enable LangSmith tracing
    langchain_tracing_v2: bool = False  # LangChain v2 tracing protocol
    langsmith_api_key: str | None = None  # LangSmith API key
    langchain_project: str = "elios-interviews-dev"  # LangSmith project name
    langchain_endpoint: str = "https://api.smith.langchain.com"  # LangSmith API endpoint
    langsmith_filter_pii: bool = True  # Enable PII filtering in traces
    langsmith_sample_rate: float = 1.0  # Trace sampling rate (0.0-1.0, 1.0 = 100%)
    langsmith_max_trace_size_kb: int = 1024  # Max trace size in KB (prevent large traces)

    # LangGraph Planning Workflow (Phase 2)
    # DEPRECATED: This flag will be removed in v0.5.0 - LangGraph is now the default implementation
    use_langgraph_planning: bool = True  # Feature flag for LangGraph planning workflow (deprecated)
    langgraph_checkpointer_type: str = "postgresql"  # Checkpoint storage backend
    langgraph_checkpointer_pool_size: int = 5  # Connection pool size for AsyncPostgresSaver
    # Note: Currently reserved for future use. AsyncPostgresSaver.from_conn_string() does not
    # support pool configuration via API. The checkpointer creates its own internal pool (~5-10 connections).
    # Total connections: SQLAlchemy (10-30) + AsyncPostgresSaver (~5-10) = ~35-40 connections.
    langgraph_checkpointer_init_on_startup: bool = (
        True  # Initialize checkpointer at startup (prevents first-request timeout)
    )
    langgraph_checkpointer_setup_timeout: float = (
        20.0  # Timeout in seconds for checkpointer setup (default: 120s)
    )

    # LangGraph Adaptive Evaluation Workflow (Phase 3A)
    use_langgraph_adaptive_simple: bool = (
        False  # Feature flag for adaptive evaluation workflow (no interrupts)
    )

    # LangGraph Adaptive Evaluation with Interrupts (Phase 3B)
    use_langgraph_adaptive_interrupt: bool = (
        False  # Feature flag for interrupt-based adaptive workflow (WebSocket loop)
    )


    # Mock Adapters (for development/testing)
    # Individual flags for each adapter - set to False to use real implementations
    use_mock_llm: bool = True
    use_mock_vector_search: bool = True
    use_mock_cv_analyzer: bool = True
    use_mock_stt: bool = True
    use_mock_tts: bool = True
    use_mock_analytics: bool = True

    # Hybrid CV Analyzer Configuration
    use_hybrid_cv_analyzer: bool = False  # Feature flag (default: legacy)
    hybrid_confidence_threshold: float = 0.7  # LLM fallback trigger
    hybrid_enable_llm_fallback: bool = True  # Allow LLM when confidence low
    hybrid_skill_patterns_path: str = "./src/adapters/cv_processing/skill_patterns.json"

    # spaCy Model Configuration
    spacy_model_en: str = "en_core_web_sm"  # English NER model
    spacy_model_vi: str = "vi_core_news_sm"  # Vietnamese NER model
    spacy_disable_components: list[str] = ["parser", "lemmatizer"]  # Optimize speed

    model_config = SettingsConfigDict(
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    def print_loaded_env_file(self) -> None:
        """Print active environment (env file already loaded by _load_environment_config)."""
        print(f"Active environment: {self.environment}")

    def is_production(self) -> bool:
        """Check if running in production."""
        return self.environment == "production"

    def is_development(self) -> bool:
        """Check if running in development."""
        return self.environment == "development"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance.

    Returns:
        Settings instance
    """

    settings = Settings()
    settings.print_loaded_env_file()

    return settings
