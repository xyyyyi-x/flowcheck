"""认证相关的请求/响应模型。"""

from __future__ import annotations

import uuid
from typing import Annotated

from pydantic import Field, StringConstraints, field_validator

from app.core.schemas import ApiModel, UtcDatetime

Username = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=3,
        max_length=32,
        pattern=r"^[A-Za-z0-9_]+$",
    ),
]
Password = Annotated[str, Field(min_length=8, max_length=128)]


class RegisterRequest(ApiModel):
    username: Username
    password: Password

    @field_validator("username")
    @classmethod
    def _normalize_username(cls, value: str) -> str:
        return value.lower()


class LoginRequest(ApiModel):
    username: Username
    password: Password

    @field_validator("username")
    @classmethod
    def _normalize_username(cls, value: str) -> str:
        return value.lower()


class UserRead(ApiModel):
    id: uuid.UUID
    username: str
    created_at: UtcDatetime


class TokenResponse(ApiModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 1800
