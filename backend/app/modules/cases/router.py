"""用例路由。"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.schemas import Page
from app.db.async_session import get_async_session
from app.db.models import Case, Project
from app.modules.cases.schemas import CaseCreate, CaseRead, CaseUpdate
from app.modules.cases.service import create_case, get_case, list_cases, update_case
from app.modules.projects.deps import require_owned_project

router = APIRouter(tags=["cases"])

PageNumber = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=100)]


@router.post(
    "/projects/{project_id}/cases",
    response_model=CaseRead,
    status_code=status.HTTP_201_CREATED,
)
async def create(
    payload: CaseCreate,
    project: Project = Depends(require_owned_project),
    db: AsyncSession = Depends(get_async_session),
) -> CaseRead:
    case = await create_case(db, project.id, payload)
    return CaseRead.model_validate(case)


@router.get("/projects/{project_id}/cases", response_model=Page[CaseRead])
async def list_all(
    page: PageNumber = 1,
    page_size: PageSize = 20,
    project: Project = Depends(require_owned_project),
    db: AsyncSession = Depends(get_async_session),
) -> Page[CaseRead]:
    items, total = await list_cases(db, project.id, page, page_size)
    return Page(
        items=[CaseRead.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/projects/{project_id}/cases/{case_id}", response_model=CaseRead)
async def read_one(
    case_id: uuid.UUID,
    project: Project = Depends(require_owned_project),
    db: AsyncSession = Depends(get_async_session),
) -> CaseRead:
    case = await _require_case(db, project.id, case_id)
    return CaseRead.model_validate(case)


@router.put("/projects/{project_id}/cases/{case_id}", response_model=CaseRead)
async def update(
    case_id: uuid.UUID,
    payload: CaseUpdate,
    project: Project = Depends(require_owned_project),
    db: AsyncSession = Depends(get_async_session),
) -> CaseRead:
    case = await _require_case(db, project.id, case_id)
    updated = await update_case(db, case, payload)
    return CaseRead.model_validate(updated)


async def _require_case(db: AsyncSession, project_id: uuid.UUID, case_id: uuid.UUID) -> Case:
    case = await get_case(db, project_id, case_id)
    if case is None:
        raise AppError("NOT_FOUND", "资源不存在或无权访问", 404)
    return case
