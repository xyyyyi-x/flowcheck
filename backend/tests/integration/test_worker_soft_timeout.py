"""SoftTimeLimitExceeded 与未处理异常的兜底终结。"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from celery.exceptions import SoftTimeLimitExceeded
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Run, StepResult
from app.workers import execution
from app.workers.repository import claim_run
from tests.integration.conftest import build_test_settings
from tests.integration.test_run_creation import create_run, setup


class NoopTransport:
    def close(self) -> None:
        return None


async def test_soft_timeout_marks_running_step_error(
    api_client: AsyncClient, sync_factory, db: AsyncSession, monkeypatch
) -> None:
    headers, project, environment, case = await setup(api_client)
    response = await create_run(api_client, headers, project["id"], case["id"], environment["id"])
    run_id = uuid.UUID(response.json()["run_id"])
    claimed = claim_run(run_id, sync_factory, datetime.now(UTC))
    assert claimed is not None

    def fake_execute(snapshot, transport, sink, monotonic):
        sink.start_step(1)
        raise SoftTimeLimitExceeded

    monkeypatch.setattr(execution, "execute_snapshot", fake_execute)
    outcome = execution.execute_claimed(
        claimed, build_test_settings(), sync_factory, NoopTransport()
    )
    assert outcome is None

    run = await db.scalar(select(Run).where(Run.id == run_id))
    assert run is not None
    assert run.status == "interrupted"
    assert run.error_code == "RUN_TIMEOUT"
    steps = (
        await db.scalars(
            select(StepResult).where(StepResult.run_id == run_id).order_by(StepResult.position)
        )
    ).all()
    assert [(item.status, item.error_code) for item in steps] == [
        ("error", "RUN_TIMEOUT"),
        ("skipped", None),
    ]


async def test_unexpected_exception_finishes_error(
    api_client: AsyncClient, sync_factory, db: AsyncSession, monkeypatch
) -> None:
    headers, project, environment, case = await setup(api_client)
    response = await create_run(api_client, headers, project["id"], case["id"], environment["id"])
    run_id = uuid.UUID(response.json()["run_id"])
    claimed = claim_run(run_id, sync_factory, datetime.now(UTC))
    assert claimed is not None

    def explode(snapshot, transport, sink, monotonic):
        raise RuntimeError("boom")

    monkeypatch.setattr(execution, "execute_snapshot", explode)
    execution.execute_claimed(claimed, build_test_settings(), sync_factory, NoopTransport())

    run = await db.scalar(select(Run).where(Run.id == run_id))
    assert run is not None
    assert run.status == "error"
    assert run.error_code == "INTERNAL_ERROR"
