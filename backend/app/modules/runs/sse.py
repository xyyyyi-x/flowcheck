"""持久化 SSE：数据库事件回放、心跳、过期关闭与短会话轮询。"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.errors import AppError
from app.core.security import decode_token
from app.db.models import Project, Run
from app.modules.runs.repository import get_events, get_run_status

TERMINAL_STATUSES = {"passed", "failed", "error", "interrupted"}
_bearer = HTTPBearer(auto_error=False)


@dataclass
class SseContext:
    run_id: uuid.UUID
    expires_at: datetime


async def sse_context(
    run_id: uuid.UUID,
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> SseContext:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AppError("UNAUTHORIZED", "认证已失效，请重新登录", 401)
    user_id, expires_at = decode_token(credentials.credentials)
    session_factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with session_factory() as session:
        owned = await session.scalar(
            select(Run.id)
            .join(Project, Project.id == Run.project_id)
            .where(Run.id == run_id, Project.owner_id == user_id)
        )
    if owned is None:
        raise AppError("NOT_FOUND", "资源不存在或无权访问", 404)
    return SseContext(run_id=run_id, expires_at=expires_at)


def format_frame(event_id: int, event_type: str, payload: dict) -> str:
    data = json.dumps(payload, ensure_ascii=False)
    return f"id: {event_id}\nevent: {event_type}\ndata: {data}\n\n"


async def stream_run_events(
    run_id: uuid.UUID,
    after: int,
    expires_at: datetime,
    session_factory: async_sessionmaker[AsyncSession],
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    wall_clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    connection_seconds: float = 60.0,
    heartbeat_seconds: float = 15.0,
    poll_seconds: float = 1.0,
) -> AsyncIterator[str]:
    started = monotonic()
    last_heartbeat = started
    cursor = after
    while True:
        if wall_clock() >= expires_at:
            return
        if monotonic() - started >= connection_seconds:
            return
        async with session_factory() as session:
            events = await get_events(session, run_id, cursor, 100)
            status = await get_run_status(session, run_id)
        if events:
            for event in events:
                cursor = event.id
                yield format_frame(event.id, event.event_type, event.payload_safe)
            last_heartbeat = monotonic()
            continue
        if status in TERMINAL_STATUSES or status is None:
            return
        current = monotonic()
        if current - last_heartbeat >= heartbeat_seconds:
            yield ": heartbeat\n\n"
            last_heartbeat = current
            continue
        await sleep(poll_seconds)
