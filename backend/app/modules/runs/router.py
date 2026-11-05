"""运行提交、列表、报告与 SSE 路由。"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.dependencies import get_settings
from app.core.errors import AppError
from app.core.schemas import Page
from app.db.async_session import get_async_session
from app.db.models import Project, Run, StepResult, User
from app.modules.auth.deps import get_current_user
from app.modules.projects.deps import require_owned_project
from app.modules.runs.repository import (
    get_owned_run_with_steps,
    list_runs,
    step_status_counts,
)
from app.modules.runs.schemas import (
    RunCreate,
    RunCreated,
    RunReport,
    RunStatusFilter,
    RunSummary,
    StepCounts,
    StepResultRead,
)
from app.modules.runs.service import create_run
from app.modules.runs.sse import SseContext, sse_context, stream_run_events

router = APIRouter(tags=["runs"])

PageNumber = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=100)]
MAX_EVENT_ID = 9223372036854775807


def _summary(run: Run, counts: dict[str, int]) -> RunSummary:
    return RunSummary(
        id=run.id,
        project_id=run.project_id,
        case_id=run.case_id,
        environment_id=run.environment_id,
        case_name=run.case_name,
        case_version=run.case_version,
        environment_name=run.environment_name,
        environment_version=run.environment_version,
        status=run.status,
        created_at=run.created_at,
        started_at=run.started_at,
        finished_at=run.finished_at,
        error_code=run.error_code,
        counts=StepCounts(**counts),
    )


def _report(run: Run, steps: list[StepResult]) -> RunReport:
    counts = {
        "total": len(steps),
        "pending": 0,
        "running": 0,
        "passed": 0,
        "failed": 0,
        "error": 0,
        "skipped": 0,
    }
    for step in steps:
        if step.status in counts:
            counts[step.status] += 1
    summary = _summary(run, counts)
    return RunReport(
        **summary.model_dump(),
        steps=[StepResultRead.model_validate(step) for step in steps],
    )


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


@router.get("/projects/{project_id}/runs", response_model=Page[RunSummary])
async def list_all(
    page: PageNumber = 1,
    page_size: PageSize = 20,
    status_filter: Annotated[RunStatusFilter | None, Query(alias="status")] = None,
    project: Project = Depends(require_owned_project),
    db: AsyncSession = Depends(get_async_session),
) -> Page[RunSummary]:
    runs, total = await list_runs(db, project.id, status_filter, page, page_size)
    counts = await step_status_counts(db, [run.id for run in runs])
    return Page(
        items=[_summary(run, counts[run.id]) for run in runs],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/runs/{run_id}", response_model=RunReport)
async def read_report(
    run_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
) -> RunReport:
    found = await get_owned_run_with_steps(db, user.id, run_id)
    if found is None:
        raise AppError("NOT_FOUND", "资源不存在或无权访问", 404)
    run, steps = found
    return _report(run, steps)


@router.get("/runs/{run_id}/events")
async def events(
    request: Request,
    after: Annotated[int, Query(ge=0, le=MAX_EVENT_ID)] = 0,
    context: SseContext = Depends(sse_context),
) -> StreamingResponse:
    return StreamingResponse(
        stream_run_events(
            context.run_id,
            after,
            context.expires_at,
            request.app.state.session_factory,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
