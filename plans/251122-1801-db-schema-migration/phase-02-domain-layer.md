# Phase 2: Domain Layer

## Context Links

- **Parent Plan**: [plan.md](./plan.md)
- **Previous Phase**: [phase-01-database-migration.md](./phase-01-database-migration.md)
- **Dependencies**: Phase 1 complete (database schema updated)
- **Documentation**:
  - [Codebase Summary](../../docs/codebase-summary.md)
  - [System Architecture](../../docs/system-architecture.md)
  - [Code Standards](../../docs/code-standards.md)

---

## Overview

**Date**: 2025-11-22
**Priority**: 🔴 Critical
**Estimated Duration**: 2-3 hours
**Implementation Status**: ⏳ Pending
**Review Status**: ⏳ Pending

**Description**: Update domain models to match new schema - create CVSkill and InterviewQuestion models, update existing models to remove deprecated fields and use ENUMs.

---

## Key Insights

- Create 2 new domain models (CVSkill, InterviewQuestion) as rich entities
- Update 5 existing models (CVAnalysis, Question, Interview, Answer, PromptTemplate)
- Replace string types with ENUMs for type safety (QuestionType, Difficulty, ProficiencyLevel)
- Remove deprecated fields (cv_file_path, candidate_id in answers, arrays in interviews)
- Domain models remain database-agnostic (no SQLAlchemy dependencies)

---

## Requirements

### Functional Requirements
- Create CVSkill domain model (skill_name, proficiency_level, years_of_experience, is_primary)
- Create InterviewQuestion domain model (sequence_order, asked_at, skipped, skip_reason)
- Update CVAnalysis to use List[CVSkill] instead of skills JSONB
- Update Question to use ENUMs (QuestionType, Difficulty)
- Update Interview to remove question_ids/answer_ids arrays
- Update Answer to remove candidate_id, deprecated JSONB fields
- Update PromptTemplate with decomposed fields (system_prompt, user_template, model params)

### Non-Functional Requirements
- Maintain backward compatibility where possible
- Add type hints for all new fields
- Include docstrings for new models/methods
- Follow existing domain model patterns
- No database/adapter dependencies in domain layer

---

## Architecture

**Domain Layer Structure**:
```
src/domain/models/
├── cv_skill.py              (NEW - CVSkill entity)
├── interview_question.py    (NEW - InterviewQuestion entity)
├── cv_analysis.py          (UPDATED - List[CVSkill], remove JSONB)
├── question.py             (UPDATED - ENUMs, remove tags/criteria)
├── interview.py            (UPDATED - remove arrays)
├── answer.py               (UPDATED - remove candidate_id, metadata)
├── prompt_template.py      (UPDATED - decomposed fields)
└── __init__.py             (UPDATED - export new models)
```

**Dependency Flow**:
```
Domain Models (Pure Python)
    ↓ (no dependencies)
Domain Services (use models)
    ↓
Ports (abstract interfaces)
    ↓
Adapters (implement ports)
```

---

## Related Code Files

### Files to Create
- `src/domain/models/cv_skill.py` - CVSkill entity
- `src/domain/models/interview_question.py` - InterviewQuestion entity

### Files to Modify
- `src/domain/models/cv_analysis.py` - Update skills to List[CVSkill]
- `src/domain/models/question.py` - Add ENUMs, remove deprecated fields
- `src/domain/models/interview.py` - Remove question_ids, answer_ids
- `src/domain/models/answer.py` - Remove candidate_id, metadata, evaluation
- `src/domain/models/prompt_template.py` - Add decomposed fields
- `src/domain/models/__init__.py` - Export new models

---

## Implementation Steps

### Step 1: Create ProficiencyLevel ENUM (10 mins)

**File**: `src/domain/models/cv_skill.py`

