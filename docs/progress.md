# 开发进度

更新时间：2026-11-05（Asia/Shanghai）。
当前状态：T01–T07 已通过验证；T08 进行中。
执行方式：用户后续通过Claude Code接DeepSeek实施。

| 任务 | 内容 | 状态 | 验证证据 |
|---|---|---|---|
| T01 | 工程/配置/健康接口 | 已完成 | 12 unit passed；Ruff/format/前端构建/compose config 通过 |
| T02 | 数据库/迁移/测试底座 | 已完成 | 6 integration passed（真实 PG）；Compose test 18 passed |
| T03 | 认证/项目/owner | 已完成 | auth/owner 集成测试通过；全量 40 passed |
| T04 | 环境加密/secret协议 | 已完成 | 环境/加密测试通过；全量 40 passed |
| T05 | DSL/用例CRUD | 已完成 | DSL/selectors/cases 测试通过；全量 85 passed |
| T06 | OpenAPI导入 | 已完成 | 解析/导入/并发测试通过；全量 104 passed |
| T07 | 渲染/取值/断言 | 已完成 | 纯函数测试 91 unit passed |
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

继续 T08：有界 HTTP transport、脱敏与线性执行器。

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

### T02 数据库模型、迁移与集成测试底座（2026-11-05）

- 涉及文件：`app/db/{models,base,sync_session}.py`、`migrations/env.py`、
  `migrations/versions/0001_initial.py`、`alembic.ini`、`tests/integration/{conftest,db_utils}.py`、
  `tests/integration/test_migrations.py`、`tests/integration/test_health_ready.py`、
  `compose.test.yaml`、`backend/Dockerfile`。
- 实现需求/验收：设计第 6 节全部表与约束；ready 真实 `SELECT 1`；A09/A19 的数据基础。
- 实例：隔离 test 容器 `arp-test-db`（PostgreSQL 17.5）与 `arp-test-redis`（Redis 7.4），
  宿主测试端口 55488/56500（Windows 排除端口段规避 55432/56379）。
- 实际命令与结果：
  - `APP_TEST_DATABASE_URL=... pytest tests/integration/test_migrations.py -q` → 4 passed。
  - `... pytest tests/integration -q` → 6 passed（含 ready 503 反例）。
  - `docker compose -f compose.yaml -f compose.test.yaml run --rm test pytest tests/integration -q`
    → 18 passed（T02+T03 代码镜像）。
  - `ruff check` / `ruff format --check` → 通过。
- 关键实现：
  - 唯一约束 `(project_id,idempotency_key)`、`(run_id,position)`、`(project_id,name)`；
    `runs` 索引 `(project_id, created_at DESC, id DESC)` 与 `(status, created_at)`；
    `run_events.id BIGSERIAL`。
  - 状态值使用 CHECK 约束；外键均 RESTRICT，不做物理删除。
  - Alembic URL 由 `APP_TEST_DATABASE_URL`/`APP_SYNC_DATABASE_URL` 注入，无硬编码密码。
- 调试记录：
  - 原始迁移测试漏传 `cases.version`/`environments.version`，报 NotNullViolation；修正测试数据，
    未放宽数据库约束。
  - pytest-asyncio 测试与 fixture 事件循环不一致导致 asyncpg 在已关闭 loop 上清理连接；
    固定 `asyncio_default_test_loop_scope=session`。
  - TRUNCATE 被遗留 idle-in-transaction 连接阻塞；集成 fixture 在隔离 test 库中断开其它连接后清理。
- 设计调整：后端镜像不再从 ghcr.io 拉取 uv 层（实测 19.34MB 下载 140 秒仍未完成），
  改为 `pip install uv==0.13.7` 使用同一镜像源。
- 下一任务：T03 认证与项目 owner 边界。

### T03 注册登录、项目与 owner 边界（2026-11-05）

- 涉及文件：`app/core/security.py`、`app/core/schemas.py`、
  `app/modules/auth/*`、`app/modules/projects/*`、`tests/integration/test_auth.py`、
  `tests/integration/test_project_ownership.py`、`tests/factories.py`。
- 实现需求/验收：A01、A02（项目层）；注册/登录/me、owner 隔离、分页边界。
- 实际命令与结果：`pytest tests/unit tests/integration -q` → 40 passed；Ruff 通过。
- 关键实现：Argon2（pwdlib）、HS256 + 30 分钟 exp/iat/sub、HTTPBearer；
  用户名小写归一化唯一；`require_owned_project` 作为后续全部子资源依赖；
  `extra=forbid` 拒绝请求体中的 `owner_id`。
- 未运行：前端 401 清 Token（T12）。
- 下一任务：T04 环境加密与 secret 协议。

### T04 环境、加密与 secret 编辑协议（2026-11-05）

- 涉及文件：`app/core/{crypto,dependencies}.py`、`app/modules/environments/*`、
  `tests/unit/test_crypto.py`、`tests/integration/test_environments.py`。
