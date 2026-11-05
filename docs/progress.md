# 开发进度

更新时间：2026-11-05（Asia/Shanghai）。
当前状态：T01–T15 全部完成；P0 验收 A01–A19 通过（A18 窄屏未完整验证），P1 A20 通过。
最终交付：最新代码已重建开发 Compose，seed + smoke 五步 passed；E2E 截图与验证记录见
docs/verification.md。
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
| T08 | HTTP/脱敏/执行器 | 已完成 | transport/redaction/runner 单测；115 unit passed |
| T09 | 快照/幂等提交 | 已完成 | 提交/幂等/快照集成测试；全量 161 passed |
| T10 | Worker/outbox/中断恢复 | 已完成（真实 broker 待 T14） | claim/sink/outbox/reconcile 集成；全量 178 passed |
| T11 | 报告/SSE | 已完成 | 报告/SSE 集成测试；全量 187 passed |
| T12 | 前端账号/配置 | 已完成 | typecheck、13 unit、build 通过 |
| T13 | 前端用例/执行/报告 | 已完成 | typecheck、25 unit、build 通过 |
| T14 | Demo/部署/P0验收 | 已完成 | 真实 Compose + smoke + Playwright 3 passed；中断 336.4s；Redis 停机恢复 |
| T15 | 统计缓存/P1交付 | 已完成 | 5 summary 集成测试；10k 基准 4.18/4.27 ms |

## 已确认

选题：接口回归测试平台；带简单前端；主要服务Python后端实习项目展示；
本聊天负责详细计划，用户交给Claude Code接DeepSeek实施。

## 默认设计

Vue 3、PostgreSQL、模块化单体、项目owner隔离、本地OpenAPI JSON、
线性流程、数据快照、Celery+Redis、持久化SSE、部署者origin白名单。
若用户修改默认值，同步更新规格/契约/计划再开发。

## 当前待办

T14：Demo API、真实 Compose 部署、Playwright/E2E 与三项演示。

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

### T08 有界 HTTP、脱敏与线性执行器（2026-11-05）

- 涉及文件：`app/domain/{ports,redaction,runner}.py`、`app/infra/http_transport.py`、
  `tests/unit/{test_transport,test_redaction,test_runner}.py`。
- 实现需求/验收：A06–A09、A15、A16 的执行与脱敏基础。
- 实际命令与结果：`pytest tests/unit -q` → 115 passed；Ruff/format 通过。
- 关键实现：
  - `HttpxTransport`：exact origin 校验、Host/Content-Length 等拒绝、
    `trust_env=false`、`follow_redirects=false`、分项 timeout、流式读取 ≤1MiB、
    单次发送无重试；302 原样返回不跟随；HTTP 4xx/5xx 不自动判失败。
  - 脱敏：secret 注册表替换已知值；Authorization/Cookie/Set-Cookie/X-API-Key 整体遮蔽；
    敏感 JSON 键递归遮蔽；URL 只保留 origin/path 模板/query 键名；
    预览 ≤8192 字节；非 JSON 或 omit_response_body 时正文省略。
  - 执行器：独立上下文、逐步开始/保存、断言全部计算、失败即停；
    断言通过后才发布提取变量；断言失败仍收集 secret 提取值用于脱敏；
    缺变量在 HTTP 前失败；预算耗尽标记 interrupted/RUN_TIMEOUT。
- 未运行：真实 Redis/Celery 链路（T10）；报告序列化（T11）。
- 下一任务：T09 运行快照与幂等提交。

### T09 运行快照与幂等提交（2026-11-05）

- 涉及文件：`app/modules/runs/{schemas,service,repository,router}.py`、
  `tests/integration/{test_run_creation,test_run_idempotency,test_run_snapshot}.py`。
