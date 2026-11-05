# FlowCheck 接口回归测试平台 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.
> 外部 Claude Code 没有这些 skills 时，按 CLAUDE.md 和本计划等效执行；不要求安装技能或使用特定模型。
> 用户指定执行方式：Claude Code 接 DeepSeek。此交接包只规划，不在当前聊天实现应用。

**Goal:** 用简单前端完成接口流程配置、后台回归执行、实时进度与可追溯报告。
**Architecture:** 模块化单体，API/Worker/dispatcher共享代码、独立进程；PostgreSQL保存状态与结果，
Redis做broker。API异步DB，Worker同步DB与HTTP；前端同源访问API并用fetch SSE订阅。
**Tech Stack:** Python 3.12 / FastAPI / Pydantic 2 / SQLAlchemy 2.0 / PostgreSQL 17 /
Celery 5.6 / Redis 7.4 / Vue 3 / TypeScript / Vite 8 / Element Plus / Compose。
**Spec:** docs/superpowers/specs/2026-11-05-api-regression-platform-design.md
**Contracts:** docs/contracts/api-v1.md
**Acceptance:** docs/handoff/acceptance.md

## Global Constraints

- Python 3.12；Node.js 22（>=22.12）；PostgreSQL 17；Redis 7.4。
- 一次 run 执行一个 case；case 内严格串行，不允许自动重试业务 HTTP 请求或整个 run。
- 状态、快照、结果、事件存 PostgreSQL。Celery 状态和 Redis Pub/Sub 不作为报告事实来源。
- 环境秘密与完整运行输入快照加密；日志、结果、事件只保存脱敏数据。
- JWT 不放 URL，不放日志。前端 Token 只放内存，刷新后重新登录。
- 每用例1..20步；每步至少一个 status_code 断言；method仅GET/POST/PUT/PATCH/DELETE。
- 所有对象schema默认 extra=forbid；所有用户资源均owner隔离。
- 只处理本地OpenAPI JSON；只请求部署者允许的origin。
- 不做AI运行时、定时回归、通用工作流引擎、团队协作或任意脚本。
- 本计划15项依次推进；P0=T01..T14，P1=T15。不可把未通过验收的任务勾选完成。
- 默认每个任务通过后向用户交付证据并停止；连续执行须有用户授权。

## Review Focus

RF1：并发提交/消息重复 → 同一次run只会有一个执行者；T09/T10加入真实PG并发测试。
RF2：请求已生效但客户端/Worker中断 → 不重放，不承诺exactly-once；T10/T14验证。
RF3：秘密被回显、URL带秘密或SSE被越权访问 → 仅安全结果公开；T08/T11/T14验证。
RF4：SSE中文跨chunk、断线、刷新、Token过期 → 能恢复报告且不创建新run；T11/T13验证。
RF5：导入外部引用、嵌套超限、JSON true与1 → 明确拒绝或按契约比较；T05/T06/T07验证。

## 文件结构与职责

以下是计划创建的文件，不代表现在已存在；实现者不得以文档目录冒充应用脚手架。
每个Python包补__init__.py。未列路径只可为本任务必要的测试/配置增加，需记录原因。

~~~text
backend/
  pyproject.toml, uv.lock, alembic.ini, Dockerfile
  migrations/env.py, migrations/versions/0001_initial.py
  app/main.py                       create_app工厂、路由注册
  app/core/config.py                Settings、必需密钥验证
  app/core/errors.py                业务异常、统一错误响应
  app/core/logging.py               request_id与结构化安全日志
  app/core/crypto.py                Fernet与密文JSON序列化
  app/core/security.py              Argon2、JWT
  app/db/base.py, models.py         ORM及约束，模型统一注册
  app/db/async_session.py           API session
  app/db/sync_session.py            Worker/dispatcher session
  app/domain/contracts.py          DSL、快照、运行结果类型
  app/domain/template.py           模板校验/渲染
  app/domain/selectors.py          受限选择器
  app/domain/assertions.py         JSON语义断言
  app/domain/redaction.py          秘密注册与安全视图
  app/domain/ports.py              HttpTransport、RunSink协议
  app/domain/runner.py             线性执行逻辑
  app/infra/http_transport.py      HTTPX有界读取与目标限制
  app/modules/auth/{schemas,service,router,deps}.py
  app/modules/projects/{schemas,service,router,deps}.py
  app/modules/environments/{schemas,service,router}.py
  app/modules/imports/{schemas,parser,service,router}.py
  app/modules/cases/{schemas,service,router}.py
  app/modules/runs/{schemas,service,repository,router,sse}.py
  app/modules/summary/{schemas,service,router}.py
  app/workers/{celery_app,tasks,sink,dispatcher,reconcile}.py
  tests/{conftest, factories}.py
  tests/unit/, tests/integration/
