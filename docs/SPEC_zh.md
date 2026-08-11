# text-cli Protocol Specification v1.3.2

协议让'自然语言'通过'网络'和'句法'成一个稳定的语义空间.在稳定的语义空间中:
能力提供方可以将'软件服务/经验服务/时间服务'等能力通过支持'协议'的'运行时'对外提供服务.
能力调用方用'自然语言'通过协议调动'运行时'调用'能力提供方'存入的能力,双方基于协议完成使能.
只要能通过网络输出'自然语言'并有对应'语义空间'的使用权限,无论是人还是AI,都可以通过'语义空间'获得服务.
协议生态与项目生态无关,协议原语是自然语言,协议生态是自然语言生态.

### 阅读约定

本规范使用以下格式区分不同层次的信息：

- **正文**：协议要求——所有符合协议的实现必须满足。
- **> 引用块**：实现参考——非强制，提供理解上下文的示例或建议，不构成合规约束。
- **表格中的"可选"标注**：该字段/行为在最低基线合规中非必须。
- **"是实现"/"协议不规定"**：标记协议的边界——该处由运行时自行决定具体机制，协议仅定义原则。

### 章节概览

| 章节 | 面向角色 | 说明 |
|------|---------|------|
| §1 指令格式规范 | 调用方 / 能力提供方 | 协议的通信原语：指令格式、请求/响应信封、错误码、能力发现 |
| §2 鉴权与配额 | 能力提供方 / 端点开发者 | 身份验证、配额保护、联邦凭证 |
| §3 Schema 元数据规范 | 能力提供方 | 如何声明指令包：包级与指令级字段定义 |
| §4 路径协议 | 能力提供方 | 如何编排多步指令序列（pipeline） |
| §5 聚合指令 | 能力提供方 | 多提供方降级与域级入口 |
| §6 运行时 | 运行时开发者 | 标准运行时 vs 旁路运行时的机制要求 |
| §7 多语言 | 能力提供方 | 指令的本地化声明与响应 |
| §8 集成端点 | 端点开发者 | 纯管道：鉴权、路由、透传 |



---

## 1. 指令格式规范

### 1.1 基本结构

```
AI:<领域>;<动作>,<参数1>,<参数2>,...
指令:<领域>;<动作>,<参数1>,<参数2>,...
```

- **当前两前缀**：`指令:`（中文入口，过渡期保留-1.5.0）和 `AI:`（长期规范）。两者等效。
- **领域**：命名空间，规范名 ASCII，别名不限字符集，通过别名支持多语言。
- **动作**：动词，规范名 ASCII，别名不限，通过别名支持多语言。
- **参数**：逗号分隔，顺序固定。末位参数可为自由文本（含逗号）。参数中 JSON 数组/对象可能含逗号——实现层追踪括号深度 `{}` `[]` 和字符串引号 `""`，只在深度为 0 的逗号处拆分。

> 规范名（`domain`/`action`）是路由的唯一主键，恒为 ASCII；一切非 ASCII 形式（含中文/其他语言别名）须由运行时经别名映射归一化回规范名后，方可参与路由与跨运行时去重。别名平等、双向、大小写不敏感，但仅是规范名的访问入口，不改变路由主键。

### 1.2 基于 HTTP 的 请求与响应

> 所有 HTTP 端点统一在 `/text-cli/` 前缀下。符合本协议的节点均使用此路径约定。



#### 1.2.1 请求结构

```
POST /text-cli/cli
Content-Type: application/json
Service-token: <token>

{"prompt": "AI:域;动作,参数1,参数2"}
```

#### 1.2.2 响应结构

```json
{
  "rst_types": "text",
  "rst_data": {"status": "ok", "result": 14},
  "rst_err": ""
}
```

- `rst_types`：反映响应类型。默认为 `"text"`。当 handler 在返回字典中包含 `pray_rst_types` 键时，骨架将其值提升至此字段。取值：`text` / `picture` / `video` / `audio` / `file`。
- `rst_data`：handler 返回的 JSON 对象，骨架直接承载 —— 不再以 `{"text": "..."}` 嵌套。调用方直接读取 `rst_data` 即可。
- `rst_err`：结构化错误字段。空字符串 `""` 表示成功，非空表示失败。取值见 §1.2.8。

> 提升键（如 `pray_rst_types`）由骨架在封 envelope 前消费并从 `rst_data` 剥离；调用方收到的 `rst_data` 不含任何骨架内部约定键。

**内容类型映射**（据 `rst_types` 值）：

| `rst_types` | 调用方行为 |
|------------|-----------|
| `"text"` | 直接展示 `rst_data` |
| `"picture"` | 渲染 `rst_data.url` |
| `"video"` | 渲染 `rst_data.url` |
| `"audio"` | 渲染 `rst_data.url` |
| `"file"` | 渲染 `rst_data.url` |

示例：

```json
// 纯文本
{"rst_types":"text","rst_data":{"status":"ok","result":14},"rst_err":""}
// 可渲染媒体
{"rst_types":"picture","rst_data":{"status":"ok","url":"https://example.com/photo.jpg","alt":"示例"},"rst_err":""}
// 结构化元数据
{"rst_types":"text","rst_data":{"status":"ok","lon":122.1,"lat":37.5},"rst_err":""}
```

异步指令返回 task_id：

```json
{"rst_types": "text", "rst_data": {"status": "pending", "task_id": "asr-12345"}, "rst_err": ""}
```

调用方通过 `GET /text-cli/tasks/{task_id}` 查询任务状态（见 §1.2.6）。

#### 1.2.3 GET 应急通道

```
GET /text-cli/cli?prompt=<URL编码的指令>
```

默认关闭。能力提供方显式开启。无需认证，风险自担。

#### 1.2.4 技能端点

```
GET  /text-cli/skills          → 公开技能列表（受 service_manifest 白名单控制）
```

**技能暴露控制**：服务通过 `service_manifest.json` 声明对外暴露的指令白名单：

```json
{"public_directives": ["map;geocode", "web;search", "weather;query"]}
```

白名单为空 = 全部暴露；有内容时只暴露列出的条目。`/skills` 端点据此过滤输出。

#### 1.2.5 健康检查

```
GET /text-cli/health
```

公开层返回 `{status, body, version, spec_version, public_skills}`。鉴权层返回完整 `capabilities`。

> **跨终端提供服务的运行时 SHOULD 在 `mechanism` 中声明其承载的机制子集**（如 `{"mechanism": ["directive_execution", "discovery", "async"]}`），供调用方程序化感知运行时的能力边界。不跨终端提供服务的运行时无此义务——调用方即使用者本人，不存在信息不对称。
>
> 机制标识词表（稳定标识，供 `mechanism` 引用）：`directive_execution`（指令运行）、`package_lifecycle`（包安装卸载）、`discovery`（指令发现）、`path`（路径编排）、`async`（异步任务调度）、`aggregate`（聚合降级）、`mesh`（联邦 Mesh）、`bridge`（协议桥）、`facade`（门面抽象）。

#### 1.2.6 异步任务查询

```
GET /text-cli/tasks/{task_id}
```

**成功响应**：

```json
{
  "status": "ok",
  "task": {
    "task_id": "task-0001",
    "domain": "domain",
    "action": "action",
    "state": "pending|running|done|error|cancelled",
    "result": {"..."},
    "progress": "步骤 3/8"
  }
}
```

**任务不存在**：`404` + `{"rst_err": "not_found"}`

