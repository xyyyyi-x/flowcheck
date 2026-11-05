"""超时回收：DISPATCH_TIMEOUT 与 WORKER_INTERRUPTED。"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Run, RunEvent, RunOutbox, StepResult
from app.domain.contracts import RunOutcome, SafeStepResult
from app.workers.reconcile import reconcile_runs
from app.workers.repository import claim_run
from app.workers.sink import PostgresRunSink
from tests.integration.test_run_creation import create_run, setup


async def test_queued_timeout_becomes_dispatch_timeout(
    api_client: AsyncClient, sync_factory, db: AsyncSession
) -> None:
    headers, project, environment, case = await setup(api_client)
    response = await create_run(api_client, headers, project["id"], case["id"], environment["id"])
    run_id = uuid.UUID(response.json()["run_id"])
    now = datetime.now(UTC)
    await db.execute(
        update(Run).where(Run.id == run_id).values(created_at=now - timedelta(seconds=301))
    )
    await db.commit()

    counts = reconcile_runs(now, sync_factory)
    assert counts.dispatch_timeouts == 1
    run = await db.scalar(select(Run).where(Run.id == run_id))
    assert run is not None
    assert run.status == "error"
    assert run.error_code == "DISPATCH_TIMEOUT"
    steps = (await db.scalars(select(StepResult).where(StepResult.run_id == run_id))).all()
    assert all(item.status == "skipped" for item in steps)
    outbox = await db.scalar(select(RunOutbox).where(RunOutbox.run_id == run_id))
    assert outbox is not None and outbox.status == "abandoned"
    finished_events = await db.scalar(
        select(func.count())
        .select_from(RunEvent)
        .where(RunEvent.run_id == run_id, RunEvent.event_type == "run.finished")
    )
    assert finished_events == 1

    again = reconcile_runs(now, sync_factory)
    assert again.dispatch_timeouts == 0


async def test_running_timeout_becomes_interrupted(
    api_client: AsyncClient, sync_factory, db: AsyncSession
) -> None:
    headers, project, environment, case = await setup(api_client)
    response = await create_run(api_client, headers, project["id"], case["id"], environment["id"])
    run_id = uuid.UUID(response.json()["run_id"])
    now = datetime.now(UTC)
    claimed = claim_run(run_id, sync_factory, now - timedelta(seconds=400))
    assert claimed is not None
    sink = PostgresRunSink(run_id, claimed.execution_token, sync_factory)
    sink.start_step(1)

    counts = reconcile_runs(now, sync_factory)
    assert counts.worker_interruptions == 1
    run = await db.scalar(select(Run).where(Run.id == run_id))
    assert run is not None
    assert run.status == "interrupted"
    assert run.error_code == "WORKER_INTERRUPTED"
    steps = (
        await db.scalars(
            select(StepResult).where(StepResult.run_id == run_id).order_by(StepResult.position)
        )
    ).all()
    assert [(item.status, item.error_code) for item in steps] == [
        ("error", "WORKER_INTERRUPTED"),
        ("skipped", None),
    ]


async def test_terminal_run_is_not_overwritten(
    api_client: AsyncClient, sync_factory, db: AsyncSession
) -> None:
    headers, project, environment, case = await setup(api_client)
    response = await create_run(api_client, headers, project["id"], case["id"], environment["id"])
    run_id = uuid.UUID(response.json()["run_id"])
    now = datetime.now(UTC)
    claimed = claim_run(run_id, sync_factory, now - timedelta(seconds=400))
    assert claimed is not None
    sink = PostgresRunSink(run_id, claimed.execution_token, sync_factory)
    sink.start_step(1)
    sink.save_step(1, SafeStepResult(status="passed", elapsed_ms=1))
    sink.start_step(2)
    sink.save_step(2, SafeStepResult(status="passed", elapsed_ms=1))
    sink.finish(RunOutcome("passed", None, 2))

    counts = reconcile_runs(now, sync_factory)
    assert counts.worker_interruptions == 0
    run = await db.scalar(select(Run).where(Run.id == run_id))
    assert run is not None and run.status == "passed"
