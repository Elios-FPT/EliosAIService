"""Unit tests for interview caching optimization (Phase 1)."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime
from uuid import UUID, uuid4

from src.application.workflows.interview_conversation_workflow import (
    InterviewConversationWorkflow,
    ConversationState,
)
from src.domain.models.interview import Interview, InterviewStatus


@pytest.fixture
def mock_checkpointer():
    """Create mock AsyncPostgresSaver."""
    checkpointer = MagicMock()
    checkpointer.aget = AsyncMock(return_value=None)
    checkpointer.aput = AsyncMock()
    return checkpointer


@pytest.fixture
def mock_interview_repo():
    """Create mock InterviewRepositoryPort."""
    repo = MagicMock()
    return repo


@pytest.fixture
def mock_question_repo():
    """Create mock QuestionRepositoryPort."""
    repo = MagicMock()
    return repo


@pytest.fixture
def mock_answer_repo():
    """Create mock AnswerRepositoryPort."""
    repo = MagicMock()
    return repo


@pytest.fixture
def mock_evaluation_repo():
    """Create mock EvaluationRepositoryPort."""
    repo = MagicMock()
    return repo


@pytest.fixture
def mock_followup_repo():
    """Create mock FollowUpQuestionRepositoryPort."""
    repo = MagicMock()
    return repo


@pytest.fixture
def mock_llm():
    """Create mock LLMPort."""
    llm = MagicMock()
    return llm


@pytest.fixture
def mock_event_publisher():
    """Create mock EventPublisherPort."""
    publisher = MagicMock()
    return publisher


@pytest.fixture
def workflow(
    mock_checkpointer,
    mock_interview_repo,
    mock_question_repo,
    mock_answer_repo,
    mock_evaluation_repo,
    mock_followup_repo,
    mock_llm,
    mock_event_publisher,
):
    """Create InterviewConversationWorkflow instance with mocks."""
    return InterviewConversationWorkflow(
        checkpointer=mock_checkpointer,
        interview_repo=mock_interview_repo,
        question_repo=mock_question_repo,
        answer_repo=mock_answer_repo,
        evaluation_repo=mock_evaluation_repo,
        followup_repo=mock_followup_repo,
        llm=mock_llm,
        event_publisher=mock_event_publisher,
    )


@pytest.fixture
def sample_interview():
    """Create sample Interview domain object."""
    interview_id = uuid4()
    candidate_id = uuid4()
    return Interview(
        id=interview_id,
        candidate_id=candidate_id,
        status=InterviewStatus.IDLE,
        updated_at=datetime.utcnow(),
    )


@pytest.fixture
def sample_state(sample_interview):
    """Create sample ConversationState."""
    return {
        "interview_id": str(sample_interview.id),
        "candidate_id": str(sample_interview.candidate_id),
        "messages": [],
        "current_question_id": None,
        "current_question": None,
        "parent_question": None,
        "parent_question_id": None,
        "pending_answer_text": None,
        "is_voice_answer": False,
        "voice_metrics": None,
        "answers": [],
        "evaluations": [],
        "followup_count": 0,
        "cumulative_gaps": [],
        "has_more_questions": False,
        "needs_followup": False,
        "complete": False,
        "followup_reason": None,
        "summary": None,
        "final_status": None,
        "errors": [],
        "retry_count": 0,
        "checkpoint_thread_id": f"interview_{sample_interview.id}",
        "last_checkpoint_time": None,
        "_cached_interview": None,
        "_interview_version": None,
    }


class TestInterviewCaching:
    """Test suite for interview caching optimization."""

    async def test_get_or_refresh_interview_first_access(
        self, workflow, mock_interview_repo, sample_interview, sample_state
    ):
        """Test cache is populated on first access."""
        mock_interview_repo.get_by_id = AsyncMock(return_value=sample_interview)

        interview, cache_updates = await workflow._get_or_refresh_interview(
            sample_state, force_refresh=False
        )

        assert interview == sample_interview
        assert "_cached_interview" in cache_updates
        assert "_interview_version" in cache_updates
        assert cache_updates["_cached_interview"] == sample_interview.model_dump(mode="json")
        mock_interview_repo.get_by_id.assert_called_once()

    async def test_get_or_refresh_interview_cache_hit(
        self, workflow, mock_interview_repo, sample_interview, sample_state
    ):
        """Test cache is reused on subsequent access."""
        # Populate cache
        sample_state["_cached_interview"] = sample_interview.model_dump(mode="json")
        sample_state["_interview_version"] = sample_interview.updated_at.timestamp()

        interview, cache_updates = await workflow._get_or_refresh_interview(
            sample_state, force_refresh=False
        )

        assert interview.id == sample_interview.id
        assert cache_updates == {}  # No updates when cache hit
        mock_interview_repo.get_by_id.assert_not_called()

    async def test_get_or_refresh_interview_force_refresh(
        self, workflow, mock_interview_repo, sample_interview, sample_state
    ):
        """Test force refresh bypasses cache."""
        # Populate cache
        sample_state["_cached_interview"] = sample_interview.model_dump(mode="json")
        sample_state["_interview_version"] = sample_interview.updated_at.timestamp()

        # Update interview
        updated_interview = Interview(
            id=sample_interview.id,
            candidate_id=sample_interview.candidate_id,
            status=InterviewStatus.QUESTIONING,
            updated_at=datetime.utcnow(),
        )
        mock_interview_repo.get_by_id = AsyncMock(return_value=updated_interview)

        interview, cache_updates = await workflow._get_or_refresh_interview(
            sample_state, force_refresh=True
        )

        assert interview.status == InterviewStatus.QUESTIONING
        assert "_cached_interview" in cache_updates
        mock_interview_repo.get_by_id.assert_called_once()

    async def test_get_or_refresh_interview_not_found(
        self, workflow, mock_interview_repo, sample_state
    ):
        """Test error handling when interview not found."""
        mock_interview_repo.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(ValueError, match="not found"):
            await workflow._get_or_refresh_interview(sample_state, force_refresh=False)

    async def test_get_or_refresh_interview_cache_reconstruction_failure(
        self, workflow, mock_interview_repo, sample_interview, sample_state
    ):
        """Test fallback to DB when cache reconstruction fails."""
        # Invalid cache data
        sample_state["_cached_interview"] = {"invalid": "data"}
        sample_state["_interview_version"] = 1234567890.0

        mock_interview_repo.get_by_id = AsyncMock(return_value=sample_interview)

        interview, cache_updates = await workflow._get_or_refresh_interview(
            sample_state, force_refresh=False
        )

        assert interview == sample_interview
        assert "_cached_interview" in cache_updates
        mock_interview_repo.get_by_id.assert_called_once()

