"""Configuration management for test bot.

Supports loading from YAML files and environment variables with fallback to defaults.
"""

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class CVAnalysisConfig(BaseModel):
    """Configuration for CV analysis defaults."""

    default_proficiency: str = Field(
        default="intermediate",
        description="Default proficiency level for skills",
    )
    default_category: str = Field(
        default="technical",
        description="Default category for skills",
    )


class ExperienceMappingConfig(BaseModel):
    """Configuration for experience years mapping."""

    senior_years: int = Field(default=5, description="Years for senior titles")
    mid_years: int = Field(default=3, description="Years for mid/intermediate titles")
    junior_years: int = Field(default=1, description="Years for junior titles")
    default_years: int = Field(default=2, description="Default years if title unrecognized")


class DifficultyMappingConfig(BaseModel):
    """Configuration for difficulty mapping."""

    senior_difficulty: str = Field(default="HARD", description="Difficulty for senior")
    mid_difficulty: str = Field(default="MEDIUM", description="Difficulty for mid-level")
    default_difficulty: str = Field(default="EASY", description="Default difficulty")


class APIConfig(BaseModel):
    """Configuration for API endpoints."""

    base_url: str = Field(
        default="http://localhost:8000",
        description="API base URL",
    )
    timeout_sec: float = Field(
        default=30.0,
        description="HTTP client timeout in seconds",
    )


class PathConfig(BaseModel):
    """Configuration for file paths."""

    output_dir: str = Field(
        default="tests/bot/reports",
        description="Output directory for test reports",
    )
    scenarios_dir: str = Field(
        default="scenarios",
        description="Directory containing scenario YAML files (relative to tests/bot/)",
    )
    fixtures_dir: str = Field(
        default="fixtures",
        description="Directory containing test fixtures (relative to tests/bot/)",
    )
    baseline_path: str = Field(
        default="fixtures/baselines/baseline_metrics.json",
        description="Path to baseline metrics file (relative to tests/bot/)",
    )


class InterviewConfig(BaseModel):
    """Configuration for interview test parameters."""

    default_expected_questions: int = Field(
        default=3,
        description="Default number of questions per interview",
    )
    default_answer_quality: str = Field(
        default="good",
        description="Default answer quality (poor, good, excellent)",
    )
    qa_loop_buffer: int = Field(
        default=10,
        description="Buffer for follow-up questions in QA loop",
    )


class TimeoutConfig(BaseModel):
    """Configuration for various timeout values."""

    question_timeout_sec: float = Field(
        default=5.0,
        description="Timeout for waiting for questions",
    )
    follow_up_timeout_sec: float = Field(
        default=5.0,
        description="Timeout for waiting for follow-up questions",
    )
    completion_timeout_sec: float = Field(
        default=5.0,
        description="Timeout for waiting for completion message",
    )
    evaluation_timeout_sec: float = Field(
        default=10.0,
        description="Timeout for waiting for answer evaluation",
    )
    interview_timeout_sec: float = Field(
        default=30.0,
        description="Timeout for entire interview session",
    )


class BotConfig(BaseModel):
    """Main test bot configuration."""

    cv_analysis: CVAnalysisConfig = Field(default_factory=CVAnalysisConfig)
    experience_mapping: ExperienceMappingConfig = Field(
        default_factory=ExperienceMappingConfig
    )
    difficulty_mapping: DifficultyMappingConfig = Field(
        default_factory=DifficultyMappingConfig
    )
    api: APIConfig = Field(default_factory=APIConfig)
    paths: PathConfig = Field(default_factory=PathConfig)
    interview: InterviewConfig = Field(default_factory=InterviewConfig)
    timeouts: TimeoutConfig = Field(default_factory=TimeoutConfig)

    @classmethod
    def from_yaml(cls, yaml_path: Path | str) -> "BotConfig":
        """Load configuration from YAML file.

        Args:
            yaml_path: Path to YAML config file

        Returns:
            BotConfig instance
        """
        yaml_path = Path(yaml_path)

        if not yaml_path.exists():
            raise FileNotFoundError(f"Config file not found: {yaml_path}")

        with open(yaml_path) as f:
            data = yaml.safe_load(f)

        return cls(**data)

    @classmethod
    def from_env(cls, env_prefix: str = "BOT_") -> "BotConfig":
        """Load configuration from environment variables.

        Environment variables should be in format:
        BOT_API__BASE_URL=http://localhost:8000
        BOT_TIMEOUTS__QUESTION_TIMEOUT_SEC=10.0

        Args:
            env_prefix: Prefix for environment variables

        Returns:
            BotConfig instance
        """
        config_data: dict[str, Any] = {}

        # Parse environment variables
        for key, value in os.environ.items():
            if not key.startswith(env_prefix):
                continue

            # Remove prefix and split by double underscore
            config_key = key[len(env_prefix) :].lower()
            parts = config_key.split("__")

            if len(parts) == 2:
                section, field = parts
                if section not in config_data:
                    config_data[section] = {}
                # Convert to appropriate type
                config_data[section][field] = _parse_env_value(value)

        return cls(**config_data)

    @classmethod
    def load(cls, config_path: Path | str | None = None) -> "BotConfig":
        """Load configuration with precedence: custom file > default file > defaults.

        Args:
            config_path: Optional path to custom config file

        Returns:
            BotConfig instance
        """
        # Try custom config path first
        if config_path:
            custom_path = Path(config_path)
            if custom_path.exists():
                return cls.from_yaml(custom_path)

        # Try default config file
        default_path = Path(__file__).parent / "bot_config.yaml"
        if default_path.exists():
            return cls.from_yaml(default_path)

        # Fall back to defaults
        return cls()


def _parse_env_value(value: str) -> Any:
    """Parse environment variable value to appropriate type.

    Args:
        value: String value from environment

    Returns:
        Parsed value (int, float, bool, or str)
    """
    # Try int
    try:
        return int(value)
    except ValueError:
        pass

    # Try float
    try:
        return float(value)
    except ValueError:
        pass

    # Try bool
    if value.lower() in ("true", "1", "yes"):
        return True
    if value.lower() in ("false", "0", "no"):
        return False

    # Return as string
    return value


# Global config instance (lazy-loaded)
_config: BotConfig | None = None


def get_config(config_path: Path | str | None = None) -> BotConfig:
    """Get global config instance (singleton).

    Args:
        config_path: Optional path to custom config file

    Returns:
        BotConfig instance
    """
    global _config

    if _config is None:
        _config = BotConfig.load(config_path)

    return _config


def reload_config(config_path: Path | str | None = None) -> BotConfig:
    """Reload configuration (useful for tests).

    Args:
        config_path: Optional path to custom config file

    Returns:
        New BotConfig instance
    """
    global _config
    _config = BotConfig.load(config_path)
    return _config
