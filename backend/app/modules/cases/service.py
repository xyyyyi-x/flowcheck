"""用例 CRUD；steps 作为完整聚合整体替换。"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.db.models import ApiDefinition, Case
from app.modules.cases.schemas import CaseCreate, CaseUpdate


def _steps_payload(steps: list) -> list[dict[str, Any]]:
    return [step.model_dump(mode="json") for step in steps]


async def _validate_source_apis(db: AsyncSession, project_id: uuid.UUID, steps: list) -> None:
    ids = {step.source_api_id for step in steps if step.source_api_id is not None}
    if not ids:
        return
    found = set(
        await db.scalars(
            select(ApiDefinition.id).where(
                ApiDefinition.project_id == project_id, ApiDefinition.id.in_(ids)
            )
        )
    )
    if found != ids:
        raise AppError("NOT_FOUND", "资源不存在或无权访问", 404)


async def create_case(db: AsyncSession, project_id: uuid.UUID, payload: CaseCreate) -> Case:
    await _validate_source_apis(db, project_id, payload.steps)
    case = Case(
        project_id=project_id,
        name=payload.name,
        description=payload.description,
        version=1,
        steps=_steps_payload(payload.steps),
    )
    db.add(case)
    await db.commit()
    await db.refresh(case)
    return case


async def update_case(db: AsyncSession, case: Case, payload: CaseUpdate) -> Case:
    if payload.version != case.version:
        raise AppError("CONFLICT", "用例已被修改，请重新加载", 409)
    await _validate_source_apis(db, case.project_id, payload.steps)
    case.name = payload.name
    case.description = payload.description
    case.steps = _steps_payload(payload.steps)
    case.version += 1
    await db.commit()
    await db.refresh(case)
    return case


async def list_cases(
    db: AsyncSession, project_id: uuid.UUID, page: int, page_size: int
) -> tuple[list[Case], int]:
    total = await db.scalar(
        select(func.count()).select_from(Case).where(Case.project_id == project_id)
    )
    items = await db.scalars(
        select(Case)
        .where(Case.project_id == project_id)
        .order_by(Case.created_at.desc(), Case.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(items), int(total or 0)


async def get_case(db: AsyncSession, project_id: uuid.UUID, case_id: uuid.UUID) -> Case | None:
    return await db.scalar(select(Case).where(Case.id == case_id, Case.project_id == project_id))
