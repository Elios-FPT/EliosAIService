"""Unit tests for AdaptiveEvalSimpleWorkflow (Phase 3A).

Tests each workflow node in isolation with mocked dependencies.
"""

import pytest
from datetime import datetime
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch

from src.application.workflows.adaptive_eval_simple_workflow import (
    AdaptiveEvalSimpleWorkflow,
    AdaptiveEvalSimpleState,
)
from src.domain.models.answer import Answer, AnswerEvaluation
from src.domain.models.evaluation import Evaluation, ConceptGap, GapSeverity
from src.domain.models.follow_up_question import FollowUpQuestion
from src.domain.models.interview import Interview, InterviewStatus
from src.domain.models.question import Question, QuestionType, DifficultyLevel


@pytest.fixture
def mock_checkpointer():
    """Mock AsyncPostgresSaver checkpointer."""
    return AsyncMock()


@pytest.fixture
def mock_repos():
    """Mock all repository ports."""
    return {
        "answer_repo": AsyncMock(),
        "evaluation_repo": AsyncMock(),
        "interview_repo": AsyncMock(),
        "question_repo": AsyncMock(),
        "follow_up_repo": AsyncMock(),
    }


@pytest.fixture
def mock_llm():
    """Mock LLM port."""
    llm = AsyncMock()

    # Mock evaluate_answer
    llm.evaluate_answer.return_value = AnswerEvaluation(
        score=75.0,
        semantic_similarity=0.75,
        completeness=0.8,
        relevance=0.9,
        sentiment="positive",
        reasoning="Good answer with minor gaps",
        strengths=["Clear explanation", "Good examples"],
        weaknesses=["Missing edge cases"],
        improvement_suggestions=["Add error handling discussion"],
    )

    # Mock generate_followup_question
    llm.generate_followup_question.return_value = "Can you explain how you would handle edge cases?"

    # Mock detect_concept_gaps
    llm.detect_concept_gaps.return_value = {
        "concepts": ["error handling", "edge cases"],
        "confirmed": True,
        "severity": "moderate",
    }

    return llm


@pytest.fixture
def sample_interview():
    """Create sample interview entity."""
    interview_id = uuid4()
    candidate_id = uuid4()
    question_ids = [uuid4(), uuid4(), uuid4()]

    return Interview(
        id=interview_id,
        candidate_id=candidate_id,
        question_ids=question_ids,
        status=InterviewStatus.QUESTIONING,
        current_question_index=0,
        answer_ids=[],
        created_at=datetime.utcnow(),
    )


@pytest.fixture
def sample_question():
    """Create sample question entity."""
    return Question(
        id=uuid4(),
        text="Explain the concept of recursion in programming.",
        question_type=QuestionType.TECHNICAL,
        difficulty=DifficultyLevel.MEDIUM,
        topic="Programming Fundamentals",
        ideal_answer="Recursion is when a function calls itself...",
        keywords=["recursion", "base case", "recursive case"],
        created_at=datetime.utcnow(),
    )


@pytest.fixture
async def workflow(mock_checkpointer, mock_repos, mock_llm):
    """Create AdaptiveEvalSimpleWorkflow instance with mocked dependencies."""
    workflow = AdaptiveEvalSimpleWorkflow(
        checkpointer=mock_checkpointer,
        answer_repo=mock_repos["answer_repo"],
        evaluation_repo=mock_repos["evaluation_repo"],
        interview_repo=mock_repos["interview_repo"],
        question_repo=mock_repos["question_repo"],
        follow_up_repo=mock_repos["follow_up_repo"],
        llm=mock_llm,
    )
    return workflow


