# FlowCheck API v1、执行 DSL 与页面契约

此文档与设计规格共同约束实现。所有路径除特别说明均以 /api/v1 为前缀。
参数名称采用 snake_case；前端在 API 边界保留 snake_case，避免重复映射。
UUID 对外是字符串。时间 ISO8601 UTC。成功响应不套通用 data 壳。

## C01. 通用 API 规则

认证：Authorization: Bearer <access_token>。登录注册和health不要求认证，其余全部要求。
无效/过期/缺失认证401；资源不存在、非本人资源、资源不属于URL中的项目统一404；
合法用户修改旧版本409；结构或业务参数校验422；未处理异常500且不回传内部错误。
列表返回 {items: [...],total: 0,page: 1,page_size: 20}，默认20最大100；
排序 created_at DESC,id DESC，不提供任意排序字段。空列表items=[]且total=0。
所有对象schema默认 extra=forbid；文本去除首尾空白；password和变量值不trim。
错误响应（也适用于RequestValidationError；禁止返回Pydantic的原始input）：

~~~json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "请求参数不符合要求",
    "details": [{"path": "body.steps.0.request.path", "message": "必须使用相对路径"}]
  },
  "request_id": "9aec0170-7081-4689-acad-c5414d8610d2"
}
~~~

每HTTP请求生成新的request_id，响应头X-Request-ID同步返回；日志不用用户提供的任意字符串。
401前端清除内存Token并跳转登录；404显示“资源不存在或无权访问”；409提示重新加载；
422定位字段；500显示request_id方便排查。非JSON原始异常不直接展示。

## C02. 数据类型

VariableInput：{name: string,value: JSON标量|null,is_secret: boolean}。
普通变量允许null；secret的null仅在更新时表示保留旧secret，首次创建禁止。
VariableRead：同上，额外has_value:boolean；secret永远value=null；非secret返回真实标量。
secret变量必须非空字符串；普通变量可string/number/bool/null，禁止数组/对象。
名字正则[A-Za-z_][A-Za-z0-9_]{0,63}，不能用run_id。同一环境<=50个且名称唯一。

HeaderInput：{name: string,value: string|null,is_secret: boolean}。
HeaderRead增加has_value。名字按HTTP header token语法验证，大小写不敏感去重；
secret null保留规则与变量相同。<=30个；认证相关header强制secret。
非secret header=null不合法。Host/Content-Length/Connection/Transfer-Encoding禁止用户配置。
common_headers与step headers合并，step按不区分大小写的名字覆盖common；
框架计算Content-Length，Content-Type在有JSON body时固定application/json。

EnvironmentCreate：
{name: string,base_url: string,variables: VariableInput[],common_headers: HeaderInput[]}。
EnvironmentUpdate：以上全部字段 + version:int；是整体替换，不是PATCH。
EnvironmentRead：id,project_id,name,base_url,variables:VariableRead[],common_headers:HeaderRead[],
version,created_at,updated_at。不返回config_ciphertext。

ApiDefinitionRead：
id,project_id,method,path,summary,parameters,request_body_schema,created_at。
parameters是[{name,in,required,type}]，in仅path/query/header；type可为string/number/integer/boolean/array/object/unknown。
request_body_schema为经过移除example/examples/default的元数据对象或null；不据此自动决定业务值。

CaseCreate：{name:string(1..80),description:string<=500,steps:StepDefinition[]}。
CaseUpdate：以上全部字段 + version:int（当前版本）；成功version+1。
CaseRead：id,project_id,name,description,steps,version,created_at,updated_at。
steps 1..20，local id唯一，顺序由数组决定，位置从1计算。

StepDefinition：
- id: UUID，由前端crypto.randomUUID生成，用于编辑稳定key。
- name: string，1..80。
- source_api_id: UUID|null，只作溯源；如存在必须同项目。执行使用步骤内的请求，不回读API定义。
- request: RequestDefinition。
- assertions: AssertionDefinition[]，1..20，必须恰有一个status_code断言。
- extractors: ExtractorDefinition[]，0..10。
- omit_response_body: boolean，默认false；登录步骤UI默认true。

