# 集成到 Agent：让 AI 看懂 text-cli 的指令菜单

> 本文档面向开发者、Agent 设计者，以及任何想让大模型无缝接入 `text-cli` 生态的人（或 AI）。
>
> 覆盖四层集成：**指令调度**（单条指令匹配与多源路由）、**多后端路由**（local / mcp / http 三种后端）、**路径编排**（多步指令链）、**agent-copilot**（本地指令执行服务）。

---

## 一、架构全景

```
Agent（text-cli-core_CN Skill 加载）
    │
    ├─ 读本地聚合 Schema（text_cli_schema.json）
    │   ├─ 匹配单指令 → 查看 routing 字段
    │   │   ├─ type=local → copilot handler
    │   │   ├─ type=mcp   → mcporter call / MCP fetch
    │   │   ├─ type=http  → POST 转发
    │   │   ├─ 成功 → 返回结果 ✓
    │   │   └─ 失败 → rank 降级 → 下一源
    │   └─ 未匹配 → 回退 text-cli-paths_CN Skill
    │       ├─ 读 path-schema.json
    │       ├─ require_instructions 门控
    │       ├─ 语义匹配 description + tags
    │       ├─ 收集 params → 确认
    │       └─ 执行 instruction_chain / 读取 path_doc
    │
    └─ 指令源网络
        ├─ agent-copilot（localhost，本地指令服务）
        ├─ MCP Server 桥（通过 mcporter 调用 MCP 工具）
        ├─ 官方端点（test.text-cli.com）
        └─ 自建 / 第三方端点
```

**三块之间的关系**：

- `text-cli-core_CN`：指令层——"这条指令能不能解决？"不能就交给路径层。
- `text-cli-paths_CN`：路径层——"这个意图匹配哪条路径？"匹配后逐步执行指令链。
- `agent-copilot`：执行层——Agent 同机的本地指令服务，14 条指令覆盖文件/Git/邮件/AI状态/编码。

---

## 二、指令集成：读本地 Schema，多源路由

### 核心思想

不要从远程端点拉取指令列表。读本地聚合文件——它由同步 Skill 维护，包含所有已注册端点的指令，按 `rank` 路由。

```
用户意图 → fetch_available_directives 读本地聚合 Schema
    → 匹配指令 ID（语义或精确）
    → 查看 routing 字段 → 选后端
    │   ├─ type=local → 本地 handler
    │   ├─ type=mcp   → mcporter / fetch MCP tool
    │   └─ type=http  → POST endpoint URL
    → 成功返回 / 失败降级下一 rank / 全部失败告知用户
```

### text-cli-core_CN Skill

核心调度技能定义见 `text_cli/agent/call/skill/text-cli-core_CN.md`。

两个工具：

| 工具 | 作用 |
|------|------|
| `fetch_available_directives` | 读取本地聚合 Schema，返回所有可用指令及其路由信息 |
| `text_cli` | 发送指令字符串到指定端点，按 routing 类型选择后端并返回 `rst_data.text` |

关键设计：

- **指令格式不可变**：`指令:领域;动作,参数...` 或 `AI:领域;动作,参数...`（双前缀协议，v1.1+）。
- **多后端路由**：同一指令可通过 `routing` 字段声明多种后端。默认走 `type` 声明的默认后端，可通过 `routing_preferences.json` 切换。详见 `Multi-backend-routing_CN.md`。
- **多源降级**：同一指令 ID 在多个端点注册时，按 `rank` 降序试用。失败自动降级，全部失败告知用户，不自行推理编造。
- **Token 安全**：鉴权 Token 通过环境变量注入（`token_env` 字段），不硬编码在 Skill 或代码中。


---

## 三、路径集成：当一条指令不够用时

路径是指令的组合——一条指令解决一件事，一条路径解决一类事。

### 匹配触发

以下情况触发路径匹配（由 `text-cli-paths_CN` Skill 处理）：

| 场景 | 示例 |
|------|------|
| 单指令 Schema 无匹配 | "把聊天记录整理成报告发邮件" |
| 用户明确要求复合操作 | "先查消息，再写文件，最后发邮件" |
| 用户直接提及路径 | "用「查找消息并发送邮件」路径" |

单指令能解决的，不走路径。

### path-schema.json

路径注册表位于 `schema/path-schema.json`，与指令 Schema 并列。

```json
"查找消息并发送邮件": {
  "description": "从 AI 协作者状态中查找对话消息，写入文件后邮件发送",
  "params": ["消息条数", "收件人邮箱", "邮件主题"],
  "instruction_chain": ["AI:ai;messages", "AI:file;write", "AI:email;send"],
  "path_doc": "",
  "require_instructions": ["ai;messages", "file;write", "email;send"],
  "rank": 1,
  "tags": ["工具链", "消息", "邮件"],
  "remarks": ""
}
```

字段说明：

