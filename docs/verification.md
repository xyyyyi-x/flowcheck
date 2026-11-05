# FlowCheck 验证记录

验证日期：2026-11-05（Asia/Shanghai）
代码版本：`6a478f8`（T01–T15 共 15 个任务提交 + 最终文档提交，`git log --oneline` 可复查）
最终复跑：以最新代码重建开发 Compose（`docker compose up -d --build`），
seed 幂等复用原项目/环境/用例，smoke 再次 `run_status=passed`（五步），
Web 代理 `/api/v1/health/live` 返回 200。
OS：Windows 11 Home China 10.0.26200
Python：3.12.16（uv 管理；宿主另有 3.14，仅用于运行 uv/标准库脚本）
Node：24.22.1；npm 11.19.1
Docker：29.9.2；Docker Compose v5.6.1
后端依赖 lockfile：`backend/uv.lock`（镜像源 https://pypi.tuna.tsinghua.edu.cn/simple）
前端 lockfile：`frontend/package-lock.json`

镜像（RepoDigest）：
- postgres:17-alpine `postgres@sha256:266d3c257594e195b309ae9d1805e54c788f1d7b375f56bf6c367aac6c917e7b`
- redis:7.4-alpine `redis@sha256:8da19c7399dca900c6822a1cf30f9d2285585e2c4b457ff4095b0f4500054d3f`
- python:3.12-slim `python@sha256:b18b261e1b4974b4f321451ad5251ded85abb22c2b8b262da527dda1d031ab30`
- node:24-alpine `node@sha256:8a32c8cf649a49915a66e81e7a609223c708d0adabf288ee3f4077d765542f85`
- nginx:1.29-alpine `nginx@sha256:5616878291a2eed594aee8db4dade5878cf7edcb475e59193904b198d9b830de`

> 未提交本地 `.env` / `.env.e2e`；本文件不包含任何真实密码、Token 或密钥。

## 一、测试命令与结果

### 后端（宿主 + 真实隔离 PostgreSQL）

```powershell
cd backend
uv sync --frozen
$env:APP_TEST_DATABASE_URL="postgresql+psycopg://test:test@127.0.0.1:55488/test"
uv run pytest tests/unit tests/integration -q
uv run ruff check .
uv run ruff format --check .
```

实际结果：`193 passed`（115 unit + 78 integration）；Ruff 全部通过；format 106 files 通过。
测试库为独立容器 `arp-test-db`（PostgreSQL 17.5）与 `arp-test-redis`，不连接开发库。

### Compose 隔离集成（test-db/test-redis）

```powershell
docker compose -f compose.yaml -f compose.test.yaml run --build --rm test pytest tests/integration -q
```

实际结果：`78 passed`（T15 后复跑）。

### 统计查询基准（隔离 test 库）

```powershell
cd backend
$env:APP_TEST_DATABASE_URL="postgresql+psycopg://test:test@127.0.0.1:55488/test"
uv run python ../scripts/benchmark_summary.py
```

实际结果（10,000 条合成 runs）：
- 统计 GROUP BY 平均 **4.18 ms**；运行列表第一页平均 **4.27 ms**；
- 计划使用 `ix_runs_project_created`（Bitmap Index Scan + GroupAggregate / top-N Sort）；
- 脚本结束删除全部合成 user/project/case/env/run。

### Demo API

```powershell
cd demo-api
uv run pytest tests -q
```

实际结果：`4 passed`（登录、CRUD、404、故障标题、SQLite 重启持久化）。

### 前端

```powershell
cd frontend
npm run typecheck
npm run test:unit -- --run
npm run build
```

实际结果：typecheck 通过；Vitest `6 files / 25 tests passed`；Vite build 成功。

### 开发 Compose 真实链路

```powershell
python scripts/init_env.py
docker compose up --build -d
python scripts/seed_demo.py
python scripts/smoke.py
```

实际结果：
- 全部服务 healthy；worker 连接 `redis://redis:6379/0`。
- smoke：`run_status=passed`，五步全部 passed（真实 HTTP：API→outbox→dispatcher→Redis→Celery→demo-api→PostgreSQL）。
- 本机 8001 被其他项目容器占用，开发 `.env` 使用 `DEMO_PORT=18001`；默认仍为 8001。

### 故障断言（真实 Demo 故障注入）

