"""Decide follow-up use case.

Extracted from InterviewConversationWorkflow._decide_followup_node.
Decides if follow-up question needed based on evaluation.
"""

import logging

from ...domain.models.evaluation import Evaluation
from ..dto.interview.decide_followup_dto import DecideFollowupInput, DecideFollowupOutput

logger = logging.getLogger(__name__)


class DecideFollowupUseCase:
    """Decide if follow-up question needed.

    Break conditions:
    1. followup_count >= 3 (max reached)
    2. evaluation.is_adaptive_complete() (similarity >= 0.8 OR no gaps)

    Uses domain method for batched status transitions.
    Extracted from InterviewConversationWorkflow._decide_followup_node.
    """

    async def execute(self, input: DecideFollowupInput) -> DecideFollowupOutput:
        """Execute follow-up decision.

        Args:
            input: Decide follow-up input data

        Returns:
            DecideFollowupOutput with follow-up decision and updated gaps
        """
        followup_count = input.followup_count
        latest_eval_dict = input.latest_evaluation

        # Break condition 1: Max follow-ups
        if followup_count >= 3:
            logger.info(f"Max follow-ups reached ({followup_count})")
            return DecideFollowupOutput(
                needs_followup=False,
                followup_reason="Max follow-ups reached",
                cumulative_gaps=input.cumulative_gaps,
                errors=[],
            )

        # Reconstruct Evaluation entity to call domain method
        try:
            evaluation = Evaluation(**latest_eval_dict)
        except Exception as exc:
            logger.error(f"Failed to reconstruct evaluation: {exc}", exc_info=True)
            return DecideFollowupOutput(
                needs_followup=False,
                followup_reason="Failed to parse evaluation",
                cumulative_gaps=input.cumulative_gaps,
                errors=[f"decide_followup: {str(exc)}"],
            )

        # Break condition 2: Adaptive completion criteria (domain method)
        if evaluation.is_adaptive_complete():
            reason = (
                f"Answer meets completion criteria: "
                f"similarity={evaluation.similarity_score:.2f}"
                if evaluation.similarity_score is not None and evaluation.similarity_score >= 0.8
                else "No unresolved gaps"
            )
            logger.info(reason)
            return DecideFollowupOutput(
                needs_followup=False,
                followup_reason=reason,
                cumulative_gaps=input.cumulative_gaps,
                errors=[],
            )

        # Accumulate gaps from unresolved
        unresolved_gaps = [gap for gap in evaluation.gaps if not gap.resolved]

        cumulative = input.cumulative_gaps.copy()
        for gap in unresolved_gaps:
            if gap.concept and gap.concept not in cumulative:
                cumulative.append(gap.concept)

        logger.info(
            f"Follow-up needed: {len(unresolved_gaps)} gaps detected",
            extra={"gaps": cumulative},
        )

        return DecideFollowupOutput(
            needs_followup=True,
            cumulative_gaps=cumulative,
            followup_reason=f"Detected {len(unresolved_gaps)} gaps",
            errors=[],
        )

