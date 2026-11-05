"""Celery 应用配置：JSON、无结果后端、无自动重试。"""

from __future__ import annotations

from celery import Celery

from app.core.config import Settings

_settings = Settings()

celery_app = Celery(
    "api_regression_platform",
    broker=_settings.app_redis_broker_url,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_ignore_result=True,
    task_acks_late=False,
    worker_prefetch_multiplier=1,
    worker_concurrency=2,
    task_reject_on_worker_lost=False,
    broker_connection_retry_on_startup=True,
    # 发布侧不无限重试；socket 连接/读写与重试上限都压到 3 秒级。
    task_publish_retry=False,
    broker_transport_options={
        "socket_connect_timeout": 3,
        "socket_timeout": 3,
        "retry_policy": {"max_retries": 0},
    },
    task_soft_time_limit=310,
    task_time_limit=330,
)
