"""Dependency injection container.

This module wires up all dependencies and provides them to the application.
It's the only place that knows about concrete implementations.
"""

from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncSession

# Import adapters
from ...adapters.llm.azure_openai_adapter import AzureOpenAIAdapter
from ...adapters.llm.openai_adapter import OpenAIAdapter
from ...adapters.llm.langchain_adapter import LangChainAdapter

# Import mock adapters
from ...adapters.mock import (
    MockAnalyticsAdapter,
    MockCVAnalyzerAdapter,
    MockLLMAdapter,
    MockSTTAdapter,
    MockTTSAdapter,
    MockVectorSearchAdapter,
)

# Import persistence adapters
from ...adapters.persistence import (
    PostgreSQLAnswerRepository,
    PostgreSQLCandidateRepository,
    PostgreSQLCVAnalysisRepository,
    PostgreSQLEvaluationRepository,
    PostgreSQLFollowUpQuestionRepository,
    PostgreSQLInterviewRepository,
    PostgreSQLQuestionRepository,
)
from ...adapters.vector_db.pinecone_adapter import PineconeAdapter
from ...adapters.vector_db.chroma_adapter import ChromaAdapter
from ...adapters.cv_processing.cv_processing_adapter import CVProcessingAdapter
from ...adapters.cv_processing.hybrid_cv_analyzer_adapter import HybridCVAnalyzerAdapter
from ...domain.ports import (
    AnalyticsPort,
    AnswerRepositoryPort,
    CandidateRepositoryPort,
    CVAnalysisRepositoryPort,
    CVAnalyzerPort,
    EvaluationRepositoryPort,
    FollowUpQuestionRepositoryPort,
    InterviewRepositoryPort,
    LLMPort,
    QuestionRepositoryPort,
    SpeechToTextPort,
    TextToSpeechPort,
    VectorSearchPort,
)
from ...infrastructure.config.settings import Settings, get_settings