```powershell
# .env: DEMO_FAULT_MODE=title_mismatch; docker compose up -d demo-api
python scripts/smoke.py
```

实际结果：`run_status=failed / ASSERTION_FAILED`；step1 passed、step2 passed、
step3 failed、step4/5 skipped。随后恢复 `DEMO_FAULT_MODE=` 并重建 demo-api，
`reset_demo.py --confirm` 清空 Demo 残留文章 1 条。

### Playwright（真实浏览器 + 独立 arp-e2e）

```powershell
python scripts/init_env.py --e2e
docker compose --project-name arp-e2e --env-file .env.e2e up --build -d
python scripts/seed_demo.py --env-file .env.e2e
python scripts/smoke.py --env-file .env.e2e
cd frontend
npx playwright install chromium          # 本机下载停滞，未完成
$env:E2E_BROWSER_CHANNEL="chrome"        # 改用本机已安装 Chrome（真实浏览器）
npm run test:e2e
```

实际结果：
- arp-e2e 栈健康，smoke `run_status=passed`（五步）。
- Playwright：`3 passed`（happy / failure / isolation）。
- 浏览器：系统 Chrome（channel=chrome）。Chromium 1248 下载在本机网络下超过 10 分钟未完成，
  因此未使用 Playwright 自带 Chromium；这是唯一未按默认方式执行的检查。

### Worker 强杀与 reconcile

执行 `scripts/interrupt_demo.py --confirm`（写入后延迟响应，确认运行中步骤后 kill arp-e2e worker）。
实际结果：`reconcile 完成，实际等待 336.4s`；
run=interrupted / WORKER_INTERRUPTED；step1 passed、step2 error(WORKER_INTERRUPTED)、step3–5 skipped。
重启 worker 后日志只有 ready，没有重放旧 run；Demo 数据清理显示 2 条文章
（一条来自 Playwright 失败用例，一条来自被杀 worker 已发出但未收到响应的写请求），
与“写操作可能已生效”的提示一致。

### Redis 短时停机与恢复

执行 `scripts/redis_outage_demo.py --confirm`（停止 arp-e2e redis → 提交 run → 恢复）。
实际结果：
- 提交后与 6 秒后 run 均为 `queued`；
- outbox `attempt_count=1 / BROKER_UNAVAILABLE`；
- Redis 恢复后 dispatcher 补发，五步全部 passed。

调试记录：首次测试发现 Celery producer 连接重试会让单次发布阻塞超过 6 秒；
为 dispatcher 增加 3 秒线程级发布超时，并用 `task_publish_retry=False` +
`retry_policy.max_retries=0` 收紧。复测 outbox 在 6 秒内记录失败与退避。

### 截图

- `docs/screenshots/run-passed.png`：五步全部通过，Authorization/password/token 已脱敏。
- `docs/screenshots/run-failed.png`：第 3 步断言失败，第 4/5 步已跳过。

## 二、验收矩阵

