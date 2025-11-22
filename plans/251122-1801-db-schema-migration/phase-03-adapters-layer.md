# Phase 3: Adapters Layer - Persistence

## Context Links

- **Parent Plan**: [plan.md](./plan.md)
- **Previous Phase**: [phase-02-domain-layer.md](./phase-02-domain-layer.md)
- **Next Phase**: [phase-04-application-layer.md](./phase-04-application-layer.md)
- **Dependencies**: Phase 1 (DB migrated), Phase 2 (domain models updated)
- **Documentation**: [System Architecture](../../docs/system-architecture.md)

---

## Overview

**Date**: 2025-11-22
**Priority**: 🔴 Critical
**Estimated Duration**: 3-4 hours
**Implementation Status**: ⏳ Pending
**Review Status**: ⏳ Pending

**Description**: Update repositories, SQLAlchemy models, and mappers for new schema.

---

## Key Insights

- Repositories must query junction tables (`cv_skills`, `interview_questions`) via JOINs
- SQLAlchemy models must match new schema (ENUMs, decomposed columns)
- Mappers convert between DB models and domain entities
- Clean Architecture: Adapters depend on domain (not vice versa)
- New repository methods: `get_cv_analysis_with_skills`, `add_question_to_interview`, `get_current_question`

---

## Requirements

### Functional Requirements
- Update SQLAlchemy models for new schema
- Create mappers for new entities (`CVSkill`, `InterviewQuestion`)
- Add repository methods for junction table queries
- Support ENUM filtering in question repository
- Handle decomposed `prompt_template` fields

### Non-Functional Requirements
- Maintain backward compatibility where possible
- Optimize JOIN queries (use indexes)
- Keep repository methods simple (single responsibility)
- Follow existing repository patterns

---

## Architecture

**Layer**: Adapters (Persistence)
**Pattern**: Repository Pattern + Data Mapper

```
Domain Models (Phase 2)
       ↓
   Mappers (bi-directional conversion)
       ↓
SQLAlchemy Models (DB schema)
       ↓
  Repositories (CRUD + business queries)
       ↓
   Database
```

**Key Changes**:
- Add `CVSkillModel`, `InterviewQuestionModel` (SQLAlchemy)
- Update existing models (remove columns, add ENUMs)
- Create `CVSkillMapper`, `InterviewQuestionMapper`
- Extend repositories with new methods

---

## Related Code Files

### Files to Modify
- `src/adapters/persistence/models.py` (10 models)
- `src/adapters/persistence/mappers.py` (add 2 mappers, update 4)
- `src/adapters/persistence/cv_analysis_repository.py` (add 3 methods)
- `src/adapters/persistence/interview_repository.py` (add 4 methods)
- `src/adapters/persistence/question_repository.py` (update filters)
- `src/adapters/persistence/answer_repository.py` (remove candidate_id references)
- `src/adapters/persistence/postgres_prompt_repository.py` (handle decomposed fields)

### Files to Create
None (all updates to existing files)

---

## Implementation Steps

### Step 1: Update `src/adapters/persistence/models.py` (60 mins)