demo-api/
  pyproject.toml, uv.lock, Dockerfile
  app/{main,models,auth,faults}.py
frontend/
  package.json, package-lock.json, vite.config.ts, tsconfig.json, Dockerfile
  src/main.ts, App.vue
  src/router/index.ts
  src/api/{client,types,auth,projects,environments,imports,cases,runs,summary}.ts
  src/stores/auth.ts
  src/composables/useRunEvents.ts
  src/layouts/ProjectLayout.vue
  src/views/{Login,Register,Projects,Overview,Environments,Apis,Cases,CaseEditor,Runs,RunReport}View.vue
  src/components/{StepList,RequestEditor,AssertionEditor,ExtractorEditor,StepResult,SecretField}.vue
  tests/unit/
  e2e/{playwright.config.ts,auth.setup.ts,happy.spec.ts,failure.spec.ts,isolation.spec.ts}
infra/nginx.conf
compose.yaml, compose.test.yaml
scripts/init_env.py, seed_demo.py, reset_demo.py, smoke.py
docs/progress.md, architecture.md, decisions.md, demo.md, verification.md
~~~

模块service负责事务提交与回滚；repository/deps不commit。
API共用一次请求的AsyncSession：认证查询已触发autobegin后，不能再无条件session.begin；
写service在同一隐式事务完成校验和写入，再commit；退出依赖finally rollback未提交事务并关闭。
Worker/dispatcher每次仓储操作新建同步Session+短事务。禁止跨网络调用持锁。

## 阶段与依赖

M1 数据与接口：T01→T02→T03→T04→T05→T06。
M2 执行闭环：T07依赖T05；T08依赖T07；T09依赖T04/T05/T08；
T10依赖T09；T11依赖T10。
M3 可用产品：T12依赖T06；T13依赖T11/T12；T14依赖T13；T15依赖T14。
先连通一条真实流程，再做统计缓存与展示；前端可先读契约，不依赖假接口长期开发。

## 统一验证命令约定

以下命令是未来应执行的命令，不是本交接已通过的结果。
任务开始前先建真实测试文件；若首轮是ImportError而不是行为断言失败，先补最小导入骨架，再确认行为测试失败。

后端单元：从backend运行 uv run pytest tests/unit -q。
后端静态：从backend运行 uv run ruff check . 与 uv run ruff format --check .。
后端集成：根运行 docker compose -f compose.yaml -f compose.test.yaml run --rm test pytest tests/integration -q。
  test服务使用隔离的test-db/test-redis，不能连接开发数据库。
前端：从frontend运行 npm run typecheck、npm run test:unit -- --run、npm run build。
E2E：从frontend运行 npm run test:e2e，package script固定 playwright test --config e2e/playwright.config.ts。
命令若因平台路径不兼容，修正脚本并记录，不把“预计通过”记为结果。
每个任务结束执行适用检查；只有新变更/失败才重复全套。

---

## T01：工程骨架、配置与健康接口

依赖：无。交付：可启动的API健康接口、前端空壳和安全配置加载，尚不声称业务完成。
Files：backend/pyproject.toml、uv.lock、app/main.py、core/config.py、core/errors.py、
core/logging.py、tests/unit/test_health.py、test_config.py；frontend基础文件；
scripts/init_env.py；.gitignore、.env.example；compose.yaml的基础db/redis/api/web结构；
docs/progress.md、docs/decisions.md。

Interfaces：
- create_app(settings: Settings | None = None) -> FastAPI；测试可传独立Settings，无全局缓存污染。
- Settings包含APP_DATABASE_URL、APP_SYNC_DATABASE_URL、APP_REDIS_BROKER_URL、
  APP_REDIS_CACHE_URL、APP_JWT_SECRET、APP_ENCRYPTION_KEY、TARGET_ORIGINS、CORS_ORIGINS。
- init_env.py只用stdlib生成.env；已有文件拒绝覆盖；不向stdout打印秘密。
- GET /api/v1/health/live恒定200；ready在T02接DB。

- [ ] 1. 建配置测试：缺密钥/非法Fernet key失败，未知origin配置失败；健康响应不含连接串。
  核心断言：live.json()=={"status":"ok"}；len(response.headers["X-Request-ID"])==36。
- [ ] 2. 运行上述测试确认行为尚未实现；再实现最小app工厂、异常处理与日志中间件。
- [ ] 3. 按规格兼容范围安装依赖、生成真实lockfile；前端创建Vue/TS空壳，保留纯文本占位页面。
  只需一个依赖可解析的基线；记录Python、Node、包精确版本及实际安装错误。
- [ ] 4. 实现配置初始化脚本；.env.example只含变量名/占位说明。
  .gitignore包含.env及.env.*，显式放行.env.example；忽略node_modules、.venv、测试产物。
