# text-cli Protocol Specification v1.2

> 2026-05-17 — 协议从文本 RPC 格式升级为技能交付规范。
> 新增：聚合指令、nocode 指令包、包生命周期（export/manifest）、管道闭包原则、service_manifest 白名单暴露。
> 前缀变更：`指令:` 为过渡期中文前缀，未来仅保留 `AI:`。废弃从未实现的 `directive:` 前缀。
> 废弃：旧 Schema 格式（prompt_template/trigger_keywords/directive_zh）——v1.2 统一为新格式。

---

## 1. 指令格式规范

### 1.1 基本结构

```
指令:<领域>;<动作>,<参数1>,<参数2>,...
AI:<领域>;<动作>,<参数1>,<参数2>,...
```

- **当前两前缀**：`指令:`（中文入口，过渡期保留）和 `AI:`（长期规范）。两者等效。
- **远期一前缀**：`指令:` 将在协议下一主版本中移除，统一为 `AI:`。
- **从未存在的前缀**：`directive:` 从未在实现中存在——v1.2 正式移除。

- 
- **领域**：命名空间，规范名 ASCII，别名不限字符集。
- **动作**：动词，规范名 ASCII，别名不限。
- **参数**：逗号分隔，顺序固定。末位参数可为自由文本（含逗号）。

### 1.2 指令类型

协议识别四种指令载体：

