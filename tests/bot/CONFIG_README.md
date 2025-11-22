# Test Bot Configuration Guide

The interview test bot now supports flexible configuration through YAML files and environment variables, making it easy to customize behavior without modifying code.

## Quick Start

### Using Default Configuration

The bot uses `bot_config.yaml` by default:

```bash
python -m tests.bot.run_tests --scenarios all
```

### Using Custom Configuration

Create a custom config file and pass it via `--config` flag:

```bash
# Create custom config
cp tests/bot/bot_config.custom.example.yaml tests/bot/my_config.yaml

# Edit my_config.yaml with your values
# ...

# Run tests with custom config
python -m tests.bot.run_tests --scenarios all --config tests/bot/my_config.yaml
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

## Configuration Precedence

The configuration system uses the following precedence (highest to lowest):

1. **Command-line arguments** (e.g., `--base-url`, `--output`)
2. **Custom config file** (via `--config` flag)
3. **Default config file** (`bot_config.yaml`)
4. **Hardcoded defaults** (defined in `config.py`)

## Usage Examples

### Example 1: Testing Against Staging Environment

Create `staging_config.yaml`:

```yaml
api:
  base_url: "https://staging.example.com"
  timeout_sec: 60.0

paths:
  output_dir: "reports/staging/"
```

Run tests:

```bash
python -m tests.bot.run_tests --scenarios all --config staging_config.yaml
```

### Example 2: Fast CI/CD Pipeline Tests

Create `ci_config.yaml`:

```yaml
timeouts:
  question_timeout_sec: 2.0
  follow_up_timeout_sec: 2.0
  completion_timeout_sec: 2.0
  evaluation_timeout_sec: 5.0
  interview_timeout_sec: 15.0

interview:
  default_expected_questions: 2  # Fewer questions for faster tests
  qa_loop_buffer: 5
```

Run tests:

```bash
python -m tests.bot.run_tests --scenarios mock --config ci_config.yaml
```

### Example 3: Override Single Value

You only need to specify values you want to override:

```yaml
# production_config.yaml
api:
  base_url: "https://api.production.com"
```

All other values will use defaults from `bot_config.yaml`.

### Example 4: Using Environment Variables

Set environment variables with `BOT_` prefix:

```bash
# Set API URL via environment
export BOT_API__BASE_URL="http://localhost:9000"
export BOT_TIMEOUTS__QUESTION_TIMEOUT_SEC=10.0

# Run tests (environment variables take precedence)
python -m tests.bot.run_tests --scenarios all
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
1. Verify you're using `--config` flag correctly
2. Check that command-line args don't override your config
3. Ensure config file is valid YAML
4. Check logs for config loading messages

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

1. **Don't modify `bot_config.yaml` directly** - Create custom config files instead
2. **Use version control** for custom configs used in CI/CD
3. **Document custom configs** - Add comments explaining why values were changed
4. **Test config changes** - Run with `--scenarios mock` first to validate
5. **Keep configs minimal** - Only override values you need to change
6. **Use meaningful names** - Name config files by environment (e.g., `staging_config.yaml`)

## Contributing

When adding new configurable values:

1. Add field to appropriate config class in `config.py`
2. Add default value to `bot_config.yaml`
3. Update this README with examples
4. Add example usage to `bot_config.custom.example.yaml`
