"""清空 Demo 文章表；只影响被测 Demo 服务自己的 SQLite 数据。"""

from __future__ import annotations

import argparse
import os
import sqlite3


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm", action="store_true", help="确认清空 Demo 文章")
    args = parser.parse_args()
    if not args.confirm:
        print("拒绝执行：需要 --confirm", flush=True)
        return 2
    path = os.environ.get("DEMO_DB_PATH", "/data/demo.db")
    connection = sqlite3.connect(path)
    try:
        deleted = connection.execute("DELETE FROM articles").rowcount
        connection.commit()
    finally:
        connection.close()
    print(f"已清空 Demo 文章 {deleted} 条（仅 Demo SQLite）。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
