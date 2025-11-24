"""Unit tests for AdaptiveEvalInterruptWorkflow (Phase 3B).

Tests interrupt-based adaptive evaluation workflow with loop-back logic.
"""

import pytest
from datetime import datetime
from uuid import uuid4, UUID
from unittest.mock import AsyncMock, MagicMock

from src.application.workflows.adaptive_eval_interrupt_workflow import (
    AdaptiveEvalInterruptWorkflow,
    AdaptiveEvalInterruptState,
)
from src.domain.models.answer import Answer, AnswerEvaluation
from src.domain.models.evaluation import Evaluation, ConceptGap, GapSeverity
from src.domain.models.follow_up_question import FollowUpQuestion
from src.domain.models.interview import Interview, InterviewStatus
from src.domain.models.question import Question, QuestionType, DifficultyLevel


pytestmark = pytest.mark.asyncio


class TestSendWebsocketNode:
    """Test send_websocket interrupt node."""

    async def test_send_websocket_node_sets_waiting_state(self):
        """Test that send_websocket node sets waiting_for_answer=True."""
        # Setup
        mock_checkpointer = AsyncMock()
        mock_repos = self._create_mock_repos()
        mock_llm = AsyncMock()

        workflow = AdaptiveEvalInterruptWorkflow(
            checkpointer=mock_checkpointer,
            **mock_repos,
            llm=mock_llm,
        )

        # Create state with follow-up question
        followup_question = FollowUpQuestion(
            id=uuid4(),
            parent_question_id=uuid4(),
            interview_id=uuid4(),
            text="Can you explain the different exception types?",
            generated_reason="Missing concepts: exception types, custom exceptions",
            order_in_sequence=1,
            created_at=datetime.utcnow(),
        )

        state: AdaptiveEvalInterruptState = {
            "interview_id": uuid4(),
            "question_id": uuid4(),
            "answer_text": "Test answer",
            "audio_file_path": None,
            "voice_metrics": None,
            "interview": None,
            "question": None,
            "parent_question_id": None,
            "is_followup": False,
            "iteration": 0,
            "answers": [],
            "evaluations": [],
            "cumulative_gaps": ["exception types", "custom exceptions"],
            "followup_questions_generated": [followup_question],
            "current_followup_question": None,
            "waiting_for_answer": False,
            "resume_node": None,
            "combined_evaluation": None,
            "final_answer": None,
            "has_more_questions": False,
            "complete": False,
            "errors": [],
            "retry_count": 0,
        }

        # Execute node
        result = await workflow._send_websocket_node(state)

        # Assert interrupt state
        assert result["waiting_for_answer"] is True
        assert result["current_followup_question"] == followup_question
        assert result["resume_node"] == "evaluate_answer"
        assert result["iteration"] == 1  # Incremented for next evaluation
        assert result["question_id"] == followup_question.id
        assert result["is_followup"] is True

    async def test_send_websocket_node_handles_missing_followup(self):
        """Test that send_websocket node handles missing follow-up question."""
        # Setup
        mock_checkpointer = AsyncMock()
        mock_repos = self._create_mock_repos()
        mock_llm = AsyncMock()

        workflow = AdaptiveEvalInterruptWorkflow(
            checkpointer=mock_checkpointer,
            **mock_repos,
            llm=mock_llm,
        )

        # Create state WITHOUT follow-up question
        state: AdaptiveEvalInterruptState = {
            "interview_id": uuid4(),
            "question_id": uuid4(),
            "answer_text": "Test answer",
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
            "followup_questions_generated": [],  # Empty list
            "current_followup_question": None,
            "waiting_for_answer": False,
            "resume_node": None,
            "combined_evaluation": None,
            "final_answer": None,
            "has_more_questions": False,
            "complete": False,
            "errors": [],
            "retry_count": 0,
        }

        # Execute node
        result = await workflow._send_websocket_node(state)

        # Assert error handling
        assert "errors" in result
        assert len(result["errors"]) > 0
        assert "No follow-up question to send" in result["errors"][0]

    def _create_mock_repos(self):
        """Create mock repository ports."""
        return {
            "answer_repo": AsyncMock(),
            "evaluation_repo": AsyncMock(),
            "interview_repo": AsyncMock(),
            "question_repo": AsyncMock(),
            "follow_up_repo": AsyncMock(),
        }


