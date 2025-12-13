"""Unit tests for LangChainAdapter helper methods.

Tests DB prompt loading, execution logging, and metadata extraction helpers.
"""

import time
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from langchain_core.language_models import BaseChatModel

from src.infrastructure.adapters.llm.langchain_adapter import LangChainAdapter
from src.domain.models.prompt_template import PromptTemplate


@pytest.fixture
def mock_chat_model():
    """Create a mock LangChain chat model."""
    model = MagicMock(spec=BaseChatModel)
    model.model_name = "gpt-4"
    return model


@pytest.fixture
def mock_prompt_repo():
    """Create a mock PromptRepositoryPort."""
    repo = AsyncMock()
    return repo


@pytest.fixture
def sample_prompt_template():
    """Create a sample PromptTemplate for testing."""
    return PromptTemplate(
        id=uuid4(),
        name="test_prompt",
        version=2,
        template_json={
            "system": "You are a helpful assistant.",
            "user_template": "Answer: {question}",
            "variables": ["question"],
        },
        is_active=True,
        is_draft=False,
        created_by="test",
    )


class TestLoadPromptFromDb:
    """Test _load_prompt_from_db() helper method."""

    @pytest.mark.asyncio
    async def test_load_prompt_from_db_success(
        self, mock_chat_model, mock_prompt_repo, sample_prompt_template
    ):
        """Test successful DB prompt loading."""
        mock_prompt_repo.get_active_prompt.return_value = sample_prompt_template

        adapter = LangChainAdapter(model=mock_chat_model, prompt_repository=mock_prompt_repo)
        prompt_template, template_json, cache_key = await adapter._load_prompt_from_db(
            "test_prompt"
        )

        assert prompt_template == sample_prompt_template
        assert template_json == sample_prompt_template.template_json
        assert cache_key == "test_prompt:v2"
        mock_prompt_repo.get_active_prompt.assert_called_once_with("test_prompt")

    @pytest.mark.asyncio
    async def test_load_prompt_from_db_not_found(self, mock_chat_model, mock_prompt_repo):
        """Test DB prompt not found (fallback)."""
        mock_prompt_repo.get_active_prompt.return_value = None

        adapter = LangChainAdapter(model=mock_chat_model, prompt_repository=mock_prompt_repo)
        prompt_template, template_json, cache_key = await adapter._load_prompt_from_db(
            "missing_prompt"
        )

        assert prompt_template is None
        assert template_json is None
        assert cache_key is None
        mock_prompt_repo.get_active_prompt.assert_called_once_with("missing_prompt")

    @pytest.mark.asyncio
    async def test_load_prompt_from_db_exception(self, mock_chat_model, mock_prompt_repo):
        """Test DB exception (fallback)."""
        mock_prompt_repo.get_active_prompt.side_effect = Exception("DB connection failed")

        adapter = LangChainAdapter(model=mock_chat_model, prompt_repository=mock_prompt_repo)
        prompt_template, template_json, cache_key = await adapter._load_prompt_from_db(
            "test_prompt"
        )

        assert prompt_template is None  # Fallback
        assert template_json is None
        assert cache_key is None
        mock_prompt_repo.get_active_prompt.assert_called_once_with("test_prompt")

    @pytest.mark.asyncio
    async def test_load_prompt_from_db_no_repository(self, mock_chat_model):
        """Test fallback when prompt_repo is None."""
        adapter = LangChainAdapter(model=mock_chat_model, prompt_repository=None)
        prompt_template, template_json, cache_key = await adapter._load_prompt_from_db(
            "test_prompt"
        )

        assert prompt_template is None
        assert template_json is None
        assert cache_key is None


