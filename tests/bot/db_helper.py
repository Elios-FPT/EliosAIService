"""Database helper for inserting pre-defined test data (mock tests only)."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.cv_analysis import CVAnalysis
from src.domain.models.cv_skill import CVSkill, ProficiencyLevel
from src.domain.models.interview import Interview, InterviewStatus
from src.domain.models.question import Question, QuestionType, DifficultyLevel
from src.adapters.persistence.cv_analysis_repository import PostgreSQLCVAnalysisRepository
from src.adapters.persistence.mappers import (
    CVAnalysisMapper,
    InterviewMapper,
    QuestionMapper,
)

from .config import BotConfig, get_config

logger = logging.getLogger(__name__)


class DatabaseHelper:
    """Helper for direct database operations in mock tests."""

    def __init__(self, session: AsyncSession, config: BotConfig | None = None):
        """Initialize database helper.

        Args:
            session: SQLAlchemy async session
            config: Optional bot configuration (uses global config if not provided)
        """
        self.session = session
        self.cv_analysis_repo = PostgreSQLCVAnalysisRepository(session)
        self.config = config or get_config()

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

        # Insert candidate (using raw SQL - no dedicated repository yet)
        from sqlalchemy import text
        await self.session.execute(
            text(
                """
            INSERT INTO candidates (id, name, email, created_at, updated_at)
            VALUES (:id, :name, :email, :created_at, :updated_at)
            """
            ),
            {
                "id": candidate_id,
                "name": cv_data["name"],
                "email": cv_data["email"],
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            },
        )

        # Create CV Analysis domain model
        cv_analysis = self._create_cv_analysis_from_fixture(
            cv_analysis_id, candidate_id, cv_data
        )

        # Save using repository (ORM)
        await self.cv_analysis_repo.save(cv_analysis)

        # Create Interview domain model
        interview = self._create_interview(
            interview_id, candidate_id, cv_analysis_id, question_ids
        )

        # Save interview using mapper (ORM)
        interview_mapper = InterviewMapper()
        interview_db = interview_mapper.to_db_model(interview)
        self.session.add(interview_db)

        # Create and save questions
        await self._create_questions(question_ids, cv_data)

        await self.session.commit()

        logger.info(
            f"Inserted mock data: candidate={candidate_id}, "
            f"interview={interview_id}, questions={len(question_ids)}"
        )

        return candidate_id, interview_id, question_ids

    def _create_cv_analysis_from_fixture(
        self, cv_analysis_id: UUID, candidate_id: UUID, cv_data: dict[str, Any]
    ) -> CVAnalysis:
        """Create CVAnalysis domain model from fixture data.

        Args:
            cv_analysis_id: CV analysis UUID
            candidate_id: Candidate UUID
            cv_data: CV fixture data

        Returns:
            CVAnalysis domain model
        """
        # Extract skills from fixture
        skills_list = cv_data.get("skills", [])
        cv_skills = [
            CVSkill(
                id=uuid4(),
                cv_analysis_id=cv_analysis_id,
                skill_name=skill,
                proficiency_level=self._map_proficiency(self.config.cv_analysis.default_proficiency),
                years_of_experience=float(self._extract_experience_years(cv_data)),
                is_primary=(idx < 3),  # First 3 are primary
                created_at=datetime.utcnow(),
            )
            for idx, skill in enumerate(skills_list)
        ]

        # Use first 3 skills as suggested topics
        suggested_topics = skills_list[:3] if len(skills_list) >= 3 else skills_list

        return CVAnalysis(
            id=cv_analysis_id,
            candidate_id=candidate_id,
            cv_file_path=f"fixtures/cvs/{cv_data.get('cv_file', 'mock.pdf')}",
            extracted_text=cv_data.get("summary", "Mock CV extracted text"),
            skills=cv_skills,
            work_experience_years=self._extract_experience_years(cv_data),
            education_level=cv_data.get("education", "Bachelor's"),
            suggested_topics=suggested_topics,
            suggested_difficulty=self._suggest_difficulty(cv_data),
            summary=cv_data.get("summary", "Mock CV summary"),
            metadata={
                "source": "test_fixture",
                "fixture_file": cv_data.get("cv_file", "mock.pdf"),
            },
            embedding=None,  # Skip embedding for tests
            created_at=datetime.utcnow(),
        )

    def _create_interview(
        self,
        interview_id: UUID,
        candidate_id: UUID,
        cv_analysis_id: UUID,
        question_ids: list[UUID],
    ) -> Interview:
        """Create Interview domain model.

        Args:
            interview_id: Interview UUID
            candidate_id: Candidate UUID
            cv_analysis_id: CV analysis UUID
            question_ids: List of question UUIDs

        Returns:
            Interview domain model
        """
        return Interview(
            id=interview_id,
            candidate_id=candidate_id,
            cv_analysis_id=cv_analysis_id,
            status=InterviewStatus.IDLE,
            current_question_index=0,
            question_ids=question_ids,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

    async def _create_questions(
        self, question_ids: list[UUID], cv_data: dict[str, Any]
    ) -> None:
        """Create Question domain models and save to DB.

        Args:
            question_ids: List of question UUIDs
            cv_data: CV fixture data
        """
        question_mapper = QuestionMapper()
        skills_list = cv_data.get("skills", ["General"])

        for idx, question_id in enumerate(question_ids):
            skill = skills_list[idx % len(skills_list)]

            # Map difficulty
            difficulty_map = {0: DifficultyLevel.EASY, 1: DifficultyLevel.MEDIUM, 2: DifficultyLevel.HARD}
            difficulty = difficulty_map[idx % 3]

            question = Question(
                id=question_id,
                text=f"What is your experience with {skill}?",
                question_type=QuestionType.TECHNICAL,
                difficulty=difficulty,
                skills=[skill],
                ideal_answer=f"Candidate should demonstrate understanding of {skill}.",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )

            question_db = question_mapper.to_db_model(question)
            self.session.add(question_db)

    async def cleanup_interview_data(self, interview_id: UUID) -> None:
        """Clean up test data after test completion.

        Args:
            interview_id: Interview UUID to clean up
        """
        try:
            from sqlalchemy import text
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
                text("DELETE FROM interviews WHERE id = :id"),
                {"id": interview_id},
            )

            await self.session.commit()
            logger.info(f"Cleaned up interview data: {interview_id}")
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Failed to cleanup interview data: {e}")
            raise

    def _extract_experience_years(self, cv_data: dict[str, Any]) -> int:
        """Extract experience years from CV data.

        Args:
            cv_data: CV data dict

        Returns:
            Experience years (estimated)
        """
        title = cv_data.get("title", "").lower()

        if "senior" in title:
            return self.config.experience_mapping.senior_years
        elif "mid" in title or "intermediate" in title:
            return self.config.experience_mapping.mid_years
        elif "junior" in title:
            return self.config.experience_mapping.junior_years
        else:
            return self.config.experience_mapping.default_years

    def _suggest_difficulty(self, cv_data: dict[str, Any]) -> str:
        """Suggest interview difficulty based on CV.

        Args:
            cv_data: CV data dict

        Returns:
            Difficulty level (EASY, MEDIUM, HARD)
        """
        title = cv_data.get("title", "").lower()

        if "senior" in title:
            return self.config.difficulty_mapping.senior_difficulty
        elif "mid" in title or "intermediate" in title:
            return self.config.difficulty_mapping.mid_difficulty
        else:
            return self.config.difficulty_mapping.default_difficulty

    def _map_proficiency(self, proficiency_str: str) -> ProficiencyLevel:
        """Map string proficiency to ProficiencyLevel enum.

        Args:
            proficiency_str: Proficiency string (e.g., "expert", "intermediate")

        Returns:
            ProficiencyLevel enum value
        """
        proficiency_map = {
            "expert": ProficiencyLevel.EXPERT,
            "advanced": ProficiencyLevel.ADVANCED,
            "intermediate": ProficiencyLevel.INTERMEDIATE,
            "beginner": ProficiencyLevel.BEGINNER,
        }
        return proficiency_map.get(proficiency_str.lower(), ProficiencyLevel.INTERMEDIATE)
