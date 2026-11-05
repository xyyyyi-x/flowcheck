"""认证依赖。"""

from __future__ import annotations

import uuid

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.security import decode_access_token
from app.db.async_session import get_async_session
from app.db.models import User

_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: AsyncSession = Depends(get_async_session),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AppError("UNAUTHORIZED", "认证已失效，请重新登录", 401)
    user_id: uuid.UUID = decode_access_token(credentials.credentials)
    user = await db.scalar(select(User).where(User.id == user_id))
    if user is None:
        raise AppError("UNAUTHORIZED", "认证已失效，请重新登录", 401)
    request.state.user = user
    return user
