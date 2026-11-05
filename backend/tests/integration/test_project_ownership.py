"""项目 CRUD、owner 隔离与分页边界。"""

from __future__ import annotations

import uuid

from httpx import AsyncClient


async def make_user(client: AsyncClient, username: str) -> tuple[dict[str, str], str]:
    register = await client.post(
        "/api/v1/auth/register", json={"username": username, "password": "password-123"}
    )
    assert register.status_code == 201
    login = await client.post(
        "/api/v1/auth/login", json={"username": username, "password": "password-123"}
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    return headers, register.json()["id"]


async def create_project(client: AsyncClient, headers: dict[str, str], name: str = "项目"):
    return await client.post(
        "/api/v1/projects",
        headers=headers,
        json={"name": name, "description": "演示项目"},
    )


async def test_create_read_and_update_project(api_client: AsyncClient) -> None:
    owner_headers, owner_id = await make_user(api_client, "owner_a")
    created = await create_project(api_client, owner_headers)
    assert created.status_code == 201
    project = created.json()
    assert project["name"] == "项目"
    assert project["owner_id"] == owner_id
    assert uuid.UUID(project["id"])

    fetched = await api_client.get(f"/api/v1/projects/{project['id']}", headers=owner_headers)
    assert fetched.status_code == 200
    assert fetched.json()["id"] == project["id"]

    updated = await api_client.put(
        f"/api/v1/projects/{project['id']}",
        headers=owner_headers,
        json={"name": "新名称", "description": ""},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "新名称"


async def test_other_user_cannot_read_or_update_project(api_client: AsyncClient) -> None:
    owner_headers, _ = await make_user(api_client, "owner_a")
    stranger_headers, _ = await make_user(api_client, "owner_b")
    project_id = (await create_project(api_client, owner_headers)).json()["id"]

    assert (
        await api_client.get(f"/api/v1/projects/{project_id}", headers=stranger_headers)
    ).status_code == 404
    assert (
        await api_client.put(
            f"/api/v1/projects/{project_id}",
            headers=stranger_headers,
            json={"name": "劫持", "description": ""},
        )
    ).status_code == 404

    stranger_list = await api_client.get("/api/v1/projects", headers=stranger_headers)
    assert stranger_list.json() == {"items": [], "total": 0, "page": 1, "page_size": 20}
    owner_list = await api_client.get("/api/v1/projects", headers=owner_headers)
    assert owner_list.json()["total"] == 1


async def test_owner_id_in_body_is_rejected(api_client: AsyncClient) -> None:
    owner_headers, _ = await make_user(api_client, "owner_a")
    response = await api_client.post(
        "/api/v1/projects",
        headers=owner_headers,
        json={"name": "项目", "description": "", "owner_id": str(uuid.uuid4())},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_pagination_bounds_and_defaults(api_client: AsyncClient) -> None:
    owner_headers, _ = await make_user(api_client, "owner_a")
    for index in range(3):
        assert (await create_project(api_client, owner_headers, f"项目{index}")).status_code == 201

    default = await api_client.get("/api/v1/projects", headers=owner_headers)
    assert default.json()["page"] == 1
    assert default.json()["page_size"] == 20
    assert len(default.json()["items"]) == 3

    page = await api_client.get("/api/v1/projects?page=2&page_size=2", headers=owner_headers)
    assert page.status_code == 200
    assert page.json()["total"] == 3
    assert len(page.json()["items"]) == 1

    assert (
        await api_client.get("/api/v1/projects?page=0", headers=owner_headers)
    ).status_code == 422
    assert (
        await api_client.get("/api/v1/projects?page_size=101", headers=owner_headers)
    ).status_code == 422


async def test_authentication_required(api_client: AsyncClient) -> None:
    assert (await api_client.get("/api/v1/projects")).status_code == 401
    assert (await api_client.post("/api/v1/projects", json={"name": "x"})).status_code == 401
