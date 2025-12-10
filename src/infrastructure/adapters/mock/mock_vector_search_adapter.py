"""Mock vector search adapter for development and testing."""

from dataclasses import dataclass
from uuid import UUID

from src.domain.models.exemplar_models import ExemplarFilters, ExemplarResult
from src.domain.models.question import Difficulty, QuestionType
from src.application.ports.vector_search_port import VectorSearchPort


@dataclass
class _MockQuestion:
    """Internal storage for mock questions."""

    question_id: UUID
    text: str
    question_type: QuestionType
    difficulty: Difficulty
    skills: list[str]  # Already normalized


class MockVectorSearchAdapter(VectorSearchPort):
    """Mock vector search adapter for testing."""

    def __init__(self):
        """Initialize with seed questions."""
        self._questions: dict[UUID, _MockQuestion] = {}
        self._seed_mock_data()

    def _seed_mock_data(self) -> None:
        """Seed with deterministic mock questions."""
        seed_questions = [
            (
                UUID("650e8400-e29b-41d4-a716-446655440001"),
                "Explain the difference between var, let, and const in JavaScript.",
                QuestionType.TECHNICAL,
                Difficulty.EASY,
                ["javascript"],
            ),
            (
                UUID("650e8400-e29b-41d4-a716-446655440002"),
                "What is a REST API and how does it work?",
                QuestionType.TECHNICAL,
                Difficulty.EASY,
                ["api", "rest"],
            ),
            (
                UUID("650e8400-e29b-41d4-a716-446655440003"),
                "Explain async/await in Python.",
                QuestionType.TECHNICAL,
                Difficulty.MEDIUM,
                ["python", "async"],
            ),
            (
                UUID("650e8400-e29b-41d4-a716-446655440004"),
                "Explain SOLID principles.",
                QuestionType.TECHNICAL,
                Difficulty.MEDIUM,
                ["oop", "design"],
            ),
            (
                UUID("650e8400-e29b-41d4-a716-446655440005"),
                "Explain database normalization.",
                QuestionType.TECHNICAL,
                Difficulty.HARD,
                ["database", "sql"],
            ),
            (
                UUID("650e8400-e29b-41d4-a716-446655440006"),
                "Design a microservices architecture.",
                QuestionType.SYSTEM_DESIGN,
                Difficulty.HARD,
                ["architecture"],
            ),
            (
                UUID("650e8400-e29b-41d4-a716-446655440007"),
                "Tell me about a challenging project.",
                QuestionType.BEHAVIORAL,
                Difficulty.MEDIUM,
                ["communication"],
            ),
            (
                UUID("650e8400-e29b-41d4-a716-446655440008"),
                "How do you handle teamwork conflicts?",
                QuestionType.BEHAVIORAL,
                Difficulty.MEDIUM,
                ["teamwork"],
            ),
        ]

        for qid, text, qtype, diff, skills in seed_questions:
            self._questions[qid] = _MockQuestion(
                question_id=qid,
                text=text,
                question_type=qtype,
                difficulty=diff,
                skills=[s.lower() for s in skills],
            )

    async def insert_question(
        self,
        question_id: UUID,
        text: str,
        question_type: QuestionType,
        difficulty: Difficulty,
        skills: list[str],
    ) -> None:
        """Insert question into mock storage."""
        self._questions[question_id] = _MockQuestion(
            question_id=question_id,
            text=text,
            question_type=question_type,
            difficulty=difficulty,
            skills=[s.lower() for s in skills],
        )

    async def search_exemplars(
        self,
        cv_summary: str,
        filters: ExemplarFilters | None = None,
        top_k: int = 5,
    ) -> list[ExemplarResult]:
        """Search mock storage with metadata filters."""
        results: list[ExemplarResult] = []

        for q in self._questions.values():
            if filters:
                if filters.question_type and q.question_type != filters.question_type:
                    continue
                if filters.difficulty and q.difficulty != filters.difficulty:
                    continue
                if filters.skills:
                    filter_skills = {s.lower() for s in filters.skills}
                    if not filter_skills.intersection(set(q.skills)):
                        continue

            results.append(
                ExemplarResult(
                    question_id=q.question_id,
                    text=q.text,
                    question_type=q.question_type,
                    difficulty=q.difficulty,
                    skills=q.skills,
                    similarity_score=0.0,
                )
            )

        results.sort(key=lambda r: str(r.question_id))

        for i, result in enumerate(results[:top_k]):
            result.similarity_score = 0.95 - (i * 0.05)

        return results[:top_k]

    def clear(self) -> None:
        """Clear all stored questions (useful for tests)."""
        self._questions.clear()

    def reset(self) -> None:
        """Reset to seed data (useful for tests)."""
        self._questions.clear()
        self._seed_mock_data()