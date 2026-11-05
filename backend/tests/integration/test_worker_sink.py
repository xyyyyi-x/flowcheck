"""fenced sink：状态、事件、中断终结与迟到写入拒绝。"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Run, RunEvent, StepResult
from app.domain.contracts import RunOutcome, SafeStepResult
from app.domain.ports import RunNoLongerActive
from app.workers.repository import claim_run
from app.workers.sink import PostgresRunSink
from tests.integration.test_run_creation import create_case, create_run, setup, simple_step


def passed_result() -> SafeStepResult:
    return SafeStepResult(
        status="passed",
        elapsed_ms=5,
        request_safe={"method": "GET"},
        response_safe={"status_code": 200},
        assertions_safe=[{"type": "status_code", "passed": True}],
        extracts_safe=[],
        error_code=None,
    )


async def test_sink_writes_steps_events_and_terminal_status(
    api_client: AsyncClient, sync_factory, db: AsyncSession
) -> None:
    headers, project, environment, case = await setup(api_client)
    response = await create_run(api_client, headers, project["id"], case["id"], environment["id"])
    run_id = uuid.UUID(response.json()["run_id"])
    claimed = claim_run(run_id, sync_factory, datetime.now(UTC))
    assert claimed is not None
    sink = PostgresRunSink(run_id, claimed.execution_token, sync_factory)

    sink.start_step(1)
    sink.save_step(1, passed_result())
    sink.start_step(2)
    sink.save_step(2, passed_result())
    sink.finish(RunOutcome("passed", None, 2))

    run = await db.scalar(select(Run).where(Run.id == run_id))
    assert run is not None and run.status == "passed" and run.finished_at is not None
    steps = (
        await db.scalars(
            select(StepResult).where(StepResult.run_id == run_id).order_by(StepResult.position)
        )
    ).all()
    assert [item.status for item in steps] == ["passed", "passed"]
    event_types = (
        await db.scalars(
            select(RunEvent.event_type).where(RunEvent.run_id == run_id).order_by(RunEvent.id)
        )
    ).all()
    assert event_types == [
        "run.queued",
        "run.started",
        "step.started",
        "step.finished",
        "step.started",
        "step.finished",
        "run.finished",
    ]


async def test_late_writes_are_rejected(
    api_client: AsyncClient, sync_factory, db: AsyncSession
) -> None:
    headers, project, environment, case = await setup(api_client)
    response = await create_run(api_client, headers, project["id"], case["id"], environment["id"])
    run_id = uuid.UUID(response.json()["run_id"])
    claimed = claim_run(run_id, sync_factory, datetime.now(UTC))
    assert claimed is not None
    sink = PostgresRunSink(run_id, claimed.execution_token, sync_factory)
    sink.start_step(1)
    sink.save_step(1, passed_result())
    sink.start_step(2)
    sink.save_step(2, passed_result())
    sink.finish(RunOutcome("passed", None, 2))

    with pytest.raises(RunNoLongerActive):
        sink.save_step(1, passed_result())
    with pytest.raises(RunNoLongerActive):
        sink.finish(RunOutcome("failed", "ASSERTION_FAILED", 2))

    run = await db.scalar(select(Run).where(Run.id == run_id))
    assert run is not None and run.status == "passed"
    step_one = await db.scalar(
        select(StepResult).where(StepResult.run_id == run_id, StepResult.position == 1)
    )
    assert step_one is not None and step_one.status == "passed"


async def test_finish_marks_running_error_and_pending_skipped(
    api_client: AsyncClient, sync_factory, db: AsyncSession
) -> None:
    headers, project, environment, case = await setup(api_client)
    steps = [simple_step("一"), simple_step("二"), simple_step("三")]
    case = await create_case(api_client, headers, project["id"], steps)
    response = await create_run(api_client, headers, project["id"], case["id"], environment["id"])
    run_id = uuid.UUID(response.json()["run_id"])
    claimed = claim_run(run_id, sync_factory, datetime.now(UTC))
    assert claimed is not None
    sink = PostgresRunSink(run_id, claimed.execution_token, sync_factory)
    sink.start_step(1)
    sink.finish(RunOutcome("interrupted", "RUN_TIMEOUT", 0))

    run = await db.scalar(select(Run).where(Run.id == run_id))
    assert run is not None
    assert run.status == "interrupted"
    assert run.error_code == "RUN_TIMEOUT"
    steps_rows = (
        await db.scalars(
            select(StepResult).where(StepResult.run_id == run_id).order_by(StepResult.position)
        )
    ).all()
    assert [(item.status, item.error_code) for item in steps_rows] == [
        ("error", "RUN_TIMEOUT"),
        ("skipped", None),
        ("skipped", None),
    ]


async def test_unknown_step_does_not_emit_event(
    api_client: AsyncClient, sync_factory, db: AsyncSession
) -> None:
    headers, project, environment, case = await setup(api_client)
    response = await create_run(api_client, headers, project["id"], case["id"], environment["id"])
    run_id = uuid.UUID(response.json()["run_id"])
    claimed = claim_run(run_id, sync_factory, datetime.now(UTC))
    assert claimed is not None
    sink = PostgresRunSink(run_id, claimed.execution_token, sync_factory)
    before = await db.scalar(
        select(func.count()).select_from(RunEvent).where(RunEvent.run_id == run_id)
    )
    with pytest.raises(RunNoLongerActive):
        sink.start_step(99)
    after = await db.scalar(
        select(func.count()).select_from(RunEvent).where(RunEvent.run_id == run_id)
    )
    assert before == after
