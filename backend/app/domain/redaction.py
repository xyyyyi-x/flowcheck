"""秘密注册与安全视图：持久化前完成脱敏。"""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlsplit

from app.domain.contracts import (
    SENSITIVE_KEYS,
    AssertionOutcome,
    RenderedRequest,
    ResponseData,
)

SENSITIVE_HEADERS = {
    "authorization",
    "proxy-authorization",
    "cookie",
    "set-cookie",
    "x-api-key",
}
REDACTED = "[REDACTED]"
PREVIEW_LIMIT = 8192


class SecretRegistry:
    def __init__(self) -> None:
        self._values: set[str] = set()

    def add(self, value: Any) -> None:
        if isinstance(value, str) and value:
            self._values.add(value)

    def add_all(self, values: list[Any]) -> None:
        for value in values:
            self.add(value)

    def redact_text(self, text: str) -> str:
        for secret in sorted(self._values, key=len, reverse=True):
            if secret in text:
                text = text.replace(secret, REDACTED)
        return text

    @property
    def values(self) -> list[str]:
        return list(self._values)


def redact_json(value: Any, registry: SecretRegistry) -> Any:
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if isinstance(key, str) and key.lower() in SENSITIVE_KEYS:
                result[key] = REDACTED
            else:
                result[key] = redact_json(item, registry)
        return result
    if isinstance(value, list):
        return [redact_json(item, registry) for item in value]
    if isinstance(value, str):
        return registry.redact_text(value)
    return value


def redact_headers(headers: dict[str, str], registry: SecretRegistry) -> dict[str, str]:
    result = {}
    for name, value in headers.items():
        if name.lower() in SENSITIVE_HEADERS:
            result[name] = REDACTED
        else:
            result[name] = registry.redact_text(value)
    return result


def preview_json(value: Any, registry: SecretRegistry, limit: int = PREVIEW_LIMIT) -> str | None:
    if value is None:
        return None
    text = json.dumps(redact_json(value, registry), ensure_ascii=False)
    encoded = text.encode("utf-8")
    if len(encoded) <= limit:
        return text
    truncated = encoded[: max(0, limit - 64)].decode("utf-8", errors="ignore")
    return truncated + "…[truncated]"


def request_safe(
    request: RenderedRequest, registry: SecretRegistry, limit: int = PREVIEW_LIMIT
) -> dict[str, Any]:
    parsed = urlsplit(request.url)
    return {
        "method": request.method,
        "origin": f"{parsed.scheme}://{parsed.netloc}",
        "path_template": request.path_template,
        "query_keys": request.query_keys,
        "headers_safe": redact_headers(request.headers, registry),
        "json_preview": preview_json(request.json_body, registry, limit),
    }


def response_safe(
    response: ResponseData | None,
    registry: SecretRegistry,
    omit_body: bool,
    limit: int = PREVIEW_LIMIT,
) -> dict[str, Any] | None:
    if response is None:
        return None
    preview = None
    body_omitted = omit_body or not response.is_json
    if not body_omitted:
        preview = preview_json(response.body_json, registry, limit)
    return {
        "status_code": response.status_code,
        "headers_safe": redact_headers(response.headers, registry),
        "json_preview": preview,
        "body_omitted": body_omitted,
    }


def assertions_safe(
    outcomes: list[AssertionOutcome], registry: SecretRegistry
) -> list[dict[str, Any]]:
    result = []
    for outcome in outcomes:
        item: dict[str, Any] = {"type": outcome.type, "passed": outcome.passed}
        if outcome.selector is not None:
            item["selector"] = outcome.selector
        item["expected_safe"] = redact_json(outcome.expected_safe, registry)
        item["actual_safe"] = redact_json(outcome.actual_safe, registry)
        result.append(item)
    return result
