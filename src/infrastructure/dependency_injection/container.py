"""Dependency injection container.

This module wires up all dependencies and provides them to the application.
It's the only place that knows about concrete implementations.
"""

# ruff: noqa: E402, I001

import asyncio
import logging
import re
from datetime import datetime
from typing import TYPE_CHECKING

def debug_print(msg: str):
    """Helper function to print debug messages with timestamps."""
    print(f"DEBUG [{datetime.now().strftime('%H:%M:%S.%f')[:-3]}]: {msg}", flush=True)


logger = logging.getLogger(__name__)

debug_print("container.py: Starting imports...")

from contextlib import asynccontextmanager
from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncSession

# Import adapters
debug_print("container.py: About to import LLM adapters...")
from ...adapters.llm.langchain_adapter import LangChainAdapter
debug_print("container.py: LangChainAdapter imported")

# Import mock adapters
debug_print("container.py: About to import mock adapters...")
from ...adapters.mock import MockVectorSearchAdapter
debug_print("container.py: Mock adapters imported")

# Import persistence adapters
debug_print("container.py: About to import persistence adapters...")
from ...adapters.persistence import (
    PostgreSQLAnswerRepository,
    PostgreSQLCVAnalysisRepository,
    PostgreSQLEvaluationRepository,
    PostgreSQLFollowUpQuestionRepository,
    PostgreSQLInterviewRepository,
    PostgreSQLPromptRepository,
    PostgreSQLQuestionRepository,
    PostgresFeedbackRequestRepository,
    PostgresFeedbackResponseRepository,
    SessionProvider,
)
debug_print("container.py: Persistence adapters imported")

debug_print("container.py: About to import vector_db adapters...")
from ...adapters.vector_db.pinecone_adapter import PineconeAdapter
debug_print("container.py: PineconeAdapter imported")

debug_print("container.py: About to import CV processing adapters...")
from ...adapters.cv_processing.hybrid_cv_analyzer_adapter import HybridCVAnalyzerAdapter
debug_print("container.py: HybridCVAnalyzerAdapter imported")

debug_print("container.py: About to import messaging adapters...")
from ...adapters.messaging import KafkaEventPublisher
debug_print("container.py: KafkaEventPublisher imported")

debug_print("container.py: About to import domain ports...")
from ...domain.ports import (
    AnswerRepositoryPort,
    CVAnalysisRepositoryPort,
    CVAnalyzerPort,
    EvaluationRepositoryPort,
    EventPublisherPort,
    FollowUpQuestionRepositoryPort,
    InterviewRepositoryPort,
    LLMPort,
    PromptRepositoryPort,
    QuestionRepositoryPort,
    SpeechToTextPort,
    TextToSpeechPort,
    VectorSearchPort,
)
from ...domain.ports.feedback_repository_port import (
    FeedbackRequestRepositoryPort,
    FeedbackResponseRepositoryPort,
)
debug_print("container.py: Domain ports imported")

debug_print("container.py: About to import settings...")
from ...infrastructure.config.settings import Settings, get_settings
from ...infrastructure.database import session_scope
from ...application.use_cases.list_interview_history import ListInterviewHistoryUseCase
from ...infrastructure.background.checkpointer_heartbeat import (
    HeartbeatHandle,
    start_checkpointer_heartbeat,
)
debug_print("container.py: Settings imported")

if TYPE_CHECKING:
    from ...adapters.messaging.candidate_event_consumer import CandidateEventConsumer
    from ...application.use_cases.analyze_feedback import AnalyzeFeedbackUseCase

