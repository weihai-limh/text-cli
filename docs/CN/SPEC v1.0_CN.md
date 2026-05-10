

# text-cli Protocol Specification v1.0 **（草案）**

> 这是一份正式协议规范，描述 `text-cli` 的指令格式、API 交互、安全模型及 Schema 元数据。  
> 本文件适用于平台方、指令开发者、Agent 构建者，以及任何希望加入 `text-cli` 生态的协作者（人或 AI）。

---

## 1. 指令格式规范

### 1.1 基本结构

一条文本指令必须遵循以下格式（`指令:` 和 `AI:` 前缀同等效力）：

```
指令:<领域>;<动作>,<参数1>,<参数2>,...
AI:<领域>;<动作>,<参数1>,<参数2>,...
```

- **双前缀协议**（v1.1+）：`指令:` 是中文原生前缀，`AI:` 是英文国际化前缀。两者在协议层完全等效，由解析器统一处理。
- **Unicode 冒号兼容**：全角冒号 `：` 与半角 `:` 等效，解析器自动归一化。

- **领域**（Domain）：命名空间，长度 1–32 字符，只能包含 `A-Z a-z 0-9 _ -`。
- **动作**（Action）：动词，长度 1–32 字符，字符规则同领域。
- **参数列表**：以逗号分隔的参数值，顺序固定。参数 total 个数建议不超过 10 个，总指令长度建议不超过 512 字符。

**示例**

```
指令:基础应用;天气查询,明天,威海
AI:基础应用;天气查询,明天,威海
指令:家庭园艺;盆栽急救,绿萝,叶片发黄
AI:ai;infer,什么是量子计算,gpt-4
```

### 1.2 领域与动作的命名约定

- 领域和动作大小写不敏感，但推荐英文小写作为规范名（Canonical），中文作为别名（Alias）。
- 领域名建议由平台级前缀与应用名组成，如 `基础应用`、`地理空间`、`我的传感器`。
- 动作名应为动词短语，体现一个完整的操作。
- **双向别名**（v1.1+）：指令服务支持 `@directive(domain, action, domain_alias="中文域", action_aliases={"action": "动作"})` 形式的别名注册。调度时英文规范名和中文别名等效，大小写不敏感。
  - `AI:key;register` ⇔ `AI:密钥;注册`
  - `指令:file;read` ⇔ `指令:文件;读取`
  - 四种前缀×别名组合均可互通（过渡期保证）。

### 1.3 参数规则

- 参数默认是纯文本字符串，不进行 URL 编码或转义。
- **除末位参数外，参数不得含半角逗号（,）、分号（;）或换行符**。末位参数为自由文本，可达意传入逗号等内容（如 `文件;写入,/path/file.md,这是第一行，这是第二行`）。如有需求，由服务提供方在内部自行处理，不得要求调用方转义。
- 参数前后空白将被服务端 trim。

### 1.4 指令别名（v1.1 已实现）

**前缀别名**：`指令:` 和 `AI:` 两种前缀等效。

**领域/动作别名**：指令服务注册时通过 `domain_alias` 和 `action_aliases` 声明中文别名。调度时双向解析：

```
# 以下四条指令完全等效，指向同一个 handler：
AI:key;register,svc,val,type     # 英文规范名
AI:密钥;注册,svc,val,type        # 中文别名
指令:key;register,svc,val,type    # 旧前缀 + 英文
指令:密钥;注册,svc,val,type       # 旧前缀 + 中文
```

**解析器正则**（统一实现）：`^(?:指令|AI)[：:]([^;]+);([^,]+)(?:,(.+))?$`

缩写指令（如 `w:明天,威海`）保留为未来扩展。

---

## 2. HTTP API 规范

### 2.1 集成端点

`text-cli` 的集成端点是一个对外的 HTTP 服务，负责接收指令、鉴权、转发给后端技能服务。

#### 2.1.1 调用地址

```
POST https://<endpoint>/cli/text_cli
```

公共体验端点为 `test.text-cli.com`，自建端点路径需与此保持一致。本地部署的指令服务（如 agent-copilot）同样遵循此端点路径约定，在 `http://127.0.0.1:<port>/cli/text_cli` 上接收指令。

#### 2.1.2 请求结构

请求必须携带：

- **方法**：`POST`
- **Content-Type**：`application/json`
- **Authorization**：`Bearer <Access Token>`（由集成端点发放）
- **Service-token**（可选）：`<技能服务商约定的 Service Token>`

请求体 JSON：

