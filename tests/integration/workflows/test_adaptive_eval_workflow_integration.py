"""Integration tests for AdaptiveEvalSimpleWorkflow (Phase 3A).

Tests complete workflow execution with real database and mocked external services.
"""

import pytest
from datetime import datetime
from uuid import uuid4

from src.application.workflows.adaptive_eval_simple_workflow import AdaptiveEvalSimpleWorkflow
from src.domain.models.answer import Answer, AnswerEvaluation
from src.domain.models.candidate import Candidate
from src.domain.models.evaluation import Evaluation, ConceptGap, GapSeverity
from src.domain.models.follow_up_question import FollowUpQuestion
from src.domain.models.interview import Interview, InterviewStatus
from src.domain.models.question import Question, QuestionType, DifficultyLevel


pytestmark = pytest.mark.asyncio


class TestAdaptiveEvalWorkflowIntegration:
    """Integration tests for adaptive evaluation workflow."""

    async def test_workflow_execution_no_followup_needed(
        self,
        async_session,
        container,
        mock_llm_high_score,
    ):
        """Test complete workflow when answer is good (no follow-up needed)."""
        # Setup: Create test data in database
        candidate = Candidate(
            id=uuid4(),
            name="Test Candidate",
            email="test@example.com",
            created_at=datetime.utcnow(),
        )

        question = Question(
            id=uuid4(),
            text="Explain recursion in programming.",
            question_type=QuestionType.TECHNICAL,
            difficulty=DifficultyLevel.MEDIUM,
            topic="Programming",
            ideal_answer="Recursion is when a function calls itself...",
            keywords=["recursion", "base case"],
            created_at=datetime.utcnow(),
        )

        interview = Interview(
            id=uuid4(),
            candidate_id=candidate.id,
            question_ids=[question.id],
            status=InterviewStatus.QUESTIONING,
            current_question_index=0,
            answer_ids=[],
            created_at=datetime.utcnow(),
        )

        # Save to DB
        async_session.add(candidate)
        async_session.add(question)
        async_session.add(interview)
        await async_session.commit()

        # Create workflow
        workflow = await container.create_adaptive_eval_simple_workflow(async_session)

        # Execute workflow
        result = await workflow.execute(
            interview_id=interview.id,
            question_id=question.id,
            answer_text="Recursion is when a function calls itself with a base case to avoid infinite loops.",
            voice_metrics=None,
        )

        # Assertions
        assert result["evaluation"] is not None
        assert result["answer"] is not None
        assert result["needs_followup"] is False  # Good answer, no follow-up
        assert result["followup_question"] is None
        assert result["has_more_questions"] is False  # Only one question

        # Verify database persistence
        saved_answer = await async_session.get(Answer, result["answer"].id)
        assert saved_answer is not None
        assert saved_answer.text == "Recursion is when a function calls itself with a base case to avoid infinite loops."

        saved_evaluation = await async_session.get(Evaluation, result["evaluation"].id)
        assert saved_evaluation is not None
        assert saved_evaluation.final_score >= 80.0  # High score from mock

    async def test_workflow_execution_with_followup_needed(
        self,
        async_session,
        container,
        mock_llm_low_score_with_gaps,
    ):
        """Test complete workflow when answer has gaps (follow-up needed)."""
        # Setup: Create test data
        candidate = Candidate(
            id=uuid4(),
            name="Test Candidate",
            email="test@example.com",
            created_at=datetime.utcnow(),
        )

        question = Question(
            id=uuid4(),
            text="Explain error handling in Python.",
            question_type=QuestionType.TECHNICAL,
            difficulty=DifficultyLevel.MEDIUM,
            topic="Programming",
            ideal_answer="Error handling uses try-except blocks...",
            keywords=["try", "except", "finally", "raise"],
            created_at=datetime.utcnow(),
        )

        interview = Interview(
            id=uuid4(),
            candidate_id=candidate.id,
            question_ids=[question.id, uuid4()],  # Multiple questions
            status=InterviewStatus.QUESTIONING,
            current_question_index=0,
            answer_ids=[],
            created_at=datetime.utcnow(),
        )

        # Save to DB
        async_session.add(candidate)
        async_session.add(question)
        async_session.add(interview)
        await async_session.commit()

        # Create workflow
        workflow = await container.create_adaptive_eval_simple_workflow(async_session)

        # Execute workflow
        result = await workflow.execute(
            interview_id=interview.id,
            question_id=question.id,
            answer_text="You use try and except blocks.",  # Incomplete answer
            voice_metrics=None,
        )

        # Assertions
        assert result["evaluation"] is not None
        assert result["answer"] is not None
        assert result["needs_followup"] is True  # Poor answer, needs follow-up
        assert result["followup_question"] is not None
        assert result["has_more_questions"] is True  # More main questions available

        # Verify follow-up question saved to DB
        followup_id = result["followup_question"].id
        saved_followup = await async_session.get(FollowUpQuestion, followup_id)
        assert saved_followup is not None
        assert saved_followup.parent_question_id == question.id
        assert saved_followup.order_in_sequence == 1

    async def test_workflow_with_voice_answer(
        self,
        async_session,
        container,
        mock_llm_high_score,
    ):
        """Test workflow with voice answer and metrics."""
        # Setup
        candidate = Candidate(
            id=uuid4(),
            name="Test Candidate",
            email="test@example.com",
            created_at=datetime.utcnow(),
        )

        question = Question(
            id=uuid4(),
            text="Describe object-oriented programming.",
            question_type=QuestionType.TECHNICAL,
            difficulty=DifficultyLevel.MEDIUM,
            topic="Programming",
            ideal_answer="OOP is a programming paradigm...",
            keywords=["OOP", "class", "object", "inheritance"],
            created_at=datetime.utcnow(),
        )

        interview = Interview(
            id=uuid4(),
            candidate_id=candidate.id,
            question_ids=[question.id],
            status=InterviewStatus.QUESTIONING,
            current_question_index=0,
            answer_ids=[],
            created_at=datetime.utcnow(),
        )

        async_session.add(candidate)
        async_session.add(question)
        async_session.add(interview)
        await async_session.commit()

        # Create workflow
        workflow = await container.create_adaptive_eval_simple_workflow(async_session)

        # Voice metrics
        voice_metrics = {
            "intonation_score": 0.85,
            "fluency_score": 0.80,
            "confidence_score": 0.90,
            "speaking_rate_wpm": 155,
        }

        # Execute
        result = await workflow.execute(
            interview_id=interview.id,
            question_id=question.id,
            answer_text="OOP is a programming paradigm based on objects and classes.",
            audio_file_path="/uploads/audio/test.wav",
            voice_metrics=voice_metrics,
        )

        # Assertions
        assert result["answer"].is_voice is True
        assert result["answer"].voice_metrics == voice_metrics
        assert result["answer"].audio_file_path == "/uploads/audio/test.wav"

    async def test_workflow_handles_database_errors(
        self,
        async_session,
        container,
        mock_llm_high_score,
    ):
        """Test workflow error handling when database operations fail."""
        # Setup with invalid interview ID (not in DB)
        invalid_interview_id = uuid4()
        invalid_question_id = uuid4()

        # Create workflow
        workflow = await container.create_adaptive_eval_simple_workflow(async_session)

        # Execute - should raise exception
        with pytest.raises(Exception) as exc_info:
            await workflow.execute(
                interview_id=invalid_interview_id,
                question_id=invalid_question_id,
                answer_text="Test answer",
            )

        # Assert error message contains useful info
        assert "failed" in str(exc_info.value).lower() or "not found" in str(exc_info.value).lower()


