"""运行相关的只读查询。"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Project, Run, RunEvent, StepResult


async def get_owned_run(db: AsyncSession, owner_id: uuid.UUID, run_id: uuid.UUID) -> Run | None:
    return await db.scalar(
        select(Run)
        .join(Project, Project.id == Run.project_id)
        .where(Run.id == run_id, Project.owner_id == owner_id)
    )


async def get_run_by_idempotency(
    db: AsyncSession, project_id: uuid.UUID, idempotency_key: uuid.UUID
) -> Run | None:
    return await db.scalar(
        select(Run).where(Run.project_id == project_id, Run.idempotency_key == idempotency_key)
    )


async def list_runs(
    db: AsyncSession,
    project_id: uuid.UUID,
    status: str | None,
    page: int,
    page_size: int,
) -> tuple[list[Run], int]:
    conditions = [Run.project_id == project_id]
    if status is not None:
        conditions.append(Run.status == status)
    total = await db.scalar(select(func.count()).select_from(Run).where(*conditions))
    items = await db.scalars(
        select(Run)
        .where(*conditions)
        .order_by(Run.created_at.desc(), Run.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(items), int(total or 0)


async def get_steps_for_runs(
    db: AsyncSession, run_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[StepResult]]:
    if not run_ids:
        return {}
    rows = await db.scalars(
        select(StepResult)
        .where(StepResult.run_id.in_(run_ids))
        .order_by(StepResult.run_id, StepResult.position)
    )
    result: dict[uuid.UUID, list[StepResult]] = {}
    for row in rows:
        result.setdefault(row.run_id, []).append(row)
    return result


async def step_status_counts(
    db: AsyncSession, run_ids: list[uuid.UUID]
) -> dict[uuid.UUID, dict[str, int]]:
    counts: dict[uuid.UUID, dict[str, int]] = {
        run_id: {
            "total": 0,
            "pending": 0,
            "running": 0,
            "passed": 0,
            "failed": 0,
            "error": 0,
            "skipped": 0,
        }
        for run_id in run_ids
    }
    if not run_ids:
        return counts
    rows = await db.execute(
        select(StepResult.run_id, StepResult.status, func.count())
        .where(StepResult.run_id.in_(run_ids))
        .group_by(StepResult.run_id, StepResult.status)
    )
    for run_id, status, amount in rows.all():
        counts[run_id][status] = int(amount)
    for run_id in run_ids:
        counts[run_id]["total"] = sum(
            value for key, value in counts[run_id].items() if key != "total"
        )
    return counts


async def get_owned_run_with_steps(
    db: AsyncSession, owner_id: uuid.UUID, run_id: uuid.UUID
) -> tuple[Run, list[StepResult]] | None:
    run = await get_owned_run(db, owner_id, run_id)
    if run is None:
        return None
    steps = list(
        await db.scalars(
            select(StepResult).where(StepResult.run_id == run_id).order_by(StepResult.position)
        )
    )
    return run, steps


async def get_events(
    db: AsyncSession, run_id: uuid.UUID, after: int, limit: int = 100
) -> list[RunEvent]:
    return list(
        await db.scalars(
            select(RunEvent)
            .where(RunEvent.run_id == run_id, RunEvent.id > after)
            .order_by(RunEvent.id)
            .limit(limit)
        )
    )


async def get_run_status(db: AsyncSession, run_id: uuid.UUID) -> str | None:
    return await db.scalar(select(Run.status).where(Run.id == run_id))


def counts_from_steps(steps: list[StepResult]) -> dict[str, Any]:
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
    return counts
