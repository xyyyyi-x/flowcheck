# FlowCheck 接口回归测试平台设计规格

版本：1.0；日期：2026-11-05；状态：基于已选方向的交接基线，具体默认值可在实施前由用户调整。
项目根：D:\开发学习\flowcheck。当前为空项目；本交付不包含应用实现。

## 1. 目标、使用者与可验证价值

面向个人开发者，保存自己控制的服务的接口测试流程，减少反复配置鉴权、参数和请求顺序的操作。
第一版多账号独立使用，项目只归一个 owner；团队邀请、共享与角色管理不做。
已有 Postman/pytest 等成熟方案；本项目是对明确工作流的独立工程实现，不承诺替代成熟产品或已有真实客户。

G1：浏览器完成注册、登录、项目/环境创建、OpenAPI 导入、流程编排、执行、报告查看。
G2：五步文章 CRUD 流程全通过；故障后能准确指出失败步骤，后续步骤跳过。
G3：编辑用例/环境不改变已经创建的 run；历史结果可追溯。
G4：重复提交和重复队列消息不会让同一次 run 再次发出业务请求。
G5：服务中断后不盲目重放可能生效的写操作，明确展示不确定性。
G6：另一个用户无法查看本人的环境、用例、报告或事件；秘密不出现在公开响应/报告/日志。
G7：从干净环境用文档命令启动并完成真实 E2E。

## 2. 范围与优先级

P0：
- 账号、JWT、owner 隔离；项目和环境配置。
- 本地 OpenAPI JSON 元数据导入，人工编辑请求、参数和断言。
- 线性流程、标量变量、受限选择器、三类断言。
- 不可变输入快照、后台执行、幂等抢占、可靠发布、超时中断标记。
- 持久化结果、SSE 进度、脱敏报告。
- 独立 Demo API、完整前端、Compose、集成和 E2E。

P1（P0 完整后才做）：项目统计、Redis 30 秒统计缓存、历史筛选、错误展示和简历材料。
本计划含 P1 任务；交付验收分开报告 P0/P1。

不做：AI/Agent 运行时、定时回归、团队共享、嵌套流程、循环/并行分支、任意脚本、
文件上传到被测服务、multipart/form、GraphQL、WebSocket 测试、OAuth 自动续期、Cookie 鉴权、
完整 JSONPath、全量 OpenAPI/JSON Schema 实现、URL 拉取 OpenAPI、第三方招聘数据。

## 3. 用户主流程

注册 → 登录 → 创建项目 → 新建环境（选择允许的 origin）→ 上传本地 OpenAPI JSON →
查看导入接口 → 创建用例 → 从接口添加步骤 → 编辑 body/header/path/query →
配置变量提取与断言 → 选择环境执行 → 实时看状态 → 查看历史报告。

演示用例：
1. POST /auth/login，期望 200；提取 $.access_token 为 auth_token（secret）。
2. POST /articles，携带 Bearer {{auth_token}}，标题 smoke-{{run_id}}；期望 201；提取 $.id 为 article_id。
3. GET /articles/{id}，path_params.id={{article_id}}；期望 200，$.title 等于 smoke-{{run_id}}。
4. DELETE /articles/{id}，期望 204。
5. GET /articles/{id}，期望 404（这是通过条件，不能由 raise_for_status 自动判失败）。
失败即停；不执行自动 cleanup。页面说明可能残留测试数据，Demo 提供显式 reset 命令供用户调用。

## 4. 架构选择及理由

选择模块化单体，而非微服务。API、Worker、dispatcher 是同一后端代码包的不同进程。
不选择纯 FastAPI BackgroundTasks：测试任务要与 Web 请求生命周期解耦。
不选择通用工作流引擎：线性执行足以覆盖接口回归，减少无必要复杂度。

