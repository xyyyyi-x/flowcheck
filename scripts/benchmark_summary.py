#!/usr/bin/env python3
"""在隔离 test 库创建 1 万条合成 run，记录统计/列表查询计划与耗时。

只允许连接名为 test 的数据库；结束后删除本脚本创建的合成数据。
"""

from __future__ import annotations

import io
import os
import time
import uuid
from datetime import UTC, datetime, timedelta

import psycopg
from psycopg.conninfo import conninfo_to_dict

COUNT = 10000


def database_url() -> str:
    url = os.environ.get("APP_TEST_DATABASE_URL")
    if not url:
        raise SystemExit("需要 APP_TEST_DATABASE_URL")
    info = conninfo_to_dict(url.replace("postgresql+psycopg://", "postgresql://"))
    if info.get("dbname") != "test":
        raise SystemExit("只允许在名为 test 的数据库运行")
    return url.replace("postgresql+psycopg://", "postgresql://")


def main() -> int:
    url = database_url()
    user_id, project_id, case_id, environment_id = (uuid.uuid4() for _ in range(4))
    now = datetime.now(UTC)
    statuses = ["passed"] * 6000 + ["failed"] * 2000 + ["error"] * 500 + [
        "interrupted"
    ] * 500 + ["queued"] * 500 + ["running"] * 500

    with psycopg.connect(url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO users (id, username, password_hash) VALUES (%s, %s, 'x')",
                (user_id, f"bench_{user_id.hex[:10]}"),
            )
            cursor.execute(
                "INSERT INTO projects (id, owner_id, name, description) VALUES (%s, %s, 'bench', '')",
                (project_id, user_id),
            )
            cursor.execute(
                "INSERT INTO cases (id, project_id, name, description, steps, version) "
                "VALUES (%s, %s, 'bench', '', '[]'::jsonb, 1)",
                (case_id, project_id),
            )
            cursor.execute(
                "INSERT INTO environments (id, project_id, name, base_url, config_ciphertext, version) "
                "VALUES (%s, %s, 'bench', 'http://demo-api:8001', 'cipher', 1)",
                (environment_id, project_id),
            )

            buffer = io.StringIO()
            for index, status in enumerate(statuses):
                created = now - timedelta(seconds=index)
                buffer.write(
                    "\t".join(
                        [
                            str(uuid.uuid4()),
                            str(project_id),
                            str(case_id),
                            str(environment_id),
                            "bench",
                            "1",
                            "bench",
                            "1",
                            status,
                            "cipher",
                            str(uuid.uuid4()),
                            "fingerprint",
                            created.isoformat(),
                            created.isoformat() if status in {"running", "passed", "failed", "error", "interrupted"} else "\\N",
                            created.isoformat() if status in {"passed", "failed", "error", "interrupted"} else "\\N",
                            created.isoformat(),
                            "\\N",
                            "\\N",
                        ]
                    )
                    + "\n"
                )
            buffer.seek(0)
            with cursor.copy(
                "COPY runs (id, project_id, case_id, environment_id, case_name, case_version, "
                "environment_name, environment_version, status, snapshot_ciphertext, "
                "idempotency_key, request_fingerprint, created_at, started_at, finished_at, "
                "deadline_at, error_code, execution_token) FROM STDIN"
            ) as copy:
                copy.write(buffer.read())
        connection.commit()

        summary_sql = (
            "SELECT status, count(*) FROM runs WHERE project_id = %s GROUP BY status"
        )
        list_sql = (
            "SELECT id, case_name, status, created_at FROM runs WHERE project_id = %s "
            "ORDER BY created_at DESC, id DESC LIMIT 20 OFFSET 0"
        )
        with connection.cursor() as cursor:
            cursor.execute("EXPLAIN (ANALYZE, BUFFERS) " + summary_sql, (project_id,))
            print("SUMMARY PLAN:")
            for row in cursor.fetchall():
                print("  " + row[0])
            cursor.execute("EXPLAIN (ANALYZE, BUFFERS) " + list_sql, (project_id,))
            print("LIST PLAN:")
            for row in cursor.fetchall():
                print("  " + row[0])

            start = time.perf_counter()
            for _ in range(20):
                cursor.execute(summary_sql, (project_id,))
                cursor.fetchall()
            summary_ms = (time.perf_counter() - start) / 20 * 1000
            start = time.perf_counter()
            for _ in range(20):
                cursor.execute(list_sql, (project_id,))
                cursor.fetchall()
            list_ms = (time.perf_counter() - start) / 20 * 1000
            cursor.execute(
                "SELECT count(*) FROM runs WHERE project_id = %s", (project_id,)
            )
            total = cursor.fetchone()[0]
        print(f"synthetic_runs={total}")
        print(f"summary_avg_ms={summary_ms:.2f}")
        print(f"list_page_avg_ms={list_ms:.2f}")

        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM runs WHERE project_id = %s", (project_id,))
            cursor.execute("DELETE FROM environments WHERE id = %s", (environment_id,))
            cursor.execute("DELETE FROM cases WHERE id = %s", (case_id,))
            cursor.execute("DELETE FROM projects WHERE id = %s", (project_id,))
            cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
        connection.commit()
        print("cleanup_done=1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
