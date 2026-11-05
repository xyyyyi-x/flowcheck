"""OpenAPI 导入 API、幂等跳过与并发唯一冲突处理。"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from httpx import AsyncClient

from tests.factories import create_project, make_user

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "openapi_minimal.json"


async def upload(client: AsyncClient, headers: dict[str, str], project_id: str, content: bytes):
    return await client.post(
        f"/api/v1/projects/{project_id}/imports/openapi",
        headers=headers,
        files={"file": ("openapi.json", content, "application/json")},
    )


async def test_import_creates_then_skips(api_client: AsyncClient) -> None:
    headers = await make_user(api_client)
    project = await create_project(api_client, headers)
    content = FIXTURE.read_bytes()

    first = await upload(api_client, headers, project["id"], content)
    assert first.status_code == 201, first.text
    assert first.json()["created_count"] == 4
    assert first.json()["skipped_count"] == 0

    second = await upload(api_client, headers, project["id"], content)
    assert second.status_code == 201
    assert second.json()["created_count"] == 0
    assert second.json()["skipped_count"] == 4

    listed = await api_client.get(
        f"/api/v1/projects/{project['id']}/api-definitions", headers=headers
    )
    assert listed.status_code == 200
    assert listed.json()["total"] == 4
    item = listed.json()["items"][0]
    detail = await api_client.get(
        f"/api/v1/projects/{project['id']}/api-definitions/{item['id']}", headers=headers
    )
    assert detail.status_code == 200
    assert "request_body_schema" in detail.json()
    assert "openapi" not in detail.text


async def test_invalid_document_leaves_no_rows(api_client: AsyncClient) -> None:
    headers = await make_user(api_client)
    project = await create_project(api_client, headers)
    document = json.loads(FIXTURE.read_text(encoding="utf-8"))
    document["paths"]["/broken"] = {
        "get": {"parameters": [{"in": "query", "schema": {"type": "string"}}]}
    }
    response = await upload(
        api_client, headers, project["id"], json.dumps(document).encode("utf-8")
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"

    listed = await api_client.get(
        f"/api/v1/projects/{project['id']}/api-definitions", headers=headers
    )
    assert listed.json()["total"] == 0


async def test_import_owner_isolation(api_client: AsyncClient) -> None:
    owner = await make_user(api_client, "owner_a")
    stranger = await make_user(api_client, "owner_b")
    project = await create_project(api_client, owner)
    assert (
        await upload(api_client, stranger, project["id"], FIXTURE.read_bytes())
    ).status_code == 404
    assert (
        await api_client.get(f"/api/v1/projects/{project['id']}/api-definitions", headers=stranger)
    ).status_code == 404


async def test_concurrent_import_does_not_duplicate_or_500(api_client: AsyncClient) -> None:
    headers = await make_user(api_client)
    project = await create_project(api_client, headers)
    url = f"/api/v1/projects/{project['id']}/imports/openapi"
    content = FIXTURE.read_bytes()

    async def one_import():
        return await api_client.post(
            url,
            headers=headers,
            files={"file": ("openapi.json", content, "application/json")},
        )

    responses = await asyncio.gather(one_import(), one_import())
    assert all(response.status_code == 201 for response in responses), [
        response.text for response in responses
    ]
    created_total = sum(response.json()["created_count"] for response in responses)
    assert created_total == 4

    listed = await api_client.get(
        f"/api/v1/projects/{project['id']}/api-definitions", headers=headers
    )
    assert listed.json()["total"] == 4


async def test_warnings_are_capped_at_100(api_client: AsyncClient) -> None:
    headers = await make_user(api_client)
    project = await create_project(api_client, headers)
    parameters = [
        {"name": f"c{index}", "in": "cookie", "schema": {"type": "string"}} for index in range(150)
    ]
    document = {
        "openapi": "3.1.0",
        "paths": {"/cookies": {"get": {"parameters": parameters}}},
    }
    response = await upload(api_client, headers, project["id"], json.dumps(document).encode())
    assert response.status_code == 201, response.text
    warnings = response.json()["warnings"]
    assert len(warnings) == 100
    assert "截断" in warnings[-1]["message"]
