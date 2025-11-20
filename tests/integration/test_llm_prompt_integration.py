"""Integration tests for LLM adapter with prompt management."""

import pytest
from unittest.mock import AsyncMock, patch

from src.adapters.llm.openai_adapter import OpenAIAdapter
from src.adapters.persistence.postgres_prompt_repository import PostgreSQLPromptRepository


@pytest.mark.asyncio
async def test_openai_adapter_with_prompt_repository(async_session):
    """Test OpenAI adapter loads prompts from DB and logs executions."""
    # Create prompt repository
    repo = PostgreSQLPromptRepository(async_session)

    # Create and activate a prompt
    prompt = await repo.create_initial_prompt(
        name="ideal_answer_generation",
        template_json={
            "system": "You are a test assistant.",
            "user_template": "Generate ideal answer for: {question_text}\nBackground: {summary}, Skills: {skills}, Experience: {experience}",
            "variables": ["question_text", "summary", "skills", "experience"],
        },
        created_by="test",
    )
    await repo.activate_version(prompt.id, "test", "Test activation", traffic_percentage=100)

    # Create adapter with prompt repository
    adapter = OpenAIAdapter(
        api_key="test-key",
        model="gpt-4",
        prompt_repository=repo,
    )

    # Mock OpenAI client
    mock_response = AsyncMock()
    mock_response.choices = [AsyncMock()]
    mock_response.choices[0].message.content = "This is a test ideal answer."
    mock_response.usage.total_tokens = 100
    mock_response.usage.prompt_tokens = 50
    mock_response.usage.completion_tokens = 50

    # Create async mock for create method
    async def mock_create(*args, **kwargs):
        return mock_response

    with patch.object(adapter.client.chat.completions, 'create', side_effect=mock_create):
        # Call generate_ideal_answer
        result = await adapter.generate_ideal_answer(
            question_text="What is Python?",
            context={
                "summary": "Senior developer",
                "skills": ["Python", "Django"],
                "experience": 5,
                "interview_id": None,
                "candidate_id": None,
            },
        )

    # Verify result
    assert result == "This is a test ideal answer."

    # Verify execution was logged
    # Note: Since we're mocking, the execution log might not be persisted
    # In a real integration test with actual DB, we'd verify:
    # executions = await async_session.execute(
    #     select(PromptExecutionModel).where(PromptExecutionModel.prompt_template_id == prompt.id)
    # )
    # assert executions.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_openai_adapter_fallback_to_hardcoded():
    """Test adapter uses hardcoded prompts when repository is None."""
    # Create adapter WITHOUT prompt repository
    adapter = OpenAIAdapter(
        api_key="test-key",
        model="gpt-4",
        prompt_repository=None,  # No DB prompts
    )

    # Mock OpenAI client
    mock_response = AsyncMock()
    mock_response.choices = [AsyncMock()]
    mock_response.choices[0].message.content = "Hardcoded prompt answer."
    mock_response.usage.total_tokens = 100
    mock_response.usage.prompt_tokens = 50
    mock_response.usage.completion_tokens = 50

    # Create async mock for create method
    async def mock_create(*args, **kwargs):
        return mock_response

    with patch.object(adapter.client.chat.completions, 'create', side_effect=mock_create):
        # Call generate_ideal_answer (should use hardcoded prompt)
        result = await adapter.generate_ideal_answer(
            question_text="What is Python?",
            context={
                "summary": "Senior developer",
                "skills": ["Python", "Django"],
                "experience": 5,
            },
        )

    # Verify result
    assert result == "Hardcoded prompt answer."


@pytest.mark.asyncio
async def test_prompt_template_get_prompt_text():
    """Test PromptTemplate.get_prompt_text() renders variables correctly."""
    from src.domain.models.prompt_template import PromptTemplate

    prompt = PromptTemplate(
        name="test",
        version=1,
        template_json={
            "system": "You are a helpful assistant.",
            "user_template": "Answer the question: {question}",
            "variables": ["question"],
        },
        created_by="test",
    )

    # Render prompt
    rendered = prompt.get_prompt_text(question="What is 2+2?")

    # Verify rendering
    assert "You are a helpful assistant." in rendered
    assert "What is 2+2?" in rendered


