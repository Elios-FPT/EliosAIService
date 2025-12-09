"""Prompt template REST API endpoints."""

from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from ....application.dto.prompt_dto import (
    ActivatePromptRequest,
    AnalyticsSummaryResponse,
    AuditTrailResponse,
    CreatePromptRequest,
    CreateVersionRequest,
    PaginatedPromptsResponse,
    PromptTemplateResponse,
    RollbackRequest,
    UpdateDraftPromptRequest,
    VersionHistoryResponse,
)
from ....infrastructure.database.session import get_async_session
from ....infrastructure.dependency_injection.container import get_container

router = APIRouter(prefix="/prompts", tags=["Prompt Management"])




# ========== Version Management Endpoints ==========


@router.post("", response_model=PromptTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_initial_prompt(
    request: CreatePromptRequest,
    session: AsyncSession = Depends(get_async_session),
) -> PromptTemplateResponse:
    """Create initial prompt version (v1).

    Args:
        request: CreatePromptRequest with prompt configuration
        session: Database session

    Returns:
        Created PromptTemplateResponse

    Raises:
        HTTPException: 400 if prompt already exists or validation fails
    """
    container = get_container()
    prompt_repo = container.prompt_repository_port(session=session)

    try:
        prompt = await prompt_repo.create_initial_prompt(
            name=request.prompt_name,
            system_prompt=request.system_prompt,
            user_template=request.user_template,
            input_variables=request.input_variables,
            partial_variables=request.partial_variables or {},
            output_schema=request.output_schema or {},
            temperature=Decimal(str(request.temperature)),
            max_tokens=request.max_tokens,
            top_p=Decimal(str(request.top_p)),
            frequency_penalty=Decimal(str(request.frequency_penalty)),
            presence_penalty=Decimal(str(request.presence_penalty)),
            created_by=request.created_by,
        )
        return PromptTemplateResponse.from_domain(prompt)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.post(
    "/{name}/versions",
    response_model=PromptTemplateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_new_version(
    name: str,
    request: CreateVersionRequest,
    session: AsyncSession = Depends(get_async_session),
) -> PromptTemplateResponse:
    """Create new version from parent version.

    Args:
        name: Prompt name
        request: CreateVersionRequest with new configuration
        session: Database session

    Returns:
        Created PromptTemplateResponse

    Raises:
        HTTPException: 400 if parent version not found or validation fails
    """
    container = get_container()
    prompt_repo = container.prompt_repository_port(session=session)

    try:
        prompt = await prompt_repo.create_new_version(
            name=name,
            parent_version=request.parent_version,
            system_prompt=request.system_prompt,
            user_template=request.user_template,
            input_variables=request.input_variables,
            partial_variables=request.partial_variables or {},
            output_schema=request.output_schema or {},
            temperature=Decimal(str(request.temperature)),
            max_tokens=request.max_tokens,
            top_p=Decimal(str(request.top_p)),
            frequency_penalty=Decimal(str(request.frequency_penalty)),
            presence_penalty=Decimal(str(request.presence_penalty)),
            change_summary=request.change_summary,
            created_by=request.created_by,
        )
        return PromptTemplateResponse.from_domain(prompt)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.patch(
    "/{prompt_id}/draft",
    response_model=PromptTemplateResponse,
)
async def update_draft_prompt_version(
    prompt_id: UUID,
    request: UpdateDraftPromptRequest,
    session: AsyncSession = Depends(get_async_session),
) -> PromptTemplateResponse:
    """Update the content of a draft prompt version.

    Args:
        prompt_id: Prompt version UUID
        request: UpdateDraftPromptRequest with updated template content and params

    Returns:
        Updated PromptTemplateResponse

    Raises:
        HTTPException: 404 if prompt not found, 400 if version is not draft
    """
    container = get_container()
    prompt_repo = container.prompt_repository_port(session=session)

    try:
        prompt = await prompt_repo.update_draft_prompt(
            prompt_id=prompt_id,
            updates={
                "system_prompt": request.system_prompt,
                "user_template": request.user_template,
                "input_variables": request.input_variables,
                "partial_variables": request.partial_variables or {},
                "output_schema": request.output_schema or {},
                "temperature": Decimal(str(request.temperature)),
                "max_tokens": request.max_tokens,
                "top_p": Decimal(str(request.top_p)),
                "frequency_penalty": Decimal(str(request.frequency_penalty)),
                "presence_penalty": Decimal(str(request.presence_penalty)),
            },
        )
        return PromptTemplateResponse.from_domain(prompt)
    except LookupError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.post(
    "/{name}/rollback",
    response_model=PromptTemplateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def rollback_prompt(
    name: str,
    request: RollbackRequest,
    session: AsyncSession = Depends(get_async_session),
) -> PromptTemplateResponse:
    """Rollback to target version by creating new version with target's content.

    Args:
        name: Prompt name
        request: RollbackRequest with target version and reason

    Returns:
        Created PromptTemplateResponse (new version with target's content)

    Raises:
        HTTPException: 400 if target version not found
    """
    container = get_container()
    prompt_repo = container.prompt_repository_port(session=session)

    try:
        prompt = await prompt_repo.rollback_to_version(
            name=name,
            target_version=request.target_version,
            changed_by=request.changed_by,
            reason=request.reason,
        )
        return PromptTemplateResponse.from_domain(prompt)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.get("/{name}/versions", response_model=list[VersionHistoryResponse])
async def get_version_history(
    name: str,
    session: AsyncSession = Depends(get_async_session),
) -> list[VersionHistoryResponse]:
    """Get version history with diffs.

    Args:
        name: Prompt name

    Returns:
        List of VersionHistoryResponse (empty list if prompt doesn't exist)
    """
    container = get_container()
    prompt_repo = container.prompt_repository_port(session=session)

    history = await prompt_repo.get_version_history(name)

    return [
        VersionHistoryResponse(
            id=entry["id"],
            version=entry["version"],
            created_at=entry["created_at"],
            created_by=entry.get("created_by"),
            change_summary=entry.get("change_summary"),
            is_active=entry["is_active"],
            is_draft=entry.get("is_draft", False),
            parent_version_id=entry.get("parent_version_id"),
            diff=entry.get("diff"),
        )
        for entry in history
    ]


@router.get(
    "/{name}/versions/{version}",
    response_model=PromptTemplateResponse,
)
async def get_specific_version(
    name: str,
    version: int,
    session: AsyncSession = Depends(get_async_session),
) -> PromptTemplateResponse:
    """Get specific version by name and version number.

    Args:
        name: Prompt name
        version: Version number

    Returns:
        PromptTemplateResponse

    Raises:
        HTTPException: 404 if version not found
    """
    container = get_container()
    prompt_repo = container.prompt_repository_port(session=session)

    prompt = await prompt_repo.get_version(name, version)

    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prompt '{name}' version {version} not found",
        )

    return PromptTemplateResponse.from_domain(prompt)


@router.get("/{prompt_id}", response_model=PromptTemplateResponse)
async def get_prompt_by_id(
    prompt_id: UUID,
    session: AsyncSession = Depends(get_async_session),
) -> PromptTemplateResponse:
    """Get prompt by UUID.

    Args:
        prompt_id: Prompt UUID

    Returns:
        PromptTemplateResponse

    Raises:
        HTTPException: 404 if prompt not found
    """
    container = get_container()
    prompt_repo = container.prompt_repository_port(session=session)

    prompt = await prompt_repo.get_by_id(prompt_id)

    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prompt {prompt_id} not found",
        )

    return PromptTemplateResponse.from_domain(prompt)


# ========== Activation Endpoints ==========


@router.patch("/{prompt_id}/activate", status_code=status.HTTP_204_NO_CONTENT)
async def activate_prompt_version(
    prompt_id: UUID,
    request: ActivatePromptRequest,
    session: AsyncSession = Depends(get_async_session),
) -> None:
    """Activate prompt version (deactivates all other versions).

    Args:
        prompt_id: Prompt version UUID to activate
        request: ActivatePromptRequest with activation details

    Raises:
        HTTPException: 404 if prompt not found, 400 if validation fails
    """
    container = get_container()
    prompt_repo = container.prompt_repository_port(session=session)

    # Verify prompt exists
    prompt = await prompt_repo.get_by_id(prompt_id)
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prompt {prompt_id} not found",
        )

    try:
        await prompt_repo.activate_version(
            prompt_id=prompt_id,
            changed_by=request.changed_by,
            reason=request.reason,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.get("/{name}/active", response_model=PromptTemplateResponse)
async def get_active_prompt(
    name: str,
    session: AsyncSession = Depends(get_async_session),
) -> PromptTemplateResponse:
    """Get active prompt version.

    Args:
        name: Prompt name

    Returns:
        PromptTemplateResponse (active version)

    Raises:
        HTTPException: 404 if no active version exists
    """
    container = get_container()
    prompt_repo = container.prompt_repository_port(session=session)

    prompt = await prompt_repo.get_active_prompt(name)

    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active version found for prompt '{name}'",
        )

    return PromptTemplateResponse.from_domain(prompt)


