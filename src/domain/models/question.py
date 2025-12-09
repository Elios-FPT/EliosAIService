"""Question domain model."""

from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


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


# Alias for backward compatibility
DifficultyLevel = Difficulty


class Question(BaseModel):
    """Represents an interview question.

    Questions are value objects in the interview domain.
    They contain metadata for semantic search and categorization.
    """

    id: UUID = Field(default_factory=uuid4)
    text: str
    question_type: QuestionType
    difficulty: Difficulty
    skills: list[str] = Field(default_factory=list)  # e.g., ["Python", "OOP"]
    embedding: list[float] | None = None  # Vector embedding for semantic search

    # Pre-planning fields for adaptive interviews
    ideal_answer: str | None = None  # Reference answer for similarity scoring and evaluation
    rationale: str | None = None  # Explanation of why this question is suitable for the candidate

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        """Pydantic configuration."""

        pass

    def has_skill(self, skill: str) -> bool:
        """Check if question tests a specific skill.

        Args:
            skill: Skill name to check

        Returns:
            True if skill is tested, False otherwise
        """
        return skill.lower() in [s.lower() for s in self.skills]

    def is_suitable_for_difficulty(self, max_difficulty: Difficulty) -> bool:
        """Check if question difficulty is appropriate.

        Args:
            max_difficulty: Maximum allowed difficulty

        Returns:
            True if suitable, False otherwise
        """
        difficulty_order = {
            Difficulty.EASY: 1,
            Difficulty.MEDIUM: 2,
            Difficulty.HARD: 3,
            Difficulty.EXPERT: 4,
        }
        return difficulty_order[self.difficulty] <= difficulty_order[max_difficulty]

    def has_ideal_answer(self) -> bool:
        """Check if question has ideal answer for similarity scoring.

        Returns:
            True if ideal_answer is present and non-empty
        """
        return self.ideal_answer is not None and len(self.ideal_answer.strip()) > 10

    @property
    def is_planned(self) -> bool:
        """Check if question is part of pre-planned interview.

        Returns:
            True if has ideal_answer and rationale
        """
        return self.has_ideal_answer() and self.rationale is not None
