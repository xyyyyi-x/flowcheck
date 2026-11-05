"""Outbox 发布：每 2 秒处理最多 50 条，网络调用不持数据库事务。"""

from __future__ import annotations

import signal
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.core.logging import configure_logging, logger
from app.db.models import Run, RunOutbox
from app.db.sync_session import build_sync_engine, build_sync_session_factory, session_scope
from app.workers.reconcile import reconcile_runs
from app.workers.repository import QUEUE_DEADLINE

DISPATCH_INTERVAL = 2
RECONCILE_INTERVAL = 5
DISPATCH_BATCH = 50
PUBLISH_TIMEOUT = 3.0


def publish_with_timeout(
    publish: Callable[[str], None], run_id: str, timeout: float = PUBLISH_TIMEOUT
) -> None:
    """单次发布最多等待 timeout 秒；超时线程不阻塞维护循环。"""
    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(publish, run_id)
    try:
        future.result(timeout=timeout)
    except FuturesTimeout as exc:
        raise TimeoutError("publish timeout") from exc
    finally:
        executor.shutdown(wait=False)


@dataclass
class DispatchCounts:
    published: int = 0
    failed: int = 0
    abandoned: int = 0


def dispatch_due(
    now: datetime,
    publish: Callable[[str], None],
    session_factory: sessionmaker[Session],
    limit: int = DISPATCH_BATCH,
) -> DispatchCounts:
    counts = DispatchCounts()
    with session_scope(session_factory) as session:
        rows = session.execute(
            select(RunOutbox.id, RunOutbox.attempt_count, RunOutbox.run_id)
            .where(
                RunOutbox.status == "pending",
                RunOutbox.next_attempt_at <= now,
            )
            .order_by(RunOutbox.next_attempt_at, RunOutbox.id)
            .limit(limit)
        ).all()

    for outbox_id, attempt_count, run_id in rows:
        with session_scope(session_factory) as session:
            run = session.execute(
                select(Run.status, Run.created_at).where(Run.id == run_id)
            ).one_or_none()
            if run is None or run.status != "queued" or run.created_at <= now - QUEUE_DEADLINE:
                session.execute(
                    update(RunOutbox)
                    .where(RunOutbox.id == outbox_id, RunOutbox.status == "pending")
                    .values(status="abandoned")
                )
                counts.abandoned += 1
                continue

        try:
            publish_with_timeout(publish, str(run_id))
        except Exception:
            new_attempt = attempt_count + 1
            delay = min(2**new_attempt, 30)
            with session_scope(session_factory) as session:
                session.execute(
                    update(RunOutbox)
                    .where(RunOutbox.id == outbox_id, RunOutbox.status == "pending")
                    .values(
                        attempt_count=new_attempt,
                        next_attempt_at=now + timedelta(seconds=delay),
                        last_error_code="BROKER_UNAVAILABLE",
                    )
                )
            counts.failed += 1
        else:
            with session_scope(session_factory) as session:
                session.execute(
                    update(RunOutbox)
                    .where(RunOutbox.id == outbox_id, RunOutbox.status == "pending")
                    .values(status="sent", sent_at=now)
                )
            counts.published += 1
    return counts


def publish_to_celery(run_id: str) -> None:
    from app.workers.celery_app import celery_app

    celery_app.send_task("app.workers.tasks.execute_run", args=[run_id])


def main() -> None:
    configure_logging()
    settings = Settings()
    factory = build_sync_session_factory(build_sync_engine(settings.app_sync_database_url))
    stopping = False

    def _stop(signum, frame) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    next_dispatch = 0.0
    next_reconcile = 0.0
    while not stopping:
        current = time.monotonic()
        now = datetime.now(UTC)
        if current >= next_dispatch:
            try:
                counts = dispatch_due(now, publish_to_celery, factory)
                if counts.published or counts.failed or counts.abandoned:
                    logger.info(
                        "dispatch_completed",
                        extra={
                            "published": counts.published,
                            "failed": counts.failed,
                            "abandoned": counts.abandoned,
                        },
                    )
            except Exception:
                logger.exception("dispatch_loop_error")
            next_dispatch = current + DISPATCH_INTERVAL
        if current >= next_reconcile:
            try:
                reconcile_runs(now, factory)
            except Exception:
                logger.exception("reconcile_loop_error")
            next_reconcile = current + RECONCILE_INTERVAL
        time.sleep(0.5)


if __name__ == "__main__":
    main()