```python
"""Domain model for CV skill."""
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4
from datetime import datetime
from pydantic import BaseModel, Field, field_validator


class ProficiencyLevel(str, Enum):
    """Skill proficiency levels matching DB ENUM."""
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


class CVSkill(BaseModel):
    """
    Represents a skill extracted from a CV.

    Normalized from cv_analyses.skills JSONB to dedicated table.
    """

    id: UUID = Field(default_factory=uuid4)
    cv_analysis_id: UUID
    skill_name: str = Field(min_length=1, max_length=100)
    proficiency_level: Optional[ProficiencyLevel] = ProficiencyLevel.INTERMEDIATE
    years_of_experience: Optional[float] = Field(default=None, ge=0, le=50)
    is_primary: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)

    @field_validator('skill_name')
    @classmethod
    def validate_skill_name(cls, v: str) -> str:
        """Normalize skill name (strip whitespace, title case)."""
        normalized = v.strip()
        if not normalized:
            raise ValueError("skill_name cannot be empty")
        return normalized

    def __str__(self) -> str:
        """String representation for logging."""
        return f"CVSkill({self.skill_name}, {self.proficiency_level.value})"

    def __repr__(self) -> str:
        """Developer-friendly representation."""
        return (
            f"CVSkill(id={self.id}, skill_name='{self.skill_name}', "
            f"proficiency={self.proficiency_level.value}, "
            f"years={self.years_of_experience}, is_primary={self.is_primary})"
        )
```

### Step 2: Create InterviewQuestion Model (15 mins)

**File**: `src/domain/models/interview_question.py`

```python
"""Domain model for interview question relationship."""
from typing import Optional
from uuid import UUID, uuid4
from datetime import datetime
from pydantic import BaseModel, Field


class InterviewQuestion(BaseModel):
    """
    Represents a question assigned to an interview.

    Junction table between interviews and questions with metadata.
    """

    id: UUID = Field(default_factory=uuid4)
    interview_id: UUID
    question_id: UUID
    sequence_order: int = Field(ge=0, description="0-based question order")
    asked_at: Optional[datetime] = None
    skipped: bool = False
    skip_reason: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    def mark_asked(self) -> None:
        """Mark question as asked (sets asked_at to now)."""
        self.asked_at = datetime.utcnow()

    def mark_skipped(self, reason: str) -> None:
        """Mark question as skipped with reason."""
        self.skipped = True
        self.skip_reason = reason

    def is_asked(self) -> bool:
        """Check if question has been asked."""
        return self.asked_at is not None

    def __str__(self) -> str:
        """String representation for logging."""
        status = "asked" if self.is_asked() else "skipped" if self.skipped else "pending"
        return f"InterviewQuestion(seq={self.sequence_order}, status={status})"

    def __repr__(self) -> str:
        """Developer-friendly representation."""
        return (
            f"InterviewQuestion(id={self.id}, interview_id={self.interview_id}, "
            f"question_id={self.question_id}, sequence_order={self.sequence_order}, "
            f"asked_at={self.asked_at}, skipped={self.skipped})"
        )
```

### Step 3: Update CVAnalysis Model (20 mins)

**File**: `src/domain/models/cv_analysis.py`

Find and replace:

```python
# OLD (remove):
from typing import List, Optional, Dict, Any
# ...
skills: List[Dict[str, Any]] = Field(default_factory=list)
cv_file_path: Optional[str] = None
metadata: Dict[str, Any] = Field(default_factory=dict)

# NEW:
from typing import List, Optional
from .cv_skill import CVSkill, ProficiencyLevel
# ...
skills: List[CVSkill] = Field(default_factory=list)
# Remove cv_file_path and metadata completely
```

Add methods:

```python
def add_skill(
    self,
    skill_name: str,
    proficiency_level: Optional[ProficiencyLevel] = None,
    years_of_experience: Optional[float] = None,
    is_primary: bool = False
) -> CVSkill:
    """
    Add a skill to this CV analysis.

    Args:
        skill_name: Name of the skill (e.g., "Python", "Leadership")
        proficiency_level: Skill proficiency (default: INTERMEDIATE)
        years_of_experience: Years of experience with skill
        is_primary: Whether this is a primary/core skill

    Returns:
        The created CVSkill instance
    """
    skill = CVSkill(
        cv_analysis_id=self.id,
        skill_name=skill_name,
        proficiency_level=proficiency_level or ProficiencyLevel.INTERMEDIATE,
        years_of_experience=years_of_experience,
        is_primary=is_primary
    )
    self.skills.append(skill)
    return skill

def get_primary_skills(self) -> List[CVSkill]:
    """Get all primary skills."""
    return [skill for skill in self.skills if skill.is_primary]

def get_skills_by_proficiency(self, level: ProficiencyLevel) -> List[CVSkill]:
    """Get skills filtered by proficiency level."""
    return [skill for skill in self.skills if skill.proficiency_level == level]
```

### Step 4: Update Question Model with ENUMs (25 mins)

**File**: `src/domain/models/question.py`

```python
# Add ENUMs at top
from enum import Enum

class QuestionType(str, Enum):
    """Question type categories matching DB ENUM."""
    TECHNICAL = "technical"
    BEHAVIORAL = "behavioral"
    SITUATIONAL = "situational"
    PROBLEM_SOLVING = "problem_solving"
    SYSTEM_DESIGN = "system_design"


class Difficulty(str, Enum):
    """Question difficulty levels matching DB ENUM."""
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    EXPERT = "expert"


# Update Question model
class Question(BaseModel):
    """Interview question entity."""

    id: UUID = Field(default_factory=uuid4)
    question_text: str = Field(min_length=10, max_length=5000)
    question_type: QuestionType = QuestionType.TECHNICAL
    difficulty: Difficulty = Difficulty.MEDIUM
    expected_answer: Optional[str] = None
    topics: List[str] = Field(default_factory=list)
    # REMOVE: tags, evaluation_criteria
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Update __str__ and __repr__ to use ENUMs
    def __str__(self) -> str:
        return f"Question({self.question_type.value}, {self.difficulty.value})"
```

### Step 5: Update Interview Model (15 mins)

**File**: `src/domain/models/interview.py`

```python
# REMOVE these fields:
question_ids: List[UUID] = Field(default_factory=list)
answer_ids: List[UUID] = Field(default_factory=list)

# Keep other fields unchanged:
# - id, candidate_id, cv_analysis_id, status, current_question_index, etc.

# Remove any methods that reference question_ids/answer_ids
# Example methods to REMOVE:
# - add_question(question_id: UUID)
# - add_answer(answer_id: UUID)
# - get_next_question_id()

# Note: Question navigation will now use InterviewQuestion relationship
# (handled in repository layer)
```

### Step 6: Update Answer Model (15 mins)

**File**: `src/domain/models/answer.py`

```python
# REMOVE these fields:
candidate_id: UUID  # Redundant (via interview_id → interview.candidate_id)
metadata: Dict[str, Any] = Field(default_factory=dict)
evaluation: Optional[Dict[str, Any]] = None  # Migrated to evaluations table in 0003
gaps: Optional[Dict[str, Any]] = None  # Migrated to evaluations table in 0003
similarity_score: Optional[float] = None  # Now in evaluations table
evaluated_at: Optional[datetime] = None  # Now in evaluations table

# KEEP these fields:
# - id, interview_id, question_id, answer_text, audio_file_path, transcription_metadata
# - created_at, updated_at
```

### Step 7: Update PromptTemplate Model (30 mins)

**File**: `src/domain/models/prompt_template.py`