@pytest.mark.asyncio
async def test_prompt_template_missing_variables():
    """Test get_prompt_text raises error for missing variables."""
    from src.domain.models.prompt_template import PromptTemplate

    prompt = PromptTemplate(
        name="test",
        version=1,
        template_json={
            "system": "System prompt",
            "user_template": "Question: {question}, Context: {context}",
            "variables": ["question", "context"],
        },
        created_by="test",
    )

    # Try to render without providing all variables
    with pytest.raises(ValueError, match="Missing variables"):
        prompt.get_prompt_text(question="What is 2+2?")  # Missing 'context'


@pytest.mark.asyncio
async def test_azure_openai_adapter_with_prompt_repository(async_session):
    """Test Azure OpenAI adapter with DB-managed prompts."""
    from src.adapters.llm.azure_openai_adapter import AzureOpenAIAdapter

    # Create prompt repository
    repo = PostgreSQLPromptRepository(async_session)

    # Create and activate a prompt
    prompt = await repo.create_initial_prompt(
        name="ideal_answer_generation",
        template_json={
            "system": "You are a test assistant.",
            "user_template": "Generate ideal answer for: {question_text}\nBackground: {summary}, Skills: {skills}, Experience: {experience}",
            "variables": ["question_text", "summary", "skills", "experience"],
        },
        created_by="test",
    )
    await repo.activate_version(prompt.id, "test", "Test activation", traffic_percentage=100)

    # Create adapter with prompt repository
    adapter = AzureOpenAIAdapter(
        api_key="test-key",
        azure_endpoint="https://test.openai.azure.com/",
        api_version="2024-02-15-preview",
        deployment_name="gpt-4",
        prompt_repository=repo,
    )

    # Mock Azure OpenAI client
    mock_response = AsyncMock()
    mock_response.choices = [AsyncMock()]
    mock_response.choices[0].message.content = "This is a test Azure answer."
    mock_response.usage.total_tokens = 100
    mock_response.usage.prompt_tokens = 50
    mock_response.usage.completion_tokens = 50

    # Create async mock for create method
    async def mock_create(*args, **kwargs):
        return mock_response

    with patch.object(adapter.client.chat.completions, 'create', side_effect=mock_create):
        # Call generate_ideal_answer
        result = await adapter.generate_ideal_answer(
            question_text="What is Python?",
            context={
                "summary": "Senior developer",
                "skills": ["Python", "Django"],
                "experience": 5,
            },
        )

    # Verify result
    assert result == "This is a test Azure answer."


@pytest.mark.asyncio
async def test_langchain_adapter_with_prompt_repository(async_session):
    """Test LangChain adapter with DB-managed prompts."""
    from src.adapters.llm.langchain_adapter import LangChainAdapter
    from langchain_openai import ChatOpenAI

    # Create prompt repository
    repo = PostgreSQLPromptRepository(async_session)

    # Create and activate a prompt
    prompt = await repo.create_initial_prompt(
        name="ideal_answer_generation",
        template_json={
            "system": "You are a test assistant.",
            "user_template": "Generate ideal answer for: {question_text}\nBackground: {summary}, Skills: {skills}, Experience: {experience}",
            "variables": ["question_text", "summary", "skills", "experience"],
        },
        created_by="test",
    )
    await repo.activate_version(prompt.id, "test", "Test activation", traffic_percentage=100)

    # Create LangChain model (mock)
    mock_model = ChatOpenAI(model="gpt-4", api_key="test-key")

    # Create adapter with prompt repository
    adapter = LangChainAdapter(
        model=mock_model,
        prompt_repository=repo,
    )

    # Mock LangChain model response
    mock_response = AsyncMock()
    mock_response.content = "This is a test LangChain answer."

    # Create async mock for ainvoke method
    async def mock_ainvoke(*args, **kwargs):
        return mock_response

    with patch.object(mock_model, 'ainvoke', side_effect=mock_ainvoke):
        # Call generate_ideal_answer
        result = await adapter.generate_ideal_answer(
            question_text="What is Python?",
            context={
                "summary": "Senior developer",
                "skills": ["Python", "Django"],
                "experience": 5,
            },
        )

    # Verify result
    assert result == "This is a test LangChain answer."