```python
# Add new models
from sqlalchemy import Column, String, Float, Boolean, Integer, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
import enum

# Proficiency Level ENUM
class ProficiencyLevelEnum(str, enum.Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"

# CV Skill Model (NEW)
class CVSkillModel(Base):
    __tablename__ = "cv_skills"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    cv_analysis_id = Column(UUID(as_uuid=True), ForeignKey("cv_analyses.id", ondelete="CASCADE"), nullable=False)
    skill_name = Column(String(100), nullable=False)
    proficiency_level = Column(SAEnum(ProficiencyLevelEnum), nullable=True)
    years_of_experience = Column(Float, nullable=True)
    is_primary = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    # Relationship
    cv_analysis = relationship("CVAnalysisModel", back_populates="skills")

# Interview Question Model (NEW)
class InterviewQuestionModel(Base):
    __tablename__ = "interview_questions"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    interview_id = Column(UUID(as_uuid=True), ForeignKey("interviews.id", ondelete="CASCADE"), nullable=False)
    question_id = Column(UUID(as_uuid=True), ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    sequence_order = Column(Integer, nullable=False)
    asked_at = Column(DateTime, nullable=True)
    skipped = Column(Boolean, default=False, nullable=False)
    skip_reason = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    # Relationships
    interview = relationship("InterviewModel", back_populates="interview_questions")
    question = relationship("QuestionModel")

# Update CVAnalysisModel
class CVAnalysisModel(Base):
    __tablename__ = "cv_analyses"

    # REMOVE: cv_file_path, skills (JSONB), metadata
    # ADD: relationship to cv_skills
    skills = relationship("CVSkillModel", back_populates="cv_analysis", cascade="all, delete-orphan")

# Update QuestionModel
class QuestionModel(Base):
    __tablename__ = "questions"

    # CHANGE to ENUM
    question_type = Column(SAEnum("technical", "behavioral", "situational", "problem_solving", "system_design", name="question_type_enum"), nullable=False)
    difficulty = Column(SAEnum("easy", "medium", "hard", "expert", name="difficulty_enum"), nullable=False)

    # REMOVE: tags, evaluation_criteria

# Update InterviewModel
class InterviewModel(Base):
    __tablename__ = "interviews"

    # REMOVE: question_ids, answer_ids arrays
    # ADD: relationship to interview_questions
    interview_questions = relationship("InterviewQuestionModel", back_populates="interview", cascade="all, delete-orphan")

# Update AnswerModel
class AnswerModel(Base):
    __tablename__ = "answers"

    # REMOVE: candidate_id, metadata, evaluation, gaps, similarity_score, evaluated_at

# Update PromptTemplateModel
class PromptTemplateModel(Base):
    __tablename__ = "prompt_templates"

    # ADD: Decomposed fields
    system_prompt = Column(String, nullable=False)
    user_template = Column(String, nullable=False)
    input_variables = Column(ARRAY(String), server_default='{}', nullable=False)
    partial_variables = Column(JSONB, server_default='{}', nullable=False)
    output_parser_type = Column(String(50), server_default='json_output_parser', nullable=False)
    output_schema = Column(JSONB, nullable=False)
    temperature = Column(Numeric(3, 2), server_default='0.3', nullable=False)
    max_tokens = Column(Integer, server_default='2000', nullable=False)
    top_p = Column(Numeric(3, 2), server_default='0.95', nullable=False)
    frequency_penalty = Column(Numeric(3, 2), server_default='0', nullable=False)
    presence_penalty = Column(Numeric(3, 2), server_default='0', nullable=False)
    deleted_at = Column(DateTime, nullable=True)

    # template_json is computed column (read-only)
```

### Step 2: Update `src/adapters/persistence/mappers.py` (45 mins)

Add mappers for new models:

