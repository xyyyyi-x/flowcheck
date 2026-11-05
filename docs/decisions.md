# 实施决策记录

本文件记录实施过程中对规格的落地选择、发现的问题与最小调整；不改变主技术栈。

## 2026-11-05

### D001 本机 Python 版本

- 现象：宿主仅有 Python 3.14.2；规格要求 Python 3.12。
- 决策：使用 uv 安装并锁定 CPython 3.12.16（`backend/.python-version` 固定 `3.12`），
  本地开发与 Docker 镜像均使用 3.12。宿主 3.14 只用于运行安装工具与 `scripts/` 标准库脚本。
- 证据：`python -m uv python find 3.12` 输出
  `C:\Users\DELL\AppData\Roaming\uv\python\cpython-3.12-windows-x86_64-none\python.exe`。

### D002 包管理器入口

- 宿主 `uv` 未加入 PATH；使用 `python -m uv ...`（uv 0.13.7）。README 同时给出 PATH 就绪时的
  `uv ...` 写法与本机实际可用写法。

### D003 Compose 项目名

- 开发环境 `compose.yaml` 固定 `name: arp-dev`；E2E 用 `--project-name arp-e2e` 覆盖，
  依赖 Compose 对卷/网络的自动前缀隔离。数据库与 Redis 不映射宿主端口。

### D006 后端镜像构建目标

- 现象：后端 Dockerfile 最后一个 stage 是 `test`（CMD 为 pytest），Compose 默认构建最后
  stage，导致 api 容器启动后直接跑测试、健康检查失败。
- 修正：compose.yaml 中 migrate/api/worker/dispatcher 显式 `target: base`；`test` 服务使用
  `target: test`。已通过 `docker compose up --build -d` 与健康检查验证。

### D007 Compose 环境文件与 E2E 隔离

- 现象：服务内硬编码 `env_file: .env`，`--env-file .env.e2e` 只影响变量插值，容器仍读开发
  密码，导致 arp-e2e 的 migrate 数据库认证失败。
- 修正：移除硬编码 env_file，所有服务所需变量通过 `${VAR:?}` / `${VAR:-default}` 插值注入。
  这样开发与 arp-e2e 使用同一份 compose 定义，但值完全来自各自 `--env-file`。
- 证据：`docker compose --env-file .env.e2e config --quiet` 通过；arp-e2e migrate 成功，
  seed/smoke/Playwright 全部通过。

### D008 Nginx 上游解析

- 现象：api 容器重建后 web 返回 502；Nginx 在启动时缓存了 `api` 的旧容器 IP。
- 修正：`resolver 127.0.0.11 valid=10s` + `set $api_upstream http://api:8000`，
  proxy_pass 使用变量在请求时解析。web 重建后 `/api/v1/health/live` 返回 200。

### D009 Playwright 浏览器

- 本机 Playwright 1.64.1 要求 Chromium 1248；`playwright install chromium` 在本地网络
  超过 10 分钟未完成下载。
- 修正：配置支持 `E2E_BROWSER_CHANNEL`，验证时使用系统 Chrome（真实浏览器）执行
  `npm run test:e2e`，3 个场景通过。默认仍为 Playwright Chromium；干净环境应运行
  `npx playwright install chromium`。

### D005 依赖下载源

- 现象：官方 PyPI 到本机连接在多轮 `uv sync` 中长时间停滞（>20 分钟，缓存不再增长）；
  清华镜像索引响应约 0.5s，官方约 4s。
- 决策：`uv.lock` 以清华镜像为默认源重新解析并安装（`--default-index
  https://pypi.tuna.tsinghua.edu.cn/simple`），版本仍满足 pyproject 约束；镜像滞后一个
  patch 时接受解析出的实际版本（如 Pydantic 2.14.2）。此选择同时加速 Docker 构建。
- 影响：lockfile 中的 registry 指向该镜像；换网络环境需保证镜像可达，或在受控环境重新
  `uv lock --default-index https://pypi.org/simple`。
- 证据：`uv lock` 输出 `Updated pydantic v2.14.3 -> v2.14.2`，随后 `uv sync` 在数分钟内完成。

### D004 origin 规范化

- `normalize_origin` 只接受 http/https、无凭据、无路径/query/fragment；显式端口保留，
  host 小写化。配置与执行期使用同一函数比较，避免大小写或默认端口字符串差异
  （显式 `:443` 与省略端口不自动视为同一字符串，前端只提供配置列表，用户无需手写）。
