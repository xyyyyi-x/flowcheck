"""项目统计路由（P1）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.dependencies import get_settings
from app.db.async_session import get_async_session
from app.db.models import Project
from app.modules.projects.deps import require_owned_project
from app.modules.summary.schemas import ProjectSummary
from app.modules.summary.service import SummaryCache, get_project_summary

router = APIRouter(tags=["summary"])


@router.get("/projects/{project_id}/summary", response_model=ProjectSummary)
async def summary(
    project: Project = Depends(require_owned_project),
    db: AsyncSession = Depends(get_async_session),
    settings: Settings = Depends(get_settings),
) -> ProjectSummary:
    cache = SummaryCache(settings.app_redis_cache_url)
    try:
        return await get_project_summary(db, project.id, cache)
    finally:
        await cache.close()
