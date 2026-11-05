"""运行提交：冻结快照、幂等键与同事务写入 queued 记录。"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, normalize_origin
from app.core.crypto import decrypt_json, encrypt_json
from app.core.errors import AppError
from app.db.models import Case, Environment, Project, Run, RunEvent, RunOutbox, StepResult
from app.domain.contracts import StepDefinition
from app.modules.runs.repository import get_run_by_idempotency
from app.modules.runs.schemas import RunCreated

RUN_QUEUE_DEADLINE = timedelta(seconds=300)
LIMITS = {
    "max_steps": 20,
    "request_max_bytes": 65536,
    "response_max_bytes": 1048576,
    "report_preview_bytes": 8192,
    "run_budget_s": 300,
}


def request_fingerprint(case_id: uuid.UUID, environment_id: uuid.UUID) -> str:
    return hashlib.sha256(f"{case_id}:{environment_id}".encode()).hexdigest()


def snapshot_payload(
    case: Case,
    environment: Environment,
    run_id: uuid.UUID,
    settings: Settings,
    captured_at: datetime,
) -> dict:
    config = decrypt_json(environment.config_ciphertext, settings.encryption_key)
    steps = [StepDefinition.model_validate(item) for item in case.steps]
    return {
        "schema_version": 1,
        "run_id": str(run_id),
        "case_id": str(case.id),
        "case_name": case.name,
        "case_version": case.version,
        "environment_id": str(environment.id),
        "environment_name": environment.name,
        "environment_version": environment.version,
        "target_origin": environment.base_url,
        "variables": config.get("variables", []),
        "common_headers": config.get("common_headers", []),
        "steps": [step.model_dump(mode="json") for step in steps],
        "limits": LIMITS,
        "captured_at": captured_at.isoformat().replace("+00:00", "Z"),
    }


def snapshot_from_ciphertext(ciphertext: str, settings: Settings) -> dict:
    return decrypt_json(ciphertext, settings.encryption_key)


def _validation_error(message: str, path: str) -> AppError:
    return AppError(
        "VALIDATION_ERROR",
        "请求参数不符合要求",
        422,
        details=[{"path": path, "message": message}],
    )


def _validate_case_and_environment(
    case: Case,
    environment: Environment,
    settings: Settings,
) -> list[StepDefinition]:
    try:
        steps = [StepDefinition.model_validate(item) for item in case.steps]
    except Exception as exc:
        raise _validation_error("用例步骤定义无效", "body.case_id") from exc
    if not steps:
        raise _validation_error("用例必须包含至少一个步骤", "body.case_id")
    if normalize_origin(environment.base_url) not in settings.allowed_origins:
        raise _validation_error("目标 origin 不在允许列表中", "body.environment_id")
    config = decrypt_json(environment.config_ciphertext, settings.encryption_key)
    variable_names = {item["name"] for item in config.get("variables", [])}
    for step_index, step in enumerate(steps):
        for extractor in step.extractors:
            if extractor.name in variable_names:
                raise _validation_error(
                    f"提取器名称与环境变量冲突: {extractor.name}",
                    f"body.case_id.steps.{step_index}.extractors",
                )
    return steps


async def create_run(
    db: AsyncSession,
    project: Project,
    case_id: uuid.UUID,
    environment_id: uuid.UUID,
    idempotency_key: uuid.UUID,
    settings: Settings,
) -> RunCreated:
    project_id = project.id
    fingerprint = request_fingerprint(case_id, environment_id)
    existing = await get_run_by_idempotency(db, project_id, idempotency_key)
    if existing is not None:
        if existing.request_fingerprint != fingerprint:
            raise AppError("CONFLICT", "Idempotency-Key 已用于不同请求", 409)
        return RunCreated(run_id=existing.id, status=existing.status, reused=True)

    case = await db.scalar(
        select(Case)
        .where(Case.id == case_id, Case.project_id == project_id)
        .with_for_update(read=True)
    )
    if case is None:
        raise AppError("NOT_FOUND", "资源不存在或无权访问", 404)
    environment = await db.scalar(
        select(Environment)
        .where(Environment.id == environment_id, Environment.project_id == project_id)
        .with_for_update(read=True)
    )
    if environment is None:
        raise AppError("NOT_FOUND", "资源不存在或无权访问", 404)

    steps = _validate_case_and_environment(case, environment, settings)

    now = datetime.now(UTC)
    run_id = uuid.uuid4()
    payload = snapshot_payload(case, environment, run_id, settings, now)
    run = Run(
        id=run_id,
        project_id=project_id,
        case_id=case.id,
        environment_id=environment.id,
        case_name=case.name,
        case_version=case.version,
        environment_name=environment.name,
        environment_version=environment.version,
        status="queued",
        snapshot_ciphertext=encrypt_json(payload, settings.encryption_key),
        idempotency_key=idempotency_key,
        request_fingerprint=fingerprint,
        deadline_at=now + RUN_QUEUE_DEADLINE,
    )
    db.add(run)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        existing = await get_run_by_idempotency(db, project_id, idempotency_key)
        if existing is not None:
            if existing.request_fingerprint != fingerprint:
                raise AppError("CONFLICT", "Idempotency-Key 已用于不同请求", 409) from exc
            return RunCreated(run_id=existing.id, status=existing.status, reused=True)
        raise AppError("INTERNAL_ERROR", "服务器内部错误", 500) from exc
    for position, step in enumerate(steps, start=1):
        db.add(
            StepResult(
                run_id=run.id,
                position=position,
                name=step.name,
                status="pending",
                assertions_safe=[],
                extracts_safe=[],
            )
        )
    db.add(
        RunEvent(
            run_id=run.id,
            event_type="run.queued",
            payload_safe={"run_id": str(run.id), "status": "queued"},
        )
    )
    db.add(
        RunOutbox(
            run_id=run.id,
            status="pending",
            attempt_count=0,
            next_attempt_at=now,
        )
    )
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        existing = await get_run_by_idempotency(db, project_id, idempotency_key)
        if existing is not None:
            if existing.request_fingerprint != fingerprint:
                raise AppError("CONFLICT", "Idempotency-Key 已用于不同请求", 409) from exc
            return RunCreated(run_id=existing.id, status=existing.status, reused=True)
        raise AppError("INTERNAL_ERROR", "服务器内部错误", 500) from exc
    return RunCreated(run_id=run.id, status="queued", reused=False)