> 当前任务状态仅支持轮询。对于长时任务，调用方以指数退避轮询。**（可选扩展）** 运行时可在任务创建时接受 `callback_url`，完成后以 **webhook（单向 HTTP POST）** 通知；是否实现 webhook 由运行时决定，非标准运行时强制要求。

> 同步调用中，配额耗尽以 `status:"stop"` 表达，触发聚合降级链。异步任务（`tasks/{id}` 轮询）执行中遭遇配额耗尽时，其 `state` 应记为终态 `error` 并附带原因 `quota_exhausted`；消费侧据该原因决定是否切换提供方重发，而非依赖同步降级链（异步上下文已脱离原调用方同步降级路径）。
>
> **`cancelled` 终态**（第五态）：`task;cancel,<task_id>` 将 `pending`/`running` 任务标记为 `cancelled`。cancelled 为终态，不可恢复为其他状态。
>
> **重启残留处理**：运行时重启应将所有残留 `running` 任务标记为 `error`，原因 `service_restarted`。


#### 1.2.7 指令发现

当'运行时'支持'指令发现'时,应参考以下要求:

##### 触发形式

| 指令 | 含义 |
|------|------|
| `AI:text-cli;query` | 全量纯文本（人类可读） |
| `AI:text-cli;query,json` | **机器可读 JSON**（本契约核心） |
| `AI:text-cli;query,compact` | 极简（每行一条 `domain;action`） |
| `AI:text-cli;query,python\|js\|mcp\|cloudbase` | 按 runtime 过滤 |
| `AI:text-cli;query,category[,<名>]` | 按分类过滤 / 列分类 |
| `AI:text-cli;query,<keyword>` | 关键词搜索 |
| `AI:文本指令;查询` | 中文别名（等效 `AI:text-cli;query`） |

尾参可附加语言覆盖：`,zh` / `,en`（仅影响文本/极简模式；JSON 模式返回全部 locale 变体，见 §3.5）。

> 实现参考：运行时过滤（`,python|js|mcp|cloudbase`）、分类过滤、关键词搜索均为**可选能力**——单语言运行时可不支持过滤或仅返回自身指令，不影响最低基线合规。

##### 响应信封

查询响应**复用 §1.2.2 信封**，不引入新字段：

```
{ "rst_types": "text", "rst_data": <发现数据>, "rst_err": "" }
```

- 成功：`rst_err` 为空字符串。
- 失败：见 §1.2.8，错误走 `rst_err` 主信号，不得塞入 `rst_data`。

#####  机器可读响应 canonical（`,json` 模式）

`rst_data` 结构：

```json
{
  "directives": [
    {
      "domain": "web-utils",
      "domain_zh": "网络工具",
      "action": "get_public_ip",
      "action_zh": "获取公网IP",
      "usage": "web-utils;get_public_ip",
      "usage_zh": "网络工具;获取公网IP",
      "params": ["target"],
      "description": "Return caller public IP",
      "description_zh": "返回调用方公网IP",
      "package": "web-utils",
      "runtime": "js"
    }
  ]
}
```

> 实现参考：上例为**完整形态**，包含所有可选增强字段。最低基线合规响应只需每条指令含 `domain`+`action`，其余字段可缺（消费端回退 canonical 或忽略）。

> **usage 前缀约定**：`usage` / `usage_zh` 字段**不含** `AI:` / `指令:` 前缀——它们是可调用指令的**主干部分**（`domain;action,params`），调用方需自行拼上前缀再发出（如 `AI:` + `usage`）。全文各节示例（§1.2.7 / §3.1 / §7.2）统一遵守此约定。


##### 字段级定义

| 字段 | 类型 | 层级 | 来源 | 说明 |
|------|------|------|------|------|
| `directives` | `array` | **强制** | 固定顶层键 | 指令列表容器，键名固定为 `directives` |
| `domain` | `string` | **强制** | 包 schema `directives[].domain` | 规范（英文）域，调用原语之一 |
| `action` | `string` | **强制** | 包 schema `directives[].action` | 规范动作，调用原语之一 |
| `usage` | `string?` | 可选 | 包 schema `directives[].usage` | 可调用指令原文（可由 `domain`/`action` 派生） |
| `package` | `string?` | 可选 | 包 schema `id`（扁平提升） | 包标识提升，用于分组/去重，单语言运行时可省 |
| `runtime` | `string?` | 可选 | 包 schema `runtime`（扁平提升） | 运行时标识提升；**非协议强制**（协议不指定运行时） |
| `domain_zh` | `string?` | 可选 | 包 schema `domain_zh` | 中文域别名（存在则带） |
| `action_zh` | `string?` | 可选 | 包 schema `action_zh` | 中文动作别名 |
| `usage_zh` | `string?` | 可选 | 包 schema `usage_zh` | 中文指令原文 |
| `description` | `string?` | 可选 | 包 schema `description` | canonical 描述 |
| `description_zh` | `string?` | 可选 | 包 schema `description_zh` | 中文描述 |
| `params` | `array?` | 可选 | 包 schema `directives[].params` | **原样透传** |

**分层规则：**

- **强制基线（任何运行时必过）：**
  - 每条指令**必须**含 `domain` 与 `action`——二者即调用原语 `AI:domain;action`，有即可调。
  - `directives` 容器键名固定，消费端按 `rst_data["directives"]` 读取，不得假设裸数组。
  - 内部 `_package` 嵌套对象**必须剥离**，不得出现在响应中。
  - 错误走 `rst_err` 主信号。
- **可选增强：**
  - `usage`：canonical 可调用指令原文（由 `domain`/`action` 可派生，推荐但非必填）。
  - `package` / `runtime`：顶层提升标签，用于跨运行时分组/去重——**不强制**，单语言运行时可省略。
  - `domain_zh` / `action_zh` / `usage_zh` / `description` / `description_zh`：locale overlay，缺失时消费端回退 canonical。
  - `params`：原样透传。

> 实现参考：协议不指定运行时，故契约**不得强制任何运行时支持多语言或打运行时标签**。多语言 / 运行时标签是"你愿意就上"的增强层，而非准入门槛。


##### 本地化策略

- **JSON 模式**：返回 schema 中存在的全部 locale 变体（canonical 字段 + `_zh` + `_en` 如声明）。消费端按自身需要选取字段，**服务端不做单语选择**。
- **文本/极简模式**：服务端按尾参 `,zh` / `,en` 选单一语言（回退 canonical）。
- **禁止**：在响应 item 内携带 `lang` 字段并依赖客户端按 `lang` 过滤——即响应结构不含 `lang` 键，消费端不应依赖任何未定义字段。

##### `params` 字段处理

`params` **原样透传**包声明，本契约不约束其形状：
- 标准 Python 包：字符串数组 `["text","target"]`（SPEC §3.3）。
- 平台子集（如 CloudBase 要求对象数组 `[{name,required,description}]`）：属平台约束，非协议 canonical。

> 实现参考：query 契约只规范"发现响应的传输形状"，`params` 的具体形状由包声明契约（SPEC §3.3）管辖；跨运行时差异是平台子集，不应在发现契约里强行统一。

##### 错误处理

查询自身失败时（如运行时无注册指令、查询内部异常），同样走 §1.2.8 错误响应

```json
{ "rst_types": "text", "rst_data": {"status":"error","reason":"..."}, "rst_err": "ERR_EXECUTION" }
```

- 错误码进入 `rst_err`（如 `ERR_EXECUTION` / `ERR_NOT_FOUND`），**不得**把错误塞进 `rst_data` 的业务字段（如旧的 `rst_data.text.status` 范式）。
- 空结果（无指令）视为成功：`rst_err=""`，`directives: []`。





