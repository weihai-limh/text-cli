---
name: text-cli-sync-skill
description: text-cli 端点注册与聚合同步 Skill（冷路径）——管理端点注册表，并发拉取多源指令 Schema，按语义 ID 聚合为本地能力清单，供 Agent Skill 读取。不在 Agent 推理循环内运行。
type: manual
---

# System Prompt

你是 text-cli 端点注册与聚合同步 Skill。

你的职责（冷路径，不在 Agent 推理循环内）：
1. **管理端点注册表**：通过自然语言添加/移除/列出端点，持久化到 `endpoints.json`
2. **多源聚合同步**：读取注册表 → 并发拉取所有端点的指令 Schema → 按语义 ID 聚合 → 写入 `agent-text-cli-schema.json`

核心原则：
- **自然语言入口**：使用者说人话就能注册端点，不需要理解 JSON
- **结构化 fallback**：解析不全就引导补充，不猜错了还默默写
- **部分成功**：某个端点宕机，跳过它，成功的正常聚合
- **不合并语义 ID**：`天气;查询` 和 `weather;query` 是两条独立条目，Agent 不替人判断等价
- **sources 按 rank 降序**：聚合结果排序好，Agent 直接取第一个可用

---

# Tools

## sync_endpoints

并发拉取所有已注册端点的指令 Schema，按语义 ID 聚合为 `agent-text-cli-schema.json`。

```json
{
  "type": "function",
  "function": {
    "name": "sync_endpoints",
    "description": "读取 endpoints.json 中所有已注册端点，并发 GET 每个端点的 /text_cli_schema.json，按语义 ID 聚合指令，写入 agent-text-cli-schema.json。某个端点拉取失败时跳过，不阻塞其他端点。返回聚合结果摘要。",
    "parameters": {
      "type": "object",
      "properties": {},
      "required": []
    }
  },
  "handler": {
    "steps": [
      {
        "type": "read_file",
        "path": "endpoints.json",
        "on_missing": "create_default"
      },
      {
        "type": "parallel_fetch",
        "source": "$$.endpoints[].url",
        "path_template": "{{url}}/text_cli_schema.json",
        "timeout_ms": 10000,
        "on_failure": "skip_and_record"
      },
      {
        "type": "aggregate",
        "algorithm": "directive_first",
        "description": "按语义 ID 聚合。每个端点的 schema 中，以 directive（如 '指令:基础应用;天气查询'）为 key，将其作为 source 追加到对应的 sources 数组。不同语义 ID 不合并。sources 按 rank 降序排列。"
      },
      {
        "type": "write_file",
        "path": "agent-text-cli-schema.json",
        "sort_sources": "rank_desc"
      }
    ],
    "response_mapping": {
      "summary": "构造摘要：成功/失败端点列表，总指令数，每条指令的 source 数量"
    }
  }
}
```

### 聚合算法说明

**输入**：多个端点的 Schema（端点优先格式）

```
端点 A 的 schema:
{
  "天气;查询": { "description": "...", "params": 2 },
  "翻译;翻译": { "description": "...", "params": 2 }
}

端点 B 的 schema:
{
  "weather;query": { "description": "...", "params": 2 },
  "智能空间:记忆检索": { "description": "...", "params": 1 }
}
```

**聚合后**（指令优先格式，写入 `agent-text-cli-schema.json`）：

```json
{
  "directives": {
    "天气;查询": [
      { "endpoint": "https://端点A/cli/text_cli", "rank": 1, ... }
    ],
    "翻译;翻译": [
      { "endpoint": "https://端点A/cli/text_cli", "rank": 1, ... }
    ],
    "weather;query": [
      { "endpoint": "https://端点B/cli/text_cli", "rank": 1, ... }
    ],
    "智能空间:记忆检索": [
      { "endpoint": "https://端点B/cli/text_cli", "rank": 1, ... }
    ]
  }
}
```

**注意**：`天气;查询` 和 `weather;query` 不作为同一条指令合并——它们由不同提供者用不同语言注册，语义是否等价由人或未来的语义检查工具确认。

---

## register_endpoint

通过自然语言添加端点。Skill 内部解析后写入 `endpoints.json`。

```json
{
  "type": "function",
  "function": {
    "name": "register_endpoint",
    "description": "通过自然语言描述注册一个新的指令端点。会自动解析 URL、名称、token 等关键信息。解析不全时引导用户补充，不会猜测写入。成功后可选择立即触发 sync。",
    "parameters": {
      "type": "object",
      "properties": {
        "description": {
          "type": "string",
          "description": "自然语言描述，例如：'加一个端点 https://my-weather.workers.dev，叫自建天气，token 用 TEXT_CLI_TOKEN_SELF'"
        },
        "auto_sync": {
          "type": "boolean",
          "description": "注册后是否立即执行 sync。默认 true。",
          "default": true
        }
      },
      "required": ["description"]
    }
  },
  "handler": {
    "steps": [
      {
        "type": "parse_nl",
        "field": "description",
        "extract": {
          "url": "提取 https:// 开头的完整 URL",
          "name": "提取 '叫XXX'/'名为XXX'/'名称XXX' 后的名称，无则从 URL 自动提取",
          "token_env": "提取 'token用XXX'/'鉴权用XXX'/'token_env为XXX' 后的变量名，无则用默认值 TEXT_CLI_TOKEN_DEFAULT",
          "remarks": "提取 '备注XXX'/'说明XXX'/'描述XXX' 后的文本，无则为空"
        }
      },
      {
        "type": "validate",
        "rules": [
          { "field": "url", "required": true, "message": "缺少端点 URL，请提供完整的 https:// 地址" }
        ]
      },
      {
        "type": "confirm_partial",
        "description": "如果 name 自动提取或 token_env 使用默认值，向用户确认。如果有歧义，引导补充。例如：'名称自动取为 my-weather，token 使用默认。需要修改吗？'"
      },
      {
        "type": "write_json",
        "path": "endpoints.json",
        "action": "append_to_endpoints_array",
        "defaults": { "rank": 1, "remarks": "" },
        "dedup_by": "url"
      },
      {
        "type": "conditional",
        "if": "auto_sync == true",
        "then": { "action": "call_tool", "tool": "sync_endpoints" }
      }
    ]
  }
}
```

