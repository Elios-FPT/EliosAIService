"""Create interview use case.

Extracted from PlanningWorkflow._update_interview_node (lines 477-531).
Includes helper method _build_interview_title (lines 590-613).
"""

import logging
import uuid
from typing import Any

from ....domain.models.interview import Interview, InterviewStatus
from ....application.ports.interview_repository_port import InterviewRepositoryPort
from ...dto.planning.create_interview_dto import (
    CreateInterviewInput,
    CreateInterviewOutput,
)

logger = logging.getLogger(__name__)


class CreateInterviewUseCase:
    """Create interview with generated question IDs.

    Creates Interview entity with human-friendly title based on skills,
    saves it, then links questions via junction table.
    """

    def __init__(self, interview_repo: InterviewRepositoryPort):
        """Initialize with required port.

        Args:
            interview_repo: Interview repository port
        """
        self.interview_repo = interview_repo

    async def execute(self, input_dto: CreateInterviewInput) -> CreateInterviewOutput:
        """Create interview and attach questions.

        Args:
            input_dto: Contains candidate ID, CV analysis ID, question IDs, and specs

        Returns:
            CreateInterviewOutput with created interview
        """
        try:
            candidate_id = input_dto.candidate_id
            question_ids = input_dto.stored_question_ids
            cv_analysis_id = input_dto.cv_analysis_id
            question_specs = input_dto.question_specs

            if not question_ids:
                return CreateInterviewOutput(
                    interview={},
                    errors=["No question IDs to attach to interview"]
                )

            # Build human-friendly title using skills from planned questions
            title = self._build_interview_title(question_specs)

            # Create interview entity
            interview = Interview(
                id=uuid.uuid4(),
                candidate_id=candidate_id,
                title=title,
                status=InterviewStatus.IDLE,
                cv_analysis_id=cv_analysis_id,
            )
            interview = await self.interview_repo.save(interview)

            # Add questions to interview via junction table
            for idx, question_id in enumerate(question_ids):
                await self.interview_repo.add_question(
                    interview_id=interview.id,
                    question_id=question_id,
                    sequence_order=idx,
                )

            logger.info(f"Created interview {interview.id} with {len(question_ids)} questions")

            return CreateInterviewOutput(
                interview=interview.model_dump(mode="json"),
                errors=[]
            )

        except Exception as e:
            logger.error(f"Failed to create interview: {e}", exc_info=True)
            return CreateInterviewOutput(
                interview={},
                errors=[f"Failed to create interview: {str(e)}"]
            )

    def _build_interview_title(self, question_specs: list[dict[str, Any]]) -> str:
        """Build simple, human-friendly interview title from planned question skills.

        Avoids dates to keep titles stable and clean.

        Args:
            question_specs: List of question specification dictionaries

        Returns:
            Interview title string
        """
        if not question_specs:
            return "General Interview"

        # Extract ordered, unique skill names from specs
        skills: list[str] = []
        for spec in question_specs:
            skill = spec.get("skill")
            if skill and isinstance(skill, str):
                skills.append(skill)

        if not skills:
            return "General Interview"

        # Deduplicate while preserving order
        seen: set[str] = set()
        ordered_skills: list[str] = []
        for skill in skills:
            if skill not in seen:
                seen.add(skill)
                ordered_skills.append(skill)

        skills_str = ", ".join(ordered_skills)
        return f"Interview – {skills_str}"
