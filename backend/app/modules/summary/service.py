"""项目统计：SQL GROUP BY + Redis 30 秒缓存（失败回退数据库）。"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Run
from app.modules.summary.schemas import ProjectSummary

CACHE_TTL = 30


def cache_key(project_id: uuid.UUID) -> str:
    return f"summary:v1:{project_id}"


class SummaryCache:
    def __init__(self, url: str) -> None:
        self._redis = Redis.from_url(url, decode_responses=True, socket_timeout=1)

    async def get(self, key: str) -> dict | None:
        try:
            raw = await self._redis.get(key)
        except (RedisError, OSError):
            return None
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    async def set(self, key: str, value: dict, ttl: int = CACHE_TTL) -> None:
        try:
            await self._redis.set(key, json.dumps(value, ensure_ascii=False), ex=ttl)
        except (RedisError, OSError):
            return None

    async def delete(self, key: str) -> None:
        try:
            await self._redis.delete(key)
        except (RedisError, OSError):
            return None

    async def close(self) -> None:
        await self._redis.aclose()


def _summary_from_row_counts(
    counts: dict[str, int], computed_at: datetime, cache_hit: bool
) -> ProjectSummary:
    passed = counts.get("passed", 0)
    failed = counts.get("failed", 0)
    denominator = passed + failed
    pass_rate = (passed / denominator) if denominator else None
    return ProjectSummary(
        total_runs=sum(counts.values()),
        passed_runs=passed,
        failed_runs=failed,
        error_runs=counts.get("error", 0),
        interrupted_runs=counts.get("interrupted", 0),
        active_runs=counts.get("queued", 0) + counts.get("running", 0),
        pass_rate=pass_rate,
        computed_at=computed_at,
        cache_hit=cache_hit,
    )


async def get_project_summary(
    db: AsyncSession, project_id: uuid.UUID, cache: SummaryCache
) -> ProjectSummary:
    key = cache_key(project_id)
    cached = await cache.get(key)
    if cached is not None:
        try:
            return ProjectSummary(
                **{
                    **cached,
                    "cache_hit": True,
                }
            )
        except Exception:
            await cache.delete(key)

    rows = await db.execute(
        select(Run.status, func.count()).where(Run.project_id == project_id).group_by(Run.status)
    )
    counts = {status: int(amount) for status, amount in rows.all()}
    computed_at = datetime.now(UTC)
    summary = _summary_from_row_counts(counts, computed_at, cache_hit=False)
    payload = summary.model_dump(mode="json")
    payload.pop("cache_hit", None)
    payload["computed_at"] = computed_at.isoformat().replace("+00:00", "Z")
    await cache.set(key, payload)
    return summary
