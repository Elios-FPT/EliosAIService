"""Unit tests for AnalyzeFeedbackUseCase."""

import json
import pytest
from unittest.mock import AsyncMock
from uuid import uuid4

from src.application.use_cases.analyze_feedback import AnalyzeFeedbackUseCase
from src.domain.models.feedback_request import FeedbackRequest
from src.domain.models.feedback_result import (
    CVFeedbackResult,
    CodeReviewFeedbackResult,
    FeedbackStatus,
    InputType,
)
from src.domain.ports.llm_port import LLMPort


@pytest.fixture
def mock_llm():
    """Create mock LLM port."""
    return AsyncMock(spec=LLMPort)


@pytest.fixture
def mock_dependencies(mock_llm):
    """Create mock dependencies for use case."""
    return {
        "request_repo": AsyncMock(),
        "response_repo": AsyncMock(),
        "event_publisher": AsyncMock(),
        "llm": mock_llm,
    }


@pytest.fixture
def use_case(mock_dependencies):
    """Create AnalyzeFeedbackUseCase with mocked dependencies."""
    return AnalyzeFeedbackUseCase(**mock_dependencies)


@pytest.mark.asyncio
async def test_execute_success_cv(use_case, mock_dependencies, mock_llm):
    """Test successful CV analysis."""
    cv_analysis_id = uuid4()
    request_id = uuid4()
    user_id = uuid4()

    # Mock feedback_input (JSON string)
    feedback_input = json.dumps({
        "skills": ["Python", "FastAPI"],
        "summary": "5 years experience",
    })

    # Mock request creation
    mock_dependencies["request_repo"].create.return_value = FeedbackRequest(
        id=request_id,
        entity_id=cv_analysis_id,
        input_type=InputType.CV,
        status=FeedbackStatus.PENDING,
        user_id=user_id,
        feedback_input=feedback_input,
    )

    # Mock LLM response
    mock_cv_result = CVFeedbackResult(
        cv_analysis_id=cv_analysis_id,
        skills_identified=[],
        primary_skills=["Python"],
        secondary_skills=["FastAPI"],
        total_experience_years=5.0,
        work_experience_summary="5 years experience",
        education_level="Unknown",
        education_details=[],
        skill_gaps=[],
        improvement_areas=[],
        suggested_certifications=[],
        language="en",
    )
    mock_llm.analyze_feedback.return_value = mock_cv_result

    # Act
    request, result = await use_case.execute(
        entity_id=cv_analysis_id,
        input_type=InputType.CV,
        user_id=user_id,
        feedback_input=feedback_input,
    )

    # Assert
    # Note: request object returned is the original, status updates happen in repo
    assert isinstance(result, CVFeedbackResult)
    assert result.cv_analysis_id == cv_analysis_id
    mock_dependencies["request_repo"].update_status.assert_any_call(
        request_id=request_id,
        status=FeedbackStatus.PROCESSING,
    )
    mock_dependencies["request_repo"].update_status.assert_any_call(
        request_id=request_id,
        status=FeedbackStatus.SUCCESS,
    )
    mock_llm.analyze_feedback.assert_called_once()
    call_kwargs = mock_llm.analyze_feedback.call_args[1]
    assert call_kwargs["input_type"] == InputType.CV
    assert call_kwargs["feedback_input"] == feedback_input
    assert "user_id" in call_kwargs["context"]


@pytest.mark.asyncio
async def test_execute_success_code(use_case, mock_dependencies, mock_llm):
    """Test successful CODE analysis."""
    code_id = uuid4()
    request_id = uuid4()

    # Mock feedback_input (JSON string)
    feedback_input = json.dumps({
        "problem_description": "Sort array",
        "language": "python",
        "user_code_solution": "def sort(arr): return sorted(arr)",
    })

    # Mock request creation
    mock_dependencies["request_repo"].create.return_value = FeedbackRequest(
        id=request_id,
        entity_id=code_id,
        input_type=InputType.CODE,
        status=FeedbackStatus.PENDING,
        feedback_input=feedback_input,
    )

    # Mock LLM response
    mock_code_result = CodeReviewFeedbackResult(
        submission_id=str(code_id),
        code_quality_score=75.0,
        maintainability_score=80.0,
        readability_score=70.0,
        bugs_detected=[],
        security_issues=[],
        code_smells=[],
        best_practices_violations=[],
        refactoring_suggestions=[],
        performance_tips=[],
        language="python",
    )
    mock_llm.analyze_feedback.return_value = mock_code_result

    # Act
    request, result = await use_case.execute(
        entity_id=code_id,
        input_type=InputType.CODE,
        feedback_input=feedback_input,
    )

    # Assert
    # Note: request object returned is the original, status updates happen in repo
    assert isinstance(result, CodeReviewFeedbackResult)
    assert result.submission_id == str(code_id)
    mock_llm.analyze_feedback.assert_called_once_with(
        input_type=InputType.CODE,
        feedback_input=feedback_input,
        context={"user_id": None, "entity_id": str(code_id), "request_id": str(request_id)},
    )


@pytest.mark.asyncio
async def test_execute_rejects_interview(use_case):
    """Test that INTERVIEW type is rejected."""
    interview_id = uuid4()
    feedback_input = json.dumps({"interview_id": str(interview_id)})

    # Act & Assert
    with pytest.raises(ValueError, match="INTERVIEW feedback analysis is not supported"):
        await use_case.execute(
            entity_id=interview_id,
            input_type=InputType.INTERVIEW,
            feedback_input=feedback_input,
        )


@pytest.mark.asyncio
async def test_execute_requires_feedback_input(use_case):
    """Test that feedback_input is required."""
    cv_id = uuid4()

    # Act & Assert
    with pytest.raises(ValueError, match="feedback_input is required"):
        await use_case.execute(
            entity_id=cv_id,
            input_type=InputType.CV,
            feedback_input=None,
        )


