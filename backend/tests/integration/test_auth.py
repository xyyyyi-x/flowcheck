"""注册、登录、JWT 与认证边界测试。"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from httpx import AsyncClient

from app.core.security import decode_access_token, issue_access_token


async def register(client: AsyncClient, username: str = "Alice", password: str = "password-123"):
    return await client.post(
        "/api/v1/auth/register", json={"username": username, "password": password}
    )


async def login(client: AsyncClient, username: str = "alice", password: str = "password-123"):
    return await client.post(
        "/api/v1/auth/login", json={"username": username, "password": password}
    )


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_register_returns_safe_user(api_client: AsyncClient) -> None:
    response = await register(api_client)
    assert response.status_code == 201
    body = response.json()
    assert body["username"] == "alice"
    assert uuid.UUID(body["id"])
    assert "password" not in response.text
    assert "hash" not in response.text


async def test_duplicate_username_is_case_insensitive(api_client: AsyncClient) -> None:
    assert (await register(api_client, "Alice")).status_code == 201
    response = await register(api_client, "alice")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CONFLICT"


async def test_invalid_registration_fields_are_422(api_client: AsyncClient) -> None:
    assert (await register(api_client, "ab")).status_code == 422
    assert (await register(api_client, "bad name")).status_code == 422
    assert (await register(api_client, "valid_name", "short")).status_code == 422
    assert (await register(api_client, "valid_name2", "x" * 129)).status_code == 422


async def test_login_success_returns_bearer_token(api_client: AsyncClient) -> None:
    await register(api_client)
    response = await login(api_client)
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 1800
    assert isinstance(decode_access_token(body["access_token"]), uuid.UUID)


async def test_wrong_password_and_unknown_user_are_401(api_client: AsyncClient) -> None:
    await register(api_client)
    wrong = await login(api_client, password="wrong-password")
    unknown = await login(api_client, username="nobody")
    assert wrong.status_code == 401
    assert unknown.status_code == 401
    assert "wrong-password" not in wrong.text
    assert wrong.json()["error"]["code"] == "UNAUTHORIZED"


async def test_me_requires_valid_token(api_client: AsyncClient) -> None:
    await register(api_client)
    token = (await login(api_client)).json()["access_token"]
    ok = await api_client.get("/api/v1/auth/me", headers=bearer(token))
    missing = await api_client.get("/api/v1/auth/me")
    forged = await api_client.get("/api/v1/auth/me", headers=bearer("not-a-real-token"))
    assert ok.status_code == 200
    assert ok.json()["username"] == "alice"
    assert missing.status_code == 401
    assert forged.status_code == 401


async def test_expired_and_wrongly_signed_tokens_are_401(
    api_client: AsyncClient,
) -> None:
    await register(api_client)
    token = (await login(api_client)).json()["access_token"]
    user_id = decode_access_token(token)
    expired = issue_access_token(user_id, datetime.now(UTC) - timedelta(minutes=31))
    response = await api_client.get("/api/v1/auth/me", headers=bearer(expired))
    wrong_signature = await api_client.get("/api/v1/auth/me", headers=bearer(token + "x"))
    assert response.status_code == 401
    assert wrong_signature.status_code == 401
