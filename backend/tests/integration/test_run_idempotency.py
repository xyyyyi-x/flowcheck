"""幂等键：并发、请求指纹与编辑后的原 run 复用。"""

from __future__ import annotations

import asyncio
import uuid

from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Run, RunOutbox
from app.main import create_app
from tests.factories import create_environment, create_project, make_user
from tests.integration.conftest import build_test_settings
from tests.integration.test_run_creation import create_case, create_run, setup, simple_step


async def test_same_key_same_request_reuses_run(api_client: AsyncClient, db: AsyncSession) -> None:
    headers, project, environment, case = await setup(api_client)
    key = str(uuid.uuid4())
    first = await create_run(api_client, headers, project["id"], case["id"], environment["id"], key)
    second = await create_run(
        api_client, headers, project["id"], case["id"], environment["id"], key
    )
    assert first.status_code == 202 and second.status_code == 202
    assert first.json()["run_id"] == second.json()["run_id"]
    assert second.json()["reused"] is True
    assert second.json()["status"] == "queued"

    run_count = await db.scalar(select(func.count()).select_from(Run))
    outbox_count = await db.scalar(select(func.count()).select_from(RunOutbox))
    assert run_count == 1
    assert outbox_count == 1


async def test_same_key_different_request_conflicts(api_client: AsyncClient) -> None:
    headers, project, environment, case = await setup(api_client)
    other_case = await create_case(api_client, headers, project["id"])
    key = str(uuid.uuid4())
    first = await create_run(api_client, headers, project["id"], case["id"], environment["id"], key)
    assert first.status_code == 202
    conflict = await create_run(
        api_client, headers, project["id"], other_case["id"], environment["id"], key
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "CONFLICT"


async def test_concurrent_same_key_creates_single_run(
    api_client: AsyncClient, db: AsyncSession
) -> None:
    headers, project, environment, case = await setup(api_client)
    key = str(uuid.uuid4())

    async def submit():
        return await create_run(
            api_client, headers, project["id"], case["id"], environment["id"], key
        )

    responses = await asyncio.gather(submit(), submit())
    assert all(item.status_code == 202 for item in responses), [item.text for item in responses]
    run_ids = {item.json()["run_id"] for item in responses}
    assert len(run_ids) == 1
    assert sorted(item.json()["reused"] for item in responses) == [False, True]

    run_count = await db.scalar(select(func.count()).select_from(Run))
    outbox_count = await db.scalar(select(func.count()).select_from(RunOutbox))
    assert run_count == 1
    assert outbox_count == 1


async def test_editing_case_does_not_change_same_key_result(api_client: AsyncClient) -> None:
    headers, project, environment, case = await setup(api_client)
    key = str(uuid.uuid4())
    first = await create_run(api_client, headers, project["id"], case["id"], environment["id"], key)
    edited = await api_client.put(
        f"/api/v1/projects/{project['id']}/cases/{case['id']}",
        headers=headers,
        json={
            "name": "改过",
            "description": "",
            "version": case["version"],
            "steps": [simple_step("新步骤")],
        },
    )
    assert edited.status_code == 200
    again = await create_run(api_client, headers, project["id"], case["id"], environment["id"], key)
    assert again.status_code == 202
    assert again.json()["reused"] is True
    assert again.json()["run_id"] == first.json()["run_id"]


async def test_submission_does_not_require_redis() -> None:
    settings = build_test_settings()
    settings.app_redis_broker_url = "redis://127.0.0.1:1/0"
    settings.app_redis_cache_url = "redis://127.0.0.1:1/1"
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            headers = await make_user(client)
            project = await create_project(client, headers)
            environment = await create_environment(client, headers, project["id"])
            case = await create_case(client, headers, project["id"])
            response = await client.post(
                f"/api/v1/projects/{project['id']}/runs",
                headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
                json={"case_id": case["id"], "environment_id": environment["id"]},
            )
    assert response.status_code == 202
    assert response.json()["status"] == "queued"
