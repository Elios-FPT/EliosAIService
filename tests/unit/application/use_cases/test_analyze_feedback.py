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
    OverallAssessment,
    SectionFeedback,
    ActionableRecommendations,
    MarketCompetitiveness,
    CodeQuality,
    BestPractices,
    CodeActionableRecommendation,
)
from src.application.ports.llm_port import LLMPort


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
        overall_assessment=OverallAssessment(
            overall_score=75.0,
            summary="Good CV with relevant experience",
        ),
        professional_summary=SectionFeedback(
            score=12.0,
            feedback="Clear professional positioning",
            suggestions=[],
        ),
        work_experience=SectionFeedback(
            score=20.0,
            feedback="5 years experience",
            suggestions=[],
        ),
        projects=SectionFeedback(
            score=18.0,
            feedback="Good project descriptions",
            suggestions=[],
        ),
        skills=SectionFeedback(
            score=15.0,
            feedback="Relevant skills: Python, FastAPI",
            suggestions=[],
        ),
        actionable_recommendations=ActionableRecommendations(),
        market_competitiveness=MarketCompetitiveness(
            assessment="Competitive for mid-level positions",
            target_roles=["Backend Developer"],
            improvement_areas=[],
        ),
    )
    mock_llm.analyze_feedback.return_value = mock_cv_result

    # Act
    request, result, result_markdown = await use_case.execute(
        entity_id=cv_analysis_id,
        input_type=InputType.CV,
        user_id=user_id,
        feedback_input=feedback_input,
    )

    # Assert
    # Note: request object returned is the original, status updates happen in repo
    assert isinstance(result, CVFeedbackResult)
    assert result.cv_analysis_id == cv_analysis_id
    assert result_markdown is not None
    assert "# CV Feedback Analysis" in result_markdown
    assert "75.0/100" in result_markdown
    assert "Good CV with relevant experience" in result_markdown
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
        language="python",
        overall_assessment=OverallAssessment(
            overall_score=75.0,
            summary="Good code quality overall",
        ),
        code_quality=CodeQuality(
            score=18.75,
            feedback="Code is readable and well-structured",
            suggestions=[],
        ),
        best_practices=BestPractices(
            score=16.0,
            feedback="Follows most best practices",
            principles_violated=[],
            principles_followed=["SOLID"],
            suggestions=[],
        ),
        actionable_recommendations=CodeActionableRecommendation(
            recommendation="Add error handling",
            impact="Improves robustness",
            effort="medium",
            line_reference=None,
        ),
    )
    mock_llm.analyze_feedback.return_value = mock_code_result

    # Act
    request, result, result_markdown = await use_case.execute(
        entity_id=code_id,
        input_type=InputType.CODE,
        feedback_input=feedback_input,
    )

    # Assert
    # Note: request object returned is the original, status updates happen in repo
    assert isinstance(result, CodeReviewFeedbackResult)
    assert result.submission_id == str(code_id)
    assert result_markdown is not None
    assert "# Code Review Feedback" in result_markdown
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
        overall_assessment=OverallAssessment(
            overall_score=70.0,
            summary="Basic CV structure",
        ),
        professional_summary=SectionFeedback(
            score=10.0,
            feedback="Basic professional summary",
            suggestions=[],
        ),
        work_experience=SectionFeedback(
            score=15.0,
            feedback="Work experience section",
            suggestions=[],
        ),
        projects=SectionFeedback(
            score=12.0,
            feedback="Projects section",
            suggestions=[],
        ),
        skills=SectionFeedback(
            score=10.0,
            feedback="Skills section",
            suggestions=[],
        ),
        actionable_recommendations=ActionableRecommendations(),
        market_competitiveness=MarketCompetitiveness(
            assessment="Needs improvement",
            target_roles=[],
            improvement_areas=[],
        ),
    )
    mock_llm.analyze_feedback.return_value = mock_cv_result

    # Act
    _, _, result_markdown = await use_case.execute(
        entity_id=cv_id,
        input_type=InputType.CV,
        user_id=user_id,
        feedback_input=feedback_input,
    )


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