- [ ] 5. 检查：uv run pytest tests/unit/test_health.py tests/unit/test_config.py -q；
  Ruff；npm run typecheck、npm run build；docker compose config --quiet。
  不直接输出完整compose config，防止展开密码。
- [ ] 6. 更新进度并提交 chore: initialize platform configuration and health checks。

## T02：数据库模型、迁移与集成测试底座

依赖：T01。Files：db/base.py、models.py、async_session.py、sync_session.py；
migrations/env.py、versions/0001_initial.py；tests/conftest.py、factories.py；
tests/integration/test_migrations.py；compose.test.yaml。

Interfaces：
- get_async_session() -> AsyncIterator[AsyncSession]；sync_session_factory() -> sessionmaker[Session]。
- 模型名固定User、Project、Environment、ApiDefinition、Case、Run、StepResult、RunEvent、RunOutbox。
- 全字段/约束按设计第6节；run/step/outbox状态用校验约束或明确Enum，不能允许任意字符串。
- tests提供api_client: AsyncClient、db: AsyncSession；后续任务扩展user/token/project工厂。
- test-db/test-redis为独立Compose服务，test profile，不映射宿主端口；迁移针对test-db。

- [ ] 1. 建迁移集成测试：空测试库upgrade head成功，检查全部表、唯一约束与外键索引；
  upgrade重复执行不报错；仅在隔离测试库验证downgrade base再upgrade。
- [ ] 2. 确认失败后写ORM与迁移；alembic env允许测试URL注入，不在迁移脚本硬编码密码。
  进程创建连接池前不得fork；API与sync Worker engine在各自进程创建，pool_pre_ping开启。
- [ ] 3. 建事务测试：同项目重复idempotency_key受唯一约束，StepResult重复position受约束；
  RunEvent id可递增；created_at是UTC aware。
- [ ] 4. 实现测试fixture：每测试独立清理test-db数据、不碰开发库；
  不用SQLite；测试按串行运行，async engine生命周期与event loop一致，结束dispose。
- [ ] 5. 集成迁移测试、Ruff通过；ready实际执行SELECT 1，数据库不可用返回503且固定文案。
  新库初始化只能通过alembic，不允许app启动时create_all。
- [ ] 6. 更新进度并提交 feat: add database schema and migrations。

## T03：注册登录、项目与owner边界

