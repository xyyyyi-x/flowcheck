"""健康检查路由。"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

router = APIRouter(tags=["health"])


@router.get("/health/live")
async def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
async def ready(request: Request) -> JSONResponse:
    session_factory = getattr(request.app.state, "session_factory", None)
    if session_factory is None:
        return JSONResponse(status_code=503, content={"status": "unavailable"})
    try:
        async with session_factory() as session:
            await session.execute(text("SELECT 1"))
    except (SQLAlchemyError, OSError):
        return JSONResponse(status_code=503, content={"status": "unavailable"})
    return JSONResponse(status_code=200, content={"status": "ok"})
