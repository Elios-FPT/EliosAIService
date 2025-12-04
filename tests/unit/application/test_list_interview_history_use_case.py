"""Tests for ListInterviewHistoryUseCase."""

from datetime import datetime, timedelta
from uuid import uuid4
from unittest.mock import AsyncMock

import pytest

from src.application.use_cases.list_interview_history import ListInterviewHistoryUseCase
from src.domain.models.interview import Interview, InterviewStatus


@pytest.mark.asyncio
async def test_execute_returns_history_payload():
    repo = AsyncMock()
    candidate_id = uuid4()
    interview = Interview(
        id=uuid4(),
        candidate_id=candidate_id,
        title="System Design Prep",
        status=InterviewStatus.COMPLETE,
        cv_analysis_id=uuid4(),
        current_question_index=2,
        plan_metadata={"n": 4},
        started_at=datetime.utcnow() - timedelta(hours=1),
        completed_at=datetime.utcnow(),
        created_at=datetime.utcnow() - timedelta(days=1),
        updated_at=datetime.utcnow(),
    )
    repo.list_by_candidate_paginated.return_value = ([interview], 1)

    use_case = ListInterviewHistoryUseCase(interview_repository=repo)

    result = await use_case.execute(
        candidate_id=candidate_id,
        ws_base_url="ws://localhost:8000",
        include_active=False,
    )

    repo.list_by_candidate_paginated.assert_awaited_once()
    assert result.pagination.total == 1
    assert len(result.items) == 1
    item = result.items[0]
    assert item.ws_url.endswith(f"/ws/interviews/{interview.id}")
    assert item.question_count == interview.planned_question_count
    assert item.progress_percentage == pytest.approx(50.0)


@pytest.mark.asyncio
async def test_execute_raises_for_invalid_limit():
    repo = AsyncMock()
    use_case = ListInterviewHistoryUseCase(interview_repository=repo)

    with pytest.raises(ValueError):
        await use_case.execute(
            candidate_id=uuid4(),
            ws_base_url="ws://localhost:8000",
            limit=0,
        )

    repo.list_by_candidate_paginated.assert_not_awaited()

