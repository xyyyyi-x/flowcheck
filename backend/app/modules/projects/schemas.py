"""项目请求/响应模型。"""

from __future__ import annotations

import uuid
from typing import Annotated

from pydantic import StringConstraints

from app.core.schemas import ApiModel, UtcDatetime

ProjectName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
ProjectDescription = Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]


class ProjectCreate(ApiModel):
    name: ProjectName
    description: ProjectDescription = ""


class ProjectUpdate(ApiModel):
    name: ProjectName
    description: ProjectDescription = ""


class ProjectRead(ApiModel):
    id: uuid.UUID
    owner_id: uuid.UUID
    name: str
    description: str
    created_at: UtcDatetime
    updated_at: UtcDatetime