class TestInterruptWorkflowExecution:
    """Test full interrupt workflow execution."""

    async def test_workflow_interrupts_after_followup_generation(self, mocker):
        """Test that workflow interrupts and returns status='interrupted'."""
        # Setup mocks
        mock_checkpointer = AsyncMock()
        mock_checkpointer.aget_tuple = AsyncMock(return_value=None)  # No existing checkpoint

        mock_repos = self._create_mock_repos_with_data()
        mock_llm = self._create_mock_llm_with_gaps()

        workflow = AdaptiveEvalInterruptWorkflow(
            checkpointer=mock_checkpointer,
            **mock_repos,
            llm=mock_llm,
        )

        # Mock the app.ainvoke to simulate interrupt
        workflow.app = AsyncMock()
        workflow.app.ainvoke = AsyncMock(return_value={
            "waiting_for_answer": True,  # Interrupted
            "current_followup_question": FollowUpQuestion(
                id=uuid4(),
                parent_question_id=uuid4(),
                interview_id=uuid4(),
                text="Can you explain exception types?",
                generated_reason="Missing concepts: exception types",
                order_in_sequence=1,
                created_at=datetime.utcnow(),
            ),
            "iteration": 1,
            "cumulative_gaps": ["exception types", "custom exceptions"],
            "followup_questions_generated": [],
            "evaluations": [],
            "answers": [],
            "complete": False,
        })

        # Execute workflow
        result = await workflow.execute(
            interview_id=uuid4(),
            question_id=uuid4(),
            answer_text="Try and except blocks handle errors.",
        )

        # Assert interrupt result
        assert result["status"] == "interrupted"
        assert result["followup_question"] is not None
        assert result["iteration"] == 1
        assert "thread_id" in result

    async def test_workflow_completes_when_no_followup_needed(self, mocker):
        """Test that workflow completes with status='complete' when no follow-up needed."""
        # Setup mocks
        mock_checkpointer = AsyncMock()
        mock_repos = self._create_mock_repos_with_data()
        mock_llm = self._create_mock_llm_high_score()

        workflow = AdaptiveEvalInterruptWorkflow(
            checkpointer=mock_checkpointer,
            **mock_repos,
            llm=mock_llm,
        )

        # Mock the app.ainvoke to simulate completion (no interrupt)
        answer = Answer(
            id=uuid4(),
            interview_id=uuid4(),
            question_id=uuid4(),
            candidate_id=uuid4(),
            text="Complete answer",
            is_voice=False,
            created_at=datetime.utcnow(),
        )

        evaluation = Evaluation(
            id=uuid4(),
            answer_id=answer.id,
            question_id=uuid4(),
            interview_id=uuid4(),
            raw_score=92.0,
            penalty=0.0,
            final_score=92.0,
            similarity_score=0.92,
            completeness=0.95,
            relevance=0.90,
            sentiment="very positive",
            reasoning="Excellent answer",
            strengths=["Clear explanation"],
            weaknesses=[],
            improvement_suggestions=[],
            attempt_number=1,
            gaps=[],
            evaluated_at=datetime.utcnow(),
        )

        workflow.app = AsyncMock()
        workflow.app.ainvoke = AsyncMock(return_value={
            "waiting_for_answer": False,  # Complete
            "complete": True,
            "evaluations": [evaluation],
            "answers": [answer],
            "has_more_questions": False,
            "followup_questions_generated": [],
        })

        # Execute workflow
        result = await workflow.execute(
            interview_id=uuid4(),
            question_id=uuid4(),
            answer_text="Recursion is when a function calls itself with a base case.",
        )

        # Assert completion result
        assert result["status"] == "complete"
        assert result["evaluation"] == evaluation
        assert result["answer"] == answer
        assert result["has_more_questions"] is False

    async def test_workflow_resume_with_thread_id(self, mocker):
        """Test that workflow can resume from checkpoint with thread_id."""
        # Setup mocks
        mock_checkpointer = AsyncMock()
        mock_repos = self._create_mock_repos_with_data()
        mock_llm = self._create_mock_llm_high_score()

        workflow = AdaptiveEvalInterruptWorkflow(
            checkpointer=mock_checkpointer,
            **mock_repos,
            llm=mock_llm,
        )

        # Mock existing checkpoint (resume scenario)
        thread_id = "adaptive_eval_interrupt_test-12345"
        workflow.app = AsyncMock()
        workflow.app.ainvoke = AsyncMock(return_value={
            "waiting_for_answer": False,  # Resume and complete
            "complete": True,
            "evaluations": [MagicMock()],
            "answers": [MagicMock()],
            "has_more_questions": False,
            "followup_questions_generated": [],
        })

        # Execute workflow with thread_id (resume)
        result = await workflow.execute(
            interview_id=uuid4(),
            question_id=uuid4(),
            answer_text="Exception types include ValueError, TypeError...",
            thread_id=thread_id,
        )

        # Assert resume behavior
        assert result["status"] == "complete"
        assert "thread_id" in result

    def _create_mock_repos_with_data(self):
        """Create mock repositories with data."""
        return {
            "answer_repo": AsyncMock(),
            "evaluation_repo": AsyncMock(),
            "interview_repo": AsyncMock(),
            "question_repo": AsyncMock(),
            "follow_up_repo": AsyncMock(),
        }

    def _create_mock_llm_with_gaps(self):
        """Create mock LLM that returns low score with gaps."""
        mock_llm = AsyncMock()
        mock_llm.evaluate_answer = AsyncMock(return_value=AnswerEvaluation(
            score=62.0,
            semantic_similarity=0.55,
            completeness=0.60,
            relevance=0.70,
            sentiment="neutral",
            reasoning="Answer missing key concepts",
            strengths=["Basic understanding"],
            weaknesses=["Missing exception types"],
            improvement_suggestions=["Explain different exception types"],
        ))
        mock_llm.detect_concept_gaps = AsyncMock(return_value={
            "concepts": ["exception types", "custom exceptions"],
            "confirmed": True,
            "severity": "moderate",
        })
        mock_llm.generate_followup_question = AsyncMock(
            return_value="Can you explain the different types of exceptions in Python?"
        )
        return mock_llm

    def _create_mock_llm_high_score(self):
        """Create mock LLM that returns high score (no gaps)."""
        mock_llm = AsyncMock()
        mock_llm.evaluate_answer = AsyncMock(return_value=AnswerEvaluation(
            score=92.0,
            semantic_similarity=0.92,
            completeness=0.95,
            relevance=0.90,
            sentiment="very positive",
            reasoning="Excellent answer",
            strengths=["Clear explanation", "Good examples"],
            weaknesses=[],
            improvement_suggestions=[],
        ))
        mock_llm.detect_concept_gaps = AsyncMock(return_value={
            "concepts": [],
            "confirmed": False,
            "severity": "none",
        })
        return mock_llm