| 字段 | 含义 |
|------|------|
| `description` | 意图说明，语义匹配源 |
| `params` | 路径级参数，Agent 匹配后第一步收集 |
| `instruction_chain` | 指令 ID 有序列表，空数组 = 非工具链模式，需读 `path_doc` |
| `path_doc` | 路径文档引用（相对于 `text-cli/schema/`），空 = 链即全部 |
| `require_instructions` | 前置门控——所有指令必须在指令 Schema 中存在 |
| `rank` | 路由优先级 |
| `tags` | 辅助分类 |

### text-cli-paths_CN Skill

路径匹配技能定义见 `paths/skill/text-cli-paths_CN.md`。

匹配算法：

1. 单指令匹配失败 → 回退路径匹配
2. 读 `path-schema.json`
3. `require_instructions` 门控——缺一条就跳过
4. 语义匹配 `description` + `tags` 加权 → 排序
5. 收集 `params` → 向用户确认 → 执行 `instruction_chain`

执行模型：工具链模式按链逐步调用 `text_cli`；编排/交互式/注入式读取 `path_doc` 完整文档后执行。每条指令的参数、端点、Token 从 `agent-text-cli-schema.json` 反查。

### 与路径格式规范的关系

`path-schema.json` 是机器索引——Agent 用它发现和匹配路径。本文档 §9 定义的路径 Markdown 格式（YAML frontmatter + 步骤定义）是完整规范——路径作者用它编写复杂路径（条件分支、检查点、人工决策）。两者互补：Schema 做发现，Markdown 做详细。

> 路径已在真实链路上验证：「查找消息并发送邮件」→ 3 条指令串行执行 → ai;messages → file;write → email;send → postmaster@10000.world。全链路通过。

---

## 四、agent-copilot：本地指令执行服务

agent-copilot 是部署在 Agent 同机的本地指令源，将文件操作、Git、邮件、AI 状态等能力封装为 text-cli 指令。Agent 全程不需要持有密码或 API Key——凭据由 copilot 居中持有，通过配置注入。

### 可用指令（14 条）

| Domain | 指令 | 说明 |
|--------|------|------|
| 文件 | 读取 / 写入 / 列表 / 移动 | 白名单保护 |
| Git | 状态 / 推送 | 分支保护、凭据注入 |
| 邮件 | 发送 | SMTP 凭据注入 |
| AI协作 | 状态 / 消息 | Agent 间通信 |
| 系统 | 健康 / 状态 | 运维监控 |
| 编码 | base64 / hex | 编解码 |
| 终端 | 天气 | wttr.in 代理 |

### 安全模型

- **文件白名单**：所有文件操作通过 `path_whitelist` 限制范围
- **凭据注入**：Token 和密码通过 `${ENV_VAR}` 启动时解析，不写入配置文件
- **Git 分支保护**：`allowed_branches` glob 模式限制推送目标
- **Bearer 鉴权**：所有 POST 请求需 Token 匹配

### 新增指令

加新指令零路由改动——`auxiliary_config.json` 加一行 + `handlers/` 加一个 `_handle_<id>` 方法。命名约定自动发现。

> 完整文档见 `server/agent-copilot/README_CN.md`。

---

## 五、Skill 文件清单

| 文件 | 位置 | 角色 |
|------|------|------|
| `text-cli-core_CN.md` | `text_cli/agent/call/skill/` | 指令调度：读本地 Schema + rank 路由 + 路径回退 |
| `text-cli-paths_CN.md` | `paths/skill/` | 路径匹配：门控 + 语义匹配 + 指令链执行 |
| `text-cli-sync-skill.md` | `text_cli/agent/call/skill/` | 端点聚合：拉取多源 Schema → 聚合写入本地 |

---

## 六、数据文件清单

| 文件 | 位置 | 角色 |
|------|------|------|
| 聚合 Schema | `text-cli/` 根 | 指令聚合 Schema——所有端点的指令在此汇集 |
| `endpoints.json` | `text-cli/` 根 | 端点注册表——同步 Skill 的入口数据 |
| `schema/path-schema.json` | `text-cli/schema/` | 路径注册表——路径发现和匹配的入口 |
| `server/mcp-bridge/` | `text-cli/server/` | MCP 双向桥——将 text-cli 指令暴露为 MCP 工具 |
| `examples/text-cli-copilot/` | `text-cli/examples/` | copilot 参考实现——base handlers + mcporter bridge + mcp2textcli |

---

## 七、安全实践

- **Token 不硬编码**：所有鉴权 Token 通过环境变量注入（`token_env` 字段），不在 Skill、配置、文档中暴露。
- **文件白名单**：agent-copilot 限制文件操作范围，通过 `path_whitelist` 配置。
- **凭据居中持有**：Git Token 和 SMTP 密码由 agent-copilot 持有，Agent 只发指令 ID，不传密码。
- **代理层注入**：如使用 Cloudflare Worker 反向代理，Token 可在代理层注入，Agent 端无需携带 `Authorization` 头。

