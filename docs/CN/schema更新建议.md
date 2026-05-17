# schema.json 字段全览与更新建议

> 2026-05-17 | Tide 🌊
> 基于 `service/handlers/schema/` 下 21 份实际 schema 文件分析

---

## 一、顶层字段

### 1.1 现有字段

| 字段 | 类型 | 必填 | 出现率 | 说明 |
|------|------|------|--------|------|
| `id` | string | ✅ | 20/21 | 包唯一标识，如 `tx-cloud` |
| `name` | string | ✅ | 20/21 | 英文名 |
| `name_cn` | string | ✅ | 20/21 | 中文名 |
| `type` | string | ⚠️ | 1/21 | 仅路径 schema 有（`"skill"`），其他全部缺失 |
| `category` | string | ✅ | 20/21 | 分类：基础应用/云服务/媒体生成/地图服务… |
| `runtime` | string | ✅ | 18/21 | `"python"` / `"node"` / `"mcp"` / `"cmd"` / `"path"` |
| `locales` | array | ✅ | 20/21 | `["cn", "en"]`，声明多语言覆盖 |
| `description` | string | ✅ | 20/21 | 英文描述 |
| `description_cn` | string | ✅ | 20/21 | 中文描述 |
| `trust` | string | ⚠️ | 12/21 | `"internal"` / `"public"` / `"community"`，缺失于 MCP/远程 schema |
| `requires` | object | ❌ | 2/21 | `{"pip": [...]}` 仅 ms-tts 和 geo-grid 声明了 |
| `credentials` | object | ❌ | 3/21 | ai_generate / ai_inference / embed 声明 key 依赖 |
| `entry` | string | ❌ | 6/21 | 公开端点 URL，tideweather/ai_generate/image 等 |
| `mcp_server` | string | ❌ | 3/21 | MCP server 名，仅 github/mcp_antv/mcp_tencent-maps |
| `source_file` | string | ❌ | 1/21 | 路径源文件，仅 `path_photo_analysis` |
| `steps` | array | ❌ | 1/21 | 路径步骤定义，仅 `path_photo_analysis` |
| `input_schema` | object | ❌ | 1/21 | 路径输入定义，仅 `path_photo_analysis` |
| `output_schema` | object | ❌ | 1/21 | 路径输出定义，仅 `path_photo_analysis` |
| `version` | string | ❌ | 1/21 | 版本号，仅 `path_photo_analysis` |
| `mode` | string | ❌ | 1/21 | 执行模式，仅 `path_photo_analysis`（`"toolchain"`） |

### 1.2 新字段建议

| 字段 | 类型 | 建议 | 理由 |
|------|------|------|------|
| `type` | string | **全员必填** | 当前仅路径有。应推广到全部 schema：`"native"` / `"nocode"` / `"aggregate"` / `"path"`。aggregate 不需要 handler.py，nocode 不需要代码。A3 install 据此决定部署策略 |
| `trust` | string | **全员必填** | 当前 12/21 有。缺失的应补为 `"internal"`。A5 端点 + A8 白名单依赖此字段决定暴露策略 |
| `requires` | object | **补全** | 当前仅 2/21 有。加 `tc_packages` 数组声明指令包间依赖。A3 install 做依赖检查 |

### 1.3 `requires` 子字段

| 字段 | 消费方 | 说明 |
|------|--------|------|
| `requires.pip` | A3 install（依赖安装） | `["edge_tts", "requests>=2.28"]` |
| `requires.tc_packages` | A3 install（依赖检查） | `["task-manager", "quota-manage"]` |
| `requires.binaries` | A3 install | `["ffmpeg", "chromium"]` |
| `requires.os_packages` | A3 install | `["libreoffice"]` |

---

## 二、指令级字段（directives[]）

### 2.1 现有字段

| 字段 | 类型 | 必填 | 出现率 | 说明 |
|------|------|------|--------|------|
| `domain` | string | ✅ | 全部 | 指令域，如 `tx-cloud` |
| `domain_cn` | string | ✅ | 全部 | 中文域别名，如 `腾讯云` |
| `action` | string | ✅ | 全部 | 动作名，如 `translation` |
| `action_cn` | string | ✅ | 全部 | 中文动作别名，如 `翻译` |
| `usage` | string | ✅ | 全部 | 英文用法示例 |
| `usage_cn` | string | ✅ | 全部 | 中文用法示例 |
| `description` | string | ⚠️ | 大部分 | 缺失于 mcp_tencent-maps 等 passthrough 指令 |
| `description_cn` | string | ⚠️ | 大部分 | 同上 |
| `params` | array | ⚠️ | 大部分 | 参数名列表，缺失于无参指令 |
| `params_desc` | object | ⚠️ | 部分 | 参数说明，map render 等指令缺失 |
| `mcp_tool` | string | ❌ | 3/21 | 原始 MCP tool 名，仅 github/mcp_antv/mcp_tencent-maps |
| `category` | string | ❌ | 2/21 | 个别指令有独立分类（github/system），不规范 |

### 2.2 字段消费方映射

