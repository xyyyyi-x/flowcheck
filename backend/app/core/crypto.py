"""Fernet 加密的 JSON 序列化。"""

from __future__ import annotations

import json
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from app.core.errors import AppError

JsonValue = Any


def encrypt_json(value: JsonValue, key: str) -> str:
    payload = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode(
        "utf-8"
    )
    return Fernet(key.encode("utf-8")).encrypt(payload).decode("ascii")


def decrypt_json(token: str, key: str) -> JsonValue:
    try:
        plaintext = Fernet(key.encode("utf-8")).decrypt(token.encode("ascii"))
    except (InvalidToken, ValueError, TypeError) as exc:
        raise AppError("INTERNAL_ERROR", "加密配置无法解密", 500) from exc
    return json.loads(plaintext.decode("utf-8"))
