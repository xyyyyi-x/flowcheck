"""报告 DTO、counts、分页与 owner 隔离。"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from httpx import AsyncClient

from app.domain.contracts import RunOutcome, SafeStepResult
from app.workers.repository import claim_run
from app.workers.sink import PostgresRunSink
from tests.factories import create_environment, create_project, make_user
from tests.integration.test_run_creation import create_case, create_run, setup, simple_step


def result(status: str, code: str | None = None) -> SafeStepResult:
    return SafeStepResult(
        status=status,
        elapsed_ms=7,
        request_safe={"method": "GET", "origin": "http://demo-api:8001"},
        response_safe={"status_code": 200, "body_omitted": False},
        assertions_safe=[{"type": "status_code", "passed": status == "passed"}],
        extracts_safe=[],
        error_code=code,
    )


async def test_report_counts_and_step_order(api_client: AsyncClient, sync_factory) -> None:
    headers, project, environment, case = await setup(api_client)
    response = await create_run(api_client, headers, project["id"], case["id"], environment["id"])
    run_id = uuid.UUID(response.json()["run_id"])
    claimed = claim_run(run_id, sync_factory, datetime.now(UTC))
    assert claimed is not None
    sink = PostgresRunSink(run_id, claimed.execution_token, sync_factory)
    sink.start_step(1)
    sink.save_step(1, result("passed"))
    sink.start_step(2)
    sink.save_step(2, result("failed", "ASSERTION_FAILED"))
    sink.finish(RunOutcome("failed", "ASSERTION_FAILED", 2))

    report = await api_client.get(f"/api/v1/runs/{run_id}", headers=headers)
    assert report.status_code == 200, report.text
    body = report.json()
    assert body["status"] == "failed"
    assert body["error_code"] == "ASSERTION_FAILED"
    assert [step["position"] for step in body["steps"]] == [1, 2]
    assert body["counts"] == {
        "total": 2,
        "pending": 0,
        "running": 0,
        "passed": 1,
        "failed": 1,
        "error": 0,
        "skipped": 0,
    }
    assert "snapshot" not in report.text


async def test_terminal_report_has_no_pending_or_running(
    api_client: AsyncClient, sync_factory
) -> None:
    headers = await make_user(api_client)
    project = await create_project(api_client, headers)
    environment = await create_environment(api_client, headers, project["id"])
    case = await create_case(
        api_client,
        headers,
        project["id"],
        [simple_step("一"), simple_step("二"), simple_step("三")],
    )
    response = await create_run(api_client, headers, project["id"], case["id"], environment["id"])
    run_id = uuid.UUID(response.json()["run_id"])
    claimed = claim_run(run_id, sync_factory, datetime.now(UTC))
    assert claimed is not None
    sink = PostgresRunSink(run_id, claimed.execution_token, sync_factory)
    sink.start_step(1)
    sink.save_step(1, result("passed"))
    sink.start_step(2)
    sink.save_step(2, result("failed", "ASSERTION_FAILED"))
    sink.finish(RunOutcome("failed", "ASSERTION_FAILED", 2))

    body = (await api_client.get(f"/api/v1/runs/{run_id}", headers=headers)).json()
    statuses = [step["status"] for step in body["steps"]]
    assert statuses == ["passed", "failed", "skipped"]
    assert body["counts"]["pending"] == 0
    assert body["counts"]["running"] == 0
    assert (
        sum(
            body["counts"][key]
            for key in ("pending", "running", "passed", "failed", "error", "skipped")
        )
        == body["counts"]["total"]
    )


async def test_run_list_status_filter_and_pagination(api_client: AsyncClient) -> None:
    headers, project, environment, case = await setup(api_client)
    for _ in range(3):
        assert (
            await create_run(api_client, headers, project["id"], case["id"], environment["id"])
        ).status_code == 202

    listed = await api_client.get(
        f"/api/v1/projects/{project['id']}/runs?page=1&page_size=2", headers=headers
    )
    assert listed.status_code == 200
    assert listed.json()["total"] == 3
    assert len(listed.json()["items"]) == 2
    assert listed.json()["items"][0]["counts"]["total"] == 2

    filtered = await api_client.get(
        f"/api/v1/projects/{project['id']}/runs?status=passed", headers=headers
    )
    assert filtered.status_code == 200
    assert filtered.json()["total"] == 0
    invalid = await api_client.get(
        f"/api/v1/projects/{project['id']}/runs?status=unknown", headers=headers
    )
    assert invalid.status_code == 422


async def test_report_and_events_owner_isolation(api_client: AsyncClient, sync_factory) -> None:
    headers, project, environment, case = await setup(api_client)
    stranger = await make_user(api_client, "owner_b")
    response = await create_run(api_client, headers, project["id"], case["id"], environment["id"])
    run_id = uuid.UUID(response.json()["run_id"])
    claimed = claim_run(run_id, sync_factory, datetime.now(UTC))
    assert claimed is not None
    sink = PostgresRunSink(run_id, claimed.execution_token, sync_factory)
    sink.start_step(1)
    sink.save_step(1, result("passed"))
    sink.start_step(2)
    sink.save_step(2, result("passed"))
    sink.finish(RunOutcome("passed", None, 2))

    assert (await api_client.get(f"/api/v1/runs/{run_id}", headers=stranger)).status_code == 404
    sse = await api_client.get(f"/api/v1/runs/{run_id}/events", headers=stranger)
    assert sse.status_code == 404
    assert sse.headers["content-type"].startswith("application/json")
    assert "无权访问" in sse.text
