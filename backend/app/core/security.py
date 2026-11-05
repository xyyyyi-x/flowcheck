"""Argon2 密码哈希与 HS256 JWT。"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import jwt
from pwdlib import PasswordHash

from app.core.errors import AppError

ALGORITHM = "HS256"
TOKEN_TTL = timedelta(minutes=30)

_password_hash = PasswordHash.recommended()
_configured_secret: str | None = None


def configure_security(secret: str) -> None:
    global _configured_secret
    _configured_secret = secret


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _password_hash.verify(plain, hashed)
    except Exception:
        return False


def _secret() -> str:
    if _configured_secret is None:
        raise RuntimeError("JWT 密钥尚未配置")
    return _configured_secret


def issue_access_token(
    user_id: uuid.UUID, now: datetime | None = None, secret: str | None = None
) -> str:
    issued_at = now or datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "iat": int(issued_at.timestamp()),
        "exp": int((issued_at + TOKEN_TTL).timestamp()),
    }
    return jwt.encode(payload, secret or _secret(), algorithm=ALGORITHM)


def decode_token(token: str, secret: str | None = None) -> tuple[uuid.UUID, datetime]:
    try:
        payload = jwt.decode(
            token,
            secret or _secret(),
            algorithms=[ALGORITHM],
            options={"require": ["sub", "iat", "exp"]},
        )
        return uuid.UUID(payload["sub"]), datetime.fromtimestamp(int(payload["exp"]), tz=UTC)
    except (jwt.PyJWTError, ValueError, KeyError, TypeError) as exc:
        raise AppError("UNAUTHORIZED", "认证已失效，请重新登录", 401) from exc


def decode_access_token(token: str, secret: str | None = None) -> uuid.UUID:
    user_id, _ = decode_token(token, secret)
    return user_id
