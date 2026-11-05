"""Worker/dispatcher 进程的同步数据库会话；引擎在各自进程内懒创建。"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


def build_sync_engine(database_url: str) -> Engine:
    return create_engine(database_url, pool_pre_ping=True)


def build_sync_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)


@contextmanager
def session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    """短事务：成功提交，异常回滚，最后关闭连接。"""
    session = factory()
    try:
        yield session
        session.commit()
    except BaseException:
        session.rollback()
        raise
    finally:
        session.close()
