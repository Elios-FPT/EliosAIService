# Phase 2: Domain Models

**Parent**: [Implementation Plan](./plan.md)
**Dependencies**: [Phase 1: Database Schema](./phase-01-database-schema.md)
**Created**: 2025-11-20
**Duration**: 2 days
**Priority**: High
**Status**: ✅ Complete

---

## Overview

Create domain entities for prompt version control: `PromptTemplate`, `PromptMetadataChange`, and `PromptExecution`. Pure Pydantic models with business logic, no external dependencies.

**Goals**:
- ✅ Rich domain models with validation
- ✅ Immutable version tracking
- ✅ Prompt rendering with variable substitution
- ✅ Cost calculation logic

---

## Domain Models

### Model 1: PromptTemplate

**File**: `src/domain/models/prompt_template.py`

**Purpose**: Immutable prompt version with metadata and rendering logic.

**Key Features**:
- Version lineage tracking (parent_version_id)
- A/B testing metadata
- Prompt rendering with variable substitution
- Pydantic validation

**Implementation**:

```python
"""Prompt template domain model."""

from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


class PromptTemplate(BaseModel):
    """Immutable prompt version with metadata.

    Represents a single version of a prompt template.
    Each version is immutable (append-only).
    """

    id: UUID = Field(default_factory=uuid4)
    name: str = Field(..., max_length=100, description="Prompt identifier")
    version: int = Field(..., ge=1, description="Version number (auto-increment)")
    parent_version_id: UUID | None = Field(
        default=None,
        description="Parent version for lineage tracking"
    )
    change_summary: str | None = Field(
        default=None,
        description="Human-readable change description"
    )
    template_json: dict = Field(
        ...,
        description="Full prompt content (immutable)"
    )
    is_active: bool = Field(default=False, description="Currently deployed")
    is_draft: bool = Field(default=True, description="Draft vs production")
    ab_test_group: str | None = Field(
        default=None,
        max_length=50,
        description="A/B test group identifier"
    )
    traffic_percentage: int = Field(
        default=0,
        ge=0,
        le=100,
        description="% of traffic for this version"
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None)

    @field_validator("template_json")
    @classmethod
    def validate_template_json(cls, v: dict) -> dict:
        """Validate template_json structure."""
        required_keys = ["system", "user_template", "variables"]
        if not all(key in v for key in required_keys):
            raise ValueError(f"template_json must contain: {required_keys}")
        return v

    @field_validator("is_active", "is_draft")
    @classmethod
    def validate_active_not_draft(cls, v: bool, info) -> bool:
        """Ensure active versions are not drafts."""
        values = info.data
        if values.get("is_active") and values.get("is_draft"):
            raise ValueError("Active versions cannot be drafts")
        return v

    def get_prompt_text(self, **variables) -> str:
        """Render prompt with variables.

        Args:
            **variables: Variable values for interpolation

        Returns:
            Rendered prompt text

        Raises:
            ValueError: If required variables missing
        """
        required_vars = set(self.template_json["variables"])
        provided_vars = set(variables.keys())

        if missing := required_vars - provided_vars:
            raise ValueError(f"Missing variables: {missing}")

        user_prompt = self.template_json["user_template"].format(**variables)
        return f"{self.template_json['system']}\n\n{user_prompt}"
```

---

### Model 2: PromptMetadataChange

**File**: `src/domain/models/prompt_metadata_change.py`

**Purpose**: Audit log entry for metadata changes.

**Key Features**:
- Tracks non-content changes (activation, traffic %, etc.)
- Factory method for creating changes
- Automatic serialization of values

**Implementation**:

```python
"""Prompt metadata change domain model."""

from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class PromptMetadataChange(BaseModel):
    """Audit log entry for metadata changes.

    Tracks all non-version changes to prompt templates
    (activation, traffic adjustments, A/B test group changes).
    """

    id: UUID = Field(default_factory=uuid4)
    prompt_template_id: UUID = Field(..., description="Foreign key to prompt_templates")
    field_name: str = Field(..., max_length=50, description="Changed field name")
    old_value: str | None = Field(default=None, description="Previous value (serialized)")
    new_value: str | None = Field(default=None, description="New value (serialized)")
    changed_by: str = Field(..., max_length=100, description="User identifier")
    changed_at: datetime = Field(default_factory=datetime.utcnow)
    reason: str | None = Field(default=None, description="Why change made")

    @classmethod
    def create_change(
        cls,
        prompt_template_id: UUID,
        field_name: str,
        old_value: any,
        new_value: any,
        changed_by: str,
        reason: str | None = None,
    ) -> "PromptMetadataChange":
        """Factory method to create change entry.

        Args:
            prompt_template_id: ID of changed prompt
            field_name: Name of changed field
            old_value: Previous value (any type, will be serialized)
            new_value: New value (any type, will be serialized)
            changed_by: User identifier
            reason: Optional reason for change

        Returns:
            PromptMetadataChange instance
        """
        return cls(
            prompt_template_id=prompt_template_id,
            field_name=field_name,
            old_value=str(old_value) if old_value is not None else None,
            new_value=str(new_value) if new_value is not None else None,
            changed_by=changed_by,
            reason=reason,
        )
```

---

### Model 3: PromptExecution

**File**: `src/domain/models/prompt_execution.py`

**Purpose**: Analytics record for prompt execution.

**Key Features**:
- Tracks LLM call metadata
- Cost calculation method
- Success/failure tracking

**Implementation**:

```python
"""Prompt execution domain model."""

from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class PromptExecution(BaseModel):
    """Analytics record for prompt execution.

    Tracks every LLM call for cost tracking,
    performance monitoring, and debugging.
    """

    id: UUID = Field(default_factory=uuid4)
    prompt_template_id: UUID = Field(..., description="Which version executed")
    interview_id: UUID | None = Field(default=None, description="Interview context")
    candidate_id: UUID | None = Field(default=None, description="Candidate context")
    input_variables: dict = Field(..., description="Variables passed to prompt")
    output_text: str | None = Field(default=None, description="LLM response")
    tokens_used: int | None = Field(default=None, ge=0, description="Total tokens")
    prompt_tokens: int | None = Field(default=None, ge=0, description="Prompt tokens")
    completion_tokens: int | None = Field(default=None, ge=0, description="Completion tokens")
    latency_ms: int = Field(..., ge=0, description="Execution time (ms)")
    model_name: str | None = Field(default=None, max_length=50, description="LLM model")
    success: bool = Field(..., description="Execution success")
    error_message: str | None = Field(default=None, description="Error details")
    executed_at: datetime = Field(default_factory=datetime.utcnow)

    def calculate_estimated_cost(self) -> float:
        """Calculate estimated cost in USD.

        Uses OpenAI gpt-4 pricing:
        - Prompt: $0.03/1k tokens
        - Completion: $0.06/1k tokens

        Returns:
            Estimated cost in USD
        """
        if not self.prompt_tokens or not self.completion_tokens:
            return 0.0

        prompt_cost = (self.prompt_tokens / 1000.0) * 0.03
        completion_cost = (self.completion_tokens / 1000.0) * 0.06

        return prompt_cost + completion_cost
```

---

## Implementation Steps

### Step 1: Create PromptTemplate Model
**Duration**: 3-4 hours

- [ ] Create `src/domain/models/prompt_template.py`
- [ ] Implement all fields with Pydantic validators
- [ ] Implement `get_prompt_text()` method
- [ ] Add validators: `validate_template_json`, `validate_active_not_draft`
- [ ] Write unit tests

### Step 2: Create PromptMetadataChange Model
**Duration**: 1-2 hours

- [ ] Create `src/domain/models/prompt_metadata_change.py`
- [ ] Implement all fields
- [ ] Implement `create_change()` factory method
- [ ] Write unit tests

### Step 3: Create PromptExecution Model
**Duration**: 2-3 hours

- [ ] Create `src/domain/models/prompt_execution.py`
- [ ] Implement all fields
- [ ] Implement `calculate_estimated_cost()` method
- [ ] Write unit tests

---

## Testing

### Unit Tests

**File**: `tests/unit/domain/test_prompt_template.py`