@router.patch(
    "/{prompt_id}/publish",
    response_model=PromptTemplateResponse,
    status_code=status.HTTP_200_OK,
)
async def publish_draft_prompt(
    prompt_id: UUID,
    session: AsyncSession = Depends(get_async_session),
) -> PromptTemplateResponse:
    """Publish a draft prompt version (change is_draft from True to False).

    Args:
        prompt_id: Prompt version UUID to publish
        session: Database session

    Returns:
        Updated PromptTemplateResponse with is_draft=False

    Raises:
        HTTPException: 404 if prompt not found, 400 if not a draft or validation fails
    """
    container = get_container()
    prompt_repo = container.prompt_repository_port(session=session)

    # Get prompt
    prompt = await prompt_repo.get_by_id(prompt_id)
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prompt {prompt_id} not found",
        )

    # Validate it's a draft
    if not prompt.is_draft:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Prompt {prompt_id} is not a draft (already published)",
        )

    # Update is_draft to False
    prompt.is_draft = False

    try:
        # Update via repository
        updated_prompt = await prompt_repo.update(prompt)
        return PromptTemplateResponse.from_domain(updated_prompt)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


# ========== Analytics, Audit & Lifecycle Endpoints ==========


@router.get("/{name}/analytics", response_model=AnalyticsSummaryResponse)
async def get_analytics_summary(
    name: str,
    session: AsyncSession = Depends(get_async_session),
) -> AnalyticsSummaryResponse:
    """Get analytics summary for prompt.

    Args:
        name: Prompt name
        session: Database session

    Returns:
        AnalyticsSummaryResponse with execution metrics

    Raises:
        HTTPException: 404 if prompt never executed (no analytics data)
    """
    container = get_container()
    prompt_repo = container.prompt_repository_port(session=session)

    summary = await prompt_repo.get_analytics_summary(name)

    if not summary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No analytics data found for prompt '{name}'",
        )

    return AnalyticsSummaryResponse(
        prompt_name=name,
        total_executions=summary["total_executions"],
        avg_prompt_tokens=summary["avg_prompt_tokens"],
        avg_completion_tokens=summary["avg_completion_tokens"],
        avg_latency_ms=summary["avg_latency_ms"],
        success_rate=summary["success_rate"],
        estimated_cost_usd=summary["estimated_cost_usd"],
        last_executed_at=summary.get("last_executed_at"),
    )


