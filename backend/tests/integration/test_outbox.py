"""Outbox 发布、退避与过期放弃。"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Run, RunOutbox
from app.workers.dispatcher import dispatch_due
from app.workers.reconcile import reconcile_runs
from app.workers.repository import claim_run
from tests.integration.test_run_creation import create_run, setup


async def test_dispatch_success_marks_sent(
    api_client: AsyncClient, sync_factory, db: AsyncSession
) -> None:
    headers, project, environment, case = await setup(api_client)
    response = await create_run(api_client, headers, project["id"], case["id"], environment["id"])
    run_id = response.json()["run_id"]
    published: list[str] = []
    counts = dispatch_due(datetime.now(UTC), published.append, sync_factory)
    assert published == [run_id]
    assert counts.published == 1
    outbox = await db.scalar(select(RunOutbox).where(RunOutbox.run_id == uuid.UUID(run_id)))
    assert outbox is not None and outbox.status == "sent" and outbox.sent_at is not None


async def test_failure_keeps_pending_and_backs_off(
    api_client: AsyncClient, sync_factory, db: AsyncSession
) -> None:
    headers, project, environment, case = await setup(api_client)
    response = await create_run(api_client, headers, project["id"], case["id"], environment["id"])
    run_id = uuid.UUID(response.json()["run_id"])
    now = datetime.now(UTC)

    def failing(_: str) -> None:
        raise RuntimeError("broker down")

    counts = dispatch_due(now, failing, sync_factory)
    assert counts.failed == 1
    outbox = await db.scalar(select(RunOutbox).where(RunOutbox.run_id == run_id))
    assert outbox is not None
    assert outbox.status == "pending"
    assert outbox.attempt_count == 1
    assert outbox.last_error_code == "BROKER_UNAVAILABLE"
    assert outbox.next_attempt_at > now
    run = await db.scalar(select(Run).where(Run.id == run_id))
    assert run is not None and run.status == "queued"

    published: list[str] = []
    later = now + timedelta(seconds=5)
    counts = dispatch_due(later, published.append, sync_factory)
    assert counts.published == 1
    assert published == [str(run_id)]


async def test_backoff_caps_at_thirty_seconds(
    api_client: AsyncClient, sync_factory, db: AsyncSession
) -> None:
    headers, project, environment, case = await setup(api_client)
    response = await create_run(api_client, headers, project["id"], case["id"], environment["id"])
    run_id = uuid.UUID(response.json()["run_id"])
    await db.execute(update(RunOutbox).where(RunOutbox.run_id == run_id).values(attempt_count=10))
    await db.commit()
    now = datetime.now(UTC)

    def failing(_: str) -> None:
        raise RuntimeError("down")

    dispatch_due(now, failing, sync_factory)
    outbox = await db.scalar(select(RunOutbox).where(RunOutbox.run_id == run_id))
    assert outbox is not None
    assert outbox.attempt_count == 11
    assert outbox.next_attempt_at >= now + timedelta(seconds=29)


async def test_expired_queued_is_abandoned_not_published(
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

    published: list[str] = []
    counts = dispatch_due(now, published.append, sync_factory)
    assert published == []
    assert counts.abandoned == 1
    outbox = await db.scalar(select(RunOutbox).where(RunOutbox.run_id == run_id))
    assert outbox is not None and outbox.status == "abandoned"

    counts = reconcile_runs(now, sync_factory)
    assert counts.dispatch_timeouts == 1
    run = await db.scalar(select(Run).where(Run.id == run_id))
    assert run is not None and run.error_code == "DISPATCH_TIMEOUT"


async def test_already_running_run_outbox_is_abandoned(
    api_client: AsyncClient, sync_factory, db: AsyncSession
) -> None:
    headers, project, environment, case = await setup(api_client)
    response = await create_run(api_client, headers, project["id"], case["id"], environment["id"])
    run_id = uuid.UUID(response.json()["run_id"])
    assert claim_run(run_id, sync_factory, datetime.now(UTC)) is not None

    published: list[str] = []
    counts = dispatch_due(datetime.now(UTC), published.append, sync_factory)
    assert published == []
    assert counts.abandoned == 1
