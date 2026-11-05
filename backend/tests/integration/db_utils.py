"""集成测试数据库工具；所有操作只允许连接显式的 test 库。"""

from __future__ import annotations

import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy.engine import make_url


def sync_database_url() -> str:
    url = os.environ.get("APP_TEST_DATABASE_URL")
    if not url:
        raise RuntimeError(
            "集成测试必须设置 APP_TEST_DATABASE_URL，例如 "
            "postgresql+psycopg://test:test@127.0.0.1:55432/test"
        )
    database = make_url(url).database
    if database != "test":
        raise RuntimeError("集成测试只能连接名为 test 的数据库")
    return url


def alembic_config() -> Config:
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", sync_database_url())
    return config


def upgrade_to_head() -> None:
    command.upgrade(alembic_config(), "head")