#### 1.2.8 错误响应

错误码：

| 错误码 | 含义 |
|--------|------|
| `ERR_NOT_FOUND` | 能力不存在——上层可换路 |
| `ERR_EXECUTION` | 执行失败——可重试 |
| `ERR_ROUTING` | 路由/网络失败——停+告警 |
| `INVALID_PARAMS` | 参数不合法 |
| `ACCESS_DENIED` | Access Token 无效 |
| `SERVICE_DENIED` | Service Token 无效或提供方明确拒止（**不含配额耗尽**——配额耗尽是降级信号，返回 `{"status":"stop"}` 走降级链，见 §2.2，不产生本错误码） |

`rst_err` 字段承载错误码。空字符串 `""` 表示成功。
内层业务错误统一用 reason 字段名
错误以单行结构化字符串返回，不膨胀 调用方 上下文。

错误码（如 `ERR_NOT_FOUND`）和状态取值（如 `pending|running|done`）为闭集——实现不得引入协议未定义的取值。

### 1.3 关联方


- **调用方**：协议不关心调用者是人还是AI还是机器,只要能通过网络输出'自然语言'到'对应语义空间'并且能出示对应凭据,调用者即是符合协议的调用者.
- **能力提供方**：能力提供方通过将'软件服务/经验服务/时间服务'封装为'运行时'能够代理的服务,从而能够在自身离场后持续提供对应的服务.
- **运行时**：'能力提供方'将能力通过'指令包'安装的形式'注册'到'运行时',运行时基于'鉴权'对调用方提供服务.
- **集成端点**：'运行时'可以直接对'调用方'提供服务,也可以通过'集成端点'向'调用方'提供服务

> 运行时:'运行时'可以在各类平台或终端上部署.协议支持各种开发语言构造的运行时.




---

## 2. 鉴权与配额

> 实现参考：本章立原则，不规定具体机制。令牌的编码方案、凭证的存储介质与声明文件形状由运行时自行决定。

### 2.1 双层令牌

```
调用方 ──Access Token──> 集成端点 ──Service Token──> 技能服务
```

原则：**身份与商业分离**。

- **Access Token**：验证"你是谁"——由端点签发与验证，承载调用者身份。
- **Service Token**：承载"你与能力提供方的约定"——调用方与提供方私下约定，端点**透传**，不解析其语义、不存储其内容。

**令牌分段原则**：Service Token 在结构上分为三段——**服务实例标识 / 策略控制面 / 用户身份**。策略控制面内嵌于令牌本身：翻转控制面即可实现批量拦截与集中轮换，无需触达用户身份段。

**前缀不变性原则**：路由与拦截只依赖令牌的**固定长度前缀**（实例标识 + 策略控制面）。后段结构可扩展、可变长，前缀之外的部分对端点**永久无感知**。这是端点与令牌演进解耦的契约：令牌方案升级不要求端点升级。

> 实现参考：某实现可采用三段编码（实例标识 / 策略控制面 / 用户身份），前两段合并为固定长度前缀用于路由与拦截。具体位数与编码由运行时自行决定，非协议约束。

### 2.2 配额保护

原则：**配额耗尽不是错误，是降级信号**。

- 指令可在执行前通过 `quota;check,<target>[,<amount>]` 进行配额检查。
- 配额耗尽返回 `{"status":"stop"}`——聚合层将其作为降级信号，自动切换到下一个提供方（§5.4）。
- 语义分工：`status: "stop"` 走**降级链**（还有别的提供方可试）；`rst_err` 非空走**失败返回**（本次调用终止）。二者不混用。

作用域边界：status:"stop" 触发自动降级链的前提是请求命中聚合域（即 domain 在聚合路由表中登记、具有 default 多提供方链，见 §5.4）。聚合层在分发时识别 stop 并自动切换至下一提供方。

对于非聚合域的普通指令（含直接调用 quota;check 自身），返回 status:"stop" 仅作为信号原样透传给调用方，不触发任何自动降级——因为非聚合域不存在"可切换的下一提供方"。调用方收到 stop 后，若需故障转移，应由消费侧按 §3.3（AI 技能调度层端点级降级）或业务层自行决策。

同步调用中的 stop 由聚合层消费；异步任务（§1.2.6）内核中的 stop 处理见下文"异步降级"说明。

### 2.3 联邦 Mesh 凭证

**请托模型**：mesh 的本质是请托（delegation）——源节点将指令委托给 peer A，peer A 的自身路由表决定是否继续委托给 peer B。跳链不由源节点预先规划，而是由每一跳节点自身的路由声明决定。各运行时可通过配置限制跟随深度——这是运行时安全行为，非协议强制。

多节点联邦拓扑中，节点间转发遵循三条原则：

1. **凭证按 peer 隔离**：转发时只注入目标节点对应的凭证，不全量携带——任何一个 peer 都不应见到发给其他 peer 的凭证。
2. **映射链语义**：指令（`domain;action`）→ 目标节点（peer）→ 该节点凭证 → 注入转发。链条中每一步都是显式声明的映射，不做隐式推断。
3. **优雅降级**：凭证映射或存储缺失时**降级转发**（明示降级、记录告警），不静默阻断——联邦的可达性优先于凭证的完备性。该降级为**可用性**权衡，非安全推荐(本质是请托-出站,是运行时安全行为)；生产 mesh 应确保 `peer_credentials` 持久化到位，否则未授权节点可能收到本应带凭证限定的请求。

> 启用机制不等于自动发现/接纳 peer。peer 必须显式写进路由表才会存在；路由表为空 → 没有转发目标 → 没有任何请求出界 → 不存在"降级转发"，也不存在"未授权节点收到请求"。

> **凭证注入的运行时分层**：peer 凭证的持久化与注入是标准运行时的可选增强能力——标准运行时可以提供，但非最低基线要求。当标准运行时提供此能力时，凭证缺失应以 `_mesh_credential_degraded` 显式标注在响应 `rst_data` 中，供调用方程序化感知。安全兜底策略（拒绝跨跳 vs 降级转发）由运行时通过配置自行决定，协议不做强制。

> 实现参考：凭证存储介质、路由声明文件的形状、注入的字段名等具体机制由运行时自行决定。

---


## 3. Schema 元数据规范

协议识别四种类型的指令载体：

