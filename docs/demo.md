# FlowCheck 演示脚本

前置：已按 README 启动 Compose 并运行 `python scripts/seed_demo.py`。

## 1. 全通过（五步流程）

1. 打开 `http://127.0.0.1:8080`，用 `.env` 中的 `PLATFORM_DEMO_USERNAME` / `PLATFORM_DEMO_PASSWORD` 登录
   （也可自行注册）。
2. 进入“文章回归 Demo” → 运行记录 → 执行用例，选择“Compose Demo”环境与“文章回归五步”。
3. 报告实时更新，最终 5 步全部“通过”，状态“通过”。

命令行等价：

```powershell
python scripts/smoke.py
```

预期输出：`run_status=passed`，5 个 step passed。

## 2. 断言失败（错误标题）

1. 在 `.env` 设置 `DEMO_FAULT_MODE=title_mismatch`，执行
   `docker compose up -d demo-api` 让被测服务返回错误标题。
2. 重新执行五步用例（新 Idempotency-Key）。
3. 预期：第 1/2 步通过，第 3 步断言失败，第 4/5 步跳过，run=failed。
4. 恢复 `DEMO_FAULT_MODE=` 并 `docker compose up -d demo-api`；
   用 `python scripts/reset_demo.py --confirm` 清理 Demo 残留文章。

说明：Demo 没有自动 cleanup；失败时第 2 步创建的文章可能残留，这是演示的一部分。

## 3. Worker 中断（写请求结果不确定）

1. 在测试环境 `.env.e2e` 设置 `DEMO_WRITE_DELAY_S=60`，重建 demo-api；
   `docker compose --project-name arp-e2e --env-file .env.e2e up -d demo-api`。
2. 提交一个五步 run，确认进入 running 且第 2 步（创建文章）已开始。
3. **确认 Compose 项目为 arp-e2e 后**，强制停止 worker：
   `docker compose --project-name arp-e2e --env-file .env.e2e kill worker`。
4. 已运行的 run 不会被重新 claim；等待 `started_at + 330s` 后 dispatcher 回收：
   run=interrupted / WORKER_INTERRUPTED，运行中步骤 error，后续步骤 skipped。
5. 报告提示“部分写操作可能已生效”；Demo 中文章可能已经创建，平台不会自动重试。
6. 恢复 worker 并清理 Demo 数据；不要删除平台历史报告。

详细实测命令与结果见 `docs/verification.md`。