- 实现需求/验收：A10、A12；G3/G4 的提交侧。
- 实际命令与结果：`pytest tests/unit tests/integration -q` → 161 passed；Ruff/format 通过。
- 关键实现：
  - POST 202，同一事务写入 Run（加密快照）、pending StepResult、`run.queued` 事件、
    pending outbox；不调用 Redis。
  - `Idempotency-Key` 必填 UUID；同项目同 key 同 case/env 返回原 run（reused=true），
    不同指纹 409；并发冲突由唯一约束兜底后读取原记录。
  - 快照包含 schema_version=1、case/env 名称与版本、stub 步骤、解密变量/header、
    target_origin、limits、captured_at；整段 Fernet 加密。
  - 提交前校验 case/env 同项目、提取器名与环境变量冲突、origin 白名单。
- 调试记录：并发提交时 `IntegrityError` 发生在 flush 而非 commit；捕获后 rollback 使
  ORM Project 过期，访问 `project.id` 触发同步懒加载（MissingGreenlet）。
  改为在函数入口保存 `project_id` 局部变量。
- 下一任务：T10 Celery 执行、outbox 发布与中断回收。

### T10 Celery 执行、outbox 发布与中断回收（2026-11-05）

- 涉及文件：`app/workers/{repository,sink,execution,tasks,celery_app,dispatcher,reconcile,snapshot}.py`、
  `compose.yaml`、`backend/Dockerfile`、
  `tests/integration/{test_worker_claim,test_worker_sink,test_outbox,test_reconcile,test_worker_soft_timeout}.py`。
- 实现需求/验收：A11、A13、A14；G4/G5。
- 实际命令与结果：
  - `pytest tests/unit tests/integration -q` → 178 passed。
  - `docker compose config --quiet` → 通过。
  - **未运行**：真实 Redis/Celery 链路的 worker claim（需完整 Compose 栈，T14 执行）。
- 关键实现：
  - `claim_run` 单条 `UPDATE ... WHERE status='queued' AND created_at>now-300s RETURNING`；
    重复消息返回 None；仅抢占者写 `run.started`。
  - `PostgresRunSink` 每操作独立同步 Session + 短事务；step 状态以 `pending→running→终态`
    条件更新作为栅栏；run 终结使用 `run_id + execution_token + status='running'` CAS；
    终态同事务补写 running→error、pending→skipped 与 `run.finished`。
  - dispatcher：每批 ≤50，发前重查 run 仍 queued 且未过期；网络发布不持事务；
    失败固定 BROKER_UNAVAILABLE，退避 min(2^attempt,30)；成功标 sent。
  - reconcile：queued>300s → error/DISPATCH_TIMEOUT；running 超 330s →
    interrupted/WORKER_INTERRUPTED；均 CAS 并同事务写事件。
  - SoftTimeLimitExceeded 尽力 finish(interrupted/RUN_TIMEOUT)；未处理异常 finish(error/INTERNAL_ERROR)。
  - Celery：JSON、ignore_result、acks_late=false、prefetch=1、concurrency=2、无 autoretry。
  - Compose 新增 migrate/worker/dispatcher；api/worker/dispatcher 等待迁移成功。
- 调试记录：并发 claim 测试使用两个线程/独立 Session 验证唯一抢占；超时回收用注入 now
  避免真实等待 300/330 秒。
- 遗留：真实 broker 端到端在 T14 验收；dispatcher 发布路径尚未对真实 Redis 运行。
- 下一任务：T11 报告、持久化 SSE 与恢复。

### T11 报告、持久化 SSE 与恢复（2026-11-05）

- 涉及文件：`app/modules/runs/{schemas,repository,sse,router}.py`、
  `app/core/security.py`、`app/modules/auth/deps.py`、`infra/nginx.conf`、
  `tests/integration/{test_reports,test_sse}.py`。
