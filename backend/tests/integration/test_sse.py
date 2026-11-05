"""SSE 事件回放、after 续读、心跳与过期关闭。"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta

from httpx import ASGITransport, AsyncClient

from app.domain.contracts import RunOutcome, SafeStepResult
from app.main import create_app
from app.modules.runs.sse import format_frame, stream_run_events
from app.workers.repository import claim_run
from app.workers.sink import PostgresRunSink
from tests.factories import create_environment, create_project, make_user
from tests.integration.conftest import build_test_settings
from tests.integration.test_run_creation import create_case, create_run, setup, simple_step


def parse_frames(text: str) -> list[dict]:
    frames = []
    for block in text.split("\n\n"):
        block = block.strip()
        if not block or block.startswith(":"):
            continue
        parsed: dict = {}
        for line in block.splitlines():
            if line.startswith("id: "):
                parsed["id"] = int(line[4:])
            elif line.startswith("event: "):
                parsed["event"] = line[7:]
            elif line.startswith("data: "):
                parsed["data"] = json.loads(line[6:])
        frames.append(parsed)
    return frames


async def completed_run(api_client: AsyncClient, sync_factory):
    headers, project, environment, case = await setup(api_client)
    response = await create_run(api_client, headers, project["id"], case["id"], environment["id"])
    run_id = uuid.UUID(response.json()["run_id"])
    claimed = claim_run(run_id, sync_factory, datetime.now(UTC))
    assert claimed is not None
    sink = PostgresRunSink(run_id, claimed.execution_token, sync_factory)
    for position in (1, 2):
        sink.start_step(position)
        sink.save_step(position, SafeStepResult(status="passed", elapsed_ms=2, assertions_safe=[]))
    sink.finish(RunOutcome("passed", None, 2))
    return headers, run_id


async def test_events_replay_in_order_and_close(api_client: AsyncClient, sync_factory) -> None:
    headers, run_id = await completed_run(api_client, sync_factory)
    response = await api_client.get(f"/api/v1/runs/{run_id}/events?after=0", headers=headers)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"].startswith("no-cache")
    frames = parse_frames(response.text)
    assert [frame["event"] for frame in frames] == [
        "run.queued",
        "run.started",
        "step.started",
        "step.finished",
        "step.started",
        "step.finished",
        "run.finished",
    ]
    ids = [frame["id"] for frame in frames]
    assert ids == sorted(ids)
    assert frames[-1]["data"]["status"] == "passed"

    last_id = ids[-1]
    empty = await api_client.get(f"/api/v1/runs/{run_id}/events?after={last_id}", headers=headers)
    assert empty.status_code == 200
    assert empty.text == ""


async def test_events_require_auth_and_ownership(api_client: AsyncClient, sync_factory) -> None:
    headers, run_id = await completed_run(api_client, sync_factory)
    assert (await api_client.get(f"/api/v1/runs/{run_id}/events")).status_code == 401


async def test_invalid_after_is_422(api_client: AsyncClient, sync_factory) -> None:
    headers, run_id = await completed_run(api_client, sync_factory)
    response = await api_client.get(f"/api/v1/runs/{run_id}/events?after=-1", headers=headers)
    assert response.status_code == 422


async def test_heartbeat_and_token_expiry_with_injected_clock() -> None:
    app = create_app(build_test_settings())
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            headers = await make_user(client, "sse_owner")
            project = await create_project(client, headers)
            environment = await create_environment(client, headers, project["id"])
            case = await create_case(client, headers, project["id"], [simple_step("一")])
            response = await create_run(
                client, headers, project["id"], case["id"], environment["id"]
            )
            run_id = uuid.UUID(response.json()["run_id"])

        class FakeClock:
            def __init__(self) -> None:
                self.t = 0.0

            def monotonic(self) -> float:
                return self.t

            async def sleep(self, _: float) -> None:
                self.t += 1.0

        start = datetime.now(UTC)

        def wall_clock_at(clock: FakeClock):
            return lambda: start + timedelta(seconds=clock.t)

        clock = FakeClock()
        frames = [
            frame
            async for frame in stream_run_events(
                run_id,
                10**9,
                start + timedelta(seconds=20),
                app.state.session_factory,
                monotonic=clock.monotonic,
                sleep=clock.sleep,
                wall_clock=wall_clock_at(clock),
            )
        ]
        assert frames == [": heartbeat\n\n"]

        expired_clock = FakeClock()
        frames = [
            frame
            async for frame in stream_run_events(
                run_id,
                10**9,
                start + timedelta(seconds=3),
                app.state.session_factory,
                monotonic=expired_clock.monotonic,
                sleep=expired_clock.sleep,
                wall_clock=wall_clock_at(expired_clock),
            )
        ]
        assert frames == []


def test_chinese_payload_is_not_escaped() -> None:
    frame = format_frame(1, "step.finished", {"name": "中文", "status": "passed"})
    assert "中文" in frame
    assert "\\u4e2d" not in frame