@pytest.fixture
def mock_llm_high_score(mocker):
    """Mock LLM to return high scores (no follow-up needed)."""
    mock_llm = mocker.patch("src.adapters.llm.langchain_adapter.LangChainAdapter")

    # Mock evaluate_answer
    mock_llm.evaluate_answer.return_value = AnswerEvaluation(
        score=92.0,
        semantic_similarity=0.92,
        completeness=0.95,
        relevance=0.90,
        sentiment="very positive",
        reasoning="Excellent answer with comprehensive coverage",
        strengths=["Clear explanation", "Good examples", "Covers all key points"],
        weaknesses=[],
        improvement_suggestions=[],
    )

    # Mock detect_concept_gaps (no gaps)
    mock_llm.detect_concept_gaps.return_value = {
        "concepts": [],
        "confirmed": False,
        "severity": "none",
    }

    return mock_llm


@pytest.fixture
def mock_llm_low_score_with_gaps(mocker):
    """Mock LLM to return low scores with gaps (follow-up needed)."""
    mock_llm = mocker.patch("src.adapters.llm.langchain_adapter.LangChainAdapter")

    # Mock evaluate_answer
    mock_llm.evaluate_answer.return_value = AnswerEvaluation(
        score=62.0,
        semantic_similarity=0.55,
        completeness=0.60,
        relevance=0.70,
        sentiment="neutral",
        reasoning="Answer missing key concepts",
        strengths=["Basic understanding"],
        weaknesses=["Missing error handling details", "No exception types mentioned"],
        improvement_suggestions=["Explain different exception types", "Discuss finally block"],
    )

    # Mock detect_concept_gaps
    mock_llm.detect_concept_gaps.return_value = {
        "concepts": ["exception types", "finally block", "custom exceptions"],
        "confirmed": True,
        "severity": "moderate",
    }

    # Mock generate_followup_question
    mock_llm.generate_followup_question.return_value = (
        "Can you explain the different types of exceptions in Python and when to use them?"
    )

    return mock_llm
