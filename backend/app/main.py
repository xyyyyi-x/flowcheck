"""FastAPI 应用工厂。"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import Settings
from app.core.errors import register_exception_handlers
from app.core.logging import RequestContextMiddleware, configure_logging
from app.core.security import configure_security
from app.db.async_session import build_async_engine, build_session_factory


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or Settings()
    configure_logging()
    configure_security(resolved.jwt_secret)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = build_async_engine(resolved.app_database_url)
        app.state.engine = engine
        app.state.session_factory = build_session_factory(engine)
        try:
            yield
        finally:
            await engine.dispose()

    app = FastAPI(title="接口回归测试平台", version="0.1.0", docs_url="/docs", lifespan=lifespan)
    app.state.settings = resolved
    app.add_middleware(RequestContextMiddleware)
    if resolved.allowed_cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=resolved.allowed_cors_origins,
            allow_credentials=False,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    register_exception_handlers(app)

    from app.modules.auth.router import router as auth_router
    from app.modules.health.router import router as health_router
    from app.modules.projects.router import router as projects_router

    app.include_router(health_router, prefix="/api/v1")
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(projects_router, prefix="/api/v1")
    return app


app = None
