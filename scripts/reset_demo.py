#!/usr/bin/env python3
"""清空 Demo 服务的文章数据；不触碰平台 PostgreSQL。"""

from __future__ import annotations

import argparse
import subprocess

from demo_common import PROJECT_ROOT


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm", action="store_true", help="确认只清理 Demo 文章")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--project-name", default="arp-dev")
    args = parser.parse_args()
    if not args.confirm:
        print("拒绝执行：需要 --confirm；该操作只清空 Demo SQLite 文章，不影响平台数据库。")
        return 2
    command = [
        "docker",
        "compose",
        "--project-name",
        args.project_name,
        "--env-file",
        args.env_file,
        "exec",
        "-T",
        "demo-api",
        "python",
        "-m",
        "app.reset",
        "--confirm",
    ]
    result = subprocess.run(command, cwd=PROJECT_ROOT, check=False)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
