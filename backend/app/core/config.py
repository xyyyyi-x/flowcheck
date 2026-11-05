"""应用配置：启动时校验必需密钥与受控 origin。"""

from __future__ import annotations

from urllib.parse import urlsplit

from cryptography.fernet import Fernet
from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def normalize_origin(url: str) -> str:
    """将 URL 规范化为 scheme://host[:port]；拒绝路径、query、fragment 与凭据。"""
    if not isinstance(url, str) or not url:
        raise ValueError("origin 不能为空")
    parts = urlsplit(url.strip())
    if parts.scheme not in {"http", "https"}:
        raise ValueError("origin 只允许 http 或 https")
    if parts.username is not None or parts.password is not None:
        raise ValueError("origin 不能包含凭据")
    if parts.path not in {"", "/"} or parts.query or parts.fragment:
        raise ValueError("origin 不能包含路径、query 或 fragment")
    try:
        port = parts.port
    except ValueError as exc:
        raise ValueError("origin 端口非法") from exc
    host = (parts.hostname or "").lower()
    if not host:
        raise ValueError("origin 缺少主机名")
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    if port is None:
        return f"{parts.scheme}://{host}"
    return f"{parts.scheme}://{host}:{port}"


def _split_csv(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore", case_sensitive=False)

    app_jwt_secret: SecretStr
    app_encryption_key: SecretStr
    app_database_url: str
    app_sync_database_url: str
    app_redis_broker_url: str
    app_redis_cache_url: str
    target_origins: str = "http://demo-api:8001"
    cors_origins: str = ""

    @field_validator("app_jwt_secret")
    @classmethod
    def _validate_jwt_secret(cls, value: SecretStr) -> SecretStr:
        raw = value.get_secret_value()
        if len(raw.encode("utf-8")) < 32:
            raise ValueError("APP_JWT_SECRET 至少需要 32 字节")
        return value

    @field_validator("app_encryption_key")
    @classmethod
    def _validate_fernet_key(cls, value: SecretStr) -> SecretStr:
        try:
            Fernet(value.get_secret_value().encode("utf-8"))
        except (ValueError, TypeError) as exc:
            raise ValueError("APP_ENCRYPTION_KEY 必须是合法 Fernet key") from exc
        return value

    @model_validator(mode="after")
    def _validate_origins(self) -> Settings:
        origins = _split_csv(self.target_origins)
        if not origins:
            raise ValueError("TARGET_ORIGINS 至少需要一个 origin")
        for origin in origins:
            normalize_origin(origin)
        for origin in _split_csv(self.cors_origins):
            normalize_origin(origin)
        return self

    @property
    def jwt_secret(self) -> str:
        return self.app_jwt_secret.get_secret_value()

    @property
    def encryption_key(self) -> str:
        return self.app_encryption_key.get_secret_value()

    @property
    def allowed_origins(self) -> list[str]:
        return [normalize_origin(origin) for origin in _split_csv(self.target_origins)]

    @property
    def allowed_cors_origins(self) -> list[str]:
        return _split_csv(self.cors_origins)
