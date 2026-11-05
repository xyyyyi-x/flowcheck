#!/usr/bin/env python3
"""对运行中的 Compose 栈做真实 smoke：健康检查 + 执行五步用例并等待终态。"""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
import uuid

from demo_common import api_base, load_env, request, require_env

PROJECT_NAME = "文章回归 Demo"
ENVIRONMENT_NAME = "Compose Demo"
CASE_NAME = "文章回归五步"
TERMINAL = {"passed", "failed", "error", "interrupted"}


def find_by_name(base: str, token: str, path: str, name: str) -> dict | None:
    status, payload = request("GET", f"{base}{path}?page=1&page_size=100", token=token)
    if status != 200 or not isinstance(payload, dict):
        return None
    return next((item for item in payload.get("items", []) if item.get("name") == name), None)


def submit_run(base: str, token: str, project_id: str, case_id: str, environment_id: str) -> dict:
    body = json.dumps({"case_id": case_id, "environment_id": environment_id}).encode("utf-8")
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
        return json.loads(response.read())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--timeout", type=float, default=90.0)
    args = parser.parse_args()
    env = load_env(args.env_file)
    require_env(env, "PLATFORM_DEMO_USERNAME", "PLATFORM_DEMO_PASSWORD")
    base = api_base(env)

    status, _ = request(
        "GET", f"http://127.0.0.1:{env.get('API_PORT', '8000')}/api/v1/health/live"
    )
    if status != 200:
        print(f"健康检查失败（HTTP {status}）")
        return 1

    status, payload = request(
        "POST",
        f"{base}/auth/login",
        {
            "username": env["PLATFORM_DEMO_USERNAME"],
            "password": env["PLATFORM_DEMO_PASSWORD"],
        },
    )
    if status != 200 or not isinstance(payload, dict):
        print(f"登录失败（HTTP {status}）；请先运行 seed_demo.py")
        return 1
    token = payload["access_token"]

    project = find_by_name(base, token, "/projects", PROJECT_NAME)
    if project is None:
        print("未找到演示项目；请先运行 seed_demo.py")
        return 1
    environment = find_by_name(
        base, token, f"/projects/{project['id']}/environments", ENVIRONMENT_NAME
    )
    case = find_by_name(base, token, f"/projects/{project['id']}/cases", CASE_NAME)
    if environment is None or case is None:
        print("未找到演示环境或用例；请先运行 seed_demo.py")
        return 1

    try:
        created = submit_run(
            base, token, project["id"], case["id"], environment["id"]
        )
    except urllib.error.HTTPError as error:
        print(f"提交运行失败（HTTP {error.code}）")
        return 1
    run_id = created["run_id"]
    print(f"run_id={run_id} status={created['status']}")

    deadline = time.monotonic() + args.timeout
    while time.monotonic() < deadline:
        status, report = request("GET", f"{base}/runs/{run_id}", token=token)
        if status != 200 or not isinstance(report, dict):
            print(f"读取报告失败（HTTP {status}）")
            return 1
        if report["status"] in TERMINAL:
            print(f"run_status={report['status']} error_code={report['error_code']}")
            for step in report["steps"]:
                suffix = f" ({step['error_code']})" if step["error_code"] else ""
                print(f"  step {step['position']} {step['name']}: {step['status']}{suffix}")
            return 0 if report["status"] == "passed" else 1
        time.sleep(1)
    print("等待运行终态超时")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
