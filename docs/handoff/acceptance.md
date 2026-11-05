# 验收清单与验证证据

此文档是未来开发验收标准。当前只有规划文档，以下检查均未执行，不表示功能已存在。
P0完成必须A01..A19全部通过；P1完成再通过A20。每项在docs/verification.md附命令、日期、结果和必要截图。
测试使用合成账号/数据；集成用test-db，E2E用arp-e2e独立Compose项目，禁止清空开发数据库。

## 一、需求验收矩阵

| 编号 | 验收动作与预期 | 负责 |
|---|---|---|
| A01 | 注册/登录成功；错误密码、伪造或过期JWT均401；响应无密码/hash；401清前端内存Token | T03/T12 |
| A02 | 用户B无法读写A项目/环境/用例/API定义/run/report/SSE；跨项目ID也404 | T03..T06/T09/T11 |
| A03 | 环境secret保留/替换/移除行为一致；首次null拒绝；密文中无已知secret明文；读API不暴露 | T04 |
| A04 | 本地OpenAPI JSON成功导入；重复导入skip；坏文档整批回滚；外部/循环引用、大小/深度超限拒绝 | T06 |
| A05 | 创建、读取、修改1..20步case；顺序保持；旧version409；未知字段、非法selector、敏感literal拒绝 | T05 |
| A06 | 整段模板保留类型；嵌入模板转字符串；null和缺字段区分；true不等于1；不存在变量在HTTP前失败 | T07/T08 |
| A07 | 登录→创建→查询→删除→再查404五步passed；404不能被HTTP客户端自动判失败 | T08/T14 |
| A08 | 错误标题导致第3步failed，4/5 skipped；显示具体断言差异；无自动cleanup或重试 | T08/T14 |
| A09 | 网络超时、提取失败、非JSON提取分别error；run终态不留pending/running；统计counts相加=total | T08/T10/T11 |
| A10 | 同key并发提交只一个run和outbox；同key不同请求409；主动再次执行用新key | T09 |
| A11 | 同run重复投递/并发claim只一个执行者；一次POST在目标服务的计数为1 | T10/T14 |
| A12 | run提交后改case/env，执行仍用旧快照；历史报告版本/期望值不随最新定义改变 | T09/T14 |
| A13 | Redis不可用时run保留queued/outbox；恢复后可派发；超过300秒无执行则error；不永久排队 | T10 |
| A14 | 强杀Worker后run变interrupted；迟到结果不覆盖终态；不自动重发可能成功的写请求；UI提示不确定 | T10/T14 |
| A15 | 报告/事件/日志不含已知密码Token；query不显示值、path显示模板；认证头与响应回显脱敏 | T08/T11/T14 |
| A16 | 无任意origin请求；Host篡改拒绝；302不跟随；代理环境不生效；响应>1MiB停止且不存原始正文 | T08 |
| A17 | SSE中文分片正常；after续读/重复帧不重复显示；断线后重连，3次失败GET兜底；401与终态停止 | T11/T13 |
| A18 | 页面可完成全流程；加载/空态/422/409清晰；保存后刷新可恢复；Token刷新后需登录；不创建重复run | T12/T13/T14 |
| A19 | 干净隔离Compose环境按README启动，迁移/健康依赖正确，真实PG/Redis/Worker/E2E均通过，lockfile可复现 | T14 |
| A20 | 统计SQL正确、owner检查先于cache、TTL30秒、Redis坏时回DB；通过率2/(2+1)=2/3，0分母null | T15 |

## 二、建议逐项测试组织

单元测试：
- schema边界：20/21步、敏感literal、类型/方法/selector白名单。
- renderer：数字、字符串、bool、null、嵌套、原始输入不变、未定义变量、路径参数URL编码。
- selector：$.items[0].id、缺字段/null、错误语法/越界/最大长度。
- assertion：期望404、true/1、对象/数组、耗时边界。
- transport：302、不允许origin、stream上限、HTTPX分项timeout、无重试。
- redaction：header/JSON深层/回显/失败提取/URL/omit_response_body。
- 前端：secret编辑协议、case顺序和JSON校验、idempotency-key、SSE UTF-8分片/取消/重连。

真实PostgreSQL集成：
- migrations、唯一约束、owner、版本冲突。
- run+step+event+outbox原子事务。
- 幂等并发、CAS claim、状态/事件一致性、迟到结果栅栏。
- 报告与SSE跨用户不可读，分页和counts。
- 时间恢复使用注入now测试，不sleep330秒。
- test-db与开发库必须分离；不允许通过回滚一个共享connection掩盖多session真实提交问题。

真实Compose验收：
- API→outbox→Redis→Celery→Demo HTTP→PostgreSQL→SSE→浏览器。
- Playwright运行真正浏览器，不用前端假响应冒充后端成功。
- 故障用例、Worker被杀、Redis短暂不可用须至少各一次人工或脚本验证。
- 300/330秒超时的快速测试可注入clock；至少一次真实Worker强杀完整等待reconcile并记录实际耗时。

## 三、关键故障实验步骤

### F1：断言失败

