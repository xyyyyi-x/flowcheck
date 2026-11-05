"""HTTPX 有界传输：固定 origin、禁止重定向、流式上限与不重试。"""

from __future__ import annotations

import json
import time
from collections.abc import Iterable
from typing import Any
from urllib.parse import urlsplit

import httpx

from app.domain.contracts import RenderedRequest, ResponseData
from app.domain.ports import (
    NetworkFailure,
    RequestTimeout,
    ResponseTooLarge,
    RunBudgetExceeded,
    TargetNotAllowed,
)

RESPONSE_MAX_BYTES = 1024 * 1024
FORBIDDEN_REQUEST_HEADERS = {"host", "content-length", "connection", "transfer-encoding"}


class HttpxTransport:
    def __init__(
        self,
        allowed_origins: Iterable[str],
        client: httpx.Client | None = None,
        response_max_bytes: int = RESPONSE_MAX_BYTES,
    ) -> None:
        self._allowed_origins = set(allowed_origins)
        self._response_max_bytes = response_max_bytes
        self._client = client or httpx.Client(trust_env=False, follow_redirects=False, timeout=30.0)

    def close(self) -> None:
        self._client.close()

    def send(self, request: RenderedRequest, timeout_s: int, remaining_s: float) -> ResponseData:
        self._client.cookies.clear()
        parsed = urlsplit(request.url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        if origin not in self._allowed_origins:
            raise TargetNotAllowed(origin)
        if any(name.lower() in FORBIDDEN_REQUEST_HEADERS for name in request.headers):
            raise TargetNotAllowed("restricted header")
        if remaining_s <= 0:
            raise RunBudgetExceeded("run budget exhausted")

        effective_timeout = min(float(timeout_s), remaining_s)
        headers = {
            name: value
            for name, value in request.headers.items()
            if name.lower() not in FORBIDDEN_REQUEST_HEADERS
        }
        body = request.json_body
        if body is not None and not any(name.lower() == "content-type" for name in headers):
            headers["Content-Type"] = "application/json"

        started = time.perf_counter()
        try:
            with self._client.stream(
                request.method,
                request.url,
                headers=headers,
                json=body if body is not None else None,
                timeout=httpx.Timeout(
                    connect=min(effective_timeout, 3.0),
                    read=effective_timeout,
                    write=effective_timeout,
                    pool=effective_timeout,
                ),
                follow_redirects=False,
            ) as response:
                chunks: list[bytes] = []
                total = 0
                for chunk in response.iter_bytes():
                    total += len(chunk)
                    if total > self._response_max_bytes:
                        raise ResponseTooLarge("response exceeds 1MiB")
                    if time.perf_counter() - started > remaining_s:
                        raise RunBudgetExceeded("run budget exhausted during read")
                    chunks.append(chunk)
                status_code = response.status_code
                response_headers = {name.lower(): value for name, value in response.headers.items()}
                content = b"".join(chunks)
        except httpx.TimeoutException as exc:
            raise RequestTimeout("request timed out") from exc
        except (httpx.HTTPError, OSError) as exc:
            raise NetworkFailure("network error") from exc

        elapsed_ms = (time.perf_counter() - started) * 1000
        body_json: Any = None
        is_json = False
        content_type = response_headers.get("content-type", "").split(";")[0].strip()
        if content and (content_type == "application/json" or content_type.endswith("+json")):
            try:
                body_json = json.loads(content.decode("utf-8"))
                is_json = True
            except (UnicodeDecodeError, json.JSONDecodeError):
                is_json = False
                body_json = None
        return ResponseData(
            status_code=status_code,
            headers=response_headers,
            body_json=body_json,
            is_json=is_json,
            elapsed_ms=elapsed_ms,
        )
