"""Validate gaps use case.

Extracted from InterviewConversationWorkflow._validate_gaps_node.
Validates cumulative gaps against DB (resume safety check).
"""

import logging
from uuid import UUID

from ..dto.interview.validate_gaps_dto import ValidateGapsInput, ValidateGapsOutput

logger = logging.getLogger(__name__)


class ValidateGapsUseCase:
    """Validate cumulative gaps against DB (resume safety check).

    Only runs when resuming from checkpoint during follow-up context.
    Ensures no gaps missed if state was corrupted or reset.
    Extracted from InterviewConversationWorkflow._validate_gaps_node.
    """

    async def execute(self, input: ValidateGapsInput) -> ValidateGapsOutput:
        """Execute gap validation.

        Args:
            input: Validate gaps input data

        Returns:
            ValidateGapsOutput with validated/merged gaps list
        """
        # Skip if no parent question (new main question)
        if not input.parent_question_id:
            return ValidateGapsOutput(
                cumulative_gaps=input.cumulative_gaps,
                gaps_mismatch_count=0,
            )

        parent_question_id = input.parent_question_id

        # Get all answers from input (already loaded)
        answers_list = input.answers
        if not answers_list:
            return ValidateGapsOutput(
                cumulative_gaps=input.cumulative_gaps,
                gaps_mismatch_count=0,
            )

        # Get all evaluations from input (already loaded)
        evaluations_dicts = input.evaluations
        if not evaluations_dicts:
            return ValidateGapsOutput(
                cumulative_gaps=input.cumulative_gaps,
                gaps_mismatch_count=0,
            )

        # Extract all unresolved gaps from evaluations related to parent question
        db_gaps: set[str] = set()
        for eval_dict in evaluations_dicts:
            # Filter evaluations for parent question
            eval_q_id = eval_dict.get("question_id")
            if eval_q_id:
                # Handle both UUID and string formats
                eval_q_id_str = str(eval_q_id)
                parent_q_id_str = str(parent_question_id)
                if eval_q_id_str == parent_q_id_str:
                    for gap_dict in eval_dict.get("gaps", []):
                        if not gap_dict.get("resolved", False):
                            concept = gap_dict.get("concept", "")
                            if concept:
                                db_gaps.add(concept)

        # Compare with input gaps
        state_gaps = set(input.cumulative_gaps)
        missing_gaps = db_gaps - state_gaps

        if missing_gaps:
            logger.warning(
                f"Gap mismatch detected: {len(missing_gaps)} gaps missing from state",
                extra={
                    "interview_id": str(input.interview_id),
                    "parent_question_id": str(parent_question_id),
                    "state_gaps": list(state_gaps),
                    "db_gaps": list(db_gaps),
                    "missing_gaps": list(missing_gaps),
                    "mismatch_count": len(missing_gaps),
                },
            )

            # Merge missing gaps into output
            merged_gaps = list(state_gaps.union(db_gaps))
            return ValidateGapsOutput(
                cumulative_gaps=merged_gaps,
                gaps_mismatch_count=len(missing_gaps),
            )

        logger.debug("Gap validation passed: state matches DB")
        return ValidateGapsOutput(
            cumulative_gaps=input.cumulative_gaps,
            gaps_mismatch_count=0,
        )

