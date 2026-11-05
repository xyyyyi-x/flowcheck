"""认证路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import issue_access_token
from app.db.async_session import get_async_session
from app.db.models import User
from app.modules.auth.deps import get_current_user
from app.modules.auth.schemas import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserRead,
)
from app.modules.auth.service import authenticate, register_user

router = APIRouter(tags=["auth"])


@router.post("/auth/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest, db: AsyncSession = Depends(get_async_session)
) -> UserRead:
    user = await register_user(db, payload.username, payload.password)
    return UserRead.model_validate(user)


@router.post("/auth/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest, db: AsyncSession = Depends(get_async_session)
) -> TokenResponse:
    user = await authenticate(db, payload.username, payload.password)
    return TokenResponse(access_token=issue_access_token(user.id))


@router.get("/auth/me", response_model=UserRead)
async def me(user: User = Depends(get_current_user)) -> UserRead:
    return UserRead.model_validate(user)