```python
from typing import List, Dict, Optional, Any
from decimal import Decimal

class PromptTemplate(BaseModel):
    """
    LLM prompt template with version control.

    Decomposed from template_json for UI editing.
    """

    id: UUID = Field(default_factory=uuid4)
    prompt_name: str = Field(min_length=1, max_length=100)
    version: int = Field(ge=1)
    is_active: bool = False
    traffic_percentage: int = Field(ge=0, le=100)

    # Decomposed prompt structure
    system_prompt: str = Field(description="System message (role/context)")
    user_template: str = Field(description="User message template with {variables}")
    input_variables: List[str] = Field(
        default_factory=list,
        description="Variables to interpolate (e.g., ['question', 'answer'])"
    )
    partial_variables: Dict[str, Any] = Field(
        default_factory=dict,
        description="Pre-filled variables (e.g., {'format': 'JSON'})"
    )

    # Output parsing config
    output_parser_type: str = Field(
        default="json_output_parser",
        description="Parser type (json_output_parser, structured_output_parser, etc.)"
    )
    output_schema: Dict[str, Any] = Field(
        default_factory=dict,
        description="Expected output schema (JSON Schema format)"
    )

    # Model parameters
    temperature: Decimal = Field(
        default=Decimal("0.3"),
        ge=Decimal("0"),
        le=Decimal("2"),
        description="Sampling temperature (0-2)"
    )
    max_tokens: int = Field(default=2000, ge=1, le=100000)
    top_p: Decimal = Field(
        default=Decimal("0.95"),
        ge=Decimal("0"),
        le=Decimal("1"),
        description="Nucleus sampling parameter"
    )
    frequency_penalty: Decimal = Field(
        default=Decimal("0"),
        ge=Decimal("-2"),
        le=Decimal("2")
    )
    presence_penalty: Decimal = Field(
        default=Decimal("0"),
        ge=Decimal("-2"),
        le=Decimal("2")
    )

    # Soft delete
    deleted_at: Optional[datetime] = None

    # Legacy JSONB (backup, not used in domain logic)
    template_json_legacy: Optional[Dict[str, Any]] = None

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def soft_delete(self) -> None:
        """Soft delete this template."""
        self.deleted_at = datetime.utcnow()
        self.is_active = False

    def is_deleted(self) -> bool:
        """Check if template is soft-deleted."""
        return self.deleted_at is not None

    def to_langchain_config(self) -> Dict[str, Any]:
        """
        Convert to LangChain-compatible config.

        Returns:
            Dict matching structure expected by LangChainAdapter
        """
        return {
            "template_type": "chat",
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": self.user_template}
            ],
            "input_variables": self.input_variables,
            "partial_variables": self.partial_variables,
            "output_parser": {
                "type": self.output_parser_type,
                "schema": self.output_schema
            },
            "model_params": {
                "temperature": float(self.temperature),
                "max_tokens": self.max_tokens,
                "top_p": float(self.top_p),
                "frequency_penalty": float(self.frequency_penalty),
                "presence_penalty": float(self.presence_penalty)
            }
        }
```

### Step 8: Update __init__.py Exports (5 mins)

**File**: `src/domain/models/__init__.py`

```python
"""Domain models for Elios AI Interview Service."""

from .candidate import Candidate
from .cv_analysis import CVAnalysis
from .cv_skill import CVSkill, ProficiencyLevel  # NEW
from .question import Question, QuestionType, Difficulty  # Updated with ENUMs
from .interview import Interview, InterviewStatus
from .interview_question import InterviewQuestion  # NEW
from .answer import Answer
from .evaluation import Evaluation
from .prompt_template import PromptTemplate
from .prompt_execution import PromptExecution
from .prompt_metadata_change import PromptMetadataChange
from .follow_up_question import FollowUpQuestion

__all__ = [
    # Existing
    "Candidate",
    "CVAnalysis",
    "Question",
    "Interview",
    "InterviewStatus",
    "Answer",
    "Evaluation",
    "PromptTemplate",
    "PromptExecution",
    "PromptMetadataChange",
    "FollowUpQuestion",

    # New models
    "CVSkill",
    "InterviewQuestion",

    # New ENUMs
    "ProficiencyLevel",
    "QuestionType",
    "Difficulty",
]
```

---

## Todo List