- 实现需求/验收：A09、A17；G3 的报告侧。
- 实际命令与结果：`pytest tests/unit tests/integration -q` → 187 passed；Ruff/format 通过。
- 关键实现：
  - `RunSummary/RunReport` 仅序列化安全字段；counts 由真实步骤 GROUP BY / 内存统计，
    和 total 一致；报告步骤按 position 升序；终态不残留 pending/running。
  - 运行列表按 created_at DESC,id DESC；status 过滤非法值 422；owner 404。
  - SSE：独立短 Session 每批查询 ≤100，等待时释放连接；事件按 id 升序；
    `after` 续读；心跳 15s；连接最长 60s；JWT 过期关闭；终态事件发完后关闭。
    SSE 鉴权在返回 StreamingResponse 前用短 Session 完成，不持有连接。
  - Nginx 仅对 events 路径关闭 buffering/缓存/gzip，read timeout 75s。
- 测试：事件回放、after 去重、401/404、心跳与过期注入时钟、中文不转义。
- 下一任务：T12 前端登录、项目、环境与导入。

### T12 前端登录、项目、环境和导入（2026-11-05）

- 涉及文件：`frontend/src/api/{client,types,auth,projects,environments,imports,secretPayload}.ts`、
  `stores/auth.ts`、`router/index.ts`、`layouts/ProjectLayout.vue`、
  `components/SecretField.vue`、`views/{Login,Register,Projects,Overview,Environments,Apis}View.vue`、
  `tests/unit/{auth,api-errors,secret-field}.test.ts`。
- 实现需求/验收：A01（前端 401）、A02/A03 的编辑界面、A18 的前半部分。
- 实际命令与结果：
  - `npm run typecheck` → 通过。
  - `npm run test:unit -- --run` → 3 files / 13 tests passed。
  - `npm run build` → 成功（Element Plus 主包导致 1.04MB chunk 警告，未阻塞）。
- 关键实现：
  - Token 仅 Pinia 内存；401 清 Token 并跳登录；错误统一映射 404/409/422/500。
  - SecretField 明确 keep/replace/remove；secret 默认保留，替换要求非空；
    payload 构造为纯函数并单测。
  - 环境编辑从 `/target-origins` 选择 base_url；认证 header 强制 secret。
  - OpenAPI 上传使用 multipart，无需手写 Content-Type；警告与计数展示。
  - 页面覆盖加载、空态、错误、409 提示；不使用 v-html。
- 未运行：真实浏览器 E2E（T14）；真实 API 手工串联留待 T14 smoke。
- 下一任务：T13 前端用例编辑、执行与实时报告。

### T13 前端用例编辑、执行和实时报告（2026-11-05）

- 涉及文件：`src/api/{cases,runs,sse}.ts`、`composables/useRunEvents.ts`、
  `utils/{caseEditor,runSubmission,labels}.ts`、
  `components/{StepList,RequestEditor,AssertionEditor,ExtractorEditor,StepResult}.vue`、
  `views/{Cases,CaseEditor,Runs,RunReport}View.vue`、router/layout、3 个测试文件。
- 实现需求/验收：A17 的前端侧、A18；G2/G5 的界面。
- 实际命令与结果：`typecheck` 通过；`test:unit -- --run` → 6 files / 25 tests passed；
  `build` 成功（一次模板插值语法错误已修复）。
- 关键实现：
  - 用例编辑器：步骤增删/上移下移、保留 step UUID；JSON 语法错误阻止保存；
    数字期望值按 JSON 解析保持 number；必须恰有一个 status_code；版本冲突显示重新加载。
  - “从接口添加”只预填 method/path/参数名与期望 200 草稿，不自动断言业务正确。
  - 运行提交：RunSubmitter 生成一次幂等键；传输失败保留同键重试；成功后新键；
    双击复用同一 Promise，只发一次请求；刷新报告不会创建新 run。
  - SSE composable：fetch + Bearer + AbortController + eventsource-parser；
    TextDecoder(stream) 处理中文分片；按事件 id 去重；after 游标重连；
    3 次连续失败降级为每 2 秒 GET 报告；终态停止；卸载时 abort。
  - 报告页展示脱敏请求/响应、断言、提取与中断不确定性提示。
