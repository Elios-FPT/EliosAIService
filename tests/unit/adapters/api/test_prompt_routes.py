"""Unit tests for prompt management API routes."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from src.adapters.api.rest.prompt_routes import router
from src.application.dto.prompt_dto import PromptTemplateResponse
from src.domain.models.prompt_template import PromptTemplate
from src.infrastructure.dependency_injection.container import Container

# Create test client
from fastapi import FastAPI

app = FastAPI()
app.include_router(router)
client = TestClient(app)


@pytest.fixture
def mock_container():
    """Mock container with prompt repository."""
    container = MagicMock(spec=Container)
    mock_repo = AsyncMock()
    container.prompt_repository_port.return_value = mock_repo
    return container, mock_repo


@pytest.fixture
def sample_prompt():
    """Sample prompt template for testing."""
    from decimal import Decimal
    from datetime import datetime

    return PromptTemplate(
        id=uuid4(),
        prompt_name="test_prompt",
        version=1,
        is_active=False,
        traffic_percentage=0,
        system_prompt="System message",
        user_template="User template",
        input_variables=["var1"],
        partial_variables={},
        output_parser_type="json_output_parser",
        output_schema={},
        temperature=Decimal("0.7"),
        max_tokens=1000,
        top_p=Decimal("0.9"),
        frequency_penalty=Decimal("0.0"),
        presence_penalty=Decimal("0.0"),
        created_at=datetime.utcnow(),
    )


class TestCreateInitialPrompt:
    """Test POST /prompts endpoint."""

    @patch("src.adapters.api.rest.prompt_routes.get_container")
    @patch("src.adapters.api.rest.prompt_routes.get_async_session")
    def test_create_initial_prompt_success(self, mock_session, mock_get_container, sample_prompt, mock_container):
        """Test successful prompt creation."""
        container, mock_repo = mock_container
        mock_get_container.return_value = container
        mock_repo.create_initial_prompt.return_value = sample_prompt

        response = client.post(
            "/prompts",
            json={
                "prompt_name": "test_prompt",
                "system_prompt": "System message",
                "user_template": "User template",
                "input_variables": ["var1"],
                "temperature": 0.7,
                "max_tokens": 1000,
                "top_p": 0.9,
                "frequency_penalty": 0.0,
                "presence_penalty": 0.0,
                "created_by": "admin",
            },
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["prompt_name"] == "test_prompt"
        assert data["version"] == 1

    @patch("src.adapters.api.rest.prompt_routes.get_container")
    @patch("src.adapters.api.rest.prompt_routes.get_async_session")
    def test_create_initial_prompt_duplicate(self, mock_session, mock_get_container, mock_container):
        """Test creating duplicate prompt returns 400."""
        container, mock_repo = mock_container
        mock_get_container.return_value = container
        mock_repo.create_initial_prompt.side_effect = ValueError("Prompt 'test_prompt' already exists")

        response = client.post(
            "/prompts",
            json={
                "prompt_name": "test_prompt",
                "system_prompt": "System",
                "user_template": "User",
                "temperature": 0.7,
                "max_tokens": 1000,
                "top_p": 0.9,
                "frequency_penalty": 0.0,
                "presence_penalty": 0.0,
                "created_by": "admin",
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_initial_prompt_validation_error(self):
        """Test validation error for invalid temperature."""
        response = client.post(
            "/prompts",
            json={
                "prompt_name": "test",
                "system_prompt": "System",
                "user_template": "User",
                "temperature": 3.0,  # Invalid (> 2.0)
                "max_tokens": 1000,
                "top_p": 0.9,
                "frequency_penalty": 0.0,
                "presence_penalty": 0.0,
                "created_by": "admin",
            },
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestGetPromptById:
    """Test GET /prompts/{prompt_id} endpoint."""

    @patch("src.adapters.api.rest.prompt_routes.get_container")
    @patch("src.adapters.api.rest.prompt_routes.get_async_session")
    def test_get_prompt_by_id_success(self, mock_session, mock_get_container, sample_prompt, mock_container):
        """Test successful prompt retrieval."""
        container, mock_repo = mock_container
        mock_get_container.return_value = container
        mock_repo.get_by_id.return_value = sample_prompt

        response = client.get(f"/prompts/{sample_prompt.id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == str(sample_prompt.id)

    @patch("src.adapters.api.rest.prompt_routes.get_container")
    @patch("src.adapters.api.rest.prompt_routes.get_async_session")
    def test_get_prompt_by_id_not_found(self, mock_session, mock_get_container, mock_container):
        """Test 404 when prompt not found."""
        container, mock_repo = mock_container
        mock_get_container.return_value = container
        mock_repo.get_by_id.return_value = None

        prompt_id = uuid4()
        response = client.get(f"/prompts/{prompt_id}")

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestActivatePrompt:
    """Test PATCH /prompts/{prompt_id}/activate endpoint."""

    @patch("src.adapters.api.rest.prompt_routes.get_container")
    @patch("src.adapters.api.rest.prompt_routes.get_async_session")
    def test_activate_prompt_success(self, mock_session, mock_get_container, sample_prompt, mock_container):
        """Test successful activation."""
        container, mock_repo = mock_container
        mock_get_container.return_value = container
        mock_repo.get_by_id.return_value = sample_prompt
        mock_repo.activate_version.return_value = None

        response = client.patch(
            f"/prompts/{sample_prompt.id}/activate",
            json={
                "changed_by": "admin",
                "reason": "Deploy to production",
                "traffic_percentage": 100,
            },
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT

    @patch("src.adapters.api.rest.prompt_routes.get_container")
    @patch("src.adapters.api.rest.prompt_routes.get_async_session")
    def test_activate_prompt_not_found(self, mock_session, mock_get_container, mock_container):
        """Test 404 when prompt not found."""
        container, mock_repo = mock_container
        mock_get_container.return_value = container
        mock_repo.get_by_id.return_value = None

        prompt_id = uuid4()
        response = client.patch(
            f"/prompts/{prompt_id}/activate",
            json={
                "changed_by": "admin",
                "reason": "test",
                "traffic_percentage": 100,
            },
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

