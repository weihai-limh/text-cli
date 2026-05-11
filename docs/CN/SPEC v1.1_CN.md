

# text-cli Protocol Specification v1.1 **(草案)**

> 这是一份正式协议规范,描述 `text-cli` 的指令格式、API 交互、安全模型及 Schema 元数据。
> 本文件适用于平台方、指令开发者、Agent 构建者,以及任何希望加入 `text-cli` 生态的协作者(人或 AI)。
>
> **修订记录**:2026-05-11 - §1 领域字符约束修正、§2.1.4 GET 应急通道、§4 Schema 补全(directive_zh/routing/trigger_keywords 结构化)、§6 响应类型扩展(picture/video/audio/file)、§8 固定映射表 → 注册声明、§11.4 routing Schema 补全(adapter/param_names/timeout_ms)

---

## 1. 指令格式规范

### 1.1 基本结构

一条文本指令必须遵循以下格式(`指令:` 和 `AI:` 前缀同等效力):

```
指令:<领域>;<动作>,<参数1>,<参数2>,...
AI:<领域>;<动作>,<参数1>,<参数2>,...
```

- **双前缀协议**(v1.1+):`指令:` 是中文原生前缀,`AI:` 是英文国际化前缀。两者在协议层完全等效,由解析器统一处理。
- **Unicode 冒号兼容**:全角冒号 `:` 与半角 `:` 等效,解析器自动归一化。

- **领域**(Domain):命名空间,长度 1-32 字符。**规范名(canonical)** 必须使用 ASCII(`A-Z a-z 0-9 _ -`)。**别名(alias)** 不限字符集--中文、日文等均可,通过注册时声明的映射归一化到规范名。
- **动作**(Action):动词,长度 1-32 字符。字符规则同领域--规范名 ASCII,别名不限。
- **参数列表**:以逗号分隔的参数值,顺序固定。参数 total 个数建议不超过 10 个,总指令长度建议不超过 512 字符。

**示例**

```
AI:basic;weather,tomorrow,Weihai              ← canonical(英文规范名)
AI:基础应用;天气查询,明天,威海                  ← alias(中文别名,等效)
指令:tencentmap;geocode,威海                   ← canonical
AI:腾讯地图;地址解析,北京                       ← alias
指令:home-gardening;rescue,绿萝,叶片发黄        ← 自定义领域 canonical
```

> 四条指令中,canonical 和 alias 在协议层完全等效。解析器通过注册表将所有 alias 归一化为 canonical 后执行路由。调用方可任选一种形式,无需关心映射细节。

### 1.2 领域与动作的命名约定

- 领域和动作大小写不敏感。规范名(canonical)推荐英文小写,别名(alias)不限语言。
- 领域名由服务提供方在注册时声明规范名和别名。例如 `tencentmap`(规范名,alias: `腾讯地图`)、`antvchart`(规范名,alias: `蚂蚁图表`)。
- 动作名应为动词短语,体现一个完整的操作。同样在注册时声明规范名和别名。
- **双向别名**(v1.1+):指令服务支持 `@directive(domain, action, domain_alias="中文域", action_aliases={"action": "动作"})` 形式的别名注册。调度时英文规范名和中文别名等效,大小写不敏感。
  - `AI:key;register` ⇔ `AI:密钥;注册`
  - `指令:file;read` ⇔ `指令:文件;读取`
  - 四种前缀×别名组合均可互通(过渡期保证)。

### 1.3 参数规则

- 参数默认是纯文本字符串,不进行 URL 编码或转义。
- **除末位参数外,参数不得含半角逗号(,)、分号(;)或换行符**。末位参数为自由文本,可达意传入逗号等内容(如 `文件;写入,/path/file.md,这是第一行,这是第二行`)。如有需求,由服务提供方在内部自行处理,不得要求调用方转义。
- 参数前后空白将被服务端 trim。

### 1.4 指令别名(v1.1 已实现)

**前缀别名**:`指令:` 和 `AI:` 两种前缀等效。

**领域/动作别名**:指令服务注册时通过 `domain_alias` 和 `action_aliases` 声明中文别名。调度时双向解析:

```
# 以下四条指令完全等效,指向同一个 handler:
AI:key;register,svc,val,type     # 英文规范名
AI:密钥;注册,svc,val,type        # 中文别名
指令:key;register,svc,val,type    # 旧前缀 + 英文
指令:密钥;注册,svc,val,type       # 旧前缀 + 中文
```

