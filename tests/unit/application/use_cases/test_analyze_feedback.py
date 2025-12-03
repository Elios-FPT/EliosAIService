"""Unit tests for AnalyzeFeedbackUseCase."""

import pytest
import time
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from src.application.use_cases.analyze_feedback import (
    AnalyzeFeedbackUseCase,
    LLMTimeoutError,
    LLMMaxRetriesError,
)
from src.domain.models.feedback_request import FeedbackRequest
from src.domain.models.feedback_result import (
    CVFeedbackResult,
    FeedbackStatus,
    InputType,
    InterviewFeedbackResult,
)
from src.domain.models.interview import Interview, InterviewStatus


@pytest.fixture
def mock_dependencies():
    """Create mock dependencies for use case."""
    return {
        "request_repo": AsyncMock(),
        "response_repo": AsyncMock(),
        "event_publisher": AsyncMock(),
        "interview_repo": AsyncMock(),
        "cv_analysis_repo": AsyncMock(),
        "complete_interview_use_case": AsyncMock(),
    }


@pytest.fixture
def use_case(mock_dependencies):
    """Create AnalyzeFeedbackUseCase with mocked dependencies."""
    return AnalyzeFeedbackUseCase(**mock_dependencies)


@pytest.mark.asyncio
async def test_execute_success_interview(use_case, mock_dependencies):
    """Test successful interview analysis on first attempt."""
    interview_id = uuid4()
    request_id = uuid4()

    # Mock request creation
    mock_dependencies["request_repo"].create.return_value = FeedbackRequest(
        id=request_id,
        entity_id=interview_id,
        input_type=InputType.INTERVIEW,
        status=FeedbackStatus.PENDING,
    )

    # Mock interview in EVALUATING status (ready to be completed)
    mock_interview = Interview(
        candidate_id=uuid4(),
        status=InterviewStatus.EVALUATING,
    )
    mock_dependencies["interview_repo"].get_by_id.return_value = mock_interview

    # Mock CompleteInterviewUseCase result
    from src.application.dto.detailed_feedback_dto import DetailedInterviewFeedback
    from src.application.dto.interview_completion_dto import InterviewCompletionResult
    from datetime import datetime, UTC

    detailed_feedback = DetailedInterviewFeedback(
        interview_id=interview_id,
        overall_score=85.0,
        theoretical_score_avg=80.0,
        speaking_score_avg=60.0,
        total_questions=5,
        total_follow_ups=3,
        completion_time=datetime.now(UTC),
    )
    mock_dependencies["complete_interview_use_case"].execute.return_value = (
        InterviewCompletionResult(
            interview=mock_interview,
            summary=detailed_feedback,
        )
    )

    # Act
    request, result = await use_case.execute(
        entity_id=interview_id,
        input_type=InputType.INTERVIEW,
    )

    # Assert
    assert request.status == FeedbackStatus.SUCCESS
    assert isinstance(result, InterviewFeedbackResult)
    assert result.overall_score == 85.0
    mock_dependencies["request_repo"].update_status.assert_called_with(
        request_id=request_id,
        status=FeedbackStatus.SUCCESS,
    )


@pytest.mark.asyncio
async def test_execute_success_cv(use_case, mock_dependencies):
    """Test successful CV analysis."""
    cv_analysis_id = uuid4()
    request_id = uuid4()

    # Mock request creation
    mock_dependencies["request_repo"].create.return_value = FeedbackRequest(
        id=request_id,
        entity_id=cv_analysis_id,
        input_type=InputType.CV,
        status=FeedbackStatus.PENDING,
    )

    # Mock CV analysis
    from src.domain.models.cv_analysis import CVAnalysis

    mock_cv = CVAnalysis(
        id=cv_analysis_id,
        candidate_id=uuid4(),
        summary="5 years experience",
    )
    mock_dependencies["cv_analysis_repo"].get_by_id.return_value = mock_cv

    # Act
    request, result = await use_case.execute(
        entity_id=cv_analysis_id,
        input_type=InputType.CV,
    )

    # Assert
    assert request.status == FeedbackStatus.SUCCESS
    assert isinstance(result, CVFeedbackResult)
    assert result.cv_analysis_id == cv_analysis_id


@pytest.mark.asyncio
async def test_execute_code_not_implemented(use_case, mock_dependencies):
    """Test CODE analysis raises NotImplementedError."""
    code_id = uuid4()
    request_id = uuid4()

    mock_dependencies["request_repo"].create.return_value = FeedbackRequest(
        id=request_id,
        entity_id=code_id,
        input_type=InputType.CODE,
        status=FeedbackStatus.PENDING,
    )

    # Act & Assert
    with pytest.raises(NotImplementedError, match="CODE analysis not yet implemented"):
        await use_case.execute(
            entity_id=code_id,
            input_type=InputType.CODE,
        )

    # Verify request marked as failed
    mock_dependencies["request_repo"].update_status.assert_called_with(
        request_id=request_id,
        status=FeedbackStatus.FAILED,
        error_message=NotImplementedError("CODE analysis not yet implemented").__str__(),
    )


