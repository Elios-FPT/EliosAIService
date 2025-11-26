"""Shared fixtures for parity tests between legacy and workflow paths."""
import pytest
from typing import Any
from uuid import UUID, uuid4
from unittest.mock import AsyncMock, MagicMock

from src.domain.models.interview import Interview
from src.domain.models.question import Question, QuestionType, Difficulty
from src.domain.models.cv_analysis import CVAnalysis
from src.application.workflows.interview_conversation_workflow import (
    InterviewConversationWorkflow,
)
from src.infrastructure.dependency_injection.container import Container


@pytest.fixture
async def test_interview(async_session):
    """Create test interview with questions."""
    from src.adapters.persistence.postgres.interview_repository import (
        PostgresInterviewRepository,
    )
    from src.adapters.persistence.postgres.question_repository import (
        PostgresQuestionRepository,
    )
    from src.adapters.persistence.postgres.cv_analysis_repository import (
        PostgresCVAnalysisRepository,
    )

    # Create repositories
    interview_repo = PostgresInterviewRepository(async_session)
    question_repo = PostgresQuestionRepository(async_session)
    cv_repo = PostgresCVAnalysisRepository(async_session)

    # Create CV analysis
    cv_analysis = CVAnalysis(
        id=uuid4(),
        candidate_id=uuid4(),
        filename="test-cv.pdf",
        raw_text="Python developer with 5 years experience",
        extracted_skills=["Python", "FastAPI", "PostgreSQL"],
    )
    await cv_repo.save(cv_analysis)

    # Create interview
    interview = Interview(
        id=uuid4(),
        candidate_id=cv_analysis.candidate_id,
        cv_analysis_id=cv_analysis.id,
        position="Senior Python Developer",
    )
    await interview_repo.save(interview)

    # Create questions
    questions = [
        Question(
            id=uuid4(),
            text="Explain async/await in Python and its benefits",
            question_type=QuestionType.TECHNICAL,
            difficulty=Difficulty.MEDIUM,
            skills=["Python"],
            ideal_answer="Async/await enables asynchronous programming using coroutines...",
        ),
        Question(
            id=uuid4(),
            text="What is the Global Interpreter Lock (GIL) in Python?",
            question_type=QuestionType.TECHNICAL,
            difficulty=Difficulty.HARD,
            skills=["Python"],
            ideal_answer="The GIL is a mutex that protects access to Python objects...",
        ),
        Question(
            id=uuid4(),
            text="Describe the decorator pattern and provide an example",
            question_type=QuestionType.DESIGN,
            difficulty=Difficulty.MEDIUM,
            skills=["Python", "Design Patterns"],
            ideal_answer="Decorators allow modifying function behavior without changing code...",
        ),
    ]

    for question in questions:
        await question_repo.save(question)
        await interview_repo.add_question(
            interview_id=interview.id,
            question_id=question.id,
            sequence_order=len(interview.question_ids),
        )

    await async_session.commit()

    return {
        "interview": interview,
        "questions": questions,
        "cv_analysis": cv_analysis,
    }


@pytest.fixture
def mock_websocket():
    """Create mock WebSocket for legacy path testing."""
    mock = MagicMock()
    mock.sent_messages = []

    async def send_json(data: dict[str, Any]) -> None:
        mock.sent_messages.append(data)

    mock.send_json = AsyncMock(side_effect=send_json)
    return mock


@pytest.fixture
async def workflow_runner(async_session):
    """Run interview through LangGraph workflow."""

    async def _run(
        interview_id: UUID, answers: list[str], container: Container
    ) -> dict[str, Any]:
        """Execute workflow path and collect results."""
        # Create workflow instance
        workflow = InterviewConversationWorkflow(
            interview_repo=container.interview_repository(async_session),
            question_repo=container.question_repository(async_session),
            evaluation_repo=container.evaluation_repository(async_session),
            followup_repo=container.followup_question_repository(async_session),
            langchain_adapter=container.langchain_adapter(async_session),
            checkpointer=container.async_postgres_saver(async_session),
        )

        # Start session
        start_result = await workflow.start_session(
            interview_id=interview_id,
            candidate_id=uuid4(),
        )
        thread_id = start_result["thread_id"]

        # Process answers
        results = []
        for answer_text in answers:
            result = await workflow.process_answer(
                thread_id=thread_id,
                answer_text=answer_text,
            )
            results.append(result)

        # Extract structured results
        evaluations = []
        followups = []
        questions_sent = []

        for result in results:
            # Extract evaluation if present
            if result.get("evaluation"):
                evaluations.append(result["evaluation"])

            # Extract follow-up question if present
            if result.get("follow_up_question"):
                followups.append(result["follow_up_question"])

            # Extract main question if present
            if result.get("question"):
                questions_sent.append(result["question"])

        return {
            "results": results,
            "evaluations": evaluations,
            "followups": followups,
            "questions": questions_sent,
        }

    return _run


def extract_gap_concepts(evaluation: dict[str, Any]) -> set[str]:
    """Extract gap concepts from evaluation dict."""
    gaps = evaluation.get("gaps", [])
    if isinstance(gaps, list):
        return {gap.get("concept", "") for gap in gaps if not gap.get("resolved", False)}
    return set()


def compare_scores(legacy_score: float, workflow_score: float, tolerance: float = 2.0) -> bool:
    """Compare evaluation scores within tolerance."""
    return abs(legacy_score - workflow_score) <= tolerance


def compare_feedback_fields(legacy_eval: dict[str, Any], workflow_eval: dict[str, Any]) -> dict[str, bool]:
    """Compare feedback field presence and structure."""
    return {
        "has_feedback": bool(legacy_eval.get("feedback")) == bool(workflow_eval.get("feedback")),
        "has_strengths": isinstance(legacy_eval.get("strengths"), list) == isinstance(workflow_eval.get("strengths"), list),
        "has_weaknesses": isinstance(legacy_eval.get("weaknesses"), list) == isinstance(workflow_eval.get("weaknesses"), list),
        "has_gaps": isinstance(legacy_eval.get("gaps"), list) == isinstance(workflow_eval.get("gaps"), list),
    }
