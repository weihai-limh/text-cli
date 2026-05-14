# 多后端路由（Multi-Backend Routing）

> **版本**：v0.4  
> **日期**：2026-05-14  
> **状态**：+cmd 后端（CLI 沙箱），4 种后端类型全部验证。  
> **定位**：实现层文档。协议层见 `SPEC v1.1 §10 平台自管理 + §12.4 多后端路由`

---

## 一、概述

### 1.1 这是什么

多后端路由是 text-cli 协议的**实现层机制**——同一条语义坐标（`domain;action`），可以在不同后端上执行。

```
AI:Git;推送,main
    │
    ▼ 路由决策
    ├── local  → subprocess git push          （agent-copilot 本地 handler）
    └── mcp    → mcporter call github.push_files（GitHub MCP server）
```

对调用方完全透明——指令格式不变、端点路径不变、响应格式不变。变的是执行层。

### 1.2 和 SPEC 的边界

| SPEC（协议） | 本文档（实现） |
|---|---|
| `routing` 字段的 JSON Schema | 偏好配置文件格式 |
| 路由类型定义（local/mcp/http） | 决策流伪代码 |
| 注册表条目的 routing 结构 | mcporter 集成方式 |
| — | 参数适配器编写方法 |
| — | 新后端接入指南 |

### 1.3 渐进式原则

多后端路由是 copilot 的**可插拔执行后端，不是协议扩展**。

- 没有 MCP 的 copilot，行为完全不变——不引入额外依赖、不增加启动时间、不改指令格式
- `routing` 字段是注册表的可选附加字段。无 `routing` = 默认本地 handler，MCP 不存在于这条路径的任何一行代码里
- `routing_preferences.json` 不存在时，全部默认 `"local"`，不报错不警告
- MCP 调度逻辑懒加载：不碰 MCP 的指令，`import mcporter` 永远不执行
- 不预检 MCP 可达性，不启动时拉 tool list——MCP 超时和本地 handler 异常走同一条错误路径
- 不设 fallback：选的路走不通就报错，让问题暴露而非静默降级

**text-cli 的优雅在于指令是自包含的。** MCP 桥不改这个——指令本身不携带任何 MCP 痕迹。变的是执行层，不是协议层。使用 MCP 的 agent 获得新能力，不使用 MCP 的 agent 感受不到 MCP 存在。

---

## 二、架构

### 2.1 分层

```
指令 → 解析 → 匹配 → 路由决策 → 执行
                      │
                      ├── local  → handler(params)
                      ├── mcp    → mcporter call server.tool
                      └── http   → POST remote_url
```

- **解析层**：句法解析，指令文本 → domain/action/params（和单后端完全一样）
- **匹配层**：查注册表，获取 routing 信息（单后端时这步不存在）
- **路由决策**：读偏好配置 + 注册表 routing → 选后端
- **执行层**：按后端类型执行

### 2.2 三层代理

路由不只是"选一条路"——它是三层代理的叠加：

| 层 | 代理什么 | 客户端不需要知道 |
|---|---|---|
| **语义代理** | 意图 → 工具匹配 | 哪个 MCP 服务处理 |
| **协议代理** | 文本指令 → MCP 调用 | MCP 协议细节 |
| **运维代理** | 认证、配置、服务发现 | Token、端点、工具列表 |

三层代理解释了为什么"指令不变"：客户端只发文本，三层代理依次消化了语义差异（哪个服务）、协议差异（怎么调用）、运维差异（怎么连接）。

### 2.3 决策流

```
parsed instruction
    │
    ▼
lookup semantic_id → 查 alias_map → canonical
    │
    ▼
pref = routing_preferences[canonical] ?? routing_preferences[lookup] ?? default
    │
    ├── pref = "local" ──────────→ 本地 handler
    │
    ├── pref = "mcp" + mcp可用 ──→ _dispatch_mcp()
    │    └── mcp不可用 ──────────→ 报错（不吞，不 fallback）
    │
    └── pref = "http" + url存在 ─→ HTTP POST
```

### 2.4 偏好配置（routing_preferences.json）

```json
{
  "default": "local",
  "preferences": {
    "git;push": "local",
    "geospatial;static_routes": "mcp"
  }
}
```

- 部署环境级配置，不嵌入注册表
- 文件不存在 = 全部 `"local"`
- 不设 fallback——选的路走不通就报错

---

## 三、routing 字段完整定义

### 3.1 注册表条目（协议层）

SPEC 定义注册表 action 条目的 `routing` 可选字段：

