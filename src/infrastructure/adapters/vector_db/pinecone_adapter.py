"""Pinecone vector database adapter with hosted embedding."""

from uuid import UUID

from pinecone import Pinecone

from src.domain.models.exemplar_models import ExemplarFilters, ExemplarResult
from src.domain.models.question import Difficulty, QuestionType
from src.application.ports.vector_search_port import VectorSearchPort


class PineconeAdapter(VectorSearchPort):
    """Pinecone implementation using hosted embedding.

    Uses Pinecone's integrated embedding model to automatically convert text
    to vectors during upsert and search operations.
    """

    def __init__(
        self,
        api_key: str,
        index_name: str,
        namespace: str = "__default__",
    ):
        """Initialize Pinecone adapter."""
        self.pc = Pinecone(api_key=api_key)
        self.index = self.pc.Index(index_name)
        self.namespace = namespace

    async def insert_question(
        self,
        question_id: UUID,
        text: str,
        question_type: QuestionType,
        difficulty: Difficulty,
        skills: list[str],
    ) -> None:
        """Insert question with auto-generated embedding."""
        normalized_skills = [s.lower() for s in skills]

        record = {
            "id": str(question_id),
            "text": text,
            "question_type": question_type.value,
            "difficulty": difficulty.value,
            "skills": normalized_skills,
        }

        # upsert_records handles embedding generation automatically
        self.index.upsert_records(records=[record], namespace=self.namespace)

    async def search_exemplars(
        self,
        cv_summary: str,
        filters: ExemplarFilters | None = None,
        top_k: int = 5,
    ) -> list[ExemplarResult]:
        """Search for exemplar questions using hybrid search."""
        pinecone_filter: dict[str, object] = {}

        if filters:
            if filters.question_type:
                pinecone_filter["question_type"] = {"$eq": filters.question_type.value}
            if filters.difficulty:
                pinecone_filter["difficulty"] = {"$eq": filters.difficulty.value}
            if filters.skills:
                normalized = [s.lower() for s in filters.skills]
                pinecone_filter["skills"] = {"$in": normalized}

        results = self.index.search_records(
            namespace=self.namespace,
            query={
                "inputs": {"text": cv_summary},
                "top_k": top_k,
                "filter": pinecone_filter or None,
            },
        )

        exemplars: list[ExemplarResult] = []
        for hit in results.get("result", {}).get("hits", []):
            exemplars.append(
                ExemplarResult(
                    question_id=UUID(hit["_id"]),
                    text=hit["fields"].get("text", ""),
                    question_type=QuestionType(hit["fields"].get("question_type", QuestionType.TECHNICAL.value)),
                    difficulty=Difficulty(hit["fields"].get("difficulty", Difficulty.MEDIUM.value)),
                    skills=hit["fields"].get("skills", []),
                    similarity_score=hit.get("_score", 0.0),
                )
            )

        return exemplars
