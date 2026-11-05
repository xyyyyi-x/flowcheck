"""项目 CRUD；所有读取都按 owner 过滤。"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Project
from app.modules.projects.schemas import ProjectCreate, ProjectUpdate


async def create_project(db: AsyncSession, owner_id: uuid.UUID, payload: ProjectCreate) -> Project:
    project = Project(owner_id=owner_id, name=payload.name, description=payload.description)
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


async def list_projects(
    db: AsyncSession, owner_id: uuid.UUID, page: int, page_size: int
) -> tuple[list[Project], int]:
    base = select(Project).where(Project.owner_id == owner_id)
    total = await db.scalar(
        select(func.count()).select_from(Project).where(Project.owner_id == owner_id)
    )
    result = await db.scalars(
        base.order_by(Project.created_at.desc(), Project.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(result), int(total or 0)


async def get_owned_project(
    db: AsyncSession, owner_id: uuid.UUID, project_id: uuid.UUID
) -> Project | None:
    return await db.scalar(
        select(Project).where(Project.id == project_id, Project.owner_id == owner_id)
    )


async def update_project(db: AsyncSession, project: Project, payload: ProjectUpdate) -> Project:
    project.name = payload.name
    project.description = payload.description
    await db.commit()
    await db.refresh(project)
    return project
