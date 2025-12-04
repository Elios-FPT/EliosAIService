"""Use case for fetching interview history for a user."""

from __future__ import annotations

from uuid import UUID

from ...domain.models.interview import Interview, InterviewStatus
from ...domain.ports.interview_repository_port import InterviewRepositoryPort
from ..dto.interview_dto import (
    InterviewHistoryItemResponse,
    InterviewHistoryListResponse,
    InterviewHistoryPagination,
)


class ListInterviewHistoryUseCase:
    """Use case responsible for fetching interview history."""

    def __init__(self, interview_repository: InterviewRepositoryPort) -> None:
        self._interview_repository = interview_repository

    async def execute(
        self,
        *,
        candidate_id: UUID,
        ws_base_url: str,
        status: InterviewStatus | None = None,
        limit: int = 20,
        offset: int = 0,
        include_active: bool = True,
        include_deleted: bool = False,
    ) -> InterviewHistoryListResponse:
        """Fetch paginated interview history.

        Args:
            candidate_id: Candidate/user identifier
            ws_base_url: Base URL for websocket connections
            status: Optional interview status filter
            limit: Max rows per page (1-100)
            offset: Number of rows to skip (>=0)
            include_active: Whether to include active (non-terminal) interviews
            include_deleted: Whether to include soft-deleted interviews
        """
        self._validate_pagination(limit=limit, offset=offset)

        if not ws_base_url:
            raise ValueError("ws_base_url must be provided")

        interviews, total = await self._interview_repository.list_by_candidate_paginated(
            candidate_id=candidate_id,
            limit=limit,
            offset=offset,
            status=status,
            include_active=include_active,
            include_deleted=include_deleted,
        )

        items = [
            self._build_history_item(
                interview=interview,
                ws_base_url=ws_base_url,
            )
            for interview in interviews
        ]

        pagination = InterviewHistoryPagination(limit=limit, offset=offset, total=total)
        return InterviewHistoryListResponse(items=items, pagination=pagination)

    @staticmethod
    def _validate_pagination(*, limit: int, offset: int) -> None:
        if limit < 1 or limit > 100:
            raise ValueError("limit must be between 1 and 100")
        if offset < 0:
            raise ValueError("offset must be greater than or equal to 0")

    def _build_history_item(
        self,
        *,
        interview: Interview,
        ws_base_url: str,
    ) -> InterviewHistoryItemResponse:
        question_count = interview.planned_question_count
        progress_percentage = (
            min(
                100.0,
                (interview.current_question_index / question_count) * 100.0,
            )
            if question_count > 0
            else 0.0
        )

        base_url = ws_base_url.rstrip("/")
        ws_url = f"{base_url}/ws/interviews/{interview.id}"

        return InterviewHistoryItemResponse(
            id=interview.id,
            title=getattr(interview, "title", "General Interview"),
            status=interview.status.value,
            cv_analysis_id=interview.cv_analysis_id,
            planned_question_count=question_count,
            current_question_index=interview.current_question_index,
            question_count=question_count,
            progress_percentage=progress_percentage,
            ws_url=ws_url,
            started_at=interview.started_at,
            completed_at=interview.completed_at,
            created_at=interview.created_at,
            updated_at=interview.updated_at,
        )

