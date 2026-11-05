"""Worker 原子抢占：重复投递与过期排队。"""

from __future__ import annotations

import threading
import uuid
from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Run, RunEvent
from app.workers.repository import claim_run
from tests.integration.test_run_creation import create_run, setup


async def test_single_claim_and_duplicate_message(api_client: AsyncClient, sync_factory) -> None:
    headers, project, environment, case = await setup(api_client)
    response = await create_run(api_client, headers, project["id"], case["id"], environment["id"])
    run_id = uuid.UUID(response.json()["run_id"])
    now = datetime.now(UTC)

    first = claim_run(run_id, sync_factory, now)
    second = claim_run(run_id, sync_factory, now)
    assert first is not None
    assert first.execution_token is not None
    assert second is None


async def test_two_sessions_race_only_one_claims(
    api_client: AsyncClient, sync_factory, db: AsyncSession
) -> None:
    headers, project, environment, case = await setup(api_client)
    response = await create_run(api_client, headers, project["id"], case["id"], environment["id"])
    run_id = uuid.UUID(response.json()["run_id"])
    barrier = threading.Barrier(2)
    results = []

    def attempt() -> None:
        barrier.wait()
        results.append(claim_run(run_id, sync_factory, datetime.now(UTC)))

    threads = [threading.Thread(target=attempt) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sum(item is not None for item in results) == 1
    started_events = await db.scalar(
        select(func.count())
        .select_from(RunEvent)
        .where(RunEvent.run_id == run_id, RunEvent.event_type == "run.started")
    )
    assert started_events == 1


async def test_expired_queue_is_not_claimed(
    api_client: AsyncClient, sync_factory, db: AsyncSession
) -> None:
    headers, project, environment, case = await setup(api_client)
    response = await create_run(api_client, headers, project["id"], case["id"], environment["id"])
    run_id = uuid.UUID(response.json()["run_id"])
    await db.execute(
        update(Run)
        .where(Run.id == run_id)
        .values(created_at=datetime.now(UTC) - timedelta(seconds=301))
    )
    await db.commit()
    assert claim_run(run_id, sync_factory, datetime.now(UTC)) is None
