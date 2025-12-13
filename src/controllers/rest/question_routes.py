"""Question CRUD REST API endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...application.dto.question_dto import (
    CreateQuestionRequest,
    QuestionListResponse,
    QuestionResponse,
    UpdateQuestionRequest,
)
from ...application.use_cases.questions.create_question import CreateQuestionUseCase
from ...application.use_cases.questions.delete_question import DeleteQuestionUseCase
from ...application.use_cases.questions.get_question import GetQuestionUseCase
from ...application.use_cases.questions.list_questions import ListQuestionsUseCase
from ...application.use_cases.questions.update_question import UpdateQuestionUseCase
from ...domain.models.question import Difficulty, QuestionType
from ...infrastructure.database.session import get_async_session
from ...infrastructure.dependency_injection.container import get_container

router = APIRouter(prefix="/questions", tags=["Questions"])


@router.get(
    "",
    response_model=QuestionListResponse,
    summary="List questions with optional filters",
)
async def list_questions(
    question_type: QuestionType | None = Query(default=None, description="Filter by type"),
    difficulty: Difficulty | None = Query(default=None, description="Filter by difficulty"),
    skill: str | None = Query(default=None, description="Filter by skill"),
    limit: int = Query(default=20, ge=1, le=100, description="Page size"),
    offset: int = Query(default=0, ge=0, description="Items to skip"),
    session: AsyncSession = Depends(get_async_session),
):
    container = get_container()
    repo = container.question_repository_port(session=session)
    use_case = ListQuestionsUseCase(question_repo=repo)
    return await use_case.execute(
        question_type=question_type,
        difficulty=difficulty,
        skill=skill,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{question_id}",
    response_model=QuestionResponse,
    summary="Get question by id",
)
async def get_question(
    question_id: UUID,
    session: AsyncSession = Depends(get_async_session),
):
    container = get_container()
    repo = container.question_repository_port(session=session)
    use_case = GetQuestionUseCase(question_repo=repo)
    question = await use_case.execute(question_id)
    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Question {question_id} not found",
        )
    return QuestionResponse.from_domain(question)


@router.post(
    "",
    response_model=QuestionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a question",
)
async def create_question(
    payload: CreateQuestionRequest,
    session: AsyncSession = Depends(get_async_session),
):
    container = get_container()
    repo = container.question_repository_port(session=session)
    use_case = CreateQuestionUseCase(question_repo=repo)
    question = await use_case.execute(payload)
    return QuestionResponse.from_domain(question)


@router.patch(
    "/{question_id}",
    response_model=QuestionResponse,
    summary="Partially update a question",
)
async def patch_question(
    question_id: UUID,
    payload: UpdateQuestionRequest,
    session: AsyncSession = Depends(get_async_session),
):
    container = get_container()
    repo = container.question_repository_port(session=session)
    use_case = UpdateQuestionUseCase(question_repo=repo)
    updated = await use_case.execute(question_id, payload)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Question {question_id} not found",
        )
    return QuestionResponse.from_domain(updated)


@router.put(
    "/{question_id}",
    response_model=QuestionResponse,
    summary="Replace a question",
)
async def put_question(
    question_id: UUID,
    payload: CreateQuestionRequest,
    session: AsyncSession = Depends(get_async_session),
):
    container = get_container()
    repo = container.question_repository_port(session=session)
    get_use_case = GetQuestionUseCase(question_repo=repo)
    existing = await get_use_case.execute(question_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Question {question_id} not found",
        )

    update_use_case = UpdateQuestionUseCase(question_repo=repo)
    updated = await update_use_case.execute(
        question_id=question_id,
        request=UpdateQuestionRequest(
            text=payload.text,
            question_type=payload.question_type,
            difficulty=payload.difficulty,
            skills=payload.skills,
            ideal_answer=payload.ideal_answer,
            rationale=payload.rationale,
        ),
    )
    return QuestionResponse.from_domain(updated)


@router.delete(
    "/{question_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a question",
)
async def delete_question(
    question_id: UUID,
    session: AsyncSession = Depends(get_async_session),
):
    container = get_container()
    repo = container.question_repository_port(session=session)
    use_case = DeleteQuestionUseCase(question_repo=repo)
    deleted = await use_case.execute(question_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Question {question_id} not found",
        )
    return None