依赖：T02。Files：core/security.py；modules/auth/*、projects/*；
tests/integration/test_auth.py、test_project_ownership.py。

Interfaces：
- hash_password(password: str) -> str；verify_password(plain: str, hashed: str) -> bool。
- issue_access_token(user_id: UUID, now: datetime) -> str；decode_access_token(token: str) -> UUID。
- get_current_user依赖；require_owned_project(project_id: UUID, user: User, db: AsyncSession) -> Project。
- POST/GET/PUT projects及auth路由严格按C06；owner_id来自Token，绝不信任body。

- [ ] 1. 测试：注册201；用户名规范化后重复409；错误密码401；Token过期401；
  明文密码不等于数据库password_hash；响应无password/hash。
- [ ] 2. 确认失败后实现Argon2、固定HS256与30分钟有效期、HTTPBearer依赖；
  400/401错误不泄露密码，也不接受JWT里夹带的owner_id权限。
- [ ] 3. 测试两用户：A创建project，B GET/PUT均404；B项目列表不含A；
  username/email以外未定义字段如owner_id传入时422。
- [ ] 4. 实现项目路由与分页，补参数边界page=0/page_size=101的422；
  依赖验证项目归属，为所有后续模块复用。
- [ ] 5. 跑auth/owner集成测试与Ruff；检查OpenAPI存在Bearer授权入口和清晰响应schema。
- [ ] 6. 更新进度并提交 feat: add authentication and owner-scoped projects。

## T04：环境、加密与secret编辑协议

依赖：T03。Files：core/crypto.py；modules/environments/*；
tests/unit/test_crypto.py；tests/integration/test_environments.py。

Interfaces：
- encrypt_json(value: JsonValue, key: str) -> str；decrypt_json(token: str, key: str) -> JsonValue。
- EnvironmentService.create/update/read；输入输出严格按C02/C03。
- GET /target-origins；allowlist helper normalize_origin(url: str) -> str。
- safe read DTO与数据库对象显式转换，不能直接model_dump ORM密文字段。

- [ ] 1. 测试环境create/read：secret原值不在响应或数据库config_ciphertext明文中；
  非secret值可读；新secret=null时422；重复name409。
- [ ] 2. 确认失败后实现Fernet配置与safe DTO；变量/header均存密文JSON；
  is_secret=false不能解除认证header遮蔽。
- [ ] 3. 测试保留/替换/移除三种操作与version冲突409；secret降级需提供新值；
  B读写A环境404，A用其他项目的environment_id也404。
- [ ] 4. 测试origin带userinfo/path/query/未允许域名时422；只有部署配置允许的origin可选。
  当前目录不生成真实.env，脚本由用户本地执行；测试用合成密钥。
- [ ] 5. 单元+环境集成+Ruff；确认日志不打印DTO的secret值，SQLAlchemy echo关闭/hide_parameters开启。
- [ ] 6. 更新进度并提交 feat: add encrypted environment configuration。

## T05：流程DSL校验与用例CRUD

依赖：T04。Files：domain/contracts.py、template.py、selectors.py；
modules/cases/*；tests/unit/test_case_schema.py、test_selector_parser.py；
tests/integration/test_cases.py。

Interfaces：
- 定义JsonScalar、JsonValue、RequestDefinition、AssertionDefinition、ExtractorDefinition、StepDefinition。
- validate_template(text: str) -> None；parse_selector(selector: str) -> tuple[str|int,...]。
- CaseService.create/update；C02/C04/C06定义字段与路由；case整体替换、乐观版本校验。
- schema验证重复id、重复extractor、路径参数集合、敏感literal、必须恰有一个状态码断言。

- [ ] 1. 用参数化测试验证20步可保存、21步422；未知type/多status断言/错误选择器/重复提取名拒绝。
  "$.items[0].id"合法；"$..id"、"$[-1]"、"$[01]"、"$[?(@.x)]"非法。
- [ ] 2. 确认失败后实现schema和受限选择器token parser；不用eval/exec/full JSONPath依赖。
  request.headers/body里的password字面量按敏感键规则拒绝，模板引用允许。
- [ ] 3. 测试整组PUT version成功+1；旧version409；请求额外字段422；
  source_api_id跨项目404，null可用；每一步源接口只是预填，不影响执行定义。
- [ ] 4. 实现列表/读/创建/更新；存steps JSONB可JSON往返；
  不允许空用例保存；未完成草稿保留在前端当前页面，不做后端草稿子系统。
- [ ] 5. 单元+cases集成+Ruff；保存后读取步骤顺序和id与输入一致。
- [ ] 6. 更新进度并提交 feat: add validated linear test cases。

## T06：OpenAPI元数据导入

依赖：T05。Files：modules/imports/*；
tests/unit/test_openapi_import.py；tests/integration/test_import_api.py；
tests/fixtures/openapi_minimal.json。

Interfaces：
- parse_openapi(content: bytes) -> ImportParseResult(operations:list[OperationDraft],warnings:list[ImportWarning])。
- OperationDraft字段与ApiDefinition一致，但不含数据库id。
- local_pointer(root: dict, ref: str, depth: int=0) -> JsonValue仅处理参数/RequestBody引用。
- POST imports/openapi与GET api-definitions，C07为完整兼容边界。

- [ ] 1. 单元测试3.0/3.1基本文档、path参数与operation参数覆盖、components本地引用。
  外部URL/file引用、循环引用、错误JSON、过深schema、超2MiB均拒绝；
  移除example/examples/default，保留schema本地$ref符号。
- [ ] 2. 确认失败后实现有界读取、遍历预算、引用校验与元数据提取；
  不能调用HTTP，也不能解析为本地文件路径。
- [ ] 3. 集成测试第一次created_count=N，第二次skipped_count=N；
  中间一个operation非法时全部回滚；并发导入同一文件不产生重复/500。
- [ ] 4. 实现upload、列表、详情与owner检查；warning指出未自动配置鉴权/业务参数；
  返回warnings最多100；上传内容不记日志。
- [ ] 5. 导入单元/集成+Ruff；检查GET接口不会回传原始上传文档或秘密示例。
- [ ] 6. 更新进度并提交 feat: import bounded OpenAPI metadata。

## T07：模板渲染、取值和断言纯逻辑

依赖：T05。Files：domain/template.py、selectors.py、assertions.py、contracts.py；
tests/unit/test_template.py、test_selectors.py、test_assertions.py。

Interfaces：
- render_value(value: JsonValue, context: Mapping[str,JsonScalar]) -> JsonValue。
- resolve_selector(document: JsonValue, selector: str) -> JsonValue；缺失抛SelectorMissing，null正常返回。
- render_request(request: RequestDefinition, context: Mapping[str,JsonScalar],
  common_headers: Mapping[str,str], origin: str) -> RenderedRequest。
- evaluate_assertions(assertions: list[AssertionDefinition], response: ResponseData,
  context: Mapping[str,JsonScalar]) -> list[AssertionOutcome]。
- extract_variables(extractors: list[ExtractorDefinition], document: JsonValue) -> dict[str,JsonScalar]。
- ResponseData是内存类型：status_code:int、headers:dict[str,str]、body_json:JsonValue|None、
  is_json:bool、elapsed_ms:float。RenderedRequest含method/url/headers/json_body与报告用path_template。

- [ ] 1. 先写精确反例：
  assert render_value("{{n}}",{"n":3}) == 3；
  assert render_value("x-{{n}}",{"n":3}) == "x-3"；
  原始输入对象不被修改；缺变量抛VariableUndefined；值中"{{x}}"不二次求值。
- [ ] 2. 实现纯渲染、path参数编码、header覆盖；禁止变量影响origin；
  保存时合法的模板在执行时仍可能缺变量，错误必须发生在transport前。
- [ ] 3. 测试resolve_selector({"x":None},"$.x") is None，缺字段抛SelectorMissing；
  数组越界明确错误；提取对象/数组禁止、secret提取null禁止。
- [ ] 4. 实现JSON深比较并测试true!=1、1==1.0、对象键顺序无关、数组顺序相关；
  404期望404为通过，耗时相等于阈值不通过。
- [ ] 5. 运行三组单元测试与Ruff；不接数据库/Redis，不需要异步fixture。
- [ ] 6. 更新进度并提交 feat: add deterministic request rendering and assertions。

## T08：有界HTTP、脱敏与线性执行器

依赖：T07。Files：domain/redaction.py、ports.py、runner.py；
infra/http_transport.py；tests/unit/test_transport.py、test_redaction.py、test_runner.py。

Interfaces：
- SecretRegistry.add(value: str) -> None；redact_json(value: JsonValue, secrets: SecretRegistry) -> JsonValue。
- HttpTransport.send(request: RenderedRequest, timeout_s: int, remaining_s: float) -> ResponseData。
- RunSink协议：start_step(position:int)->None；save_step(position:int,result:SafeStepResult)->None；
  finish(outcome:RunOutcome)->None。每方法必须原子并可抛RunNoLongerActive中止执行。
- execute_snapshot(snapshot:RunSnapshot, transport:HttpTransport, sink:RunSink,
  monotonic:Callable[[],float]) -> RunOutcome。
- RunSnapshot/RunOutcome/SafeStepResult在domain/contracts.py定义；Safe类型只含C06允许字段；
  RunSnapshot字段与设计第7节一致。配置limits冻结到快照。
- RunOutcome.status仅passed/failed/error/interrupted，包含error_code与最后完成位置。

- [ ] 1. 用HTTPX MockTransport+fake sink测试五步链、失败即停、后续skipped；
  缺变量时transport计数0；断言失败不把新变量发布到下一步。
- [ ] 2. 确认失败后实现runner；每个run独立context与Client；
  先在内存收集secret提取值用于脱敏，再存safe结果，不能把ResponseData直接交给DB。
- [ ] 3. 测试目标限制、//evil路径、302不跟随、HTTP_PROXY环境不生效、Host header拒绝；
  stream>1MiB停止并error；非JSON正文省略；POST超时仅发送1次。
- [ ] 4. 实现HTTPX sync transport：trust_env=false、follow_redirects=false、分项timeout；
  流读计时/上限；清cookie；转换异常为固定code，不使用raise_for_status判定业务通过。
- [ ] 5. 测试密码/Token在header、嵌套JSON、回显字符串、query及path中都不出现在safe输出；
  请求path仅模板、query仅键名；omit_response_body生效；
  登录断言失败时secret提取值仍遮蔽；原始body/异常不进日志。
- [ ] 6. 跑runner/transport/redaction及既有domain单元；Ruff；
  更新进度并提交 feat: add safe bounded regression runner。

## T09：运行快照与幂等提交

依赖：T04/T05/T08。Files：modules/runs/schemas.py、service.py、repository.py、router.py；
tests/integration/test_run_creation.py、test_run_idempotency.py、test_run_snapshot.py。

Interfaces：
- async create_run(db:AsyncSession, project:Project, case_id:UUID, environment_id:UUID,
  idempotency_key:UUID) -> RunCreated。
- async get_owned_run(db:AsyncSession, user_id:UUID, run_id:UUID) -> Run。
- make_snapshot(case,environment,run_id) -> RunSnapshot；完整输入加密保存。
- 同事务创建Run、StepResult(pending)、RunEvent(run.queued)、RunOutbox(pending)。

- [ ] 1. 测试POST返回202、run_id；数据库四类记录同事务出现；
  请求前校验跨项目资源、提取名与env冲突、无效origin、空case；
  缺Idempotency-Key或非UUID为422。
- [ ] 2. 确认失败后实现提交；case/env取FOR SHARE短锁冻结版本，保存前完成静态校验；
  router不调用Celery；某一数据库写入失败不能残留半个run。
- [ ] 3. 用真实PG两个独立session并发提交相同key；
  assert run_id_1 == run_id_2；assert run_count == outbox_count == 1；
  同key不同case/environment返回409；同key同请求在修改case后依然返回原run。
- [ ] 4. 创建run后更新case/env；解密快照验证仍为旧版本和旧secret；
  GET接口无snapshot_ciphertext/原始secret；不允许前端传run状态或execution_token。
- [ ] 5. 跑creation/idempotency/snapshot集成与Ruff；
  Redis关闭时仍能提交queued记录（本任务不依赖broker）。
- [ ] 6. 更新进度并提交 feat: create immutable idempotent regression runs。

## T10：Celery执行、outbox发布与中断回收

依赖：T09。Files：workers/celery_app.py、tasks.py、sink.py、dispatcher.py、reconcile.py；
modules/runs/repository.py；tests/integration/test_worker_claim.py、test_outbox.py、
test_reconcile.py、test_worker_sink.py；compose.yaml新增worker/dispatcher。

Interfaces：
- execute_run(run_id: str) -> None（Celery任务唯一参数）；内部claim返回Snapshot+execution_token。
- claim_run(run_id:UUID) -> ClaimedRun|None，queued且排队未超300秒才可CAS；其他情况无操作。
- PostgresRunSink(run_id:UUID, execution_token:UUID)，实现T08协议，更新+事件同事务。
- dispatch_due(now:datetime, publish:Callable[[str],None]) -> DispatchCounts。
- reconcile_runs(now:datetime) -> ReconcileCounts；sync可注入clock测试，不sleep等待超时。
- python -m app.workers.dispatcher运行维护loop；单实例，优雅SIGTERM退出。
- Worker入口 celery -A app.workers.celery_app:celery_app worker --loglevel=INFO --concurrency=2。

- [ ] 1. 先测两个独立DB session竞争同run只一个claim；重复execute_run不再发HTTP；
  safe sink事务失败时不留下孤立状态事件。
- [ ] 2. 实现Celery配置、解密快照、runner调用、fenced sink；
  禁用业务重试，acks_late=false，JSON serializer，ignore_result=true；
  sync engine在worker子进程懒加载，不能复用父进程连接。
- [ ] 3. 测试publisher失败时outbox pending且run queued，下一次到期可发；
  发成功但标sent失败后可再发，由claim防重复；网络调用不持数据库事务；
  retry次数递增、退避上限30秒，单次publish<=3秒。
- [ ] 4. 实现dispatcher与outbox；运行超时回收：
  queued>300秒error/DISPATCH_TIMEOUT；
  running>330秒interrupted/WORKER_INTERRUPTED；未开始步skipped；
  terminal之后迟到save_step/finish必须拒绝或无操作，不能覆盖。
- [ ] 5. 测试SoftTimeLimitExceeded尽力interrupted/RUN_TIMEOUT；硬中断由reconcile兜底；
  已发POST不重新发送；manual新run需要新key。模拟时钟，不让单元测试等330秒。
- [ ] 6. 集成测试、Ruff通过；Compose启动真实worker与dispatcher；
  记录真实broker链路至少一次run claim事件后提交 feat: execute runs through durable queue dispatch。

## T11：报告、持久化SSE与恢复

依赖：T10。Files：modules/runs/schemas.py、router.py、sse.py、repository.py；
tests/integration/test_reports.py、test_sse.py、test_run_ownership.py；infra/nginx.conf。

Interfaces：
- GET runs分页、GET /runs/{id}按C06；仅safe DTO。
- async stream_run_events(run_id:UUID, after:int, expires_at:datetime) -> AsyncIterator[str]。
- 事件数据库查询每批100/每1秒，等待时释放session；heartbeats15秒；每连接60秒。
- 前端只依赖C08，不直接依赖Celery task_id。

- [ ] 1. 测试报告步骤顺序、counts和终态一致；failed/error/interrupted不可遗留pending/running；
  B读A报告/事件404；404在SSE开始前返回标准JSON。
- [ ] 2. 实现safe报告serializer和分页；绝不能直接return ORM Run或snapshot。
- [ ] 3. SSE测试已有事件有序回放、after续读、终态先发完再关闭、无其他run事件；
  注入clock验证heartbeat、JWT到期关闭，连接断开释放DBsession。
- [ ] 4. 实现StreamingResponse与缓存禁止头；Nginx只对events关闭buffering和gzip；
  不用Token query参数、Redis Pub/Sub唯一历史或常驻占用DB连接。
- [ ] 5. API+SSE集成与Ruff；用Python/httpx带Bearer流读验证帧，不在命令行输出Token；
  确认Swagger文档与C06路径一致。
- [ ] 6. 更新进度并提交 feat: expose safe reports and resumable run events。

## T12：前端登录、项目、环境和导入

依赖：T06。Files：frontend/src/api/{client,types,auth,projects,environments,imports}.ts；
stores/auth.ts、router/index.ts、layouts/ProjectLayout.vue；对应Views与SecretField.vue；
tests/unit/{auth,secret-field,api-errors}.test.ts。

Interfaces：
- apiFetch<T>(path:string, init?:RequestInit) -> Promise<T>；
  加内存Bearer，统一处理C01错误；multipart不手工写Content-Type。
- useAuthStore()：token内存；login、logout；current_user。无持久化插件。
- SecretField组件明确mode=keep/replace/remove，不把null/星号字符串当新密码。
- importOpenApi(projectId:string,file:File) -> Promise<ImportResult>。

- [ ] 1. 配置Vitest/Vue Test Utils；测试登录后Bearer、退出清空、401回登录；
  secret默认keep，replace要求新值，remove从payload移除。
- [ ] 2. 实现API client和登录/注册/路由守卫；前端types与契约一致；
  不生成后端没有的/delete、/refresh、团队接口。
- [ ] 3. 实现项目列表/创建与ProjectLayout；环境列表/编辑；
  从target-origins选择origin；409要求重新加载；422显示具体字段。
- [ ] 4. 实现导入与接口只读表，显示created/skipped/warnings；
  使用Vue文本渲染，恶意summary不执行HTML。
- [ ] 5. typecheck、Vitest、build；连接真实API完成注册→项目→环境→导入；
  临时mock只用于组件单元测试，运行环境禁止mock service worker代替后端。
- [ ] 6. 更新进度并提交 feat: add project configuration frontend。

## T13：前端用例编辑、执行和实时报告

依赖：T11/T12。Files：api/cases.ts、runs.ts；CasesView.vue、CaseEditorView.vue、RunsView.vue、
RunReportView.vue；StepList/RequestEditor/AssertionEditor/ExtractorEditor/StepResult.vue；
composables/useRunEvents.ts；tests/unit/{case-editor,run-events,run-submit}.test.ts。

Interfaces：
- saveCase(projectId:string,payload:CaseCreate|CaseUpdate) -> Promise<CaseRead>。
- startRun(projectId:string,input:RunInput,key:string) -> Promise<RunCreated>。
- useRunEvents(runId:string)：start(after="0")、stop()、events、connectionState；
  fetch+eventsource-parser，chunk使用TextDecoder(stream=true)。
- reportStore/组件状态按event id字符串去重；只在run.finished后GET报告确认终态。

- [ ] 1. 测试编辑顺序、JSON语法错误阻止保存、数字expected不变字符串、
  断言/提取表单字段与DSL相同；添加接口不自动假定业务正确。
- [ ] 2. 实现用例列表/完整编辑器；数组上移下移；保留step UUID；
  source_api只预填请求；version冲突不静默覆盖。
- [ ] 3. 测试同次传输重试复用key，主动新执行新key，双击只提交一次；
  运行提交失败不丢失已保存用例；刷新报告不POST新run。
- [ ] 4. 实现运行列表/报告/进度；网络层分片测试中文跨UTF-8 chunk、注释心跳、
  事件重复、断线after重连、401停止、3次失败GET轮询、卸载取消；
  SSE不能触发重复通知/重复创建。
- [ ] 5. 连接真实Worker执行一条case；typecheck、Vitest、build；
  report完整展示失败原因、脱敏请求/响应和中断不确定性文案。
- [ ] 6. 更新进度并提交 feat: add case editor and live run reports。

## T14：真实Demo、完整部署与P0验收

依赖：T13。Files：demo-api/*；scripts/{seed_demo,reset_demo,smoke}.py；
frontend/e2e/*；完整Dockerfile/compose.yaml/compose.test.yaml/nginx.conf；
docs/demo.md、architecture.md、verification.md；frontend package scripts。

Interfaces：
- Demo独立FastAPI：POST /auth/login、POST/GET/DELETE /articles，GET /openapi.json；
  articles为UUID，应用SQLite /data/demo.db持久化仅用于被测演示服务；
  平台本身仍是PostgreSQL。demo每请求独立连接，不能用进程内dict冒充重启持久化。
- GET /articles/{id}受DEMO_FAULT_MODE=title_mismatch控制返回错误标题，重启demo即可切换；
  只能通过部署env设置故障，不能暴露无鉴权故障开关。
- Demo账号密码来自.env生成，不能与平台账号混淆；seed脚本通过平台HTTP API创建示例数据；
  脚本读.env不打印秘密；运行输出仅资源id与状态。seed/smoke支持 --env-file 路径，默认.env，E2E指定.env.e2e。
- env初始化支持 --e2e 生成独立.env.e2e，WEB_PORT=8088/API_PORT=8008/DEMO_PORT=8009；
  E2E使用Compose project arp-e2e隔离卷与网络，默认禁止清理开发卷。
- npm run test:e2e 从frontend执行Playwright，config固定 e2e/playwright.config.ts；
  Playwright包和tests均在frontend内，禁止依赖父目录node_modules。
- Compose实际用host变量生成端口；维护脚本及E2E base URL从配置读取，不写死开发端口。

- [ ] 1. Demo契约测试：登录、201创建、200查询、204删除、404再查；title_mismatch只影响查询标题。
  此Demo只包含验收所需接口，不开发第二个完整业务系统。
- [ ] 2. 实现Demo/seed/reset/smoke；种子生成完整五步case；
  reset只清理Demo文章并需 --confirm，绝不清平台数据库。
- [ ] 3. 完成Compose健康依赖：db/redis healthy，migrate成功，再启动服务；
  web/API/demo只绑定127.0.0.1；dispatcher无宿主端口；不暴露数据库；
  README写明.env生成、启动、查看日志与停止命令。
- [ ] 4. Playwright真实验收成功流程、错误标题失败、用户隔离；
  测试在独立arp-e2e项目，故障切换覆盖demo env后复位，不修改开发.env；
  完成A01..A20中的P0；真实强杀worker验证中断，不只mock异常。
- [ ] 5. 运行后端单元+PG集成、前端typecheck/unit/build、Playwright、smoke；
  docs/verification.md写实际日期/命令/结果/未覆盖项；截图报告成功与失败各一张。
  默认不运行会删数据的docker compose down -v；需要清理只针对明确的arp-e2e且用户授权。
- [ ] 6. 更新进度，标记P0已完成或列出阻塞；提交 test: verify end-to-end regression workflows。
  若P0未通过，不进入T15粉饰展示。

## T15：项目统计、缓存、性能证据与最终交接（P1）

依赖：T14。Files：modules/summary/*、api/summary.ts、OverviewView.vue；
tests/integration/test_summary.py；scripts/benchmark_summary.py；
docs/architecture.md、decisions.md、verification.md、demo.md、resume-notes.md。

Interfaces：
- async get_project_summary(db:AsyncSession,cache:CacheProtocol,project_id:UUID) -> ProjectSummary。
- cache key summary:v1:{project_id}，TTL30，先owner检查再查cache；
  Redis不可用回退DB，只记录固定cache error_code；不影响报告接口。
- SQL聚合终态和活动run；pass_rate分母仅passed+failed，0返回null。

- [ ] 1. 测试0次运行、混合状态、另用户404、缓存命中、过期、Redis失败回退；
  通过率：2passed+1failed+1error时为2/3，不能算2/4。
- [ ] 2. 确认失败后实现SQL GROUP BY和缓存；computed_at保留真实计算时间；
  前端标注统计最多30秒延迟；刷新统计不篡改历史报告。
- [ ] 3. 仅在隔离测试库创建1万条合成run，记录报告列表/统计EXPLAIN及响应耗时；
  不调用被测HTTP发1万次；若需索引调整用新Alembic迁移，不能只改ORM。
- [ ] 4. 完成架构、状态机、故障说明与演示文档；
  resume-notes只填写已实现与已测事实，未知指标不填，说明个人项目而非商业用户。
- [ ] 5. 运行受影响测试和最终验收命令；记录lockfiles、镜像版本、测试结果；
  检查Git无.env/Token/日志秘密，README所有命令在干净测试环境核实。
- [ ] 6. 更新进度与最终交接；提交 feat: add cached project statistics and delivery evidence。

---

## 开发中的停止条件与变更管理

- 当前任务测试失败先定位原因，不进入下一任务堆叠错误。
- 所需外部凭据/公网服务缺失时先完成可独立部分；此计划的P0不应依赖任何付费AI接口。
- 对主技术栈、状态机、API字段、秘密协议、队列语义的改动，先列证据和影响范围；
  经用户确认后同时修改spec/contracts/plan，再改代码。
- 允许修正文档中的路径或已证实版本兼容问题，但必须记录；不能以“优化”为由加新子系统。
- 不自动部署公网、不push远程、不删除卷、不改系统代理、不安装来源不明脚本。

## 计划自查与覆盖表

G1→T03/T04/T05/T06/T12/T13/T14；
G2→T07/T08/T10/T14；G3→T09/T11；
G4→T09/T10；G5→T10/T13/T14；G6→T03/T04/T08/T11/T14；G7→T14。
RF1→T09/T10；RF2→T08/T10/T14；RF3→T04/T08/T11/T14；
RF4→T11/T13；RF5→T05/T06/T07。
C01→T01/T03；C02..C05→T04/T05/T07；C06→各模块；
C07→T06；C08→T11/T13；C09→T12/T13。
计划自身是待执行文档；只有执行后才能在docs/verification.md声称功能或测试通过。
