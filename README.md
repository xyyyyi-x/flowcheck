# 接口回归测试平台

为个人开发者保存可复用的 HTTP 接口流程，在代码修改后由后台 Worker 真实执行，
实时展示进度并保留不可变的历史报告。

技术栈：FastAPI + Pydantic 2 + SQLAlchemy 2 + Alembic + PostgreSQL 17；
Celery 5.6 + Redis 7.4；Vue 3 + TypeScript + Vite + Element Plus；Docker Compose。

> 完成状态、实际测试结果与未覆盖项以 [docs/progress.md](docs/progress.md) 和
> [docs/verification.md](docs/verification.md) 为准，不以“应该能运行”代替验证。

## 目录

- `backend/`：FastAPI API、Celery Worker、dispatcher、Alembic 迁移、pytest。
- `frontend/`：Vue 3 单页应用、Vitest 单测、Playwright E2E。
- `demo-api/`：独立文章 Demo API（SQLite 持久化，仅作为被测服务）。
- `scripts/`：环境初始化、演示数据、smoke 与 Demo 数据重置。
- `docs/`：设计规格、API 契约、计划、验收、架构、演示与验证记录。

## 前置条件

- Python 3.12（宿主可用 uv 安装：`uv python install 3.12`；本仓库 `backend/.python-version` 固定 3.12）
- Node.js >= 22.12（本机实际 Node 24）
- Docker Desktop / Docker Compose v2
- 首次构建会从配置的镜像源下载依赖；默认使用清华 PyPI 镜像与 npmmirror。

## 1. 生成环境文件

```powershell
python scripts/init_env.py
```

- 生成 `.env`（含随机数据库密码、JWT secret、Fernet key、Demo 密码），拒绝覆盖已有文件；
- 不向 stdout 打印秘密；
- 若宿主端口冲突，可编辑 `.env` 的 `WEB_PORT` / `API_PORT` / `DEMO_PORT`
  （数据库与 Redis 不映射宿主端口）。

## 2. 启动

```powershell
docker compose config --quiet
docker compose up --build -d
docker compose ps
```

默认入口：

| 服务 | 地址 |
|---|---|
| Web | http://127.0.0.1:8080 |
| API 文档 | http://127.0.0.1:8000/docs |
| Demo API | http://127.0.0.1:8001 |
| Demo OpenAPI | http://127.0.0.1:8001/openapi.json |

健康检查：`GET /api/v1/health/live`、`GET /api/v1/health/ready`。
迁移服务成功后 api/worker/dispatcher 才启动；worker 同时依赖 demo-api 健康。

## 3. 演示数据与 smoke

```powershell
python scripts/seed_demo.py
python scripts/smoke.py
```

`seed_demo.py` 通过平台 HTTP API 幂等创建：演示用户、项目“文章回归 Demo”、
环境“Compose Demo”、五步用例“文章回归五步”。平台演示账号与 Demo 服务账号分开，
密码均在 `.env` 中（`PLATFORM_DEMO_*` 与 `DEMO_*`）。

`smoke.py` 提交一次真实 run，轮询报告并打印每一步状态；全通过时退出码为 0。

浏览器操作：登录 → 进入演示项目 → 运行记录 → 执行用例。

## 4. 测试

后端单元与真实 PostgreSQL 集成（宿主机需要 test 库 URL）：

```powershell
cd backend
uv sync --frozen
uv run pytest tests/unit -q
$env:APP_TEST_DATABASE_URL="postgresql+psycopg://test:test@127.0.0.1:55488/test"
uv run pytest tests/integration -q
uv run ruff check .
uv run ruff format --check .
```

如果本机没有 `uv` 命令，使用 `python -m uv ...`（本仓库验证时即如此）。

Compose 隔离集成测试（test-db/test-redis，不映射宿主端口）：

```powershell
docker compose -f compose.yaml -f compose.test.yaml run --rm test pytest tests/integration -q
```

前端：

```powershell
cd frontend
npm ci
npm run typecheck
npm run test:unit -- --run
npm run build
```

## 5. E2E（独立 arp-e2e Compose 项目）

```powershell
python scripts/init_env.py --e2e
docker compose --project-name arp-e2e --env-file .env.e2e up --build -d
python scripts/seed_demo.py --env-file .env.e2e
cd frontend
npx playwright install chromium
npm run test:e2e
```

Playwright 配置优先读取 `.env.e2e`，默认 `E2E_BASE_URL=http://127.0.0.1:8088`、
`E2E_API_URL=http://127.0.0.1:8008/api/v1`；也可显式设置这两个环境变量。
若无法下载 Playwright Chromium，可安装本机 Chrome/Edge 并设置
`$env:E2E_BROWSER_CHANNEL="chrome"`（或 `msedge`）后运行。
E2E 不自动启动第二套 Compose，也不会清理开发数据卷。

## 6. 故障演示

见 [docs/demo.md](docs/demo.md)：全通过、错误标题断言失败、Worker 强杀后的中断与
“写操作可能已生效”提示。

清理 Demo 文章（只影响 Demo SQLite，不影响平台 PostgreSQL）：

```powershell
python scripts/reset_demo.py --confirm
```

## 7. 停止

```powershell
docker compose down
```

不要使用 `docker compose down -v`，除非确认要删除 PostgreSQL 与 Demo 数据卷。
若密钥 `APP_ENCRYPTION_KEY` 丢失，旧环境配置与 run 快照将无法解密；本版本不支持密钥轮换。

## 安全边界

- 仅允许部署配置中的 `TARGET_ORIGINS`，不是任意 URL 公网请求代理。
- JWT 只在 `Authorization` header；前端 Token 只存内存，刷新后重新登录。
- 环境秘密与运行快照加密存储；公开报告只含脱敏内容。
- 不自动重试业务写请求；中断后不续跑。
- 第一版不包含 AI/Agent、DAG、团队协作、定时回归或任意脚本执行。
