"""Data models for vector search exemplar operations."""

from dataclasses import dataclass
from uuid import UUID

from .question import Difficulty, QuestionType


@dataclass
class ExemplarFilters:
    """Filters for exemplar search."""

    question_type: QuestionType | None = None
    difficulty: Difficulty | None = None
    skills: list[str] | None = None  # Normalized to lowercase by adapters


@dataclass
class ExemplarResult:
    """Result from exemplar search."""

    question_id: UUID
    text: str
    question_type: QuestionType
    difficulty: Difficulty
    skills: list[str]
    similarity_score: float