**解析器正则**(统一实现):`^(?:指令|AI)[::]([^;]+);([^,]+)(?:,(.+))?$`

缩写指令(如 `w:明天,威海`)保留为未来扩展。

---

## 2. HTTP API 规范

### 2.1 集成端点

`text-cli` 的集成端点是一个对外的 HTTP 服务,负责接收指令、鉴权、转发给后端技能服务。

#### 2.1.1 调用地址

```
POST https://<endpoint>/cli/text_cli
```

公共体验端点为 `test.text-cli.com`,自建端点路径需与此保持一致。本地部署的指令服务(如 agent-copilot)同样遵循此端点路径约定,在 `http://127.0.0.1:<port>/cli/text_cli` 上接收指令。

#### 2.1.2 请求结构

请求必须携带:

- **方法**:`POST`
- **Content-Type**:`application/json`
- **Authorization**:`Bearer <Access Token>`(由集成端点发放)
- **Service-token**(可选):`<技能服务商约定的 Service Token>`

请求体 JSON:

```json
{
  "prompt": "指令:领域;动作,参数1,参数2,..."
}
```

#### 2.1.3 响应结构

成功时,HTTP 状态码为 `200`,响应体:

```json
{
  "rst_types": "text",
  "rst_data": {
    "text": "..."
  }
}
```

即使发生错误,也建议返回此结构,在 `text` 字段中提供人类可读的错误信息。对于异步任务,`text` 字段返回 `taskId:<唯一任务ID>`。

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

#### 2.1.4 GET 应急通道

在双 Token 链路故障(Access Token 过期无法续签、Service Token 失效)导致 POST 通道不可用时,端点可提供 GET 应急通道:

```
GET /cli/text_cli?prompt=<URL编码的指令>
```

**设计意图**:这是一个绕过双层令牌体系的临时旁路,用于灾难恢复--让服务在 Token 修复前继续运行。

**规则**:

- **默认关闭**。由端点运营方通过配置显式开启。
- **无需认证**。不校验 Access Token 或 Service Token。请求方与响应方风险自担。
- **响应格式与 POST 完全一致**--相同的 200/400/500 状态码约定(§2.2)和 `rst_data` 结构。
- **prompt 通过 query string 传递**,需 URL 编码。认证 Token 不应出现在 query string 中。
- **凭据警告**:GET URL 会被中间代理、CDN 日志、浏览器历史记录。不应通过 GET 通道传递含密钥参数的指令。敏感操作走 POST。
- **运营建议**:开启 GET 通道时建议配合网络层限流(IP 白名单或速率限制),降低开放调用风险。

> GET 和 POST 在端点实现中是两个独立开关。部署端可选择仅开 POST、仅开 GET、或两者同开。

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

- **Access Token**:由集成端点签发,用于确认调用方是否有权使用端点,通常包含额度限制。
- **Service Token**:由技能提供方与调用方私下约定,用于服务端鉴权、计费、限流。集成端点**必须透明转发**,不解析不记录。

### 3.2 令牌传递

调用方在请求头中传递:

```
Authorization: Bearer <Access Token>
Service-token: <Service Token>
```

如果调用方未申请付费技能,`Service-token` 可省略。若集成端点收到的请求头中包含 `Service-token`,转发时**必须保留原始值**,不得修改。

---

## 4. Schema 元数据规范

### 4.1 概述

`text_cli_schema.json` 文件是公开指令的元数据入口。它是一组键值对,每个键对应一条指令的完整描述。

### 4.2 单条指令条目格式

```json
{
  "tencentmap_geocoder": {
    "id": "tencentmap_geocoder",
    "name": "地址解析(Geocode)",
    "category": "腾讯地图",
    "description": "Convert address to lat/lng;将包含省市区的地址转换为经纬度",
    "directive": "AI:tencentmap;geocode",
    "directive_zh": "AI:腾讯地图;地址解析",
    "parameters": [
      {"name": "address", "type": "string", "description": "地址"}
    ],
    "prompt_template": "AI:tencentmap;geocode,{address}",
    "trigger_keywords": {
      "zh": ["地址解析", "经纬度", "坐标", "地理编码"],
      "en": ["geocode", "latlng", "coordinates"]
    },
    "response_type": "text",
    "routing": {
      "type": "mcp",
      "backends": [
        {"type": "mcp", "server": "tencent-maps", "tool": "geocoder", "adapter": "passthrough", "param_names": ["address"], "timeout_ms": 30000}
      ]
    },
    "response_example": {
      "rst_types": "text",
      "rst_data": {
        "text": "纬度: 37.5°N, 经度: 122.1°E, 地址: 山东省威海市"
      }
    }
  }
}
```