RequestDefinition：
- method: GET/POST/PUT/PATCH/DELETE。
- path: /开头的路径模板，例如/articles/{id}。不含origin/query/fragment；长度<=2048。
- path_params: {name: JSON标量或模板字符串}，键必须恰好等于path中花括号参数。
- query: {name: JSON标量或模板字符串}，不支持重复键；<=30项。
- headers: {name: string}，可带模板；禁止受限header与CRLF；<=30项。
- json_body: 任意JSON值或null。null表示无body；非空仅POST/PUT/PATCH可用；序列化<=64KiB。
- timeout_s: int，默认10，1..30。
除path的{param}外，{{variable}}只允许出现在path_params/query/header值、body字符串叶子、json_equals.expected里；
path模板本身禁止{{}}，不允许变量替换host、method、header名、选择器或断言类型。

AssertionDefinition使用type辨别联合：
- {type:"status_code",expected:int(100..599)}
- {type:"json_equals",selector:string,expected:任意JSON}
- {type:"response_time_lt",expected_ms:int(1..30000)}
不支持字符串表达式或eval。response_time_lt为严格<，elapsed相等不通过。

ExtractorDefinition：
{name:string,selector:string,is_secret:boolean}。
name规则同变量，跨所有步骤不可重复，不能run_id；
提交run时不可与该环境变量同名；只能读取本步骤JSON response。
secret提取必须得到非空字符串；普通提取只接受JSON标量（含null）。

## C03. 环境配置示例

POST /projects/{project_id}/environments：

~~~json
{
  "name": "Compose Demo",
  "base_url": "http://demo-api:8001",
  "variables": [
    {"name": "demo_username", "value": "demo", "is_secret": false},
    {"name": "demo_password", "value": "only-for-local-demo", "is_secret": true}
  ],
  "common_headers": []
}
~~~

读取时demo_password.value=null且has_value=true。密码文本是演示占位值，真实值由本地初始化生成。
环境整体更新：
- 保留secret：同名项value=null,is_secret=true；
- 替换secret：同名项value="新值",is_secret=true；
- 删除变量：从列表移除；
- secret降级为非secret必须提供新值，不能value=null保留并同时解除保密。
secret header适用相同协议。
GET /target-origins返回 {items:["http://demo-api:8001"]}，由部署配置生成，不支持写入。

## C04. 模板、选择器、断言的精确语义

运行上下文只包括run_id、冻结的环境变量、已通过步骤的extractors。
禁止访问os/env/filesystem，禁止随机函数、时间函数、表达式和属性计算。
变量正则匹配{{name}}，不允许内部空白；包含未闭合/非法模板标记时保存422。
- JSON字符串整个等于{{count}}：替换成原生数字/bool/null/string；
- "item-{{count}}"：标量转字符串；bool为true/false，null为null，数字使用JSON表示；
- path/query/header最终都转换成字符串；body/expected保留整段模板的原类型。
- 不递归解释变量值中的模板，不渲染字典键，不修改原始定义。
- path_params用URL编码单个参数，不能改变origin或创建额外路径段。
- 缺变量在发请求前error/VARIABLE_UNDEFINED。跨run绝不共享context。

选择器仅支持 $ 根，.字段 和 [非负整数]，如 $.data.items[0].id；
字段名[A-Za-z_][A-Za-z0-9_]*，索引0或不带前导零的正整数，最大10000；
总长<=256，token最多32。不支持通配符、过滤、递归、负数、带引号的键。
实现确定性token parser，禁止eval或假装支持完整JSONPath。
缺字段/越界与值为null必须区分。缺字段导致json_equals断言失败或提取error；
JSON不是合法对象/数组也按缺路径处理，根$可返回标量。

json_equals：
先渲染expected，再按JSON语义深比较；bool和number不同（true不等于1）；
数字1与1.0视为相同；数组顺序敏感；对象键顺序无关；null只等于null。
status_code依据实际HTTP状态，4xx/5xx可作为期望成功；
response_time_lt使用HTTP开始到完整有界body读完的perf_counter毫秒，不包含后续数据库写入。
elapsed_ms以整数毫秒存储，比较用未四舍五入的实际浮点毫秒，展示取整。

所有断言都计算并记录，通过后才发布extractors给后续步骤。
同一步断言失败时仍可内部收集secret extractor值用于脱敏，但不改变run context。
任一断言失败→step failed/run failed；通过后提取失败→step error/run error。
无HTTP响应的网络错误不生成虚构状态码。204 body为空，status断言可通过；
非JSON body不支持json_equals/extract，状态/耗时仍可判断。body预览遵守脱敏策略。

