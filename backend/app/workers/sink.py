"""PostgresRunSink：带 run_id + execution_token 栅栏的同步写入。"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import update
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Run, RunEvent, StepResult
from app.db.sync_session import session_scope
from app.domain.contracts import RunOutcome, SafeStepResult
from app.domain.ports import RunNoLongerActive


class PostgresRunSink:
    def __init__(
        self,
        run_id: uuid.UUID,
        execution_token: uuid.UUID,
        session_factory: sessionmaker[Session],
    ) -> None:
        self.run_id = run_id
        self.execution_token = execution_token
        self._session_factory = session_factory

    def start_step(self, position: int) -> None:
        with session_scope(self._session_factory) as session:
            result = session.execute(
                update(StepResult)
                .where(
                    StepResult.run_id == self.run_id,
                    StepResult.position == position,
                    StepResult.status == "pending",
                )
                .values(status="running", started_at=datetime.now(UTC))
            )
            if result.rowcount != 1:
                raise RunNoLongerActive
            session.add(
                RunEvent(
                    run_id=self.run_id,
                    event_type="step.started",
                    payload_safe={
                        "run_id": str(self.run_id),
                        "position": position,
                        "status": "running",
                    },
                )
            )

    def save_step(self, position: int, result: SafeStepResult) -> None:
        with session_scope(self._session_factory) as session:
            updated = session.execute(
                update(StepResult)
                .where(
                    StepResult.run_id == self.run_id,
                    StepResult.position == position,
                    StepResult.status == "running",
                )
                .values(
                    status=result.status,
                    elapsed_ms=result.elapsed_ms,
                    request_safe=result.request_safe,
                    response_safe=result.response_safe,
                    assertions_safe=result.assertions_safe or [],
                    extracts_safe=result.extracts_safe or [],
                    error_code=result.error_code,
                    finished_at=datetime.now(UTC),
                )
            )
            if updated.rowcount != 1:
                raise RunNoLongerActive
            session.add(
                RunEvent(
                    run_id=self.run_id,
                    event_type="step.finished",
                    payload_safe={
                        "run_id": str(self.run_id),
                        "position": position,
                        "status": result.status,
                        "error_code": result.error_code,
                    },
                )
            )

    def finish(self, outcome: RunOutcome) -> None:
        with session_scope(self._session_factory) as session:
            finished = session.execute(
                update(Run)
                .where(
                    Run.id == self.run_id,
                    Run.execution_token == self.execution_token,
                    Run.status == "running",
                )
                .values(
                    status=outcome.status,
                    error_code=outcome.error_code,
                    finished_at=datetime.now(UTC),
                )
            )
            if finished.rowcount != 1:
                raise RunNoLongerActive
            running_error = outcome.error_code or "INTERNAL_ERROR"
            session.execute(
                update(StepResult)
                .where(
                    StepResult.run_id == self.run_id,
                    StepResult.status == "running",
                )
                .values(
                    status="error",
                    error_code=running_error,
                    finished_at=datetime.now(UTC),
                )
            )
            session.execute(
                update(StepResult)
                .where(
                    StepResult.run_id == self.run_id,
                    StepResult.status == "pending",
                )
                .values(status="skipped", finished_at=datetime.now(UTC))
            )
            session.add(
                RunEvent(
                    run_id=self.run_id,
                    event_type="run.finished",
                    payload_safe={
                        "run_id": str(self.run_id),
                        "status": outcome.status,
                        "error_code": outcome.error_code,
                    },
                )
            )
