"""运行相关的只读查询。"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Project, Run


async def get_owned_run(db: AsyncSession, owner_id: uuid.UUID, run_id: uuid.UUID) -> Run | None:
    return await db.scalar(
        select(Run)
        .join(Project, Project.id == Run.project_id)
        .where(Run.id == run_id, Project.owner_id == owner_id)
    )


async def get_run_by_idempotency(
    db: AsyncSession, project_id: uuid.UUID, idempotency_key: uuid.UUID
) -> Run | None:
    return await db.scalar(
        select(Run).where(Run.project_id == project_id, Run.idempotency_key == idempotency_key)
    )