class TestLoadContextNode:
    """Test load_context node."""

    @pytest.mark.asyncio
    async def test_load_context_main_question(
        self, workflow, sample_interview, sample_question, mock_repos
    ):
        """Test loading context for main question (not follow-up)."""
        # Setup
        question_id = sample_question.id
        mock_repos["interview_repo"].get_by_id.return_value = sample_interview
        mock_repos["question_repo"].get_by_id.return_value = sample_question
        mock_repos["follow_up_repo"].get_by_id.return_value = None

        state: AdaptiveEvalSimpleState = {
            "interview_id": sample_interview.id,
            "question_id": question_id,
            "answer_text": "Sample answer",
            "audio_file_path": None,
            "voice_metrics": None,
            "interview": None,
            "question": None,
            "parent_question_id": None,
            "is_followup": False,
            "iteration": 0,
            "answers": [],
            "evaluations": [],
            "cumulative_gaps": [],
            "followup_questions_generated": [],
            "combined_evaluation": None,
            "final_answer": None,
            "has_more_questions": False,
            "complete": False,
            "errors": [],
            "retry_count": 0,
        }

        # Execute
        result = await workflow._load_context_node(state)

        # Assert
        assert result["interview"] == sample_interview
        assert result["question"] == sample_question
        assert result["is_followup"] is False
        assert result["parent_question_id"] == question_id  # Main question is its own parent
        assert "errors" not in result or not result["errors"]

    @pytest.mark.asyncio
    async def test_load_context_follow_up_question(
        self, workflow, sample_interview, sample_question, mock_repos
    ):
        """Test loading context for follow-up question."""
        # Setup
        parent_question_id = sample_question.id
        followup_id = uuid4()

        followup = FollowUpQuestion(
            id=followup_id,
            parent_question_id=parent_question_id,
            interview_id=sample_interview.id,
            text="Follow-up question text",
            generated_reason="Missing concepts",
            order_in_sequence=1,
        )

        mock_repos["interview_repo"].get_by_id.return_value = sample_interview
        mock_repos["follow_up_repo"].get_by_id.return_value = followup
        mock_repos["question_repo"].get_by_id.return_value = sample_question

        state: AdaptiveEvalSimpleState = {
            "interview_id": sample_interview.id,
            "question_id": followup_id,
            "answer_text": "Sample answer",
            "audio_file_path": None,
            "voice_metrics": None,
            "interview": None,
            "question": None,
            "parent_question_id": None,
            "is_followup": False,
            "iteration": 0,
            "answers": [],
            "evaluations": [],
            "cumulative_gaps": [],
            "followup_questions_generated": [],
            "combined_evaluation": None,
            "final_answer": None,
            "has_more_questions": False,
            "complete": False,
            "errors": [],
            "retry_count": 0,
        }

        # Execute
        result = await workflow._load_context_node(state)

        # Assert
        assert result["interview"] == sample_interview
        assert result["question"] == sample_question  # Parent question
        assert result["is_followup"] is True
        assert result["parent_question_id"] == parent_question_id

    @pytest.mark.asyncio
    async def test_load_context_interview_not_found(self, workflow, mock_repos):
        """Test error handling when interview not found."""
        # Setup
        mock_repos["interview_repo"].get_by_id.return_value = None

        state: AdaptiveEvalSimpleState = {
            "interview_id": uuid4(),
            "question_id": uuid4(),
            "answer_text": "Sample answer",
            "audio_file_path": None,
            "voice_metrics": None,
            "interview": None,
            "question": None,
            "parent_question_id": None,
            "is_followup": False,
            "iteration": 0,
            "answers": [],
            "evaluations": [],
            "cumulative_gaps": [],
            "followup_questions_generated": [],
            "combined_evaluation": None,
            "final_answer": None,
            "has_more_questions": False,
            "complete": False,
            "errors": [],
            "retry_count": 0,
        }

        # Execute
        result = await workflow._load_context_node(state)

        # Assert
        assert "errors" in result
        assert len(result["errors"]) > 0
        assert "not found" in result["errors"][0].lower()


