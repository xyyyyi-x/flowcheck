"""导入与接口定义响应模型。"""

from __future__ import annotations

import uuid
from typing import Any

from app.core.schemas import ApiModel, UtcDatetime


class ImportWarningRead(ApiModel):
    path: str
    message: str


class ImportResult(ApiModel):
    created_count: int
    skipped_count: int
    warnings: list[ImportWarningRead]


class ApiDefinitionRead(ApiModel):
    id: uuid.UUID
    project_id: uuid.UUID
    method: str
    path: str
    summary: str
    parameters: list[dict[str, Any]]
    request_body_schema: dict[str, Any] | None
    created_at: UtcDatetime
