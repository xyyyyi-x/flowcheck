"""Worker/dispatcher 共用的同步数据库操作。"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import update
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Run, RunEvent
from app.db.sync_session import session_scope

QUEUE_DEADLINE = timedelta(seconds=300)
RUN_DEADLINE = timedelta(seconds=330)


@dataclass
class ClaimedRun:
    run_id: uuid.UUID
    execution_token: uuid.UUID
    snapshot_ciphertext: str


def claim_run(
    run_id: uuid.UUID,
    session_factory: sessionmaker[Session],
    now: datetime | None = None,
) -> ClaimedRun | None:
    """原子 queued→running；重复消息或超时排队返回 None。"""
    claimed_at = now or datetime.now(UTC)
    token = uuid.uuid4()
    with session_scope(session_factory) as session:
        row = session.execute(
            update(Run)
            .where(
                Run.id == run_id,
                Run.status == "queued",
                Run.created_at > claimed_at - QUEUE_DEADLINE,
            )
            .values(
                status="running",
                started_at=claimed_at,
                execution_token=token,
                deadline_at=claimed_at + RUN_DEADLINE,
            )
            .returning(Run.snapshot_ciphertext)
        ).first()
        if row is None:
            return None
        session.add(
            RunEvent(
                run_id=run_id,
                event_type="run.started",
                payload_safe={"run_id": str(run_id), "status": "running"},
            )
        )
    return ClaimedRun(run_id=run_id, execution_token=token, snapshot_ciphertext=row[0])
