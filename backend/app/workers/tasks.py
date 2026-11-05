"""Celery 任务：按 run_id 抢占并执行一次线性回归。"""

from __future__ import annotations

import time
import uuid

from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.core.logging import configure_logging
from app.db.sync_session import build_sync_engine, build_sync_session_factory
from app.infra.http_transport import HttpxTransport
from app.workers.celery_app import celery_app
from app.workers.execution import execute_claimed
from app.workers.repository import claim_run

_session_factory: sessionmaker[Session] | None = None


def get_session_factory() -> sessionmaker[Session]:
    """在 worker 子进程内懒创建引擎，避免 fork 后复用父进程连接池。"""
    global _session_factory
    if _session_factory is None:
        settings = Settings()
        engine = build_sync_engine(settings.app_sync_database_url)
        _session_factory = build_sync_session_factory(engine)
    return _session_factory


@celery_app.task(name="app.workers.tasks.execute_run")
def execute_run(run_id: str) -> None:
    configure_logging()
    settings = Settings()
    factory = get_session_factory()
    claimed = claim_run(uuid.UUID(run_id), factory)
    if claimed is None:
        return
    transport = HttpxTransport(settings.allowed_origins)
    try:
        execute_claimed(claimed, settings, factory, transport, time.monotonic)
    finally:
        transport.close()
