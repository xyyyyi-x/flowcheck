"""HTTPX 传输的有界性、origin 限制与不重试。"""

from __future__ import annotations

import httpx
import pytest

from app.domain.contracts import RenderedRequest
from app.domain.ports import (
    NetworkFailure,
    RequestTimeout,
    ResponseTooLarge,
    RunBudgetExceeded,
    TargetNotAllowed,
)
from app.infra.http_transport import HttpxTransport

ORIGIN = "http://demo-api:8001"


def request(
    method: str = "GET",
    url: str = ORIGIN + "/articles",
    headers: dict[str, str] | None = None,
    body=None,
) -> RenderedRequest:
    return RenderedRequest(
        method=method,
        url=url,
        headers=headers or {},
        json_body=body,
        path_template="/articles",
        query_keys=[],
        timeout_s=5,
    )


def transport(handler, origins=(ORIGIN,)) -> HttpxTransport:
    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        trust_env=False,
        follow_redirects=False,
    )
    return HttpxTransport(origins, client)


def test_success_parses_json_and_keeps_status() -> None:
    def handler(incoming: httpx.Request) -> httpx.Response:
        assert incoming.method == "GET"
        return httpx.Response(200, headers={"content-type": "application/json"}, json={"ok": True})

    response = transport(handler).send(request(), 5, 10)
    assert response.status_code == 200
    assert response.is_json is True
    assert response.body_json == {"ok": True}
    assert response.elapsed_ms >= 0


def test_http_error_status_is_not_raised() -> None:
    response = transport(lambda incoming: httpx.Response(404, json={"error": "x"})).send(
        request(), 5, 10
    )
    assert response.status_code == 404


def test_redirects_are_not_followed() -> None:
    calls = []

    def handler(incoming: httpx.Request) -> httpx.Response:
        calls.append(str(incoming.url))
        if incoming.url.path == "/articles":
            return httpx.Response(302, headers={"location": "/other"})
        return httpx.Response(200, json={"followed": True})

    response = transport(handler).send(request(), 5, 10)
    assert response.status_code == 302
    assert len(calls) == 1


def test_disallowed_origin_is_rejected_without_request() -> None:
    with pytest.raises(TargetNotAllowed):
        transport(lambda incoming: httpx.Response(200)).send(
            request(url="http://evil.example.com/articles"), 5, 10
        )


def test_restricted_host_header_is_rejected() -> None:
    with pytest.raises(TargetNotAllowed):
        transport(lambda incoming: httpx.Response(200)).send(
            request(headers={"Host": "evil.example.com"}), 5, 10
        )


def test_timeout_does_not_retry() -> None:
    calls = []

    def handler(incoming: httpx.Request) -> httpx.Response:
        calls.append(incoming)
        raise httpx.ReadTimeout("slow", request=incoming)

    with pytest.raises(RequestTimeout):
        transport(handler).send(request(method="POST", body={"a": 1}), 1, 10)
    assert len(calls) == 1


def test_network_error_is_mapped() -> None:
    def handler(incoming: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down", request=incoming)

    with pytest.raises(NetworkFailure):
        transport(handler).send(request(), 5, 10)


def test_response_over_one_mebibyte_is_rejected() -> None:
    def handler(incoming: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "text/plain"},
            content=b"x" * (1024 * 1024 + 1),
        )

    with pytest.raises(ResponseTooLarge):
        transport(handler).send(request(), 5, 10)


def test_non_json_and_empty_body() -> None:
    non_json = transport(
        lambda incoming: httpx.Response(200, headers={"content-type": "text/plain"}, text="hello")
    ).send(request(), 5, 10)
    assert non_json.is_json is False
    assert non_json.body_json is None

    empty = transport(lambda incoming: httpx.Response(204)).send(request(), 5, 10)
    assert empty.status_code == 204
    assert empty.is_json is False


def test_exhausted_budget_prevents_request() -> None:
    calls = []

    def handler(incoming: httpx.Request) -> httpx.Response:
        calls.append(incoming)
        return httpx.Response(200)

    with pytest.raises(RunBudgetExceeded):
        transport(handler).send(request(), 5, 0)
    assert calls == []


def test_default_client_does_not_use_environment_proxy() -> None:
    transport_instance = HttpxTransport([ORIGIN])
    try:
        assert transport_instance._client.trust_env is False
        assert transport_instance._client.follow_redirects is False
    finally:
        transport_instance.close()