- [ ] Create `cv_skill.py` with ProficiencyLevel ENUM and CVSkill model
- [ ] Create `interview_question.py` with InterviewQuestion model
- [ ] Update `cv_analysis.py` - remove JSONB fields, add List[CVSkill]
- [ ] Add helper methods to CVAnalysis (add_skill, get_primary_skills)
- [ ] Update `question.py` - add QuestionType and Difficulty ENUMs
- [ ] Remove tags and evaluation_criteria from Question
- [ ] Update `interview.py` - remove question_ids and answer_ids arrays
- [ ] Update `answer.py` - remove candidate_id and deprecated JSONB fields
- [ ] Update `prompt_template.py` - add 11 decomposed fields
- [ ] Add to_langchain_config() method to PromptTemplate
- [ ] Update `__init__.py` to export new models and ENUMs
- [ ] Run type checker: `mypy src/domain/models/`
- [ ] Verify no import errors: `python -c "from src.domain.models import *"`

---

## Success Criteria

### Must-Have
- ✅ CVSkill model created with ProficiencyLevel ENUM
- ✅ InterviewQuestion model created with junction table fields
- ✅ CVAnalysis uses List[CVSkill] instead of JSONB
- ✅ Question uses QuestionType and Difficulty ENUMs
- ✅ Interview has no question_ids/answer_ids arrays
- ✅ Answer has no candidate_id or deprecated fields
- ✅ PromptTemplate has 11 decomposed fields + to_langchain_config()
- ✅ All models exported in __init__.py
- ✅ No type errors (`mypy src/domain/models/`)
- ✅ No import errors

### Nice-to-Have
- ✅ Comprehensive docstrings for new models
- ✅ Helper methods for common operations
- ✅ Field validators for data integrity
- ✅ __str__ and __repr__ for debugging

---

## Risk Assessment

### Risk 1: Breaking Changes in Existing Code
**Likelihood**: High
**Impact**: High
**Mitigation**:
- This phase ONLY updates domain models (no adapters/services yet)
- Code won't run until Phases 3-6 complete
- Tests will catch incompatibilities in Phase 7

### Risk 2: ENUM Compatibility Issues
**Likelihood**: Low
**Impact**: Medium
**Mitigation**:
- ENUMs match database ENUM values exactly
- Pydantic handles ENUM validation automatically
- String values work transparently with ENUMs

### Risk 3: Missing Fields
**Likelihood**: Low
**Impact**: Medium
**Mitigation**:
- Cross-reference with migration SQL (Phase 1)
- Follow DB schema exactly
- Type checker will catch missing fields

---

## Security Considerations

### Data Validation
- **Risk**: Invalid data in domain models
- **Mitigation**:
  - Pydantic validators on all new fields
  - ENUM constraints enforce valid values
  - Field min/max constraints (e.g., temperature 0-2)

### No Sensitive Data Exposure
- **Risk**: Domain models log sensitive data
- **Mitigation**:
  - __str__ methods don't include CV text or answers
  - Sanitize in logging layer (not domain)

---

## Next Steps

**On Success**:
- ✅ Proceed to [Phase 3: Adapters Layer](./phase-03-adapters-layer.md)
- Domain models ready for adapter implementation
- Type system enforces new schema

**On Failure**:
- ❌ Fix type errors reported by mypy
- ❌ Fix import errors
- ❌ Verify ENUM values match database
- ❌ Do NOT proceed until domain layer compiles

**Validation Commands**:
```bash
# Type check
mypy src/domain/models/

# Import check
python -c "from src.domain.models import CVSkill, InterviewQuestion, ProficiencyLevel, QuestionType, Difficulty"

# Pydantic validation test
python -c "
from src.domain.models import CVSkill, ProficiencyLevel
skill = CVSkill(
    cv_analysis_id='123e4567-e89b-12d3-a456-426614174000',
    skill_name='Python',
    proficiency_level=ProficiencyLevel.EXPERT
)
print(skill)
"
```

---

**Phase Status**: ⏳ Ready to Start
**Blocker**: Phase 1 must be complete
**Estimated Time**: 2-3 hours
**Dependencies**: None (pure Python models)
