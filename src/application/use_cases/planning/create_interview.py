"""Create interview use case.

Extracted from PlanningWorkflow._update_interview_node.
Creates interview entity and links questions via junction table.
"""

import logging
import uuid
from typing import Any
from uuid import UUID

from ...domain.models.interview import Interview, InterviewStatus
from ...domain.ports.interview_repository_port import InterviewRepositoryPort
from ..dto.planning.create_interview_dto import CreateInterviewInput, CreateInterviewOutput

logger = logging.getLogger(__name__)


class CreateInterviewUseCase:
    """Create interview entity and link questions.

    Extracted from PlanningWorkflow._update_interview_node.
    """

    def __init__(self, interview_repo: InterviewRepositoryPort):
        """Initialize use case with required dependencies.

        Args:
            interview_repo: Interview repository port
        """
        self.interview_repo = interview_repo

    async def execute(self, input: CreateInterviewInput) -> CreateInterviewOutput:
        """Create interview.

        Args:
            input: Contains candidate_id, cv_analysis_id, question_ids, and specs

        Returns:
            CreateInterviewOutput with created interview
        """
        if not input.stored_question_ids:
            # Provide context about why question IDs are missing
            if input.question_specs:
                return CreateInterviewOutput(
                    interview={},
                    errors=[
                        "No question IDs to attach to interview. Questions were generated but failed to be stored."
                    ],
                )
            return CreateInterviewOutput(
                interview={},
                errors=["No question IDs to attach to interview"],
            )

        try:
            # Build a human-friendly, non-date-based title using skills from planned questions
            title = self._build_interview_title(input.question_specs)

            interview = Interview(
                id=uuid.uuid4(),
                candidate_id=input.candidate_id,
                title=title,
                status=InterviewStatus.IDLE,
                cv_analysis_id=input.cv_analysis_id,
            )
            interview = await self.interview_repo.save(interview)

            # Add questions to interview via junction table
            for idx, question_id in enumerate(input.stored_question_ids):
                await self.interview_repo.add_question(
                    interview_id=interview.id,
                    question_id=question_id,
                    sequence_order=idx,
                )

            logger.info(f"Created interview {interview.id} with {len(input.stored_question_ids)} questions")
            return CreateInterviewOutput(
                interview=interview.model_dump(mode="json"),
                errors=[],
            )

        except Exception as exc:
            logger.error(f"Failed to create interview: {exc}", exc_info=True)
            return CreateInterviewOutput(
                interview={},
                errors=[f"create_interview: {str(exc)}"],
            )

    def _build_interview_title(
        self, question_specs: list[dict[str, Any]] | None
    ) -> str:
        """Build a simple, human-friendly interview title from planned question skills.

        Prefer the most common or first skill from question specs; otherwise fall back
        to a generic label. Avoids including dates to keep titles stable and clean.

        Args:
            question_specs: List of question specification dicts

        Returns:
            Interview title string
        """
        if not question_specs:
            return "General Interview"

        # Extract ordered, unique skill names from specs
        skills = [spec.get("skill") for spec in question_specs if spec.get("skill")]
        if not skills:
            return "General Interview"

        # Deduplicate while preserving order
        seen = set()
        ordered_skills = []
        for skill in skills:
            if skill and skill not in seen:
                seen.add(skill)
                ordered_skills.append(skill)

        if not ordered_skills:
            return "General Interview"

        skills_str = ", ".join(ordered_skills)
        return f"Interview – {skills_str}"