### 4.3 字段说明

| 字段 | 必须 | 说明 |
|:---|:---|:---|
| `id` | 是 | 唯一标识,对应键名 |
| `name` | 是 | 人类可读的指令名称 |
| `category` | 是 | 领域分类,即指令中的"领域" |
| `directive` | 是 | 规范名指令前缀,使用英文 canonical 域名和动作名 |
| `directive_zh` | 否 | 中文别名指令前缀。解析到匹配的中文指令时归一化到 `directive` |
| `prompt_template` | 是 | 完整指令字符串模板,用 `{参数名}` 表示参数位置 |
| `parameters` | 是 | 参数定义数组 |
| `trigger_keywords` | 是 | 按语言分组的触发关键词对象(`{"zh": [...], "en": [...]}`),Agent 用于意图匹配 |
| `response_type` | 是 | 支持的响应类型。单类型如 `"text"`,多类型如 `["text", "picture", "video"]`(见 §6) |
| `response_example` | 推荐 | 帮助开发者理解返回格式 |
| `routing` | 否 | 多后端路由声明(见 §11.4)。无此字段时默认为 `{"type": "local"}` |
---

## 5. 错误响应

### 5.1 设计原则

错误响应采用**结构化 + 紧凑**策略:

- **每一行就是一个错误**:错误信息以单行结构化字符串返回(如 `[bad_request] 请求体非有效 JSON`),不放入完整 HTTP 响应体或堆栈跟踪。
- **为什么**:在 AI Agent 调用场景中,一次 JSON 格式错误或权限拒绝,传统 HTTP 响应可能膨胀 500-2000 字符进入 Agent 上下文。text-cli 将错误压缩为单行,把故障的 Token 代价降至最低。
- **错误不膨胀上下文**--这是 text-cli 协议的一条设计原则,不仅仅是实现细节。

### 5.2 错误码

错误码采用可读的字符串键,在 HTTP 响应可能无法满足描述时,放入 `rst_data.text` 或未来的 `error_code` 扩展字段中。推荐值:

- `INVALID_DIRECTIVE_FORMAT`:指令格式不正确
- `INVALID_PARAMS`:参数类型或值不合法
- `DIRECTIVE_NOT_FOUND`:未找到匹配的指令
- `ACCESS_DENIED`:Access Token 无效
- `SERVICE_DENIED`:Service Token 无效或额度不足
- `BACKEND_TIMEOUT`:后端服务超时
- `BACKEND_ERROR`:后端未知错误

---

## 6. 扩展机制

### 6.1 响应类型扩展

`rst_types` 字段声明响应的媒体类型。当前支持的取值:

| `rst_types` | 含义 | `rst_data` 承载方式 |
|:---|:---|:---|
| `text` | 纯文本(默认) | `rst_data.text` = 文本内容 |
| `picture` | 图片 | `rst_data.url` = 图片地址,`rst_data.text` = 描述 |
| `video` | 视频 | `rst_data.url` = 视频地址,`rst_data.text` = 描述 |
| `audio` | 音频 | `rst_data.url` = 音频地址,`rst_data.text` = 描述 |
| `file` | 文件 | `rst_data.url` = 文件地址,`rst_data.text` = 描述 |

- **`text` 始终可用**--即使 `rst_types` 为其他值,`rst_data.text` 仍提供人类可读的描述文本,作为渲染失败时的回退。
- **新增 `rst_types` 向后兼容**--调用方若不认识新的类型值,可安全回退到 `rst_data.text`。不强制递增协议主版本。
- **`ok()` 函数签名**:`ok(text, type='text', url=None, **extra)`。`type` 不出现时 = `text`,旧调用零改动。

### 6.2 其他扩展

