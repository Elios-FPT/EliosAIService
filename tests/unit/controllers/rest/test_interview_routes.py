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
from src.infrastructure.database.session import get_async_session

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


@patch("src.controllers.rest.interview_routes.CompleteInterviewUseCase")
@patch("src.controllers.rest.interview_routes.get_container")
def test_stop_interview_success_questioning(
    mock_get_container,
    mock_complete_uc_class,
):
    """Test stop interview from QUESTIONING status."""
    # Override FastAPI dependency
    mock_session = AsyncMock()
    async def mock_get_session():
        yield mock_session
    app.dependency_overrides[get_async_session] = mock_get_session

    interview_id = uuid4()
    mock_interview = SimpleNamespace(
        id=interview_id,
        status=InterviewStatus.QUESTIONING,
    )

    mock_container = MagicMock()
    mock_get_container.return_value = mock_container

    mock_interview_repo = AsyncMock()
    mock_interview_repo.get_by_id.return_value = mock_interview
    mock_container.interview_repository_port.return_value = mock_interview_repo

    # Mock all other dependencies
    mock_container.answer_repository_port.return_value = AsyncMock()
    mock_container.question_repository_port.return_value = AsyncMock()
    mock_container.follow_up_question_repository_port.return_value = AsyncMock()
    mock_container.evaluation_repository_port.return_value = AsyncMock()
    mock_container.llm_port.return_value = MagicMock()
    mock_container.event_publisher_port.return_value = AsyncMock()

    # Mock use case instance and result
    mock_use_case_instance = AsyncMock()
    from src.application.dto.detailed_feedback_dto import DetailedInterviewFeedback
    from src.application.dto.interview_completion_dto import InterviewCompletionResult
    from src.domain.models.interview import Interview

    completed_interview = Interview(
        id=interview_id,
        candidate_id=uuid4(),
        status=InterviewStatus.COMPLETE,
    )
    from datetime import UTC, datetime
    mock_summary = DetailedInterviewFeedback(
        interview_id=interview_id,
        overall_score=75.0,
        theoretical_score_avg=80.0,
        speaking_score_avg=70.0,
        total_questions=3,
        total_follow_ups=2,
        question_feedback=[],
        gap_progression={},
        strengths=[],
        weaknesses=[],
        study_recommendations=[],
        technique_tips=[],
        completion_time=datetime.now(UTC),
    )
    mock_result = InterviewCompletionResult(
        interview=completed_interview,
        summary=mock_summary,
    )
    mock_use_case_instance.execute.return_value = mock_result
    mock_complete_uc_class.return_value = mock_use_case_instance

    try:
        response = client.put(f"/interviews/{interview_id}/stop")

        assert response.status_code == 200
        data = response.json()
        assert data["interview_id"] == str(interview_id)
        assert data["overall_score"] == 75.0
        mock_use_case_instance.execute.assert_awaited_once_with(interview_id)
    finally:
        app.dependency_overrides.clear()


@patch("src.controllers.rest.interview_routes.get_container")
def test_stop_interview_not_found(mock_get_container):
    """Test stop interview when interview not found."""
    mock_session = AsyncMock()
    async def mock_get_session():
        yield mock_session
    app.dependency_overrides[get_async_session] = mock_get_session

    interview_id = uuid4()
    mock_container = MagicMock()
    mock_get_container.return_value = mock_container

    mock_interview_repo = AsyncMock()
    mock_interview_repo.get_by_id.return_value = None
    mock_container.interview_repository_port.return_value = mock_interview_repo

    try:
        response = client.put(f"/interviews/{interview_id}/stop")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    finally:
        app.dependency_overrides.clear()


@patch("src.controllers.rest.interview_routes.get_container")
def test_stop_interview_invalid_status_complete(mock_get_container):
    """Test stop interview when interview is already COMPLETE."""
    mock_session = AsyncMock()
    async def mock_get_session():
        yield mock_session
    app.dependency_overrides[get_async_session] = mock_get_session

    interview_id = uuid4()
    mock_interview = SimpleNamespace(
        id=interview_id,
        status=InterviewStatus.COMPLETE,
    )

    mock_container = MagicMock()
    mock_get_container.return_value = mock_container

    mock_interview_repo = AsyncMock()
    mock_interview_repo.get_by_id.return_value = mock_interview
    mock_container.interview_repository_port.return_value = mock_interview_repo

    try:
        response = client.put(f"/interviews/{interview_id}/stop")

        assert response.status_code == 400
        assert "status" in response.json()["detail"].lower()
        assert "complete" in response.json()["detail"].lower()
    finally:
        app.dependency_overrides.clear()


@patch("src.controllers.rest.interview_routes.CompleteInterviewUseCase")
@patch("src.controllers.rest.interview_routes.get_container")
def test_stop_interview_use_case_error(
    mock_get_container,
    mock_complete_uc_class,
):
    """Test stop interview when use case raises error."""
    mock_session = AsyncMock()
    async def mock_get_session():
        yield mock_session
    app.dependency_overrides[get_async_session] = mock_get_session

    interview_id = uuid4()
    mock_interview = SimpleNamespace(
        id=interview_id,
        status=InterviewStatus.EVALUATING,
    )

    mock_container = MagicMock()
    mock_get_container.return_value = mock_container

    mock_interview_repo = AsyncMock()
    mock_interview_repo.get_by_id.return_value = mock_interview
    mock_container.interview_repository_port.return_value = mock_interview_repo

    # Mock all other dependencies
    mock_container.answer_repository_port.return_value = AsyncMock()
    mock_container.question_repository_port.return_value = AsyncMock()
    mock_container.follow_up_question_repository_port.return_value = AsyncMock()
    mock_container.evaluation_repository_port.return_value = AsyncMock()
    mock_container.llm_port.return_value = MagicMock()
    mock_container.event_publisher_port.return_value = AsyncMock()

    # Mock use case to raise error
    mock_use_case_instance = AsyncMock()
    mock_use_case_instance.execute.side_effect = Exception("Database error")
    mock_complete_uc_class.return_value = mock_use_case_instance

    try:
        response = client.put(f"/interviews/{interview_id}/stop")

        assert response.status_code == 500
        assert "failed" in response.json()["detail"].lower()
    finally:
        app.dependency_overrides.clear()