| 编号 | 结果 | 证据/说明 |
|---|---|---|
| A01 | 通过 | 注册/登录/错误密码/过期与伪造 JWT 集成测试；前端 401 清 Token 单测与 Playwright 重新登录 |
| A02 | 通过 | 项目/环境/用例/API 定义/run/报告/SSE owner 404 测试；Playwright 隔离 |
| A03 | 通过 | 环境 secret 保留/替换/移除、首次 null 422、密文无明文、GET 脱敏 |
| A04 | 通过 | OpenAPI 3.0/3.1 导入、重复 skip、坏文档整批拒绝、外部/循环引用与大小/深度/节点限制、并发导入 |
| A05 | 通过 | 1/20/21 步、顺序保持、旧 version 409、未知字段、非法 selector、敏感 literal |
| A06 | 通过 | 整段模板保留类型、嵌入转字符串、null/缺字段区分、true != 1、缺变量 HTTP 前失败 |
| A07 | 通过 | 真实 Compose 五步 passed；404 作为期望通过 |
| A08 | 通过 | 真实故障注入：第 3 步 failed，4/5 skipped；Playwright failure 场景 |
| A09 | 通过 | 网络/提取/非 JSON 错误码单测；终态无 pending/running；counts 相加=total |
| A10 | 通过 | 并发提交同 key 单 run/outbox；不同指纹 409；编辑 case 后仍复用原 run |
| A11 | 通过 | 两独立 Session 竞争 claim 仅一个；重复消息不执行；真实 worker 链路 smoke |
| A12 | 通过 | 创建后修改 case/env，解密快照仍为旧版本/旧 secret |
| A13 | 通过 | 真实 Redis 停机：run 保持 queued、outbox 记 BROKER_UNAVAILABLE，恢复后补发并五步 passed；300s 超时用注入时钟测试 |
| A14 | 通过 | 真实 kill arp-e2e worker，336.4s 后 interrupted/WORKER_INTERRUPTED；step2 error、3–5 skipped；重启不重放 |
| A15 | 通过 | 报告/事件防泄漏单测；SSE/报告仅 safe 字段；日志不记录请求体/Token |
| A16 | 通过 | origin 白名单、Host 拒绝、302 不跟随、trust_env=false、>1MiB 中止、非 JSON 省略 |
| A17 | 通过 | 事件回放/after 续读/心跳/过期关闭/401/404；前端分片解析、去重、3 次失败轮询单测 |
| A18 | 部分通过 | Playwright 覆盖登录/执行/报告/失败/隔离/刷新重新登录；窄屏未做完整流程验证 |
| A19 | 通过 | 干净 arp-e2e Compose 项目启动、迁移与健康依赖、真实 PostgreSQL/Redis/Worker/Demo、lockfile |
| A20 | 通过 | 5 个 summary 集成测试：0 次、混合状态 2/3、owner 404、缓存命中/TTL/删除、Redis 故障回退；10k 基准见上 |

## 三、未覆盖项与风险

1. Playwright 自带 Chromium 未下载成功，改用系统 Chrome；两者均为真实浏览器，但版本记录不同。
2. 窄屏（<1280px）只保证不遮挡登录与报告关键信息，未做完整 E2E。
3. 真实 Redis 短时停机恢复已验证；300 秒 DISPATCH_TIMEOUT 未真实等待，使用注入时钟测试。
4. 未做公网部署、未 push 远程、未清理开发数据卷。
5. 目标服务收到写请求但响应丢失的“结果不确定”只能提示，无法由平台判定是否已生效。
6. 性能/并发未做 QPS 测量，不声称任何吞吐指标。

## 四、追加记录

- Worker 强杀：336.4s 后 interrupted，step2 error，3–5 skipped；恢复 worker 不重放。
- Redis 停机：queued + outbox attempt=1/BROKER_UNAVAILABLE；恢复后补发并 passed。
- 统计接口在 arp-e2e 实测：首次 cache_hit=false，第二次 cache_hit=true，通过率 1.0
  （4 passed / 4+0；另有 1 interrupted 不计入分母）。

## FlowCheck 命名与目录迁移复核（2026-11-05）

项目已从旧目录迁移至 D:/开发学习/flowcheck，.git与本地.env保留，旧目录不再存在。
网页、API文档、包元数据与项目文档统一FlowCheck；Compose仍使用arp-dev部署标识以沿用数据卷。
Python lockfile逐包对比确认仅项目名变化，依赖版本、来源及哈希保持一致。

本次实际执行：
- backend：python -m uv run --frozen --no-sync pytest tests/unit -q → 115 passed。
- demo-api：python -m uv run --frozen --no-sync pytest tests -q → 4 passed。
- frontend：npm run test:unit -- --run → 25 passed。
- Ruff、前端生产构建、docker compose config --quiet通过。
- Docker Desktop曾在镜像导出/容器替换期间失去响应；官方正常重启后再次卡住，
  经用户明确授权结束本次构建客户端和Desktop/backend后重新启动恢复。
- 使用已构建镜像执行docker compose up -d --no-deps api web成功，不再重复构建。
- GET http://127.0.0.1:8080/ → 200，title=FlowCheck · 接口回归测试平台。
- GET http://127.0.0.1:8000/openapi.json → 200，info.title=FlowCheck · 接口回归测试平台。
- python scripts/smoke.py → run 4af5c77c-978c-485d-9509-813cf0995bf1，五步全部passed。

目录移动后原本地虚拟环境启动器引用旧绝对路径，已仅重建backend/.venv与demo-api/.venv并用冻结依赖恢复。
未删除数据库/其他数据卷，未重置WSL，未更改测试目标或登录凭据。
本次未重跑完整集成/Playwright/强杀实验；这些结果仍以之前对应记录为准。
