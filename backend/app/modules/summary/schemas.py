"""项目统计响应。"""

from __future__ import annotations

from app.core.schemas import ApiModel, UtcDatetime


class ProjectSummary(ApiModel):
    total_runs: int
    passed_runs: int
    failed_runs: int
    error_runs: int
    interrupted_runs: int
    active_runs: int
    pass_rate: float | None
    computed_at: UtcDatetime
    cache_hit: bool
