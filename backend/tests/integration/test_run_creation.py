"""运行提交的事务、校验与幂等前置。"""

from __future__ import annotations

import uuid

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Run, RunEvent, RunOutbox, StepResult
from tests.factories import create_environment, create_project, make_user


def simple_step(name: str = "步骤", extractor: str | None = None) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "name": name,
        "source_api_id": None,
        "request": {
            "method": "GET",
            "path": "/articles",
            "path_params": {},
            "query": {},
            "headers": {},
            "json_body": None,
            "timeout_s": 10,
        },
        "assertions": [{"type": "status_code", "expected": 200}],
        "extractors": (
            [{"name": extractor, "selector": "$.id", "is_secret": False}] if extractor else []
        ),
        "omit_response_body": False,
    }


async def create_case(client: AsyncClient, headers, project_id: str, steps=None) -> dict:
    response = await client.post(
        f"/api/v1/projects/{project_id}/cases",
        headers=headers,
        json={"name": "用例", "description": "", "steps": steps or [simple_step()]},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def create_run(
    client: AsyncClient,
    headers,
    project_id: str,
    case_id: str,
    environment_id: str,
    key: str | None = None,
):
    key = key or str(uuid.uuid4())
    return await client.post(
        f"/api/v1/projects/{project_id}/runs",
        headers={**headers, "Idempotency-Key": key},
        json={"case_id": case_id, "environment_id": environment_id},
    )


async def setup(client: AsyncClient):
    headers = await make_user(client)
    project = await create_project(client, headers)
    environment = await create_environment(client, headers, project["id"])
    case = await create_case(client, headers, project["id"], [simple_step("一"), simple_step("二")])
    return headers, project, environment, case


async def test_create_run_writes_run_steps_event_and_outbox(
    api_client: AsyncClient, db: AsyncSession
) -> None:
    headers, project, environment, case = await setup(api_client)
    response = await create_run(api_client, headers, project["id"], case["id"], environment["id"])
    assert response.status_code == 202, response.text
    body = response.json()
    assert body["status"] == "queued"
    assert body["reused"] is False
    assert uuid.UUID(body["run_id"])
    assert "snapshot" not in response.text

    run = await db.scalar(select(Run).where(Run.id == uuid.UUID(body["run_id"])))
    assert run is not None and run.status == "queued"
    steps = (await db.scalars(select(StepResult).where(StepResult.run_id == run.id))).all()
    assert [(item.position, item.status) for item in steps] == [(1, "pending"), (2, "pending")]
    event_count = await db.scalar(
        select(func.count()).select_from(RunEvent).where(RunEvent.run_id == run.id)
    )
    assert event_count == 1
    outbox = await db.scalar(select(RunOutbox).where(RunOutbox.run_id == run.id))
    assert outbox is not None and outbox.status == "pending"


async def test_idempotency_header_is_required(api_client: AsyncClient) -> None:
    headers, project, environment, case = await setup(api_client)
    missing = await api_client.post(
        f"/api/v1/projects/{project['id']}/runs",
        headers=headers,
        json={"case_id": case["id"], "environment_id": environment["id"]},
    )
    assert missing.status_code == 422
    malformed = await api_client.post(
        f"/api/v1/projects/{project['id']}/runs",
        headers={**headers, "Idempotency-Key": "not-a-uuid"},
        json={"case_id": case["id"], "environment_id": environment["id"]},
    )
    assert malformed.status_code == 422


async def test_cross_project_resources_are_404(api_client: AsyncClient) -> None:
    headers, project, environment, case = await setup(api_client)
    other_headers = await make_user(api_client, "owner_b")
    other_project = await create_project(api_client, other_headers, "B")
    other_env = await create_environment(api_client, other_headers, other_project["id"])
    other_case = await create_case(api_client, other_headers, other_project["id"])

    assert (
        await create_run(api_client, headers, project["id"], other_case["id"], environment["id"])
    ).status_code == 404
    assert (
        await create_run(api_client, headers, project["id"], case["id"], other_env["id"])
    ).status_code == 404


async def test_extractor_name_conflict_with_environment_variable_is_422(
    api_client: AsyncClient,
) -> None:
    headers = await make_user(api_client)
    project = await create_project(api_client, headers)
    environment = await create_environment(
        api_client,
        headers,
        project["id"],
        {
            "name": "环境",
            "base_url": "http://demo-api:8001",
            "variables": [{"name": "article_id", "value": "x", "is_secret": False}],
            "common_headers": [],
        },
    )
    case = await create_case(api_client, headers, project["id"], [simple_step("一", "article_id")])
    response = await create_run(api_client, headers, project["id"], case["id"], environment["id"])
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_unknown_body_fields_are_rejected(api_client: AsyncClient) -> None:
    headers, project, environment, case = await setup(api_client)
    response = await api_client.post(
        f"/api/v1/projects/{project['id']}/runs",
        headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
        json={
            "case_id": case["id"],
            "environment_id": environment["id"],
            "status": "passed",
        },
    )
    assert response.status_code == 422