服务与职责：
- web：Vue SPA，Nginx 同源代理 /api/；不持有数据库凭据。
- api：FastAPI；JWT、校验、owner 检查、CRUD、提交 run、查询报告、SSE。
- worker：Celery prefork；按 run_id 抢占并执行，负责 HTTP 和逐步结果持久化。
- dispatcher：单实例同步维护进程，每 2 秒处理 outbox、每 5 秒回收超时 run；不通过 Celery 调度自己。
- postgres：配置、密文快照、状态、报告、事件、outbox 的事实来源。
- redis：Celery broker；P1 统计缓存使用独立 DB 编号。禁用 Celery result backend。
- migrate：一次性运行 Alembic；成功后 api/worker/dispatcher 才启动。
- demo-api：独立文章接口，专门被测试；与平台鉴权、数据库隔离。
DB 不对宿主暴露默认端口；web 127.0.0.1:8080；api 文档 127.0.0.1:8000；demo 127.0.0.1:8001。

API 用 SQLAlchemy AsyncSession + asyncpg；Worker/dispatcher 用 SQLAlchemy sync Session + psycopg。
共用 ORM 模型与 Pydantic 契约，不共用 Session/连接/已建立 Engine。
Worker 线性 HTTP 用 HTTPX Client，无需在 Celery 内反复 asyncio.run。
每次网络请求前后用短数据库事务；禁止持有数据库事务等待被测接口响应。

## 5. 技术与版本基线

Python 3.12；Node.js 22（>=22.12）；PostgreSQL 17；Redis 7.4。
后端：FastAPI <1、Pydantic 2、SQLAlchemy 2.0、Alembic 1、Celery 5.6、HTTPX 0.28、
pydantic-settings 2、PyJWT 2、pwdlib[argon2]、cryptography。
前端：Vue 3、Vue Router 4、Pinia 3、TypeScript 5、Vite 8、Element Plus 2、eventsource-parser 3。
质量：pytest/pytest-asyncio、Ruff、Vitest、Vue Test Utils、Playwright、vue-tsc。
包管理：后端 uv（生成 uv.lock）、前端 npm（生成 package-lock.json）。

这些是项目选择的兼容范围，不声称都是最新。任务 T01 实际安装验证并记录精确版本；
如发现不兼容，先记录证据、提出最小版本调整，再统一更新文档，不能偷偷换主版本。
Docker 镜像固定上述主版本，并在交付时记录实际 image digest。禁止已提交环境继续使用 latest。
本项目不引入 Django/Flask；招聘 JD 中的加分框架不需要在同一个项目硬塞。

## 6. 数据模型

通用：UUID 主键；数据库时间 TIMESTAMPTZ UTC；API 时间 ISO8601 Z；
列表按 created_at DESC,id DESC；页码分页 page>=1,page_size=20且1..100。
业务表 foreign key 必须有索引；JSONB 只承载变动结构，权限/关联/状态用普通列。
ORM 声明统一导出给 Alembic；生产启动不使用 create_all。

users：id, username（小写规范化后唯一，3..32，字母数字下划线）, password_hash, created_at。
projects：id, owner_id FK users, name（1..80）, description（<=500）, created_at, updated_at。
environments：id, project_id, name, base_url, config_ciphertext TEXT, version INT>=1, timestamps；
  UNIQUE(project_id,name)。密文里是 variables 与 common_headers；读取采用专用脱敏 DTO。
api_definitions：id, project_id, method, path, summary, parameters JSONB, request_body_schema JSONB, created_at；
  UNIQUE(project_id,method,path)。导入遇到已存在接口跳过，不覆盖已有资料。
cases：id, project_id, name, description, version INT>=1, steps JSONB, timestamps。
  case 是完整聚合；PUT 全量更新并携带 version；旧 version 返回 409。
runs：id, project_id, case_id, environment_id, case_name, case_version, environment_name, environment_version,
  status, snapshot_ciphertext, idempotency_key, request_fingerprint, execution_token NULL,
  created_at, started_at NULL, finished_at NULL, deadline_at NULL, error_code NULL。
  UNIQUE(project_id,idempotency_key)；索引(project_id,created_at DESC,id DESC),(status,created_at)。
step_results：id, run_id, position INT1..20, name, status, elapsed_ms NULL,
  request_safe JSONB NULL, response_safe JSONB NULL, assertions_safe JSONB, extracts_safe JSONB,
  error_code NULL, started_at NULL, finished_at NULL；UNIQUE(run_id,position)。
run_events：id BIGINT 全局递增, run_id, event_type, payload_safe JSONB, created_at；
  索引(run_id,id)。事件不存请求/响应正文或变量原值。
