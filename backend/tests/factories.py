"""集成测试共用构造器。"""

from __future__ import annotations

from typing import Any

from httpx import AsyncClient


async def make_user(client: AsyncClient, username: str = "owner_a") -> dict[str, str]:
    registered = await client.post(
        "/api/v1/auth/register", json={"username": username, "password": "password-123"}
    )
    assert registered.status_code == 201, registered.text
    logged_in = await client.post(
        "/api/v1/auth/login", json={"username": username, "password": "password-123"}
    )
    assert logged_in.status_code == 200, logged_in.text
    return {"Authorization": f"Bearer {logged_in.json()['access_token']}"}


async def create_project(
    client: AsyncClient, headers: dict[str, str], name: str = "项目"
) -> dict[str, Any]:
    response = await client.post(
        "/api/v1/projects", headers=headers, json={"name": name, "description": "演示"}
    )
    assert response.status_code == 201, response.text
    return response.json()


async def create_environment(
    client: AsyncClient,
    headers: dict[str, str],
    project_id: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    body = payload or {
        "name": "环境",
        "base_url": "http://demo-api:8001",
        "variables": [],
        "common_headers": [],
    }
    response = await client.post(
        f"/api/v1/projects/{project_id}/environments", headers=headers, json=body
    )
    assert response.status_code == 201, response.text
    return response.json()