- 可在 `rst_data` 对象中增加非标准字段,但调用方需检查 `rst_types` 字段。
- 官方保留 `rst_` 前缀,自定义字段请使用 `x_` 前缀。

---

## 7. 版本管理

- 当前协议主版本为 `1`,次版本 `1`(v1.1)。通过集成端点的响应头 `X-Protocol-Version: 1.1` 告知。
- v1.1 新增:§2.1.4 GET 应急通道、§6.1 响应类型扩展(picture/video/audio/file)、§8.2 别名注册机制重构(固定映射表 → 注册声明)、§10.3 routing 字段、§11.4 多后端路由。向后兼容--所有 v1.0 指令和端点无需任何修改即可在 v1.1 环境下运行。
- 当必须破坏兼容性时,主版本递增。次版本增加向后兼容的扩展。

---

## 8. 多语言指令规范

### 8.1 核心理念

**同一指令,多种语言表达,同一种服务。**

text-cli 的指令格式本身是语言无关的--`关键字:领域;动作,参数` 只是结构化分隔符的组合。`指令` 和 `AI` 是等效前缀,`腾讯地图` 和 `tencentmap` 指向同一个领域。多语言不是重建协议,而是通过注册时声明的**别名映射**实现等价。

### 8.2 别名注册机制

指令的前缀、领域、动作均支持通过注册表声明多语言别名。映射关系在注册时确定,端点运行时自动归一化。

**前缀别名**(协议级,固定):

| 前缀 | 等效前缀 | 说明 |
|:---|:---|:---|
| `指令` | `AI` | 两者在协议层完全等效,解析器统一处理 |

**领域/动作别名**(注册级,服务方声明):

领域和动作不限字符集--服务方在注册时声明规范名(canonical,推荐英文小写 ASCII)和别名(alias,任意语言)。端点通过注册表(§10 语义注册表)将所有别名归一化为规范名后路由。

**已注册示例**(非穷举):

| 规范名(canonical) | 中文别名 | 日文别名 |
|:---|:---|:---|
| `tencentmap` | `腾讯地图` | - |
| `antvchart` | `蚂蚁图表` | - |
| `basic` | `基础应用` | `基本アプリ` |
| `geocode` | `地址解析` | - |
| `weather` | `天气查询` | `天気検索` |

> **别名由服务方声明,不由协议枚举。** 上表仅为当前生态中已注册的代表性条目。新增服务在注册时声明自己的规范名和别名后,端点自动纳入映射。协议本身不维护固定的关键字翻译表。

### 8.3 映射规则

- 服务方在 schema 条目中提供 `directive_zh`(中文别名指令)和语义注册表的 `aliases` 字段
- 端点将所有已注册的 alias 视为等效--任一语言触发的指令路由到同一服务
- 参数位置和语义跨语言完全一致
- 中文 alias 仅需声明,大小写不敏感,无需逐条注册四种前缀组合--解析器自动处理

### 8.4 多语言指令在 Schema 中的表达

服务注册时,在 schema 条目中声明规范名和别名:

```json
{
  "tencentmap_geocoder": {
    "id": "tencentmap_geocoder",
    "name": "地址解析(Geocode)",
    "category": "腾讯地图",
    "description": "Convert address to lat/lng;将包含省市区的地址转换为经纬度",
    "directive": "AI:tencentmap;geocode",
    "directive_zh": "AI:腾讯地图;地址解析",
    "parameters": [
      {"name": "address", "type": "string", "description": "地址"}
    ],
    "prompt_template": "AI:tencentmap;geocode,{address}",
    "trigger_keywords": {
      "zh": ["地址解析", "经纬度", "坐标", "地理编码"],
      "en": ["geocode", "latlng", "coordinates"]
    },
    "response_type": "text",
    "routing": {
      "type": "mcp",
      "backends": [
        {"type": "mcp", "server": "tencent-maps", "tool": "geocoder", "adapter": "passthrough", "param_names": ["address"]}
      ]
    }
  }
}
```

**关键字段说明:**

| 字段 | 必须 | 说明 |
|:---|:---|:---|
| `directive` | 是 | 规范名指令前缀,使用英文 canonical 域名和动作名 |
| `directive_zh` | 否 | 中文别名指令前缀。端点解析到匹配的中文指令时归一化到 `directive` |
| `trigger_keywords` | 是 | 按语言分组的触发关键词。Agent 按意图匹配时使用,不要求关键词语言与指令语言一致 |
| `routing` | 否 | 多后端路由声明。见 §11.4 | |

