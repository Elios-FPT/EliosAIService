"""Database helper for inserting pre-defined test data (mock tests only)."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class DatabaseHelper:
    """Helper for direct database operations in mock tests."""

    def __init__(self, session: AsyncSession):
        """Initialize database helper.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session

    async def insert_mock_interview_data(
        self, cv_fixture: str, expected_questions: int
    ) -> tuple[UUID, UUID, list[UUID]]:
        """Insert pre-defined interview data for mock testing.

        Args:
            cv_fixture: CV fixture filename (e.g., "python_senior.json")
            expected_questions: Number of questions to create

        Returns:
            (candidate_id, interview_id, question_ids)
        """
        # Load CV data
        cv_path = Path(__file__).parent / "fixtures" / "cvs" / cv_fixture
        with open(cv_path) as f:
            cv_data = json.load(f)

        # Generate IDs
        candidate_id = uuid4()
        cv_analysis_id = uuid4()
        interview_id = uuid4()
        question_ids = [uuid4() for _ in range(expected_questions)]

        # Insert candidate
        await self.session.execute(
            text(
                """
            INSERT INTO candidates (id, name, email, created_at)
            VALUES (:id, :name, :email, :created_at)
            """
            ),
            {
                "id": candidate_id,
                "name": cv_data["name"],
                "email": cv_data["email"],
                "created_at": datetime.utcnow(),
            },
        )

        # Insert CV analysis
        await self.session.execute(
            text(
                """
            INSERT INTO cv_analyses (id, candidate_id, skills, experience_years,
                                    education_level, key_technologies, created_at)
            VALUES (:id, :candidate_id, :skills, :experience_years,
                    :education_level, :key_technologies, :created_at)
            """
            ),
            {
                "id": cv_analysis_id,
                "candidate_id": candidate_id,
                "skills": json.dumps(cv_data.get("skills", [])),
                "experience_years": self._extract_experience_years(cv_data),
                "education_level": cv_data.get("education", "Bachelor's"),
                "key_technologies": json.dumps(cv_data.get("skills", [])[:3]),
                "created_at": datetime.utcnow(),
            },
        )

        # Insert interview
        await self.session.execute(
            text(
                """
            INSERT INTO interviews (id, candidate_id, cv_analysis_id, status,
                                   current_question_index, total_questions, created_at)
            VALUES (:id, :candidate_id, :cv_analysis_id, :status,
                    :current_question_index, :total_questions, :created_at)
            """
            ),
            {
                "id": interview_id,
                "candidate_id": candidate_id,
                "cv_analysis_id": cv_analysis_id,
                "status": "IDLE",
                "current_question_index": 0,
                "total_questions": expected_questions,
                "created_at": datetime.utcnow(),
            },
        )

        # Insert questions
        for idx, question_id in enumerate(question_ids):
            skill = cv_data.get("skills", ["General"])[idx % len(cv_data.get("skills", ["General"]))]

            await self.session.execute(
                text(
                    """
                INSERT INTO questions (id, text, question_type, difficulty,
                                     skill_category, ideal_answer, created_at)
                VALUES (:id, :text, :question_type, :difficulty,
                        :skill_category, :ideal_answer, :created_at)
                """
                ),
                {
                    "id": question_id,
                    "text": f"What is your experience with {skill}?",
                    "question_type": "TECHNICAL",
                    "difficulty": ["EASY", "MEDIUM", "HARD"][idx % 3],
                    "skill_category": skill,
                    "ideal_answer": f"Candidate should demonstrate understanding of {skill}.",
                    "created_at": datetime.utcnow(),
                },
            )

            # Link question to interview
            await self.session.execute(
                text(
                    """
                INSERT INTO interview_questions (interview_id, question_id, question_order)
                VALUES (:interview_id, :question_id, :question_order)
                """
                ),
                {
                    "interview_id": interview_id,
                    "question_id": question_id,
                    "question_order": idx,
                },
            )

        await self.session.commit()

        logger.info(
            f"Inserted mock data: candidate={candidate_id}, "
            f"interview={interview_id}, questions={len(question_ids)}"
        )

        return candidate_id, interview_id, question_ids

    async def cleanup_interview_data(self, interview_id: UUID) -> None:
        """Clean up test data after test completion.

        Args:
            interview_id: Interview UUID to clean up
        """
        # Delete in reverse order of foreign key dependencies
        await self.session.execute(
            text("DELETE FROM evaluations WHERE answer_id IN (SELECT id FROM answers WHERE interview_id = :id)"),
            {"id": interview_id},
        )
        await self.session.execute(
            text("DELETE FROM follow_up_questions WHERE interview_id = :id"),
            {"id": interview_id},
        )
        await self.session.execute(
            text("DELETE FROM answers WHERE interview_id = :id"),
            {"id": interview_id},
        )
        await self.session.execute(
            text("DELETE FROM interview_questions WHERE interview_id = :id"),
            {"id": interview_id},
        )
        await self.session.execute(
            text("DELETE FROM interviews WHERE id = :id"),
            {"id": interview_id},
        )

        await self.session.commit()
        logger.info(f"Cleaned up interview data: {interview_id}")

    def _extract_experience_years(self, cv_data: dict[str, Any]) -> int:
        """Extract experience years from CV data.

        Args:
            cv_data: CV data dict

        Returns:
            Experience years (estimated)
        """
        title = cv_data.get("title", "").lower()

        if "senior" in title:
            return 5
        elif "mid" in title or "intermediate" in title:
            return 3
        elif "junior" in title:
            return 1
        else:
            return 2
