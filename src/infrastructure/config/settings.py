"""Application settings using Pydantic."""

import os
import re
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import field_validator, model_validator
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
    api_prefix: str = "/api/ai"

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
    pinecone_namespace: str = "__default__"

    # PostgreSQL Configuration
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "elios"
    postgres_password: str = ""
    postgres_db: str = "elios_interviews"
    database_url: str | None = None  # Full DATABASE_URL from environment
    db_pool_size: int = 12  # Increased from 5 (Phase 2 optimization: 4 workers × 2 + 3 checkpointer)
    db_max_overflow: int = 5
    db_pool_timeout: int = 30
    db_pool_recycle_seconds: int = 240
    db_pool_pre_ping: bool = True  # Verify connection health before use (Phase 2)

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

    # ================================================
    # Google Cloud Speech (NEW v0.4.1)
    # ================================================
    google_cloud_project_id: str | None = None
    google_application_credentials: str | None = None
    google_stt_model: str = "chirp_3"  # chirp_3, short, long, latest_long
    google_stt_location: str = "us"  # us, eu, asia, us-central1, europe-west4, asia-southeast1, etc. Determines regional API endpoint for regional models
    google_stt_language: str = "en-US"
    google_tts_voice_name: str = "en-US-Chirp3-HD-Charon"

    # Interview Configuration
    max_questions_per_interview: int = 10
    min_passing_score: float = 60.0
    question_timeout_seconds: int = 300  # 5 minutes per question
    token_delta_per_plan: int = -10  # Tokens deducted per plan_interview call

    # Audio Storage Configuration
    audio_storage_api_url: str | None = None
    audio_storage_api_timeout: float = 30.0

    # Kafka Configuration (Event Publishing)
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_interview_topic: str = "interview-user-interview"
    kafka_candidate_topic: str = "user-interview-candidate"
    kafka_feedback_topic: str = "ai-feedback-results"
    kafka_token_topic: str = "ai-user-usertokenupdate"
    kafka_candidate_consumer_group: str = "interview-service-candidate-events"

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

    # Authentication (Keycloak reverse proxy)
    auth_role_header_name: str = "X-Auth-Request-Groups"
    auth_user_id_header_name: str = "X-Auth-Request-User"
    auth_role_prefix: str = "role:"
    auth_allowed_roles: list[str] = ["Admin", "User"]

    # WebSocket Configuration
    ws_host: str = "localhost"
    ws_port: int = 8000
    ws_base_url: str = "ws://localhost:8000"

    # LangChain Integration (Phase 1)
    langchain_temperature: float = 0.7  # Default temperature for LangChain models
    langchain_max_tokens: int = 2000  # Max tokens per LLM call
    langchain_enable_fallback: bool = False  # Multi-provider fallback
    langchain_fallback_provider: str = "anthropic"  # claude fallback

    # LangGraph Planning Workflow (Phase 2)
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
    # Checkpointer heartbeat is enabled by default (no flag needed)
    langgraph_checkpointer_heartbeat_interval_seconds: int = 240
    langgraph_checkpointer_ensure_timeout_seconds: float = 10.0

    # Mock Adapters (for development/testing)
    # Vector search mock remains available for local development/testing
    use_mock_vector_search: bool = True

    # Phase 2: Unified LLM Prompt (Performance Optimization)

    model_config = SettingsConfigDict(
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_speech_config(self) -> "Settings":
        """Validate Google Cloud Speech configuration."""
        if not self.google_cloud_project_id:
            raise ValueError(
                "GOOGLE_CLOUD_PROJECT_ID required for speech adapters. "
                "Provide Google Cloud credentials."
            )
        return self

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
