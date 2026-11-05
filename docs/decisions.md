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