```json
{
  "prompt": "指令:领域;动作,参数1,参数2,..."
}
```

#### 2.1.3 响应结构

成功时，HTTP 状态码为 `200`，响应体：

```json
{
  "rst_types": "text",
  "rst_data": {
    "text": "..."
  }
}
```

即使发生错误，也建议返回此结构，在 `text` 字段中提供人类可读的错误信息。对于异步任务，`text` 字段返回 `taskId:<唯一任务ID>`。

**异步指令示例**

```json
{
  "rst_types": "text",
  "rst_data": {
    "text": "taskId:nav-20260430-001"
  }
}
```

调用方需后续通过 `指令:基础应用;任务查询,taskId` 类的指令轮询或获取结果。

### 2.2 HTTP 状态码约定

| 状态码 | 含义 | 说明 |
|:---|:---|:---|
| 200 | 处理成功 | 结果在 `rst_data.text` 中 |
| 400 | 请求格式错误 | prompt 字段缺失或指令格式不正确 |
| 401 | Access Token 无效 | 需要获取有效的 Access Token |
| 403 | Service Token 无效 | 调用方无权访问该技能 |
| 408 | 指令处理超时 | 后端未在规定时间内完成 |
| 500 | 后端通用错误 | 集成端点或技能服务未知错误 |

---

## 3. 鉴权与计费模型

### 3.1 双层令牌体系

```
调用方 ──Access Token──> 集成端点 ──Service Token──> 技能服务
```

- **Access Token**：由集成端点签发，用于确认调用方是否有权使用端点，通常包含额度限制。
- **Service Token**：由技能提供方与调用方私下约定，用于服务端鉴权、计费、限流。集成端点**必须透明转发**，不解析不记录。

### 3.2 令牌传递

调用方在请求头中传递：

```
Authorization: Bearer <Access Token>
Service-token: <Service Token>
```

如果调用方未申请付费技能，`Service-token` 可省略。若集成端点收到的请求头中包含 `Service-token`，转发时**必须保留原始值**，不得修改。

---

## 4. Schema 元数据规范

### 4.1 概述

`text_cli_schema.json` 文件是公开指令的元数据入口。它是一组键值对，每个键对应一条指令的完整描述。

### 4.2 单条指令条目格式

```json
{
  "weather_query": {
    "id": "weather_query",
    "name": "天气查询",
    "category": "基础应用",
    "description": "根据时间和城市返回天气",
    "directive": "指令:基础应用;天气查询",
    "parameters": [
      {"name": "time", "type": "string", "enum": ["今天","明天","后天","三天"]},
      {"name": "city", "type": "string", "examples": ["威海","北京"]}
    ],
    "prompt_template": "指令:基础应用;天气查询,{time},{city}",
    "trigger_keywords": ["天气","气温","下雨"],
    "response_type": "text",
    "response_example": {
      "rst_types": "text",
      "rst_data": {
        "text": "明天天气(2026-04-28): 10℃到16℃,多云,日出05:02"
      }
    }
  }
}
```

### 4.3 字段说明

| 字段 | 必须 | 说明 |
|:---|:---|:---|
| `id` | 是 | 唯一标识，对应键名 |
| `name` | 是 | 人类可读的指令名称 |
| `category` | 是 | 领域分类，即指令中的“领域” |
| `directive` | 是 | 不含参数的指令前缀，如 `指令:基础应用;天气查询` |
| `prompt_template` | 是 | 完整指令字符串模板，用 `{参数名}` 表示参数位置 |
| `parameters` | 是 | 参数定义数组 |
| `trigger_keywords` | 是 | Agent 用于匹配用户问题的关键词列表 |
| `response_type` | 固定 `"text"` | 当前版本仅支持 text |
| `response_example` | 推荐 | 帮助开发者理解返回格式 |

---

## 5. 错误响应

### 5.1 设计原则

错误响应采用**结构化 + 紧凑**策略：

- **每一行就是一个错误**：错误信息以单行结构化字符串返回（如 `[bad_request] 请求体非有效 JSON`），不放入完整 HTTP 响应体或堆栈跟踪。
- **为什么**：在 AI Agent 调用场景中，一次 JSON 格式错误或权限拒绝，传统 HTTP 响应可能膨胀 500–2000 字符进入 Agent 上下文。text-cli 将错误压缩为单行，把故障的 Token 代价降至最低。
- **错误不膨胀上下文**——这是 text-cli 协议的一条设计原则，不仅仅是实现细节。

### 5.2 错误码

