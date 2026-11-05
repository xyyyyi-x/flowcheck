"""Demo API 契约测试。"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app, init_database


@pytest.fixture(autouse=True)
def demo_environment(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("DEMO_DB_PATH", str(tmp_path / "demo.db"))
    monkeypatch.setenv("DEMO_USERNAME", "demo")
    monkeypatch.setenv("DEMO_PASSWORD", "only-for-local-demo")
    monkeypatch.delenv("DEMO_FAULT_MODE", raising=False)
    monkeypatch.delenv("DEMO_WRITE_DELAY_S", raising=False)
    init_database()
    with TestClient(app) as client:
        yield client


def login(client: TestClient) -> str:
    response = client.post(
        "/auth/login",
        json={"username": "demo", "password": "only-for-local-demo"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_login_success_and_failure(demo_environment: TestClient) -> None:
    token = login(demo_environment)
    assert token
    bad = demo_environment.post(
        "/auth/login", json={"username": "demo", "password": "wrong"}
    )
    assert bad.status_code == 401
    assert "only-for-local-demo" not in bad.text


def test_article_crud_contract(demo_environment: TestClient) -> None:
    client = demo_environment
    token = login(client)
    assert client.post("/articles", json={"title": "x"}).status_code == 401

    created = client.post(
        "/articles", headers=auth(token), json={"title": "smoke-1", "content": "hello"}
    )
    assert created.status_code == 201
    article = created.json()
    assert article["title"] == "smoke-1"
    article_id = article["id"]

    fetched = client.get(f"/articles/{article_id}", headers=auth(token))
    assert fetched.status_code == 200
    assert fetched.json()["content"] == "hello"

    deleted = client.delete(f"/articles/{article_id}", headers=auth(token))
    assert deleted.status_code == 204
    assert client.get(f"/articles/{article_id}", headers=auth(token)).status_code == 404


def test_title_mismatch_fault_only_changes_read(
    demo_environment: TestClient, monkeypatch
) -> None:
    client = demo_environment
    token = login(client)
    article = client.post(
        "/articles", headers=auth(token), json={"title": "expected-title"}
    ).json()
    monkeypatch.setenv("DEMO_FAULT_MODE", "title_mismatch")
    fetched = client.get(f"/articles/{article['id']}", headers=auth(token))
    assert fetched.status_code == 200
    assert fetched.json()["title"] != "expected-title"
    assert fetched.json()["title"] == "fault-injected-title"


def test_restart_keeps_rows_on_disk(demo_environment: TestClient, tmp_path: Path) -> None:
    client = demo_environment
    token = login(client)
    article_id = client.post(
        "/articles", headers=auth(token), json={"title": "persist"}
    ).json()["id"]
    assert (tmp_path / "demo.db").exists()

    with TestClient(app) as restarted:
        response = restarted.get(f"/articles/{article_id}", headers=auth(token))
    assert response.status_code == 200
    assert response.json()["title"] == "persist"
