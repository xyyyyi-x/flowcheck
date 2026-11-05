"""真实 PostgreSQL 集成测试 fixture。"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator

import pytest
from alembic import command
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import Settings
from app.main import create_app
from tests.integration.db_utils import alembic_config, sync_database_url


@pytest.fixture(scope="session", autouse=True)
def migrated_database() -> Iterator[None]:
    config = alembic_config()
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    yield


@pytest.fixture(autouse=True)
def clean_tables(migrated_database: None) -> Iterator[None]:
    engine = create_engine(sync_database_url())
    try:
        with engine.begin() as connection:
            # 测试库是隔离的；清理前终止其它连接，避免遗留事务阻塞 TRUNCATE。
            connection.execute(
                text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = current_database() AND pid <> pg_backend_pid()"
                )
            )
            connection.execute(
                text(
                    "TRUNCATE users, projects, environments, api_definitions, cases, "
                    "runs, step_results, run_events, run_outbox RESTART IDENTITY CASCADE"
                )
            )
        yield
    finally:
        engine.dispose()


@pytest.fixture
async def db() -> AsyncIterator:
    engine = create_async_engine(sync_database_url().replace("+psycopg", "+asyncpg"))
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
        await session.rollback()
    await engine.dispose()


def build_test_settings(database_url: str | None = None) -> Settings:
    async_url = database_url or sync_database_url().replace("+psycopg", "+asyncpg")
    sync_url = (database_url or sync_database_url()).replace("+asyncpg", "+psycopg")
    return Settings(
        app_jwt_secret="integration-secret-" + "x" * 32,
        app_encryption_key="u5nM7Qp0jXk2r8T4wY6zA1bC3dE5fG7hI9jK0lM2nO4=",
        app_database_url=async_url,
        app_sync_database_url=sync_url,
        app_redis_broker_url="redis://127.0.0.1:56379/0",
        app_redis_cache_url="redis://127.0.0.1:56379/1",
        target_origins="http://demo-api:8001",
    )


@pytest.fixture
async def api_client() -> AsyncIterator[AsyncClient]:
    app = create_app(build_test_settings())
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            yield client
