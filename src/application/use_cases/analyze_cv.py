"""Analyze CV use case."""

from uuid import UUID

from ...domain.models.cv_analysis import CVAnalysis
from ...application.ports.cv_analyzer_port import CVAnalyzerPort, FileType
from ...application.ports.vector_search_port import VectorSearchPort
from ...application.ports.cv_analysis_repository_port import CVAnalysisRepositoryPort


class AnalyzeCVUseCase:
    """Use case for analyzing a candidate's CV.

    This orchestrates the CV analysis process:
    1. Extract text from CV file
    2. Analyze and extract structured information
    3. Generate embeddings for semantic search
    4. Store embeddings in vector database
    """

    def __init__(
        self,
        cv_analyzer: CVAnalyzerPort,
        vector_search: VectorSearchPort,
        cv_analysis_repository_port: CVAnalysisRepositoryPort,
    ):
        """Initialize use case with required ports.

        Args:
            cv_analyzer: CV analysis service
            vector_search: Vector database service
        """
        self.cv_analyzer = cv_analyzer
        self.vector_search = vector_search
        self.cv_analysis_repository_port = cv_analysis_repository_port

    async def execute(
        self,
        cv_content: bytes,
        file_type: FileType,
        candidate_id: UUID,
    ) -> CVAnalysis:
        """Execute CV analysis.

        Args:
            cv_content: CV file content as bytes
            file_type: File type ("pdf", "docx", "txt")
            candidate_id: ID of the candidate

        Returns:
            CVAnalysis with extracted information

        Raises:
            ValueError: If CV file is invalid or cannot be processed
        """
        # Step 1: Analyze CV using the CV analyzer port
        cv_analysis = await self.cv_analyzer.analyze_cv(
            cv_content=cv_content,
            file_type=file_type,
            candidate_id=str(candidate_id),
        )

        # Step 2: Persist CV analysis (candidate lifecycle owned by external service)
        try:
            await self.cv_analysis_repository_port.save(cv_analysis)
        except Exception as e:
            raise ValueError(f"Failed to save CV analysis: {e}") from e

        return cv_analysis
