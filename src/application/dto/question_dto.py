"""DTOs for question CRUD endpoints."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from src.domain.models.question import Difficulty, QuestionType


class QuestionBase(BaseModel):
    """Shared fields for question creation/update."""

    text: str = Field(..., min_length=1, description="Question text")
    question_type: QuestionType
    difficulty: Difficulty
    skills: list[str] = Field(..., min_items=1, description="List of related skills")
    ideal_answer: str | None = Field(
        default=None, description="Optional reference answer for evaluation"
    )
    rationale: str | None = Field(
        default=None, description="Optional rationale for why the question was chosen"
    )

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("text cannot be empty")
        return cleaned

    @field_validator("skills")
    @classmethod
    def validate_skills(cls, value: list[str]) -> list[str]:
        cleaned = [s.strip() for s in value if s and s.strip()]
        if not cleaned:
            raise ValueError("skills must include at least one non-empty entry")
        return cleaned


class CreateQuestionRequest(QuestionBase):
    """Create question payload."""

    pass


class UpdateQuestionRequest(BaseModel):
    """Partial update payload."""

    text: str | None = None
    question_type: QuestionType | None = None
    difficulty: Difficulty | None = None
    skills: list[str] | None = None
    ideal_answer: str | None = None
    rationale: str | None = None

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str | None) -> str | None:
        if value is None:
            return value
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("text cannot be empty")
        return cleaned

    @field_validator("skills")
    @classmethod
    def validate_skills(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return value
        cleaned = [s.strip() for s in value if s and s.strip()]
        if not cleaned:
            raise ValueError("skills must include at least one non-empty entry")
        return cleaned

    @model_validator(mode="after")
    def ensure_at_least_one_field(self):
        if not any(
            getattr(self, field) is not None
            for field in [
                "text",
                "question_type",
                "difficulty",
                "skills",
                "ideal_answer",
                "rationale",
            ]
        ):
            raise ValueError("At least one field must be provided for update")
        return self


class QuestionResponse(BaseModel):
    """Response with question details."""

    id: UUID
    text: str
    question_type: QuestionType
    difficulty: Difficulty
    skills: list[str]
    ideal_answer: str | None = None
    rationale: str | None = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, question) -> "QuestionResponse":
        return cls(
            id=question.id,
            text=question.text,
            question_type=question.question_type,
            difficulty=question.difficulty,
            skills=question.skills,
            ideal_answer=question.ideal_answer,
            rationale=question.rationale,
            created_at=question.created_at,
            updated_at=question.updated_at,
        )


class QuestionListResponse(BaseModel):
    """Paginated question list response."""

    items: list[QuestionResponse]
    total: int
    limit: int
    offset: int