错误码采用可读的字符串键，在 HTTP 响应可能无法满足描述时，放入 `rst_data.text` 或未来的 `error_code` 扩展字段中。推荐值：

- `INVALID_DIRECTIVE_FORMAT`：指令格式不正确
- `INVALID_PARAMS`：参数类型或值不合法
- `DIRECTIVE_NOT_FOUND`：未找到匹配的指令
- `ACCESS_DENIED`：Access Token 无效
- `SERVICE_DENIED`：Service Token 无效或额度不足
- `BACKEND_TIMEOUT`：后端服务超时
- `BACKEND_ERROR`：后端未知错误

---

## 6. 扩展机制

- 可在 `rst_data` 对象中增加非 `text` 字段（如 `url`, `json`），但调用方需检查 `rst_types` 字段。
- 若引入新的 `rst_types`，如 `"image"`, `"task"`，需递增协议主版本。
- 官方保留 `rst_` 前缀，自定义字段请使用 `x_` 前缀。

---

## 7. 版本管理

- 当前协议主版本为 `1`，通过集成端点的响应头 `X-Protocol-Version: 1` 告知。
- 当必须破坏兼容性时，主版本递增。次版本增加向后兼容的扩展。

---

## 8. 多语言指令规范

### 8.1 核心理念

**同一指令，多种语言表达，同一种服务。**

text-cli 的指令格式本身是语言无关的——`关键字:领域;动作,参数` 只是结构化分隔符的组合。`指令` 可以用 `command` 代替，`基础应用` 可以用 `basic` 代替。多语言不是重建协议，而是定义不同语言间的**等价映射**。

### 8.2 协议关键字映射

以下映射为协议强制定义，所有兼容的集成端点和 Agent 必须支持：

| 中文 | English | 功能 |
|:---|:---|:---|
| `指令` | `command` / `directive` | 指令前缀（接受 `command` 和 `directive` 作为等效别名） |
| `基础应用` | `basic` | 基础应用领域 |
| `地理空间` | `geo` | 地理空间领域 |
| `ai集成` | `ai` | AI 集成领域 |
| `系统服务` | `system-service` | 系统服务领域 |
| `服务查询` | `service-query` | 服务发现领域 |
| `家庭园艺` | `home-gardening` | 家庭园艺领域（示例自定义领域） |

> **领域关键词不受限制。** 上表仅列出当前生态中已注册的领域。新增领域由服务提供方在注册时声明中文名和英文 alias，端点自动纳入映射表。

### 8.3 动作名称映射

动作名称的跨语言映射**不强制统一**，由各服务在注册时自行声明。规则：

- 服务方在 `handler.json` 或 schema 条目中提供 `action_aliases` 字段
- 端点将所有已注册的 alias 视为等效——任一语言触发的指令路由到同一服务
- 参数位置和语义跨语言完全一致

### 8.4 多语言指令在 Schema 中的表达

服务注册时，在 schema 条目中增加两个可选字段：

```json
{
  "weather_query": {
    "id": "weather_query",
    "name": "天气查询",
    "category": "基础应用",
    "directive": "指令:基础应用;天气查询",
    "directive_aliases": ["command:basic;weather_query"],
    "action_aliases": {
      "en": "weather_query",
      "ja": "天気検索"
    },
    "parameters": [...],
    "prompt_template": "指令:基础应用;天气查询,{time},{city}",
    "trigger_keywords": ["天气", "气温", "weather", "temperature"],
    ...
  }
}
```

**新增字段说明：**

| 字段 | 必须 | 说明 |
|:---|:---|:---|
| `directive_aliases` | 否 | 其他语言版本的完整指令前缀。格式与 `directive` 相同，使用对应语言的关键字。端点收到匹配的指令时路由到同一服务 |
| `action_aliases` | 否 | 按语言代码组织的动作名映射表。端点可据此将非注册语言的指令翻译后路由 |
| `trigger_keywords` | 扩展 | 原字段可混入多语言关键词。Agent 在多语言环境下匹配时不应要求关键词语言与指令语言一致 |

### 8.5 端点翻译层的责任边界

多语言指令的解析和翻译**在端点层完成**，不在服务层：

```
Agent → 发送任何语言版本的指令 → 集成端点
         ↓
    端点解析指令关键字：
      · "指令"/"command"/"directive" → 识别为 text-cli 指令
      · 领域名 → 查映射表或 alias 注册 → 归一化为注册语言
      · 动作名 → 查 action_aliases → 归一化为注册语言
         ↓
    端点用归一化后的 directive 匹配服务 → 路由
         ↓
    服务方收到的始终是注册时使用的语言（不变）
```