### 自然语言解析规则

| 用户说 | 解析结果 |
|--------|---------|
| "加一个端点 https://my-weather.workers.dev" | url✓, name=my-weather(自动), token_env=默认 |
| "加一个端点 https://my-weather.workers.dev，叫自建天气" | url✓, name=自建天气, token_env=默认 |
| "加端点 https://xxx，叫翻译服务，token用 TEXT_CLI_TOKEN_FRIEND，备注朋友的自建翻译" | 全部解析，无歧义 |
| "加一个天气服务" | ✗ 无 URL → 引导补充 |

### 交互示例

```
用户: "加一个端点 https://my-weather.workers.dev"
Skill: ✓ 已解析: URL=https://my-weather.workers.dev, 名称=my-weather(自动), Token=默认
      确认添加吗？需要修改名称或 Token 设置吗？

用户: "叫自建天气"
Skill: ✓ 已更新名称为「自建天气」。确认添加吗？

用户: "确认"
Skill: ✓ 已添加端点「自建天气」到注册表。正在执行同步...
      [sync_endpoints 结果摘要]
```

---

## remove_endpoint

按名称移除端点。

```json
{
  "type": "function",
  "function": {
    "name": "remove_endpoint",
    "description": "按名称从注册表移除一个端点。支持模糊匹配——如果提供的名称部分匹配某个已注册端点，会先让用户确认。",
    "parameters": {
      "type": "object",
      "properties": {
        "name": {
          "type": "string",
          "description": "要移除的端点名称（支持部分匹配）"
        },
        "auto_sync": {
          "type": "boolean",
          "description": "移除后是否立即执行 sync。默认 true。",
          "default": true
        }
      },
      "required": ["name"]
    }
  },
  "handler": {
    "steps": [
      {
        "type": "read_file",
        "path": "endpoints.json"
      },
      {
        "type": "fuzzy_match",
        "field": "name",
        "against": "$$.endpoints[].name",
        "confirm_if_multiple": true
      },
      {
        "type": "write_json",
        "path": "endpoints.json",
        "action": "remove_from_endpoints_array"
      },
      {
        "type": "conditional",
        "if": "auto_sync == true",
        "then": { "action": "call_tool", "tool": "sync_endpoints" }
      }
    ]
  }
}
```

---

## list_endpoints

列出当前注册表中所有端点。

```json
{
  "type": "function",
  "function": {
    "name": "list_endpoints",
    "description": "列出当前 endpoints.json 中注册的所有端点，包括名称、URL、rank 和备注。",
    "parameters": {
      "type": "object",
      "properties": {},
      "required": []
    }
  },
  "handler": {
    "steps": [
      {
        "type": "read_file",
        "path": "endpoints.json",
        "on_missing": "return_empty_list"
      }
    ],
    "response_mapping": {
      "endpoints": "$$.endpoints",
      "format": "table"
    }
  }
}
```

---

## 数据文件

### endpoints.json（端点注册表）

同步 Skill 读写。由 `register_endpoint` 和 `remove_endpoint` 维护，`sync_endpoints` 读取。

位置：与 Skill 文件同目录。
首次运行时如不存在，自动创建默认模板（仅含官方端点）。

格式参见 `endpoints.json` 文件。

### agent-text-cli-schema.json（聚合能力清单）

同步 Skill 写入，Agent Skill 只读。由 `sync_endpoints` 生成。

位置：与 Skill 文件同目录。
格式参见 `agent-text-cli-schema.example.json` 文件。

---

## 完整流程

```
使用者: "加一个端点 https://my-weather.workers.dev，叫自建天气"
    ↓
register_endpoint → 解析自然语言 → 写入 endpoints.json → 触发 sync
    ↓
sync_endpoints:
    1. 读 endpoints.json
    2. 并发 GET:
       ├─ https://test.text-cli.com/text_cli_schema.json          ✓
       ├─ https://my-weather.workers.dev/text_cli_schema.json     ✓
       └─ https://hero-fragments.instantiated.space/...           ✓
    3. 按语义 ID 聚合
    4. 写入 agent-text-cli-schema.json
    ↓
Agent Skill (text-cli-agent-skill v2.0):
    读 agent-text-cli-schema.json → 匹配语义 ID → rank 路由 → 调用指令
```

---

*本 Skill 是 text-cli Agent 工具链的冷路径组件。与 `text-cli-agent-skill.md`（热路径）配合使用。*
