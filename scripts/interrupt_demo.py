#!/usr/bin/env python3
"""中断演示：在写请求进行中强杀 arp-e2e worker，等待 reconcile 终结。

只允许对显式的 --project-name 执行 kill；必须带 --confirm。
"""

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
TERMINAL = {"passed", "failed", "error", "interrupted"}


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
    parser.add_argument("--confirm", action="store_true", help="确认只 kill 该 Compose 项目的 worker")
    parser.add_argument("--timeout", type=float, default=400.0)
    args = parser.parse_args()
    if not args.confirm:
        print("拒绝执行：需要 --confirm，并确认 project-name 正确。")
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
        print("平台演示账号登录失败；请先 seed。")
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
        print("缺少演示项目/环境/用例；请先 seed。")
        return 1

    run_id = submit(base, token, project["id"], case["id"], environment["id"])
    print(f"run_id={run_id} 已提交，等待第 2 步进入 running …", flush=True)
    deadline = time.monotonic() + 90
    started = False
    while time.monotonic() < deadline:
        current = report(base, token, run_id)
        steps = {step["position"]: step["status"] for step in current["steps"]}
        if steps.get(2) == "running":
            started = True
            break
        if current["status"] in TERMINAL:
            print(f"运行过早结束：{current['status']}")
            return 1
        time.sleep(1)
    if not started:
        print("等待第 2 步 running 超时")
        return 1

    time.sleep(2)
    kill_at = time.monotonic()
    print(
        f"确认 Compose 项目 {args.project_name}，强杀 worker …", flush=True
    )
    result = subprocess.run(
        [
            "docker",
            "compose",
            "--project-name",
            args.project_name,
            "--env-file",
            args.env_file,
            "kill",
            "worker",
        ],
        cwd=PROJECT_ROOT,
        check=False,
    )
    if result.returncode != 0:
        print("kill worker 失败")
        return 1

    while time.monotonic() - kill_at < args.timeout:
        current = report(base, token, run_id)
        if current["status"] in TERMINAL:
            elapsed = time.monotonic() - kill_at
            print(f"reconcile 完成，实际等待 {elapsed:.1f}s")
            print(f"run_status={current['status']} error_code={current['error_code']}")
            for step in current["steps"]:
                suffix = f" ({step['error_code']})" if step["error_code"] else ""
                print(f"  step {step['position']} {step['name']}: {step['status']}{suffix}")
            return 0 if current["status"] == "interrupted" else 1
        time.sleep(5)
    print("等待 reconcile 超时")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