**关键约束：**

- **服务提供方只用一种语言注册。** 不需要在服务端处理多语言逻辑。
- **翻译在端点层做，不在服务层。** 降低服务开发者的国际化负担。
- **参数不翻译。** 参数的语义由位置决定，与语言无关。`明天` 和 `tomorrow` 都是合法的参数值，但它们是服务商的业务逻辑问题，不是协议问题。
- **语言不匹配时不报错。** 端点收到无法匹配的指令时，返回 `DIRECTIVE_NOT_FOUND` 而非 `LANGUAGE_NOT_SUPPORTED`。调用方应尝试换一种语言或使用服务发现指令查询可用服务。

### 8.6 handler.json 格式：作为服务发现与多语言注册的统一入口

基于 open-tunnel-proxy 的实践经验，`handler.json` 同时承担服务发现和参数规范的双重角色。以下为多语言 handler 的标准格式：

```json
{
  "id": "tunnel-proxy-deploy",
  "name": "隧道代理部署",
  "category": "系统服务",
  "category_aliases": ["system-service"],
  "description": "一键部署 Cloudflare Tunnel 推送代理",
  "author": "Tide",
  "version": "1.0.0",
  "directive": "指令:系统服务;隧道代理部署",
  "directive_aliases": [
    "command:system-service;tunnel-proxy-deploy",
    "指令:システム;トンネル展開"
  ],
  "parameters": [
    {"name": "api_key", "type": "string", "description": "Cloudflare API Key"},
    {"name": "email", "type": "string", "description": "Cloudflare 账号邮箱"},
    {"name": "account_id", "type": "string", "description": "Cloudflare Account ID"},
    {"name": "github_token", "type": "string", "description": "GitHub Personal Access Token"},
    {"name": "repo", "type": "string", "description": "仓库路径，如 user/repo"},
    {"name": "domain", "type": "string", "optional": true, "description": "自定义域名"}
  ],
  "prompt_template": "指令:系统服务;隧道代理部署,{api_key},{email},{account_id},{github_token},{repo},{domain}",
  "trigger_keywords": ["隧道代理", "tunnel proxy", "トンネル"],
  "response_type": "text",
  "download": "https://github.com/tide-10000/tide/tree/main/tide-scripts/open-tunnel-proxy"
}
```

> **设计意图**：handler.json 既是服务目录条目（通过 `服务查询` 指令被发现），也是部署指令的参数规范。Agent 通过第一步服务发现拿到 handler.json，即可理解服务的完整参数需求，无需提前内置任何知识。

### 8.7 参考实现

open-tunnel-proxy（`tide-scripts/open-tunnel-proxy/`）是首个完整实现多语言指令的实际运行项目。其 `README.md` 和 `handler.json` 展示了：

- 三种语言（中文/English/日本語）触发同一 handler
- 参数位置和语义跨语言完全一致
- handler.json 作为服务发现 → 自动部署两步指令流的桥梁

建议所有新注册服务参照此模式提供多语言 handler。

### 8.8 语言平等原则

- 任一语言版本的指令享有同等功能——不能出现「中文版支持 3 个参数、英文版只支持 2 个」
- 服务返回文本的语言由服务提供方自行决定，端点不强制翻译
- 调用方可通过 `Accept-Language` 头表达语言偏好，服务方可选择响应或不响应
- 参数值本身的多语言（如 `明天` vs `tomorrow`）由服务方自行处理，不在协议范围内

---

## 9. 路径协议

### 9.1 概述

单条指令解决一件事，路径解决一类事。路径是多条指令的有序组合，Agent 通过匹配路径描述自动编排执行。路径与指令的关系：指令是原子，路径是分子。

一条路径在 `path-schema.json` 中注册，Agent 匹配后按指令链顺序执行。

### 9.2 路径类型学

text-cli 定义了四种路径模式（非互斥，不要求全覆盖）：

| 模式 | 核心步骤 | 数据流 | 适用场景 |
|:---|:---|:---|:---|
| **工具链** (Toolchain) | `action` + `condition` | 线性串联，上步产出 → 下步输入 | 覆盖 80% 场景 |
| **编排** (Orchestration) | `parallel` | 一分多 → 并行执行 → 合并 | 批量查询、多源聚合 |
| **交互式** (Interactive) | `checkpoint` + `human` | 感知 → 决策 → 执行 → 验证循环 | 需要人工审批的操作 |
| **注入式** (Injection) | `subpath` | 修改执行环境，不产出最终结果 | 配置注入、环境初始化 |