class TestLogExecution:
    """Test _log_execution() helper method."""

    @pytest.mark.asyncio
    async def test_log_execution_success(
        self, mock_chat_model, mock_prompt_repo, sample_prompt_template
    ):
        """Test execution logging with token extraction."""
        adapter = LangChainAdapter(model=mock_chat_model, prompt_repository=mock_prompt_repo)

        metadata = {
            "usage": {
                "total_tokens": 150,
                "prompt_tokens": 100,
                "completion_tokens": 50,
            }
        }

        start_time = time.time() - 1.5  # 1.5s ago

        await adapter._log_execution(
            prompt_template=sample_prompt_template,
            context={"interview_id": "test-123", "candidate_id": "cand-456"},
            input_variables={"question": "What is Python?"},
            output_text="Python is a programming language...",
            start_time=start_time,
            success=True,
            model_response_metadata=metadata,
        )

        # Verify log_execution called with correct data
        mock_prompt_repo.log_execution.assert_called_once()
        call_args = mock_prompt_repo.log_execution.call_args
        assert call_args[1]["prompt_template_id"] == sample_prompt_template.id

        execution_data = call_args[1]["execution_data"]
        assert execution_data["tokens_used"] == 150
        assert execution_data["prompt_tokens"] == 100
        assert execution_data["completion_tokens"] == 50
        assert execution_data["latency_ms"] >= 1500  # ~1.5s
        assert execution_data["success"] is True
        assert execution_data["interview_id"] == "test-123"
        assert execution_data["candidate_id"] == "cand-456"
        assert execution_data["model_name"] == "gpt-4"

    @pytest.mark.asyncio
    async def test_log_execution_no_metadata(
        self, mock_chat_model, mock_prompt_repo, sample_prompt_template
    ):
        """Test execution logging without token metadata."""
        adapter = LangChainAdapter(model=mock_chat_model, prompt_repository=mock_prompt_repo)

        start_time = time.time() - 0.5  # 0.5s ago

        await adapter._log_execution(
            prompt_template=sample_prompt_template,
            context={},
            input_variables={"question": "Test"},
            output_text="Output",
            start_time=start_time,
            success=True,
            model_response_metadata=None,
        )

        execution_data = mock_prompt_repo.log_execution.call_args[1]["execution_data"]
        assert execution_data["tokens_used"] is None
        assert execution_data["prompt_tokens"] is None
        assert execution_data["completion_tokens"] is None
        assert execution_data["success"] is True

    @pytest.mark.asyncio
    async def test_log_execution_failure(
        self, mock_chat_model, mock_prompt_repo, sample_prompt_template
    ):
        """Test execution logging for failed execution."""
        adapter = LangChainAdapter(model=mock_chat_model, prompt_repository=mock_prompt_repo)

        start_time = time.time() - 0.2

        await adapter._log_execution(
            prompt_template=sample_prompt_template,
            context={},
            input_variables={"question": "Test"},
            output_text=None,
            start_time=start_time,
            success=False,
            error_message="LLM timeout",
        )

        execution_data = mock_prompt_repo.log_execution.call_args[1]["execution_data"]
        assert execution_data["success"] is False
        assert execution_data["error_message"] == "LLM timeout"
        assert execution_data["output_text"] is None

    @pytest.mark.asyncio
    async def test_log_execution_logging_fails_gracefully(
        self, mock_chat_model, mock_prompt_repo, sample_prompt_template
    ):
        """Test that logging failures don't break the main operation."""
        mock_prompt_repo.log_execution.side_effect = Exception("DB error")

        adapter = LangChainAdapter(model=mock_chat_model, prompt_repository=mock_prompt_repo)

        # Should not raise exception
        await adapter._log_execution(
            prompt_template=sample_prompt_template,
            context={},
            input_variables={},
            output_text="Test",
            start_time=time.time(),
            success=True,
        )

        # Verify it was called (even though it failed)
        mock_prompt_repo.log_execution.assert_called_once()


class TestExtractResponseMetadata:
    """Test _extract_response_metadata() helper method."""

    def test_extract_response_metadata_dict(self, mock_chat_model):
        """Test metadata extraction from dict response."""
        adapter = LangChainAdapter(model=mock_chat_model)

        response = {
            "output": "test",
            "_metadata": {
                "usage": {
                    "total_tokens": 100,
                    "prompt_tokens": 60,
                    "completion_tokens": 40,
                }
            },
        }

        metadata = adapter._extract_response_metadata(response)

        assert metadata == response["_metadata"]

    def test_extract_response_metadata_aimessage(self, mock_chat_model):
        """Test metadata extraction from AIMessage response."""
        adapter = LangChainAdapter(model=mock_chat_model)

        # Mock AIMessage-like object
        class MockAIMessage:
            def __init__(self):
                self.response_metadata = {
                    "usage": {"total_tokens": 200},
                    "model": "gpt-4",
                }

        response = MockAIMessage()
        metadata = adapter._extract_response_metadata(response)

        assert metadata == response.response_metadata

    def test_extract_response_metadata_usage_metadata(self, mock_chat_model):
        """Test metadata extraction from newer LangChain version."""
        adapter = LangChainAdapter(model=mock_chat_model)

        # Mock object with usage_metadata
        class MockResponse:
            def __init__(self):
                self.usage_metadata = {
                    "input_tokens": 50,
                    "output_tokens": 30,
                }

        response = MockResponse()
        metadata = adapter._extract_response_metadata(response)

        assert metadata == {"usage": response.usage_metadata}

    def test_extract_response_metadata_none(self, mock_chat_model):
        """Test metadata extraction when unavailable."""
        adapter = LangChainAdapter(model=mock_chat_model)

        response = {"output": "test"}  # No metadata

        metadata = adapter._extract_response_metadata(response)

        assert metadata is None

    def test_extract_response_metadata_empty_dict(self, mock_chat_model):
        """Test metadata extraction from dict without _metadata key."""
        adapter = LangChainAdapter(model=mock_chat_model)

        response = {"output": "test", "other_field": "value"}

        metadata = adapter._extract_response_metadata(response)

        assert metadata is None