run_outbox：id, run_id UNIQUE, status=pending/sent/abandoned, attempt_count, next_attempt_at,
  last_error_code NULL, created_at, sent_at NULL。
  仅待发送消息；payload 固定为 run_id。dispatcher 每次处理<=50条。
不做物理删除：P0 只创建、读取、更新项目/环境/用例，避免外键删除和历史丢失；
页面与 API 不提供删除按钮/端点。Demo 的文章删除是被测业务，与平台数据管理不同。

## 7. 配置、秘密与报告

APP_JWT_SECRET 随机>=32字节；JWT HS256，sub=user UUID，exp=30分钟，iat；
只接受固定算法、有效用户和未过期 Token。密码 8..128字符，Argon2。
注册与登录错误不包含原密码；用户名重复409；错误密码401；无刷新Token；退出仅清除前端内存。
注册路由仅用于本地演示，不宣称具备公网账号滥用防护。平台不默认公网部署。

APP_ENCRYPTION_KEY 为 Fernet key；API/Worker 使用同一部署密钥；
环境配置与完整 run 输入快照都加密。密钥缺失/非法时启动失败；密钥不进仓库或日志。
密钥轮换不在 P0，README 说明丢失密钥无法解密旧配置/快照。

环境变量：name,value,is_secret；仅 JSON 标量；secret 必须是非空字符串。
公共 header：name,value,is_secret；value 是字符串，可含模板；认证 header 强制 is_secret=true。
GET 返回 secret 的 value=null,has_value=true。PUT 中同名 secret value=null 表示保留；
给新值表示替换；全量列表里省略该项表示删除。首次创建 secret null 必须422。
密码/Token 不写死在用例 literal，必须引用 secret 环境变量。
若 body 中 password/token/access_token/refresh_token/api_key/client_secret/secret 等敏感键出现非模板字面量，
保存用例时422，提醒放入环境变量。该规则不是任意秘密检测器。

Run 快照包含：schema_version=1、case/env名称和版本、已冻结steps、解密配置、target_origin、limits。
运行时从密文构造内存上下文，不能读取最新环境。公开 API 不返回原始快照。
编辑环境不能影响排队中的快照。run_id 是预置字符串变量；用户不能定义同名变量。

脱敏流程：
- 注册所有环境 secret、敏感公共 header 原值、secret 提取结果；提取发生在报告持久化之前。
- 大小写不敏感遮蔽 Authorization、Proxy-Authorization、Cookie、Set-Cookie、X-API-Key。
- 递归遮蔽敏感 JSON 键（同上敏感键集合）和已知秘密字符串出现的位置。
- URL 仅显示 origin、path 模板和 query 键名；不显示 query 值或渲染后的 path 参数值。
- 非 JSON 响应正文省略；JSON 完整解析后脱敏，再截成<=8192字节预览。
- 响应超过1MiB直接失败，正文省略；不得把未脱敏截断JSON当文本存储。
- error message 使用固定用户文案+error_code，不持久化 str(httpx异常) 或完整堆栈。
- 日志仅记录 request_id/run_id/step_position/error_code/duration，不记录请求体、查询字符串、Token或密文原值。
秘密替换不能保证识别未知的业务敏感信息；演示仅使用合成数据，不在简历中声称“绝不泄露任意数据”。

## 8. 执行语义

模板、提取、断言与 HTTP 契约详见 docs/contracts/api-v1.md。
每用例1..20步；每步至少一个 status_code 断言；method仅GET/POST/PUT/PATCH/DELETE。
同一步：渲染请求与期望值 → 发HTTP → 有界读取响应 → 计算断言 → 断言通过后提取变量 →
注册秘密并脱敏 → 事务保存结果及事件 → 下一步。
即使断言失败，仍可为脱敏收集标为secret的提取值，但不得将它们发布给下一步执行上下文。
运行context独立；同名extractor跨步骤不允许；与env变量冲突在提交run前422。
同一run不重试HTTP；不同run可并发。HTTP状态>=400不自动失败，由断言决定。
断言失败=failed；渲染/网络/提取/响应超限=error；进程丢失=interrupted。后续步骤skipped。

