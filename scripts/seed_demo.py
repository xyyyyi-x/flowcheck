#!/usr/bin/env python3
"""通过平台 HTTP API 创建演示项目、环境与五步用例（幂等，可重复执行）。"""

from __future__ import annotations

import argparse
import uuid

from demo_common import api_base, load_env, request, require_env

PROJECT_NAME = "文章回归 Demo"
ENVIRONMENT_NAME = "Compose Demo"
CASE_NAME = "文章回归五步"


def step(name: str, method: str, path: str, **extra) -> dict:
    payload = {
        "id": str(uuid.uuid4()),
        "name": name,
        "source_api_id": None,
        "request": {
            "method": method,
            "path": path,
            "path_params": extra.get("path_params", {}),
            "query": {},
            "headers": extra.get("headers", {}),
            "json_body": extra.get("json_body"),
            "timeout_s": 10,
        },
        "assertions": extra["assertions"],
        "extractors": extra.get("extractors", []),
        "omit_response_body": extra.get("omit_response_body", False),
    }
    return payload


def five_steps() -> list[dict]:
    auth = {"Authorization": "Bearer {{auth_token}}"}
    return [
        step(
            "1. 登录",
            "POST",
            "/auth/login",
            json_body={"username": "{{demo_username}}", "password": "{{demo_password}}"},
            assertions=[{"type": "status_code", "expected": 200}],
            extractors=[{"name": "auth_token", "selector": "$.access_token", "is_secret": True}],
            omit_response_body=True,
        ),
        step(
            "2. 创建文章",
            "POST",
            "/articles",
            headers=auth,
            json_body={"title": "smoke-{{run_id}}", "content": "hello"},
            assertions=[{"type": "status_code", "expected": 201}],
            extractors=[{"name": "article_id", "selector": "$.id", "is_secret": False}],
        ),
        step(
            "3. 查询文章",
            "GET",
            "/articles/{id}",
            headers=auth,
            path_params={"id": "{{article_id}}"},
            assertions=[
                {"type": "status_code", "expected": 200},
                {"type": "json_equals", "selector": "$.title", "expected": "smoke-{{run_id}}"},
            ],
        ),
        step(
            "4. 删除文章",
            "DELETE",
            "/articles/{id}",
            headers=auth,
            path_params={"id": "{{article_id}}"},
            assertions=[{"type": "status_code", "expected": 204}],
            omit_response_body=True,
        ),
        step(
            "5. 再查应 404",
            "GET",
            "/articles/{id}",
            headers=auth,
            path_params={"id": "{{article_id}}"},
            assertions=[{"type": "status_code", "expected": 404}],
            omit_response_body=True,
        ),
    ]


def find_by_name(base: str, token: str, path: str, name: str) -> dict | None:
    status, payload = request("GET", f"{base}{path}?page=1&page_size=100", token=token)
    if status != 200 or not isinstance(payload, dict):
        return None
    for item in payload.get("items", []):
        if item.get("name") == name:
            return item
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", default=".env")
    args = parser.parse_args()
    env = load_env(args.env_file)
    require_env(env, "PLATFORM_DEMO_USERNAME", "PLATFORM_DEMO_PASSWORD", "DEMO_PASSWORD")
    base = api_base(env)
    username = env["PLATFORM_DEMO_USERNAME"]
    password = env["PLATFORM_DEMO_PASSWORD"]

    status, _ = request(
        "POST", f"{base}/auth/register", {"username": username, "password": password}
    )
    if status not in (201, 409):
        print(f"注册平台演示用户失败（HTTP {status}）")
        return 1
    status, payload = request(
        "POST", f"{base}/auth/login", {"username": username, "password": password}
    )
    if status != 200 or not isinstance(payload, dict):
        print(f"平台演示用户登录失败（HTTP {status}）")
        return 1
    token = payload["access_token"]

    project = find_by_name(base, token, "/projects", PROJECT_NAME)
    if project is None:
        status, project = request(
            "POST",
            f"{base}/projects",
            {"name": PROJECT_NAME, "description": "Compose 演示：文章 CRUD 五步回归"},
            token=token,
        )
        if status != 201 or not isinstance(project, dict):
            print(f"创建项目失败（HTTP {status}）")
            return 1
    project_id = project["id"]

    environment = find_by_name(base, token, f"/projects/{project_id}/environments", ENVIRONMENT_NAME)
    if environment is None:
        status, environment = request(
            "POST",
            f"{base}/projects/{project_id}/environments",
            {
                "name": ENVIRONMENT_NAME,
                "base_url": env.get("TARGET_ORIGINS", "http://demo-api:8001").split(",")[0],
                "variables": [
                    {"name": "demo_username", "value": env.get("DEMO_USERNAME", "demo"), "is_secret": False},
                    {"name": "demo_password", "value": env["DEMO_PASSWORD"], "is_secret": True},
                ],
                "common_headers": [],
            },
            token=token,
        )
        if status != 201 or not isinstance(environment, dict):
            print(f"创建环境失败（HTTP {status}）")
            return 1

    case = find_by_name(base, token, f"/projects/{project_id}/cases", CASE_NAME)
    if case is None:
        status, case = request(
            "POST",
            f"{base}/projects/{project_id}/cases",
            {"name": CASE_NAME, "description": "登录→创建→查询→删除→再查 404", "steps": five_steps()},
            token=token,
        )
        if status != 201 or not isinstance(case, dict):
            print(f"创建用例失败（HTTP {status}）")
            return 1

    print(f"project_id={project_id}")
    print(f"environment_id={environment['id']}")
    print(f"case_id={case['id']}")
    print("seed 完成：五步用例已就绪。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
