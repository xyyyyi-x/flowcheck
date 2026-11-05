"""注册与登录业务逻辑。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.security import hash_password, verify_password
from app.db.models import User


async def register_user(db: AsyncSession, username: str, password: str) -> User:
    existing = await db.scalar(select(User.id).where(User.username == username))
    if existing is not None:
        raise AppError("CONFLICT", "用户名已存在", 409)
    user = User(username=username, password_hash=hash_password(password))
    db.add(user)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise AppError("CONFLICT", "用户名已存在", 409) from exc
    await db.refresh(user)
    return user


async def authenticate(db: AsyncSession, username: str, password: str) -> User:
    user = await db.scalar(select(User).where(User.username == username))
    if user is None or not verify_password(password, user.password_hash):
        raise AppError("UNAUTHORIZED", "用户名或密码错误", 401)
    return user
