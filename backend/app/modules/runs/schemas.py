"""运行提交与报告模型（报告字段在 T11 扩展）。"""

from __future__ import annotations

import uuid
from typing import Literal

from app.core.schemas import ApiModel


class RunCreate(ApiModel):
    case_id: uuid.UUID
    environment_id: uuid.UUID


class RunCreated(ApiModel):
    run_id: uuid.UUID
    status: str
    reused: bool


RunStatusFilter = Literal["queued", "running", "passed", "failed", "error", "interrupted"]
