"""运行提交与报告模型（报告字段在 T11 扩展）。"""

from __future__ import annotations

import uuid
from typing import Any, Literal

from app.core.schemas import ApiModel, UtcDatetime


class RunCreate(ApiModel):
    case_id: uuid.UUID
    environment_id: uuid.UUID


class RunCreated(ApiModel):
    run_id: uuid.UUID
    status: str
    reused: bool


RunStatusFilter = Literal["queued", "running", "passed", "failed", "error", "interrupted"]


class StepCounts(ApiModel):
    total: int
    pending: int
    running: int
    passed: int
    failed: int
    error: int
    skipped: int


class StepResultRead(ApiModel):
    id: uuid.UUID
    position: int
    name: str
    status: str
    elapsed_ms: int | None
    request_safe: dict[str, Any] | None
    response_safe: dict[str, Any] | None
    assertions_safe: list[dict[str, Any]]
    extracts_safe: list[dict[str, Any]]
    error_code: str | None
    started_at: UtcDatetime | None
    finished_at: UtcDatetime | None


class RunSummary(ApiModel):
    id: uuid.UUID
    project_id: uuid.UUID
    case_id: uuid.UUID
    environment_id: uuid.UUID
    case_name: str
    case_version: int
    environment_name: str
    environment_version: int
    status: str
    created_at: UtcDatetime
    started_at: UtcDatetime | None
    finished_at: UtcDatetime | None
    error_code: str | None
    counts: StepCounts


class RunReport(RunSummary):
    steps: list[StepResultRead]
