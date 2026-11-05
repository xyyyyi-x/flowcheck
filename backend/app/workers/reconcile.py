"""超时回收：排队未抢占与 Worker 中断的确定性终结。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import update
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Run, RunEvent, RunOutbox, StepResult
from app.db.sync_session import session_scope
from app.workers.repository import QUEUE_DEADLINE, RUN_DEADLINE


@dataclass
class ReconcileCounts:
    dispatch_timeouts: int = 0
    worker_interruptions: int = 0


def reconcile_runs(now: datetime, session_factory: sessionmaker[Session]) -> ReconcileCounts:
    counts = ReconcileCounts()
    with session_scope(session_factory) as session:
        queued_ids = list(
            session.execute(
                update(Run)
                .where(
                    Run.status == "queued",
                    Run.created_at <= now - QUEUE_DEADLINE,
                )
                .values(
                    status="error",
                    error_code="DISPATCH_TIMEOUT",
                    finished_at=now,
                )
                .returning(Run.id)
            ).scalars()
        )
        for run_id in queued_ids:
            session.execute(
                update(StepResult)
                .where(StepResult.run_id == run_id, StepResult.status == "pending")
                .values(status="skipped", finished_at=now)
            )
            session.execute(
                update(RunOutbox)
                .where(RunOutbox.run_id == run_id, RunOutbox.status == "pending")
                .values(status="abandoned")
            )
            session.add(
                RunEvent(
                    run_id=run_id,
                    event_type="run.finished",
                    payload_safe={
                        "run_id": str(run_id),
                        "status": "error",
                        "error_code": "DISPATCH_TIMEOUT",
                    },
                )
            )
        counts.dispatch_timeouts = len(queued_ids)

    with session_scope(session_factory) as session:
        running_ids = list(
            session.execute(
                update(Run)
                .where(
                    Run.status == "running",
                    Run.started_at <= now - RUN_DEADLINE,
                )
                .values(
                    status="interrupted",
                    error_code="WORKER_INTERRUPTED",
                    finished_at=now,
                )
                .returning(Run.id)
            ).scalars()
        )
        for run_id in running_ids:
            session.execute(
                update(StepResult)
                .where(StepResult.run_id == run_id, StepResult.status == "running")
                .values(
                    status="error",
                    error_code="WORKER_INTERRUPTED",
                    finished_at=now,
                )
            )
            session.execute(
                update(StepResult)
                .where(StepResult.run_id == run_id, StepResult.status == "pending")
                .values(status="skipped", finished_at=now)
            )
            session.add(
                RunEvent(
                    run_id=run_id,
                    event_type="run.finished",
                    payload_safe={
                        "run_id": str(run_id),
                        "status": "interrupted",
                        "error_code": "WORKER_INTERRUPTED",
                    },
                )
            )
        counts.worker_interruptions = len(running_ids)
    return counts
