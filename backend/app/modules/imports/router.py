"""OpenAPI 导入与接口定义读取路由。"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.schemas import Page
from app.db.async_session import get_async_session
from app.db.models import Project
from app.modules.imports.parser import MAX_BYTES
from app.modules.imports.schemas import ApiDefinitionRead, ImportResult
from app.modules.imports.service import (
    get_api_definition,
    import_openapi,
    list_api_definitions,
)
from app.modules.projects.deps import require_owned_project

router = APIRouter(tags=["imports"])

PageNumber = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=100)]


@router.post(
    "/projects/{project_id}/imports/openapi",
    response_model=ImportResult,
    status_code=status.HTTP_201_CREATED,
)
async def import_document(
    file: UploadFile = File(...),
    project: Project = Depends(require_owned_project),
    db: AsyncSession = Depends(get_async_session),
) -> ImportResult:
    content = await file.read(MAX_BYTES + 1)
    if len(content) > MAX_BYTES:
        raise AppError(
            "VALIDATION_ERROR",
            "OpenAPI 文档不符合支持范围",
            422,
            details=[{"path": "file", "message": "文件超过 2MiB"}],
        )
    return await import_openapi(db, project.id, content)


@router.get("/projects/{project_id}/api-definitions", response_model=Page[ApiDefinitionRead])
async def list_all(
    page: PageNumber = 1,
    page_size: PageSize = 20,
    project: Project = Depends(require_owned_project),
    db: AsyncSession = Depends(get_async_session),
) -> Page[ApiDefinitionRead]:
    items, total = await list_api_definitions(db, project.id, page, page_size)
    return Page(
        items=[ApiDefinitionRead.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/projects/{project_id}/api-definitions/{api_id}",
    response_model=ApiDefinitionRead,
)
async def read_one(
    api_id: uuid.UUID,
    project: Project = Depends(require_owned_project),
    db: AsyncSession = Depends(get_async_session),
) -> ApiDefinitionRead:
    definition = await get_api_definition(db, project.id, api_id)
    if definition is None:
        raise AppError("NOT_FOUND", "资源不存在或无权访问", 404)
    return ApiDefinitionRead.model_validate(definition)
