"""项目归属依赖，供所有项目内子资源复用。"""

from __future__ import annotations

import uuid

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.db.async_session import get_async_session
from app.db.models import Project, User
from app.modules.auth.deps import get_current_user
from app.modules.projects.service import get_owned_project


async def require_owned_project(
    project_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
) -> Project:
    project = await get_owned_project(db, user.id, project_id)
    if project is None:
        raise AppError("NOT_FOUND", "资源不存在或无权访问", 404)
    return project
