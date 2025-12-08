"""LLM (Large Language Model) port interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any
from uuid import UUID

from ..models.evaluation import FollowUpEvaluationContext
from ..models.feedback_result import FeedbackResult, InputType
from ..models.question import Question

if TYPE_CHECKING:
    from ...adapters.llm.comprehensive_models import ComprehensiveAnalysis


class LLMPort(ABC):
    """Interface for Large Language Model providers.

    This port abstracts LLM interactions, allowing easy switching between
    providers like OpenAI, Claude, Llama, etc.
    """

    @abstractmethod
    async def generate_followup_question(
        self,
        parent_question: str,
        answer_text: str,
        missing_concepts: list[str],
        severity: str,
        order: int,
        cumulative_gaps: list[str] | None = None,
        previous_follow_ups: list[dict[str, Any]] | None = None,
    ) -> str:
        """Generate targeted follow-up question.

        Args:
            parent_question: Original question text
            answer_text: Candidate's answer to parent question (or latest follow-up)
            missing_concepts: List of concepts missing from current answer
            severity: Gap severity ("minor" | "moderate" | "major")
            order: Follow-up order in sequence (1, 2, 3, ...)
            cumulative_gaps: All unique gaps accumulated across follow-up cycle (optional)
            previous_follow_ups: Previous follow-up questions and answers for context (optional)

        Returns:
            Follow-up question text
        """
        pass

    @abstractmethod
    async def generate_interview_recommendations(
        self,
        context: dict[str, Any],
    ) -> dict[str, list[str]]:
        """Generate personalized interview recommendations.

        Args:
            context: Interview context including:
                - interview_id: str
                - total_answers: int
                - gap_progression: dict (gaps filled, remaining, etc.)
                - evaluations: list[dict] (scores, strengths, weaknesses per answer)

        Returns:
            Dict with keys:
                - strengths: list[str] (top 3-5 strengths)
                - weaknesses: list[str] (top 3-5 weaknesses)
                - study_topics: list[str] (topic-specific study recommendations)
                - technique_tips: list[str] (voice, pacing, structure tips)
        """
        pass

    @abstractmethod
    async def generate_questions_with_answers_and_rationales_batch(
        self,
        question_specs: list[dict[str, Any]],
        context: dict[str, Any],
    ) -> list[tuple[str, str, str]]:
        """Generate questions with ideal answers and rationales in a single LLM call per spec.

        For each question_spec, generates question, ideal_answer, and rationale together
        in one LLM call to ensure consistency.

        Args:
            question_specs: List of question specifications. Each dict should contain:
                - skill: str - Target skill to test
                - difficulty: str - Question difficulty level
                - exemplars: list[dict[str, Any]] | None - Optional exemplar questions
            context: Interview context (CV analysis, etc.)

        Returns:
            List of tuples (question_text, ideal_answer, rationale) in the same order
            as question_specs. Each tuple represents one complete question set generated
            in a single LLM call.
        """
        pass

    @abstractmethod
    async def analyze_answer_comprehensive(
        self,
        question: Question,
        answer_text: str,
        context: dict[str, Any],
        followup_context: FollowUpEvaluationContext | None = None,
    ) -> ComprehensiveAnalysis:
        """Unified answer analysis (evaluation + gaps + follow-up).

        Consolidates 3 LLM calls into 1 for 46% latency reduction (Phase 2 optimization).
        Uses chain-of-thought prompting for multi-task quality.

        Args:
            question: Question entity with ideal_answer
            answer_text: Candidate's answer
            context: Interview context (interview_id, candidate_id, conversation_history)
            followup_context: Follow-up context if applicable (attempt_number, previous_scores, gaps)

        Returns:
            ComprehensiveAnalysis with evaluation + gaps + follow_up

        Raises:
            ValueError: If question has no ideal_answer
            RuntimeError: If LLM call fails after retries
        """
        pass

    @abstractmethod
    async def analyze_feedback(
        self,
        input_type: InputType,
        feedback_input: str,
        context: dict[str, Any] | None = None,
    ) -> FeedbackResult:
        """Analyze feedback using DB prompts.

        Args:
            input_type: CV or CODE (INTERVIEW not supported)
            feedback_input: JSON string with entity content
            context: Optional context (user_id, entity_id, etc.)

        Returns:
            CVFeedbackResult or CodeReviewFeedbackResult

        Raises:
            ValueError: If input_type is INTERVIEW or feedback_input is invalid
            RuntimeError: If LLM call fails
        """
        pass