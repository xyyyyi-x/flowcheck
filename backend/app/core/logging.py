"""请求关联 ID 与安全的结构化日志。"""

from __future__ import annotations

import json
import logging
import sys
import time
import uuid
from contextvars import ContextVar
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)

logger = logging.getLogger("app")


def get_request_id() -> str | None:
    return _request_id.get()


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
        }
        for key in ("request_id", "run_id", "step_position", "error_code", "duration_ms"):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
    logging.getLogger("uvicorn.access").disabled = True


class RequestContextMiddleware(BaseHTTPMiddleware):
    """为每个请求生成 request_id，并记录不含查询串/请求体的访问日志。"""

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = str(uuid.uuid4())
        token = _request_id.set(request_id)
        started = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            duration_ms = round((time.perf_counter() - started) * 1000)
            logger.info(
                "request_completed",
                extra={
                    "request_id": request_id,
                    "duration_ms": duration_ms,
                },
            )
            _request_id.reset(token)
        response.headers["X-Request-ID"] = request_id
        return response