## C05. 用例示例（节选结构，演示种子必须包含完整5步）

~~~json
{
  "name": "文章创建查询",
  "description": "用于验证登录、变量提取和文章查询",
  "steps": [
    {
      "id": "26d29d08-d7ac-4ac8-af04-30158565664a",
      "name": "登录",
      "source_api_id": null,
      "request": {
        "method": "POST", "path": "/auth/login",
        "path_params": {}, "query": {}, "headers": {},
        "json_body": {"username": "{{demo_username}}", "password": "{{demo_password}}"},
        "timeout_s": 10
      },
      "assertions": [{"type": "status_code", "expected": 200}],
      "extractors": [{"name": "auth_token", "selector": "$.access_token", "is_secret": true}],
      "omit_response_body": true
    },
    {
      "id": "9f4180ed-072c-4dc3-958f-e03eef759793",
      "name": "创建文章",
      "source_api_id": null,
      "request": {
        "method": "POST", "path": "/articles",
        "path_params": {}, "query": {},
        "headers": {"Authorization": "Bearer {{auth_token}}"},
        "json_body": {"title": "smoke-{{run_id}}", "content": "hello"},
        "timeout_s": 10
      },
      "assertions": [{"type": "status_code", "expected": 201}],
      "extractors": [{"name": "article_id", "selector": "$.id", "is_secret": false}],
      "omit_response_body": false
    },
    {
      "id": "c97ae06a-c19a-4e46-8f57-c3f002e2dc85",
      "name": "查询文章",
      "source_api_id": null,
      "request": {
        "method": "GET", "path": "/articles/{id}",
        "path_params": {"id": "{{article_id}}"}, "query": {},
        "headers": {"Authorization": "Bearer {{auth_token}}"},
        "json_body": null, "timeout_s": 10
      },
      "assertions": [
        {"type": "status_code", "expected": 200},
        {"type": "json_equals", "selector": "$.title", "expected": "smoke-{{run_id}}"}
      ],
      "extractors": [],
      "omit_response_body": false
    }
  ]
}
~~~

## C06. API 路由清单

约定列表GET支持page/page_size；除auth/health，所有路由用owner依赖校验。
项目内子资源路径先验证project归属，再验证子资源project_id；不能仅按UUID查询。
新增接口不能自行偏离此路由表，前后端共享tests中的契约样例。

| 方法与路径 | 请求 | 成功响应 |
|---|---|---|
| GET /health/live | 无 | 200 {status:"ok"} |
| GET /health/ready | 无 | DB可用200；不可用503；不暴露连接串 |
| POST /auth/register | {username,password} | 201 {id,username,created_at} |
| POST /auth/login | {username,password} | 200 {access_token,token_type:"bearer",expires_in:1800} |
| GET /auth/me | 无 | 200 {id,username,created_at} |
| GET /target-origins | 无 | 200 {items:string[]} |
| POST /projects | {name,description} | 201 ProjectRead |
| GET /projects | 分页 | 200分页ProjectRead |
| GET /projects/{project_id} | 无 | 200 ProjectRead |
| PUT /projects/{project_id} | {name,description} | 200 ProjectRead |
| POST /projects/{project_id}/environments | EnvironmentCreate | 201 EnvironmentRead |
| GET /projects/{project_id}/environments | 分页 | 200分页EnvironmentRead |
| GET /projects/{project_id}/environments/{environment_id} | 无 | 200 EnvironmentRead |
| PUT /projects/{project_id}/environments/{environment_id} | EnvironmentUpdate | 200 EnvironmentRead |
| POST /projects/{project_id}/imports/openapi | multipart file，只有一个file字段 | 201 ImportResult |
| GET /projects/{project_id}/api-definitions | 分页 | 200分页ApiDefinitionRead |
| GET /projects/{project_id}/api-definitions/{api_id} | 无 | 200 ApiDefinitionRead |
| POST /projects/{project_id}/cases | CaseCreate | 201 CaseRead |
| GET /projects/{project_id}/cases | 分页 | 200分页CaseRead |
| GET /projects/{project_id}/cases/{case_id} | 无 | 200 CaseRead |
| PUT /projects/{project_id}/cases/{case_id} | CaseUpdate | 200 CaseRead |
| POST /projects/{project_id}/runs | {case_id,environment_id}+Idempotency-Key | 202 {run_id,status,reused} |
| GET /projects/{project_id}/runs | 分页，status可选合法枚举 | 200分页RunSummary |
| GET /runs/{run_id} | 无 | 200 RunReport |
| GET /runs/{run_id}/events?after=0 | fetch SSE | 200 text/event-stream |
| GET /projects/{project_id}/summary | P1 | 200 ProjectSummary |