| 字段 | A0 协议 | A1 Skill | A2 copilot | A3 service | A4 paths | A5 endpoint | A6 SQL | A7 MCP | A8 discovery | A9 aggregate |
|------|---------|----------|------------|------------|----------|-------------|--------|--------|-------------|-------------|
| `domain` | ✅ parse | ✅ match | ✅ route | ✅ register | ✅ directive | — | — | ✅ map | ✅ search | ✅ route |
| `action` | ✅ parse | ✅ match | ✅ route | ✅ register | ✅ directive | — | — | ✅ map | ✅ search | ✅ route |
| `params` | ✅ parse | ✅ fill | ✅ forward | ✅ validate | ✅ interpolate | — | — | ✅ adapt | — | ✅ forward |
| `usage` | — | ✅ example | — | — | — | — | — | — | ✅ display | — |
| `description` | — | ✅ intent | — | — | — | — | — | — | ✅ match | — |
| `params_desc` | — | ✅ fill | — | — | — | — | — | — | ✅ hint | — |
| `mcp_tool` | — | — | — | — | — | — | — | ✅ bridge | — | — |
| `domain_cn` | ✅ parse | ✅ match | — | ✅ alias | — | — | — | — | — | — |
| `action_cn` | ✅ parse | ✅ match | — | ✅ alias | — | — | — | — | — | — |

### 2.3 顶层字段消费方映射

| 字段 | A0 | A1 | A2 | A3 | A4 | A5 | A6 | A7 | A8 | A9 |
|------|----|----|----|----|----|----|----|----|----|----|
| `id` | — | — | — | ✅ install | ✅ register | — | — | — | ✅ catalog | — |
| `type` | — | — | — | ✅ deploy | — | — | — | — | ✅ filter | ✅ route |
| `runtime` | — | — | — | ✅ install | — | — | — | — | ✅ filter | — |
| `trust` | — | — | — | — | — | ✅ expose | — | — | ✅ gate | — |
| `requires` | — | — | — | ✅ check | — | — | — | — | — | — |
| `credentials` | — | — | — | — | — | — | ✅ key.get | — | — | — |
| `mcp_server` | — | — | — | — | — | — | — | ✅ bridge | — | — |
| `entry` | — | — | — | — | — | ✅ endpoint | — | — | ✅ link | — |
| `locales` | — | — | — | — | — | — | — | — | ✅ lang | — |
| `category` | — | — | — | — | — | — | — | — | ✅ group | — |
| `steps` | — | — | — | — | ✅ execute | — | — | — | — | — |
| `input_schema` | — | ✅ validate | — | — | ✅ bind | — | — | — | ✅ hint | — |
| `output_schema` | — | — | — | — | ✅ capture | — | — | — | ✅ hint | — |
| `version` | — | — | — | ✅ update | — | — | — | — | ✅ check | — |
| `mode` | — | — | — | — | ✅ execute | — | — | — | — | — |

---

## 三、缺失与不一致

### 3.1 `type` 全员缺失（除路径）

所有 native handler schema 都没有 `type` 字段。当前隐式约定：有 handler.py = native。但有了 nocode（无 handler）和 aggregate（无 handler + 无指令）后，隐式区分不再可靠。

**建议**：所有 schema.json **必须声明** `type`。值域：`"native"` / `"nocode"` / `"aggregate"` / `"path"`。A3 的 validate_package 以此为部署条件分支。

### 3.2 `requires.tc_packages` 全部缺失

当前 `requires` 仅支持 `pip`。但 tx-cloud 依赖 task-manager 和 quota-manager——安装 tx-cloud 前必须确保它们已就绪。这个依赖关系无处声明。

**建议**：schema.json 加 `requires.tc_packages`，A3 install 遍历检查 → registry 已有？→ 否则拒绝。

### 3.3 `trust` 覆盖率仅 57%

12/21 有 `trust`。9 个缺失——主要是 MCP 桥 schema 和 tideweather/ai_generate/image 等外部接入 schema。这些缺失的 schema 在 A5 端点暴露时没有信任级别，无法决定可见性。

**建议**：所有 schema 强制声明 `trust`。

### 3.4 路径 schema 混入了指令级 directive[]

`path_photo_analysis.json` 既有顶层路径字段（`steps`/`input_schema`）又有 `directives[]` 数组，但 directives 里的指令只是"这个路径暴露为哪条 text-cli 指令"——和 native handler 的 directives 语义不同（native 是注册 handler，path 是注册别名）。

**建议**：路径 schema 的对外指令声明收束到顶层 `expose: [{domain, action}]`，不混用 `directives`。

### 3.5 MCP 指令缺少 `params`

`mcp_antv` 和 `mcp_tencent-maps` 的 directives 数组没有 `params` 和 `params_desc`。passthrough 可以省略，但 A1 Skill（AI Agent 调用）和 A8 discovery（用户查询）需要参数信息才能完成意图匹配。

**建议**：MCP 编译流程（mcp2textcli）自动填充 `params`。

---

## 四、规范 schema 模板

```json
{
  "id": "<package-id>",
  "name": "<English Name>",
  "name_cn": "<中文名>",
  "type": "native | nocode | aggregate | path",
  "runtime": "python | node | mcp | cmd",
  "category": "<分类>",
  "version": "1.0.0",
  "locales": ["cn", "en"],
  "trust": "internal | community | public",
  "description": "<EN>",
  "description_cn": "<CN>",

  "requires": {
    "pip": [],
    "tc_packages": [],
    "binaries": [],
    "os_packages": []
  },

  "credentials": {
    "<key_name>": "env | sqlite"
  },

  "entry": "<url-if-public>",
  "mcp_server": "<mcp-server-name-if-mcp>",

  "directives": [
    {
      "domain": "<domain>",
      "domain_cn": "<中文域>",
      "action": "<action>",
      "action_cn": "<中文动作>",
      "usage": "<domain;action,params>",
      "usage_cn": "<中文域;中文动作,参数>",
      "description": "<EN>",
      "description_cn": "<CN>",
      "params": ["param1", "param2"],
      "params_desc": {
        "param1": "<EN desc>",
        "param2": "<EN desc>"
      },
      "mcp_tool": "<original-mcp-tool-if-applicable>"
    }
  ]
}
```