class Container:
    """Dependency injection container.

    This class is responsible for creating and managing all dependencies.
    It follows the dependency inversion principle by depending on ports
    (interfaces) while providing concrete implementations.
    """

    def __init__(self, settings: Settings):
        """Initialize container with settings.

        Args:
            settings: Application settings
        """
        self.settings = settings
        self._llm_port: LLMPort | None = None
        self._vector_search_port: VectorSearchPort | None = None
        self._stt_port: SpeechToTextPort | None = None
        self._tts_port: TextToSpeechPort | None = None
        self._checkpointer = None  # LangGraph checkpointer (lazy init)

    def llm_port(self) -> LLMPort:
        """Get LLM port implementation.

        Returns:
            Configured LLM port based on settings

        Raises:
            ValueError: If LLM provider is not supported or not configured
        """
        if self._llm_port is None:
            # Use mock adapter if configured
            if self.settings.use_mock_llm:
                self._llm_port = MockLLMAdapter()
            # Use LangChain adapter if feature flag enabled
            elif self.settings.use_langchain:
                self._llm_port = self._create_langchain_adapter()
            elif self.settings.llm_provider == "openai":
                # Check if using Azure OpenAI
                if self.settings.use_azure_openai:
                    if not self.settings.azure_openai_api_key:
                        raise ValueError("Azure OpenAI API key not configured")
                    if not self.settings.azure_openai_endpoint:
                        raise ValueError("Azure OpenAI endpoint not configured")
                    if not self.settings.azure_openai_deployment_name:
                        raise ValueError("Azure OpenAI deployment name not configured")

                    self._llm_port = AzureOpenAIAdapter(
                        api_key=self.settings.azure_openai_api_key,
                        azure_endpoint=self.settings.azure_openai_endpoint,
                        api_version=self.settings.azure_openai_api_version,
                        deployment_name=self.settings.azure_openai_deployment_name,
                        temperature=self.settings.openai_temperature,
                    )
                else:
                    # Standard OpenAI
                    if not self.settings.openai_api_key:
                        raise ValueError("OpenAI API key not configured")

                    self._llm_port = OpenAIAdapter(
                        api_key=self.settings.openai_api_key,
                        model=self.settings.openai_model,
                        temperature=self.settings.openai_temperature,
                    )
            elif self.settings.llm_provider == "claude":
                if not self.settings.anthropic_api_key:
                    raise ValueError("Anthropic API key not configured")

                # Import Claude adapter when implemented
                # from ...adapters.llm.claude_adapter import ClaudeAdapter
                # self._llm_port = ClaudeAdapter(
                #     api_key=self.settings.anthropic_api_key,
                #     model=self.settings.anthropic_model,
                # )
                raise NotImplementedError("Claude adapter not yet implemented")
            else:
                raise ValueError(f"Unsupported LLM provider: {self.settings.llm_provider}")

        return self._llm_port

    def vector_search_port(self) -> VectorSearchPort:
        """Get vector search port implementation.

        Returns:
            Configured vector search port based on settings

        Raises:
            ValueError: If vector DB provider is not supported or not configured
        """
        if self._vector_search_port is None:
            # Use mock adapter if configured
            if self.settings.use_mock_vector_search:
                self._vector_search_port = MockVectorSearchAdapter()
            elif self.settings.vector_db_provider == "pinecone":
                if not self.settings.pinecone_api_key:
                    raise ValueError("Pinecone API key not configured")
                if not self.settings.openai_api_key:
                    raise ValueError("OpenAI API key required for embeddings")

                self._vector_search_port = PineconeAdapter(
                    api_key=self.settings.pinecone_api_key,
                    environment=self.settings.pinecone_environment,
                    index_name=self.settings.pinecone_index_name,
                    openai_api_key=self.settings.openai_api_key,
                )
            elif self.settings.vector_db_provider == "weaviate":
                # Import Weaviate adapter when implemented
                # from ...adapters.vector_db.weaviate_adapter import WeaviateAdapter
                # self._vector_search_port = WeaviateAdapter(...)
                raise NotImplementedError("Weaviate adapter not yet implemented")
            elif self.settings.vector_db_provider == "chroma":
                self._vector_search_port = ChromaAdapter()
                # raise NotImplementedError("ChromaDB adapter not yet implemented")
            else:
                raise ValueError(
                    f"Unsupported vector DB provider: {self.settings.vector_db_provider}"
                )

        return self._vector_search_port

    def question_repository_port(self, session: AsyncSession) -> QuestionRepositoryPort:
        """Get question repository port implementation.

        Args:
            session: Async database session

        Returns:
            Configured question repository
        """
        return PostgreSQLQuestionRepository(session)

    def follow_up_question_repository(
        self, session: AsyncSession
    ) -> FollowUpQuestionRepositoryPort:
        """Get follow-up question repository port implementation.

        Args:
            session: Async database session

        Returns:
            Configured follow-up question repository
        """
        return PostgreSQLFollowUpQuestionRepository(session)

    def contcandidate_repository_port(self, session: AsyncSession) -> CandidateRepositoryPort:
        """Get candidate repository port implementation.

        Args:
            session: Async database session

        Returns:
            Configured candidate repository
        """
        return PostgreSQLCandidateRepository(session)

    def interview_repository_port(self, session: AsyncSession) -> InterviewRepositoryPort:
        """Get interview repository port implementation.

        Args:
            session: Async database session

        Returns:
            Configured interview repository
        """
        return PostgreSQLInterviewRepository(session)

    def answer_repository_port(self, session: AsyncSession) -> AnswerRepositoryPort:
        """Get answer repository port implementation.

        Args:
            session: Async database session

        Returns:
            Configured answer repository
        """
        return PostgreSQLAnswerRepository(session)

    def evaluation_repository_port(
        self, session: AsyncSession
    ) -> EvaluationRepositoryPort:
        """Get evaluation repository port implementation.

        Args:
            session: Async database session

        Returns:
            Configured evaluation repository
        """
        return PostgreSQLEvaluationRepository(session)

    def cv_analysis_repository_port(
        self, session: AsyncSession
    ) -> CVAnalysisRepositoryPort:
        """Get CV analysis repository port implementation.

        Args:
            session: Async database session

        Returns:
            Configured CV analysis repository
        """
        return PostgreSQLCVAnalysisRepository(session)

    def cv_analyzer_port(self) -> CVAnalyzerPort:
        """Get CV analyzer port implementation.

        Returns:
            Configured CV analyzer (mock, hybrid, or legacy)

        Priority:
        1. Mock adapter (if use_mock_cv_analyzer=True)
        2. Hybrid adapter (if use_hybrid_cv_analyzer=True)
        3. Legacy adapter (CVProcessingAdapter)
        """
        if self.settings.use_mock_cv_analyzer:
            return MockCVAnalyzerAdapter()
        elif self.settings.use_hybrid_cv_analyzer:
            # Hybrid adapter with configurable threshold and LLM fallback
            return HybridCVAnalyzerAdapter(
                confidence_threshold=self.settings.hybrid_confidence_threshold,
                use_llm_fallback=self.settings.hybrid_enable_llm_fallback,
            )
        else:
            # Legacy adapter (default for backward compatibility)
            return CVProcessingAdapter()


    def speech_to_text_port(self) -> SpeechToTextPort:
        """Get speech-to-text port implementation.

        Returns:
            Configured STT service

        Raises:
            ValueError: If Azure Speech API key or region is not configured
        """
        if self._stt_port is None:
            # Use mock adapter if configured
            if self.settings.use_mock_stt:
                self._stt_port = MockSTTAdapter()
            else:
                # Use Azure Speech SDK
                from ...adapters.speech.azure_stt_adapter import AzureSpeechToTextAdapter

                if not self.settings.azure_speech_key:
                    raise ValueError("Azure Speech API key not configured")
                if not self.settings.azure_speech_region:
                    raise ValueError("Azure Speech region not configured")

                self._stt_port = AzureSpeechToTextAdapter(
                    api_key=self.settings.azure_speech_key,
                    region=self.settings.azure_speech_region,
                    language=self.settings.azure_speech_language,
                )

        return self._stt_port

    def text_to_speech_port(self) -> TextToSpeechPort:
        """Get text-to-speech port implementation.

        Returns:
            Configured TTS service

        Raises:
            ValueError: If Azure Speech API key or region is not configured
        """
        if self._tts_port is None:
            # Use mock adapter if configured
            if self.settings.use_mock_tts:
                self._tts_port = MockTTSAdapter()
            else:
                # Use Azure Speech SDK
                from ...adapters.speech.azure_tts_adapter import AzureTTSAdapter

                if not self.settings.azure_speech_key:
                    raise ValueError("Azure Speech API key not configured")
                if not self.settings.azure_speech_region:
                    raise ValueError("Azure Speech region not configured")

                self._tts_port = AzureTTSAdapter(
                    subscription_key=self.settings.azure_speech_key,
                    region=self.settings.azure_speech_region,
                    default_voice=self.settings.azure_speech_voice,
                )

        return self._tts_port

    def analytics_port(self) -> AnalyticsPort:
        """Get analytics port implementation.

        Returns:
            Configured analytics service

        Raises:
            NotImplementedError: Real implementation pending
        """
        if self.settings.use_mock_analytics:
            return MockAnalyticsAdapter()
        else:
            # TODO: Implement real analytics service
            # from ...adapters.analytics.analytics_adapter import AnalyticsAdapter
            # return AnalyticsAdapter(database_url=self.settings.database_url)
            raise NotImplementedError("Real analytics adapter not yet implemented")

    def _create_langchain_adapter(self) -> LangChainAdapter:
        """Create LangChain adapter with configured model.

        Returns:
            Configured LangChain adapter

        Raises:
            ValueError: If API keys not configured
        """
        # Import LangChain models
        from langchain_openai import ChatOpenAI, AzureChatOpenAI
        from langchain_anthropic import ChatAnthropic
        from ..observability.langsmith_config import create_pii_filtering_callback

        # Configure LangSmith tracing if enabled
        if self.settings.enable_langsmith:
            import os
            os.environ["LANGCHAIN_TRACING_V2"] = "true"
            if self.settings.langsmith_api_key:
                os.environ["LANGCHAIN_API_KEY"] = self.settings.langsmith_api_key
            os.environ["LANGCHAIN_PROJECT"] = self.settings.langchain_project

        # Create primary model (OpenAI or Azure OpenAI)
        primary_model = None
        if self.settings.use_azure_openai:
            if not self.settings.azure_openai_api_key:
                raise ValueError("Azure OpenAI API key not configured for LangChain")
            if not self.settings.azure_openai_endpoint:
                raise ValueError("Azure OpenAI endpoint not configured for LangChain")

            primary_model = AzureChatOpenAI(
                azure_endpoint=self.settings.azure_openai_endpoint,
                azure_deployment=self.settings.azure_openai_deployment_name,
                api_version=self.settings.azure_openai_api_version,
                api_key=self.settings.azure_openai_api_key,
                temperature=self.settings.langchain_temperature,
                max_tokens=self.settings.langchain_max_tokens,
            )
        else:
            if not self.settings.openai_api_key:
                raise ValueError("OpenAI API key not configured for LangChain")

            primary_model = ChatOpenAI(
                api_key=self.settings.openai_api_key,
                model=self.settings.openai_model,
                temperature=self.settings.langchain_temperature,
                max_tokens=self.settings.langchain_max_tokens,
            )

        # Add fallback model if enabled
        if self.settings.langchain_enable_fallback:
            if self.settings.langchain_fallback_provider == "anthropic":
                if not self.settings.anthropic_api_key:
                    raise ValueError("Anthropic API key required for fallback but not configured")

                fallback_model = ChatAnthropic(
                    api_key=self.settings.anthropic_api_key,
                    model=self.settings.anthropic_model,
                    temperature=self.settings.langchain_temperature,
                    max_tokens=self.settings.langchain_max_tokens,
                )

                # Create model with fallback
                model = primary_model.with_fallbacks([fallback_model])
            else:
                raise ValueError(f"Unsupported fallback provider: {self.settings.langchain_fallback_provider}")
        else:
            model = primary_model

        # Create callbacks (includes PII filtering tracer if enabled)
        callbacks = create_pii_filtering_callback(self.settings)

        return LangChainAdapter(model=model, callbacks=callbacks)

    async def get_checkpointer(self):
        """Get LangGraph checkpointer for workflow state persistence.

        Returns:
            AsyncPostgresSaver instance

        Raises:
            ValueError: If checkpointer type is not supported
            Exception: If checkpointer setup fails

        Note:
            This is async and must be called with await.
            Checkpointer is lazy-initialized on first access.
        """
        if self._checkpointer is None:
            if self.settings.langgraph_checkpointer_type != "postgresql":
                raise ValueError(
                    f"Unsupported checkpointer type: {self.settings.langgraph_checkpointer_type}"
                )

            # Import here to avoid circular dependency
            from ..database.session import get_async_engine
            from ..database.langgraph_checkpointer import create_checkpointer

            # Get async engine (reuses existing connection pool)
            engine = get_async_engine()

            # Create and setup checkpointer
            self._checkpointer = await create_checkpointer(engine)

        return self._checkpointer

    async def create_adaptive_eval_simple_workflow(self, session: AsyncSession):
        """Create AdaptiveEvalSimpleWorkflow with all dependencies.

        Args:
            session: Async database session

        Returns:
            Configured AdaptiveEvalSimpleWorkflow instance

        Note:
            This is async due to checkpointer initialization.
        """
        from ...application.workflows.adaptive_eval_simple_workflow import AdaptiveEvalSimpleWorkflow

        # Get checkpointer
        checkpointer = await self.get_checkpointer()

        # Get all required ports
        answer_repo = self.answer_repository_port(session)
        evaluation_repo = self.evaluation_repository_port(session)
        interview_repo = self.interview_repository_port(session)
        question_repo = self.question_repository_port(session)
        follow_up_repo = self.follow_up_question_repository(session)
        llm = self.llm_port()

        # Create and return workflow
        return AdaptiveEvalSimpleWorkflow(
            checkpointer=checkpointer,
            answer_repo=answer_repo,
            evaluation_repo=evaluation_repo,
            interview_repo=interview_repo,
            question_repo=question_repo,
            follow_up_repo=follow_up_repo,
            llm=llm,
        )

    async def create_adaptive_eval_interrupt_workflow(self, session: AsyncSession):
        """Create AdaptiveEvalInterruptWorkflow with all dependencies (Phase 3B).

        Args:
            session: Async database session

        Returns:
            Configured AdaptiveEvalInterruptWorkflow instance

        Note:
            This is async due to checkpointer initialization.
            Phase 3B workflow includes WebSocket interrupts and loop-back logic.
        """
        from ...application.workflows.adaptive_eval_interrupt_workflow import AdaptiveEvalInterruptWorkflow

        # Get checkpointer
        checkpointer = await self.get_checkpointer()

        # Get all required ports (same as Phase 3A)
        answer_repo = self.answer_repository_port(session)
        evaluation_repo = self.evaluation_repository_port(session)
        interview_repo = self.interview_repository_port(session)
        question_repo = self.question_repository_port(session)
        follow_up_repo = self.follow_up_question_repository(session)
        llm = self.llm_port()

        # Create and return workflow
        return AdaptiveEvalInterruptWorkflow(
            checkpointer=checkpointer,
            answer_repo=answer_repo,
            evaluation_repo=evaluation_repo,
            interview_repo=interview_repo,
            question_repo=question_repo,
            follow_up_repo=follow_up_repo,
            llm=llm,
        )


@lru_cache
def get_container() -> Container:
    """Get cached container instance.

    Returns:
        Container instance with all dependencies configured
    """
    settings = get_settings()
    return Container(settings)
