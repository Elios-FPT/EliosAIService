"""Mock LLM adapter for development and testing."""

import random
from typing import Any
from uuid import UUID

from ...domain.models.answer import AnswerEvaluation
from ...domain.models.evaluation import FollowUpEvaluationContext
from ...domain.models.question import Question
from ...domain.ports.llm_port import LLMPort
from ...adapters.llm.comprehensive_models import ComprehensiveAnalysis, EvaluationOutput, EvaluationDimension, ConceptGapOutput, FollowUpOutput


class MockLLMAdapter(LLMPort):
    """Mock LLM adapter that returns realistic but fake responses.

    This adapter simulates LLM behavior for development and testing
    without requiring actual API calls to external services.
    """

    async def generate_questions_with_answers_and_rationales_batch(
        self,
        question_specs: list[dict[str, Any]],
        context: dict[str, Any],
    ) -> list[tuple[str, str, str]]:
        """Generate mock questions with ideal answers and rationales in a single call per spec.

        For each question_spec, generates question, ideal_answer, and rationale together
        in one call to ensure consistency.
        """
        question_sets = []
        for spec in question_specs:
            skill = spec.get("skill", "general knowledge")
            difficulty = spec.get("difficulty", "medium")
            exemplars = spec.get("exemplars") or []

            # Generate question
            question = f"Explain the trade-offs when using {skill} at {difficulty} level"
            if exemplars:
                question += f" [Generated with {len(exemplars)} exemplar(s)]"

            # Generate ideal answer (consistent with question)
            ideal_answer = f"""Mock ideal answer for '{question[:50]}...':
This demonstrates comprehensive understanding of {skill} at {difficulty} level with clear explanation,
relevant examples, and practical application. The answer covers all key aspects
including fundamental principles, real-world use cases, and potential edge cases.
It shows how {skill} can be effectively applied in various scenarios while considering
trade-offs and best practices."""

            # Generate rationale (consistent with question and answer)
            rationale = f"""This answer demonstrates mastery by covering fundamental concepts of {skill},
providing practical examples, and explaining the reasoning behind technical choices.
A weaker answer would miss these comprehensive details and fail to address the {difficulty}
level complexity required for this question."""

            question_sets.append((question, ideal_answer, rationale))

        return question_sets

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
        """Mock follow-up question generation with cumulative context.

        Args:
            parent_question: Original question text
            answer_text: Candidate's answer to parent question (or latest follow-up)
            missing_concepts: List of concepts missing from current answer
            severity: Gap severity
            order: Follow-up order in sequence
            cumulative_gaps: All unique gaps accumulated across follow-up cycle
            previous_follow_ups: Previous follow-up questions and answers for context

        Returns:
            Follow-up question text
        """
        # Use cumulative gaps if available, otherwise current missing concepts
        target_concepts = cumulative_gaps if cumulative_gaps else missing_concepts
        concepts_str = ', '.join(target_concepts[:2]) if target_concepts else "that concept"

        # Add order context to make questions unique per iteration
        if order == 1:
            return f"Can you elaborate more on {concepts_str}? Please provide specific examples."
        elif order == 2:
            return f"Let's dive deeper into {concepts_str}. Can you explain the underlying principles?"
        else:
            return f"Final question on {concepts_str}: How would you apply this in a real-world scenario?"

    async def generate_interview_recommendations(
        self,
        context: dict[str, Any],
    ) -> dict[str, list[str]]:
        """Generate mock personalized recommendations.

        Args:
            context: Interview context with evaluations and gap progression

        Returns:
            Dict with strengths, weaknesses, study topics, and technique tips
        """
        evaluations = context.get("evaluations", [])
        gap_progression = context.get("gap_progression", {})

        # Calculate average score from evaluations
        avg_score = (
            sum(e["score"] for e in evaluations) / len(evaluations)
            if evaluations
            else 75.0
        )

        # Generate recommendations based on score
        if avg_score >= 85:
            strengths = [
                "Exceptional understanding of core concepts",
                "Strong analytical and problem-solving skills",
                "Excellent communication and explanation abilities",
                "Good use of real-world examples and context",
            ]
            weaknesses = [
                "Could explore more edge cases in answers",
                "Consider discussing performance trade-offs more explicitly",
            ]
            study_topics = [
                "Advanced system design patterns",
                "Performance optimization techniques",
                "Security best practices",
            ]
            technique_tips = [
                "Continue your clear and structured communication style",
                "Consider adding more visual diagrams when explaining concepts",
            ]
        elif avg_score >= 70:
            strengths = [
                "Solid understanding of fundamental concepts",
                "Good ability to explain technical topics",
                "Relevant examples provided in most answers",
            ]
            weaknesses = [
                "Some technical depth missing in complex topics",
                "Could improve answer structure and organization",
                "Occasionally missed key concepts in follow-up questions",
            ]
            study_topics = [
                "Deep dive into data structures and algorithms",
                "Practice system design scenarios",
                "Review concurrency and threading concepts",
                "Study testing strategies and best practices",
            ]
            technique_tips = [
                "Use the STAR method (Situation, Task, Action, Result) for answering",
                "Practice explaining concepts at multiple levels of detail",
                "Slow down pace to ensure clarity in responses",
            ]
        else:
            strengths = [
                "Shows basic understanding of core concepts",
                "Willing to tackle challenging questions",
            ]
            weaknesses = [
                "Lacks depth in technical explanations",
                "Missing critical concepts in several answers",
                "Limited use of examples and practical applications",
                "Answer structure needs improvement",
            ]
            study_topics = [
                "Review fundamental programming concepts thoroughly",
                "Practice basic data structures and algorithms",
                "Study common design patterns",
                "Build small projects to reinforce learning",
                "Review language-specific best practices",
            ]
            technique_tips = [
                "Practice explaining concepts out loud before answering",
                "Use pen and paper to diagram ideas during preparation",
                "Structure answers: state the concept, explain it, give an example",
                "Take time to think before responding - silence is acceptable",
                "Ask clarifying questions if prompt is unclear",
            ]

        # Add gap-specific recommendations
        if gap_progression.get("gaps_remaining", 0) > 3:
            study_topics.append(
                "Focus on concepts that remained unclear after follow-up questions"
            )

        return {
            "strengths": strengths,
            "weaknesses": weaknesses,
            "study_topics": study_topics,
            "technique_tips": technique_tips,
        }

    async def analyze_answer_comprehensive(
        self,
        question: Question,
        answer_text: str,
        context: dict[str, Any],
        followup_context: FollowUpEvaluationContext | None = None,
    ) -> ComprehensiveAnalysis:
        """Generate mock comprehensive analysis (evaluation + gaps + follow-up)."""
        # Calculate base score
        attempt_number = followup_context.attempt_number if followup_context else 1
        base_score = random.uniform(70.0, 95.0)
        if attempt_number > 1:
            attempt_penalty = (attempt_number - 1) * 5
            base_score = max(50.0, base_score - attempt_penalty)

        # Create evaluation dimensions
        dimensions = [
            EvaluationDimension(
                dimension_name="technical_accuracy",
                score=min(40.0, base_score * 0.4),
                reasoning="Mock: Technical accuracy assessment"
            ),
            EvaluationDimension(
                dimension_name="depth_of_understanding",
                score=min(30.0, base_score * 0.3),
                reasoning="Mock: Depth of understanding assessment"
            ),
            EvaluationDimension(
                dimension_name="clarity_of_communication",
                score=min(20.0, base_score * 0.2),
                reasoning="Mock: Clarity assessment"
            ),
            EvaluationDimension(
                dimension_name="practical_application",
                score=min(10.0, base_score * 0.1),
                reasoning="Mock: Practical application assessment"
            ),
        ]

        # Create evaluation output
        evaluation = EvaluationOutput(
            dimensions=dimensions,
            total_score=base_score,
            strengths=["Clear explanation", "Good examples"] if base_score >= 75 else ["Basic understanding"],
            weaknesses=["Could be more detailed"] if base_score >= 75 else ["Lacks depth", "Missing key concepts"],
            improvement_suggestions=["Add more examples", "Elaborate on details"],
            reasoning=f"Mock comprehensive evaluation: Score {base_score:.1f}/100"
        )

        # Create gaps (simulate some gaps for lower scores)
        gaps = []
        if base_score < 80:
            gaps.append(ConceptGapOutput(
                concept="Advanced concepts",
                severity="moderate",
                explanation="Mock: Missing advanced concepts"
            ))

        # Create follow-up (if gaps exist and attempt < 3)
        follow_up = None
        if gaps and attempt_number < 3:
            follow_up = FollowUpOutput(
                question_text=f"Can you elaborate more on {gaps[0].concept}?",
                reason="Mock: Major gaps detected",
                target_gaps=[gaps[0].concept]
            )

        return ComprehensiveAnalysis(
            evaluation=evaluation,
            gaps=gaps,
            follow_up=follow_up,
            confidence=0.85
        )