class TestEvaluateAnswerNode:
    """Test evaluate_answer node."""

    @pytest.mark.asyncio
    async def test_evaluate_answer_success(
        self, workflow, sample_interview, sample_question, mock_llm
    ):
        """Test successful answer evaluation."""
        # Setup
        state: AdaptiveEvalSimpleState = {
            "interview_id": sample_interview.id,
            "question_id": sample_question.id,
            "answer_text": "Recursion is when a function calls itself with a base case.",
            "audio_file_path": None,
            "voice_metrics": None,
            "interview": sample_interview,
            "question": sample_question,
            "parent_question_id": sample_question.id,
            "is_followup": False,
            "iteration": 0,
            "answers": [],
            "evaluations": [],
            "cumulative_gaps": [],
            "followup_questions_generated": [],
            "combined_evaluation": None,
            "final_answer": None,
            "has_more_questions": False,
            "complete": False,
            "errors": [],
            "retry_count": 0,
        }

        # Execute
        result = await workflow._evaluate_answer_node(state)

        # Assert
        assert "answers" in result
        assert "evaluations" in result
        assert len(result["answers"]) == 1
        assert len(result["evaluations"]) == 1

        answer = result["answers"][0]
        evaluation = result["evaluations"][0]

        assert answer.text == state["answer_text"]
        assert answer.interview_id == sample_interview.id
        assert evaluation.final_score > 0

    @pytest.mark.asyncio
    async def test_evaluate_answer_with_voice_metrics(
        self, workflow, sample_interview, sample_question
    ):
        """Test evaluation with voice metrics."""
        # Setup
        voice_metrics = {
            "intonation_score": 0.8,
            "fluency_score": 0.85,
            "confidence_score": 0.75,
            "speaking_rate_wpm": 150,
        }

        state: AdaptiveEvalSimpleState = {
            "interview_id": sample_interview.id,
            "question_id": sample_question.id,
            "answer_text": "Sample answer",
            "audio_file_path": "/path/to/audio.wav",
            "voice_metrics": voice_metrics,
            "interview": sample_interview,
            "question": sample_question,
            "parent_question_id": sample_question.id,
            "is_followup": False,
            "iteration": 0,
            "answers": [],
            "evaluations": [],
            "cumulative_gaps": [],
            "followup_questions_generated": [],
            "combined_evaluation": None,
            "final_answer": None,
            "has_more_questions": False,
            "complete": False,
            "errors": [],
            "retry_count": 0,
        }

        # Execute
        result = await workflow._evaluate_answer_node(state)

        # Assert
        answer = result["answers"][0]
        assert answer.is_voice is True
        assert answer.voice_metrics == voice_metrics
        assert answer.audio_file_path == "/path/to/audio.wav"


