"""Tests for CompleteInterviewUseCase (refactored - atomic operation)."""

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from src.application.dto.detailed_feedback_dto import (
    DetailedInterviewFeedback,
    EvaluationDetail,
    QuestionDetailedFeedback,
)
from src.application.dto.interview_completion_dto import InterviewCompletionResult
from src.application.use_cases.complete_interview import CompleteInterviewUseCase
from src.domain.models.answer import Answer
from src.domain.models.evaluation import ConceptGap, Evaluation, GapSeverity
from src.domain.models.interview import InterviewStatus


class TestCompleteInterviewUseCase:
    """Test interview completion with summary generation (atomic operation)."""

    @pytest.mark.asyncio
    async def test_complete_interview_generates_summary(
        self,
        sample_interview_adaptive,
        sample_question_with_ideal_answer,
        mock_interview_repo,
        mock_answer_repo,
        mock_question_repo,
        mock_follow_up_question_repo,
        mock_evaluation_repo,
        mock_llm,
    ):
        """Test complete interview always generates summary (atomic operation)."""
        # Setup interview in EVALUATING status
        sample_interview_adaptive.status = InterviewStatus.EVALUATING
        await mock_interview_repo.save(sample_interview_adaptive)

        # Create question
        # Workaround for question_ids (removed in v0.4.0, using __dict__ workaround)
        question_ids = getattr(sample_interview_adaptive, "question_ids", None) or sample_interview_adaptive.__dict__.get("question_ids", [uuid4()])
        q1_id = question_ids[0] if question_ids else uuid4()
        q1 = sample_question_with_ideal_answer
        q1.id = q1_id
        await mock_question_repo.save(q1)

        # Create answer
        answer1 = Answer(
            interview_id=sample_interview_adaptive.id,
            question_id=q1_id,
            candidate_id=sample_interview_adaptive.candidate_id,
            text="Good answer about recursion",
            is_voice=False,
        )
        await mock_answer_repo.save(answer1)

        # Create evaluation (NEW: separate entity) with voice metrics support
        evaluation1 = Evaluation(
            answer_id=answer1.id,
            raw_score=85.0,
            theoretical_score=85.0,  # Phase 01: Added field
            speaking_score=None,  # Text-only answer
            final_score=85.0,
            completeness=0.9,
            relevance=0.95,
            sentiment="confident",
            reasoning="Strong answer",
            strengths=["Clear explanation"],
            weaknesses=[],
        )
        await mock_evaluation_repo.save(evaluation1)

        # Execute use case (NEW: all dependencies required)
        mock_event_publisher = MagicMock()
        use_case = CompleteInterviewUseCase(
            interview_repository=mock_interview_repo,
            answer_repository=mock_answer_repo,
            question_repository=mock_question_repo,
            follow_up_question_repository=mock_follow_up_question_repo,
            evaluation_repository=mock_evaluation_repo,
            llm=mock_llm,
            event_publisher=mock_event_publisher,
        )

        # NEW: Returns InterviewCompletionResult DTO
        result = await use_case.execute(interview_id=sample_interview_adaptive.id)

        # Verify return type
        assert isinstance(result, InterviewCompletionResult)
        assert result.interview.status == InterviewStatus.COMPLETE
        assert result.summary is not None  # Always present

        # Verify summary is DetailedInterviewFeedback DTO
        assert isinstance(result.summary, DetailedInterviewFeedback)
        assert result.summary.interview_id == sample_interview_adaptive.id
        assert result.summary.overall_score >= 0.0
        assert isinstance(result.summary.strengths, list)
        assert isinstance(result.summary.weaknesses, list)
        # sample_interview_adaptive has 3 question_ids by default
        assert result.summary.total_questions == 3
        # Only 1 question has answer/evaluation
        assert len(result.summary.question_feedback) == 1

        # Verify summary stored in metadata
        assert result.interview.plan_metadata is not None
        assert "completion_summary" in result.interview.plan_metadata

    @pytest.mark.asyncio
    async def test_complete_interview_not_found(
        self,
        mock_interview_repo,
        mock_answer_repo,
        mock_question_repo,
        mock_follow_up_question_repo,
        mock_evaluation_repo,
        mock_llm,
    ):
        """Test error when interview not found."""
        mock_event_publisher = MagicMock()
        use_case = CompleteInterviewUseCase(
            interview_repository=mock_interview_repo,
            answer_repository=mock_answer_repo,
            question_repository=mock_question_repo,
            follow_up_question_repository=mock_follow_up_question_repo,
            evaluation_repository=mock_evaluation_repo,
            llm=mock_llm,
            event_publisher=mock_event_publisher,
        )

        with pytest.raises(ValueError, match="Interview .* not found"):
            await use_case.execute(interview_id=uuid4())

    @pytest.mark.asyncio
    async def test_complete_interview_invalid_status(
        self,
        sample_interview_adaptive,
        mock_interview_repo,
        mock_answer_repo,
        mock_question_repo,
        mock_follow_up_question_repo,
        mock_evaluation_repo,
        mock_llm,
    ):
        """Test error when interview not in valid 'in process' status."""
        # Set status to COMPLETE (invalid for completion - already completed)
        sample_interview_adaptive.status = InterviewStatus.COMPLETE
        await mock_interview_repo.save(sample_interview_adaptive)

        mock_event_publisher = MagicMock()
        use_case = CompleteInterviewUseCase(
            interview_repository=mock_interview_repo,
            answer_repository=mock_answer_repo,
            question_repository=mock_question_repo,
            follow_up_question_repository=mock_follow_up_question_repo,
            evaluation_repository=mock_evaluation_repo,
            llm=mock_llm,
            event_publisher=mock_event_publisher,
        )

        with pytest.raises(ValueError, match="Cannot complete interview with status"):
            await use_case.execute(interview_id=sample_interview_adaptive.id)

    @pytest.mark.asyncio
    async def test_complete_interview_with_multiple_evaluations(
        self,
        sample_interview_adaptive,
        sample_question_with_ideal_answer,
        mock_interview_repo,
        mock_answer_repo,
        mock_question_repo,
        mock_follow_up_question_repo,
        mock_evaluation_repo,
        mock_llm,
    ):
        """Test complete with multiple evaluated answers."""
        sample_interview_adaptive.status = InterviewStatus.EVALUATING
        await mock_interview_repo.save(sample_interview_adaptive)

        # Create 3 questions and answers
        # Workaround for question_ids (removed in v0.4.0, using __dict__ workaround)
        question_ids = getattr(sample_interview_adaptive, "question_ids", None) or sample_interview_adaptive.__dict__.get("question_ids", [uuid4(), uuid4(), uuid4()])
        for idx, q_id in enumerate(question_ids):
            question = sample_question_with_ideal_answer
            question.id = q_id
            await mock_question_repo.save(question)

            answer = Answer(
                interview_id=sample_interview_adaptive.id,
                question_id=q_id,
                candidate_id=sample_interview_adaptive.candidate_id,
                text=f"Answer {idx + 1}",
                is_voice=False,
            )
            await mock_answer_repo.save(answer)

            evaluation = Evaluation(
                answer_id=answer.id,
                raw_score=80.0 + (idx * 5),
                theoretical_score=80.0 + (idx * 5),  # Phase 01: Added field
                speaking_score=None,  # Text-only answer
                final_score=80.0 + (idx * 5),
                completeness=0.8,
                relevance=0.9,
                sentiment="confident",
                reasoning=f"Good answer {idx + 1}",
                strengths=[f"Strength {idx + 1}"],
                weaknesses=[],
            )
            await mock_evaluation_repo.save(evaluation)

        mock_event_publisher = MagicMock()
        use_case = CompleteInterviewUseCase(
            interview_repository=mock_interview_repo,
            answer_repository=mock_answer_repo,
            question_repository=mock_question_repo,
            follow_up_question_repository=mock_follow_up_question_repo,
            evaluation_repository=mock_evaluation_repo,
            llm=mock_llm,
            event_publisher=mock_event_publisher,
        )

        result = await use_case.execute(interview_id=sample_interview_adaptive.id)

        assert result.interview.status == InterviewStatus.COMPLETE
        assert isinstance(result.summary, DetailedInterviewFeedback)
        assert result.summary.total_questions == 3
        assert result.summary.overall_score > 0.0
        assert len(result.summary.question_feedback) == 3

        # Verify each question feedback is typed
        for qf in result.summary.question_feedback:
            assert isinstance(qf, QuestionDetailedFeedback)
            assert isinstance(qf.main_evaluation, EvaluationDetail)

    @pytest.mark.asyncio
    async def test_complete_interview_initializes_metadata_if_none(
        self,
        sample_interview_adaptive,
        sample_question_with_ideal_answer,
        mock_interview_repo,
        mock_answer_repo,
        mock_question_repo,
        mock_follow_up_question_repo,
        mock_evaluation_repo,
        mock_llm,
    ):
        """Test plan_metadata initialized if None before storing summary."""
        sample_interview_adaptive.status = InterviewStatus.EVALUATING
        sample_interview_adaptive.plan_metadata = None  # Force None
        await mock_interview_repo.save(sample_interview_adaptive)

        # Workaround for question_ids (removed in v0.4.0, using __dict__ workaround)
        question_ids = getattr(sample_interview_adaptive, "question_ids", None) or sample_interview_adaptive.__dict__.get("question_ids", [uuid4()])
        q1_id = question_ids[0] if question_ids else uuid4()
        q1 = sample_question_with_ideal_answer
        q1.id = q1_id
        await mock_question_repo.save(q1)

        answer = Answer(
            interview_id=sample_interview_adaptive.id,
            question_id=q1_id,
            candidate_id=sample_interview_adaptive.candidate_id,
            text="Answer",
            is_voice=False,
        )
        await mock_answer_repo.save(answer)

        evaluation = Evaluation(
            answer_id=answer.id,
            raw_score=75.0,
            theoretical_score=75.0,  # Phase 01: Added field
            speaking_score=None,  # Text-only answer
            final_score=75.0,
            completeness=0.8,
            relevance=0.85,
        )
        await mock_evaluation_repo.save(evaluation)

        mock_event_publisher = MagicMock()
        use_case = CompleteInterviewUseCase(
            interview_repository=mock_interview_repo,
            answer_repository=mock_answer_repo,
            question_repository=mock_question_repo,
            follow_up_question_repository=mock_follow_up_question_repo,
            evaluation_repository=mock_evaluation_repo,
            llm=mock_llm,
            event_publisher=mock_event_publisher,
        )

        result = await use_case.execute(interview_id=sample_interview_adaptive.id)

        # Verify metadata initialized
        assert result.interview.plan_metadata is not None
        assert "completion_summary" in result.interview.plan_metadata

    @pytest.mark.asyncio
    async def test_complete_interview_preserves_existing_metadata(
        self,
        sample_interview_adaptive,
        sample_question_with_ideal_answer,
        mock_interview_repo,
        mock_answer_repo,
        mock_question_repo,
        mock_follow_up_question_repo,
        mock_evaluation_repo,
        mock_llm,
    ):
        """Test existing plan_metadata preserved when adding summary."""
        sample_interview_adaptive.status = InterviewStatus.EVALUATING
        sample_interview_adaptive.plan_metadata = {
            "n": 3,
            "strategy": "adaptive_planning_v1",
            "custom_field": "preserved",
        }
        await mock_interview_repo.save(sample_interview_adaptive)

        # Workaround for question_ids (removed in v0.4.0, using __dict__ workaround)
        question_ids = getattr(sample_interview_adaptive, "question_ids", None) or sample_interview_adaptive.__dict__.get("question_ids", [uuid4()])
        q1_id = question_ids[0] if question_ids else uuid4()
        q1 = sample_question_with_ideal_answer
        q1.id = q1_id
        await mock_question_repo.save(q1)

        answer = Answer(
            interview_id=sample_interview_adaptive.id,
            question_id=q1_id,
            candidate_id=sample_interview_adaptive.candidate_id,
            text="Answer",
            is_voice=False,
        )
        await mock_answer_repo.save(answer)

        evaluation = Evaluation(
            answer_id=answer.id,
            raw_score=75.0,
            theoretical_score=75.0,  # Phase 01: Added field
            speaking_score=None,  # Text-only answer
            final_score=75.0,
            completeness=0.8,
            relevance=0.85,
        )
        await mock_evaluation_repo.save(evaluation)

        mock_event_publisher = MagicMock()
        use_case = CompleteInterviewUseCase(
            interview_repository=mock_interview_repo,
            answer_repository=mock_answer_repo,
            question_repository=mock_question_repo,
            follow_up_question_repository=mock_follow_up_question_repo,
            evaluation_repository=mock_evaluation_repo,
            llm=mock_llm,
            event_publisher=mock_event_publisher,
        )

        result = await use_case.execute(interview_id=sample_interview_adaptive.id)

        # Verify existing metadata preserved
        assert result.interview.plan_metadata["n"] == 3
        assert result.interview.plan_metadata["strategy"] == "adaptive_planning_v1"
        assert result.interview.plan_metadata["custom_field"] == "preserved"
        assert "completion_summary" in result.interview.plan_metadata

    @pytest.mark.asyncio
    async def test_complete_interview_returns_dto_not_tuple(
        self,
        sample_interview_adaptive,
        sample_question_with_ideal_answer,
        mock_interview_repo,
        mock_answer_repo,
        mock_question_repo,
        mock_follow_up_question_repo,
        mock_evaluation_repo,
        mock_llm,
    ):
        """Test return value is InterviewCompletionResult DTO, not tuple."""
        sample_interview_adaptive.status = InterviewStatus.EVALUATING
        await mock_interview_repo.save(sample_interview_adaptive)

        # Workaround for question_ids (removed in v0.4.0, using __dict__ workaround)
        question_ids = getattr(sample_interview_adaptive, "question_ids", None) or sample_interview_adaptive.__dict__.get("question_ids", [uuid4()])
        q1_id = question_ids[0] if question_ids else uuid4()
        q1 = sample_question_with_ideal_answer
        q1.id = q1_id
        await mock_question_repo.save(q1)

        answer = Answer(
            interview_id=sample_interview_adaptive.id,
            question_id=q1_id,
            candidate_id=sample_interview_adaptive.candidate_id,
            text="Answer",
            is_voice=False,
        )
        await mock_answer_repo.save(answer)

        evaluation = Evaluation(
            answer_id=answer.id,
            raw_score=75.0,
            theoretical_score=75.0,  # Phase 01: Added field
            speaking_score=None,  # Text-only answer
            final_score=75.0,
            completeness=0.8,
            relevance=0.85,
        )
        await mock_evaluation_repo.save(evaluation)

        mock_event_publisher = MagicMock()
        use_case = CompleteInterviewUseCase(
            interview_repository=mock_interview_repo,
            answer_repository=mock_answer_repo,
            question_repository=mock_question_repo,
            follow_up_question_repository=mock_follow_up_question_repo,
            evaluation_repository=mock_evaluation_repo,
            llm=mock_llm,
            event_publisher=mock_event_publisher,
        )

        result = await use_case.execute(interview_id=sample_interview_adaptive.id)

        # Verify DTO structure (NOT tuple)
        assert isinstance(result, InterviewCompletionResult)
        assert hasattr(result, "interview")
        assert hasattr(result, "summary")
        assert result.interview is not None
        assert result.summary is not None  # Always present

    @pytest.mark.asyncio
    async def test_complete_interview_from_questioning_status(
        self,
        sample_interview_adaptive,
        sample_question_with_ideal_answer,
        mock_interview_repo,
        mock_answer_repo,
        mock_question_repo,
        mock_follow_up_question_repo,
        mock_evaluation_repo,
        mock_llm,
    ):
        """Test complete interview from QUESTIONING status (auto-transitions to EVALUATING)."""
        # Setup interview in QUESTIONING status
        sample_interview_adaptive.status = InterviewStatus.QUESTIONING
        await mock_interview_repo.save(sample_interview_adaptive)

        # Create question and answer
        q1_id = getattr(sample_interview_adaptive, "question_ids", [uuid4()])[0]
        q1 = sample_question_with_ideal_answer
        q1.id = q1_id
        await mock_question_repo.save(q1)

        answer1 = Answer(
            interview_id=sample_interview_adaptive.id,
            question_id=q1_id,
            candidate_id=sample_interview_adaptive.candidate_id,
            text="Good answer",
            is_voice=False,
        )
        await mock_answer_repo.save(answer1)

        evaluation1 = Evaluation(
            answer_id=answer1.id,
            raw_score=85.0,
            theoretical_score=85.0,
            speaking_score=None,
            final_score=85.0,
            completeness=0.9,
            relevance=0.95,
            sentiment="confident",
            reasoning="Strong answer",
            strengths=["Clear explanation"],
            weaknesses=[],
        )
        await mock_evaluation_repo.save(evaluation1)

        mock_event_publisher = MagicMock()
        use_case = CompleteInterviewUseCase(
            interview_repository=mock_interview_repo,
            answer_repository=mock_answer_repo,
            question_repository=mock_question_repo,
            follow_up_question_repository=mock_follow_up_question_repo,
            evaluation_repository=mock_evaluation_repo,
            llm=mock_llm,
            event_publisher=mock_event_publisher,
        )

        result = await use_case.execute(interview_id=sample_interview_adaptive.id)

        # Verify interview completed successfully
        assert result.interview.status == InterviewStatus.COMPLETE
        assert isinstance(result.summary, DetailedInterviewFeedback)
        # Verify status was transitioned from QUESTIONING → EVALUATING → COMPLETE
        # (The interview in result should be COMPLETE)

    @pytest.mark.asyncio
    async def test_complete_interview_from_follow_up_status(
        self,
        sample_interview_adaptive,
        sample_question_with_ideal_answer,
        mock_interview_repo,
        mock_answer_repo,
        mock_question_repo,
        mock_follow_up_question_repo,
        mock_evaluation_repo,
        mock_llm,
    ):
        """Test complete interview from FOLLOW_UP status (auto-transitions to EVALUATING)."""
        # Setup interview in FOLLOW_UP status
        sample_interview_adaptive.status = InterviewStatus.FOLLOW_UP
        await mock_interview_repo.save(sample_interview_adaptive)

        # Create question and answer
        q1_id = getattr(sample_interview_adaptive, "question_ids", [uuid4()])[0]
        q1 = sample_question_with_ideal_answer
        q1.id = q1_id
        await mock_question_repo.save(q1)

        answer1 = Answer(
            interview_id=sample_interview_adaptive.id,
            question_id=q1_id,
            candidate_id=sample_interview_adaptive.candidate_id,
            text="Good answer",
            is_voice=False,
        )
        await mock_answer_repo.save(answer1)

        evaluation1 = Evaluation(
            answer_id=answer1.id,
            raw_score=85.0,
            theoretical_score=85.0,
            speaking_score=None,
            final_score=85.0,
            completeness=0.9,
            relevance=0.95,
            sentiment="confident",
            reasoning="Strong answer",
            strengths=["Clear explanation"],
            weaknesses=[],
        )
        await mock_evaluation_repo.save(evaluation1)

        mock_event_publisher = MagicMock()
        use_case = CompleteInterviewUseCase(
            interview_repository=mock_interview_repo,
            answer_repository=mock_answer_repo,
            question_repository=mock_question_repo,
            follow_up_question_repository=mock_follow_up_question_repo,
            evaluation_repository=mock_evaluation_repo,
            llm=mock_llm,
            event_publisher=mock_event_publisher,
        )

        result = await use_case.execute(interview_id=sample_interview_adaptive.id)

        # Verify interview completed successfully
        assert result.interview.status == InterviewStatus.COMPLETE
        assert isinstance(result.summary, DetailedInterviewFeedback)
        # Verify status was transitioned from FOLLOW_UP → EVALUATING → COMPLETE