ProjectRead=id,owner_id,name,description,created_at,updated_at。
RunSummary=id,project_id,case_id,environment_id,case_name,case_version,environment_name,environment_version,
status,created_at,started_at,finished_at,error_code,counts。
counts={total,pending,running,passed,failed,error,skipped}，各步状态计数之和=total。
RunReport=RunSummary + steps:StepResultRead[]；按position升序。
StepResultRead=id,position,name,status,elapsed_ms,request_safe,response_safe,assertions_safe,extracts_safe,
error_code,started_at,finished_at。
request_safe={method,origin,path_template,query_keys,headers_safe,json_preview}；
response_safe={status_code|null,headers_safe,json_preview|null,body_omitted:boolean}。
json_preview为脱敏后的JSON文本字符串（截断时加说明），不是再次执行或校验的输入。
assertions_safe=[{type,passed,selector?,expected_safe?,actual_safe?}]；
extracts_safe=[{name,is_secret,success,value_safe}]；secret value_safe固定"[REDACTED]"。
未执行字段为null/[]，不能编造HTTP200或0ms。

状态文案：queued=排队中；running=执行中；passed=通过；failed=断言失败；
error=执行错误；interrupted=执行中断；step额外pending=待执行、skipped=已跳过。
error_code：ASSERTION_FAILED、VARIABLE_UNDEFINED、SELECTOR_MISSING、EXTRACTION_INVALID、
REQUEST_TIMEOUT、NETWORK_ERROR、RESPONSE_TOO_LARGE、RESPONSE_NOT_JSON、TARGET_NOT_ALLOWED、
DISPATCH_TIMEOUT、RUN_TIMEOUT、WORKER_INTERRUPTED、INTERNAL_ERROR。不可混用HTTP错误响应code与run状态。
保存case时静态问题用VALIDATION_ERROR/422；只有运行时问题才写step error_code。

ProjectSummary字段见设计第10节；另含computed_at和cache_hit。pass_rate为0..1或null；
前端展示乘100；cache_hit=true仍返回原computed_at。

## C07. OpenAPI 导入支持范围

读取文件大小最多2MiB（流读上限，不依赖Content-Length），只接受UTF-8 JSON对象；
openapi必须以3.0.或3.1.开头；paths必须对象；最多200个支持的operation。
支持GET/POST/PUT/PATCH/DELETE；忽略其他method并返回warnings。
导入提取method/path/summary、path级与operation级parameters、application/json body schema；
同名同in的operation参数覆盖path参数。cookie参数跳过且警告。
参数/RequestBody的本地$ref可用JSON Pointer解析，最大深度8，循环/不存在则422；
schema内部本地$ref只保留符号不递归解析；移除example/examples/default，不生成示例数据。
任何外部$ref（非#/开头）整份422；不访问网络，不打开本地文件。
忽略servers、security自动绑定、links、callbacks、webhooks；warnings说明需人工配置鉴权及业务值。
schema超深（>32）或JSON遍历节点>20000返回422，避免无限递归/大对象。
已存在(project_id,method,path)跳过；重复导入不覆盖；并发唯一冲突按skip处理，不能整批500。
先完整校验再事务保存，任一结构错误不得部分入库。

ImportResult={created_count:int,skipped_count:int,warnings:[{path,message}]}。
warnings最多100条，超过后最后一条提示截断；不把原始上传文件、示例或异常堆栈写进日志。
不宣称支持完整OpenAPI；请求参数仍由用户确认后保存case。

## C08. SSE 契约

GET /runs/{run_id}/events?after=N：after为0..9223372036854775807的十进制字符串。
数据库事件id在SSE和JSON均用十进制字符串，避免JS超过安全整数。
使用fetch + Authorization + AbortController + eventsource-parser，不能把JWT放URL。
每条事件格式：

