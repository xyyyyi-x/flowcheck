"""环境与允许 origin 路由。"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.dependencies import get_settings
from app.core.errors import AppError
from app.core.schemas import Page
from app.db.async_session import get_async_session
from app.db.models import Environment, Project, User
from app.modules.auth.deps import get_current_user
from app.modules.environments.schemas import (
    EnvironmentCreate,
    EnvironmentRead,
    EnvironmentUpdate,
    TargetOrigins,
)
from app.modules.environments.service import (
    create_environment,
    environment_read,
    get_environment,
    list_environments,
    update_environment,
)
from app.modules.projects.deps import require_owned_project

router = APIRouter(tags=["environments"])

PageNumber = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=100)]


@router.get("/target-origins", response_model=TargetOrigins)
async def target_origins(
    _: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> TargetOrigins:
    return TargetOrigins(items=settings.allowed_origins)


@router.post(
    "/projects/{project_id}/environments",
    response_model=EnvironmentRead,
    status_code=status.HTTP_201_CREATED,
)
async def create(
    payload: EnvironmentCreate,
    project: Project = Depends(require_owned_project),
    db: AsyncSession = Depends(get_async_session),
    settings: Settings = Depends(get_settings),
) -> EnvironmentRead:
    environment = await create_environment(db, project.id, payload, settings)
    return environment_read(environment, settings)


@router.get("/projects/{project_id}/environments", response_model=Page[EnvironmentRead])
async def list_all(
    page: PageNumber = 1,
    page_size: PageSize = 20,
    project: Project = Depends(require_owned_project),
    db: AsyncSession = Depends(get_async_session),
    settings: Settings = Depends(get_settings),
) -> Page[EnvironmentRead]:
    items, total = await list_environments(db, project.id, page, page_size)
    return Page(
        items=[environment_read(item, settings) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/projects/{project_id}/environments/{environment_id}",
    response_model=EnvironmentRead,
)
async def read_one(
    environment_id: uuid.UUID,
    project: Project = Depends(require_owned_project),
    db: AsyncSession = Depends(get_async_session),
    settings: Settings = Depends(get_settings),
) -> EnvironmentRead:
    environment = await _require_environment(db, project.id, environment_id)
    return environment_read(environment, settings)


@router.put(
    "/projects/{project_id}/environments/{environment_id}",
    response_model=EnvironmentRead,
)
async def update(
    environment_id: uuid.UUID,
    payload: EnvironmentUpdate,
    project: Project = Depends(require_owned_project),
    db: AsyncSession = Depends(get_async_session),
    settings: Settings = Depends(get_settings),
) -> EnvironmentRead:
    environment = await _require_environment(db, project.id, environment_id)
    updated = await update_environment(db, environment, payload, settings)
    return environment_read(updated, settings)


async def _require_environment(
    db: AsyncSession, project_id: uuid.UUID, environment_id: uuid.UUID
) -> Environment:
    environment = await get_environment(db, project_id, environment_id)
    if environment is None:
        raise AppError("NOT_FOUND", "资源不存在或无权访问", 404)
    return environment