```python
from src.domain.models import CVSkill, ProficiencyLevel, InterviewQuestion

class CVSkillMapper:
    """Map between CVSkillModel and CVSkill domain entity."""

    @staticmethod
    def to_domain(model: CVSkillModel) -> CVSkill:
        return CVSkill(
            id=model.id,
            cv_analysis_id=model.cv_analysis_id,
            skill_name=model.skill_name,
            proficiency_level=ProficiencyLevel(model.proficiency_level) if model.proficiency_level else None,
            years_of_experience=model.years_of_experience,
            is_primary=model.is_primary,
            created_at=model.created_at
        )

    @staticmethod
    def to_model(entity: CVSkill) -> CVSkillModel:
        return CVSkillModel(
            id=entity.id,
            cv_analysis_id=entity.cv_analysis_id,
            skill_name=entity.skill_name,
            proficiency_level=entity.proficiency_level.value if entity.proficiency_level else None,
            years_of_experience=entity.years_of_experience,
            is_primary=entity.is_primary,
            created_at=entity.created_at
        )

class InterviewQuestionMapper:
    """Map between InterviewQuestionModel and InterviewQuestion domain entity."""

    @staticmethod
    def to_domain(model: InterviewQuestionModel) -> InterviewQuestion:
        return InterviewQuestion(
            id=model.id,
            interview_id=model.interview_id,
            question_id=model.question_id,
            sequence_order=model.sequence_order,
            asked_at=model.asked_at,
            skipped=model.skipped,
            skip_reason=model.skip_reason,
            created_at=model.created_at
        )

    @staticmethod
    def to_model(entity: InterviewQuestion) -> InterviewQuestionModel:
        return InterviewQuestionModel(
            id=entity.id,
            interview_id=entity.interview_id,
            question_id=entity.question_id,
            sequence_order=entity.sequence_order,
            asked_at=entity.asked_at,
            skipped=entity.skipped,
            skip_reason=entity.skip_reason,
            created_at=entity.created_at
        )

# Update CVAnalysisMapper
class CVAnalysisMapper:
    @staticmethod
    def to_domain(model: CVAnalysisModel) -> CVAnalysis:
        return CVAnalysis(
            # ...
            skills=[CVSkillMapper.to_domain(s) for s in model.skills],  # NEW: map skills relationship
            # REMOVE: cv_file_path, metadata mapping
        )
```

### Step 3: Update `src/adapters/persistence/cv_analysis_repository.py` (30 mins)

```python
class PostgresCVAnalysisRepository:
    async def get_by_id(self, cv_analysis_id: UUID) -> CVAnalysis:
        """Get CV analysis with skills (via JOIN)."""
        async with self.session() as session:
            # Use joinedload to eager load skills
            result = await session.execute(
                select(CVAnalysisModel)
                .options(joinedload(CVAnalysisModel.skills))
                .where(CVAnalysisModel.id == cv_analysis_id)
            )
            model = result.scalar_one_or_none()
            if not model:
                raise NotFoundError(f"CVAnalysis {cv_analysis_id} not found")
            return CVAnalysisMapper.to_domain(model)

    async def add_skill(self, cv_skill: CVSkill) -> CVSkill:
        """Add skill to CV analysis."""
        async with self.session() as session:
            model = CVSkillMapper.to_model(cv_skill)
            session.add(model)
            await session.commit()
            await session.refresh(model)
            return CVSkillMapper.to_domain(model)

    async def remove_skill(self, skill_id: UUID) -> None:
        """Remove skill from CV analysis."""
        async with self.session() as session:
            await session.execute(
                delete(CVSkillModel).where(CVSkillModel.id == skill_id)
            )
            await session.commit()
```

### Step 4: Update `src/adapters/persistence/interview_repository.py` (45 mins)

```python
class PostgresInterviewRepository:
    async def get_interview_questions(self, interview_id: UUID) -> list[InterviewQuestion]:
        """Get questions for interview (via junction table)."""
        async with self.session() as session:
            result = await session.execute(
                select(InterviewQuestionModel)
                .where(InterviewQuestionModel.interview_id == interview_id)
                .order_by(InterviewQuestionModel.sequence_order)
            )
            models = result.scalars().all()
            return [InterviewQuestionMapper.to_domain(m) for m in models]

    async def add_question(self, interview_id: UUID, question_id: UUID, sequence_order: int) -> InterviewQuestion:
        """Add question to interview with sequence."""
        async with self.session() as session:
            iq = InterviewQuestionModel(
                interview_id=interview_id,
                question_id=question_id,
                sequence_order=sequence_order
            )
            session.add(iq)
            await session.commit()
            await session.refresh(iq)
            return InterviewQuestionMapper.to_domain(iq)

    async def get_current_question(self, interview_id: UUID) -> Question | None:
        """Get current question based on interview.current_question_index."""
        async with self.session() as session:
            result = await session.execute(
                select(QuestionModel)
                .join(InterviewQuestionModel, InterviewQuestionModel.question_id == QuestionModel.id)
                .join(InterviewModel, InterviewModel.id == InterviewQuestionModel.interview_id)
                .where(InterviewModel.id == interview_id)
                .where(InterviewQuestionModel.sequence_order == InterviewModel.current_question_index)
            )
            model = result.scalar_one_or_none()
            return QuestionMapper.to_domain(model) if model else None

    async def mark_question_asked(self, interview_id: UUID, sequence_order: int) -> None:
        """Mark question as asked (set timestamp)."""
        async with self.session() as session:
            await session.execute(
                update(InterviewQuestionModel)
                .where(InterviewQuestionModel.interview_id == interview_id)
                .where(InterviewQuestionModel.sequence_order == sequence_order)
                .values(asked_at=func.now())
            )
            await session.commit()
```

