# FlowCheck 简历与面试要点（只写已实现、已测试的事实）

## 一句话

个人全栈项目：FlowCheck 接口回归测试平台。保存线性 HTTP 流程，由后台 Worker 在代码变更后真实执行，
通过可恢复 SSE 展示进度，并用不可变快照与脱敏报告保留历史结果。

## 技术栈（实际使用）

FastAPI / Pydantic 2 / SQLAlchemy 2（async API + sync worker）/ Alembic /
PostgreSQL 17 / Celery 5.6 / Redis 7.4 / HTTPX / Fernet / PyJWT+Argon2 /
Vue 3 + TypeScript + Vite 8 + Element Plus / Docker Compose / pytest / Vitest / Playwright。

## 可讲清楚的工程点

1. **异步边界**：API 用 AsyncSession + asyncpg；Worker/dispatcher 用同步 Session + psycopg，
   不共享 Session/连接；worker 子进程懒创建引擎，避免 fork 复用父进程连接池。
2. **幂等提交**：`Idempotency-Key` + `(project_id,idempotency_key)` 唯一约束；
   并发冲突后读取原 run；同 key 不同请求指纹 409；编辑 case/env 不改变已提交 run。
3. **可靠发布**：事务内写 outbox；dispatcher 每 2 秒批量发布，网络调用不持数据库事务；
   失败固定错误码与指数退避；重复投递由 Worker 的 CAS 抢占挡住。
4. **执行状态机**：queued→running→终态；步骤 pending→running→终态；失败即停，后续 skipped；
   最终状态、步骤、事件在同一事务；Worker 写入带 `execution_token` 栅栏，过期写入拒绝。
5. **中断处理**：软超时尽力终结；进程被杀后由 reconcile 在 330 秒后标记 interrupted，
   不重放可能已生效的写请求，页面明确提示不确定性。
6. **不可变快照**：完整输入（解密后的变量/header、步骤、origin、limits）Fernet 加密保存；
   历史报告不受后续编辑影响。
7. **秘密与脱敏**：secret 只写不读；持久化前注册已知秘密并遮蔽 header/JSON 键/回显内容；
   URL 只保留 path 模板与 query 键名；响应 >1MiB 失败；正文预览 ≤8192 字节。
8. **SSE**：事件持久化在 PostgreSQL，按自增 id 游标回放；fetch+JWT+AbortController；
   15 秒心跳、60 秒连接上限、断线 after 续读，3 次失败降级轮询报告。
9. **有界 HTTP**：部署配置的 exact origin 白名单；不跟随重定向、trust_env=false；
   禁止 Host 等受限 header；单次发送不重试；状态码 >=400 由断言决定成败。
10. **受限导入**：本地 OpenAPI 3.0/3.1 JSON，本地 $ref 深度 8、节点/深度预算、
    外部引用整份拒绝；先完整校验再事务写入，重复/并发导入 skip。
11. **统计与索引**：SQL GROUP BY；通过率分母只含 passed+failed；30 秒 Redis 缓存，
    Redis 异常回退数据库；主人检查先于缓存。

## 实测数据（2026-11-05，Windows 11 + Docker Desktop）

- 后端：193 passed（115 unit + 78 integration，真实 PostgreSQL 17）。
- Compose 隔离集成：`docker compose ... run --build --rm test`。
- Demo API：4 passed（含 SQLite 重启持久化与故障标题）。
- 前端：typecheck 通过；Vitest 25 passed；Vite build 成功。
- Playwright：3 passed（成功流程、断言失败、用户隔离），使用系统 Chrome。
- 合成数据基准（隔离 test 库，10,000 runs）：
  - 统计 GROUP BY 平均 4.18 ms；
  - 运行列表第一页平均 4.27 ms；
  - 计划使用 `ix_runs_project_created`。
- 真实链路：API → outbox → dispatcher → Redis → Celery → demo HTTP → PostgreSQL → 报告/SSE；
  五步文章 CRUD 全部 passed；故障注入时第 3 步 failed、4/5 skipped。

以上为本机测量，不代表线上用户量或吞吐；项目是个人学习/求职项目，没有真实客户。

## 限制

- 仅线性流程、标量变量、受限选择器；不支持 AI 判定、DAG、定时任务、团队协作、任意脚本。
- 结果不确定的写请求不会被自动判定是否生效，也不会自动补偿。
- 未做公网部署与大规模并发压测。

## 面试常问

- 为什么 async API 与 Celery 是两种不同并发机制？
- 数据库提交成功为什么不等于消息已发布？outbox 解决什么？
- task_id 为什么不足以防重复执行？CAS 抢占与 execution_token 栅栏如何工作？
- 为什么不自动重试写请求？Worker 被杀后为什么不能续跑？
- 快照解决了什么追溯问题？密文快照与公开报告的区别？
- SSE 如何认证、续读、降级？刷新为什么不会丢最终报告？
- 脱敏为什么必须发生在持久化前？URL 与 query 如何最小化？
- 分页/索引/通过率分母如何选择？EXPLAIN 实测结果是什么？
