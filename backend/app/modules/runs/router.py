"""运行提交路由（报告与 SSE 在 T11 加入）。"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.dependencies import get_settings
from app.db.async_session import get_async_session
from app.db.models import Project
from app.modules.projects.deps import require_owned_project
from app.modules.runs.schemas import RunCreate, RunCreated
from app.modules.runs.service import create_run

router = APIRouter(tags=["runs"])


@router.post(
    "/projects/{project_id}/runs",
    response_model=RunCreated,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create(
    payload: RunCreate,
    idempotency_key: Annotated[uuid.UUID, Header(alias="Idempotency-Key")],
    project: Project = Depends(require_owned_project),
    db: AsyncSession = Depends(get_async_session),
    settings: Settings = Depends(get_settings),
) -> RunCreated:
    return await create_run(
        db,
        project,
        payload.case_id,
        payload.environment_id,
        idempotency_key,
        settings,
    )