@router.get("/{name}/audit-trail", response_model=list[AuditTrailResponse])
async def get_audit_trail(
    name: str,
    session: AsyncSession = Depends(get_async_session),
) -> list[AuditTrailResponse]:
    """Get audit trail of metadata changes for prompt.

    Args:
        name: Prompt name
        session: Database session

    Returns:
        List of AuditTrailResponse (empty list if no changes)
    """
    container = get_container()
    prompt_repo = container.prompt_repository_port(session=session)

    trail = await prompt_repo.get_audit_trail(name)

    return [
        AuditTrailResponse(
            field_name=entry["field_name"],
            old_value=entry["old_value"],
            new_value=entry["new_value"],
            changed_by=entry["changed_by"],
            changed_at=entry["changed_at"],
        )
        for entry in trail
    ]


@router.get("", response_model=PaginatedPromptsResponse)
async def list_prompts(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    is_active: bool | None = Query(None, description="Filter by active status"),
    include_deleted: bool = Query(False, description="Include soft-deleted prompts"),
    session: AsyncSession = Depends(get_async_session),
) -> PaginatedPromptsResponse:
    """List all prompts with pagination and filters.

    Args:
        page: Page number (1-indexed)
        page_size: Items per page (1-100, default 20)
        is_active: Filter by active status (None = no filter)
        include_deleted: Include soft-deleted prompts (default: False)
        session: Database session

    Returns:
        PaginatedPromptsResponse with prompts and pagination metadata
    """
    container = get_container()
    prompt_repo = container.prompt_repository_port(session=session)

    offset = (page - 1) * page_size
    prompts, total = await prompt_repo.list_prompts(
        limit=page_size,
        offset=offset,
        is_active=is_active,
        include_deleted=include_deleted,
    )

    prompt_responses = [PromptTemplateResponse.from_domain(p) for p in prompts]
    has_next = page * page_size < total

    return PaginatedPromptsResponse(
        prompts=prompt_responses,
        total=total,
        page=page,
        page_size=page_size,
        has_next=has_next,
    )


@router.delete("/{prompt_id}", status_code=status.HTTP_204_NO_CONTENT)
async def soft_delete_prompt(
    prompt_id: UUID,
    session: AsyncSession = Depends(get_async_session),
) -> None:
    """Soft delete prompt template.

    Sets deleted_at timestamp and deactivates the prompt.
    Preserves all data for audit purposes.

    Args:
        prompt_id: Prompt UUID
        session: Database session

    Raises:
        HTTPException: 404 if prompt not found, 400 if already deleted
    """
    container = get_container()
    prompt_repo = container.prompt_repository_port(session=session)

    prompt = await prompt_repo.get_by_id(prompt_id)

    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prompt {prompt_id} not found",
        )

    if prompt.is_deleted():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Prompt {prompt_id} is already deleted",
        )

    # Use domain method to soft delete
    prompt.soft_delete()

    # Update via repository (follows Clean Architecture)
    await prompt_repo.update(prompt)
