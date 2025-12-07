"""Validate gaps use case.

Extracted from InterviewConversationWorkflow._validate_gaps_node (lines 634-701).
"""

import logging

from ...dto.interview.validate_gaps_dto import ValidateGapsInput, ValidateGapsOutput

logger = logging.getLogger(__name__)


class ValidateGapsUseCase:
    """Validate cumulative gaps against DB (resume safety check).

    Only runs when resuming from checkpoint during follow-up context.
    Ensures no gaps missed if state was corrupted or reset.
    """

    def __init__(self) -> None:
        """Initialize use case (no dependencies required)."""
        pass

    async def execute(self, input_dto: ValidateGapsInput) -> ValidateGapsOutput:
        """Validate cumulative gaps against evaluations from state.

        Args:
            input_dto: Contains parent_question_id, cumulative_gaps, evaluations

        Returns:
            ValidateGapsOutput with validated/merged gaps list
        """
        try:
            # Skip if no parent question (new main question)
            if not input_dto.parent_question_id:
                return ValidateGapsOutput()

            parent_question_id = input_dto.parent_question_id

            # Skip if no previous answers
            if not input_dto.answers:
                return ValidateGapsOutput()

            # Skip if no previous evaluations
            if not input_dto.evaluations:
                return ValidateGapsOutput()

            # Extract all unresolved gaps from evaluations related to parent question
            db_gaps: set[str] = set()
            for eval_dict in input_dto.evaluations:
                # Filter evaluations for parent question
                if str(eval_dict.get("question_id")) == str(parent_question_id):
                    for gap_dict in eval_dict.get("gaps", []):
                        if not gap_dict.get("resolved", False):
                            db_gaps.add(gap_dict.get("concept", ""))

            # Compare with state gaps
            state_gaps = set(input_dto.cumulative_gaps)
            missing_gaps = db_gaps - state_gaps

            if missing_gaps:
                logger.warning(
                    f"Gap mismatch detected: {len(missing_gaps)} gaps missing from state",
                    extra={
                        "interview_id": str(input_dto.interview_id),
                        "parent_question_id": str(parent_question_id),
                        "state_gaps": list(state_gaps),
                        "db_gaps": list(db_gaps),
                        "missing_gaps": list(missing_gaps),
                        "mismatch_count": len(missing_gaps),
                    },
                )

                # Merge missing gaps into state
                merged_gaps = list(state_gaps.union(db_gaps))
                return ValidateGapsOutput(
                    cumulative_gaps=merged_gaps,
                    gaps_mismatch_count=len(missing_gaps),
                )

            logger.debug("Gap validation passed: state matches DB")
            return ValidateGapsOutput()

        except Exception as exc:
            logger.error(f"Gap validation failed: {exc}", exc_info=True)
            # Non-blocking: continue with state gaps if validation fails
            return ValidateGapsOutput()
