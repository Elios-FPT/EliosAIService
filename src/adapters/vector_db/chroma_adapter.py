"""ChromaDB adapter for vector search operations.

This adapter uses lazy initialization to avoid blocking operations during module import.
All ChromaDB clients and OpenAI embeddings are initialized only when first accessed.
"""

from datetime import datetime

def debug_print(msg: str):
    """Helper function to print debug messages with timestamps."""
    print(f"DEBUG [{datetime.now().strftime('%H:%M:%S.%f')[:-3]}]: {msg}", flush=True)

debug_print("chroma_adapter.py: Starting imports...")

import os
import chromadb
import asyncio
import numpy as np
from uuid import UUID
from typing import Any, Dict
import json
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from ...domain.ports.vector_search_port import VectorSearchPort
from ...infrastructure.config import Settings

debug_print("chroma_adapter.py: Imports completed")

# Constants - safe to define at module level
CHROMA_PATH = os.path.join(os.path.dirname(__file__), "..", "chroma_db")
CV_COLLECTION_NAME = "cv_embedding"
QUESTION_COLLECTION_NAME = "question_embedding"
debug_print("chroma_adapter.py: Constants defined")


class ChromaAdapter(VectorSearchPort):
    """Interface for vector database operations.

    This port abstracts vector storage and semantic search, allowing easy
    switching between Pinecone, Weaviate, ChromaDB, etc.

    Uses lazy initialization to prevent blocking operations during import.
    """

    def __init__(self):
        """Initialize adapter with lazy-loaded dependencies."""
        self._chromaDB_client: chromadb.PersistentClient | None = None
        self._cv_collection = None
        self._question_collection = None
        self._embedding_client: OpenAIEmbeddings | None = None
        self._settings: Settings | None = None

    @property
    def chromaDB_client(self) -> chromadb.PersistentClient:
        """Get or create ChromaDB client (lazy initialization)."""
        if self._chromaDB_client is None:
            self._chromaDB_client = chromadb.PersistentClient(path=CHROMA_PATH)
        return self._chromaDB_client

    @property
    def cv_collection(self):
        """Get or create CV collection (lazy initialization)."""
        if self._cv_collection is None:
            self._cv_collection = self.chromaDB_client.get_or_create_collection(
                name=CV_COLLECTION_NAME
            )
        return self._cv_collection

    @property
    def question_collection(self):
        """Get or create question collection (lazy initialization)."""
        if self._question_collection is None:
            self._question_collection = self.chromaDB_client.get_or_create_collection(
                name=QUESTION_COLLECTION_NAME
            )
        return self._question_collection

    @property
    def settings(self) -> Settings:
        """Get or create settings instance (lazy initialization)."""
        if self._settings is None:
            # Load environment variables only when needed
            load_dotenv()
            self._settings = Settings()
        return self._settings

    @property
    def embedding_client(self) -> OpenAIEmbeddings:
        """Get or create OpenAI embeddings client (lazy initialization)."""
        if self._embedding_client is None:
            self._embedding_client = OpenAIEmbeddings(
                model=self.settings.openai_embedding_model,
                api_key=self.settings.openai_embedding_api_key,
                dimensions=1536,
                max_retries=3,
                request_timeout=30
            )
        return self._embedding_client

    async def store_cv_embedding(self, cv_analysis_id, embedding, metadatas):
        """Store a CV analysis vector embedding."""
        try:
            self.cv_collection.add(
                ids=[cv_analysis_id],
                embeddings=[embedding],
                metadatas=[metadatas]
            )
        except Exception as e:
            print(f"Error storing CV embedding: {e}")

    async def get_embedding(self, text):
        """Generate an embedding for the given text (summarized CV info)."""
        cleaned_text = text.strip()
        loop = asyncio.get_event_loop()
        try:
            embedding = await loop.run_in_executor(
                None,
                lambda: self.embedding_client.embed_query(cleaned_text)
            )
            return embedding
        except Exception as e:
            print(f"Error generating embedding: {e.__cause__}")
            return None

    async def delete_embeddings(self, ids):
        """Delete embeddings by their IDs."""
        valid_ids = [id.strip() for id in ids if id and id.strip()]

        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(None, lambda: self.cv_collection.delete(ids=valid_ids))
        except Exception as e:
            print(f"Error deleting embeddings: {e.__cause__}")

    async def find_similar_questions(self, query_embedding, top_k=5):
        """Find similar questions based on a query embedding."""

        loop = asyncio.get_event_loop()
        include_metadata = True
        try:
            raw_results = await loop.run_in_executor(
            None,
            lambda: self.cv_collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                include=["metadatas", "distances", "documents"] if include_metadata else ["distances"]
                )
            )
            ids = raw_results.get("ids", [[]])[0]
            distances = raw_results.get("distances", [[]])[0]
            metadatas = raw_results.get("metadatas", [[]])[0]
            results = []
            for i, doc_id in enumerate(ids):
                if i >= len(distances):
                    break
                distance = distances[i]
                # Convert distance → similarity (cosine: 0= giống nhất → 1=khác nhất)
                similarity_score = 1.0 - distance

                item = {
                    "id": doc_id,
                    "score": round(similarity_score, 4),
                    "distance": round(distance, 4)
                }
                if include_metadata and i < len(metadatas):
                    item["metadata"] = metadatas[i]

                results.append(item)
            return results
        except Exception as e:
            print(f"Error finding similar questions: {e}")
            return None

    async def store_question_embedding(self, question_id: UUID, embedding: list[float], metadatas: dict[str, Any]):
        try:
            self.question_collection.add(
                ids=[question_id],
                embeddings=[embedding],
                metadatas=[metadatas]
            )
        except Exception as e:
            print(f"Error storing question embedding: {e}")

    async def find_similar_answers(self, answer_embedding: list[float], reference_embeddings: list[list[float]]) -> float:
        return await super().find_similar_answers(answer_embedding, reference_embeddings)