1. 在独立arp-e2e环境执行种子五步用例，确认passed。
2. 使用测试Compose覆盖配置，将demo-api的DEMO_FAULT_MODE设为title_mismatch并重建该服务。
3. 新Idempotency-Key再次执行相同case。
4. 验证第1/2步passed，第3步failed，第4/5步skipped；run failed。
5. 恢复Demo配置，显式reset残留测试文章；不能自动删除平台历史。

### F2：写请求响应不确定

1. 在测试专用Demo模式提供“写入后延迟响应”，仅由env启用，不能提供公网故障控制端点。
2. 请求在目标已写入后超时；平台step error/REQUEST_TIMEOUT。
3. 检查目标记录只增加一次，平台没有自动重试。
4. 报告不能宣称写入一定失败；给“请求可能已生效，请检查目标数据”提示。
5. 新run属于用户主动的新操作，必须警告可能产生新的业务数据。

### F3：Worker进程丢失

1. 使用测试专用延迟响应，让run进入running且至少开始一个HTTP步骤。
2. 明确确认Compose project是arp-e2e，再强杀其worker；禁止误杀开发项目。
3. 已running的run不能被重新claim；等待330秒上限和reconcile后interrupted。
4. 恢复worker，确认不会重放旧run；报告中运行中的step error、后续skipped。
5. 测试迟到sink回调，确认终态和run.finished事件不被再次覆盖。

### F4：派发中断

1. 只停止arp-e2e Redis，API与PG保留。
2. 提交run，返回202且queued；outbox pending。
3. 300秒内恢复Redis，dispatcher应补发且只一个claim。
4. 另一个测试用注入时间验证queued超300秒转error/DISPATCH_TIMEOUT并abandoned。
5. publish成功、sent落库失败的场景用可控publisher模拟重复；最终仅一个run执行者。

### F5：秘密与事件

1. 使用足够长、唯一的合成secret值，配置在环境和登录提取中。
2. 让Demo返回嵌套回显、认证头、query等已知secret。
3. 检查API报告、持久化safe结果、事件、日志均不含原值；不要只看前端星号。
4. 检查加密列只含密文；配置/快照没有另外的明文字段副本。
5. B用自己的Token访问A的run/SSE均404；不允许以run_id难猜代替鉴权。

## 四、交付时必须能运行的命令

根目录：
~~~powershell
python scripts/init_env.py
docker compose config --quiet
docker compose up --build -d
docker compose ps
python scripts/seed_demo.py
python scripts/smoke.py
docker compose -f compose.yaml -f compose.test.yaml run --rm test pytest tests/integration -q
~~~

backend目录：
~~~powershell
uv sync --frozen
uv run pytest tests/unit -q
uv run ruff check .
uv run ruff format --check .
~~~

frontend目录：
~~~powershell
npm ci
npm run typecheck
npm run test:unit -- --run
npm run build
npm run test:e2e
~~~

首次E2E（根目录，独立环境）：
~~~powershell
python scripts/init_env.py --e2e
docker compose --project-name arp-e2e --env-file .env.e2e up --build -d
python scripts/seed_demo.py --env-file .env.e2e
~~~
随后在frontend运行 npx playwright install chromium 和 npm run test:e2e；
默认E2E_BASE_URL=http://127.0.0.1:8088，测试通过API_PORT=8008准备数据。
Playwright配置不自动启动第二套Compose，由用户明确启动隔离环境。
实际命令会在实现T14中核实。README必须给出完整先后顺序。
当前不能把以上命令当成已可运行脚本或测试已通过的证明。
若宿主不安装Python依赖，seed/smoke脚本必须只用stdlib urllib/json或提供明确容器入口。
网络下载失败、浏览器未安装等须记录为未完成，不能写“全部通过”。

禁止把下面这些当作验收：
- uvicorn进程起来了，所以整个项目完成；
- 只有前端截图，没有真实后台任务；
- 只有单元fake transport，没有真实PG/Redis/Celery；
- 用前端hardcode计数替代SQL统计；
- 用sleep让测试碰巧通过，或将所有异常都显示成网络问题；
- 编造QPS/覆盖率/用户量。

## 五、verification.md填写模板

~~~text
验证日期与时区：
Commit：
OS / Python / Node / Docker：
依赖与镜像版本：
测试环境（开发/test-db/arp-e2e）：
命令：
实际结果（通过/失败数量）：
对应验收编号：
截图/日志位置（仅合成数据）：
未覆盖项与原因：
遗留风险：
~~~

## 六、面试准备材料

项目完成后，用户应能不看模型解释回答：
1. 为什么Web层async与Celery是两种不同的并发机制？
2. 为什么数据库提交成功不等于消息已可靠发布？
3. 为什么task_id不是防重复执行的充分条件？
4. 为什么不自动重试写请求？Worker被杀后为什么不能直接续跑？
5. 快照解决了什么历史追溯问题？
6. SSE如何认证、重连，刷新为什么不会丢最终报告？
7. 脱敏为什么发生在持久化前？密文快照和公开报告有什么区别？
8. 查询如何分页、哪些索引实际有用、通过率分母为什么这样选？
9. OpenAPI能告诉你什么，哪些业务断言必须人工确定？
