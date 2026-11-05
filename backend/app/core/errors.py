"""统一业务异常与错误响应。"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_request_id, logger

DEFAULT_MESSAGES: dict[int, tuple[str, str]] = {
    400: ("BAD_REQUEST", "请求无法处理"),
    401: ("UNAUTHORIZED", "认证已失效，请重新登录"),
    403: ("FORBIDDEN", "无权执行该操作"),
    404: ("NOT_FOUND", "资源不存在或无权访问"),
    409: ("CONFLICT", "资源已被修改，请重新加载"),
    422: ("VALIDATION_ERROR", "请求参数不符合要求"),
    500: ("INTERNAL_ERROR", "服务器内部错误"),
}


class AppError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        details: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details


def error_body(code: str, message: str, details: list[dict[str, Any]] | None = None) -> dict:
    body: dict[str, Any] = {"error": {"code": code, "message": message}}
    if details:
        body["error"]["details"] = details
    body["request_id"] = get_request_id() or str(uuid.uuid4())
    return body


def _validation_details(exc: RequestValidationError) -> list[dict[str, str]]:
    details: list[dict[str, str]] = []
    for error in exc.errors():
        location = error.get("loc", ())
        path = ".".join(str(part) for part in location)
        message = str(error.get("msg", "参数不合法"))
        # 不透传 Pydantic 的原始 input（可能包含密码或完整请求体）。
        details.append({"path": path, "message": message})
    return details


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(exc.code, exc.message, exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=error_body("VALIDATION_ERROR", "请求参数不符合要求", _validation_details(exc)),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code, message = DEFAULT_MESSAGES.get(exc.status_code, ("HTTP_ERROR", "请求失败"))
        return JSONResponse(status_code=exc.status_code, content=error_body(code, message))

    @app.exception_handler(Exception)
    async def _unhandled_error(_: Request, exc: Exception) -> JSONResponse:
        request_id = get_request_id()
        logger.error(
            "unhandled_error",
            extra={"request_id": request_id, "error_type": type(exc).__name__},
        )
        code, message = DEFAULT_MESSAGES[500]
        return JSONResponse(status_code=500, content=error_body(code, message))