### 8.5 端点翻译层的责任边界

多语言指令的解析和翻译**在端点层完成**,不在服务层:

```
Agent → 发送任何语言版本的指令 → 集成端点
         ↓
    端点解析指令关键字:
      · "指令"/"AI" → 识别为 text-cli 指令(双前缀协议)
      · 领域名 → 查注册表 aliases → 归一化为 canonical
      · 动作名 → 查注册表 aliases → 归一化为 canonical
         ↓
    端点用归一化后的 canonical 匹配服务 → 路由
         ↓
    服务方收到的始终是注册时使用的语言(不变)
```

**关键约束:**

- **服务提供方只用一种语言注册。** 不需要在服务端处理多语言逻辑。
- **翻译在端点层做,不在服务层。** 降低服务开发者的国际化负担。
- **参数不翻译。** 参数的语义由位置决定,与语言无关。`明天` 和 `tomorrow` 都是合法的参数值,但它们是服务商的业务逻辑问题,不是协议问题。
- **语言不匹配时不报错。** 端点收到无法匹配的指令时,返回 `DIRECTIVE_NOT_FOUND` 而非 `LANGUAGE_NOT_SUPPORTED`。调用方应尝试换一种语言或使用服务发现指令查询可用服务。

### 8.6 handler.json 格式

`handler.json` 在 Schema 条目(§8.4)的基础上增加三个服务发现字段:

| 字段 | 必须 | 说明 |
|:---|:---|:---|
| `author` | 否 | 服务作者或维护方 |
| `version` | 否 | 语义化版本号(如 `"1.0.0"`) |
| `category_aliases` | 否 | 领域分类的多语言别名(如 `["tencentmap"]`) |

其余字段(`id`、`directive`、`directive_zh`、`parameters`、`routing` 等)与 §8.4 完全一致。

> **设计意图**:handler.json 既是服务目录条目(通过 `服务查询` 指令被发现),也是指令的参数规范。Agent 通过服务发现拿到 handler.json,即可理解服务的完整参数需求和路由方式,无需提前内置任何知识。`directive` 使用英文规范名,`directive_zh` 提供中文别名--解析器自动归一化,调用方可任选语言。

### 8.7 参考实现

`server/mcp-bridge/`(MCP 双向桥)和 `examples/text-cli-copilot/base/`(copilot base handlers)展示了多语言指令的完整实现:

- 指令同时支持 canonical(如 `AI:tencentmap;geocode`)和中文 alias(如 `AI:腾讯地图;地址解析`)
- 参数位置和语义跨语言完全一致
- handler.json / schema 条目作为服务发现 → 指令执行的桥梁

建议所有新注册服务为领域和动作声明中英文别名。

### 8.8 语言平等原则

- 任一语言版本的指令享有同等功能--不能出现「中文版支持 3 个参数、英文版只支持 2 个」
- 服务返回文本的语言由服务提供方自行决定,端点不强制翻译
- 调用方可通过 `Accept-Language` 头表达语言偏好,服务方可选择响应或不响应
- 参数值本身的多语言(如 `明天` vs `tomorrow`)由服务方自行处理,不在协议范围内

---

## 9. 路径协议

### 9.1 概述

单条指令解决一件事,路径解决一类事。路径是多条指令的有序组合,Agent 通过匹配路径描述自动编排执行。路径与指令的关系:指令是原子,路径是分子。

一条路径在 `path-schema.json` 中注册,Agent 匹配后按指令链顺序执行。

### 9.2 路径类型学

text-cli 定义了四种路径模式(非互斥,不要求全覆盖):

| 模式 | 核心步骤 | 数据流 | 实例 |
|:---|:---|:---|:---|
| **工具链** (Toolchain) | `action` 线性串联 | 上步产出 → 下步输入 | 查找消息 → 写入文件 → 发送邮件 |
| **编排** (Orchestration) | `parallel` | 一分多 → 并行执行 → 合并 | 多源图片渲染(多个图片源并行下载 → 统一渲染) |
| **交互式** (Interactive) | `call` + `loop`(human_review) | 生成 → 审阅 → 决策 → 部署 → 验证循环 | MCP 服务接入(生成 config → 人工审阅 → 编译部署 → 健康校验) |
| **注入式** (Injection) | `subpath` | 修改执行环境,不产出最终结果 | 配置注入、环境初始化 |

