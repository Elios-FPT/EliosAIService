# Test Bot Configuration Guide

The interview test bot now supports flexible configuration through YAML files and environment variables, making it easy to customize behavior without modifying code.

## Quick Start

The bot uses `bot_config.yaml` by default:

```bash
# Run all mock scenarios
python -m tests.bot.run_tests

# Run single scenario
python -m tests.bot.run_tests --scenario mock_001_basic_flow

# Override API base URL
python -m tests.bot.run_tests --base-url http://localhost:8010
```

## Configuration Structure

### CV Analysis Configuration

Controls how CV data is analyzed and processed:

```yaml
cv_analysis:
  default_proficiency: "intermediate"  # Default skill proficiency level
  default_category: "technical"        # Default skill category
```

### Experience Mapping

Maps job titles to years of experience:

```yaml
experience_mapping:
  senior_years: 5       # Years for "senior" titles
  mid_years: 3          # Years for "mid" or "intermediate" titles
  junior_years: 1       # Years for "junior" titles
  default_years: 2      # Default if title doesn't match
```

### Difficulty Mapping

Maps seniority levels to interview difficulty:

```yaml
difficulty_mapping:
  senior_difficulty: "HARD"     # Difficulty for senior candidates
  mid_difficulty: "MEDIUM"      # Difficulty for mid-level
  default_difficulty: "EASY"    # Default difficulty
```

### API Configuration

Controls API endpoint and timeouts:

```yaml
api:
  base_url: "http://localhost:8000"  # API base URL
  timeout_sec: 30.0                   # HTTP client timeout
```

### Path Configuration

Configures file and directory paths:

```yaml
paths:
  output_dir: "reports/"                                      # Report output directory
  scenarios_dir: "scenarios"                                  # Scenarios directory
  fixtures_dir: "fixtures"                                    # Fixtures directory
  baseline_path: "fixtures/baselines/baseline_metrics.json"  # Baseline metrics file
```

### Interview Configuration

Controls interview test parameters:

```yaml
interview:
  default_expected_questions: 3      # Default number of questions
  default_answer_quality: "good"     # Default answer quality (poor, good, excellent)
  qa_loop_buffer: 10                 # Buffer for follow-up questions
```

### Timeout Configuration

Fine-tune timeout values for different operations:

```yaml
timeouts:
  question_timeout_sec: 5.0      # Timeout for waiting for next question
  follow_up_timeout_sec: 5.0     # Timeout for follow-up questions
  completion_timeout_sec: 5.0    # Timeout for interview completion
  evaluation_timeout_sec: 10.0   # Timeout for answer evaluation
  interview_timeout_sec: 30.0    # Timeout for entire interview session
```

### Data Seed Configuration (NEW)

Mock scenarios can seed the database using curated SQL:

```yaml
config:
  data_seed:
    sql_file: fixtures/sql/java-backend-beginner.sql  # Relative to tests/bot/
    interview_id: b323c6a1-4749-4922-876f-72b6c426b2a6
    question_ids:
      - 453523fb-8ac5-43d9-8aa8-856803fa950d
      - f405aaad-3e97-401f-bd5c-d68c62bb1445
```

Guidelines:
- Fixtures must live under `tests/bot/fixtures/sql`.
- Scripts should delete conflicting IDs before inserting replacements.
- SQL execution is allowed only when `ENVIRONMENT=test`; ensure this env var is set before running the bot.
- `question_ids` help downstream validation but remain optional.

### Answer Strategy Configuration (NEW)

The bot can follow deterministic answer plans:

```yaml
config:
  answer_strategy:
    type: ideal        # ideal | degraded | scripted
    degrade_profile:
      keep_ratio: 0.4
      min_sentences: 1
    scripted_answers:
      e2cb66cb-2a4f-4c62-9955-9aa1bb476988: EMPTY
      7f9bf40e-3970-4c91-8c4f-8f9a2b5f9c02: LONG_2500
```