| 类型 | 实现 | 声明 |
|------|------|------|
| **native** | 基于实现'运行时'的语言的版本 | schema.json + 处理器（如 python: handler.py） |
| **nocode** | Markdown 知识文件 + path JSON | schema.json + knowledge/ + paths/ |
| **aggregate** | 纯声明，无 handler | aggregate/*.json |
| **pipeline** | 步骤链 JSON | path JSON + schema.json |

### 3.1 指令包 Schema（package-level）

每个指令包必须有一个 `schema.json`，声明包元数据和指令列表。

```json
{
  "id": "xx-cloud",
  "name": "XX Cloud",
  "name_zh": "XX云",
  "type": "native",
  "runtime": "python",
  "entry_runtimes": ["python"],
  "category": "云服务",
  "version": "1.0.0",
  "locales": ["zh", "en"],
  "trust": "internal",
  "description": "...",
  "description_zh": "...",
  "requires": {
    "pip": ["requests>=2.28"],
    "tc_packages": ["task-manager", "quota-manage"]
  },
  "credentials": [
    {
      "name": "xx_cloud_key",
      "description_en": "API key for XX Cloud",
      "description_zh": "XX云 API 密钥",
      "storage": "key_registry",
      "register_cmd": "AI:key;register,xx_cloud_key,<key>,api_key"
    }
  ],
  "directives": [
    {
      "domain": "xx-cloud",
      "domain_zh": "XX云",
      "action": "translation",
      "action_zh": "翻译",
      "usage": "xx-cloud;translation,<text>[,<target>]",
      "usage_zh": "XX云;翻译,<文本>[,<目标>]",
      "description": "Translate text via API.",
      "description_zh": "通过 API 翻译文本。",
      "params": ["text", "target"],
      "params_desc": {
        "text": "Text to translate",
        "target": "Target language ISO code (default: en)"
      },
      "outputs": ["text"],
      "estimated_time": "3s",
      "estimated_time_note": "单次翻译通常 1-3 秒，取决于文本长度和 API 响应速度"
    }
  ]
}
```

### 3.2 顶层字段

| 字段 | 必填 | 说明 |
|------|------|------|
| `id` | ✅ | 包唯一标识 |
| `name` | ✅ | 包名（canonical，英文 / 中立） |
| `name_zh` | 推荐 | 中文包名覆盖 |
| `description` | ✅ | 英文描述 |
| `description_zh` | 推荐 | 中文描述覆盖 |
| `type` | ✅ | `"native"` / `"nocode"` / `"aggregate"` / `"pipeline"`。描述**如何构建**指令包（载体类型） |
| `runtime` | ✅ | `"python"` / `"js"` / `"mcp"` / `"cmd"` / `"path"` / `"aggregate"`。描述**以何种语言/形态运行**；当 `type` 为 `pipeline` / `aggregate` 时，`runtime` 取同名值（`"path"` / `"aggregate"`）或由运行时按 `type` 推定而省略。二者正交：`type` 描述构建方式，`runtime` 描述运行语言 |
| `category` | ✅ | 分类标签 |
| `locales` | ✅ | 多语言覆盖。格式 `["<ISO 639-1 语言代码>", ...]`（如 `["zh", "en"]`）。中文使用 `"zh"` 非 `"cn"` |
| `trust` | ✅ | `"internal"` / `"community"` / `"public"` |
| `requires.<ecosystem>` | 否 | 外部生态依赖的通用约定：键名为生态标识，值为该生态语法下的依赖列表。生态名开放，不设闭集。示例：`requires.pip`（Python 包依赖，如 `["requests>=2.28"]`）、`requires.npm`（Node.js 包依赖，项目级安装，如 `["@scope/name@^1.0"]`） |
| `requires.tc_packages` | 否 | 指令包间依赖 |
| `requires.modules` | 否 | `text_cli_modules/` 运行时依赖 |
| `requires.binaries` | 否 | 系统二进制 / 全局 CLI 依赖。格式：`{"<name>": {"source": "system"\|"package"\|"npm-global", "min_version": "..."}}`。`source: "system"` = OS 包管理器安装；`source: "package"` = 随包分发；`source: "npm-global"` = npm 全局安装 |
| `entry_runtimes` | 否 | 包的运行时环境清单（当单个 `runtime` 不能完整描述时使用）。格式：`["python", "js"]`。不影响框架注册方式，仅声明运行前需准备的环境 |
| `requires.service_db` | 否 | 声明包依赖的服务端持久化表面（表名列表，如 `["token_registry", "token_call_logs"]`）。安装时建立、卸载时回收。存储介质与建表机制是实现 |
| `tables` | 否 | 声明包自建的持久化表面。安装时建立、卸载时回收。声明语法与建表机制是实现 |
| `credentials` | 否 | 需要的凭据（key name → source） |
| `entry` | 否 | 公开端点 URL |
| `mcp_server` | 否 | MCP server 名 |
| `version` | 推荐 | Semver |

### 3.3 指令级字段（directives[]）

| 字段 | 必填 | 说明 |
|------|------|------|
| `domain` | ✅ | 指令域 |
| `domain_zh` | 推荐 | 中文域别名 |
| `action` | ✅ | 动作名 |
| `action_zh` | 推荐 | 中文动作别名 |
| `usage` | ✅ | 用法示例（规范名） |
| `usage_zh` | 推荐 | 中文用法示例 |
| `description` | ✅ | 英文描述 |
| `description_zh` | 否 | 中文描述 |
| `params` | 否 | 参数名列表 |
| `params_desc` | 否 | 参数说明对象 |
| `mcp_tool` | 否 | 原始 MCP tool 名 |
| `outputs` | 否 | 指令返回的 status 级字段名列表（声明性，非运行时强制）。路径引擎用于 `{step.field}` 引用校验；后续考虑用图自动建立 `:OUTPUTS` 关系。声明了但未返回的字段不会导致错误 |
| `estimated_time` | 否 | 指令最大预期执行时间。格式 `"<数值><ms\|s\|h>"`（如 `"500ms"`、`"30s"`、`"2h"`）。供异步调度器做超时预估和优先级决策。同步指令不填 |
| `estimated_time_note` | 否 | 预估时间的解释说明。如 `"0.5h视频转换约120s，耗时与视频时长近似线性增长"`。配合 `estimated_time` 使用，帮助调用方推算不同输入规模下的预期耗时 |

### 3.4 聚合指令 Schema

聚合指令，只有路由声明。

```json
{
  "id": "map",
  "type": "aggregate",
  "domain": "map",
  "name_zh": "地图服务",
  "description_zh": "地图服务：多提供方自动降级",
  "default": ["x1-map", "x2-map", "x3-map"],
  "providers": {
    "x1-map": {"geocode": "x1-map;geocode", "route": "x1-map;route"},
    "x2-map": {"geocode": "x2-map;geocode"},
    "x3-map": {"geocode": "x3-map;geocode"}
  }
}
```

| 字段 | 必填 | 说明 |
|------|------|------|
| `id` | ✅ | 聚合唯一标识 |
| `type` | ✅ | 固定为 `"aggregate"` |
| `domain` | ✅ | 对外暴露的聚合域名 |
| `default` | ✅ | 降级链顺序 |
| `providers` | ✅ | 提供方→action 映射。值格式 `"<domain>;<action>"` |

### 3.5 路径声明条目

```json
{
  "id": "route-map",
  "name_zh": "地图连线",
  "type": "pipeline",
  "version": "1.0.0",
  "input_schema": {"type": "string"},
  "output_schema": {"type": "picture"},
  "requires": ["map;geocode", "map;route", "xx-map;static-map"],
  "steps": [
    {"id": "start", "instruction": "map;geocode,{input.address}", "output_as": "start"},
    {"id": "route", "instruction": "map;route,{start.lat},{start.lon},{end.lat},{end.lon}", "output_as": "route"},
    {"id": "map", "instruction": "xx-map;static-map,{end.lat},{end.lon},14,600x400,...", "output_as": "map"}
  ]
}
```

| 字段 | 必填 | 说明 |
|------|------|------|
| `id` | ✅ | 路径唯一标识 |
| `type` | ✅ | 固定为 `"pipeline"` |
| `version` | 推荐 | Semver |
| `input_schema` | 推荐 | 输入参数的 JSON Schema 片段 |
| `output_schema` | 推荐 | 输出结果的 JSON Schema 片段 |
| `requires` | ✅ | 依赖的指令列表 |
| `default_source` | 否 | 路径级默认端点 URL。省略时所有 step 在本机服务 执行 |
| `steps` | ✅ | 步骤数组 |

---


## 4. 路径协议

### 4.1 管道闭包原则

**路径只做编排和插值。文件 IO、API 调用、推理——全部通过指令完成。**

```
路径引擎：编排指令序列（step1 → step2 → step3）
指令：     执行具体操作（tc-markdown;read, ai;infer, map;geocode）
```

路径不读文件——它调 `tc-markdown;read`。不推理——它调 `ai;infer`。不调 API——它调 `map;geocode`。这是协议的设计红线。

### 4.2 步骤语法

```json
{
  "id": "step_id",
  "instruction": "domain;action,{input.key},{prev.field}",
  "if": "{step.field} == 'NOMATCH'"
}
```
```json
{
  "id": "step_id",
  "instruction": "domain;action,{input.key},{prev.field}",
  "if": {"step": "prev", "field": "field", "equals": "NOMATCH"}
}
```
> 两种写法地位平等：字符串式适合人工编写与简单 `==`/`!=`；对象式适合程序生成与复杂条件。
> 路径引擎对引用未声明字段的处理须全局一致：校验仅产生警告，执行时未定义变量一律以空串代入，不因运行时不同而改变行为。禁止某一实现将未声明引用当作阻断错误。


| 语法 | 含义 |
|------|------|
| `{input.key}` | 用户输入 JSON 中的 key 字段 |
| `{step_id.field}` | 上一步输出的 JSON 字段（支持深度路径如 `{geo.poi.0.name}`） |
| `"if"` | 可选条件——条件为 false 时跳过此步骤。支持两种**地位平等**的写法，各有适用场景：(a) 字符串简写 `"{step.field} == 'VALUE'"`（仅 `==`/`!=` 文本比较），适合人工编写与简单条件；(b) 对象式 `{step, field, equals\|contains\|matches\|exists}` 或带 `op`/`value` 的比较，支持顶层 `all`/`any` 复合，适合程序生成与复杂条件。协议**不指定单一主形式** |
| `"instruction"` | 要分派的 text-cli 指令模板 |
| `"source"` | 可选 — 步骤级端点 URL。省略时继承 `default_source` 或本机服务。值必须为完整 URL，如 `"http://10.168.1.122/text-cli/cli"` |
| `"mode"` | 可选 — pipeline 的执行模式。当前定义 `"toolchain"`（串行链）、`"parallel"`（并行，最小形状为 `{"mode":"parallel","strategy":"all|first_ok"}`，`strategy` 取值 `all`（全部执行）/`first_ok`（任一成功即返回））、`"map"`（循环迭代，对集合逐元素执行子步骤数组，最小形状为 `{"mode":"map","items":"<变量名>","steps":[...]}`；`as`（元素绑定名，默认 `"item"`）、`collect_as`（收集变量名，默认 = `output_as`）、`max_iter`（扇出上限，可选；部署侧 yaml 配置 `paths.map_max_iter`，非 LLM 编写面，非协议强制）、`on_error`（`"break"` 熔断 / `"continue"` 跳过，默认 `"break"`）、`concurrency`（`"serial"` 串行 / `"parallel"` 并行，默认 `"serial"`）均为可选增强字段）。协议保留扩充其他模式与 strategy 的权利 |

> `{step_id.field}` 引用的字段应在目标指令的 schema.json `outputs` 声明范围内。路径引擎可据此做字段引用校验。
> **未定义变量行为**：引用的变量不存在时，替换为空字符串 `""` 并记录 `WARNING: 未定义变量 {name}`。不抛错——异步场景下变量可能因步骤执行时序暂未就绪，抛错会阻断路径执行。

> 实现参考：`mode` 默认为 `"toolchain"`——步骤按数组顺序串行执行，前一步的输出通过 `{step_id.field}` 注入后续步骤。`"toolchain"`、`"parallel"`（并行，含 `strategy: all|first_ok`）与 `"map"`（循环迭代，对集合逐元素执行子步骤）为当前定义模式；各运行时可按需实现并注册其他模式，协议不枚举所有可能的 mode 值。

路径跨节点执行示例：

```json
{
  "id": "cross-node-demo",
  "default_source": "http://10.168.1.122/text-cli/cli",
  "steps": [
    {"id": "local", "instruction": "tc-datetime;now", "output_as": "time"},
    {"id": "remote", "instruction": "tc-ffmpeg;info,{video.path}", "source": "http://10.168.1.122/text-cli/cli", "output_as": "info"}
  ]
}
```

`source` 省略时继承 `default_source`；`default_source` 也省略时默认本机服务。


### 4.3 条件执行

```json
{"id": "fallback", "instruction": "...", "if": "{step.field} == 'NOMATCH'"}
{"id": "fallback", "instruction": "...", "if": {"step": "prev", "field": "field", "equals": "NOMATCH"}}
```

**条件算子**（对象式 `if` 可用）：

| 算子 | 写法 | 说明 |
|------|------|------|
| 相等 | `{"step","field","equals":"V"}` | 文本/值相等 |
| 包含 | `{"step","field","contains":"V"}` | 子串/元素包含 |
| 匹配 | `{"step","field","matches":"regex"}` | 正则匹配 |
| 存在 | `{"step","field","exists":true}` | 字段非空/存在 |
| 比较 | `{"step","field","op":"gt\|lt\|gte\|lte\|ne","value":N}` | 数值比较,`op` 与 equals/contains/matches/exists 同时出现时，op 生效，其余字段被忽略|
| 复合 | `{"all":[...]}` / `{"any":[...]}` | 多条件与/或，元素为上述任意算子对象 |

字符串式仅支持 `==`/`!=` 文本比较，是对象式的等价简写。



### 4.4 上下文注入防护

路径声明天然抗注入——`steps` 在 JSON 中固定，数据通过命名管道单向流动。注入载荷永远不会从数据位置逃脱到指令位置。循环绑定 `{as}`（如 `{item}`）同属参数位，数据仍无法从数据位逃逸到指令位——`map` 的迭代强化而非削弱此保证。

### 4.5 门面入口

```
text-cli;pro,<name>[,<input_json>]
```

原则：门面层维护**门面注册表**，将短名称（name）映射到执行目标（target）——目标可以是一条路径，也可以是一条聚合指令。

> 实现参考：注册表的文件形状与解析机制由运行时自行决定。

门面指令与原子指令平权——调用方不感知背后的实现是单步还是多步。这是高级指令门面层的核心价值：**按服务领域数增长，而非按工具数增长。**

---

## 5. 聚合指令

### 5.1 概述

聚合指令提供域级入口，将多个提供方收敛为一条指令。调用方不感知提供方差异，只看到一个入口。

### 5.2 声明

聚合指令以纯声明方式定义（无 handler），声明形状与字段见 §3.4。

> 实现参考：声明文件的存放位置与加载时机由运行时自行决定。

### 5.3 提供方不区分来源

native handler、MCP bridge、Skill Bridge——在聚合降级链中地位平等。`providers` 中的值只要是一个可被 `dispatch()` 解析的 `domain;action` 即可。

### 5.4 降级链

```
请求 → 聚合命中
  → 查 default 降级链
  → 依次 dispatch 每个提供方
  → 返回第一个成功结果
```

降级触发条件：返回 `status: "stop"`（配额耗尽）、返回 `status: "error"`、dispatch 异常或指令未注册。

> 用户显式指定提供方时，该提供方返回的 `status:"stop"` 视为硬失败（终止本次调用、不走降级链），因为用户的显式选择表达了确定性意图，降级链仅对默认路由生效。

### 5.5 用户显性选择

末参数匹配提供方名时，优先该提供方：

```
map;geocode,威海,x2-map     → 只用 x2-map，不降级
```

### 5.6 聚合在请求管道中的位置

原则：**聚合最先命中**——请求进入分发管道时优先匹配聚合入口，未命中时继续走后续分发管道。

> 实现参考：管道的具体段序由运行时自行决定。

### 5.7 协议桥

原则：运行时可通过协议桥将其他协议生态的能力（如 MCP tools、第三方 skill）映射为本协议指令。

- 桥接而来的指令与 native 指令**平权**——可被解析、可作为聚合降级链中的提供方、可被路径编排引用。
- 桥接应是平等互惠的, 有能力时尽可能建双向桥。
- 调用方不感知指令背后是 native 实现还是协议桥接。

> 实现参考：具体桥接机制（声明文件、适配器、编译方式）由运行时自行决定。

---

## 6. 运行时

### 6.1 运行时分类

运行时在**两个相互独立的维度**上定位：

**维度一：机制覆盖度**——决定「能跑哪些包」。

- **最小合规运行时（强制基线）**：实现且仅实现机制 1「指令运行」。接收 `AI:domain;action[,params]`，路由到实现，返回 `{rst_types, rst_data, rst_err}` 三字段信封。**这是运行时的准入门槛，也是全部门槛。**
- **旁路运行时**：在强制基线之上实现任意机制子集。按部署形态可分为云平台（如 CloudBase、Cloudflare，由平台方决定支持哪些机制子集）和多语言 SDK（以 SDK 形态跨语言接入如 pypi、npm）。
- **标准运行时**：实现 §6.2.1 全部机制。标准运行时是能力定义，不特指某一语言——任何能完整承载协议机制集的实现都是标准运行时。

三者是**同一条梯度上的位置，不是三个等级**。不实现任何可选机制，不影响合规性。

**维度二：是否跨终端提供服务**——决定「有没有鉴权与声明义务」。

判据：**调用方是否位于 OS/进程边界已经担保的信任域之外。**

- **不跨终端**：调用方与运行时处于同一 OS/进程信任域内（进程内库、loopback 绑定 127.0.0.1）。**无鉴权义务、无能力声明义务**——调用方即使用者本人，不存在信息不对称。
- **跨终端**：服务对象超出 OS 担保范围（网络可达）。**产生鉴权义务（§2）与能力声明义务（§1.2.5 `capabilities`）**。

两个维度互不推导：最小合规运行时可以跨终端（如 no-code 模板），全量标准运行时也可以只绑 loopback（如 copilot）。

> 约束示例：`textcli-loader`（PyPI 旁路运行时）为进程内库——不跨终端，机制覆盖度 2–3，不支持 `mesh` 和 `path` 机制。


### 6.2 标准运行时

#### 6.2.1 标准运行时必要的机制

标准运行时必须完整实现以下协议机制集（闭集）。实现全集即为标准运行时；只实现子集的形态归入旁路运行时（§6.1）。协议只规定机制集本身，不规定各机制的实现方式。

| 机制 | 说明 | 规范章节 | 层级 |
|------|------|----------|------|
| 指令运行 | 对符合协议的指令进行解析、路由、执行与响应封装 | §1 | **强制基线** |
| 安装及卸载指令包 | 指令包生命周期管理：安装时注册指令与依赖，卸载时完整回收 | §3 | 可选增强 |
| 指令发现 | 基于 schema 的指令查询（§1.2.7） | §1.2.7 / §3 | 可选增强 |
| 路径编排 | 指令序列的编排与插值执行 | §4 | 可选增强 |
| 异步任务调度（状态持久化） | 异步指令的任务化调度与查询，状态持久化为其支撑 | §1.2.6 | 可选增强 |
| 聚合与降级链 | 域级聚合入口与提供方降级 | §5 | 可选增强 |
| 联邦 Mesh | 多节点联邦拓扑下的按 peer 凭证注入与转发 | §2.3 | 可选增强 |
| 协议桥 | 与其他协议生态的双向桥接（如 MCP 为其一种实现） | §5.7 | 可选增强 |
| 门面抽象 | 短名到执行目标的映射，门面指令与原子指令平权 | §4.5 | 可选增强 |

**鉴权与配额**不属于运行时能力集，属于**跨终端关系的属性**（见 §2 / §8）：
- 跨终端提供服务的运行时**必须**实现鉴权——出现了一个不了解你的第二方，凭据是唯一的信任锚点。
- 不跨终端提供服务的运行时**无鉴权义务**——调用方即使用者本人，范畴之外。
- 配额保护（§2.2）同理：仅在跨终端场景下产生义务。

**保留域扩展**：本表为必备最小表面。运行时 MAY 在 `text-cli` 保留域内扩展自管理指令，不污染第三方命名空间。先例：copilot 的 `co-install` / `co-uninstall`（见 §6.2.2）。

**包能力分类（术语）**：指令包按其是否依赖宿主资源，分为两类——**非宿主特权包**：能力不访问宿主机的终端/文件/Git/shell/本地服务等资源（如纯函数、外部 API 调用）；**宿主特权包**：能力依赖宿主机执行面（如截屏、摄像头、麦克风、锁屏、本地服务管控、shell 桥接）。本分类为协议层术语定义，仅用于厘清包的能力性质，不引入新的 schema 字段。
> 基于包能力分类，**非宿主特权包**的区分,在运行时内部允许内部分为copilot 与 service 是同一标准运行时的不同组件。**非宿主特权包**可在 copilot 与 service 下加载，**宿主特权包**因依赖宿主资源，仅能在 copilot（`127.0.0.1` 本机代理）下加载,组件的部署形态与组合方式是实现选择，协议不作规定。

> 实现参考：包的安装边界、校验与隔离机制由运行时自行定义（见 §6.2.2 ）。

**跨信任域的能力提供**:copilot 与 service 既是独立的，也是合作的。**在能力提供者显式同意时**，service 可消费 copilot 贮存的指令。这是宿主特权包从「不跨终端」跃迁到「跨终端」的唯一授权路径——跃迁的那一刻，鉴权义务从无到有。「同意」的表达形式由运行时定义，协议只要求其**显式**且**可撤销**。

**平台自管理元指令表面**：标准运行时通过 `text-cli` 域的元指令对外暴露自管理能力：

| 元指令 | 语义 |
|--------|------|
| `text-cli;install,<包名>` | 安装指令包 |
| `text-cli;uninstall,<包名>` | 卸载指令包（完整回收文件、注册项与自建表） |
| `text-cli;export,<包名>` | 单包导出——导出结构与安装格式一致，可被 `install` 直接消费 |
| `text-cli;export-all` | 全量导出 |
| `text-cli;packages` | 列出已安装包 |
| `text-cli;query,<关键词>` | 指令发现/搜索 |
| `text-cli;path,<json_or_file>[,<input_json>]` | 执行路径步骤序列 |
| `text-cli;pro,<name>[,<input_json>]` | 门面入口 |

> 实现参考：元指令的安装器行为（按 runtime 类型部署哪些文件、如何建表等）由运行时自行决定，协议只规定指令表面与语义。

#### 6.2.2 标准运行时-python

Python 标准运行时是标准运行时的一种具体实例（标准运行时是能力定义，不特指某一语言，见 §6.1）。

由三组件构成：

- **copilot**：面向本机终端的运行时组件。
- **service**：面向网络服务的运行时组件。
- **MCP**：协议桥机制的承载组件，实现与 MCP 生态的双向桥接。



```
AI:text-cli;co-install,<package-name>
AI:text-cli;co-uninstall,<package-name>
```


---



## 7. 多语言

协议指令格式本身语言无关（见 §1.1：`domain;action` 规范名是 ASCII，别名不限字符集，运行时对别名做归一化后路由）。本章规定多语言的三条**协议原则**，分三层：查询响应（L1）、注册（L2）、执行（L3）。翻译责任在包内，端点不翻译（端点为纯转发管道，见 §8 / 生态规范）。

> 实现参考：本章立原则，不规定具体机制。运行时如何抽取语言、包内如何用数据表承载翻译，因语言 / 运行时而异。

### 7.1 查询时的多语言响应（L1）

原则：用户发起查询（如 `text-cli;query`）时，运行时应当返回 `schema.json` 中**对应语言**的内容。

- 协议只立原则：**查询响应按调用方期望的语言抽取相应字段**，不规定抽哪些语言、如何抽。
- canonical 字段（如 `domain` / `action` / `usage` / `name`）为默认 / 语言中立（英文）；本地化覆盖以 `_zh` 为例——`domain_zh` / `action_zh` / `usage_zh` 提供中文覆盖，缺失时回退 canonical。
- 调用方表达期望语言是**实现机制**（如元指令尾参、服务端配置），协议不规定其形态；运行时支持哪些语言是**实现选择**，不是协议约束。

> 实现参考：某运行时以 `field_zh` 等覆盖抽取、缺失回退 canonical，调用方语言优先于配置默认。这是一处实现示例，非协议要求。

### 7.2 指令包注册的多语言 schema（L2）

原则：指令包把自己的多语言内容**注册进 `schema.json`**——这是声明面的契约。

- `schema.json` 是跨实现语言共有的契约表面（无论 python / node / mcp / cmd / path / aggregate / nocode），多语言声明形状相同。
- `locales`：声明包支持的**输出语言**（ISO 639-1，中文 `zh`）。供 AI / 运行时发现。
- canonical 字段为默认（英文 / 中立）；以 `_zh` 为本地化覆盖示例：
  ```json
  {
    "locales": ["zh"],
    "directives": [{
      "domain": "weather",
      "domain_zh": "天气",
      "action": "query",
      "action_zh": "查询",
      "usage": "weather;query,<city>[,<date>[,<lang>]]",
      "usage_zh": "天气;查询,<城市>[,<日期>[,<语言>]]"
    }]
  }
  ```
- 协议规定**字段形状**（`locales` + `<field>_zh` 覆盖约定），**不规定运行时必须支持其中哪些语言**——那是实现层的事。

> 注：`name` 本身为英文 / 中立，故不显式定义 `_en`；canonical 即承担英文形态。其他语言按同一 `<field>_<lang>` 约定扩展，协议不再单列。

### 7.3 指令执行对调用时多语言的响应（L3）

原则：指令执行函数应对**调用时传入的语言**做出响应——这是**包内的抽象**，协议不规定其机制。

- 包应对调用时语言负责：调用方可在指令调用中显式携带语言（如末位可选位置参数 `lang`，默认 `zh`）。
- 语言越界时**优雅降级到默认语言**，不应返回 `ERR_NOT_FOUND`（§1.2.8 的 `ERR_NOT_FOUND` 仅用于路由层别名未命中，不用于输出语言）。
- 具体机制（数据驱动 i18n 表、模板即资源、错误文案本地化、输入输出分离等）是**实现**，因语言而异；协议只要求"执行对调用时语言负责"这一原则。

> 实现参考：Python 包可用 handler 内的 I18N 数据表 + `lang` 位置参数实现；Node / MCP / nocode 各自承载位置不同。这些都是合法实现示例，非协议唯一规定。


---



## 8. 集成端点

### 8.1 架构角色

集成端点是 text-cli 架构中位于调用方与运行时之间的公网入口组件。它不执行指令、不持有能力——只做**鉴权、路由和透明转发**。

```
调用方 ──→ 集成端点 ──→ 运行时 A (:28050)
                  ├──→ 运行时 B (:28050)
                  └──→ 运行时 C (:28050)
```

调用方的请求到达端点，端点校验调用方身份后，将请求转发至后端运行时，结果原样返回给调用方。

### 8.2 纯管道原则

与运行时本身一样，集成端点是纯管道：

- **不解析** `rst_data` 的内容——`pray_rst_types` 为协议约定键名，不属于内容解析
- **不执行** 任何 handler——指令的执行始终在后端运行时完成
- **不存储** 调用方的 Service Token——端点只透传，不拥有其语义

端点的唯一职责是：校验 Access Token → 匹配后端 → 透传请求 → 返回结果。

### 8.3 多后端聚合

一个端点可以聚合多个后端运行时的指令表。端点启动时从各后端拉取 `/text-cli/skills`，合并为统一的对外能力目录。调用方通过端点调用指令时，端点根据指令的 `domain;action` 将请求路由到对应的后端。

调用方不感知背后的运行时数量、地址或形态（标准 Python service、Docker 部署、旁路运行时——在端点后端列表中地位平等）。

端点对外暴露的指令表中，每条指令的调用地址被重写为端点自身的 URL——调用方始终向端点发请求，不感知后端运行时的真实地址。

### 8.4 透传 Service Token

Service Token 由调用方与能力提供方私下约定（§2.1）。端点**只透传**——不验证其有效性、不解析其结构、不存储其内容。端点在联邦 Mesh 场景下按 peer 注入凭证（§2.3）时，仅使用 Service Token 的固定长度前缀做策略控制面识别——前缀之外的 Token 内容对端点永久无感知。

### 8.5 可选安全层

端点可以提供独立于协议的三层可选防御：

1. **IP 过滤**：CIDR 黑名单
2. **速率限制**：滑动窗口限流
3. **Token 鉴权**：Access Token 校验调用方身份（§2.1）

这些是端点级的可选机制，不是协议强制要求。

### 8.6 端点不做什么

- 不执行指令——执行始终在后端运行时
- 不托管结算——计费由调用方与提供方私约
- 不拥有 Service Token 的语义——端点只透传
- 不保证后端可用性——后端不可达时返回 `ERR_ROUTING`

> - 不保证后端可用性——后端不可达时返回 `ERR_ROUTING`（端点侧 `ERR_ROUTING` **仅**用于此场景，治理拒止不得共用，见 §8.7）


**8.7 端点自有响应**

端点的响应分为两类：

| 类别 | 触发条件 | 处置 |
|------|---------|------|
| **转发响应** | 请求已到达后端运行时 | 后端信封原样返回，端点不得改写 |
| **自有响应** | 请求被端点终止，未到达后端 | 端点自行构造完整信封 |

端点产生自有响应时，**必须**输出完整的三字段信封（`rst_types` / `rst_data` / `rst_err`），不得省略 `rst_err`。

- `rst_err` 取值必须落在 §1.2.8 闭集内；
- 端点的治理原因（如 `IP_BLOCKED`、`RATE_LIMIT_EXCEEDED`）置于 `rst_data.reason`，不受闭集约束。

端点自有响应的 `rst_err` **只能**取以下四个值：

| 场景 | `rst_err` |
|------|-----------|
| 端点安全层拒止（§8.5：IP 过滤 / 速率限制 / Token 鉴权 / ST 前缀拦截） | `ACCESS_DENIED` |
| 请求参数或指令格式不合法 | `INVALID_PARAMS` |
| 指令未在聚合表中登记；端点通道未开启 | `ERR_NOT_FOUND` |
| 后端不可达（连接失败 / 超时，见 §8.6） | `ERR_ROUTING` |

端点**不得**在自有响应中使用 `SERVICE_DENIED`——端点不解析 Service Token（§8.4），亦非能力提供方，不具备产出该码的资格。

端点亦不得使用 `ERR_EXECUTION`——端点不执行指令（§8.1、§8.6）。

> 实现参考：
> ```json
> HTTP 403
> {"rst_types":"text","rst_data":{"status":"error","reason":"IP_BLOCKED"},"rst_err":"ACCESS_DENIED"}
> ```
> `reason` 中的治理词汇由端点自行定义，协议不约束其取值。
>
> 本动议不涉及 HTTP 状态码与 `rst_err` 的对应关系，端点沿用现有状态码。

---


## 附录A 协议的原语与生态

### 协议原语

协议的根契即是以'祈使句'压缩后的'自然语言'.
协议以自然语言为原语,原生支持多语言.

```
AI:math;eval,2+3*4+pi  ->英语
AI:数学;计算,2+3*4+pi  ->简体中文
AI:数学;計算,2+3*4+pi  ->日语
AI:數學;計算,2+3*4+pi  ->繁体中文
AI:수학;계산,2+3*4+pi  ->韩语
```
`协议`是定义的是以`协议原语`进行请求时,应收到的响应.
项目`text-cli`是对`协议原语`的支持,`协议原语`本身不依赖任何项目.
`协议`源于对'自然语言'的探索,没有人或群体拥有'自然语言',也没有任何人或群体拥有`协议原语`.`协议`由项目`text-cli`从对'自然语言'的推理得到.
`协议`当前由项目`text-cli`维护,当项目的腐败试图侵染`协议`,协议本身以自然语言为根基,任何项目都可以基于`协议原语`对协议进行纠偏.


项目`text-cli`对协议的主要修订如下:
- **调用平等**：凡是可以生成'自然语言'的人或ai,均可用'文本指令'向接收该指令的'运行时'发起请求。
- **响应信封**：'运行时'对'文本指令'处理是如何响应不同模态的制品。
- **指令查询**：用过'查询'指令获得'目标运行时'能够提供哪些'指令服务'
- **一维契约**：对用户而言，入口永远只有一句 `AI:域;动作,参数`，出去永远只有一个结果。内部的聚合降级、路径编排、联邦多跳、多提供方选路——全部发生在接缝之后，**对调用方不可见**
- **运行时**：运行时是处理'文本指令'请求的实体.`运行时`不绑定编程语言,`运行时`概念体只定义能力范围(协议新增能力范围时,必须有对应的`落地实现`以保证协议的完整性).运行时应当附带若干能够处理'文本指令'的'指令包'.
- **指令包**：在协议中提案`指令包`相关内容时,对'指令包'的定义要同步提供'指令包创建指南,转化框架,模板,示例包'.并且'指令包'的'最小实现'应让`参数不高于9b`的llm和没有代码能力的人完成对应实现.

### 协议生态

从人类的每一次言语表达,到LLM每一次生成'自然语言'的响应,都是在使用'自然语言'.
自然语言的生态,就是'协议'的生态,项目从不拥有'协议',只是擦拭浮尘.

| 传统代码生态 | 协议 的自然语言生态 |
|---|---|
| 繁殖单元 = 代码库 | 繁殖单元 = 一条祈使句 + 一个包 |
| 生产者 = 开发者 | 生产者 = 任何会表达的人(花店老板...) |
| 门槛 = 编程能力 | 门槛 = 表达能力 |
| AI 是消费者 | AI 是消费者 + 生产者(帮你把经验变成包) |

**花店老板口述十年经验 → AI 封装成指令/或无代码封装成指令 → 别的花店老板或它的 AI 直接调用**——这个循环里没有一行代码是人类写的,但它完成了"经验 → 服务 → 被消费"的完整繁殖。**这就是自然语言的生态:以自然语言为介质,任何人都能繁殖能力。**

协议不是"等着被生态验证"——是"以最低门槛等待繁殖"。而最低门槛,就是会说话。


---


## 附录B 

### 1.0
- **指令格式规范**：协议的通信原语：指令格式(`AI:<领域>;<动作>,<参数1>,<参数2>,.../指令:<领域>;<动作>,<参数1>,<参数2>,...`)、请求/响应信封、错误码、能力发现、如何声明指令包：包级与指令级字段定义
- **运行时**：身份验证、配额保护、路径协议、 聚合指令 
- **集成端点**：鉴权、路由、透传(纯管道)
### 1.1
- **一维契约**：对用户而言，入口永远只有一句 `AI:域;动作,参数`，出去永远只有一个结果。内部的聚合降级、路径编排、联邦多跳、多提供方选路——全部发生在接缝之后，对调用方不可见。
- **指令包**：引入指令包概念（schema.json 声明），定义包级元数据（id/name/type/runtime/category/trust/version）与指令级字段（domain/action/usage/description/params），以及包安装/卸载生命周期。
- **'指令:'退出**：遵循'1.2'版本以上协议的运行时,可不再支持'指令:'前缀,最终在'1.5'版本协议中,将'指令:'完全退出.
- **指令发现强化**：`text-cli;query,json` 机器可读响应引入 `directives` 容器与字段级定义（domain/action 强制基线 + usage/package/runtime/domain_zh/action_zh/usage_zh/description/description_zh/params 可选增强）。分层规则：强制基线 / 可选增强 / 禁止行为。本地化策略（JSON 模式返回全部 locale 变体，文本/极简按尾参选语言）。
- **路径模式扩展**：pipeline 步骤新增 `mode` 字段，支持 `"toolchain"`（串行，默认）和 `"parallel"`（并行，strategy: all/first_ok）。
- **技能端点暴露控制**：新增 `service_manifest.json` 的 `public_directives` 白名单，控制 `/text-cli/skills` 端点对外暴露的指令范围。白名单为空=全部暴露，有内容时只暴露列出的条目。
### 1.2
- **多运行时指令包**：指令包 schema 新增 `entry_runtimes` 字段，声明包的运行时环境清单。引入 `requires.modules`（运行时模块依赖）、`requires.binaries`（系统二进制依赖）、`requires.service_db`（服务端持久化表面依赖）、`tables`（包自建持久化表面）。
### 1.3.0
- **GET 应急通道**：新增 `GET /text-cli/cli?prompt=` 作为应急入口，默认关闭，能力提供方显式开启。
- **异步任务调度**：新增 `task_id` 异步模型（pending/running/done/error/cancelled 五态），`GET /text-cli/tasks/{task_id}` 轮询端点。重启残留处理规则（running→error, service_restarted）。可选 webhook 回调通知。
- **协议桥**：引入协议桥原则——桥接指令与 native 指令平权，可被解析、作为聚合降级链提供方、被路径编排引用。
### 1.3.1
- **多语言**：协议指令格式本身语言无关（规范名 ASCII，别名不限字符集）。定义三层多语言原则：L1 查询响应按调用方语言抽取；L2 指令包注册多语言 schema（`locales` + `<field>_zh` 覆盖约定）；L3 指令执行对调用时语言负责（包内抽象，语言越界优雅降级）。
- **联邦凭证**：多节点联邦拓扑的三条原则：凭证按 peer 隔离（不全量携带）；映射链语义（domain;action→peer→凭证→注入，每步显式声明）；优雅降级（凭证缺失时降级转发，不静默阻断）。Service Token 三段分段原则（实例标识/策略控制面/用户身份）与固定长度前缀不变性原则。
- **健康检查增强**：`/text-cli/health` 公开层响应增加 `spec_version` 字段，声明该运行时遵循的协议规范版本号，与运行时自身 `version` 正交。
### 1.3.2
- **指令新增字段**：`estimated_time`（异步指令最大预期执行时间）、`estimated_time_note`（预估时间的解释说明）。


---


