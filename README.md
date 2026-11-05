# 接口回归测试平台

为个人开发者保存可复用的 HTTP 接口流程，在代码修改后由后台 Worker 真实执行，
实时展示进度并保留不可变的历史报告。技术栈：FastAPI + PostgreSQL + Celery/Redis +
Vue 3，Docker Compose 单机部署。

> 当前处于实现阶段，完成状态以 [docs/progress.md](docs/progress.md) 与
> [docs/verification.md](docs/verification.md) 为准。

## 目录

- `backend/`：FastAPI API、Celery Worker、dispatcher、Alembic 迁移。
- `frontend/`：Vue 3 + TypeScript + Element Plus 单页应用。
- `demo-api/`：独立文章 Demo API，仅作为被测服务。
- `scripts/`：环境初始化、演示数据、smoke 与重置脚本。
- `docs/`：设计规格、API 契约、计划、验收与验证记录。

## 本地开发（不使用 Docker 跑后端时）

需要 Python 3.12（可用 uv 安装）与 Node.js >= 22.12。

```powershell
# 1. 生成本地环境文件（拒绝覆盖已有文件，不打印秘密）
python scripts/init_env.py

# 2. 后端依赖与测试
cd backend
python -m uv sync --frozen
python -m uv run pytest tests/unit -q

# 3. 前端
cd ../frontend
npm ci
npm run typecheck
npm run build
```

## Compose 部署

```powershell
python scripts/init_env.py
docker compose config --quiet
docker compose up --build -d
docker compose ps
```

默认端口（仅绑定 127.0.0.1）：Web 8080、API 文档 8000、Demo 8001。
数据库与 Redis 不映射宿主端口。

停止：`docker compose down`（不要加 `-v`，除非确认要删除数据卷）。