| 类型 | 实现 | 声明 |
|------|------|------|
| **native** | handler.py，`@directive` 装饰器 | schema.json + handler.py |
| **nocode** | Markdown 知识文件 + path JSON | schema.json + knowledge/ + paths/ |
| **aggregate** | 纯声明，无 handler | aggregate/*.json |
| **path** | 步骤链 JSON | path JSON + schema.json |

### 1.3 聚合指令

聚合指令提供域级入口，收敛多个提供方。调用方使用 `domain;action` 格式，不感知背后的降级链：

```
map;geocode,威海        ← 聚合入口，内部依次尝试多个提供方
web;search,威海攻略      ← 聚合入口
```

详见 §13。

---

## 2. HTTP API 规范

### 2.1 请求结构

```
POST /cli/text_cli
Content-Type: application/json
Service-token: <token>

{"prompt": "AI:域;动作,参数1,参数2"}
```

### 2.2 响应结构

```json
{
  "rst_types": "text",
  "rst_data": {"text": "..."}
}
```

异步指令返回 task_id：

```json
{"rst_types": "text", "rst_data": {"text": "{\"status\":\"pending\",\"task_id\":\"asr-12345\"}"}}
```

调用方通过 `task;status,<task_id>` 查询——task-manager 实时向外部服务获取最新状态。

### 2.3 GET 应急通道

```
GET /cli/text_cli?prompt=<URL编码的指令>
```

默认关闭。运营方显式开启。无需认证，风险自担。

### 2.4 技能端点

```
GET  /text-cli/skills          → 公开技能列表（受 service_manifest 白名单控制）
GET  /text-cli/skills/<id>     → 单个技能详情
POST /text-cli/skills/<id>     → 执行技能
```

### 2.5 健康检查

```
GET /health
```

公开层返回 `{status, body, version, public_skills}`。鉴权层返回完整 `capabilities`。

---

## 3. 鉴权与计费

### 3.1 双层令牌

```
调用方 ──Access Token──> 集成端点 ──Service Token──> 技能服务
```

- **Access Token**：端点签发，验证调用者身份。
- **Service Token**：调用方与技能提供方私下约定，端点透传。

### 3.2 配额保护

指令可在执行前通过 `quota;check,<target>[,<amount>]` 进行配额检查。配额耗尽返回 `{"status":"stop"}`——聚合层将其作为降级信号，自动切换到下一个提供方。

---

## 4. Schema 元数据规范

### 4.1 指令包 Schema（package-level）

每个指令包必须有一个 `schema.json`，声明包元数据和指令列表。

```json
{
  "id": "xx-cloud",
  "name": "XX Cloud",
  "name_cn": "XX云",
  "type": "native",
  "runtime": "python",
  "category": "云服务",
  "version": "1.0.0",
  "locales": ["cn", "en"],
  "trust": "internal",
  "description": "...",
  "description_cn": "...",
  "requires": {
    "pip": ["requests>=2.28"],
    "tc_packages": ["task-manager", "quota-manage"]
  },
  "credentials": {"tx": "sqlite"},
  "directives": [
    {
      "domain": "xx-cloud",
      "domain_cn": "XX云",
      "action": "translation",
      "action_cn": "翻译",
      "usage": "xx-cloud;translation,<text>[,<target>]",
      "usage_cn": "XX云;翻译,<文本>[,<目标>]",
      "description": "Translate text via API.",
      "description_cn": "通过 API 翻译文本。",
      "params": ["text", "target"],
      "params_desc": {
        "text": "Text to translate",
        "target": "Target language ISO code (default: en)"
      }
    }
  ]
}
```

### 4.2 顶层字段

| 字段 | 必填 | 说明 |
|------|------|------|
| `id` | ✅ | 包唯一标识 |
| `type` | ✅ | `"native"` / `"nocode"` / `"aggregate"` / `"path"` |
| `runtime` | ✅ | `"python"` / `"node"` / `"mcp"` / `"cmd"` |
| `category` | ✅ | 分类标签 |
| `locales` | ✅ | 多语言覆盖 |
| `trust` | ✅ | `"internal"` / `"community"` / `"public"` |
| `requires.pip` | 否 | Python 包依赖 |
| `requires.tc_packages` | 否 | 指令包间依赖 |
| `requires.binaries` | 否 | 系统二进制依赖 |
| `credentials` | 否 | 需要的凭据（key name → source） |
| `entry` | 否 | 公开端点 URL |
| `mcp_server` | 否 | MCP server 名 |
| `version` | 否 | Semver |

### 4.3 指令级字段（directives[]）

| 字段 | 必填 | 说明 |
|------|------|------|
| `domain` | ✅ | 指令域 |
| `domain_cn` | 推荐 | 中文域别名 |
| `action` | ✅ | 动作名 |
| `action_cn` | 推荐 | 中文动作别名 |
| `usage` | ✅ | 用法示例（规范名） |
| `usage_cn` | 推荐 | 中文用法示例 |
| `description` | ✅ | 英文描述 |
| `description_cn` | ✅ | 中文描述 |
| `params` | 否 | 参数名列表 |
| `params_desc` | 否 | 参数说明对象 |
| `mcp_tool` | 否 | 原始 MCP tool 名 |

### 4.4 聚合指令 Schema

聚合指令没有 handler.py，只有路由声明。

```json
{
  "id": "map",
  "type": "aggregate",
  "domain": "map",
  "description_cn": "地图服务：多提供方自动降级",
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

### 4.5 路径声明条目

```json
{
  "id": "route-map",
  "name_cn": "地图连线",
  "type": "path",
  "version": "1.0.0",
  "input_schema": {"type": "string"},
  "output_schema": {"type": "picture"},
  "requires": ["map;geocode", "map;route", "xx-map;static-map"],
  "steps": [
    {"id": "start", "directive": "map;geocode,${input}", "output_as": "start"},
    {"id": "route", "directive": "map;route,{start.lat},{start.lon},{end.lat},{end.lon}", "output_as": "route"},
    {"id": "map", "directive": "xx-map;static-map,{end.lat},{end.lon},14,600x400,...", "output_as": "map"}
  ]
}
```

| 字段 | 必填 | 说明 |
|------|------|------|
| `id` | ✅ | 路径唯一标识 |
| `type` | ✅ | 固定为 `"path"` |
| `version` | 推荐 | Semver |
| `input_schema` | 推荐 | 输入参数的 JSON Schema 片段 |
| `output_schema` | 推荐 | 输出结果的 JSON Schema 片段 |
| `requires` | ✅ | 依赖的指令列表 |
| `steps` | ✅ | 步骤数组 |

---

## 5. 错误响应

错误码：

| 错误码 | 含义 |
|--------|------|
| `INVALID_DIRECTIVE_FORMAT` | 指令格式不正确 |
| `INVALID_PARAMS` | 参数不合法 |
| `DIRECTIVE_NOT_FOUND` | 未找到匹配的指令 |
| `ACCESS_DENIED` | Access Token 无效 |
| `SERVICE_DENIED` | Service Token 无效或额度不足 |
| `BACKEND_TIMEOUT` | 后端服务超时 |
| `BACKEND_ERROR` | 后端未知错误 |

错误以单行结构化字符串返回，不膨胀 Agent 上下文。

---

## 6. 响应类型扩展

| `rst_types` | `rst_data` 承载 |
|-------------|----------------|
| `text` | `rst_data.text` |
| `picture` | `rst_data.url` + `rst_data.text` |
| `video` | `rst_data.url` + `rst_data.text` |
| `audio` | `rst_data.url` + `rst_data.text` |
| `file` | `rst_data.url` + `rst_data.text` |

`text` 始终可用——作为渲染失败时的回退。

---

## 7. 版本管理

- 当前版本 v1.2
- v1.2 新增：聚合指令（§13）、nocode 指令包（§4.2 type 值域）、管道闭包原则（§9.1）、包生命周期导出（§10.3）、service_manifest 白名单（§10.5）
- v1.2 废弃：旧 Schema 格式（prompt_template/trigger_keywords/directive_zh 字段）。运行时保留向后兼容，SPEC 正文中不再出现

---

## 8. 多语言指令规范

指令格式语言无关。服务方注册时声明规范名和别名，端点归一化后路由。

- 服务提供方只用一种语言注册
- 翻译在端点层做，不在服务层
- 参数不翻译——语义由位置决定
- 语言不匹配时返回 `DIRECTIVE_NOT_FOUND`

---

## 9. 路径协议

### 9.1 管道闭包原则

**路径只做编排和插值。文件 IO、API 调用、推理——全部通过指令完成。**

```
路径引擎：编排指令序列（step1 → step2 → step3）
指令：     执行具体操作（tc-markdown;read, ai;infer, map;geocode）
```

路径不读文件——它调 `tc-markdown;read`。不推理——它调 `ai;infer`。不调 API——它调 `map;geocode`。这是协议的设计红线。

### 9.2 步骤语法

```json
{
  "id": "step_id",
  "directive": "domain;action,${input},{prev.field}",
  "output_as": "step_id"
}
```

| 语法 | 含义 |
|------|------|
| `${input}` | 用户输入 |
| `{step_id.field}` | 上一步输出的 JSON 字段（支持深度路径如 `{geo.poi.0.name}`） |
| `output_as` | 捕获步骤输出为变量 |

### 9.3 收敛模板

AI 自由文本 → 路径引擎 JSON 插值的关键桥梁。步骤间传递时，要求 AI 返回纯 JSON：

```
ai;infer,'只返回JSON如{"file":"根腐病.md"}'
→ 下一步: tc-markdown;read,{lookup.file}
```

### 9.4 条件执行

```json
{"id": "fallback", "directive": "...", "if": "{step.field} == 'NOMATCH'"}
```

### 9.5 上下文注入防护

路径声明天然抗注入——`steps` 在 JSON 中固定，数据通过命名管道单向流动。注入载荷永远不会从数据位置逃脱到指令位置。

### 9.6 技能发布

```json
text-cli;pro,<path_id>
```

发布后路径获得 `skill;*` 调用入口，与原子指令平权。

---

## 10. 平台自管理

### 10.1 指令包安装

```
text-cli;install,<包名>
```

安装流程：验证 schema.json → 安装依赖 → 复制 handler → 写入 handler_inits → 写入 manifest。重启后自动加载。

### 10.2 指令包卸载

```
text-cli;uninstall,<包名>
```

移除文件 + 清理 handler_inits 条目 + 清理 manifest。

### 10.3 包生命周期导出

```
text-cli;export,<包名>         → 单包导出
text-cli;export-all            → 全量导出
text-cli;packages              → 列出已安装包
```

导出的包结构与安装格式一致，可被 `text-cli;install` 直接消费。

### 10.4 指令查询与发现

```
text-cli;query,<关键词>        → 搜索指令
text-cli;path,<路径文件>       → 注册路径
```

### 10.5 技能暴露控制

服务通过 `service_manifest.json` 声明对外暴露的指令：

```json
{"public_directives": ["map;geocode", "web;search", "weather;query"]}
```

白名单为空 = 全部暴露（向后兼容）。有内容时只暴露列出的条目。`/skill` 端点据此过滤输出。

### 10.6 包清单跟踪

`installed_packages.json` 记录每个已安装包的来源、类型、文件列表和安装时间。支撑 export/uninstall/list 操作。

---

## 11. 语义注册表

服务启动时自动扫描已注册指令，建立 domain → action → handler 映射。别名（中文域/动作名）等价路由。注册表通过 `text-cli;query` 对外暴露，Agent 用于意图匹配。

---

## 12. MCP 与 Skill Bridge

### 12.1 MCP Bridge

`mcp_exposure.json` 声明 MCP server 连接。`mcp2textcli` 自动编译 tools → text-cli 指令。passthrough 指令（纯文本参数）零手写。

### 12.2 Skill Bridge

`skill_bridge_routes.json` 声明 ClawHub skill → text-cli 指令映射。

```json
{
  "skill-bdmap;geocode": {
    "skill": "baidu-ai-map",
    "command": "python3 {skill_dir}/scripts/baidumap.py geocode '{address}'",
    "adapter": "baidumap",
    "output_adapter": "baidu-map/geocode",
    "timeout_ms": 15000
  }
}
```

两层适配器：通用适配器（status 归一化）+ output_adapter（字段映射到规范格式）。

### 12.3 routing：单指令多后端

用户只接入了少量 MCP 服务转化来的指令时，通过 `routing` 字段声明单条指令的多后端。当同一个域有多个提供方后，升级到 aggregate 做域级降级链收敛。

```json
{
  "routing": {
    "type": "mcp",
    "backends": [
      {"type": "mcp", "server": "x1-maps", "tool": "geocoder", "adapter": "passthrough", "param_names": ["address"]}
    ]
  }
}
```

---

## 13. 聚合指令

### 13.1 概述

聚合指令提供域级入口，将多个提供方收敛为一条指令。调用方不感知提供方差异，只看到一个入口。

### 13.2 声明

`aggregate/` 目录下 JSON 文件，启动时自动加载。

```json
{
  "id": "map",
  "type": "aggregate",
  "domain": "map",
  "default": ["x1-map", "x2-map", "x3-map"],
  "providers": {
    "x1-map": {"geocode": "x1-map;geocode", "route": "x1-map;route"},
    "x2-map": {"geocode": "x2-map;geocode"}
  }
}
```

### 13.3 提供方不区分来源

native handler、MCP bridge、Skill Bridge——在聚合降级链中地位平等。`providers` 中的值只要是一个可被 `dispatch()` 解析的 `domain;action` 即可。

### 13.4 降级链

```
请求 → 聚合命中
  → 查 default 降级链
  → 依次 dispatch 每个提供方
  → 返回第一个成功结果
```

降级触发条件：返回 `status: "stop"`（配额耗尽）、返回 `status: "error"`、dispatch 异常或指令未注册。

### 13.5 用户显性选择

末参数匹配提供方名时，优先该提供方：

```
map;geocode,威海,x2-map     → 只用 x2-map，不降级
```

### 13.6 聚合在请求管道中的位置

```
请求 → 聚合 dispatch → MCP 优先路由 → 本地 dispatch → MCP 后备 → proxy
```

聚合最先执行。未命中时继续走后续管道。