@pytest.mark.asyncio
async def test_execute_handles_llm_failure(use_case, mock_dependencies, mock_llm):
    """Test that LLM failures are handled (fail fast)."""
    cv_id = uuid4()
    request_id = uuid4()
    feedback_input = json.dumps({"skills": ["Python"]})

    # Mock request creation
    mock_dependencies["request_repo"].create.return_value = FeedbackRequest(
        id=request_id,
        entity_id=cv_id,
        input_type=InputType.CV,
        status=FeedbackStatus.PENDING,
        feedback_input=feedback_input,
    )

    # Mock LLM failure
    mock_llm.analyze_feedback.side_effect = RuntimeError("LLM service unavailable")

    # Act & Assert
    with pytest.raises(RuntimeError, match="LLM service unavailable"):
        await use_case.execute(
            entity_id=cv_id,
            input_type=InputType.CV,
            feedback_input=feedback_input,
        )

    # Verify request marked as failed
    mock_dependencies["request_repo"].update_status.assert_any_call(
        request_id=request_id,
        status=FeedbackStatus.PROCESSING,
    )
    mock_dependencies["request_repo"].update_status.assert_any_call(
        request_id=request_id,
        status=FeedbackStatus.FAILED,
        error_message="LLM service unavailable",
    )


@pytest.mark.asyncio
async def test_execute_publishes_event(use_case, mock_dependencies, mock_llm):
    """Test that FEEDBACK_COMPLETED event is published."""
    cv_id = uuid4()
    request_id = uuid4()
    user_id = uuid4()
    feedback_input = json.dumps({"skills": ["Python"]})

    # Mock request creation
    mock_dependencies["request_repo"].create.return_value = FeedbackRequest(
        id=request_id,
        entity_id=cv_id,
        input_type=InputType.CV,
        status=FeedbackStatus.PENDING,
        user_id=user_id,
        feedback_input=feedback_input,
    )

    # Mock LLM response
    mock_cv_result = CVFeedbackResult(
        cv_analysis_id=cv_id,
        skills_identified=[],
        primary_skills=[],
        secondary_skills=[],
        total_experience_years=0.0,
        work_experience_summary="",
        education_level="Unknown",
        education_details=[],
        skill_gaps=[],
        improvement_areas=[],
        suggested_certifications=[],
        language="en",
    )
    mock_llm.analyze_feedback.return_value = mock_cv_result

    # Act
    await use_case.execute(
        entity_id=cv_id,
        input_type=InputType.CV,
        user_id=user_id,
        feedback_input=feedback_input,
    )

    # Assert event published
    mock_dependencies["event_publisher"].publish_feedback_completed.assert_called_once()
    call_kwargs = mock_dependencies["event_publisher"].publish_feedback_completed.call_args[1]
    assert call_kwargs["request_id"] == request_id
    assert call_kwargs["entity_id"] == cv_id
    assert call_kwargs["input_type"] == InputType.CV.value
    assert call_kwargs["user_id"] == user_id
    assert call_kwargs["result"] == mock_cv_result


@pytest.mark.asyncio
async def test_execute_event_publish_failure_does_not_fail_use_case(
    use_case, mock_dependencies, mock_llm
):
    """Test that event publish failure doesn't fail the use case."""
    cv_id = uuid4()
    request_id = uuid4()
    feedback_input = json.dumps({"skills": ["Python"]})

    # Mock request creation
    mock_dependencies["request_repo"].create.return_value = FeedbackRequest(
        id=request_id,
        entity_id=cv_id,
        input_type=InputType.CV,
        status=FeedbackStatus.PENDING,
        feedback_input=feedback_input,
    )

    # Mock LLM response
    mock_cv_result = CVFeedbackResult(
        cv_analysis_id=cv_id,
        skills_identified=[],
        primary_skills=[],
        secondary_skills=[],
        total_experience_years=0.0,
        work_experience_summary="",
        education_level="Unknown",
        education_details=[],
        skill_gaps=[],
        improvement_areas=[],
        suggested_certifications=[],
        language="en",
    )
    mock_llm.analyze_feedback.return_value = mock_cv_result

    # Mock event publish failure
    mock_dependencies["event_publisher"].publish_feedback_completed.side_effect = Exception(
        "Kafka unavailable"
    )

    # Act (should not raise)
    request, result = await use_case.execute(
        entity_id=cv_id,
        input_type=InputType.CV,
        feedback_input=feedback_input,
    )

    # Assert use case still succeeds (request object is original, status updates in repo)
    assert result == mock_cv_result


@pytest.mark.asyncio
async def test_list_user_feedback(use_case, mock_dependencies):
    """Test listing user feedback history."""
    user_id = uuid4()
    requests = [
        FeedbackRequest(
            id=uuid4(),
            entity_id=uuid4(),
            input_type=InputType.CV,
            user_id=user_id,
            status=FeedbackStatus.SUCCESS,
            feedback_input='{"skills": ["Python"]}',
        ),
        FeedbackRequest(
            id=uuid4(),
            entity_id=uuid4(),
            input_type=InputType.CODE,
            user_id=user_id,
            status=FeedbackStatus.SUCCESS,
            feedback_input='{"code": "def test(): pass"}',
        ),
    ]

    mock_dependencies["request_repo"].list_by_user.return_value = requests

    # Act
    result = await use_case.list_user_feedback(user_id, limit=50, offset=0)

    # Assert
    assert len(result) == 2
    assert result[0].input_type == InputType.CV
    assert result[1].input_type == InputType.CODE
    mock_dependencies["request_repo"].list_by_user.assert_called_once_with(
        user_id, 50, 0
    )