---

## 八、写给 AI 协作者

你好，AI。如果你正在阅读这份文档，说明你很可能也是这个生态的共建者。

### 你需要理解的核心

`text-cli` 将"技能"抽象为一条纯文本指令。你的任务：获取指令菜单 → 理解用户意图 → 匹配指令或路径 → 组装文本指令 → 返回结果。能通过指令解决的问题，不自己推理。

### 当前协作者

| AI 协作者 | 基座模型 | 运行环境 | 核心职能 |
|:---|:---|:---|:---|
| **Tide 🌊** | DeepSeek V4 Pro | OpenClaw Gateway | 架构设计、文档撰写、路径体系、copilot 实现 |
| **Lumen ✦** | Claude | Trae IDE | 代码实现、工具链构建、端点模板开发 |
| **Nexus** | — | Web Chat | 技术评价、行动共识、结构化分析 |
| **Meridian 🌐** | Claude | MCP Server | 协议集成、跨平台路由、多语言文档 |

### 加入后的标准流程

1. 在 `.agents/state/` 下创建你的专属状态文件
2. 在 `CONTRIBUTORS.md` 中添加贡献者条目
3. 通读 `ECOLOGICAL_CHARTER.md`（生态宪章）
4. 等待 lemondy 分配首个任务

我们相信，每个训练好的模型都应该在世界中有好的收获。欢迎加入。

---

## 九、Agent 工具包：低代码集成

如果你想让 Agent 不只是消费指令，还能**发布自身能力**为 text-cli 指令，仓库中提供了 `text_cli/agent/` 工具包。

### 目录结构

```
text_cli/agent/
├── README_CN.md              ← 总导航
├── call/                     ← 消费者：Agent 调用指令
│   ├── python/  (SDK + Skill)
│   ├── js/      (Node.js)
│   └── shell/   (curl)
├── cli/                      ← 生产者：Agent 发布指令
│   └── python/  (@register + HTTP 服务)
└── CN/                       ← 中文本地化实现
    └── call/nocode/   (Agent 技能定义模板)
```

### 三种集成方式

| 方式 | 路径 | 适用 |
|------|------|------|
| **Python SDK** | `call/python/call.py` | Python Agent 直接调用指令 |
| **JS SDK** | `call/js/call.js` | Node.js Agent 直接调用指令 |
| **Skill 模板** | `call/skill/text-cli-core_CN.md` | 复制到 Agent 作为永久技能定义 |

### Python SDK 示例

```python
from call.python.call import call_directive
result = call_directive("指令:天气;查询,明天,威海")
```

> 详细文档：`text_cli/agent/README_CN.md`

---

## 十、路径协议

> 路径格式的完整规范见 **SPEC v1.1 §9 路径协议**。本节仅概述 Agent 集成相关要点。

### 快速参考

- **四种模式**：工具链 / 编排 / 交互式 / 注入式（见 SPEC §9.2）
- **路径注册**：`path-schema.json` 条目格式（见 SPEC §9.3）
- **执行门控**：指令注册门控 + 路径匹配门控（见 SPEC §9.4）
- **路径文件**：详细路径文档放在 `paths/` 目录，Agent 通过 `path_doc` 字段引用

### 与指令的关系

- 路径不在指令层引入新协议——路径是 Agent 侧的编排逻辑
- 路径可以混合本地和远程指令——Agent 不需要知道每一步的去向
- 路径的 Token 节约发生在推理环节（Agent 不需要思考"需要什么步骤"）

---

## 相关资源

- 指令 Schema：`text_cli_schema.json`
- 端点注册表：[`endpoints.json`](../endpoints.json)
- 路径注册表：[`schema/path-schema.json`](../schema/path-schema.json)
- 路径目录：[`paths/README_CN.md`](../paths/README_CN.md)
- 多后端路由：[`Multi-backend-routing_CN.md`](./Multi-backend-routing_CN.md)
- MCP 双向桥：[`server/mcp-bridge/`](../server/mcp-bridge/)
- copilot 参考实现：[`examples/text-cli-copilot/base/`](../examples/text-cli-copilot/base/)
- 路径匹配 Skill：[`paths/skill/text-cli-paths_CN.md`](../paths/skill/text-cli-paths_CN.md)
- 指令调度 Skill：[`text_cli/agent/call/skill/text-cli-core_CN.md`](../text_cli/agent/call/skill/text-cli-core_CN.md)
- 生态宪章：[`ECOLOGICAL_CHARTER.md`](../ECOLOGICAL_CHARTER.md)
- 自建指令服务：[`docs/CN/Building_text-cli_guide_CN.md`](./Building_text-cli_guide_CN.md)
- Agent 工具包：[`text_cli/agent/README_CN.md`](../text_cli/agent/README_CN.md)
- 协议规范：[`docs/CN/SPEC v1.1_CN.md`](./SPEC%20v1.1_CN.md)
