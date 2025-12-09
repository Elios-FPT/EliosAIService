"""PostgreSQL implementation of FeedbackRequestRepositoryPort."""

import json
from datetime import datetime
from uuid import UUID

from sqlalchemy import select, text

from ...domain.models.feedback_request import FeedbackRequest
from ...domain.models.feedback_result import FeedbackStatus, InputType
from ...domain.ports.feedback_repository_port import FeedbackRequestRepositoryPort
from .mappers import FeedbackRequestMapper
from .models import FeedbackRequestModel
from .session_provider import SessionProvider


class PostgresFeedbackRequestRepository(FeedbackRequestRepositoryPort):
    """PostgreSQL implementation of feedback request repository."""

    def __init__(self, session_provider: SessionProvider):
        """Initialize repository with session provider.

        Args:
            session_provider: Async context manager for database sessions
        """
        self._session_provider = session_provider

    async def create(
        self,
        entity_id: UUID,
        input_type: InputType,
        user_id: UUID | None = None,
        feedback_input: str | None = None,
    ) -> FeedbackRequest:
        """Create new feedback request with status=PENDING.

        Args:
            entity_id: UUID of entity to analyze
            input_type: Type of entity (INTERVIEW/CV/CODE)
            user_id: Optional user who requested analysis
            feedback_input: Optional content (if None, extracted from entity)

        Returns:
            Created FeedbackRequest

        Raises:
            ValueError: If creation fails
        """
        from uuid import uuid4

        # If feedback_input not provided, extract from entity
        if feedback_input is None:
            feedback_input = await self._extract_content_from_entity(entity_id, input_type)

        request = FeedbackRequest(
            id=uuid4(),
            entity_id=entity_id,
            input_type=input_type,
            user_id=user_id,
            status=FeedbackStatus.PENDING,
            error_message=None,
            feedback_input=feedback_input,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        async with self._session_provider() as session:
            db_model = FeedbackRequestMapper.to_db_model(request)
            session.add(db_model)
            await session.commit()
            await session.refresh(db_model)
            return FeedbackRequestMapper.to_domain(db_model)

    async def get_by_id(self, request_id: UUID) -> FeedbackRequest | None:
        """Get request by ID.

        Args:
            request_id: Request UUID

        Returns:
            FeedbackRequest if found, None otherwise
        """
        async with self._session_provider() as session:
            result = await session.execute(
                select(FeedbackRequestModel).where(FeedbackRequestModel.id == request_id)
            )
            db_model = result.scalar_one_or_none()
            return (
                FeedbackRequestMapper.to_domain(db_model) if db_model else None
            )

    async def update_status(
        self,
        request_id: UUID,
        status: FeedbackStatus,
        error_message: str | None = None,
    ) -> FeedbackRequest:
        """Update request status and optional error message.

        Args:
            request_id: Request UUID
            status: New status
            error_message: Error message if status=FAILED

        Returns:
            Updated FeedbackRequest

        Raises:
            ValueError: If request not found
        """
        async with self._session_provider() as session:
            result = await session.execute(
                select(FeedbackRequestModel).where(
                    FeedbackRequestModel.id == request_id
                )
            )
            db_model = result.scalar_one_or_none()

            if not db_model:
                raise ValueError(f"FeedbackRequest {request_id} not found")

            db_model.status = status.value
            db_model.error_message = error_message
            db_model.updated_at = datetime.utcnow()

            await session.commit()
            await session.refresh(db_model)
            return FeedbackRequestMapper.to_domain(db_model)

    async def list_by_user(
        self,
        user_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[FeedbackRequest]:
        """List requests for user (for frontend dashboard).

        Args:
            user_id: User UUID
            limit: Max results (default 50, max 100)
            offset: Pagination offset

        Returns:
            List of FeedbackRequest ordered by created_at DESC
        """
        # Enforce max limit
        if limit > 100:
            limit = 100

        async with self._session_provider() as session:
            result = await session.execute(
                select(FeedbackRequestModel)
                .where(FeedbackRequestModel.user_id == user_id)
                .order_by(FeedbackRequestModel.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            db_models = result.scalars().all()
            return [FeedbackRequestMapper.to_domain(m) for m in db_models]

    async def _extract_content_from_entity(
        self, entity_id: UUID, input_type: InputType
    ) -> str:
        """Extract content from entity for feedback_input.

        Used when feedback_input not provided directly.

        Args:
            entity_id: UUID of entity
            input_type: Type of entity

        Returns:
            JSON string with extracted content
        """
        async with self._session_provider() as session:
            if input_type == InputType.INTERVIEW:
                return await self._extract_interview_content(session, entity_id)
            elif input_type == InputType.CV:
                return await self._extract_cv_content(session, entity_id)
            elif input_type == InputType.CODE:
                return json.dumps({
                    "code_submission_id": str(entity_id),
                    "note": "CODE submission (not implemented)"
                })
            else:
                return json.dumps({
                    "error": f"Unknown input_type: {input_type}",
                    "entity_id": str(entity_id)
                })

    async def _extract_interview_content(
        self, session, interview_id: UUID
    ) -> str:
        """Extract interview Q&A content for audit trail."""
        result = await session.execute(
            text("""
                SELECT
                    iq.sequence_order,
                    iq.question_text,
                    iq.question_type,
                    a.answer_text,
                    a.is_voice,
                    a.created_at as answer_created_at
                FROM interview_questions iq
                LEFT JOIN answers a ON a.question_id = iq.question_id
                WHERE iq.interview_id = :interview_id
                ORDER BY iq.sequence_order
            """),
            {"interview_id": str(interview_id)}
        )
        questions = result.fetchall()

        content = {
            "interview_id": str(interview_id),
            "questions": []
        }

        for q in questions:
            content["questions"].append({
                "sequence": q.sequence_order,
                "question": q.question_text,
                "type": q.question_type,
                "answer": q.answer_text or None,
                "is_voice": q.is_voice or False,
                "answered_at": q.answer_created_at.isoformat() if q.answer_created_at else None
            })

        return json.dumps(content, indent=2)

    async def _extract_cv_content(self, session, cv_analysis_id: UUID) -> str:
        """Extract CV analysis content for audit trail."""
        # Get CV analysis
        cv_result = await session.execute(
            text("""
                SELECT summary, created_at
                FROM cv_analyses
                WHERE id = :cv_id
            """),
            {"cv_id": str(cv_analysis_id)}
        )
        cv = cv_result.fetchone()

        if not cv:
            return json.dumps({"error": "CV analysis not found"})

        # Get skills
        skills_result = await session.execute(
            text("""
                SELECT
                    skill_name,
                    proficiency_level,
                    years_of_experience,
                    is_primary
                FROM cv_skills
                WHERE cv_analysis_id = :cv_id
                ORDER BY is_primary DESC, skill_name
            """),
            {"cv_id": str(cv_analysis_id)}
        )
        skills = skills_result.fetchall()

        content = {
            "cv_analysis_id": str(cv_analysis_id),
            "summary": cv.summary or "",
            "skills": [
                {
                    "name": s.skill_name,
                    "proficiency": s.proficiency_level or "intermediate",
                    "years": float(s.years_of_experience) if s.years_of_experience else None,
                    "is_primary": s.is_primary
                }
                for s in skills
            ],
            "created_at": cv.created_at.isoformat() if cv.created_at else None
        }

        return json.dumps(content, indent=2)