@pytest.mark.asyncio
async def test_analyze_with_retry_exponential_backoff(use_case, mock_dependencies):
    """Test retry with exponential backoff timing."""
    request_id = uuid4()
    interview_id = uuid4()

    # Mock interview
    mock_interview = Interview(
        candidate_id=uuid4(),
        status=InterviewStatus.EVALUATING,
    )
    mock_dependencies["interview_repo"].get_by_id.return_value = mock_interview

    # Simulate failures then success
    from src.application.dto.detailed_feedback_dto import DetailedInterviewFeedback
    from src.application.dto.interview_completion_dto import InterviewCompletionResult
    from datetime import datetime, UTC

    detailed_feedback = DetailedInterviewFeedback(
        interview_id=interview_id,
        overall_score=75.0,
        theoretical_score_avg=70.0,
        speaking_score_avg=50.0,
        total_questions=3,
        total_follow_ups=2,
        completion_time=datetime.now(UTC),
    )

    mock_dependencies["complete_interview_use_case"].execute.side_effect = [
        LLMTimeoutError("Timeout"),  # Attempt 1
        LLMTimeoutError("Timeout"),  # Attempt 2
        InterviewCompletionResult(
            interview=mock_interview,
            summary=detailed_feedback,
        ),  # Attempt 3 - success
    ]

    start = time.time()
    result = await use_case._analyze_with_retry(
        request_id=request_id,
        entity_id=interview_id,
        input_type=InputType.INTERVIEW,
        max_retries=3,
    )
    elapsed = time.time() - start

    # Verify exponential backoff: 2s + 4s = 6s minimum
    assert elapsed >= 6.0
    assert elapsed < 7.0  # Allow some variance
    assert isinstance(result, InterviewFeedbackResult)


@pytest.mark.asyncio
async def test_analyze_max_retries_exceeded(use_case, mock_dependencies):
    """Test failure after max retries."""
    request_id = uuid4()
    interview_id = uuid4()

    mock_interview = Interview(
        candidate_id=uuid4(),
        status=InterviewStatus.EVALUATING,
    )
    mock_dependencies["interview_repo"].get_by_id.return_value = mock_interview

    # Simulate all attempts failing
    mock_dependencies["complete_interview_use_case"].execute.side_effect = (
        LLMTimeoutError("Timeout")
    )

    # Act & Assert
    with pytest.raises(LLMMaxRetriesError):
        await use_case._analyze_with_retry(
            request_id=request_id,
            entity_id=interview_id,
            input_type=InputType.INTERVIEW,
            max_retries=3,
        )

    # Verify 3 attempts
    assert mock_dependencies["complete_interview_use_case"].execute.call_count == 3


@pytest.mark.asyncio
async def test_analyze_permanent_error_no_retry(use_case, mock_dependencies):
    """Test permanent error doesn't retry."""
    request_id = uuid4()
    interview_id = uuid4()

    # Simulate entity not found (permanent error)
    mock_dependencies["interview_repo"].get_by_id.return_value = None

    # Act & Assert
    with pytest.raises(ValueError, match="Interview.*not found"):
        await use_case._analyze_with_retry(
            request_id=request_id,
            entity_id=interview_id,
            input_type=InputType.INTERVIEW,
            max_retries=3,
        )

    # Verify only 1 attempt (no retry)
    assert mock_dependencies["interview_repo"].get_by_id.call_count == 1


@pytest.mark.asyncio
async def test_analyze_interview_wrong_status(use_case, mock_dependencies):
    """Test interview must be EVALUATING or COMPLETE to generate feedback."""
    interview_id = uuid4()

    # Mock interview in QUESTIONING status (not ready)
    mock_interview = Interview(
        candidate_id=uuid4(),
        status=InterviewStatus.QUESTIONING,
    )
    mock_dependencies["interview_repo"].get_by_id.return_value = mock_interview

    # Act & Assert
    with pytest.raises(ValueError, match="must be in EVALUATING or COMPLETE"):
        await use_case._analyze_interview(interview_id)


@pytest.mark.asyncio
async def test_list_user_feedback(use_case, mock_dependencies):
    """Test listing user feedback history."""
    user_id = uuid4()
    requests = [
        FeedbackRequest(
            id=uuid4(),
            entity_id=uuid4(),
            input_type=InputType.INTERVIEW,
            user_id=user_id,
            status=FeedbackStatus.SUCCESS,
        ),
        FeedbackRequest(
            id=uuid4(),
            entity_id=uuid4(),
            input_type=InputType.CV,
            user_id=user_id,
            status=FeedbackStatus.SUCCESS,
        ),
    ]

    mock_dependencies["request_repo"].list_by_user.return_value = requests

    # Act
    result = await use_case.list_user_feedback(user_id, limit=50, offset=0)

    # Assert
    assert len(result) == 2
    assert result[0].input_type == InputType.INTERVIEW
    assert result[1].input_type == InputType.CV
    mock_dependencies["request_repo"].list_by_user.assert_called_once_with(
        user_id, 50, 0
    )