### 9.3 path-schema.json 条目格式

每条路径在 `path-schema.json` 中为一个独立的 JSON 对象，键为路径标识：

```json
{
  "查找消息并发送邮件": {
    "description": "从 AI 协作者状态中查找最近的对话消息，写入文件后通过邮件发送给指定收件人",
    "params": ["消息条数", "收件人邮箱", "邮件主题"],
    "instruction_chain": [
      "指令:AI协作;消息",
      "指令:文件;写入",
      "指令:邮件;发送"
    ],
    "require_instructions": ["AI协作;消息", "文件;写入", "邮件;发送"],
    "rank": 1,
    "tags": ["工具链", "消息", "邮件"]
  }
}
```

| 字段 | 必须 | 说明 |
|:---|:---|:---|
| `description` | 是 | 意图说明，Agent 用于语义匹配 |
| `params` | 是 | 路径级参数列表，Agent 执行前从用户/环境收集 |
| `instruction_chain` | 是 | 指令 ID 有序列表，Agent 按序执行 |
| `require_instructions` | 是 | 前置指令门控——链中每条指令的 `领域;动作` 必须已在指令 Schema 中注册 |
| `rank` | 否 | 路由优先级，默认 1 |
| `tags` | 否 | 辅助分类标签 |
| `path_doc` | 否 | 复杂路径的详细文档引用 |

### 9.4 路径执行门控

**路径生效前必须通过两道门控：**

1. **指令注册门控**：`require_instructions` 中的每条 `领域;动作` 必须在 `agent-text-cli-schema.json` 中存在。任一指令未注册 → 路径不生效。
2. **路径匹配门控**：Agent 将用户意图与路径 `description` 进行语义匹配。匹配不成功 → 回退到指令调度或 Agent 推理。

门控确保了路径的可靠性——不会因引用了不存在的指令而在执行中失败。

### 9.5 路径与指令的关系

- 路径引用的每条指令独立遵循 §2 的 HTTP API 规范，通过 `/cli/text_cli` 端点调用。
- 路径不在指令层引入新协议——路径是 Agent 侧的编排逻辑，指令服务无需感知路径。
- 路径的 Token 节约发生在推理环节（Agent 不需要思考"需要什么步骤"），而非执行环节。

---

## 10. 语义注册表

### 10.1 定位

语义注册表是 text-cli 生态的**受控词表**——收录生态内已注册的领域和动作，附带多语言别名和嵌入指纹。它不是运行时调度层（意图匹配走 `trigger_keywords`），而是**命名规范层**，用于：

1. **新指令命名校验**：私有指令接入时，提供方提交的 `领域;动作` 应与注册表比对。新提出的名称如果和已有条目嵌入过于接近，建议复用已有名称而非新建，防止生态内语义冗余。
2. **多语言对齐**：同一条目的所有语言 alias 始终指向同一个 `semantic_id`。与 §8 协同——§8 定义协议关键字的翻译规则，§10 把这件事扩展到所有领域和动作。
3. **跨模型可移植**：一个条目在多个嵌入模型的注册表文件中共享同一个 `semantic_id`，独立于嵌入模型。

### 10.2 文件命名约定

```
schema/semantic-registry_{model-slug}.json
```

- `{model-slug}` 为嵌入模型的简称，全小写，下划线分隔。如 `bge-m3`、`gte-qwen2`、`text-embedding-3`。
- 多个嵌入模型的注册表文件并行存在。调用方按部署环境选择对应文件进行命名校验。
- 所有文件共享相同的 `semantic_id` 命名空间——同一领域/动作在不同模型文件中使用相同的 `semantic_id`。

### 10.3 条目格式

语义注册表包含两个独立数组——`domains` 和 `actions`。领域和动作分表存储，允许自由组合（同一动作可用于不同领域）。

#### 领域条目

```json
{
  "semantic_id": "domain.basic_application",
  "aliases": {
    "zh": "基础应用",
    "en": "basic",
    "ja": "基本アプリ"
  },
  "description": "General-purpose daily queries and tools;面向日常生活的通用查询与工具指令",
  "embedding": [0.0123, -0.0456]
}
```

#### 动作条目

```json
{
  "semantic_id": "action.weather_query",
  "aliases": {
    "zh": "天气查询",
    "en": "weather",
    "ja": "天気検索"
  },
  "description": "Query weather by time and city;根据时间和城市查询天气信息",
  "embedding": [0.0678, -0.0901]
}
```

