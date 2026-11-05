#!/usr/bin/env python3
"""Redis 短时停机演示：提交仍 queued，恢复后 dispatcher 补发并执行。"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
import urllib.request
import uuid

from demo_common import PROJECT_ROOT, api_base, load_env, request, require_env

PROJECT_NAME = "文章回归 Demo"
ENVIRONMENT_NAME = "Compose Demo"
CASE_NAME = "文章回归五步"


def compose(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["docker", "compose", *args],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def find_by_name(base: str, token: str, path: str, name: str) -> dict | None:
    status, payload = request("GET", f"{base}{path}?page=1&page_size=100", token=token)
    if status != 200 or not isinstance(payload, dict):
        return None
    return next((item for item in payload.get("items", []) if item.get("name") == name), None)


def submit(base: str, token: str, project_id: str, case_id: str, env_id: str) -> str:
    body = json.dumps({"case_id": case_id, "environment_id": env_id}).encode()
    req = urllib.request.Request(
        f"{base}/projects/{project_id}/runs",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
            "Idempotency-Key": str(uuid.uuid4()),
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as response:
        return json.loads(response.read())["run_id"]


def report(base: str, token: str, run_id: str) -> dict:
    status, payload = request("GET", f"{base}/runs/{run_id}", token=token)
    if status != 200 or not isinstance(payload, dict):
        raise SystemExit(f"读取报告失败（HTTP {status}）")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", default=".env.e2e")
    parser.add_argument("--project-name", default="arp-e2e")
    parser.add_argument("--confirm", action="store_true", help="确认只停止该项目的 redis")
    parser.add_argument("--timeout", type=float, default=150.0)
    args = parser.parse_args()
    if not args.confirm:
        print("拒绝执行：需要 --confirm")
        return 2
    env = load_env(args.env_file)
    require_env(env, "PLATFORM_DEMO_USERNAME", "PLATFORM_DEMO_PASSWORD")
    base = api_base(env)
    status, payload = request(
        "POST",
        f"{base}/auth/login",
        {
            "username": env["PLATFORM_DEMO_USERNAME"],
            "password": env["PLATFORM_DEMO_PASSWORD"],
        },
    )
    if status != 200 or not isinstance(payload, dict):
        print("登录失败；请先 seed。")
        return 1
    token = payload["access_token"]
    project = find_by_name(base, token, "/projects", PROJECT_NAME)
    environment = (
        find_by_name(base, token, f"/projects/{project['id']}/environments", ENVIRONMENT_NAME)
        if project
        else None
    )
    case = find_by_name(base, token, f"/projects/{project['id']}/cases", CASE_NAME) if project else None
    if project is None or environment is None or case is None:
        print("缺少演示数据；请先 seed。")
        return 1

    print(f"停止 {args.project_name} 的 redis …", flush=True)
    stopped = compose(
        ["--project-name", args.project_name, "--env-file", args.env_file, "stop", "redis"]
    )
    if stopped.returncode != 0:
        print(stopped.stderr)
        return 1

    try:
        run_id = submit(base, token, project["id"], case["id"], environment["id"])
        print(f"run_id={run_id} 已提交（Redis 停机中）", flush=True)
        first = report(base, token, run_id)
        print(f"after_submit_status={first['status']}")
        time.sleep(6)
        still = report(base, token, run_id)
        print(f"after_6s_status={still['status']}")
        queries = compose(
            [
                "--project-name",
                args.project_name,
                "--env-file",
                args.env_file,
                "exec",
                "-T",
                "db",
                "sh",
                "-c",
                'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -t -A -c '
                '"select attempt_count,coalesce(last_error_code,\'\') from run_outbox '
                f"where run_id='{run_id}'\"",
            ]
        )
        print("outbox(attempt_count,last_error_code)=" + queries.stdout.strip())
    finally:
        print("恢复 redis …", flush=True)
        compose(
            ["--project-name", args.project_name, "--env-file", args.env_file, "start", "redis"]
        )

    deadline = time.monotonic() + args.timeout
    while time.monotonic() < deadline:
        current = report(base, token, run_id)
        if current["status"] in {"passed", "failed", "error", "interrupted"}:
            print(f"run_status={current['status']} error_code={current['error_code']}")
            for step in current["steps"]:
                suffix = f" ({step['error_code']})" if step["error_code"] else ""
                print(f"  step {step['position']} {step['name']}: {step['status']}{suffix}")
            return 0 if current["status"] == "passed" else 1
        time.sleep(2)
    print("等待补发执行超时")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
