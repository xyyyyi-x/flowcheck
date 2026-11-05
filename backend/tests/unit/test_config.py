"""配置加载与安全边界的单元测试。"""

import pytest
from pydantic import ValidationError

from app.core.config import Settings, normalize_origin

FERNET_KEY = "u5nM7Qp0jXk2r8T4wY6zA1bC3dE5fG7hI9jK0lM2nO4="
JWT_SECRET = "a" * 64


def make_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "app_jwt_secret": JWT_SECRET,
        "app_encryption_key": FERNET_KEY,
        "app_database_url": "postgresql+asyncpg://u:p@db:5432/app",
        "app_sync_database_url": "postgresql+psycopg://u:p@db:5432/app",
        "app_redis_broker_url": "redis://redis:6379/0",
        "app_redis_cache_url": "redis://redis:6379/1",
        "target_origins": "http://demo-api:8001",
    }
    values.update(overrides)
    return Settings(**values)


def test_valid_settings_load() -> None:
    settings = make_settings()
    assert settings.allowed_origins == ["http://demo-api:8001"]


def test_missing_jwt_secret_fails() -> None:
    with pytest.raises(ValidationError):
        make_settings(app_jwt_secret="")


def test_short_jwt_secret_fails() -> None:
    with pytest.raises(ValidationError):
        make_settings(app_jwt_secret="short")


def test_invalid_fernet_key_fails() -> None:
    with pytest.raises(ValidationError):
        make_settings(app_encryption_key="not-a-fernet-key")


def test_origin_with_path_is_rejected() -> None:
    with pytest.raises(ValidationError):
        make_settings(target_origins="https://example.com/api")


def test_origin_with_userinfo_or_query_is_rejected() -> None:
    for bad in ("https://user:pw@example.com", "https://example.com?a=1", "ftp://example.com"):
        with pytest.raises(ValidationError):
            make_settings(target_origins=bad)


def test_unknown_origin_normalization_accepts_default_port() -> None:
    assert normalize_origin("http://demo-api:8001") == "http://demo-api:8001"
    assert normalize_origin("https://Example.COM:443") == "https://example.com:443"


def test_secrets_are_not_in_repr() -> None:
    settings = make_settings()
    assert JWT_SECRET not in repr(settings)
    assert FERNET_KEY not in repr(settings)
