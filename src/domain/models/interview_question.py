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