class TestConditionalEdgeLogic:
    """Test _should_generate_followup conditional logic."""

    def test_should_finalize_max_iterations(self, workflow, sample_interview):
        """Test break condition: max iterations reached."""
        # Setup
        evaluation = Evaluation(
            answer_id=uuid4(),
            question_id=uuid4(),
            interview_id=uuid4(),
            raw_score=70.0,
            penalty=0.0,
            final_score=70.0,
            similarity_score=0.6,
            completeness=0.7,
            relevance=0.8,
            attempt_number=3,  # Max is 3, not 4
            gaps=[],
            evaluated_at=datetime.utcnow(),
        )

        state: AdaptiveEvalSimpleState = {
            "interview_id": sample_interview.id,
            "question_id": uuid4(),
            "answer_text": "Answer",
            "audio_file_path": None,
            "voice_metrics": None,
            "interview": sample_interview,
            "question": None,
            "parent_question_id": uuid4(),
            "is_followup": False,
            "iteration": 3,  # Max reached
            "answers": [],
            "evaluations": [evaluation],
            "cumulative_gaps": ["some gap"],
            "followup_questions_generated": [],
            "combined_evaluation": None,
            "final_answer": None,
            "has_more_questions": False,
            "complete": False,
            "errors": [],
            "retry_count": 0,
        }

        # Execute
        result = workflow._should_generate_followup(state)

        # Assert
        assert result == "finalize"

    def test_should_finalize_high_similarity(self, workflow, sample_interview):
        """Test break condition: high similarity score."""
        # Setup
        evaluation = Evaluation(
            answer_id=uuid4(),
            question_id=uuid4(),
            interview_id=uuid4(),
            raw_score=90.0,
            penalty=0.0,
            final_score=90.0,
            similarity_score=0.85,  # >= 0.8
            completeness=0.9,
            relevance=0.95,
            attempt_number=1,
            gaps=[],
            evaluated_at=datetime.utcnow(),
        )

        state: AdaptiveEvalSimpleState = {
            "interview_id": sample_interview.id,
            "question_id": uuid4(),
            "answer_text": "Answer",
            "audio_file_path": None,
            "voice_metrics": None,
            "interview": sample_interview,
            "question": None,
            "parent_question_id": uuid4(),
            "is_followup": False,
            "iteration": 0,
            "answers": [],
            "evaluations": [evaluation],
            "cumulative_gaps": [],
            "followup_questions_generated": [],
            "combined_evaluation": None,
            "final_answer": None,
            "has_more_questions": False,
            "complete": False,
            "errors": [],
            "retry_count": 0,
        }

        # Execute
        result = workflow._should_generate_followup(state)

        # Assert
        assert result == "finalize"

    def test_should_finalize_no_gaps(self, workflow, sample_interview):
        """Test break condition: no gaps detected."""
        # Setup
        evaluation = Evaluation(
            answer_id=uuid4(),
            question_id=uuid4(),
            interview_id=uuid4(),
            raw_score=85.0,
            penalty=0.0,
            final_score=85.0,
            similarity_score=0.75,
            completeness=0.9,
            relevance=0.9,
            attempt_number=1,
            gaps=[],
            evaluated_at=datetime.utcnow(),
        )

        state: AdaptiveEvalSimpleState = {
            "interview_id": sample_interview.id,
            "question_id": uuid4(),
            "answer_text": "Answer",
            "audio_file_path": None,
            "voice_metrics": None,
            "interview": sample_interview,
            "question": None,
            "parent_question_id": uuid4(),
            "is_followup": False,
            "iteration": 0,
            "answers": [],
            "evaluations": [evaluation],
            "cumulative_gaps": [],  # No gaps
            "followup_questions_generated": [],
            "combined_evaluation": None,
            "final_answer": None,
            "has_more_questions": False,
            "complete": False,
            "errors": [],
            "retry_count": 0,
        }

        # Execute
        result = workflow._should_generate_followup(state)

        # Assert
        assert result == "finalize"

    def test_should_generate_followup_with_gaps(self, workflow, sample_interview):
        """Test follow-up needed: gaps detected, iterations left."""
        # Setup
        evaluation = Evaluation(
            answer_id=uuid4(),
            question_id=uuid4(),
            interview_id=uuid4(),
            raw_score=65.0,
            penalty=0.0,
            final_score=65.0,
            similarity_score=0.6,
            completeness=0.7,
            relevance=0.8,
            attempt_number=1,
            gaps=[
                ConceptGap(
                    evaluation_id=uuid4(),
                    concept="error handling",
                    severity=GapSeverity.MODERATE,
                    resolved=False,
                    created_at=datetime.utcnow(),
                )
            ],
            evaluated_at=datetime.utcnow(),
        )

        state: AdaptiveEvalSimpleState = {
            "interview_id": sample_interview.id,
            "question_id": uuid4(),
            "answer_text": "Answer",
            "audio_file_path": None,
            "voice_metrics": None,
            "interview": sample_interview,
            "question": None,
            "parent_question_id": uuid4(),
            "is_followup": False,
            "iteration": 0,
            "answers": [],
            "evaluations": [evaluation],
            "cumulative_gaps": ["error handling"],
            "followup_questions_generated": [],
            "combined_evaluation": None,
            "final_answer": None,
            "has_more_questions": False,
            "complete": False,
            "errors": [],
            "retry_count": 0,
        }

        # Execute
        result = workflow._should_generate_followup(state)

        # Assert
        assert result == "generate_followup"


