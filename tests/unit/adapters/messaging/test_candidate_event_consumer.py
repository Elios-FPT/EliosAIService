"""Tests for candidate event consumer."""

from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from src.adapters.messaging.candidate_event_consumer import CandidateEventConsumer
from src.domain.models.candidate_event import CandidateEvent, CandidateEventPayload, EventType


@pytest.fixture
def mock_interview_repo():
    repo = Mock()
    repo.soft_delete_by_candidate_id = AsyncMock(return_value=2)
    return repo


@pytest.fixture
def mock_cv_repo():
    repo = Mock()
    repo.soft_delete_by_candidate_id = AsyncMock(return_value=1)
    return repo


@pytest.fixture
def consumer(mock_interview_repo, mock_cv_repo):
    return CandidateEventConsumer(
        bootstrap_servers="localhost:9092",
        topic="user-interview-candidate",
        group_id="test-group",
        interview_repo=mock_interview_repo,
        cv_analysis_repo=mock_cv_repo,
    )


@pytest.mark.asyncio
async def test_handle_candidate_deleted_event(consumer, mock_interview_repo, mock_cv_repo):
    """Test handling candidate.DELETED event triggers soft deletes."""
    candidate_id = uuid4()
    payload = CandidateEventPayload(UserId=candidate_id, DeletedAt="2025-12-02T00:00:00Z")
    event = CandidateEvent(
        event_type=EventType.DELETED,
        payload=payload,
    )

    await consumer._handle_candidate_deleted(event)

    mock_interview_repo.soft_delete_by_candidate_id.assert_called_once_with(candidate_id)
    mock_cv_repo.soft_delete_by_candidate_id.assert_called_once_with(candidate_id)