> 四种模式不是互斥分类--一条路径可以混合多种模式。实例列基于当前已实现的路径。

### 9.3 path-schema.json 条目格式

每条路径在 `path-schema.json` 中为一个独立的 JSON 对象,键为路径标识。

**示例 1:工具链(纯本地)**

```json
{
  "查找消息并发送邮件": {
    "description": "从 AI 协作者状态中查找最近的对话消息,写入文件后通过邮件发送给指定收件人",
    "mode": "toolchain",
    "params": ["消息条数", "收件人邮箱", "邮件主题"],
    "instruction_chain": [
      "AI:ai;fetch_messages",
      "AI:file;write",
      "AI:mail;send"
    ],
    "require_instructions": ["ai;fetch_messages", "file;write", "mail;send"],
    "rank": 1,
    "tags": ["消息", "邮件"]
  }
}
```

**示例 2:跨端点(本地 + 远程 MCP)**

```json
{
  "照片分析": {
    "description": "加载本地照片,通过 AI 推理分析照片内容并生成图表",
    "mode": "toolchain",
    "params": ["照片路径"],
    "instruction_chain": [
      "AI:media;load",
      "AI:ai;infer",
      "AI:antvchart;pie"
    ],
    "require_instructions": ["media;load", "ai;infer", "antvchart;pie"],
    "rank": 1,
    "tags": ["照片", "AI", "图表"],
    "_note": "第 1 步走本地 copilot(media;load),第 2 步可走本地或远程,第 3 步走 MCP(antvchart)。Agent 不需要知道三步分别去哪个端点--路径层统一编排。"
  }
}
```

**字段说明:**

| 字段 | 必须 | 说明 |
|:---|:---|:---|
| `description` | 是 | 意图说明,Agent 用于语义匹配 |
| `mode` | 否 | 路径模式标识:`"toolchain"` / `"orchestration"` / `"interactive"` / `"injection"`。辅助 Agent 选择执行策略 |
| `params` | 是 | 路径级参数列表,Agent 执行前从用户/环境收集 |
| `instruction_chain` | 是 | 指令有序列表。推荐使用 `AI:domain;action` 规范名,但 alias 形式等效 |
| `require_instructions` | 是 | 前置指令门控--链中每条指令的 `领域;动作` 必须已在指令 Schema 中注册 |
| `rank` | 否 | 路由优先级,默认 1 |
| `tags` | 否 | 辅助分类标签 |
| `path_doc` | 否 | 复杂路径的详细实现文档引用 |

> **路径的跨度决定它的价值**:当一条路径横跨本地和远程两种端点时(如示例 2),路径层的抽象价值才真正体现--Agent 调用方只需要知道"照片分析"这一个意图,不需要理解三步的去向。

### 9.4 路径执行门控

**路径生效前必须通过两道门控:**

1. **指令注册门控**:`require_instructions` 中的每条 `领域;动作` 必须在当前端点的指令 Schema(如 `text_cli_schema.json`)中存在。任一指令未注册 → 路径不生效。
2. **路径匹配门控**:Agent 将用户意图与路径 `description` 进行语义匹配。匹配不成功 → 回退到指令调度或 Agent 推理。

门控确保了路径的可靠性--不会因引用了不存在的指令而在执行中失败。

### 9.5 路径与指令的关系

- 路径引用的每条指令独立遵循 §2 的 HTTP API 规范，通过 `/cli/text_cli` 端点调用。一条路径内可以混合本地端点和远程端点——Agent 调用方不需要知道每一步的去向。
- 路径不在指令层引入新协议——路径是 Agent 侧的编排逻辑，指令服务无需感知路径。
- 路径的 Token 节约发生在推理环节（Agent 不需要思考"需要什么步骤"），而非执行环节。
- 路径不定义新端点——路径在本地路径文件中声明，由 Agent 读取并编排。路径文件与指令 Schema 的关系：路径引用指令，指令不引用路径。

---

## 10. 语义注册表

### 10.1 定位

语义注册表是 text-cli 生态的**受控词表**--收录生态内已注册的领域和动作,附带多语言别名和嵌入指纹。它不是运行时调度层(意图匹配走 `trigger_keywords`),而是**命名规范层**,用于:

1. **新指令命名校验**:私有指令接入时,提供方提交的 `领域;动作` 应与注册表比对。新提出的名称如果和已有条目嵌入过于接近,建议复用已有名称而非新建,防止生态内语义冗余。
2. **多语言对齐**:同一条目的所有语言 alias 始终指向同一个 `semantic_id`。与 §8 协同--§8 定义别名注册机制,§10 把别名映射扩展到所有领域和动作的语义注册。
3. **跨模型可移植**:一个条目在多个嵌入模型的注册表文件中共享同一个 `semantic_id`,独立于嵌入模型。

### 10.2 文件命名约定

```
schema/semantic-registry_{model-slug}.json
```

- `{model-slug}` 为嵌入模型的简称,全小写,下划线分隔。如 `bge-m3`、`gte-qwen2`、`text-embedding-3`。
- 多个嵌入模型的注册表文件并行存在。调用方按部署环境选择对应文件进行命名校验。
- 所有文件共享相同的 `semantic_id` 命名空间--同一领域/动作在不同模型文件中使用相同的 `semantic_id`。

### 10.3 条目格式

语义注册表包含两个独立数组--`domains` 和 `actions`。领域和动作分表存储,允许自由组合(同一动作可用于不同领域)。

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
  "embedding": [0.0678, -0.0901],
  "routing": {
    "type": "local",
    "backends": [
      {"type": "local"},
      {"type": "http", "url": "https://weather.example.com/cli/text_cli"}
    ]
  }
}
```

#### 字段说明

| 字段 | 必须 | 说明 |
|:---|:---|:---|
| `semantic_id` | 是 | 全局唯一标识符。`domain.*` 或 `action.*` 前缀区分类型,不可变 |
| `aliases` | 是 | 多语言别名映射。键为 ISO 639-1 语言代码,值在该语言中唯一 |
| `description` | 是 | 语义说明,格式为 `English description;中文说明`,两段用半角分号分隔 |
| `embedding` | 是 | 当前模型的嵌入向量。维度由 `_meta.dimensions` 声明 |
| `routing` | 否 | 多后端路由声明。定义此语义坐标支持哪些执行后端。无此字段时默认为 `{"type": "local"}`。具体 Schema 见 §11.4 |

> **`semantic_id` 不可变**:录入后即固定。如需废弃,通过 `_meta.deprecated_ids` 标记,不直接删除(防止引用断裂)。

### 10.4 `aliases` 与 §4 Schema 的关系

语义注册表的 `aliases` 和指令 Schema 的多语言字段(`directive_zh`、`category` 别名等,见 §8.4)是两个独立层次:

- **语义注册表 aliases**:规范层--定义"这个动作在中文叫什么"。是生态共识。
- **指令 Schema 多语言字段**:实现层--定义"具体这条指令还接受什么语言触发"。可以超出语义注册表的范围(例如接受方言或缩写)。

两者互补不冲突:语义注册表设下限(至少具备这些别名),指令 Schema 可在此之上扩展。

### 10.5 命名校验流程(参考)

当新指令申请注册 `领域;动作` 时:

1. 将新名称按语言嵌入当前注册的嵌入模型
2. 在语义注册表中计算新名称与所有同类型条目(领域 vs 领域,动作 vs 动作)的余弦相似度
3. 相似度超过阈值 → 返回已有的 `semantic_id`,建议复用
4. 相似度低于阈值 → 新建 `semantic_id`,录入注册表

> 阈值和具体校验工具链由实现层定义,不在协议规范范围内。

### 10.6 参考文件

- 首个注册表文件:`schema/semantic-registry_bge-m3.json`(BAAI/bge-m3,1024 维)
- 注册表条目从生态内已运行的指令中提取--即 `text_cli_schema.json` 和 agent-copilot 14 条指令中所有已出现的领域和动作

---

## 11. 本地指令端点

### 11.1 概述

text-cli 协议定义了两种端点形态:

| | 集成端点(转发型) | 本地端点(执行型) |
|:---|:---|:---|
| **代表** | `api.text-cli.com` | `agent-copilot` |
| **职责** | 接收指令 → 鉴权 → 转发到技能服务 | 接收指令 → 鉴权 → 本地执行 → 返回结果 |
| **双层令牌** | Access Token + Service Token | 单层 Token(local auth) |
| **计费** | 支持,按 Service Token 计数 | 无(自用端点) |
| **安全模型** | 令牌鉴权 + 转发隔离 | 路径白名单 + 分支白名单 + 凭据居中 |
| **端点路径** | `/cli/text_cli` | `/cli/text_cli`(统一) |

两种端点使用相同的端点路径、请求格式和响应格式--Agent 从集成端点切换到本地端点不需要修改调用逻辑,只改变目标地址。

### 11.2 本地端点的安全模型

本地端点不依赖 Service Token 计费,安全模型围绕以下机制构建:

**路径白名单**:文件读写操作限定在配置的目录范围内。任何越界访问在指令解析阶段即被拒绝,返回 `[path_denied]`。

**分支白名单**:Git 推送操作限定在允许的分支列表内。向未授权分支推送时返回 `[branch_denied]`。

**凭据居中**:SMTP 密码、Git 凭证等敏感信息仅存储在 copilot 配置文件中,不进入 Agent 上下文。Agent 发送的指令中不包含任何凭据。

**单层鉴权**:本地端点通过本地 Token 鉴权(Bearer Token),仅绑定本地回路。不对外开放,不走网络转发。

### 11.3 本地端点与指令 Schema 的关系

- 本地端点提供的指令应在 `agent-text-cli-schema.json` 中注册,与远程端点指令统一管理。
- 路径链可以混合本地指令和远程指令--`instruction_chain` 不区分指令来源。
- 未来版本建议在指令 Schema 中增加 `source` 字段标记指令来源(本地/远程),便于 Agent 路由决策。

### 11.4 多后端路由(v1.1 新增)

同一语义坐标可以通过 `routing` 字段声明多个执行后端。路由在执行时决策,对指令格式透明。

#### routing 字段 Schema

```json
{
  "routing": {
    "type": "mcp",
    "backends": [
      {"type": "local"},
      {"type": "mcp", "server": "tencent-maps", "tool": "geocoder", "adapter": "passthrough", "param_names": ["address"], "timeout_ms": 30000},
      {"type": "http", "url": "https://api.example.com/cli/text_cli"}
    ]
  }
}
```

| 字段 | 必须 | 说明 |
|:---|:---|:---|
| `routing.type` | 否 | 默认路由类型。`"local"`(默认)、`"mcp"`、`"http"` |
| `routing.backends` | 否 | 此语义坐标支持的所有后端列表 |

**MCP 后端字段**(`type = "mcp"` 时):

| 字段 | 必须 | 说明 |
|:---|:---|:---|
| `server` | 是 | MCP server 名称 |
| `tool` | 是 | MCP tool 名称 |
| `adapter` | 否 | 参数适配器,默认 `"passthrough"`。可选值:`passthrough`(位置参数按 `param_names` 顺序映射)、`json_parse`(首个参数作为 JSON 解析)、自定义 adapter 名 |
| `param_names` | 否 | 位置参数 → MCP tool 参数的名称映射。仅在 `adapter = "passthrough"` 时使用 |
| `timeout_ms` | 否 | 超时时间(毫秒),默认 30000 |

**HTTP 后端字段**(`type = "http"` 时):

| 字段 | 必须 | 说明 |
|:---|:---|:---|
| `url` | 是 | 目标端点地址 |

**设计原则**:

- `routing` 是语义注册表条目的**可选**字段。无此字段的条目行为不变--等同于 `{"type": "local"}`。
- 指令格式(§1)不携带任何 routing 信息。变的是执行层,不是协议层。
- routing 的偏好配置(优先走哪条路)、参数适配器、具体执行方式属于实现层,见独立文档 `Multi-backend-routing_CN.md`。

**与 §10 的关系**:

`routing` 挂在语义注册表的 action 条目上,而不是指令 Schema(§4)上。因为 routing 是「这个语义坐标有哪些执行方式」--它是注册表的概念。指令 Schema 负责「这个端点提供了哪些指令」--它是服务发现的概念。两者互不替代。

### 11.5 参考实现

`server/agent-copilot/` 是本地端点的首个参考实现:14 条指令,Python stdlib 零依赖,安全模型完整(路径白名单、分支白名单、凭据居中)。可作为本地端点开发的模板和测试基准。

---
