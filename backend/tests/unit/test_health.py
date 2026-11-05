"""健康检查与请求追踪的单元测试。"""

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app

FERNET_KEY = "u5nM7Qp0jXk2r8T4wY6zA1bC3dE5fG7hI9jK0lM2nO4="


def make_settings() -> Settings:
    return Settings(
        app_jwt_secret="a" * 64,
        app_encryption_key=FERNET_KEY,
        app_database_url="postgresql+asyncpg://u:p@db:5432/app",
        app_sync_database_url="postgresql+psycopg://u:p@db:5432/app",
        app_redis_broker_url="redis://redis:6379/0",
        app_redis_cache_url="redis://redis:6379/1",
        target_origins="http://demo-api:8001",
    )


def test_live_returns_ok() -> None:
    with TestClient(create_app(make_settings())) as client:
        response = client.get("/api/v1/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_every_response_has_request_id_header() -> None:
    with TestClient(create_app(make_settings())) as client:
        response = client.get("/api/v1/health/live")
    assert len(response.headers["X-Request-ID"]) == 36


def test_error_response_hides_internal_details() -> None:
    with TestClient(create_app(make_settings())) as client:
        response = client.get("/api/v1/definitely-missing")
    body = response.json()
    assert response.status_code == 404
    assert body["error"]["code"] == "NOT_FOUND"
    assert body["error"]["message"] == "资源不存在或无权访问"
    assert len(body["request_id"]) == 36
    assert "app_database_url" not in response.text


def test_health_response_contains_no_connection_string() -> None:
    with TestClient(create_app(make_settings())) as client:
        response = client.get("/api/v1/health/live")
    assert "postgresql" not in response.text
    assert "redis" not in response.text
