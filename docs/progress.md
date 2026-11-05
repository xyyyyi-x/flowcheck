# 开发进度

更新时间：2026-11-05（Asia/Shanghai）。
当前状态：T01 已通过验证；T02 进行中。
执行方式：用户后续通过Claude Code接DeepSeek实施。

| 任务 | 内容 | 状态 | 验证证据 |
|---|---|---|---|
| T01 | 工程/配置/健康接口 | 已完成 | 12 unit passed；Ruff/format/前端构建/compose config 通过 |
| T02 | 数据库/迁移/测试底座 | 未开始 | 无 |
| T03 | 认证/项目/owner | 未开始 | 无 |
| T04 | 环境加密/secret协议 | 未开始 | 无 |
| T05 | DSL/用例CRUD | 未开始 | 无 |
| T06 | OpenAPI导入 | 未开始 | 无 |
| T07 | 渲染/取值/断言 | 未开始 | 无 |
| T08 | HTTP/脱敏/执行器 | 未开始 | 无 |
| T09 | 快照/幂等提交 | 未开始 | 无 |
| T10 | Worker/outbox/中断恢复 | 未开始 | 无 |
| T11 | 报告/SSE | 未开始 | 无 |
| T12 | 前端账号/配置 | 未开始 | 无 |
| T13 | 前端用例/执行/报告 | 未开始 | 无 |
| T14 | Demo/部署/P0验收 | 未开始 | 无 |
| T15 | 统计缓存/P1交付 | 未开始 | 无 |

## 已确认

选题：接口回归测试平台；带简单前端；主要服务Python后端实习项目展示；
本聊天负责详细计划，用户交给Claude Code接DeepSeek实施。

## 默认设计

Vue 3、PostgreSQL、模块化单体、项目owner隔离、本地OpenAPI JSON、
线性流程、数据快照、Celery+Redis、持久化SSE、部署者origin白名单。
若用户修改默认值，同步更新规格/契约/计划再开发。

## 当前待办

继续 T02：ORM 模型、Alembic 初始迁移、真实 PostgreSQL 集成测试底座与 ready 检查。

## 任务记录

### T01 工程骨架、配置与健康接口（2026-11-05）

- 涉及文件：`backend/pyproject.toml`、`uv.lock`、`app/core/{config,errors,logging}.py`、
  `app/main.py`、`app/modules/health/router.py`、`app/db/{base,async_session}.py`、
  `frontend/*`、`compose.yaml`、`infra/nginx.conf`、`scripts/init_env.py`、
  `.env.example`、`.gitignore`、`Dockerfile`。
- 实现需求/验收：G7 基础、A19 启动前置；健康接口不含连接串，响应统一 request_id。
- 依赖版本（uv.lock 实际解析）：Python 3.12.16；FastAPI 0.162.0；Pydantic 2.14.2；
  pydantic-settings 2.16.2；SQLAlchemy 2.0.57（约束 `<2.1`）；Alembic 1.20.1；
  pytest-asyncio 1.4.1.post1；
  Celery 5.6.3；HTTPX 0.28.1；asyncpg 0.32.0；psycopg 3.3.8；redis 7.4.1；
  PyJWT 2.15.1；pwdlib 0.3.1；cryptography 50.0.2；Ruff 0.17.3。
  前端：Vue 3.5.45、Vue Router 4.6.4、Pinia 3.0.4、Vite 8.3.6、TypeScript 5.9.3、
  Element Plus 2.14.7、eventsource-parser 3.1.1、Vitest 5.1.0。
- 实际命令与结果：
  - `python -m uv sync --frozen --default-index https://pypi.tuna.tsinghua.edu.cn/simple`
    → 63 packages，成功。
  - `python -m uv run --frozen pytest tests/unit -q` → 12 passed。
  - `python -m uv run --frozen ruff check .` → All checks passed。
  - `python -m uv run --frozen ruff format --check .` → 23 files already formatted。
  - `npm run typecheck`、`npm run build` → 成功（Vite 8.3.6，91.70 kB JS）。
  - `docker compose config --quiet` → 成功。
- 未运行检查及原因：尚未构建 Docker 镜像/启动容器（T14 完整部署验收时执行）。
- 设计调整：见 decisions.md D001–D005（Python 3.12 由 uv 安装；镜像源加速）。
- 遗留问题：`starlette.testclient` 对 httpx 发出弃用提示，不影响测试；后续集成测试用
  ASGITransport，避免依赖 TestClient。
- 下一任务：T02 数据库模型、迁移与集成测试底座。

## 每任务追加记录模板

~~~text
日期/任务：
Commit：
涉及文件：
实现的需求/验收编号：
依赖版本（如变化）：
实际验证命令与结果：
未运行检查及原因：
设计调整及依据：
遗留问题：
下一任务：
~~~
