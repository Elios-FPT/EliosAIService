"""Integration tests for prompt management API."""

import pytest
from fastapi.testclient import TestClient

from src.main import create_app

app = create_app()
client = TestClient(app)


@pytest.mark.asyncio
async def test_create_and_get_prompt_workflow(async_session):
    """Test complete workflow: create prompt, get by ID."""
    # Create initial prompt
    response = client.post(
        "/api/prompts",
        json={
            "prompt_name": "integration_test_prompt",
            "system_prompt": "You are a helpful assistant",
            "user_template": "Answer: {question}",
            "input_variables": ["question"],
            "temperature": 0.7,
            "max_tokens": 1000,
            "top_p": 0.9,
            "frequency_penalty": 0.0,
            "presence_penalty": 0.0,
            "created_by": "test_user",
        },
    )

    assert response.status_code == 201
    prompt_data = response.json()
    prompt_id = prompt_data["id"]

    # Get prompt by ID
    response = client.get(f"/api/prompts/{prompt_id}")
    assert response.status_code == 200
    assert response.json()["prompt_name"] == "integration_test_prompt"


@pytest.mark.asyncio
async def test_version_management_workflow(async_session):
    """Test version management: create, create version, get history."""
    # Create initial
    response = client.post(
        "/api/prompts",
        json={
            "prompt_name": "version_test",
            "system_prompt": "System v1",
            "user_template": "User v1",
            "temperature": 0.7,
            "max_tokens": 1000,
            "top_p": 0.9,
            "frequency_penalty": 0.0,
            "presence_penalty": 0.0,
            "created_by": "test",
        },
    )
    assert response.status_code == 201

    # Create version 2
    response = client.post(
        "/api/prompts/version_test/versions",
        json={
            "parent_version": 1,
            "system_prompt": "System v2",
            "user_template": "User v2",
            "change_summary": "Updated to v2",
            "temperature": 0.8,
            "max_tokens": 2000,
            "top_p": 0.95,
            "frequency_penalty": 0.0,
            "presence_penalty": 0.0,
            "created_by": "test",
        },
    )
    assert response.status_code == 201
    assert response.json()["version"] == 2

    # Get version history
    response = client.get("/api/prompts/version_test/versions")
    assert response.status_code == 200
    history = response.json()
    assert len(history) == 2
    assert history[0]["version"] == 1
    assert history[1]["version"] == 2

