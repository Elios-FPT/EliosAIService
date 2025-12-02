"""Tests for soft delete behaviour in PostgreSQLInterviewRepository."""

from uuid import uuid4

import pytest

from src.adapters.persistence.interview_repository import PostgreSQLInterviewRepository
from src.adapters.persistence.session_provider import SessionProvider
from src.domain.models.interview import Interview, InterviewStatus


@pytest.mark.asyncio
async def test_soft_delete_by_candidate_id(async_session_maker):
    """Soft deleting interviews by candidate ID should hide them from queries."""
    candidate_id = uuid4()
    interview = Interview.create_new(
        candidate_id=candidate_id,
        cv_analysis_id=None,
        status=InterviewStatus.PLANNING,
    )

    repo = PostgreSQLInterviewRepository(SessionProvider(async_session_maker))

    # Save interview
    saved = await repo.save(interview)

    # Soft delete
    deleted_count = await repo.soft_delete_by_candidate_id(candidate_id)
    assert deleted_count == 1

    # Should not be returned by get_by_id
    assert await repo.get_by_id(saved.id) is None


