"""seed/smoke 共用的标准库 HTTP 与 .env 读取工具。"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def load_env(path: str) -> dict[str, str]:
    file = Path(path)
    if not file.is_absolute():
        file = PROJECT_ROOT / file
    values: dict[str, str] = {}
    for raw_line in file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def api_base(env: dict[str, str]) -> str:
    return f"http://127.0.0.1:{env.get('API_PORT', '8000')}/api/v1"


def request(
    method: str,
    url: str,
    body: dict | None = None,
    token: str | None = None,
    timeout: float = 15.0,
) -> tuple[int, dict | list | None]:
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read()
            return response.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as error:
        raw = error.read()
        try:
            payload = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            payload = None
        return error.code, payload


def require_env(env: dict[str, str], *keys: str) -> None:
    missing = [key for key in keys if not env.get(key)]
    if missing:
        raise SystemExit(f"缺少环境变量: {', '.join(missing)}；请先运行 init_env.py")