HTTP：
- base_url 只允许部署者 TARGET_ORIGINS 配置的 exact origin（scheme,host,port），无路径/凭据/query/fragment。
- 默认唯一 http://demo-api:8001；UI显示这是 Worker 可达地址，不是浏览器 localhost。
- 步骤path必须以单个/开头的相对路径模板，无scheme/host/query/fragment；禁点路径与CRLF。
- 从origin+相对path构造请求；渲染后再次检查origin；禁止修改Host、Content-Length、Connection、Transfer-Encoding。
- follow_redirects=false；trust_env=false；TLS默认验证；不提供关闭验证开关。
- 每步清空client cookie，鉴权只用显式header。
- timeout_s默认10且1..30，是HTTPX connect/read/write/pool分项超时，不宣称绝对总耗时。
- connect=min(timeout_s,3)，其余timeout_s；请求体JSON<=64KiB，响应有界流读<=1MiB。
- run最长300秒；每步开始和读取chunk检查单调时钟预算；Celery soft310/hard330秒兜底。
- 最终origin允许不等于解决所有SSRF；部署者只应加入可信且受控的服务域名，不开放公共请求代理。

## 9. 状态、并发与可靠性

run：queued → running → passed / failed / error / interrupted。
queued只能转running或error（DISPATCH_TIMEOUT）。全部终态不可重开。
step：pending → running → passed/failed/error；未开始的变skipped；中断时正在执行步error。
run终态时不得留下pending/running步骤。状态码与用户文案映射固定在contracts。

提交：
1. 校验owner、case/environment同项目、case有效、变量冲突与目标合法。
2. 同一事务插入run密文快照、pending步骤、queued事件、outbox pending。
3. 返回202；不在HTTP事务中调用Redis。入队失败不让API假装执行完成。

幂等：
- POST /runs 必须有 Idempotency-Key（UUID）。
- 同项目同key同case/environment：返回原run，标识reused=true，不重建快照。
- 同key不同请求指纹409；并发唯一冲突后读原记录比较；环境/用例已编辑不改变同key含义。
- UI一次点击生成一个key；传输重试复用key；用户主动再次运行生成新key。

dispatcher：
- 单实例循环，每2秒发布due outbox，成功后标sent；网络调用不持有DB事务。
  发前检查run仍queued且未过排队期限；已过期项不发布，交给reconcile终结。
- 发布异常只写固定BROKER_UNAVAILABLE并增加attempt；退避min(2^attempt,30)秒；
  publisher内部禁无限重试（每次尝试<=3秒），防止维护循环永久阻塞。
- publish成功但落库前崩溃可导致重复消息；允许重复。
- Worker原子UPDATE status=queued→running RETURNING成功后才发HTTP；条件还需created_at未超过300秒；同时生成execution_token。
- running/终态的重复消息直接退出。只有第一次抢占者允许创建started事件。
- 所有worker落库使用run_id+execution_token+status=running栅栏；过期写入丢弃，不覆盖终态。

Celery：JSON序列化、ignore_result=true、acks_late=false、worker_prefetch_multiplier=1、
concurrency=2、无autoretry_for、无业务task.retry、task_reject_on_worker_lost=false。
这些不提供跨网络exactly-once；目标服务收到请求但平台未收到响应时，结果可能不确定。

reconcile每5秒：
- queued超过300秒且尚未抢占 → error/DISPATCH_TIMEOUT；outbox abandoned，全部步骤skipped。
- running超过started_at+330秒 → interrupted/WORKER_INTERRUPTED；
  running步error，未开始步skipped；终态事件同事务写入。
- soft超时由worker尽力终结为interrupted/RUN_TIMEOUT；进程被杀由reconcile兜底。
- 所有更新CAS，不能把刚刚完成的run改回错误。
- 中断后仅允许创建新run；禁止自动续跑/重新发送；页面提示“部分写操作可能已生效”。

## 10. 事件、报告、统计

