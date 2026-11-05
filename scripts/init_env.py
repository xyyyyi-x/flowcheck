#!/usr/bin/env python3
"""生成 .env 或 .env.e2e。只用标准库，不覆盖已有文件，不打印秘密值。"""

from __future__ import annotations

import argparse
import base64
import secrets
import string
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_PORTS = {"web": 8080, "api": 8000, "demo": 8001}
E2E_PORTS = {"web": 8088, "api": 8008, "demo": 8009}


def random_password(length: int = 24) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def make_env(e2e: bool) -> str:
    ports = E2E_PORTS if e2e else DEFAULT_PORTS
    db_password = random_password(28)
    jwt_secret = secrets.token_urlsafe(48)
    encryption_key = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii")
    demo_password = random_password(24)
    platform_demo_password = random_password(24)
    env_name = "e2e" if e2e else "development"
    lines = [
        f"# 由 scripts/init_env.py 生成的 {env_name} 配置（{Path(__file__).name}）。不要提交本文件。",
        "POSTGRES_DB=arp",
        "POSTGRES_USER=arp",
        f"POSTGRES_PASSWORD={db_password}",
        f"APP_JWT_SECRET={jwt_secret}",
        f"APP_ENCRYPTION_KEY={encryption_key}",
        f"APP_DATABASE_URL=postgresql+asyncpg://arp:{db_password}@db:5432/arp",
        f"APP_SYNC_DATABASE_URL=postgresql+psycopg://arp:{db_password}@db:5432/arp",
        "APP_REDIS_BROKER_URL=redis://redis:6379/0",
        "APP_REDIS_CACHE_URL=redis://redis:6379/1",
        "TARGET_ORIGINS=http://demo-api:8001",
        "CORS_ORIGINS=",
        f"WEB_PORT={ports['web']}",
        f"API_PORT={ports['api']}",
        f"DEMO_PORT={ports['demo']}",
        "DEMO_USERNAME=demo",
        f"DEMO_PASSWORD={demo_password}",
        "PLATFORM_DEMO_USERNAME=demo_owner",
        f"PLATFORM_DEMO_PASSWORD={platform_demo_password}",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--e2e",
        action="store_true",
        help="生成独立 E2E 环境 .env.e2e（端口 8088/8008/8009）",
    )
    args = parser.parse_args()
    target = PROJECT_ROOT / (".env.e2e" if args.e2e else ".env")
    if target.exists():
        print(f"拒绝覆盖已存在的 {target.name}；如需重建请自行备份并删除。", file=sys.stderr)
        return 1
    target.write_text(make_env(args.e2e), encoding="utf-8")
    print(f"已生成 {target.name}（秘密值未显示）。接下来运行: docker compose up --build -d")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