- 实现需求/验收：A03；C02/C03 的 secret 保留/替换/移除、origin 白名单。
- 实际命令与结果：`pytest tests/unit tests/integration -q` → 40 passed；Ruff/format 通过。
- 关键实现：`config_ciphertext` 存 Fernet 密文的 variables+common_headers；
  GET 中 secret `value=null,has_value=true`；认证 header 强制 secret；
  仅接受 `TARGET_ORIGINS` 中规范化后的 exact origin；版本冲突 409；
  密文断言中不存在已知 secret 明文。
- 遗留问题：`GET /target-origins` 目前要求登录（依 C06 全局规则），前端 T12 接入。
- 下一任务：T05 流程 DSL 校验与用例 CRUD。

### T05 流程 DSL 校验与用例 CRUD（2026-11-05）

- 涉及文件：`app/domain/{contracts,template,selectors}.py`、`app/modules/cases/*`、
  `tests/unit/test_case_schema.py`、`tests/unit/test_selector_parser.py`、
  `tests/integration/test_cases.py`。
- 实现需求/验收：A05、A06（静态部分）；C02/C04/C05 的 DSL。
- 实际命令与结果：`pytest tests/unit tests/integration -q` → 85 passed；Ruff/format 通过。
- 关键实现：
  - 步骤 1..20，步骤 UUID 唯一，跨步骤提取器名唯一；每步恰有一个 status_code 断言。
  - path 仅接受单斜杠开头的相对模板；path_params 键集合必须等于路径参数；
    禁止 `{{}}` 出现在 path 本身；禁止点路径、query、fragment、origin。
  - 受限选择器 token parser（`$`、`.field`、`[n]`），不依赖完整 JSONPath/eval。
  - 模板 `{{name}}` 静态校验；非模板标记导致的未闭合/非法名称拒绝。
  - body 中 password/token/access_token/refresh_token/api_key/client_secret/secret
    只允许完整模板，字面量 422。
  - 整体 PUT 携带 version，旧版本 409；`source_api_id` 仅溯源且必须同项目。
- 未运行：T06 导入；执行期模板渲染在 T07。
- 下一任务：T06 OpenAPI 元数据导入。

### T06 OpenAPI 元数据导入（2026-11-05）

- 涉及文件：`app/modules/imports/{parser,service,router,schemas}.py`、
  `tests/unit/test_openapi_import.py`、`tests/integration/test_import_api.py`、
  `tests/fixtures/openapi_minimal.json`。
- 实现需求/验收：A04。
- 实际命令与结果：`pytest tests/unit tests/integration -q` → 104 passed；Ruff/format 通过。
- 关键实现：
  - 文件 ≤2MiB、UTF-8 JSON、openapi 3.0.x/3.1.x、paths 对象、支持 operation ≤200。
  - 全文档本地 `$ref` 限制：非 `#/` 开头一律 422；参数/RequestBody 引用最大深度 8，
    循环引用 422；schema 内部 `$ref` 保留符号不递归展开。
  - JSON 遍历节点 ≤20000、深度 ≤32；移除 example/examples/default。
  - path 参数与 operation 参数按 (name,in) 合并，operation 覆盖；cookie 跳过并警告。
  - 写入使用 PostgreSQL `ON CONFLICT (project_id, method, path) DO NOTHING`，
    并发导入不会 500 或产生重复；解析在事务前完成。
  - warnings 截断到 100 条并附截断说明。
- 调试记录：导入测试中“非法 operation”文档被完整校验拦截，数据库无残留行（符合预期）。
- 下一任务：T07 模板渲染、选择器取值与断言纯逻辑。

### T07 模板渲染、取值和断言纯逻辑（2026-11-05）

- 涉及文件：`app/domain/{template,selectors,assertions,contracts}.py`、
  `tests/unit/{test_template,test_selectors,test_assertions}.py`。
- 实现需求/验收：A06、A07 的执行语义基础。
- 实际命令与结果：`pytest tests/unit -q` → 91 passed；Ruff/format 通过。
- 关键实现：
  - 整段 `{{name}}` 保留原生标量；嵌入模板按 true/false/null/JSON 数字转字符串。
  - 不递归解释变量值、不渲染字典键、不修改原始定义；缺变量抛 `VariableUndefined`。
  - path_params 逐参数 URL 编码；query 键值编码；step header 大小写不敏感覆盖 common；
    渲染后再校验最终 origin 未改变。
  - `json_equals` 先渲染 expected；bool 与数字不相等，1 与 1.0 相等；
    对象键序无关、数组顺序敏感；缺选择器判失败而不抛错。
  - `response_time_lt` 使用未取整浮点毫秒严格小于；404 期望 404 可通过。
  - 提取器：secret 必须非空字符串；普通提取只接受 JSON 标量。
- 下一任务：T08 有界 HTTP、脱敏与线性执行器。

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
