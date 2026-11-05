# 架构说明

## 进程与职责

| 进程 | 技术 | 职责 |
|---|---|---|
| web | Vue 3 + Nginx | 同源提供 SPA；`/api/` 反代到 api；SSE 关闭缓冲 |
| api | FastAPI（async） | 认证、owner 校验、配置 CRUD、提交 run、报告、SSE |
| migrate | Alembic | 一次性 `upgrade head`；成功后 api/worker/dispatcher 才启动 |
| worker | Celery prefork | 按 run_id 原子抢占，调用 HTTPX 执行线性步骤，fenced 写结果 |
| dispatcher | Python 同步进程 | 每 2s 发布 due outbox；每 5s 回收超时 run |
| db | PostgreSQL 17 | run/step/event/outbox 与加密快照的唯一事实来源 |
| redis | Redis 7.4 | Celery broker；不配置 result backend，不作为报告事实 |
| demo-api | FastAPI + SQLite | 独立被测文章服务；数据存 `/data/demo.db` |

API 使用 SQLAlchemy `AsyncSession + asyncpg`；worker/dispatcher 使用同步 `Session + psycopg`。
两者不共享 Session、连接或已建立 Engine；worker 在子进程内懒创建 engine。

## 数据流

提交：

```text
POST /projects/{id}/runs (Idempotency-Key)
  → 校验 owner/case/env（FOR SHARE 冻结版本）
  → 构造并 Fernet 加密 RunSnapshot
  → 同一事务写 runs + step_results(pending) + run.queued 事件 + outbox(pending)
  → 202
```

执行：

```text
dispatcher 读 outbox（≤50）→ 发布 run_id 到 Redis（不持 DB 事务）
  → worker claim: UPDATE runs SET running ... WHERE status='queued' RETURNING
  → 解密快照，构造独立 context
  → 每步：渲染 → HTTPX 有界发送 → 断言 → 提取 → 脱敏 → 短事务保存 + 事件
  → finish: run CAS + 剩余步骤 skipped + run.finished
```

## 状态机

```text
run:   queued → running → passed / failed / error / interrupted
       queued → error (DISPATCH_TIMEOUT, reconcile >300s)
       running → interrupted (WORKER_INTERRUPTED, reconcile started_at+330s)
       running → interrupted (RUN_TIMEOUT, soft limit)
step:  pending → running → passed / failed / error
       未开始 → skipped
```

- 终态不可重开；所有 worker 写入带 `run_id + execution_token + status=running` 栅栏。
- 断言失败为 `failed`；渲染/网络/提取/响应超限为 `error`；进程丢失为 `interrupted`。
- 不自动重试业务 HTTP；中断后仅允许用户主动创建新 run。

## 不可变与幂等

- 快照在提交事务中冻结 case/env 版本、解密后的变量与 header、步骤、origin、limits、时间。
- 同项目同 `Idempotency-Key` 同 case/env 返回原 run；不同指纹 409；并发唯一冲突后读取原记录。
- outbox 发布成功但落库前崩溃、或 Celery 重复投递，都由 claim CAS 防止第二次执行。
- 目标服务若已收到写请求而 worker 丢失，平台不重放；报告提示写操作可能已生效。

## 秘密与脱敏

- 环境 variables/common_headers 与 run 快照整段 Fernet 加密。
- 公开 API 的 secret 只返回 `value=null,has_value=true`。
- 提取值在持久化前注册为 secret；请求/响应 header、敏感 JSON 键、已知秘密子串统一遮蔽。
- URL 只保存 origin、路径模板和 query 键名；正文预览 ≤8192 字节；响应 >1MiB 直接失败。
- JWT 只放 Authorization header，不放 URL；前端 Token 只在 Pinia 内存。

## 失败与恢复

- dispatcher 发布失败：outbox 保持 pending，固定 `BROKER_UNAVAILABLE`，退避 `min(2^n,30)`s。
- 排队 >300s 未抢占：`error/DISPATCH_TIMEOUT`，outbox abandoned。
- worker 被杀：330s 后 `interrupted/WORKER_INTERRUPTED`，运行中步骤 error，后续 skipped。
- SSE 从持久化事件按 `id > after` 回放；断线重连不丢事件；3 次失败后前端降级轮询报告。
