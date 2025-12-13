"""Unit tests for question use cases."""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from src.application.dto.question_dto import CreateQuestionRequest, UpdateQuestionRequest
from src.application.use_cases.questions.create_question import CreateQuestionUseCase
from src.application.use_cases.questions.delete_question import DeleteQuestionUseCase
from src.application.use_cases.questions.get_question import GetQuestionUseCase
from src.application.use_cases.questions.list_questions import ListQuestionsUseCase
from src.application.use_cases.questions.update_question import UpdateQuestionUseCase
from src.domain.models.question import Difficulty, Question, QuestionType
from src.application.ports.question_repository_port import QuestionRepositoryPort


class InMemoryQuestionRepo(QuestionRepositoryPort):
    """Simple in-memory repo for testing."""

    def __init__(self):
        self._store: dict[str, Question] = {}

    async def save(self, question: Question) -> Question:
        self._store[str(question.id)] = question
        return question

    async def save_batch(self, questions: list[Question]) -> list[Question]:
        for q in questions:
            await self.save(q)
        return questions

    async def get_by_id(self, question_id):
        return self._store.get(str(question_id))

    async def get_by_ids(self, question_ids):
        return [q for qid, q in self._store.items() if qid in {str(i) for i in question_ids}]

    async def find_by_skill(self, skill: str, difficulty=None, limit: int = 10):
        matches = [
            q for q in self._store.values() if skill in q.skills and (difficulty is None or q.difficulty == difficulty)
        ]
        return matches[:limit]

    async def find_by_type(self, question_type: QuestionType, difficulty=None, limit: int = 10):
        matches = [
            q
            for q in self._store.values()
            if q.question_type == question_type and (difficulty is None or q.difficulty == difficulty)
        ]
        return matches[:limit]

    async def update(self, question: Question) -> Question:
        if str(question.id) not in self._store:
            raise ValueError("not found")
        self._store[str(question.id)] = question
        return question

    async def delete(self, question_id) -> bool:
        return self._store.pop(str(question_id), None) is not None

    async def list_all(self, skip: int = 0, limit: int = 100):
        items = list(self._store.values())
        return items[skip : skip + limit]

    async def list_filtered(self, question_type=None, difficulty=None, skill=None, limit: int = 20, offset: int = 0):
        items = list(self._store.values())
        if question_type:
            items = [q for q in items if q.question_type == question_type]
        if difficulty:
            items = [q for q in items if q.difficulty == difficulty]
        if skill:
            items = [q for q in items if skill in q.skills]
        items.sort(key=lambda q: q.created_at, reverse=True)
        return items[offset : offset + limit]

    async def count_filtered(self, question_type=None, difficulty=None, skill=None) -> int:
        return len(
            await self.list_filtered(
                question_type=question_type,
                difficulty=difficulty,
                skill=skill,
                limit=10_000,
                offset=0,
            )
        )


@pytest.mark.asyncio
async def test_create_and_get_question():
    repo = InMemoryQuestionRepo()
    create_uc = CreateQuestionUseCase(repo)
    get_uc = GetQuestionUseCase(repo)

    request = CreateQuestionRequest(
        text="Explain async/await in Python",
        question_type=QuestionType.TECHNICAL,
        difficulty=Difficulty.MEDIUM,
        skills=["python"],
    )
    created = await create_uc.execute(request)
    fetched = await get_uc.execute(created.id)

    assert fetched is not None
    assert fetched.text == request.text
    assert fetched.question_type == request.question_type
    assert fetched.difficulty == request.difficulty


@pytest.mark.asyncio
async def test_list_questions_with_filters_and_pagination():
    repo = InMemoryQuestionRepo()
    now = datetime.utcnow()
    await repo.save(
        Question(
            text="Q1",
            question_type=QuestionType.TECHNICAL,
            difficulty=Difficulty.EASY,
            skills=["python"],
            created_at=now,
            updated_at=now,
        )
    )
    await repo.save(
        Question(
            text="Q2",
            question_type=QuestionType.BEHAVIORAL,
            difficulty=Difficulty.MEDIUM,
            skills=["communication"],
            created_at=now - timedelta(seconds=1),
            updated_at=now - timedelta(seconds=1),
        )
    )

    list_uc = ListQuestionsUseCase(repo)
    response = await list_uc.execute(
        question_type=QuestionType.TECHNICAL,
        difficulty=None,
        skill="python",
        limit=20,
        offset=0,
    )

    assert response.total == 1
    assert len(response.items) == 1
    assert response.items[0].text == "Q1"


@pytest.mark.asyncio
async def test_update_and_delete_question():
    repo = InMemoryQuestionRepo()
    create_uc = CreateQuestionUseCase(repo)
    update_uc = UpdateQuestionUseCase(repo)
    delete_uc = DeleteQuestionUseCase(repo)

    request = CreateQuestionRequest(
        text="Old",
        question_type=QuestionType.TECHNICAL,
        difficulty=Difficulty.EASY,
        skills=["python"],
    )
    created = await create_uc.execute(request)

    updated = await update_uc.execute(
        created.id,
        UpdateQuestionRequest(text="New text", skills=["python", "asyncio"]),
    )

    assert updated is not None
    assert updated.text == "New text"
    assert "asyncio" in updated.skills

    deleted = await delete_uc.execute(created.id)
    assert deleted is True
    assert await repo.get_by_id(created.id) is None

