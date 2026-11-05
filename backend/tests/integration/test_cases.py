"""用例 CRUD、版本冲突与 DSL 校验集成测试。"""

from __future__ import annotations

import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ApiDefinition
from tests.factories import create_project, make_user


def step(position: int, extractor: str | None = None) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "name": f"步骤{position}",
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
            [{"name": extractor, "selector": f"$.value{position}", "is_secret": False}]
            if extractor
            else []
        ),
        "omit_response_body": False,
    }


def demo_steps() -> list[dict]:
    return [
        {
            "id": str(uuid.uuid4()),
            "name": "登录",
            "source_api_id": None,
            "request": {
                "method": "POST",
                "path": "/auth/login",
                "path_params": {},
                "query": {},
                "headers": {},
                "json_body": {
                    "username": "{{demo_username}}",
                    "password": "{{demo_password}}",
                },
                "timeout_s": 10,
            },
            "assertions": [{"type": "status_code", "expected": 200}],
            "extractors": [{"name": "auth_token", "selector": "$.access_token", "is_secret": True}],
            "omit_response_body": True,
        },
        {
            "id": str(uuid.uuid4()),
            "name": "创建文章",
            "source_api_id": None,
            "request": {
                "method": "POST",
                "path": "/articles",
                "path_params": {},
                "query": {},
                "headers": {"Authorization": "Bearer {{auth_token}}"},
                "json_body": {"title": "smoke-{{run_id}}", "content": "hello"},
                "timeout_s": 10,
            },
            "assertions": [{"type": "status_code", "expected": 201}],
            "extractors": [{"name": "article_id", "selector": "$.id", "is_secret": False}],
            "omit_response_body": False,
        },
        {
            "id": str(uuid.uuid4()),
            "name": "查询文章",
            "source_api_id": None,
            "request": {
                "method": "GET",
                "path": "/articles/{id}",
                "path_params": {"id": "{{article_id}}"},
                "query": {},
                "headers": {"Authorization": "Bearer {{auth_token}}"},
                "json_body": None,
                "timeout_s": 10,
            },
            "assertions": [
                {"type": "status_code", "expected": 200},
                {
                    "type": "json_equals",
                    "selector": "$.title",
                    "expected": "smoke-{{run_id}}",
                },
            ],
            "extractors": [],
            "omit_response_body": False,
        },
        {
            "id": str(uuid.uuid4()),
            "name": "删除文章",
            "source_api_id": None,
            "request": {
                "method": "DELETE",
                "path": "/articles/{id}",
                "path_params": {"id": "{{article_id}}"},
                "query": {},
                "headers": {"Authorization": "Bearer {{auth_token}}"},
                "json_body": None,
                "timeout_s": 10,
            },
            "assertions": [{"type": "status_code", "expected": 204}],
            "extractors": [],
            "omit_response_body": True,
        },
        {
            "id": str(uuid.uuid4()),
            "name": "再查应 404",
            "source_api_id": None,
            "request": {
                "method": "GET",
                "path": "/articles/{id}",
                "path_params": {"id": "{{article_id}}"},
                "query": {},
                "headers": {"Authorization": "Bearer {{auth_token}}"},
                "json_body": None,
                "timeout_s": 10,
            },
            "assertions": [{"type": "status_code", "expected": 404}],
            "extractors": [],
            "omit_response_body": True,
        },
    ]