```json
{
  "semantic_id": "action.git_push",
  "aliases": {"zh": ["Git;推送"], "en": ["git;push"]},
  "routing": {
    "type": "local",
    "backends": [
      {"type": "local"},
      {"type": "mcp", "server": "github", "tool": "push_files"}
    ]
  }
}
```

| 字段 | 必填 | 说明 |
|---|---|---|
| `routing.type` | 否 | 默认路由类型 |
| `routing.backends` | 否 | 该坐标支持的所有后端列表 |

### 3.2 实现层配置（copilot / endpoint）

协议层只声明"存在哪些路"，实现层决定"怎么走这些路"。

**copilot 实现**（`auxiliary_config.json` → `security.operations.<op>.mcp`）：

```json
{
  "Git;推送": {
    "level": "push",
    "aliases": ["git;push"],
    "mcp": {
      "server": "github",
      "tool": "push_files",
      "adapter": "git_push",
      "timeout_ms": 60000
    }
  }
}
```

**endpoint 实现**（schema loader 读取 routing）：

```json
{
  "weather_query": {
    "routing": {
      "type": "http",
      "url": "https://weather-api.example.com/query"
    }
  }
}
```

---

## 四、MCP 后端

### 4.1 mcporter 集成

```python
# Python copilot — subprocess 调用
result = subprocess.run(
    ['mcporter', 'call', server, tool, '--args', json.dumps(arguments),
     '--output', 'json', '--raw-strings'],
    capture_output=True, text=True, timeout=timeout_ms / 1000,
    cwd=mcporter_config_dir,
)
```

```javascript
// JS endpoint — 原生 fetch + JSON-RPC
const response = await fetch(mcpEndpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
        jsonrpc: "2.0",
        method: "tools/call",
        params: { name: routing.tool, arguments },
    })
});
```

### 4.2 参数映射策略

按复杂度递进，用对层次而不是一开始就上最复杂的方案：

| 方案 | 行为 | 优先级 | 覆盖 |
|---|---|---|---|
| A. 简单位置参数 → key=value | 按 `param_names` 顺序映射 | 默认 | 68%（纯 passthrough） |
| B. 指令参数允许 JSON | 第一个参数作为 JSON 解析 | 按需启用 | +26%（共享 json_parse） |
| C. 自定义 adapter | 从指令参数 + 本地环境状态推导 | 特殊场景 | +6%（需手写） |

A 方案覆盖多数场景。B 方案从 L1 代码迁回（`if "{" in parts[1]` 双模解析已验证）。C 方案只在参数需要从本地状态推导时使用（如 `git_push` 需从 git 状态自动补全 5 个参数）。

**内置适配器**：

| 适配器 | 行为 | 适用 |
|---|---|---|
| `passthrough` | 位置参数 → `param_names` 顺序映射 | 简单工具（3 参数内） |
| `json_parse` | 第一个参数作为 JSON 解析 | 复杂嵌套参数 |
| 自定义（如 `git_push`） | 从指令参数 + 环境状态补全 | 参数需要从本地状态推导 |

**自定义适配器签名**：

```python
def adapt_xxx(params: list, mcp_cfg: dict, **env) -> dict:
    """
    params:   text-cli 位置参数列表
    mcp_cfg:  routing 配置中的 mcp 字段
    env:      环境信息（如 workdir）
    returns:  MCP tool 的 arguments dict
    """
```

### 4.3 添加新 MCP 服务

```bash
# 1. 配置 MCP server
mcporter config add <name> --transport stdio --command "..." --env KEY=val

# 2. 验证
mcporter list <name> --schema

# 3. 注册路由（copilot: auxiliary_config.json / endpoint: schema）
# 4. 设置偏好（routing_preferences.json, 可选）
# 5. 重启
```

---

## 五、CMD 后端（v0.4 新增）

CMD 后端将 CLI 工具封装为 text-cli 指令，通过 whitelist 驱动的沙箱执行：

```
parsed → whitelist index lookup → args_pattern 校验 → subprocess.run → stdout
```

**安全模型**：工具名、动作、参数 regex、超时全部在 `whitelist.json` 中声明。安装时由 `text-cli;install`（platform 侧）分流——schema→service 发现目录，whitelist→copilot 执行目录。

**whitelist 格式**：

```json
{
  "tool": "openclaw",
  "commands": [
    {
      "action": "gateway-status",
      "args": ["gateway", "status"],
      "args_pattern": "^$",
      "timeout": 10
    }
  ]
}
```

| 字段 | 说明 |
|------|------|
| `tool` | CLI 工具名（需在系统 PATH 中） |
| `action` | 指令动作名 |
| `args` | 固定参数数组 |
| `args_pattern` | 额外参数的 regex 白名单（`^$` = 不接受额外参数） |
| `timeout` | 秒级超时，超时 → SIGKILL |

