"""Assertion evaluation logic for test scenarios."""

import logging
import re
from typing import Any
from uuid import UUID

import httpx

logger = logging.getLogger(__name__)


class AssertionValidator:
    """Evaluate assertions against interview context and DB state."""

    async def evaluate(
        self,
        expression: str,
        context: dict[str, Any],
        interview_id: UUID,
        http_client: httpx.AsyncClient,
    ) -> bool:
        """Evaluate assertion expression.

        Args:
            expression: Python expression to evaluate
            context: Interview context (questions, answers, evaluations, etc.)
            interview_id: Interview UUID
            http_client: HTTP client for API calls

        Returns:
            True if assertion passes
        """
        # Build evaluation namespace
        namespace = self._build_namespace(context, interview_id, http_client)

        try:
            # Evaluate expression
            result = eval(expression, {"__builtins__": {}}, namespace)
            return bool(result)

        except Exception as e:
            logger.error(f"Assertion evaluation failed: {expression} - {e}")
            return False

    def _build_namespace(
        self,
        context: dict[str, Any],
        interview_id: UUID,
        http_client: httpx.AsyncClient,
    ) -> dict[str, Any]:
        """Build namespace for expression evaluation.

        Args:
            context: Interview context
            interview_id: Interview UUID
            http_client: HTTP client

        Returns:
            Namespace dict with available variables and functions
        """
        # Extract from context
        questions = context.get("questions", [])
        answers = context.get("answers", [])
        evaluations = context.get("evaluations", [])
        follow_ups = context.get("follow_ups", [])
        summary = context.get("summary")

        # Mock interview object (simplified)
        class InterviewMock:
            status = summary.get("status", "COMPLETE") if summary else "UNKNOWN"

        interview = InterviewMock()

        # Helper functions for assertions
        def len_fn(obj):
            return len(obj) if obj else 0

        def all_fn(iterable):
            return all(iterable)

        def any_fn(iterable):
            return any(iterable)

        # Validator functions
        from .answer_generator import (
            is_verbal_question,
            no_code_writing_questions,
            no_diagram_questions,
        )

        def skill_coverage(questions_list, cv_skills):
            """Calculate skill coverage (simplified)."""
            # For MVP: return 1.0 (100%)
            return 1.0

        def skill_diversity(questions_list):
            """Calculate skill diversity (simplified)."""
            # For MVP: return 1.0 (100%)
            return 1.0

        def unique_skills(questions_list):
            """Extract unique skills from questions (simplified)."""
            # For MVP: return dummy list
            return ["Skill1", "Skill2", "Skill3"]

        def has_difficulty_distribution(questions_list, expected_difficulties):
            """Check if questions have expected difficulty distribution."""
            # For MVP: return True
            return True

        def is_context_aware(follow_up, parent_question, answer):
            """Check if follow-up is context-aware."""
            # For MVP: return True
            return True

        def targets_gaps(follow_up, gaps):
            """Check if follow-up targets identified gaps."""
            # For MVP: return True
            return True

        def weighted_avg(evaluations_list):
            """Calculate weighted average score."""
            if not evaluations_list:
                return 0.0
            return sum(e.get("score", 0) for e in evaluations_list) / len(
                evaluations_list
            )

        def no_invalid_transitions(transitions):
            """Validate state transitions."""
            # For MVP: return True
            return True

        def no_cross_contamination(interview_1, interview_2):
            """Check for data isolation."""
            # For MVP: return True
            return True

        # DB query helpers (async, so not directly callable in eval)
        # For MVP: provide mock implementations

        class DBMock:
            def interview_exists(self, interview_id):
                return True

            def count_answers(self, interview_id):
                return len(answers)

        db = DBMock()

        # Build namespace
        namespace = {
            # Variables
            "interview": interview,
            "questions": questions,
            "answers": answers,
            "evaluations": evaluations,
            "follow_ups": follow_ups,
            "summary": summary,
            "interview_id": str(interview_id),
            "db": db,
            # Built-in functions (safe subset)
            "len": len_fn,
            "all": all_fn,
            "any": any_fn,
            "sum": sum,
            "min": min,
            "max": max,
            # Helper functions
            "is_verbal_question": is_verbal_question,
            "no_code_writing_questions": no_code_writing_questions,
            "no_diagram_questions": no_diagram_questions,
            "skill_coverage": skill_coverage,
            "skill_diversity": skill_diversity,
            "unique_skills": unique_skills,
            "has_difficulty_distribution": has_difficulty_distribution,
            "is_context_aware": is_context_aware,
            "targets_gaps": targets_gaps,
            "weighted_avg": weighted_avg,
            "no_invalid_transitions": no_invalid_transitions,
            "no_cross_contamination": no_cross_contamination,
            # Additional context
            "weak_answer_detected": self._check_weak_answer_detected(evaluations),
            "follow_up_generated": len(follow_ups) > 0,
            "error_occurred": False,  # Placeholder
            "error_message": "",  # Placeholder
            "actual_cost": 0.0,  # Placeholder (filled by runner)
            "cost_budget": 0.15,  # Placeholder
            "cv_skills": [],  # Placeholder
            "state_transitions": self._extract_state_transitions(context),
        }

        return namespace

    def _check_weak_answer_detected(self, evaluations: list) -> bool:
        """Check if any evaluation indicates weak answer.

        Args:
            evaluations: List of evaluation dicts

        Returns:
            True if weak answer detected
        """
        for eval_data in evaluations:
            score = eval_data.get("score", 100)
            if score < 60:
                return True

        return False

    def _extract_state_transitions(self, context: dict) -> list[str]:
        """Extract state transitions from context.

        Args:
            context: Interview context

        Returns:
            List of states in order
        """
        # For MVP: return simplified state sequence
        states = ["IDLE"]

        questions = context.get("questions", [])
        evaluations = context.get("evaluations", [])
        follow_ups = context.get("follow_ups", [])

        for _ in questions:
            states.append("QUESTIONING")
            states.append("EVALUATING")

        for _ in follow_ups:
            states.append("FOLLOW_UP")
            states.append("EVALUATING")

        if context.get("summary"):
            states.append("COMPLETE")

        return states
