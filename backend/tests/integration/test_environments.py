"""环境加密、secret 编辑协议、origin 白名单与 owner 隔离。"""

from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import decrypt_json
from app.db.models import Environment
from tests.factories import create_environment, create_project, make_user
from tests.integration.conftest import build_test_settings

SECRET_VALUE = "only-for-local-demo-secret"


async def test_create_environment_hides_secret_in_api_and_database(
    api_client: AsyncClient, db: AsyncSession
) -> None:
    headers = await make_user(api_client, "owner_a")
    project = await create_project(api_client, headers)
    payload = {
        "name": "Compose Demo",
        "base_url": "http://demo-api:8001",
        "variables": [
            {"name": "demo_username", "value": "demo", "is_secret": False},
            {"name": "demo_password", "value": SECRET_VALUE, "is_secret": True},
        ],
        "common_headers": [
            {"name": "Authorization", "value": "Bearer top-secret", "is_secret": False}
        ],
    }
    response = await api_client.post(
        f"/api/v1/projects/{project['id']}/environments",
        headers=headers,
        json=payload,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    variables = {item["name"]: item for item in body["variables"]}
    assert variables["demo_username"]["value"] == "demo"
    assert variables["demo_password"]["value"] is None
    assert variables["demo_password"]["has_value"] is True
    header = body["common_headers"][0]
    assert header["is_secret"] is True
    assert header["value"] is None
    assert SECRET_VALUE not in response.text
    assert "Bearer top-secret" not in response.text
    assert "config_ciphertext" not in body

    stored = await db.scalar(select(Environment).where(Environment.id == body["id"]))
    assert stored is not None
    assert SECRET_VALUE not in stored.config_ciphertext
    decrypted = decrypt_json(stored.config_ciphertext, build_test_settings().encryption_key)
    assert decrypted["variables"][1]["value"] == SECRET_VALUE


async def test_create_secret_null_is_422_and_duplicate_name_is_409(
    api_client: AsyncClient,
) -> None:
    headers = await make_user(api_client, "owner_a")
    project = await create_project(api_client, headers)
    invalid = await api_client.post(
        f"/api/v1/projects/{project['id']}/environments",
        headers=headers,
        json={
            "name": "环境",
            "base_url": "http://demo-api:8001",
            "variables": [{"name": "token", "value": None, "is_secret": True}],
            "common_headers": [],
        },
    )
    assert invalid.status_code == 422

    await create_environment(api_client, headers, project["id"])
    duplicate = await api_client.post(
        f"/api/v1/projects/{project['id']}/environments",
        headers=headers,
        json={
            "name": "环境",
            "base_url": "http://demo-api:8001",
            "variables": [],
            "common_headers": [],
        },
    )
    assert duplicate.status_code == 409


async def test_update_protocol_keep_replace_remove_and_version(
    api_client: AsyncClient,
) -> None:
    headers = await make_user(api_client, "owner_a")
    project = await create_project(api_client, headers)
    created = await create_environment(
        api_client,
        headers,
        project["id"],
        {
            "name": "环境",
            "base_url": "http://demo-api:8001",
            "variables": [
                {"name": "a", "value": "1", "is_secret": False},
                {"name": "b", "value": "s1", "is_secret": True},
                {"name": "c", "value": "old", "is_secret": False},
            ],
            "common_headers": [],
        },
    )
    assert created["version"] == 1

    kept = await api_client.put(
        f"/api/v1/projects/{project['id']}/environments/{created['id']}",
        headers=headers,
        json={
            "name": "环境",
            "base_url": "http://demo-api:8001",
            "version": 1,
            "variables": [
                {"name": "a", "value": "2", "is_secret": False},
                {"name": "b", "value": None, "is_secret": True},
                {"name": "d", "value": "new", "is_secret": False},
            ],
            "common_headers": [],
        },
    )
    assert kept.status_code == 200, kept.text
    assert kept.json()["version"] == 2
    variables = {item["name"]: item for item in kept.json()["variables"]}
    assert set(variables) == {"a", "b", "d"}
    assert variables["a"]["value"] == "2"
    assert variables["b"]["value"] is None
    assert variables["b"]["has_value"] is True

    conflict = await api_client.put(
        f"/api/v1/projects/{project['id']}/environments/{created['id']}",
        headers=headers,
        json={
            "name": "环境",
            "base_url": "http://demo-api:8001",
            "version": 1,
            "variables": [],
            "common_headers": [],
        },
    )
    assert conflict.status_code == 409

    downgrade = await api_client.put(
        f"/api/v1/projects/{project['id']}/environments/{created['id']}",
        headers=headers,
        json={
            "name": "环境",
            "base_url": "http://demo-api:8001",
            "version": 2,
            "variables": [{"name": "b", "value": None, "is_secret": False}],
            "common_headers": [],
        },
    )
    assert downgrade.status_code == 422

    replaced = await api_client.put(
        f"/api/v1/projects/{project['id']}/environments/{created['id']}",
        headers=headers,
        json={
            "name": "环境",
            "base_url": "http://demo-api:8001",
            "version": 2,
            "variables": [{"name": "b", "value": "s2", "is_secret": True}],
            "common_headers": [],
        },
    )
    assert replaced.status_code == 200
    assert replaced.json()["version"] == 3


async def test_origin_allowlist(api_client: AsyncClient) -> None:
    headers = await make_user(api_client, "owner_a")
    project = await create_project(api_client, headers)
    origins = await api_client.get("/api/v1/target-origins", headers=headers)
    assert origins.json() == {"items": ["http://demo-api:8001"]}

    for bad_url in (
        "https://evil.example.com",
        "http://demo-api:8001/path",
        "http://user:pw@demo-api:8001",
    ):
        response = await api_client.post(
            f"/api/v1/projects/{project['id']}/environments",
            headers=headers,
            json={
                "name": "环境",
                "base_url": bad_url,
                "variables": [],
                "common_headers": [],
            },
        )
        assert response.status_code == 422, bad_url


async def test_environment_owner_and_cross_project_isolation(
    api_client: AsyncClient,
) -> None:
    owner_a = await make_user(api_client, "owner_a")
    owner_b = await make_user(api_client, "owner_b")
    project_a = await create_project(api_client, owner_a, "A 项目")
    project_b = await create_project(api_client, owner_b, "B 项目")
    env_a = await create_environment(api_client, owner_a, project_a["id"])

    assert (
        await api_client.get(
            f"/api/v1/projects/{project_a['id']}/environments/{env_a['id']}",
            headers=owner_b,
        )
    ).status_code == 404
    assert (
        await api_client.get(
            f"/api/v1/projects/{project_b['id']}/environments/{env_a['id']}",
            headers=owner_a,
        )
    ).status_code == 404
    assert (
        await api_client.post(
            f"/api/v1/projects/{project_a['id']}/environments",
            headers=owner_b,
            json={
                "name": "越权",
                "base_url": "http://demo-api:8001",
                "variables": [],
                "common_headers": [],
            },
        )
    ).status_code == 404


async def test_structural_validation(api_client: AsyncClient) -> None:
    headers = await make_user(api_client, "owner_a")
    project = await create_project(api_client, headers)
    base = {
        "name": "环境",
        "base_url": "http://demo-api:8001",
        "variables": [],
        "common_headers": [],
    }
    body = dict(base, variables=[{"name": "run_id", "value": "x", "is_secret": False}])
    assert (
        await api_client.post(
            f"/api/v1/projects/{project['id']}/environments", headers=headers, json=body
        )
    ).status_code == 422

    body = dict(base, variables=[{"name": "x", "value": {"a": 1}, "is_secret": False}])
    assert (
        await api_client.post(
            f"/api/v1/projects/{project['id']}/environments", headers=headers, json=body
        )
    ).status_code == 422

    body = dict(base, common_headers=[{"name": "Host", "value": "evil", "is_secret": False}])
    assert (
        await api_client.post(
            f"/api/v1/projects/{project['id']}/environments", headers=headers, json=body
        )
    ).status_code == 422

    body = dict(
        base, variables=[{"name": f"v{i}", "value": 1, "is_secret": False} for i in range(51)]
    )
    assert (
        await api_client.post(
            f"/api/v1/projects/{project['id']}/environments", headers=headers, json=body
        )
    ).status_code == 422
