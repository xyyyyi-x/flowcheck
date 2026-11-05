"""运行快照不可变：后续编辑 case/env 不影响已创建的 run。"""

from __future__ import annotations

import uuid

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Run
from app.modules.runs.service import snapshot_from_ciphertext
from tests.factories import create_environment, create_project, make_user
from tests.integration.conftest import build_test_settings
from tests.integration.test_run_creation import create_case, create_run, simple_step


async def test_snapshot_freezes_steps_and_secrets(
    api_client: AsyncClient, db: AsyncSession
) -> None:
    settings = build_test_settings()
    headers = await make_user(api_client)
    project = await create_project(api_client, headers)
    environment = await create_environment(
        api_client,
        headers,
        project["id"],
        {
            "name": "环境",
            "base_url": "http://demo-api:8001",
            "variables": [{"name": "auth_token", "value": "secret-v1", "is_secret": True}],
            "common_headers": [],
        },
    )
    case = await create_case(api_client, headers, project["id"], [simple_step("旧步骤")])
    key = str(uuid.uuid4())
    response = await create_run(
        api_client, headers, project["id"], case["id"], environment["id"], key
    )
    assert response.status_code == 202, response.text
    assert "secret-v1" not in response.text
    assert "snapshot" not in response.text
    run_id = uuid.UUID(response.json()["run_id"])

    stored = await db.scalar(select(Run).where(Run.id == run_id))
    assert stored is not None
    assert "secret-v1" not in stored.snapshot_ciphertext
    snapshot = snapshot_from_ciphertext(stored.snapshot_ciphertext, settings)
    captured_at = snapshot["captured_at"]
    assert snapshot["case_version"] == 1
    assert snapshot["environment_version"] == 1
    assert snapshot["steps"][0]["name"] == "旧步骤"
    assert snapshot["variables"][0]["value"] == "secret-v1"

    edited_case = await api_client.put(
        f"/api/v1/projects/{project['id']}/cases/{case['id']}",
        headers=headers,
        json={
            "name": "新用例",
            "description": "",
            "version": 1,
            "steps": [simple_step("新步骤")],
        },
    )
    assert edited_case.status_code == 200
    edited_env = await api_client.put(
        f"/api/v1/projects/{project['id']}/environments/{environment['id']}",
        headers=headers,
        json={
            "name": "环境",
            "base_url": "http://demo-api:8001",
            "version": 1,
            "variables": [{"name": "auth_token", "value": "secret-v2", "is_secret": True}],
            "common_headers": [],
        },
    )
    assert edited_env.status_code == 200

    again = await create_run(api_client, headers, project["id"], case["id"], environment["id"], key)
    assert again.status_code == 202
    assert again.json()["reused"] is True
    assert again.json()["run_id"] == str(run_id)

    refreshed = await db.scalar(select(Run).where(Run.id == run_id))
    assert refreshed is not None
    snapshot_after = snapshot_from_ciphertext(refreshed.snapshot_ciphertext, settings)
    assert snapshot_after["captured_at"] == captured_at
    assert snapshot_after["case_version"] == 1
    assert snapshot_after["environment_version"] == 1
    assert snapshot_after["steps"][0]["name"] == "旧步骤"
    assert snapshot_after["variables"][0]["value"] == "secret-v1"