### Step 5: Update `src/adapters/persistence/question_repository.py` (20 mins)

```python
# Update filter methods to use ENUM
async def find_by_type(self, question_type: QuestionType) -> list[Question]:
    """Find questions by type (ENUM)."""
    async with self.session() as session:
        result = await session.execute(
            select(QuestionModel)
            .where(QuestionModel.question_type == question_type.value)
        )
        models = result.scalars().all()
        return [QuestionMapper.to_domain(m) for m in models]
```

### Step 6: Update `src/adapters/persistence/postgres_prompt_repository.py` (30 mins)

```python
async def create(self, prompt: PromptTemplate) -> PromptTemplate:
    """Create prompt with decomposed fields."""
    async with self.session() as session:
        model = PromptTemplateModel(
            name=prompt.name,
            version=prompt.version,
            system_prompt=prompt.system_prompt,
            user_template=prompt.user_template,
            input_variables=prompt.input_variables,
            output_schema=prompt.output_schema,
            temperature=prompt.temperature,
            max_tokens=prompt.max_tokens,
            # ... other fields
            # template_json is auto-generated by DB
        )
        session.add(model)
        await session.commit()
        await session.refresh(model)  # Gets computed template_json
        return PromptTemplateMapper.to_domain(model)
```

---

## Todo List

- [ ] Update `models.py`: Add `CVSkillModel`, `InterviewQuestionModel`
- [ ] Update `models.py`: Modify 6 existing models (remove columns, add ENUMs)
- [ ] Update `mappers.py`: Add `CVSkillMapper`, `InterviewQuestionMapper`
- [ ] Update `mappers.py`: Update `CVAnalysisMapper`, `QuestionMapper`
- [ ] Update `cv_analysis_repository.py`: Add `add_skill`, `remove_skill`
- [ ] Update `interview_repository.py`: Add 4 new methods
- [ ] Update `question_repository.py`: ENUM filters
- [ ] Update `answer_repository.py`: Remove `candidate_id` references
- [ ] Update `postgres_prompt_repository.py`: Handle decomposed fields
- [ ] Run repository tests: `pytest tests/integration/adapters/persistence/`

---

## Success Criteria

- ✅ All SQLAlchemy models match new schema
- ✅ Mappers convert correctly (domain ↔ DB)
- ✅ Repository queries work (JOINs return correct data)
- ✅ ENUM filtering works in question repository
- ✅ No import errors
- ✅ Integration tests pass (>85%)

---

## Risk Assessment

### Risk 1: JOIN Query Performance
**Likelihood**: Low
**Impact**: Medium
**Mitigation**: Migration created indexes on FK columns; monitor query times

### Risk 2: ENUM Mapping Errors
**Likelihood**: Medium
**Impact**: Medium
**Mitigation**: Test ENUM conversion in mappers; add unit tests

---

## Next Steps

**On Success**: Proceed to [Phase 4: Application Layer](./phase-04-application-layer.md)
**On Failure**: Debug repository queries, check mapper logic

---

**Phase Status**: ⏳ Pending
**Blocker**: Phase 2 (Domain Layer) must be complete
