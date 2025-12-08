"""Vector search port interface."""

from abc import ABC, abstractmethod
from uuid import UUID

from ..models.exemplar_models import ExemplarFilters, ExemplarResult
from ..models.question import Difficulty, QuestionType


class VectorSearchPort(ABC):
    """Interface for vector database operations.

    Supports question storage and hybrid search using Pinecone's
    hosted embedding feature for automatic text-to-vector conversion.
    """

    @abstractmethod
    async def insert_question(
        self,
        question_id: UUID,
        text: str,
        question_type: QuestionType,
        difficulty: Difficulty,
        skills: list[str],
    ) -> None:
        """Insert question into vector database.

        Embedding generated automatically by Pinecone from text.
        Skills normalized to lowercase for consistent matching.

        Args:
            question_id: Unique question identifier
            text: Question text (embedded automatically)
            question_type: Type of question (technical, behavioral, etc.)
            difficulty: Difficulty level
            skills: Related skills (will be lowercased)
        """
        pass

    @abstractmethod
    async def search_exemplars(
        self,
        cv_summary: str,
        filters: ExemplarFilters | None = None,
        top_k: int = 5,
    ) -> list[ExemplarResult]:
        """Search for exemplar questions using hybrid search.

        1. Pre-filter by metadata (question_type, difficulty, skills)
        2. Rank by cosine similarity to cv_summary embedding

        Args:
            cv_summary: CV summary text (embedded automatically)
            filters: Optional metadata filters
            top_k: Maximum results to return

        Returns:
            List of matching questions with similarity scores
        """
        pass