debug_print("container.py: All imports completed, defining Container class...")


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
        self._checkpointer_heartbeat: HeartbeatHandle | None = None
        self._event_publisher: EventPublisherPort | None = None
        self._default_session_provider: SessionProvider | None = None

    def _resolve_session_provider(
        self,
        session: AsyncSession | None = None,
        session_provider: SessionProvider | None = None,
    ) -> SessionProvider:
        """Return a session provider based on explicit provider or session."""
        if session_provider is not None:
            return session_provider
        if session is not None:
            @asynccontextmanager
            async def _provider():
                try:
                    yield session
                except Exception:
                    await session.rollback()
                    raise

            return _provider
        if self._default_session_provider is None:
            self._default_session_provider = session_scope
        return self._default_session_provider

    def llm_port(self, session: AsyncSession | None = None) -> LLMPort:
        """Get LLM port implementation.

        Args:
            session: Optional database session for injecting prompt repository.
                If provided and using LangChain adapter, prompt repository will be injected.

        Returns:
            Configured LLM port based on settings

        Raises:
            ValueError: If LLM provider is not supported or not configured
        """
        # If a session is provided, build a fresh instance that can use a session-scoped prompt repo.
        if session is not None:
            if self.settings.llm_provider == "openai":
                prompt_repo = self.prompt_repository_port(session=session)
                return self._create_langchain_adapter(prompt_repository=prompt_repo)

            raise ValueError(f"Unsupported LLM provider: {self.settings.llm_provider}")

        # No session → use cached singleton instance.
        if self._llm_port is None:
            if self.settings.llm_provider == "openai":
                prompt_repo = self.prompt_repository_port()
                self._llm_port = self._create_langchain_adapter(prompt_repository=prompt_repo)
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
            else:
                raise ValueError(
                    f"Unsupported vector DB provider: {self.settings.vector_db_provider}"
                )

        return self._vector_search_port

    def question_repository_port(
        self,
        session: AsyncSession | None = None,
        session_provider: SessionProvider | None = None,
    ) -> QuestionRepositoryPort:
        """Get question repository port implementation.

        Args:
            session: Async database session

        Returns:
            Configured question repository
        """
        provider = self._resolve_session_provider(session=session, session_provider=session_provider)
        return PostgreSQLQuestionRepository(provider)

    def follow_up_question_repository_port(
        self,
        session: AsyncSession | None = None,
        session_provider: SessionProvider | None = None,
    ) -> FollowUpQuestionRepositoryPort:
        """Get follow-up question repository port implementation.

        Args:
            session: Async database session

        Returns:
            Configured follow-up question repository
        """
        provider = self._resolve_session_provider(session=session, session_provider=session_provider)
        return PostgreSQLFollowUpQuestionRepository(provider)

    def interview_repository_port(
        self,
        session: AsyncSession | None = None,
        session_provider: SessionProvider | None = None,
    ) -> InterviewRepositoryPort:
        """Get interview repository port implementation.

        Args:
            session: Async database session

        Returns:
            Configured interview repository
        """
        provider = self._resolve_session_provider(session=session, session_provider=session_provider)
        return PostgreSQLInterviewRepository(provider)

    def list_interview_history_use_case(
        self,
        session: AsyncSession | None = None,
        session_provider: SessionProvider | None = None,
    ) -> ListInterviewHistoryUseCase:
        """Get configured ListInterviewHistoryUseCase."""

        interview_repo = self.interview_repository_port(
            session=session,
            session_provider=session_provider,
        )
        return ListInterviewHistoryUseCase(interview_repository=interview_repo)

    def answer_repository_port(
        self,
        session: AsyncSession | None = None,
        session_provider: SessionProvider | None = None,
    ) -> AnswerRepositoryPort:
        """Get answer repository port implementation.

        Args:
            session: Async database session

        Returns:
            Configured answer repository
        """
        provider = self._resolve_session_provider(session=session, session_provider=session_provider)
        return PostgreSQLAnswerRepository(provider)

    def evaluation_repository_port(
        self,
        session: AsyncSession | None = None,
        session_provider: SessionProvider | None = None,
    ) -> EvaluationRepositoryPort:
        """Get evaluation repository port implementation.

        Args:
            session: Async database session

        Returns:
            Configured evaluation repository
        """
        provider = self._resolve_session_provider(session=session, session_provider=session_provider)
        return PostgreSQLEvaluationRepository(provider)

    def prompt_repository_port(
        self,
        session: AsyncSession | None = None,
        session_provider: SessionProvider | None = None,
    ) -> PromptRepositoryPort:
        """Get prompt repository port implementation.

        Args:
            session: Async database session

        Returns:
            Configured prompt repository
        """
        provider = self._resolve_session_provider(session=session, session_provider=session_provider)
        return PostgreSQLPromptRepository(provider)

    def cv_analysis_repository_port(
        self,
        session: AsyncSession | None = None,
        session_provider: SessionProvider | None = None,
    ) -> CVAnalysisRepositoryPort:
        """Get CV analysis repository port implementation.

        Args:
            session: Async database session

        Returns:
            Configured CV analysis repository
        """
        provider = self._resolve_session_provider(session=session, session_provider=session_provider)
        return PostgreSQLCVAnalysisRepository(provider)

    def feedback_request_repository_port(
        self,
        session: AsyncSession | None = None,
        session_provider: SessionProvider | None = None,
    ) -> FeedbackRequestRepositoryPort:
        """Get feedback request repository port implementation.

        Args:
            session: Async database session
            session_provider: Optional session provider

        Returns:
            Configured feedback request repository
        """
        provider = self._resolve_session_provider(session=session, session_provider=session_provider)
        return PostgresFeedbackRequestRepository(session_provider=provider)

    def feedback_response_repository_port(
        self,
        session: AsyncSession | None = None,
        session_provider: SessionProvider | None = None,
    ) -> FeedbackResponseRepositoryPort:
        """Get feedback response repository port implementation.

        Args:
            session: Async database session
            session_provider: Optional session provider

        Returns:
            Configured feedback response repository
        """
        provider = self._resolve_session_provider(session=session, session_provider=session_provider)
        return PostgresFeedbackResponseRepository(session_provider=provider)

    def cv_analyzer_port(self) -> CVAnalyzerPort:
        """Get CV analyzer port implementation.

        Returns:
            Hybrid CV analyzer implementation.
        """
        return HybridCVAnalyzerAdapter(
            confidence_threshold=self.settings.hybrid_confidence_threshold,
            use_llm_fallback=self.settings.hybrid_enable_llm_fallback,
        )


    def speech_to_text_port(self) -> SpeechToTextPort:
        """Get speech-to-text port implementation.

        Returns:
            Configured STT service

        Raises:
            ValueError: If Google Cloud Speech config is not configured
        """
        if self._stt_port is None:
            from ...adapters.speech.google_chirp3_stt_adapter import GoogleChirp3STTAdapter

            if not self.settings.google_cloud_project_id:
                raise ValueError("Google Cloud project ID not configured")

            self._stt_port = GoogleChirp3STTAdapter(
                project_id=self.settings.google_cloud_project_id,
                credentials_path=self.settings.google_application_credentials,
                model=self.settings.google_stt_model,
                language=self.settings.google_stt_language,
            )

        return self._stt_port

    def text_to_speech_port(self) -> TextToSpeechPort:
        """Get text-to-speech port implementation.

        Returns:
            Configured TTS service

        Raises:
            ValueError: If Google Cloud Speech config is not configured
        """
        if self._tts_port is None:
            from ...adapters.speech.google_chirp3_tts_adapter import GoogleChirp3TTSAdapter

            if not self.settings.google_cloud_project_id:
                raise ValueError("Google Cloud project ID not configured")

            self._tts_port = GoogleChirp3TTSAdapter(
                project_id=self.settings.google_cloud_project_id,
                credentials_path=self.settings.google_application_credentials,
                voice_name=self.settings.google_tts_voice_name,
            )

        return self._tts_port

    def event_publisher_port(self) -> EventPublisherPort:
        """Get event publisher port implementation.

        Returns:
            Configured event publisher (Kafka or Mock)

        Note:
            Kafka adapter must be started via start_event_publisher().
            Mock adapter does not require start/stop.
        """
        if self._event_publisher is None:
            self._event_publisher = KafkaEventPublisher(
                bootstrap_servers=self.settings.kafka_bootstrap_servers,
                interview_topic=self.settings.kafka_interview_topic,
                feedback_topic=self.settings.kafka_feedback_topic,
                token_topic=self.settings.kafka_token_topic,
            )

        return self._event_publisher

    async def start_event_publisher(self) -> None:
        """Start event publisher (call in FastAPI lifespan startup).

        Only starts Kafka producer (Mock has no start/stop).

        Raises:
            Exception: If Kafka producer fails to start
        """
        publisher = self.event_publisher_port()

        # Only Kafka adapter has start() method
        if isinstance(publisher, KafkaEventPublisher):
            await publisher.start()

    async def stop_event_publisher(self) -> None:
        """Stop event publisher (call in FastAPI lifespan shutdown).

        Flushes pending Kafka messages before stopping.
        """
        if self._event_publisher is None:
            return

        # Only Kafka adapter has stop() method
        if isinstance(self._event_publisher, KafkaEventPublisher):
            await self._event_publisher.stop()

    def candidate_event_consumer(self) -> "CandidateEventConsumer":
        """Get candidate event consumer.

        Returns:
            Configured Kafka consumer for candidate events
        """
        from ...adapters.messaging.candidate_event_consumer import CandidateEventConsumer

        return CandidateEventConsumer(
            bootstrap_servers=self.settings.kafka_bootstrap_servers,
            topic=self.settings.kafka_candidate_topic,
            group_id=self.settings.kafka_candidate_consumer_group,
            interview_repo=self.interview_repository_port(),
            cv_analysis_repo=self.cv_analysis_repository_port(),
        )

    async def start_tts_adapter(self) -> None:
        """Pre-initialize TTS adapter at startup to eliminate first-use delay.

        This method:
        1. Triggers TTS adapter initialization (creates Google Cloud client)
        2. Optionally pre-warms with test synthesis (validates connection)
        3. Handles errors gracefully (non-blocking, logs warnings)

        Note:
            - Non-blocking: Startup continues even if TTS init fails
            - TTS will be created lazily on first use if startup init fails
            - Pre-warming is optional (can be disabled via settings)
        """
        try:
            # Trigger initialization by calling text_to_speech_port()
            tts = self.text_to_speech_port()

            # Optional: Pre-warm with test synthesis (validates connection)
            try:
                # Pre-warm with minimal text (validates Google Cloud connection)
                await tts.synthesize_speech("test", speed=1.0)
                logger.info("TTS adapter pre-warmed successfully")
            except Exception as prewarm_exc:
                # Pre-warm failure is non-critical (adapter still initialized)
                logger.warning(
                    f"TTS pre-warm failed (adapter still initialized): {prewarm_exc}. "
                    "First TTS call may be slower."
                )

        except Exception as exc:
            # Non-blocking: Log warning but don't fail startup
            # TTS will be created lazily on first use
            logger.warning(
                f"Failed to initialize TTS adapter at startup: {exc}. "
                "TTS adapter will be created lazily on first request. "
                "This may cause a delay (~12s) on the first TTS call.",
                exc_info=True
            )

    def _create_langchain_adapter(
        self, prompt_repository: PromptRepositoryPort | None = None
    ) -> LangChainAdapter:
        """Create LangChain adapter with configured model.

        Args:
            prompt_repository: Optional prompt repository for DB-managed prompts

        Returns:
            Configured LangChain adapter

        Raises:
            ValueError: If API keys not configured
        """
        # Import LangChain models
        from langchain_openai import ChatOpenAI, AzureChatOpenAI
        from langchain_anthropic import ChatAnthropic

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

        # No callbacks (LangSmith removed)
        callbacks = []

        return LangChainAdapter(
            model=model, callbacks=callbacks, prompt_repository=prompt_repository
        )

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

        Connection Pool Management:
            AsyncPostgresSaver creates its own connection pool separate from
            SQLAlchemy's pool. Total database connections:

            - SQLAlchemy: 10 base + 20 overflow = up to 30 connections (production)
            - AsyncPostgresSaver: ~5-10 connections (internal, not configurable)
            - Total: ~35-40 connections

            Ensure PostgreSQL max_connections is configured appropriately (100+ recommended).
            The langgraph_checkpointer_pool_size setting is available for future use
            if LangGraph adds pool configuration support.
        """
        if self._checkpointer is None:
            if self.settings.langgraph_checkpointer_type != "postgresql":
                raise ValueError(
                    f"Unsupported checkpointer type: {self.settings.langgraph_checkpointer_type}"
                )

            # Import here to avoid circular dependency
            from ..database.langgraph_checkpointer import create_checkpointer

            # Get connection string (AsyncPostgresSaver uses its own connection pool)
            # Note: Pool size cannot be configured via AsyncPostgresSaver API.
            # The langgraph_checkpointer_pool_size setting is reserved for future use.
            conn_string = self.settings.async_database_url
            timeout = self.settings.langgraph_checkpointer_setup_timeout

            # Create and setup checkpointer with configurable timeout
            self._checkpointer = await create_checkpointer(conn_string, timeout=timeout)
            self._log_checkpointer_diagnostics(
                conn_string,
                getattr(self._checkpointer, "endpoint_type", "unknown"),
            )
            await self._start_checkpointer_heartbeat(self._checkpointer)

        return self._checkpointer

    async def create_interview_conversation_workflow(
        self,
        session: AsyncSession | None = None,
        session_provider: SessionProvider | None = None,
    ):
        """Create InterviewConversationWorkflow with all dependencies.

        Args:
            session: Optional AsyncSession for request-scoped workflows
            session_provider: Optional provider override

        Returns:
            Configured InterviewConversationWorkflow instance

        Note:
            This is async due to checkpointer initialization.
            Replaces session_orchestrator with stateful workflow.
        """
        from ...application.workflows.interview_conversation_workflow import InterviewConversationWorkflow

        # Get checkpointer
        checkpointer = await self.get_checkpointer()

        # Get all required ports
        interview_repo = self.interview_repository_port(session=session, session_provider=session_provider)
        question_repo = self.question_repository_port(session=session, session_provider=session_provider)
        answer_repo = self.answer_repository_port(session=session, session_provider=session_provider)
        evaluation_repo = self.evaluation_repository_port(session=session, session_provider=session_provider)
        followup_repo = self.follow_up_question_repository_port(session=session, session_provider=session_provider)
        llm = self.llm_port(session=session)
        event_publisher = self.event_publisher_port()

        # Create and return workflow
        return InterviewConversationWorkflow(
            checkpointer=checkpointer,
            interview_repo=interview_repo,
            question_repo=question_repo,
            answer_repo=answer_repo,
            evaluation_repo=evaluation_repo,
            followup_repo=followup_repo,
            llm=llm,
            event_publisher=event_publisher,
        )

    def _log_checkpointer_diagnostics(self, conn_string: str, endpoint_type: str) -> None:
        """Log masked diagnostics for operators."""
        masked_conn = re.sub(r":([^:@]+)@", ":***@", conn_string)
        logger.info(
            "LangGraph checkpointer diagnostics",
            extra={
                "event": "checkpointer_diagnostics",
                "endpoint_type": endpoint_type,
                "db_pool_recycle_seconds": self.settings.db_pool_recycle_seconds,
                "db_pool_size": self.settings.db_pool_size,
                "db_max_overflow": self.settings.db_max_overflow,
                "connection_string": masked_conn,
            },
        )

    async def _start_checkpointer_heartbeat(self, checkpointer) -> None:
        """Start heartbeat loop (enabled by default)."""
        if self._checkpointer_heartbeat:
            return

        async def ping():
            # alist() requires config parameter with thread_id
            # alist() returns async generator, consume one item to verify connection
            config = {"configurable": {"thread_id": "__heartbeat__"}}
            async for _ in checkpointer.alist(config, limit=1):
                break  # Just need to verify connection works

        interval = max(1, self.settings.langgraph_checkpointer_heartbeat_interval_seconds)
        self._checkpointer_heartbeat = await start_checkpointer_heartbeat(ping, interval)
        logger.info(
            "LangGraph checkpointer heartbeat started",
            extra={
                "event": "checkpointer_heartbeat_started",
                "interval_seconds": interval,
            },
        )

    async def stop_checkpointer_heartbeat(self) -> None:
        """Stop heartbeat loop if running."""
        if self._checkpointer_heartbeat:
            await self._checkpointer_heartbeat.stop()
            self._checkpointer_heartbeat = None
            logger.info("LangGraph checkpointer heartbeat stopped")

    async def ensure_checkpointer_alive(self) -> None:
        """Ensure checkpointer connection is alive before workflow execution."""
        checkpointer = await self.get_checkpointer()
        timeout = max(1.0, float(self.settings.langgraph_checkpointer_ensure_timeout_seconds))
        max_attempts = 2
        last_exc: Exception | None = None

        for attempt in range(1, max_attempts + 1):
            try:
                # alist() requires config parameter with thread_id
                # alist() returns async generator, consume one item to verify connection
                config = {"configurable": {"thread_id": "__health_check__"}}
                async def consume_one():
                    async for _ in checkpointer.alist(config, limit=1):
                        break  # Just need to verify connection works
                await asyncio.wait_for(consume_one(), timeout=timeout)
                if attempt > 1:
                    logger.info("Checkpointer ensure alive succeeded after retry")
                return
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "Checkpointer ensure alive attempt %s failed: %s",
                    attempt,
                    exc,
                )
                if attempt < max_attempts:
                    await self._start_checkpointer_heartbeat(checkpointer)
                    await asyncio.sleep(0)
                    continue
                break

        if last_exc:
            logger.error(
                "Checkpointer ensure alive failed after retries: %s",
                last_exc,
                extra={"event": "checkpointer_ensure_failed"},
            )
            raise last_exc

    def analyze_feedback_use_case(
        self, session: AsyncSession | None = None
    ) -> "AnalyzeFeedbackUseCase":
        """Get AnalyzeFeedbackUseCase with all dependencies.

        Args:
            session: Optional database session

        Returns:
            Configured AnalyzeFeedbackUseCase
        """
        from ...application.use_cases.analyze_feedback import AnalyzeFeedbackUseCase
        from ...application.use_cases.complete_interview import CompleteInterviewUseCase

        # Get repositories
        request_repo = self.feedback_request_repository_port(session=session)
        response_repo = self.feedback_response_repository_port(session=session)
        interview_repo = self.interview_repository_port(session=session)
        cv_analysis_repo = self.cv_analysis_repository_port(session=session)

        # Create CompleteInterviewUseCase for interview analysis
        complete_interview_use_case = CompleteInterviewUseCase(
            interview_repository=interview_repo,
            answer_repository=self.answer_repository_port(session=session),
            question_repository=self.question_repository_port(session=session),
            follow_up_question_repository=self.follow_up_question_repository_port(
                session=session
            ),
            evaluation_repository=self.evaluation_repository_port(session=session),
            llm=self.llm_port(session=session),
            event_publisher=self.event_publisher_port(),
        )

        return AnalyzeFeedbackUseCase(
            request_repo=request_repo,
            response_repo=response_repo,
            event_publisher=self.event_publisher_port(),
            interview_repo=interview_repo,
            cv_analysis_repo=cv_analysis_repo,
            complete_interview_use_case=complete_interview_use_case,
        )


@lru_cache
def get_container() -> Container:
    """Get cached container instance.

    Returns:
        Container instance with all dependencies configured
    """
    settings = get_settings()
    return Container(settings)
