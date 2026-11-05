"""独立的文章 Demo API，仅用于被回归平台测试。"""

from __future__ import annotations

import hashlib
import os
import sqlite3
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, contextmanager
from datetime import UTC, datetime

from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

WRITE_DELAY_MAX = 30.0


def _database_path() -> str:
    return os.environ.get("DEMO_DB_PATH", "/data/demo.db")


def _credentials() -> tuple[str, str]:
    return (
        os.environ.get("DEMO_USERNAME", "demo"),
        os.environ.get("DEMO_PASSWORD", "demo-password"),
    )


def _expected_token() -> str:
    username, password = _credentials()
    digest = hashlib.sha256(f"{username}:{password}:arp-demo".encode()).hexdigest()
    return digest


def _fault_mode() -> str:
    return os.environ.get("DEMO_FAULT_MODE", "")


def _write_delay() -> float:
    try:
        value = float(os.environ.get("DEMO_WRITE_DELAY_S", "0"))
    except ValueError:
        return 0.0
    return max(0.0, min(value, WRITE_DELAY_MAX))


@contextmanager
def database():
    connection = sqlite3.connect(_database_path(), timeout=10)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def init_database() -> None:
    directory = os.path.dirname(_database_path())
    if directory:
        os.makedirs(directory, exist_ok=True)
    with database() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS articles (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    init_database()
    yield


app = FastAPI(title="Articles Demo API", version="1.0.0", lifespan=lifespan)


def require_token(authorization: str | None = Header(default=None)) -> None:
    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="unauthorized")
    token = authorization.removeprefix("Bearer ").strip()
    if token != _expected_token():
        raise HTTPException(status_code=401, detail="unauthorized")


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str
    password: str


class ArticleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(default="", max_length=10000)


def _article(connection: sqlite3.Connection, article_id: str) -> dict | None:
    row = connection.execute(
        "SELECT id, title, content FROM articles WHERE id = ?", (article_id,)
    ).fetchone()
    return dict(row) if row else None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/auth/login")
def login(payload: LoginRequest) -> dict[str, str]:
    username, password = _credentials()
    if payload.username != username or payload.password != password:
        raise HTTPException(status_code=401, detail="invalid credentials")
    return {"access_token": _expected_token(), "token_type": "bearer"}


@app.post("/articles", status_code=status.HTTP_201_CREATED)
def create_article(
    payload: ArticleCreate, _: None = Depends(require_token)
) -> dict[str, str]:
    article_id = str(uuid.uuid4())
    created_at = datetime.now(UTC).isoformat()
    with database() as connection:
        connection.execute(
            "INSERT INTO articles (id, title, content, created_at) VALUES (?, ?, ?, ?)",
            (article_id, payload.title, payload.content, created_at),
        )
    delay = _write_delay()
    if delay > 0:
        time.sleep(delay)
    return {"id": article_id, "title": payload.title, "content": payload.content}


@app.get("/articles/{article_id}")
def read_article(article_id: str, _: None = Depends(require_token)) -> dict[str, str]:
    with database() as connection:
        article = _article(connection, article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="not found")
    if _fault_mode() == "title_mismatch":
        article["title"] = "fault-injected-title"
    return article


@app.delete("/articles/{article_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_article(article_id: str, _: None = Depends(require_token)) -> None:
    with database() as connection:
        cursor = connection.execute("DELETE FROM articles WHERE id = ?", (article_id,))
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="not found")