#### 字段说明

| 字段 | 必须 | 说明 |
|:---|:---|:---|
| `semantic_id` | 是 | 全局唯一标识符。`domain.*` 或 `action.*` 前缀区分类型，不可变 |
| `aliases` | 是 | 多语言别名映射。键为 ISO 639-1 语言代码，值在该语言中唯一 |
| `description` | 是 | 语义说明，格式为 `English description;中文说明`，两段用半角分号分隔 |
| `embedding` | 是 | 当前模型的嵌入向量。维度由 `_meta.dimensions` 声明 |

> **`semantic_id` 不可变**：录入后即固定。如需废弃，通过 `_meta.deprecated_ids` 标记，不直接删除（防止引用断裂）。

### 10.4 `aliases` 与 §4 Schema 的关系

语义注册表的 `aliases` 和指令 Schema 的 `action_aliases`（§8.4）是两个独立层次：

- **语义注册表 aliases**：规范层——定义"这个动作在中文叫什么"。是生态共识。
- **指令 Schema action_aliases**：实现层——定义"具体这条指令还接受什么语言触发"。可以超出语义注册表的范围（例如接受方言或缩写）。

两者互补不冲突：语义注册表设下限（至少具备这些别名），指令 Schema 可在此之上扩展。

### 10.5 命名校验流程（参考）

当新指令申请注册 `领域;动作` 时：

1. 将新名称按语言嵌入当前注册的嵌入模型
2. 在语义注册表中计算新名称与所有同类型条目（领域 vs 领域，动作 vs 动作）的余弦相似度
3. 相似度超过阈值 → 返回已有的 `semantic_id`，建议复用
4. 相似度低于阈值 → 新建 `semantic_id`，录入注册表

> 阈值和具体校验工具链由实现层定义，不在协议规范范围内。

### 10.6 参考文件

- 首个注册表文件：`schema/semantic-registry_bge-m3.json`（BAAI/bge-m3，1024 维）
- 注册表条目从生态内已运行的指令中提取——即 `text_cli_schema.json` 和 agent-copilot 14 条指令中所有已出现的领域和动作

---

## 11. 本地指令端点

### 11.1 概述

text-cli 协议定义了两种端点形态：

| | 集成端点（转发型） | 本地端点（执行型） |
|:---|:---|:---|
| **代表** | `api.text-cli.com` | `agent-copilot` |
| **职责** | 接收指令 → 鉴权 → 转发到技能服务 | 接收指令 → 鉴权 → 本地执行 → 返回结果 |
| **双层令牌** | Access Token + Service Token | 单层 Token（local auth） |
| **计费** | 支持，按 Service Token 计数 | 无（自用端点） |
| **安全模型** | 令牌鉴权 + 转发隔离 | 路径白名单 + 分支白名单 + 凭据居中 |
| **端点路径** | `/cli/text_cli` | `/cli/text_cli`（统一） |

两种端点使用相同的端点路径、请求格式和响应格式——Agent 从集成端点切换到本地端点不需要修改调用逻辑，只改变目标地址。

### 11.2 本地端点的安全模型

本地端点不依赖 Service Token 计费，安全模型围绕以下机制构建：

**路径白名单**：文件读写操作限定在配置的目录范围内。任何越界访问在指令解析阶段即被拒绝，返回 `[path_denied]`。

**分支白名单**：Git 推送操作限定在允许的分支列表内。向未授权分支推送时返回 `[branch_denied]`。

**凭据居中**：SMTP 密码、Git 凭证等敏感信息仅存储在 copilot 配置文件中，不进入 Agent 上下文。Agent 发送的指令中不包含任何凭据。

**单层鉴权**：本地端点通过本地 Token 鉴权（Bearer Token），仅绑定本地回路。不对外开放，不走网络转发。

### 11.3 本地端点与指令 Schema 的关系

- 本地端点提供的指令应在 `agent-text-cli-schema.json` 中注册，与远程端点指令统一管理。
- 路径链可以混合本地指令和远程指令——`instruction_chain` 不区分指令来源。
- 未来版本建议在指令 Schema 中增加 `source` 字段标记指令来源（本地/远程），便于 Agent 路由决策。

### 11.4 参考实现

`server/agent-copilot/` 是本地端点的首个参考实现：14 条指令，Python stdlib 零依赖，安全模型完整（路径白名单、分支白名单、凭据居中）。可作为本地端点开发的模板和测试基准。

---
