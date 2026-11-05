"""项目统计 SQL、通过率分母与 30 秒缓存。"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Run
from app.main import create_app
from app.modules.summary.service import SummaryCache, cache_key
from tests.factories import create_environment, create_project, make_user
from tests.integration.conftest import build_test_settings
from tests.integration.test_run_creation import create_case, setup


async def add_run(
    db: AsyncSession,
    project_id: str,
    case_id: str,
    environment_id: str,
    status: str,
) -> None:
    db.add(
        Run(
            project_id=uuid.UUID(project_id),
            case_id=uuid.UUID(case_id),
            environment_id=uuid.UUID(environment_id),
            case_name="用例",
            case_version=1,
            environment_name="环境",
            environment_version=1,
            status=status,
            snapshot_ciphertext="cipher",
            idempotency_key=uuid.uuid4(),
            request_fingerprint="fp",
            finished_at=datetime.now(UTC)
            if status in {"passed", "failed", "error", "interrupted"}
            else None,
        )
    )


async def clear_cache(settings, project_id: str) -> None:
    cache = SummaryCache(settings.app_redis_cache_url)
    try:
        await cache.delete(cache_key(uuid.UUID(project_id)))
    finally:
        await cache.close()


async def test_empty_project_summary(api_client: AsyncClient) -> None:
    headers = await make_user(api_client)
    project = await create_project(api_client, headers)
    response = await api_client.get(f"/api/v1/projects/{project['id']}/summary", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total_runs"] == 0
    assert body["pass_rate"] is None
    assert body["cache_hit"] is False


async def test_mixed_status_pass_rate_excludes_errors(
    api_client: AsyncClient, db: AsyncSession
) -> None:
    settings = build_test_settings()
    headers, project, environment, case = await setup(api_client)
    await clear_cache(settings, project["id"])
    for status in ("passed", "passed", "failed", "error", "interrupted"):
        await add_run(db, project["id"], case["id"], environment["id"], status)
    await add_run(db, project["id"], case["id"], environment["id"], "queued")
    await add_run(db, project["id"], case["id"], environment["id"], "running")
    await db.commit()

    body = (
        await api_client.get(f"/api/v1/projects/{project['id']}/summary", headers=headers)
    ).json()
    assert body["total_runs"] == 7
    assert body["passed_runs"] == 2
    assert body["failed_runs"] == 1
    assert body["error_runs"] == 1
    assert body["interrupted_runs"] == 1
    assert body["active_runs"] == 2
    assert abs(body["pass_rate"] - 2 / 3) < 1e-9


async def test_cache_hit_preserves_computed_at(api_client: AsyncClient, db: AsyncSession) -> None:
    settings = build_test_settings()
    headers, project, environment, case = await setup(api_client)
    await clear_cache(settings, project["id"])
    await add_run(db, project["id"], case["id"], environment["id"], "passed")
    await db.commit()
    url = f"/api/v1/projects/{project['id']}/summary"

    first = (await api_client.get(url, headers=headers)).json()
    second = (await api_client.get(url, headers=headers)).json()
    assert first["cache_hit"] is False
    assert second["cache_hit"] is True
    assert second["computed_at"] == first["computed_at"]
    assert second["total_runs"] == 1

    await clear_cache(settings, project["id"])
    third = (await api_client.get(url, headers=headers)).json()
    assert third["cache_hit"] is False


async def test_other_user_gets_404_before_cache(api_client: AsyncClient) -> None:
    owner = await make_user(api_client, "owner_a")
    stranger = await make_user(api_client, "owner_b")
    project = await create_project(api_client, owner)
    response = await api_client.get(f"/api/v1/projects/{project['id']}/summary", headers=stranger)
    assert response.status_code == 404


async def test_redis_failure_falls_back_to_database() -> None:
    settings = build_test_settings()
    settings.app_redis_cache_url = "redis://127.0.0.1:1/1"
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            headers = await make_user(client, "cache_fallback")
            project = await create_project(client, headers)
            environment = await create_environment(client, headers, project["id"])
            case = await create_case(client, headers, project["id"])
            assert environment and case
            response = await client.get(
                f"/api/v1/projects/{project['id']}/summary", headers=headers
            )
    assert response.status_code == 200
    assert response.json()["cache_hit"] is False
    assert response.json()["total_runs"] == 0
