"""项目路由。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.schemas import Page
from app.db.async_session import get_async_session
from app.db.models import Project, User
from app.modules.auth.deps import get_current_user
from app.modules.projects.deps import require_owned_project
from app.modules.projects.schemas import (
    ProjectCreate,
    ProjectRead,
    ProjectUpdate,
)
from app.modules.projects.service import (
    create_project,
    list_projects,
    update_project,
)

router = APIRouter(tags=["projects"])

PageNumber = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=100)]


@router.post("/projects", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
async def create(
    payload: ProjectCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
) -> ProjectRead:
    project = await create_project(db, user.id, payload)
    return ProjectRead.model_validate(project)


@router.get("/projects", response_model=Page[ProjectRead])
async def list_all(
    page: PageNumber = 1,
    page_size: PageSize = 20,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
) -> Page[ProjectRead]:
    projects, total = await list_projects(db, user.id, page, page_size)
    return Page(
        items=[ProjectRead.model_validate(item) for item in projects],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/projects/{project_id}", response_model=ProjectRead)
async def read_one(project: Project = Depends(require_owned_project)) -> ProjectRead:
    return ProjectRead.model_validate(project)


@router.put("/projects/{project_id}", response_model=ProjectRead)
async def update_one(
    payload: ProjectUpdate,
    project: Project = Depends(require_owned_project),
    db: AsyncSession = Depends(get_async_session),
) -> ProjectRead:
    updated = await update_project(db, project, payload)
    return ProjectRead.model_validate(updated)
