"""脱敏发生在持久化之前：header、JSON、URL 与预览截断。"""

from __future__ import annotations

import json

from app.domain.contracts import AssertionOutcome, RenderedRequest, ResponseData
from app.domain.redaction import (
    REDACTED,
    SecretRegistry,
    assertions_safe,
    redact_headers,
    redact_json,
    request_safe,
    response_safe,
)


def registry() -> SecretRegistry:
    item = SecretRegistry()
    item.add("super-secret-token")
    item.add("hunter2-password")
    return item


def test_registry_and_sensitive_keys_are_redacted_recursively() -> None:
    payload = {
        "password": "hunter2-password",
        "nested": {"access_token": "super-secret-token", "note": "use super-secret-token here"},
        "items": [{"secret": "anything"}, "hunter2-password"],
    }
    redacted = redact_json(payload, registry())
    text = json.dumps(redacted)
    assert "hunter2-password" not in text
    assert "super-secret-token" not in text
    assert redacted["password"] == REDACTED
    assert redacted["nested"]["access_token"] == REDACTED
    assert redacted["nested"]["note"] == f"use {REDACTED} here"


def test_sensitive_headers_are_masked_entirely() -> None:
    headers = redact_headers(
        {
            "Authorization": "Bearer super-secret-token",
            "Set-Cookie": "session=super-secret-token",
            "X-Trace": "contains super-secret-token",
            "Accept": "application/json",
        },
        registry(),
    )
    assert headers["Authorization"] == REDACTED
    assert headers["Set-Cookie"] == REDACTED
    assert headers["X-Trace"] == f"contains {REDACTED}"
    assert headers["Accept"] == "application/json"


def test_request_safe_hides_query_values_and_uses_path_template() -> None:
    request = RenderedRequest(
        method="GET",
        url="http://demo-api:8001/articles/abc?token=super-secret-token",
        headers={"Authorization": "Bearer super-secret-token"},
        json_body={"password": "hunter2-password", "title": "hello"},
        path_template="/articles/{id}",
        query_keys=["token"],
        timeout_s=10,
    )
    safe = request_safe(request, registry())
    assert safe["origin"] == "http://demo-api:8001"
    assert safe["path_template"] == "/articles/{id}"
    assert safe["query_keys"] == ["token"]
    assert "super-secret-token" not in json.dumps(safe)
    assert REDACTED in safe["json_preview"]


def test_response_safe_honors_omit_and_non_json() -> None:
    response = ResponseData(
        status_code=200,
        headers={"Authorization": "Bearer super-secret-token"},
        body_json={"token": "super-secret-token", "ok": True},
        is_json=True,
        elapsed_ms=12.0,
    )
    omitted = response_safe(response, registry(), omit_body=True)
    assert omitted["body_omitted"] is True
    assert omitted["json_preview"] is None

    non_json = response_safe(ResponseData(200, {}, None, False, 1.0), registry(), omit_body=False)
    assert non_json["body_omitted"] is True
    assert non_json["json_preview"] is None


def test_preview_is_bounded_and_redacted() -> None:
    response = ResponseData(
        status_code=200,
        headers={},
        body_json={"data": "super-secret-token-" + "x" * 20000},
        is_json=True,
        elapsed_ms=1.0,
    )
    safe = response_safe(response, registry(), omit_body=False)
    preview = safe["json_preview"]
    assert len(preview.encode("utf-8")) <= 8192
    assert "super-secret-token" not in preview
    assert "truncated" in preview


def test_assertion_views_are_redacted() -> None:
    outcomes = [
        AssertionOutcome(
            type="json_equals",
            passed=False,
            selector="$.token",
            expected_safe="super-secret-token",
            actual_safe={"echo": "super-secret-token", "other": 1},
        )
    ]
    safe = assertions_safe(outcomes, registry())
    assert safe[0]["expected_safe"] == REDACTED
    assert safe[0]["actual_safe"]["echo"] == REDACTED
