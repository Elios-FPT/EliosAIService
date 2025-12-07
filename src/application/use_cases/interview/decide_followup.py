"""Decide follow-up use case.

Extracted from InterviewConversationWorkflow._decide_followup_node (lines 761-825).
"""

import logging

from ....domain.models.evaluation import Evaluation
from ...dto.interview.decide_followup_dto import DecideFollowupInput, DecideFollowupOutput

logger = logging.getLogger(__name__)


class DecideFollowupUseCase:
    """Decide if follow-up question needed.

    Break conditions:
    1. followup_count >= 3 (max reached)
    2. evaluation.is_adaptive_complete() (similarity >= 0.8 OR no gaps)
    """

    def __init__(self) -> None:
        """Initialize use case (no dependencies required)."""
        pass

    async def execute(self, input_dto: DecideFollowupInput) -> DecideFollowupOutput:
        """Decide if follow-up question is needed.

        Args:
            input_dto: Contains followup_count, latest_evaluation, cumulative_gaps

        Returns:
            DecideFollowupOutput with needs_followup decision and updated gaps
        """
        try:
            followup_count = input_dto.followup_count

            # Break condition 1: Max follow-ups
            if followup_count >= 3:
                logger.info(f"Max follow-ups reached ({followup_count})")
                return DecideFollowupOutput(
                    needs_followup=False,
                    followup_reason="Max follow-ups reached",
                    cumulative_gaps=input_dto.cumulative_gaps,
                )

            # Reconstruct Evaluation entity to call domain method
            evaluation = Evaluation(**input_dto.latest_evaluation)

            # Break condition 2: Adaptive completion criteria
            if evaluation.is_adaptive_complete():
                reason = (
                    f"Answer meets completion criteria: "
                    f"similarity={evaluation.similarity_score:.2f}"
                    if evaluation.similarity_score is not None
                    and evaluation.similarity_score >= 0.8
                    else "No unresolved gaps"
                )
                logger.info(reason)
                return DecideFollowupOutput(
                    needs_followup=False,
                    followup_reason=reason,
                    cumulative_gaps=input_dto.cumulative_gaps,
                )

            # Accumulate gaps from unresolved
            unresolved_gaps = [gap for gap in evaluation.gaps if not gap.resolved]

            cumulative = list(input_dto.cumulative_gaps)
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
            )

        except Exception as exc:
            logger.error(f"decide_followup failed: {exc}", exc_info=True)
            return DecideFollowupOutput(
                needs_followup=False,
                followup_reason="Error during decision",
                cumulative_gaps=input_dto.cumulative_gaps,
                errors=[f"decide_followup: {str(exc)}"],
            )
