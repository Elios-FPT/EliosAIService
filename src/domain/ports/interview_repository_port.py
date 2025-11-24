"""Interview repository port interface."""

from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from ..models.interview import Interview, InterviewStatus
from ..models.interview_question import InterviewQuestion


class InterviewRepositoryPort(ABC):
    """Interface for interview persistence operations.

    This port abstracts database operations for interviews,
    allowing easy switching between databases or storage mechanisms.
    """

    @abstractmethod
    async def save(self, interview: Interview) -> Interview:
        """Save an interview.

        Args:
            interview: Interview to save

        Returns:
            Saved interview with updated metadata
        """
        pass

    @abstractmethod
    async def get_by_id(self, interview_id: UUID) -> Interview | None:
        """Retrieve an interview by ID.

        Args:
            interview_id: Interview identifier

        Returns:
            Interview if found, None otherwise
        """
        pass

    @abstractmethod
    async def get_by_candidate_id(
        self,
        candidate_id: UUID,
        status: InterviewStatus | None = None,
    ) -> list[Interview]:
        """Retrieve interviews for a candidate.

        Args:
            candidate_id: Candidate identifier
            status: Optional status filter

        Returns:
            List of interviews
        """
        pass

    @abstractmethod
    async def get_active_by_candidate(self, candidate_id: UUID) -> Interview | None:
        """Retrieve the most recent active interview for a candidate.

        Active interviews are those that are not in terminal states (COMPLETE, CANCELLED).
        This includes: PLANNING, IDLE, QUESTIONING, EVALUATING, FOLLOW_UP.

        Args:
            candidate_id: Candidate identifier

        Returns:
            Most recent active interview if found, None otherwise
        """
        pass

    @abstractmethod
    async def get_by_status(
        self,
        status: InterviewStatus,
        limit: int = 100,
    ) -> list[Interview]:
        """Retrieve interviews by status.

        Args:
            status: Interview status
            limit: Maximum number of results

        Returns:
            List of interviews
        """
        pass

    @abstractmethod
    async def update(self, interview: Interview) -> Interview:
        """Update an existing interview.

        Args:
            interview: Interview with updated data

        Returns:
            Updated interview
        """
        pass

    @abstractmethod
    async def delete(self, interview_id: UUID) -> bool:
        """Delete an interview.

        Args:
            interview_id: Interview identifier

        Returns:
            True if deleted, False if not found
        """
        pass

    @abstractmethod
    async def list_all(
        self,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Interview]:
        """List all interviews with pagination.

        Args:
            skip: Number of interviews to skip
            limit: Maximum number of results

        Returns:
            List of interviews
        """
        pass

    # Methods for interview_questions junction table management

    @abstractmethod
    async def get_interview_questions(self, interview_id: UUID) -> list[InterviewQuestion]:
        """Get all questions for an interview, ordered by sequence.

        Args:
            interview_id: UUID of the interview

        Returns:
            List of InterviewQuestion domain models ordered by sequence_order
        """
        pass

    @abstractmethod
    async def add_question(
        self,
        interview_id: UUID,
        question_id: UUID,
        sequence_order: int,
    ) -> InterviewQuestion:
        """Add a question to an interview with specified sequence order.

        Args:
            interview_id: UUID of the interview
            question_id: UUID of the question to add
            sequence_order: 0-based order in the interview sequence

        Returns:
            Created InterviewQuestion domain model
        """
        pass

    @abstractmethod
    async def get_current_question(self, interview_id: UUID) -> InterviewQuestion | None:
        """Get the current question for an interview based on current_question_index.

        Args:
            interview_id: UUID of the interview

        Returns:
            Current InterviewQuestion or None if interview complete or not found
        """
        pass

    @abstractmethod
    async def mark_question_asked(
        self,
        interview_question_id: UUID,
        asked_at: datetime | None = None,
    ) -> InterviewQuestion:
        """Mark a question as asked with timestamp.

        Args:
            interview_question_id: UUID of the InterviewQuestion record
            asked_at: Timestamp when question was asked (defaults to now)

        Returns:
            Updated InterviewQuestion domain model

        Raises:
            ValueError: If InterviewQuestion not found
        """
        pass

    @abstractmethod
    async def count_interview_questions(self, interview_id: UUID) -> int:
        """Count total questions for an interview.

        Args:
            interview_id: UUID of the interview

        Returns:
            Total number of questions in the interview
        """
        pass