~~~text
id: 125
event: step.finished
data: {"run_id":"UUID","position":2,"status":"passed","error_code":null}

~~~

event_type：
run.queued {run_id,status:"queued"}；
run.started {run_id,status:"running"}；
step.started {run_id,position,status:"running"}；
step.finished {run_id,position,status,error_code}；
run.finished {run_id,status,error_code}。
id是帧字段，不要求data重复携带。payload无body/header/secret，报告通过GET单独读取。
心跳为": heartbeat\n\n"，无id；浏览器不能把心跳当状态变化。
按id排序查询，after不属于本run也只查询本run自己的id>after，不泄露其他事件。
终态且当前游标无剩余事件就关闭。前端初始化先GET报告，再订阅after=0；
断线保存最新id，重新订阅；run.finished后GET最终报告并停止订阅。
连接失败3次降级报告轮询；每2秒刷新，终态停止；401直接停止。
网络恢复与刷新不能导致创建新run；只有用户点击执行才POST /runs。

## C09. 前端路由与组件责任

/auth/login、/auth/register：表单、字段错误；成功登录跳转/projects。
/projects：项目列表与创建。
/projects/:projectId/overview：项目说明、最近运行；P1接统计。
/projects/:projectId/environments：列表、创建/编辑、secret保留/替换/移除。
/projects/:projectId/apis：导入上传、接口列表、参数只读查看。
/projects/:projectId/cases：用例列表；新建与编辑路由分别/cases/new、/cases/:caseId/edit。
/projects/:projectId/runs：历史列表与状态筛选。
/runs/:runId：实时进度、步骤结果、请求/响应脱敏预览、断言差异；中断提示写操作可能生效。

CaseEditor包含StepList、RequestEditor、AssertionEditor、ExtractorEditor；
JSON输入用textarea+格式化按钮即可，不引入Monaco/拖拽编辑器。
step顺序用上移/下移；source_api只负责预填method/path/参数名字，不自动生成正确断言。
“从接口添加”必须由用户确认预期状态码；无有效status断言不能保存。
初始可提供明确标注“需确认”的status_code=200草稿，不能声称AI已判断正确。

运行创建按钮：选择环境→生成Idempotency-Key→提交中禁用→跳转报告；
HTTP传输失败保留key可重试，确定已有run后重置；主动再次执行必须新key。
Token仅Pinia内存，不持久化localStorage/sessionStorage；刷新后登录，再返回原报告路径。


## C10. 内部执行类型（固定字段，防止模块各自猜测）

RunSnapshot：
~~~text
schema_version: Literal[1]
run_id: UUID
case_id: UUID
case_name: str
case_version: int
environment_id: UUID
environment_name: str
environment_version: int
target_origin: str
variables: list[{name:str,value:JsonScalar,is_secret:bool}]
common_headers: list[{name:str,value:str,is_secret:bool}]
steps: list[StepDefinition]
limits: {
  max_steps: 20,
  request_max_bytes: 65536,
  response_max_bytes: 1048576,
  report_preview_bytes: 8192,
  run_budget_s: 300
}
captured_at: datetime UTC
~~~
这里的value都是已解密真实输入，仅存在密文快照或Worker内存；不能用于公开API。
重复提交同key不得重建captured_at或快照。快照反序列化先检查schema_version；
不支持的版本终结error/INTERNAL_ERROR，不回退读取最新case/env。

SafeStepResult：
status=passed/failed/error；elapsed_ms为int|null；
request_safe/response_safe/assertions_safe/extracts_safe/error_code字段同C06。
StepResult的position/name/time由sink补充；raw ResponseData不得存进ORM。

RunOutcome：
status=passed/failed/error/interrupted；error_code=str|null；
last_completed_position:int（0表示无已完成步；失败/错误步也算已完成）。
runner正常路径只调用一次sink.finish并返回同一RunOutcome。
Worker不重复finish；仅SoftTimeLimitExceeded或未处理异常时尝试兜底finish。
RunNoLongerActive说明栅栏已失效，Worker直接退出，不修改终态。
所有HTTP、模板、提取错误都用明确领域异常映射为固定error_code；
失败响应body中的任意错误文本不能直接成为平台异常文案。
