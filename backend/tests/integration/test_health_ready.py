"""ready 检查使用真实 PostgreSQL 执行 SELECT 1。"""

from __future__ import annotations

from httpx import ASGITransport, AsyncClient

from app.main import create_app
from tests.integration.conftest import build_test_settings


async def test_ready_returns_ok_with_real_database(api_client: AsyncClient) -> None:
    response = await api_client.get("/api/v1/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_ready_returns_503_and_no_connection_string_when_database_down() -> None:
    settings = build_test_settings()
    settings.app_database_url = "postgresql+asyncpg://test:test@127.0.0.1:1/test"
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/api/v1/health/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}
    assert "postgresql" not in response.text
    assert "test:test" not in response.text