class TestGenerateFollowupNode:
    """Test generate_followup node."""

    @pytest.mark.asyncio
    async def test_generate_followup_success(
        self, workflow, sample_interview, sample_question, mock_llm, mock_repos
    ):
        """Test successful follow-up generation."""
        # Setup
        saved_followup = FollowUpQuestion(
            id=uuid4(),
            parent_question_id=sample_question.id,
            interview_id=sample_interview.id,
            text="Can you explain error handling?",
            generated_reason="Missing concepts: error handling",
            order_in_sequence=1,
        )
        mock_repos["follow_up_repo"].save.return_value = saved_followup

        state: AdaptiveEvalSimpleState = {
            "interview_id": sample_interview.id,
            "question_id": sample_question.id,
            "answer_text": "Sample answer",
            "audio_file_path": None,
            "voice_metrics": None,
            "interview": sample_interview,
            "question": sample_question,
            "parent_question_id": sample_question.id,
            "is_followup": False,
            "iteration": 0,
            "answers": [],
            "evaluations": [],
            "cumulative_gaps": ["error handling", "edge cases"],
            "followup_questions_generated": [],
            "combined_evaluation": None,
            "final_answer": None,
            "has_more_questions": False,
            "complete": False,
            "errors": [],
            "retry_count": 0,
        }

        # Execute
        result = await workflow._generate_followup_node(state)

        # Assert
        assert "followup_questions_generated" in result
        assert len(result["followup_questions_generated"]) == 1
        assert result["followup_questions_generated"][0] == saved_followup
        assert result["complete"] is True
        assert "has_more_questions" in result


class TestFinalizeNode:
    """Test finalize node."""

    @pytest.mark.asyncio
    async def test_finalize_with_more_questions(self, workflow, sample_interview):
        """Test finalize when more main questions available."""
        # Setup
        sample_interview.current_question_index = 0  # More questions available

        evaluation = Evaluation(
            answer_id=uuid4(),
            question_id=uuid4(),
            interview_id=uuid4(),
            raw_score=85.0,
            penalty=0.0,
            final_score=85.0,
            completeness=0.9,
            relevance=0.9,
            attempt_number=1,
            gaps=[],
            evaluated_at=datetime.utcnow(),
        )

        state: AdaptiveEvalSimpleState = {
            "interview_id": sample_interview.id,
            "question_id": uuid4(),
            "answer_text": "Answer",
            "audio_file_path": None,
            "voice_metrics": None,
            "interview": sample_interview,
            "question": None,
            "parent_question_id": uuid4(),
            "is_followup": False,
            "iteration": 0,
            "answers": [],
            "evaluations": [evaluation],
            "cumulative_gaps": [],
            "followup_questions_generated": [],
            "combined_evaluation": None,
            "final_answer": None,
            "has_more_questions": False,
            "complete": False,
            "errors": [],
            "retry_count": 0,
        }

        # Execute
        result = await workflow._finalize_node(state)

        # Assert
        assert result["complete"] is True
        assert result["has_more_questions"] is True

    @pytest.mark.asyncio
    async def test_finalize_no_more_questions(self, workflow, sample_interview):
        """Test finalize when no more questions (interview complete)."""
        # Setup
        sample_interview.current_question_index = len(sample_interview.question_ids)

        evaluation = Evaluation(
            answer_id=uuid4(),
            question_id=uuid4(),
            interview_id=uuid4(),
            raw_score=85.0,
            penalty=0.0,
            final_score=85.0,
            completeness=0.9,
            relevance=0.9,
            attempt_number=1,
            gaps=[],
            evaluated_at=datetime.utcnow(),
        )

        state: AdaptiveEvalSimpleState = {
            "interview_id": sample_interview.id,
            "question_id": uuid4(),
            "answer_text": "Answer",
            "audio_file_path": None,
            "voice_metrics": None,
            "interview": sample_interview,
            "question": None,
            "parent_question_id": uuid4(),
            "is_followup": False,
            "iteration": 0,
            "answers": [],
            "evaluations": [evaluation],
            "cumulative_gaps": [],
            "followup_questions_generated": [],
            "combined_evaluation": None,
            "final_answer": None,
            "has_more_questions": False,
            "complete": False,
            "errors": [],
            "retry_count": 0,
        }

        # Execute
        result = await workflow._finalize_node(state)

        # Assert
        assert result["complete"] is True
        assert result["has_more_questions"] is False