async def test_create_demo_case_preserves_order(api_client: AsyncClient) -> None:
    headers = await make_user(api_client)
    project = await create_project(api_client, headers)
    steps = demo_steps()
    response = await api_client.post(
        f"/api/v1/projects/{project['id']}/cases",
        headers=headers,
        json={"name": "文章五步", "description": "演示", "steps": steps},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["version"] == 1
    assert [item["id"] for item in body["steps"]] == [item["id"] for item in steps]
    assert [item["name"] for item in body["steps"]] == [
        "登录",
        "创建文章",
        "查询文章",
        "删除文章",
        "再查应 404",
    ]

    fetched = await api_client.get(
        f"/api/v1/projects/{project['id']}/cases/{body['id']}", headers=headers
    )
    assert fetched.status_code == 200
    assert len(fetched.json()["steps"]) == 5

    listed = await api_client.get(f"/api/v1/projects/{project['id']}/cases", headers=headers)
    assert listed.json()["total"] == 1


async def test_step_count_bounds(api_client: AsyncClient) -> None:
    headers = await make_user(api_client)
    project = await create_project(api_client, headers)
    twenty = [step(index, f"v{index}") for index in range(20)]
    ok = await api_client.post(
        f"/api/v1/projects/{project['id']}/cases",
        headers=headers,
        json={"name": "20步", "description": "", "steps": twenty},
    )
    assert ok.status_code == 201
    twenty_one = [step(index, f"w{index}") for index in range(21)]
    too_many = await api_client.post(
        f"/api/v1/projects/{project['id']}/cases",
        headers=headers,
        json={"name": "21步", "description": "", "steps": twenty_one},
    )
    assert too_many.status_code == 422


async def test_update_uses_version_and_full_replace(api_client: AsyncClient) -> None:
    headers = await make_user(api_client)
    project = await create_project(api_client, headers)
    created = (
        await api_client.post(
            f"/api/v1/projects/{project['id']}/cases",
            headers=headers,
            json={"name": "用例", "description": "", "steps": [step(1, "value1")]},
        )
    ).json()

    updated = await api_client.put(
        f"/api/v1/projects/{project['id']}/cases/{created['id']}",
        headers=headers,
        json={
            "name": "用例改",
            "description": "新描述",
            "version": 1,
            "steps": [step(2, "value2"), step(3, "value3")],
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["version"] == 2
    assert [item["name"] for item in updated.json()["steps"]] == ["步骤2", "步骤3"]

    stale = await api_client.put(
        f"/api/v1/projects/{project['id']}/cases/{created['id']}",
        headers=headers,
        json={"name": "旧版本", "description": "", "version": 1, "steps": [step(4)]},
    )
    assert stale.status_code == 409


async def test_unknown_field_and_duplicate_extractor_rejected(
    api_client: AsyncClient,
) -> None:
    headers = await make_user(api_client)
    project = await create_project(api_client, headers)
    extra = step(1)
    extra["unexpected"] = True
    response = await api_client.post(
        f"/api/v1/projects/{project['id']}/cases",
        headers=headers,
        json={"name": "用例", "description": "", "steps": [extra]},
    )
    assert response.status_code == 422

    duplicate = await api_client.post(
        f"/api/v1/projects/{project['id']}/cases",
        headers=headers,
        json={
            "name": "用例",
            "description": "",
            "steps": [step(1, "same"), step(2, "same")],
        },
    )
    assert duplicate.status_code == 422


async def test_source_api_must_belong_to_same_project(
    api_client: AsyncClient, db: AsyncSession
) -> None:
    owner_headers = await make_user(api_client, "owner_a")
    stranger_headers = await make_user(api_client, "owner_b")
    project = await create_project(api_client, owner_headers)
    other_project = await create_project(api_client, stranger_headers, "B 项目")

    api = ApiDefinition(
        project_id=uuid.UUID(project["id"]),
        method="GET",
        path="/articles",
        summary="列表",
        parameters=[],
    )
    other_api = ApiDefinition(
        project_id=uuid.UUID(other_project["id"]),
        method="GET",
        path="/other",
        summary="其他",
        parameters=[],
    )
    db.add_all([api, other_api])
    await db.commit()

    linked = step(1)
    linked["source_api_id"] = str(api.id)
    ok = await api_client.post(
        f"/api/v1/projects/{project['id']}/cases",
        headers=owner_headers,
        json={"name": "用例", "description": "", "steps": [linked]},
    )
    assert ok.status_code == 201, ok.text

    cross = step(2)
    cross["source_api_id"] = str(other_api.id)
    bad = await api_client.post(
        f"/api/v1/projects/{project['id']}/cases",
        headers=owner_headers,
        json={"name": "用例2", "description": "", "steps": [cross]},
    )
    assert bad.status_code == 404


async def test_case_owner_isolation(api_client: AsyncClient) -> None:
    owner_headers = await make_user(api_client, "owner_a")
    stranger_headers = await make_user(api_client, "owner_b")
    project = await create_project(api_client, owner_headers)
    case = (
        await api_client.post(
            f"/api/v1/projects/{project['id']}/cases",
            headers=owner_headers,
            json={"name": "用例", "description": "", "steps": [step(1)]},
        )
    ).json()

    assert (
        await api_client.get(
            f"/api/v1/projects/{project['id']}/cases/{case['id']}",
            headers=stranger_headers,
        )
    ).status_code == 404
    assert (
        await api_client.get(f"/api/v1/projects/{project['id']}/cases", headers=stranger_headers)
    ).status_code == 404