每次状态更新与相关run_events写入同一事务。event ID是数据库BIGINT。
SSE通过fetch Authorization Bearer读取；按run_id与id>after查询，每批<=100，每1秒查一次；
每次短Session并关闭，等待时不占数据库连接。无事件每15秒发注释heartbeat。
连接最多60秒后关闭，客户端带最新游标重连，最多3次连续失败后用GET报告每2秒轮询兜底。
有事件收到时重置失败次数；组件卸载AbortController取消；401停止并要求登录。
JWT在握手校验，流打开期间每轮检查exp并在到期关闭；不能在流已开始后发JSON错误。
终态的全部剩余事件发送完后关闭；前端收到run.finished再GET报告确认并停止重连。
GET报告始终能恢复最终状态；日志事件可重复送达，UI按event_id去重；顺序以ID为准。
重连参数after>=0；客户端发送自己的最后事件ID；返回只属于本run的事件。无Redis Pub/Sub依赖。
Nginx /api/.../events关闭buffering、压缩，proxy_read_timeout>=75秒。

P1统计GET /projects/{id}/summary：
total_runs（所有），passed_runs，failed_runs，error_runs，interrupted_runs，active_runs，
pass_rate=passed/(passed+failed)，分母0返回null；infrastructure error不计业务通过率分母。
仅该owner项目；缓存key=summary:v1:{project_id}，TTL30秒，Redis异常退回数据库。
允许最多30秒统计陈旧；UI明确数据更新时间。报告不走缓存。
查询要包含真实GROUP BY统计；不得加载全部历史到Python计算。索引与EXPLAIN用实测说明。

## 11. 前端体验与页面

中文界面；桌面>=1280宽可操作，窄屏不承诺完整流程编辑体验但不得遮挡登录和报告关键信息。
轻量Element Plus表单与表格，无拖拽画布。
页面：注册/登录；项目列表；项目概览；环境；接口列表与导入；用例列表/编辑；运行列表/报告。
步骤编辑：上下移动、增删、请求参数JSON编辑、断言列表、提取列表。保存前JSON语法检查；
后端校验为最终依据。刷新页面重新登录，但已保存配置不丢失。
SSE只是实时展示；刷新报告依然完整。secret显示“已配置”，编辑明确保留/替换/移除。
异步按钮显示提交中，避免重复点击；网络失败保留Idempotency-Key供重试。
接口文本按普通文本渲染，不用v-html；用例期望值输入JSON以区分数字/字符串/null。
表单冲突409提示重新加载后再编辑，不静默覆盖。空态、加载态、422字段错误、401、404均有文案。

## 12. 质量、验收与交付

完成条件看 docs/handoff/acceptance.md 的A01..A20。
单元测试覆盖渲染/选择器/断言/导入/脱敏；集成用真实PostgreSQL；Celery/Redis真实链路单独验收；
Playwright至少成功流程、故障流程、用户隔离三条。
不强行追求覆盖率数字；核心状态机、去重、秘密、身份边界必须有反例测试。
不承诺未经测量QPS。性能实验记录环境、数据量、并发、版本及原始结果。
提交.env.example、lockfiles、迁移、截图/演示步骤、架构说明和真实测试结果。不得编造业务量或用户量。

## 13. 与招聘 JD 对应

FastAPI路由/DI/Pydantic/中间件/JWT/OpenAPI → API与认证；
SQL/索引/事务/分页/联表/聚合 → 项目资源、状态事务、报告和统计；
异步 → API数据库与SSE；任务队列 → Celery/outbox；
异常/日志 → 错误分类及关联ID；
Docker/Linux → Compose多进程部署、健康检查与故障诊断；
AI开发工具 → 保存需求、阶段提示词、实际纠错记录，不必把Agent强加进产品。

## 14. 参考资料与证据范围

以下官方文档用于验证框架机制；业务规则、默认上限和状态机是本项目设计决定。
- FastAPI JWT/密码哈希：https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/
- SQLAlchemy Session并发边界：https://docs.sqlalchemy.org/en/20/orm/session_basics.html
- Celery任务与ack：https://docs.celeryq.dev/en/stable/userguide/tasks.html
- Vite运行环境：https://vite.dev/guide/
- OpenAPI 3.1.1：https://spec.openapis.org/oas/v3.1.1.html
- EventSource构造能力：https://developer.mozilla.org/en-US/docs/Web/API/EventSource/EventSource
- Compose健康依赖：https://docs.docker.com/compose/how-tos/startup-order/
- 成熟工作流参照：https://learning.postman.com/latest-v-12/docs/tests-and-scripts/running-collections/scheduling-collection-runs