class TestConditionalEdgeLogic:
    """Test conditional edge routing (same as Phase 3A)."""

    async def test_should_generate_followup_returns_finalize_when_max_iterations(self):
        """Test that _should_generate_followup returns 'finalize' at max iterations."""
        # Setup
        mock_checkpointer = AsyncMock()
        mock_repos = self._create_mock_repos()
        mock_llm = AsyncMock()

        workflow = AdaptiveEvalInterruptWorkflow(
            checkpointer=mock_checkpointer,
            **mock_repos,
            llm=mock_llm,
        )

        # Create state at max iterations (3)
        state: AdaptiveEvalInterruptState = {
            "interview_id": uuid4(),
            "question_id": uuid4(),
            "answer_text": "Test answer",
            "audio_file_path": None,
            "voice_metrics": None,
            "interview": None,
            "question": None,
            "parent_question_id": None,
            "is_followup": False,
            "iteration": 3,  # Max iterations
            "answers": [],
            "evaluations": [MagicMock(similarity_score=0.5, final_score=60.0)],
            "cumulative_gaps": ["concept1", "concept2"],
            "followup_questions_generated": [],
            "current_followup_question": None,
            "waiting_for_answer": False,
            "resume_node": None,
            "combined_evaluation": None,
            "final_answer": None,
            "has_more_questions": False,
            "complete": False,
            "errors": [],
            "retry_count": 0,
        }

        # Execute conditional edge
        result = workflow._should_generate_followup(state)

        # Assert finalize decision
        assert result == "finalize"

    async def test_should_generate_followup_returns_finalize_when_high_similarity(self):
        """Test that _should_generate_followup returns 'finalize' with high similarity."""
        # Setup
        mock_checkpointer = AsyncMock()
        mock_repos = self._create_mock_repos()
        mock_llm = AsyncMock()

        workflow = AdaptiveEvalInterruptWorkflow(
            checkpointer=mock_checkpointer,
            **mock_repos,
            llm=mock_llm,
        )

        # Create state with high similarity
        state: AdaptiveEvalInterruptState = {
            "interview_id": uuid4(),
            "question_id": uuid4(),
            "answer_text": "Test answer",
            "audio_file_path": None,
            "voice_metrics": None,
            "interview": None,
            "question": None,
            "parent_question_id": None,
            "is_followup": False,
            "iteration": 0,
            "answers": [],
            "evaluations": [MagicMock(similarity_score=0.85, final_score=85.0)],
            "cumulative_gaps": [],
            "followup_questions_generated": [],
            "current_followup_question": None,
            "waiting_for_answer": False,
            "resume_node": None,
            "combined_evaluation": None,
            "final_answer": None,
            "has_more_questions": False,
            "complete": False,
            "errors": [],
            "retry_count": 0,
        }

        # Execute conditional edge
        result = workflow._should_generate_followup(state)

        # Assert finalize decision
        assert result == "finalize"

    async def test_should_generate_followup_returns_generate_when_gaps_exist(self):
        """Test that _should_generate_followup returns 'generate_followup' when gaps exist."""
        # Setup
        mock_checkpointer = AsyncMock()
        mock_repos = self._create_mock_repos()
        mock_llm = AsyncMock()

        workflow = AdaptiveEvalInterruptWorkflow(
            checkpointer=mock_checkpointer,
            **mock_repos,
            llm=mock_llm,
        )

        # Create state with gaps and low similarity
        state: AdaptiveEvalInterruptState = {
            "interview_id": uuid4(),
            "question_id": uuid4(),
            "answer_text": "Test answer",
            "audio_file_path": None,
            "voice_metrics": None,
            "interview": None,
            "question": None,
            "parent_question_id": None,
            "is_followup": False,
            "iteration": 0,
            "answers": [],
            "evaluations": [MagicMock(similarity_score=0.55, final_score=60.0)],
            "cumulative_gaps": ["exception types", "custom exceptions"],
            "followup_questions_generated": [],
            "current_followup_question": None,
            "waiting_for_answer": False,
            "resume_node": None,
            "combined_evaluation": None,
            "final_answer": None,
            "has_more_questions": False,
            "complete": False,
            "errors": [],
            "retry_count": 0,
        }

        # Execute conditional edge
        result = workflow._should_generate_followup(state)

        # Assert generate_followup decision
        assert result == "generate_followup"

    def _create_mock_repos(self):
        """Create mock repository ports."""
        return {
            "answer_repo": AsyncMock(),
            "evaluation_repo": AsyncMock(),
            "interview_repo": AsyncMock(),
            "question_repo": AsyncMock(),
            "follow_up_repo": AsyncMock(),
        }
