"""Database helper for inserting pre-defined test data (mock tests only)."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.cv_analysis import CVAnalysis
from src.domain.models.cv_skill import CVSkill, ProficiencyLevel
from src.domain.models.interview_question import InterviewQuestion
from src.domain.models.interview import Interview, InterviewStatus
from src.domain.models.question import Difficulty, Question, QuestionType
from src.adapters.persistence.cv_analysis_repository import PostgreSQLCVAnalysisRepository
from src.adapters.persistence.mappers import (
    InterviewMapper,
    InterviewQuestionMapper,
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
        self.cv_analysis_repo = PostgreSQLCVAnalysisRepository(
            self._session_provider
        )
        self.config = config or get_config()

    @asynccontextmanager
    async def _session_provider(self):
        """Yield existing session without closing it."""
        yield self.session

    async def insert_mock_interview_data(
        self,
        cv_fixture: str,
        expected_questions: int,
        question_fixture: str | None = None,
    ) -> tuple[UUID, UUID, list[UUID], dict[UUID, UUID]]:
        """Insert pre-defined interview data for mock testing.

        Args:
            cv_fixture: CV fixture filename (e.g., "python_senior.json")
            expected_questions: Number of questions to create
            question_fixture: Optional question fixture filename (relative to fixtures/questions)

        Returns:
            (candidate_id, interview_id, question_ids, question_id_map)
        """
        # Load CV data
        cv_path = Path(__file__).parent / "fixtures" / "cvs" / cv_fixture
        with open(cv_path) as f:
            cv_data = json.load(f)

        # Load question/interview fixture (if provided)
        fixture_data = (
            self._load_question_fixture(question_fixture) if question_fixture else None
        )

        # Generate IDs
        candidate_id = uuid4()
        cv_analysis_id = uuid4()
        interview_id = uuid4()

        # Create CV Analysis domain model
        cv_analysis = self._create_cv_analysis_from_fixture(
            cv_analysis_id, candidate_id, cv_data
        )

        # Save using repository (ORM)
        await self.cv_analysis_repo.save(cv_analysis)

        if fixture_data:
            questions_payload = fixture_data.get("questions", [])
            question_ids, question_map = self._save_questions_from_fixture(
                questions_payload
            )
        else:
            question_ids = [uuid4() for _ in range(expected_questions)]
            question_map = {}
            await self._create_questions(question_ids, cv_data)

        if fixture_data and question_ids and len(question_ids) != expected_questions:
            logger.debug(
                "Fixture question count (%s) differs from expected (%s)",
                len(question_ids),
                expected_questions,
            )

        # Create Interview domain model
        interview = self._create_interview(
            interview_id,
            candidate_id,
            cv_analysis_id,
            fixture_data.get("interview") if fixture_data else None,
        )

        # Save interview using mapper (ORM)
        interview_mapper = InterviewMapper()
        interview_db = interview_mapper.to_db_model(interview)
        self.session.add(interview_db)

        if fixture_data:
            self._insert_interview_questions_from_fixture(
                interview_id,
                fixture_data.get("interview_questions", []),
                question_map,
            )
        else:
            self._create_default_interview_questions(interview_id, question_ids)

        await self.session.commit()

        logger.info(
            f"Inserted mock data: candidate={candidate_id}, "
            f"interview={interview_id}, questions={len(question_ids)}"
        )

        return candidate_id, interview_id, question_ids, question_map

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
            extracted_text=cv_data.get("summary", "Mock CV extracted text"),
            skills=cv_skills,
            work_experience_years=self._extract_experience_years(cv_data),
            education_level=cv_data.get("education", "Bachelor's"),
            suggested_topics=suggested_topics,
            suggested_difficulty=self._suggest_difficulty(cv_data),
            summary=cv_data.get("summary", "Mock CV summary"),
            embedding=None,  # Skip embedding for tests
            created_at=datetime.utcnow(),
        )

    def _create_interview(
        self,
        interview_id: UUID,
        candidate_id: UUID,
        cv_analysis_id: UUID,
        interview_data: dict[str, Any] | None = None,
    ) -> Interview:
        """Create Interview domain model."""
        data = interview_data or {}

        adaptive_follow_ups = [
            self._parse_uuid(value) for value in data.get("adaptive_follow_ups", [])
        ]

        return Interview(
            id=interview_id,
            candidate_id=candidate_id,
            cv_analysis_id=cv_analysis_id,
            status=InterviewStatus(data.get("status", InterviewStatus.IDLE.value)),
            current_question_index=data.get("current_question_index", 0),
            plan_metadata=data.get("plan_metadata", {}),
            adaptive_follow_ups=[value for value in adaptive_follow_ups if value],
            current_parent_question_id=self._parse_uuid(
                data.get("current_parent_question_id")
            ),
            current_followup_count=data.get("current_followup_count", 0),
            started_at=self._parse_datetime(data.get("started_at")),
            completed_at=self._parse_datetime(data.get("completed_at")),
            created_at=self._parse_datetime(data.get("created_at")) or datetime.utcnow(),
            updated_at=self._parse_datetime(data.get("updated_at")) or datetime.utcnow(),
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
            difficulty_map = {
                0: Difficulty.EASY,
                1: Difficulty.MEDIUM,
                2: Difficulty.HARD,
            }
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

    def _load_question_fixture(self, fixture_name: str) -> dict[str, Any]:
        """Load question/interview fixture from disk."""
        fixtures_dir = Path(__file__).parent / "fixtures" / "questions"
        fixture_path = fixtures_dir / fixture_name

        if not fixture_path.exists():
            raise FileNotFoundError(f"Question fixture not found: {fixture_path}")

        with open(fixture_path) as f:
            data = json.load(f)

        for key in ("questions", "interview", "interview_questions"):
            if key not in data:
                raise ValueError(
                    f"Fixture {fixture_name} missing required '{key}' section"
                )

        return data

    def _save_questions_from_fixture(
        self, question_payloads: list[dict[str, Any]]
    ) -> tuple[list[UUID], dict[UUID, UUID]]:
        """Persist questions described in fixture payloads."""
        if not question_payloads:
            raise ValueError("Question fixture must include at least one question")

        question_mapper = QuestionMapper()
        question_ids: list[UUID] = []
        question_map: dict[UUID, UUID] = {}

        for payload in question_payloads:
            source_id = self._parse_uuid(payload.get("id"))
            if source_id is None:
                raise ValueError("Question fixture payload missing 'id'")

            generated_id = uuid4()
            question_map[source_id] = generated_id

            question = Question(
                id=generated_id,
                text=payload["text"],
                question_type=QuestionType(
                    payload.get("question_type", QuestionType.TECHNICAL.value)
                ),
                difficulty=Difficulty(
                    payload.get("difficulty", Difficulty.MEDIUM.value)
                ),
                skills=payload.get("skills", []),
                version=payload.get("version", 1),
                ideal_answer=payload.get("ideal_answer"),
                rationale=payload.get("rationale"),
                created_at=self._parse_datetime(payload.get("created_at"))
                or datetime.utcnow(),
                updated_at=self._parse_datetime(payload.get("updated_at"))
                or datetime.utcnow(),
            )

            question_ids.append(question.id)
            self.session.add(question_mapper.to_db_model(question))

        return question_ids, question_map

    def _insert_interview_questions_from_fixture(
        self,
        interview_id: UUID,
        payloads: list[dict[str, Any]],
        question_map: dict[UUID, UUID] | None = None,
    ) -> None:
        """Persist interview_questions rows from fixture payloads."""
        if not payloads:
            raise ValueError(
                "Question fixture must include interview_questions definitions"
            )

        mapper = InterviewQuestionMapper()

        for payload in payloads:
            original_question_id = self._parse_uuid(payload.get("question_id"))
            if original_question_id is None:
                raise ValueError("interview_question payload missing question_id")

            question_id = (
                question_map.get(original_question_id, original_question_id)
                if question_map
                else original_question_id
            )

            interview_question = InterviewQuestion(
                id=uuid4(),
                interview_id=interview_id,
                question_id=question_id,
                sequence_order=payload.get("sequence_order", 0),
                asked_at=self._parse_datetime(payload.get("asked_at")),
                skipped=payload.get("skipped", False),
                skip_reason=payload.get("skip_reason"),
                created_at=self._parse_datetime(payload.get("created_at"))
                or datetime.utcnow(),
            )

            self.session.add(mapper.to_db_model(interview_question))

    def _create_default_interview_questions(
        self, interview_id: UUID, question_ids: list[UUID]
    ) -> None:
        """Fallback creation of interview_questions when no fixture provided."""
        mapper = InterviewQuestionMapper()

        for sequence_order, question_id in enumerate(question_ids):
            interview_question = InterviewQuestion(
                interview_id=interview_id,
                question_id=question_id,
                sequence_order=sequence_order,
                created_at=datetime.utcnow(),
            )
            self.session.add(mapper.to_db_model(interview_question))

    def _parse_datetime(self, value: Any) -> datetime | None:
        """Best-effort datetime parser for fixture fields."""
        if value is None:
            return None
        if isinstance(value, datetime):
            return value

        try:
            return datetime.fromisoformat(str(value))
        except (ValueError, TypeError):
            return None

    def _parse_uuid(self, value: Any) -> UUID | None:
        """Parse UUID values coming from fixture payloads."""
        if value is None:
            return None
        if isinstance(value, UUID):
            return value

        try:
            return UUID(str(value))
        except (ValueError, TypeError):
            return None

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
                text("DELETE FROM interview_questions WHERE interview_id = :id"),
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