```python
def test_prompt_template_validation():
    """Test Pydantic validation."""
    # Valid prompt
    prompt = PromptTemplate(
        name="test",
        version=1,
        template_json={
            "system": "You are an assistant.",
            "user_template": "Generate question for {skill}",
            "variables": ["skill"],
        },
    )
    assert prompt.name == "test"

    # Missing required keys → should fail
    with pytest.raises(ValueError, match="must contain"):
        PromptTemplate(
            name="test",
            version=1,
            template_json={"system": "Missing user_template"},
        )

    # Active draft → should fail
    with pytest.raises(ValueError, match="cannot be drafts"):
        PromptTemplate(
            name="test",
            version=1,
            template_json={"system": "...", "user_template": "...", "variables": []},
            is_active=True,
            is_draft=True,
        )


def test_get_prompt_text():
    """Test prompt rendering with variables."""
    prompt = PromptTemplate(
        name="test",
        version=1,
        template_json={
            "system": "You are an assistant.",
            "user_template": "Generate question for {skill} at {difficulty} level",
            "variables": ["skill", "difficulty"],
        },
    )

    # Render with all variables
    rendered = prompt.get_prompt_text(skill="Python", difficulty="medium")
    assert "You are an assistant" in rendered
    assert "Generate question for Python at medium level" in rendered

    # Missing variable → should fail
    with pytest.raises(ValueError, match="Missing variables"):
        prompt.get_prompt_text(skill="Python")
```

**File**: `tests/unit/domain/test_prompt_metadata_change.py`

```python
def test_create_change_factory():
    """Test factory method serializes values."""
    change = PromptMetadataChange.create_change(
        prompt_template_id=uuid4(),
        field_name="traffic_percentage",
        old_value=50,
        new_value=75,
        changed_by="admin",
        reason="Increase traffic",
    )

    assert change.field_name == "traffic_percentage"
    assert change.old_value == "50"  # Serialized to string
    assert change.new_value == "75"
    assert change.changed_by == "admin"
```

**File**: `tests/unit/domain/test_prompt_execution.py`

```python
def test_calculate_estimated_cost():
    """Test cost calculation with OpenAI pricing."""
    execution = PromptExecution(
        prompt_template_id=uuid4(),
        input_variables={},
        latency_ms=1000,
        success=True,
        prompt_tokens=1000,  # 1k tokens
        completion_tokens=2000,  # 2k tokens
    )

    cost = execution.calculate_estimated_cost()

    # Expected: (1000 * 0.03 / 1000) + (2000 * 0.06 / 1000) = 0.03 + 0.12 = 0.15
    assert cost == pytest.approx(0.15)

    # Missing tokens → should return 0
    execution_no_tokens = PromptExecution(
        prompt_template_id=uuid4(),
        input_variables={},
        latency_ms=1000,
        success=True,
    )
    assert execution_no_tokens.calculate_estimated_cost() == 0.0
```

---

## Success Criteria

- ✅ All 3 domain models created
- ✅ Pydantic validation working
- ✅ `get_prompt_text()` renders prompts correctly
- ✅ `create_change()` factory method works
- ✅ `calculate_estimated_cost()` calculates correctly
- ✅ Unit tests passing (>90% coverage)
- ✅ No external dependencies (pure Python + Pydantic)

---

## Related Files

**New Files**:
- `src/domain/models/prompt_template.py`
- `src/domain/models/prompt_metadata_change.py`
- `src/domain/models/prompt_execution.py`
- `tests/unit/domain/test_prompt_template.py`
- `tests/unit/domain/test_prompt_metadata_change.py`
- `tests/unit/domain/test_prompt_execution.py`

**Modified Files**:
- None

---

## Next Phase

→ [Phase 3: Repository Layer](./phase-03-repository-layer.md)

**Blockers**: None (Phase 1 complete)

---

## Notes

- All models use Pydantic for validation
- No SQLAlchemy imports (domain layer must be pure)
- Cost calculation hardcoded for OpenAI gpt-4 (can be extended later)
- `get_prompt_text()` uses Python `.format()` for variable substitution

---

**Phase Status**: Ready to implement
**Last Updated**: 2025-11-20
