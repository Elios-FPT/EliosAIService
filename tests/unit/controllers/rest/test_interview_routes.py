"""Tests for interview_routes token deduction logic."""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.controllers.rest.interview_routes import (
    router,
    _emit_token_delta_event,
)
from src.application.dto.interview_dto import (
    InterviewHistoryItemResponse,
    InterviewHistoryListResponse,
    InterviewHistoryPagination,
)
from src.domain.models.interview import InterviewStatus

app = FastAPI()
app.include_router(router)
client = TestClient(app)


@pytest.mark.asyncio
async def test_emit_token_delta_event_success():
    publisher = AsyncMock()
    user_id = uuid4()
    fake_correlation = uuid4()

    with patch("src.controllers.rest.interview_routes.uuid.uuid4", return_value=fake_correlation):
        await _emit_token_delta_event(publisher, user_id=user_id, tokens=-10)

    assert publisher.publish_token_delta.await_count == 1
    _, kwargs = publisher.publish_token_delta.await_args
    assert kwargs["user_id"] == user_id
    assert kwargs["tokens"] == -10
    assert kwargs["correlation_id"] == fake_correlation


@pytest.mark.asyncio
async def test_emit_token_delta_event_handles_failure(caplog):
    publisher = AsyncMock()
    publisher.publish_token_delta.side_effect = RuntimeError("boom")

    with caplog.at_level("WARNING"):
        await _emit_token_delta_event(publisher, user_id=uuid4(), tokens=-10)

    assert "Failed to emit token delta event" in caplog.text


@patch("src.controllers.rest.interview_routes.PlanningWorkflow")
@patch("src.controllers.rest.interview_routes.get_container")
@patch("src.controllers.rest.interview_routes.get_async_session")
def test_plan_interview_emits_token_event(
    mock_get_session,
    mock_get_container,
    mock_planning_workflow,
):
    mock_get_session.return_value = AsyncMock()

    mock_container = MagicMock()
    mock_get_container.return_value = mock_container

    mock_cv_repo = AsyncMock()
    mock_cv_repo.get_by_id.return_value = SimpleNamespace(id=uuid4())
    mock_container.cv_analysis_repository_port.return_value = mock_cv_repo
    mock_container.llm_port.return_value = MagicMock()
    mock_container.question_repository_port.return_value = MagicMock()
    mock_container.interview_repository_port.return_value = MagicMock()
    mock_container.vector_search_port.return_value = MagicMock()
    mock_container.get_checkpointer.return_value = AsyncMock(return_value=MagicMock())

    publisher = AsyncMock()
    mock_container.event_publisher_port.return_value = publisher

    interview = SimpleNamespace(
        id=uuid4(),
        status=InterviewStatus.IDLE,
        planned_question_count=3,
        plan_metadata={"foo": "bar"},
    )

    workflow_instance = MagicMock()
    workflow_instance.execute = AsyncMock(
        return_value={
            "interview": interview,
        }
    )
    mock_planning_workflow.return_value = workflow_instance

    payload = {
        "cv_analysis_id": str(uuid4()),
        "candidate_id": str(uuid4()),
    }
    response = client.post("/interviews/plan", json=payload)

    assert response.status_code == 202
    publisher.publish_token_delta.assert_awaited_once()


@patch("src.controllers.rest.interview_routes.get_container")
@patch("src.controllers.rest.interview_routes.get_async_session")
def test_list_interview_history_success(mock_get_session, mock_get_container):
    mock_get_session.return_value = AsyncMock()

    mock_container = MagicMock()
    mock_get_container.return_value = mock_container

    mock_use_case = AsyncMock()
    mock_container.list_interview_history_use_case.return_value = mock_use_case

    history_response = InterviewHistoryListResponse(
        items=[
            InterviewHistoryItemResponse(
                id=uuid4(),
                title="Mock Interview",
                status=InterviewStatus.COMPLETE.value,
                cv_analysis_id=None,
                planned_question_count=5,
                current_question_index=5,
                question_count=5,
                progress_percentage=100.0,
                ws_url="ws://localhost:8000/ws/interviews/123",
                started_at=None,
                completed_at=None,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
        ],
        pagination=InterviewHistoryPagination(limit=20, offset=0, total=1),
    )
    mock_use_case.execute.return_value = history_response

    user_id = uuid4()
    response = client.get(f"/interviews/users/{user_id}/history?limit=20&offset=0")

    assert response.status_code == 200
    assert response.json()["pagination"]["total"] == 1
    mock_use_case.execute.assert_awaited_once()


@patch("src.controllers.rest.interview_routes.get_container")
@patch("src.controllers.rest.interview_routes.get_async_session")
def test_list_interview_history_validation_error(mock_get_session, mock_get_container):
    mock_get_session.return_value = AsyncMock()

    mock_container = MagicMock()
    mock_get_container.return_value = mock_container

    mock_use_case = AsyncMock()
    mock_use_case.execute.side_effect = ValueError("limit must be between 1 and 100")
    mock_container.list_interview_history_use_case.return_value = mock_use_case

    user_id = uuid4()
    response = client.get(f"/interviews/users/{user_id}/history?limit=20")

    assert response.status_code == 400
    assert "limit" in response.json()["detail"]

