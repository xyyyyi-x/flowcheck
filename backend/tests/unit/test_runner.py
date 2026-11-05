"""线性执行器：五步链、失败即停、脱敏与预算。"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

import pytest

from app.domain.contracts import (
    RenderedRequest,
    ResponseData,
    RunSnapshot,
    SafeStepResult,
    StepDefinition,
)
from app.domain.ports import NetworkFailure, RunNoLongerActive
from app.domain.runner import execute_snapshot

ORIGIN = "http://demo-api:8001"


def step(
    name: str,
    method: str = "GET",
    path: str = "/articles",
    headers: dict[str, str] | None = None,
    body=None,
    expected: int = 200,
    extractors: list[dict] | None = None,
    omit: bool = False,
) -> StepDefinition:
    return StepDefinition.model_validate(
        {
            "id": str(uuid.uuid4()),
            "name": name,
            "source_api_id": None,
            "request": {
                "method": method,
                "path": path,
                "path_params": {},
                "query": {},
                "headers": headers or {},
                "json_body": body,
                "timeout_s": 10,
            },
            "assertions": [{"type": "status_code", "expected": expected}],
            "extractors": extractors or [],
            "omit_response_body": omit,
        }
    )


def snapshot(steps: list[StepDefinition]) -> RunSnapshot:
    return RunSnapshot(
        schema_version=1,
        run_id=uuid.uuid4(),
        case_id=uuid.uuid4(),
        case_name="用例",
        case_version=1,
        environment_id=uuid.uuid4(),
        environment_name="环境",
        environment_version=1,
        target_origin=ORIGIN,
        variables=[
            {"name": "demo_username", "value": "demo", "is_secret": False},
            {"name": "demo_password", "value": "pw-secret", "is_secret": True},
        ],
        common_headers=[],
        steps=steps,
        limits={
            "max_steps": 20,
            "request_max_bytes": 65536,
            "response_max_bytes": 1048576,
            "report_preview_bytes": 8192,
            "run_budget_s": 300,
        },
        captured_at=datetime.now(UTC),
    )


class FakeTransport:
    def __init__(self, responses) -> None:
        self.responses = responses
        self.calls: list[RenderedRequest] = []

    def send(self, request: RenderedRequest, timeout_s: int, remaining_s: float):
        self.calls.append(request)
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class FakeSink:
    def __init__(self, fail_on_save: bool = False) -> None:
        self.started: list[int] = []
        self.saved: list[tuple[int, SafeStepResult]] = []
        self.outcome = None
        self.fail_on_save = fail_on_save

    def start_step(self, position: int) -> None:
        self.started.append(position)

    def save_step(self, position: int, result: SafeStepResult) -> None:
        if self.fail_on_save:
            raise RunNoLongerActive
        self.saved.append((position, result))

    def finish(self, outcome) -> None:
        self.outcome = outcome


def response(status: int = 200, body=None, is_json: bool = True, elapsed: float = 5.0):
    return ResponseData(status, {"content-type": "application/json"}, body, is_json, elapsed)


def test_five_step_chain_publishes_extracted_values() -> None:
    steps = [
        step(
            "登录",
            method="POST",
            path="/auth/login",
            body={"username": "{{demo_username}}", "password": "{{demo_password}}"},
            extractors=[{"name": "auth_token", "selector": "$.access_token", "is_secret": True}],
        ),
        step(
            "查询",
            headers={"Authorization": "Bearer {{auth_token}}"},
            extractors=[{"name": "article_id", "selector": "$.id", "is_secret": False}],
        ),
        step("删除", method="DELETE", expected=204),
        step("再查", expected=404),
        step("完成"),
    ]
    transport = FakeTransport(
        [
            response(200, {"access_token": "secret-token"}),
            response(200, {"id": "article-1"}),
            response(204, None, is_json=False),
            response(404, {"error": "not found"}),
            response(200, {"ok": True}),
        ]
    )
    sink = FakeSink()
    outcome = execute_snapshot(snapshot(steps), transport, sink, lambda: 0.0)

    assert outcome.status == "passed"
    assert outcome.last_completed_position == 5
    assert sink.started == [1, 2, 3, 4, 5]
    assert len(sink.saved) == 5
    assert sink.outcome.status == "passed"
    assert transport.calls[1].headers["Authorization"] == "Bearer secret-token"


def test_assertion_failure_stops_and_skips_following_steps() -> None:
    steps = [
        step("登录", method="POST", path="/auth/login"),
        step("创建", expected=201),
        step("后续"),
    ]
    transport = FakeTransport([response(200, {"ok": True}), response(200, {"ok": True})])
    sink = FakeSink()
    outcome = execute_snapshot(snapshot(steps), transport, sink, lambda: 0.0)

    assert outcome.status == "failed"
    assert outcome.error_code == "ASSERTION_FAILED"
    assert outcome.last_completed_position == 2
    assert sink.started == [1, 2]
    assert len(sink.saved) == 2
    assert sink.saved[1][1].status == "failed"


def test_missing_variable_fails_before_transport() -> None:
    steps = [step("坏步骤", method="POST", body={"title": "{{missing}}"})]
    transport = FakeTransport([])
    sink = FakeSink()
    outcome = execute_snapshot(snapshot(steps), transport, sink, lambda: 0.0)

    assert outcome.status == "error"
    assert outcome.error_code == "VARIABLE_UNDEFINED"
    assert transport.calls == []
    assert sink.saved[0][1].response_safe is None


def test_network_error_is_step_error_without_fake_response() -> None:
    steps = [step("网络")]
    transport = FakeTransport([NetworkFailure("down")])
    sink = FakeSink()
    outcome = execute_snapshot(snapshot(steps), transport, sink, lambda: 0.0)

    assert outcome.status == "error"
    assert outcome.error_code == "NETWORK_ERROR"
    result = sink.saved[0][1]
    assert result.response_safe is None
    assert result.assertions_safe == []


def test_secret_extraction_is_redacted_even_when_assertion_fails() -> None:
    steps = [
        step(
            "登录",
            method="POST",
            path="/auth/login",
            expected=500,
            extractors=[{"name": "auth_token", "selector": "$.access_token", "is_secret": True}],
        )
    ]
    transport = FakeTransport(
        [response(200, {"access_token": "secret-token", "echo": "secret-token"})]
    )
    sink = FakeSink()
    outcome = execute_snapshot(snapshot(steps), transport, sink, lambda: 0.0)

    assert outcome.status == "failed"
    serialized = json.dumps(
        {
            "response": sink.saved[0][1].response_safe,
            "assertions": sink.saved[0][1].assertions_safe,
            "extracts": sink.saved[0][1].extracts_safe,
        },
        ensure_ascii=False,
    )
    assert "secret-token" not in serialized
    assert sink.saved[0][1].extracts_safe[0]["value_safe"] == "[REDACTED]"


def test_run_budget_interrupts_between_steps() -> None:
    class Clock:
        value = 0.0

        def __call__(self) -> float:
            return self.value

    clock = Clock()

    class AdvancingTransport(FakeTransport):
        def send(self, request, timeout_s, remaining_s):
            result = super().send(request, timeout_s, remaining_s)
            clock.value = 301.0
            return result

    steps = [step("第一步"), step("第二步")]
    transport = AdvancingTransport([response(200, {"ok": True}), response(200)])
    sink = FakeSink()
    outcome = execute_snapshot(snapshot(steps), transport, sink, clock)

    assert outcome.status == "interrupted"
    assert outcome.error_code == "RUN_TIMEOUT"
    assert outcome.last_completed_position == 1
    assert sink.started == [1]


def test_inactive_sink_aborts_execution() -> None:
    steps = [step("一"), step("二")]
    transport = FakeTransport([response(200, {"ok": True})])
    sink = FakeSink(fail_on_save=True)
    with pytest.raises(RunNoLongerActive):
        execute_snapshot(snapshot(steps), transport, sink, lambda: 0.0)
    assert len(transport.calls) == 1