- 未运行：真实浏览器/真实 Worker（T14）。
- 下一任务：T14 Demo API、Compose 与 E2E 验收。

### T14 真实 Demo、完整部署与 P0 验收（2026-11-05）

- 涉及文件：`demo-api/*`、`scripts/{seed_demo,smoke,reset_demo,interrupt_demo,demo_common}.py`、
  `frontend/e2e/*`、`compose.yaml`、`infra/nginx.conf`、`README.md`、`docs/{architecture,demo,verification}.md`。
- 实现需求/验收：A07/A08/A11/A13/A14/A17–A19；G2/G5/G7。
- 实际命令与结果：
  - Demo API `pytest tests -q` → 4 passed。
  - 开发 Compose：seed 成功；smoke `run_status=passed`，五步 passed。
  - 故障注入 `DEMO_FAULT_MODE=title_mismatch`：step1/2 passed、step3 failed、step4/5 skipped；
    恢复后 reset 清空 Demo 文章 1 条。
  - 独立 `arp-e2e`：迁移/健康依赖成功；seed/smoke 五步 passed；
    Playwright（系统 Chrome）3 passed：成功、断言失败、用户隔离。
  - Compose 隔离集成：72 passed（T14 时点；T15 新增 summary 后复跑见 verification）。
- 调试记录（均写入 decisions.md）：
  - Dockerfile 最后 stage 是 test，需为后端服务显式 `target: base`。
  - 服务内硬编码 `env_file: .env` 破坏 E2E 隔离，改为 `${VAR}` 插值。
  - api 重建后 Nginx 缓存旧 IP → 502；改为 Docker DNS + 变量 proxy_pass。
  - worker 运行期缺少 kombu 依赖 `packaging`，加入运行时依赖。
  - Playwright Chromium 下载停滞，改用系统 Chrome（`E2E_BROWSER_CHANNEL`）。
- 收尾证据：
  - Worker 强杀：336.4s 后 interrupted/WORKER_INTERRUPTED；step2 error、3–5 skipped；
    重启 worker 不重放。
  - Redis 停机：提交仍 queued，outbox attempt=1/BROKER_UNAVAILABLE，恢复后补发并五步 passed。
  - 发现并修复：Celery producer 连接重试使单次发布超过 6 秒；dispatcher 增加 3 秒线程级超时，
    并关闭发布重试。
- 下一任务：T15 统计缓存与交付材料（同批完成）。

### T15 项目统计、缓存、性能证据与最终交接（2026-11-05）

- 涉及文件：`app/modules/summary/*`、`tests/integration/test_summary.py`、
  `frontend/src/api/summary.ts`、`OverviewView.vue`、`scripts/benchmark_summary.py`、
  `docs/{architecture,demo,resume-notes,verification}.md`。
- 实现需求/验收：A20。
- 实际命令与结果：
  - `pytest tests/integration/test_summary.py -q` → 5 passed。
  - 全量后端：193 passed（115 unit + 78 integration）。
  - `benchmark_summary.py`（隔离 test 库，10,000 runs）：
    summary 平均 4.18 ms，列表第一页 4.27 ms；计划使用 `ix_runs_project_created`。
  - 前端 typecheck、25 unit、build 通过。
- 关键实现：
  - 真实 SQL `GROUP BY status`；active = queued+running；pass_rate=passed/(passed+failed)，
    0 分母为 null；error/interrupted 不计入业务通过率。
  - Redis `summary:v1:{project_id}` TTL 30s；命中保留原 computed_at 并 cache_hit=true；
    Redis 异常静默回退数据库。
  - owner 检查由路由依赖先于缓存执行。
  - Overview 展示统计与“最多 30 秒延迟”、计算时间、缓存标记。
- 下一任务：收尾中断/Redis 证据并更新 verification，最终提交。

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