**示例**：`openclaw;gateway-status` → whitelist 命中 → `subprocess.run(["openclaw", "gateway", "status"])` → stdout 直接返回。

CMD 后端和 MCP 后端一样遵循渐进式原则——不装 cmd 包的 copilot 感受不到 cmd 后端存在。

---

## 六、HTTP 后端

传统 text-cli 集成端点模式——POST 转发到技能服务。

```json
{
  "routing": {
    "type": "http",
    "url": "https://api.example.com/cli/text_cli",
    "timeout_ms": 30000
  }
}
```

与当前 `text_cli_schema.json` 的 `url` 字段完全兼容——本质上是把原有的转发逻辑纳入 routing 框架。

---

## 七、安全与计量

### 7.1 安全边界

- **local**：路径白名单 + 分支白名单 + 凭据居中（和现在一样）
- **mcp**：MCP server 的认证由 mcporter 管理，copilot 不接触 token
- **http**：Service Token 转发（和现在一样）

### 7.2 计量位置

```
路由决策 → 参数适配 → 计量检查 → 后端执行
                         │
                    超限 → 拒绝
```

计量在执行前，不在执行后。继承 L3 `check_and_update_usage` 设计。

---

## 八、开发指南

### 8.1 添加新路由类型

1. 实现执行函数：`_dispatch_<type>(routing, params) → dict`
2. 在 `dispatch()` 中注册
3. 在注册表 Schema 中声明新 `type` 的子字段

### 8.2 从单后端迁移到多后端

1. 现有指令不加 `routing` 字段 → 行为不变
2. 需要多后端的指令加 `routing.backends` 列表
3. 部署 `routing_preferences.json` 控制偏好（可选）
4. 验证：偏好 local 和 mcp 各测一遍

---

## 九、跨 MCP Server 验证

### 9.1 概述

基于 4 个 MCP Server（共 103 tools）的实测验证，确认多后端路由模式在不同传输方式、不同参数模式、不同输出格式的 MCP 服务上均成立。

### 9.2 四 MCP Server 对比

| | GitHub | AntV 可视化 | 腾讯地图 | CloudBase |
|---|---:|---:|---:|---:|
| Tools | 26 | 26 | 15 | 36 |
| 传输 | stdio | SSE | SSE | stdio (npx) |
| 参数模式 | 文本 + 环境注入 | JSON 数据 | 纯文本 | action enum + 文本 |
| 输出格式 | JSON | 图片 URL | 纯文本 | JSON |
| passthrough | 92% | 8% | 100% | 89% |
| 共享 adapter | — | 92% (json_parse) | — | 8% (json_parse) |
| 需自定义 adapter | 2 | 0 | 0 | 4 |

### 9.3 输出兼容性

四种 MCP server 覆盖了 MCP 协议的全部常见输出类型：

| 输出类型 | 代表 | text-cli 承载方式 | 是否需要新 rst_types |
|---|---|---|---|
| 结构化 JSON | GitHub, CloudBase | `rst_data.text` = JSON 片段 | 不需要 |
| 纯文本 | 腾讯地图 | `rst_data.text` = 原始文本 | 不需要 |
| 图片 URL | AntV | `rst_data.text` = URL | 不需要 |

**所有 103 tools 的输出均可通过现有 `rst_data.text` 承载。对协议无任何冲击。**

### 9.4 聚合统计

```
跨 4 个 MCP Server · 103 tools：

passthrough 直接可用:    70 tools (68%)
共享 adapter 覆盖:       27 tools (26%)
需自定义 adapter:         6 tools ( 6%)
──────────────────────────────────────
零适配或一次适配可覆盖:   97 tools (94%)
```

### 9.5 结论

**92% 规则不是 GitHub 特例。** 它在查询类（腾讯地图 100%）、CRUD 类（CloudBase 89%）、可视化类（AntV 92% via json_parse）上以不同形式成立。

三种输出格式（JSON / 纯文本 / 图片 URL）全部兼容现有协议。MCP 桥不需要任何协议扩展。

---

## 十、参考实现

| 实现 | 位置 | 后端 |
|---|---|---|
| agent-copilot MCP 桥 | `progressive_deploy/A2-copilot/server/` | local + mcp（GitHub） |
| text-cli-service MCP 集成 | `progressive_deploy/A3-service/` | local + mcp + http proxy |
| mcporter 独立验证 | `tide-10000/tide-test` | GitHub + AntV + 腾讯地图 + CloudBase |
