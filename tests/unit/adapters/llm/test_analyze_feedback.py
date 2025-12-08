"""Unit tests for analyze_feedback method in LangChainAdapter."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from langchain_core.language_models import BaseChatModel

from src.adapters.llm.feedback_models import CVFeedbackAnalysis, CodeFeedbackAnalysis
from src.adapters.llm.langchain_adapter import LangChainAdapter
from src.domain.models.feedback_result import InputType


@pytest.fixture
def mock_model():
    """Create mock LangChain model."""
    model = MagicMock(spec=BaseChatModel)
    return model


@pytest.fixture
def mock_prompt_repo():
    """Create mock prompt repository."""
    repo = AsyncMock()
    return repo


@pytest.fixture
def adapter(mock_model, mock_prompt_repo):
    """Create LangChainAdapter instance."""
    return LangChainAdapter(model=mock_model, prompt_repository=mock_prompt_repo)


@pytest.mark.asyncio
async def test_analyze_feedback_cv(adapter, mock_prompt_repo):
    """Test CV feedback analysis."""
    entity_id = uuid4()
    cv_data = json.dumps({"skills": ["Python", "FastAPI"], "experience": "5 years"})

    # Mock prompt template
    from src.domain.models.prompt_template import PromptTemplate

    prompt_template = PromptTemplate(
        prompt_name="cv_feedback",
        version=1,
        system_prompt="System prompt",
        user_template="User template: {cv_data}",
        input_variables=["cv_data"],
        partial_variables={},
        temperature=0.7,
        max_tokens=2000,
        top_p=0.95,
        frequency_penalty=0.0,
        presence_penalty=0.0,
        created_by="test",
    )

    mock_prompt_repo.get_active_prompt.return_value = prompt_template

    # Mock LLM response
    cv_analysis = CVFeedbackAnalysis(
        overall_assessment={"overall_score": 85.0, "summary": "Good CV"},
        professional_summary={"score": 12.0, "feedback": "Good", "suggestions": []},
        work_experience={"score": 20.0, "feedback": "Strong", "suggestions": []},
        projects={"score": 22.0, "feedback": "Good", "suggestions": []},
        skills={"score": 18.0, "feedback": "Well-organized", "suggestions": []},
        actionable_recommendations={"high_priority": [], "medium_priority": [], "low_priority": []},
        market_competitiveness={
            "assessment": "Competitive",
            "target_roles": [],
            "improvement_areas": [],
        },
    )

    # Mock structured output
    structured_model = MagicMock()
    structured_model.ainvoke = AsyncMock(return_value=cv_analysis)
    adapter.model.bind.return_value.with_structured_output.return_value = structured_model

    # Mock metadata callback
    with patch.object(adapter, "_invoke_chain_with_metadata") as mock_invoke:
        mock_invoke.return_value = (cv_analysis, {"usage": {"total_tokens": 100}})

        result = await adapter.analyze_feedback(
            input_type=InputType.CV,
            feedback_input=cv_data,
            context={"entity_id": str(entity_id)},
        )

        assert result.cv_analysis_id == entity_id
        assert result.work_experience_summary == "Strong"
        mock_prompt_repo.get_active_prompt.assert_called_once_with("cv_feedback")


@pytest.mark.asyncio
async def test_analyze_feedback_code(adapter, mock_prompt_repo):
    """Test CODE feedback analysis."""
    entity_id = uuid4()
    code_data = json.dumps({
        "problem_description": "Sort array",
        "language": "python",
        "user_code_solution": "def sort(arr): return sorted(arr)",
    })

    # Mock prompt template
    from src.domain.models.prompt_template import PromptTemplate

    prompt_template = PromptTemplate(
        prompt_name="code_solution_feedback",
        version=1,
        system_prompt="System prompt",
        user_template="User template: {problem_description} {language} {user_code_solution}",
        input_variables=["problem_description", "language", "user_code_solution"],
        partial_variables={},
        temperature=0.4,
        max_tokens=3000,
        top_p=0.95,
        frequency_penalty=0.0,
        presence_penalty=0.0,
        created_by="test",
    )

    mock_prompt_repo.get_active_prompt.return_value = prompt_template

    # Mock LLM response
    code_analysis = CodeFeedbackAnalysis(
        overall_assessment={"overall_score": 80.0, "summary": "Good code"},
        code_quality={"score": 20.0, "feedback": "Clean", "suggestions": []},
        best_practices={
            "score": 16.0,
            "feedback": "Good practices",
            "principles_violated": [],
            "principles_followed": ["SOLID"],
            "suggestions": [],
        },
        actionable_recommendations={
            "recommendation": "Add error handling",
            "impact": "High",
            "effort": "low",
            "line_reference": None,
        },
    )

    with patch.object(adapter, "_invoke_chain_with_metadata") as mock_invoke:
        mock_invoke.return_value = (code_analysis, {"usage": {"total_tokens": 150}})

        result = await adapter.analyze_feedback(
            input_type=InputType.CODE,
            feedback_input=code_data,
            context={"entity_id": str(entity_id)},
        )

        assert result.submission_id == str(entity_id)
        assert result.code_quality_score == 80.0  # 20 * 4
        assert result.language == "python"
        mock_prompt_repo.get_active_prompt.assert_called_once_with("code_solution_feedback")


@pytest.mark.asyncio
async def test_analyze_feedback_interview_rejected(adapter):
    """Test that INTERVIEW type is rejected."""
    with pytest.raises(ValueError, match="INTERVIEW analysis not supported"):
        await adapter.analyze_feedback(
            input_type=InputType.INTERVIEW,
            feedback_input='{"test": "data"}',
        )


@pytest.mark.asyncio
async def test_analyze_feedback_invalid_json(adapter, mock_prompt_repo):
    """Test that invalid JSON is rejected."""
    from src.domain.models.prompt_template import PromptTemplate

    prompt_template = PromptTemplate(
        prompt_name="cv_feedback",
        version=1,
        system_prompt="System prompt",
        user_template="User template: {cv_data}",
        input_variables=["cv_data"],
        partial_variables={},
        temperature=0.7,
        max_tokens=2000,
        top_p=0.95,
        frequency_penalty=0.0,
        presence_penalty=0.0,
        created_by="test",
    )

    mock_prompt_repo.get_active_prompt.return_value = prompt_template

    with pytest.raises(ValueError, match="Invalid feedback_input JSON"):
        await adapter.analyze_feedback(
            input_type=InputType.CV,
            feedback_input="not valid json",
        )


