"""Fernet JSON 加解密单元测试。"""

from __future__ import annotations

import pytest

from app.core.crypto import decrypt_json, encrypt_json
from app.core.errors import AppError

FERNET_KEY = "u5nM7Qp0jXk2r8T4wY6zA1bC3dE5fG7hI9jK0lM2nO4="


def test_roundtrip_preserves_nested_unicode_and_scalars() -> None:
    payload = {
        "variables": [
            {"name": "用户名", "value": "秘密值", "is_secret": True},
            {"name": "count", "value": 3, "is_secret": False},
            {"name": "flag", "value": True, "is_secret": False},
            {"name": "empty", "value": None, "is_secret": False},
        ]
    }
    token = encrypt_json(payload, FERNET_KEY)
    assert decrypt_json(token, FERNET_KEY) == payload


def test_ciphertext_does_not_contain_plaintext() -> None:
    token = encrypt_json({"password": "super-secret-value"}, FERNET_KEY)
    assert "super-secret-value" not in token
    assert token != "super-secret-value"


def test_wrong_key_cannot_decrypt() -> None:
    token = encrypt_json({"password": "value"}, FERNET_KEY)
    other_key = "M2VtYW5vSGVyZWtleUZvckRpZmZlcmVudFVzZTEyMzQ1Njc4OTA="
    with pytest.raises(AppError) as error:
        decrypt_json(token, other_key)
    assert error.value.code == "INTERNAL_ERROR"


def test_invalid_token_is_internal_error() -> None:
    with pytest.raises(AppError):
        decrypt_json("not-a-token", FERNET_KEY)
