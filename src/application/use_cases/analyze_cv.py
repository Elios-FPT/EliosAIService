"""Analyze CV use case."""

from uuid import UUID

from ...domain.models.cv_analysis import CVAnalysis
from ...domain.models.candidate import Candidate
from ...domain.ports.cv_analyzer_port import CVAnalyzerPort, FileType
from ...domain.ports.vector_search_port import VectorSearchPort
from ...domain.ports.candidate_repository_port import CandidateRepositoryPort
from ...domain.ports.cv_analysis_repository_port import CVAnalysisRepositoryPort

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
        candidate_repository_port: CandidateRepositoryPort,
        cv_analysis_repository_port: CVAnalysisRepositoryPort,
    ):
        """Initialize use case with required ports.

        Args:
            cv_analyzer: CV analysis service
            vector_search: Vector database service
        """
        self.cv_analyzer = cv_analyzer
        self.vector_search = vector_search
        self.candidate_repository_port = candidate_repository_port
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

        extracted_text = cv_analysis.extracted_text
        # print(extracted_text)

        # TODO: replace with data from User Service
        candidate = Candidate(
            id=candidate_id,
            name="Hardcoded Candidate",
            email="hardcoded@example.com",
            cv_file_path=None,  # No file path stored
        )

        try:
            if not await self.candidate_repository_port.get_by_id(candidate_id=candidate.id):
                await self.candidate_repository_port.save(candidate)
            await self.cv_analysis_repository_port.save(cv_analysis)
        except Exception as e:
            print("Error saving candidate: ", e)

        return cv_analysis