- `ideal`: reuse question fixture `ideal_answer` verbatim.
- `degraded`: shuffle/truncate the ideal answer; tuned via `degrade_profile`.
- `scripted`: map question IDs to explicit responses. Macros `EMPTY` and `LONG_<len>` are supported. When using question fixtures, you may reference fixture IDs; the runner maps them to runtime IDs automatically.
- If no strategy is defined, the legacy generator stays in place.

## Configuration Precedence

The configuration system uses the following precedence (highest to lowest):

1. **Command-line arguments** (e.g., `--base-url`)
2. **Default config file** (`bot_config.yaml`)
3. **Hardcoded defaults** (defined in `config.py`)

## Usage Examples

### Example 1: Testing Against Different API URL

Override the API base URL via command line:

```bash
python -m tests.bot.run_tests --base-url http://localhost:8010
```

Or modify `bot_config.yaml`:

```yaml
api:
  base_url: "http://localhost:8010"
```

### Example 2: Using Environment Variables

Set environment variables with `BOT_` prefix:

```bash
# Set API URL via environment
export BOT_API__BASE_URL="http://localhost:9000"
export BOT_TIMEOUTS__QUESTION_TIMEOUT_SEC=10.0

# Run tests (environment variables take precedence)
python -m tests.bot.run_tests
```

Environment variable format:
- Prefix: `BOT_`
- Section separator: `__` (double underscore)
- Example: `BOT_API__BASE_URL` → `api.base_url`

## Configuration in Code

### Using Configuration in Custom Scripts

```python
from tests.bot.config import get_config, BotConfig

# Load default config
config = get_config()

# Load custom config
config = BotConfig.load("path/to/custom_config.yaml")

# Access config values
print(config.api.base_url)
print(config.timeouts.question_timeout_sec)

# Create runner with config
from tests.bot.test_runner import TestRunner

runner = TestRunner(config=config)
```

### Creating Config from Dictionary

```python
from tests.bot.config import BotConfig

config_data = {
    "api": {
        "base_url": "http://localhost:8000",
        "timeout_sec": 30.0
    },
    "interview": {
        "default_expected_questions": 5
    }
}

config = BotConfig(**config_data)
```

## Troubleshooting

### Config File Not Found

If you get a `FileNotFoundError`, check:
1. Path is correct and relative to where you run the command
2. File has `.yaml` extension
3. File has valid YAML syntax

### Invalid Configuration Values

If you get a Pydantic validation error:
1. Check that numeric values are numbers (not strings)
2. Check that required fields are present
3. Validate YAML syntax with a YAML linter

### Configuration Not Applied

If changes don't seem to apply:
1. Check that command-line args don't override your config
2. Ensure config file is valid YAML
3. Check logs for config loading messages
4. Verify `bot_config.yaml` is in the correct location

## Migration from Hardcoded Values

If you previously relied on hardcoded values, here's what changed:

### Before (Hardcoded)
```python
# db_helper.py
proficiency="intermediate"  # Hardcoded
category="technical"        # Hardcoded
```

### After (Configurable)
```python
# db_helper.py
proficiency=self.config.cv_analysis.default_proficiency  # From config
category=self.config.cv_analysis.default_category         # From config
```

All hardcoded values are now in `bot_config.yaml` with sensible defaults.

## Best Practices

1. **Modify `bot_config.yaml` directly** - This is the primary configuration file
2. **Use version control** - Track changes to `bot_config.yaml`
3. **Document changes** - Add comments explaining why values were changed
4. **Test config changes** - Run tests to validate changes
5. **Use `--base-url` for quick overrides** - Override API URL without modifying config file

## Contributing

When adding new configurable values:

1. Add field to appropriate config class in `config.py`
2. Add default value to `bot_config.yaml`
3. Update this README with examples
4. Add example usage to `bot_config.custom.example.yaml`
