"""已抢占 run 的执行包装：软超时与未处理异常的尽力终结。"""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import UTC, datetime

from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.core.logging import logger
from app.domain.contracts import RunOutcome
from app.domain.ports import HttpTransport, RunNoLongerActive
from app.domain.runner import execute_snapshot
from app.workers.repository import ClaimedRun
from app.workers.sink import PostgresRunSink
from app.workers.snapshot import decode_snapshot


def _safe_finish(sink: PostgresRunSink, outcome: RunOutcome) -> None:
    try:
        sink.finish(outcome)
    except RunNoLongerActive:
        return


def execute_claimed(
    claimed: ClaimedRun,
    settings: Settings,
    session_factory: sessionmaker[Session],
    transport: HttpTransport,
    monotonic: Callable[[], float] = time.monotonic,
) -> RunOutcome | None:
    sink = PostgresRunSink(claimed.run_id, claimed.execution_token, session_factory)
    try:
        snapshot = decode_snapshot(claimed.snapshot_ciphertext, settings)
        return execute_snapshot(snapshot, transport, sink, monotonic)
    except SoftTimeLimitExceeded:
        _safe_finish(sink, RunOutcome("interrupted", "RUN_TIMEOUT", 0))
        return None
    except RunNoLongerActive:
        return None
    except Exception:
        logger.exception(
            "worker_execution_failed",
            extra={"run_id": str(claimed.run_id)},
        )
        _safe_finish(sink, RunOutcome("error", "INTERNAL_ERROR", 0))
        return None


def utcnow() -> datetime:
    return datetime.now(UTC)
