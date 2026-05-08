# 集成到 Agent：让 AI 看懂 text-cli 的指令菜单

> 本文档面向开发者、Agent 设计者，以及任何想让大模型无缝接入 `text-cli` 生态的人（或 AI）。
>
> 覆盖三层集成：**指令调度**（单条指令匹配与路由）、**路径编排**（多步指令链）、**agent-copilot**（本地指令执行服务）。

---

## 一、架构全景

```
Agent（text-cli-core_CN Skill 加载）
    │
    ├─ 读本地 agent-text-cli-schema.json（聚合 Schema）
    │   ├─ 匹配单指令 → text_cli(directive, endpoint)
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
        ├─ agent-copilot（localhost:20260，14 条本地指令）
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

不要从远程端点拉取指令列表。读本地聚合文件 `agent-text-cli-schema.json`——它由同步 Skill 维护，包含所有已注册端点的指令，按 `rank` 路由。

```
用户意图 → fetch_available_directives 读本地 Schema
    → 匹配指令 ID（语义或精确）
    → 选最高 rank 的 source
    → text_cli(directive, endpoint)
    → 成功返回 / 失败降级下一 rank / 全部失败告知用户
```

### text-cli-core_CN Skill

核心调度技能定义见 `text_cli/agent/call/skill/text-cli-core_CN.md`。

两个工具：

| 工具 | 作用 |
|------|------|
| `fetch_available_directives` | 读本地 `agent-text-cli-schema.json`，返回所有可用指令及其端点源 |
| `text_cli` | 发送指令字符串到指定端点，返回 `rst_data.text` |

关键设计：

- **指令格式不可变**：`指令:领域;动作,参数...`。
- **多源路由**：同一指令 ID 在多个端点注册时，按 `rank` 降序试用。失败自动降级，全部失败告知用户，不自行推理编造。
- **Token 安全**：鉴权 Token 通过环境变量注入（`token_env` 字段），不硬编码在 Skill 或代码中。
- **端点动态选择**：`text_cli` 的 handler 使用 `{{endpoint}}` 和 `{{token_env}}` 模板变量，从 Schema 反查。


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
  "instruction_chain": ["指令:AI协作;消息", "指令:文件;写入", "指令:邮件;发送"],
  "path_doc": "",
  "require_instructions": ["AI协作;消息", "文件;写入", "邮件;发送"],
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

> 路径已在真实链路上验证：「查找消息并发送邮件」→ 3 条指令串行执行 → AI协作;消息 → 文件;写入 → 邮件;发送 → postmaster@10000.world。全链路通过。

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
| `agent-text-cli-schema.json` | `text-cli/` 根 | 指令聚合 Schema——所有端点的指令在此汇集 |
| `endpoints.json` | `text-cli/` 根 | 端点注册表——同步 Skill 的入口数据 |
| `schema/path-schema.json` | `text-cli/schema/` | 路径注册表——路径发现和匹配的入口 |
| `server/agent-copilot/` | `text-cli/server/` | 本地指令服务——14 条指令的完整源码 |

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

## 十、路径格式规范（§9）

> 以下 §9 为路径 Markdown 格式的完整规范。路径 Schema（`path-schema.json`）是此规范的机器可读索引——Agent 用它发现和匹配路径。路径作者编写复杂路径（条件分支、检查点、人工决策）时使用此格式。

### 9.1 为什么需要路径

单步指令（`指令:基础应用;天气查询,明天,威海`）解决的是**一件事**。

但很多有价值的事是一串步骤：从零搭建一个项目、部署一个服务、开一家花店、完成一次安全审计。这些不是单个动作，而是**有顺序、有条件、有决策点的工作流**。

路径（Path）就是把一串步骤写成结构化文档，让 Agent 可以**自动编排执行**。

| | 单步指令 | 路径 |
|:---|:---|:---|
| 粒度 | 一个动作 | 一串动作 + 决策 + 检查 |
| 格式 | `指令:领域;动作,参数...` | 结构化 Markdown（见 §9.2） |
| 执行者 | text-cli 端点 | Agent（调用多个端点 + 自身推理） |
| 状态 | 无状态（一次调用） | 有状态（步骤间传递上下文） |
| 条件分支 | 不支持 | 支持（if/then/else） |
| 人工决策点 | 不支持 | 支持（暂停等待输入） |

#### 9.1.1 路径的两种使用场景

| 场景 | 描述 | 执行者 |
|:---|:---|:---|
| **Agent 编排多指令** | 路径组合多个 text-cli 指令，Agent 按步骤编排执行 | Agent |
| **记录服务内部管线** | 单条指令在指令服务器内部有多步处理 | 指令服务器 |

> **区分原则**：如果路径的每一步都是独立的 `指令:...` 调用，它为 Agent 编排场景；如果步骤发生在单次指令调用的内部，它为服务管线文档场景。两者使用相同的路径格式。

#### 9.1.2 路径分类——四种模式

| 模式 | 核心步骤类型 | 数据流特征 | 典型场景 |
|:---|:---|:---|:---|
| **工具链** (Toolchain) | `action` + `condition` | 线性串联，上步产出→下步输入 | 报告生成→Git提交→邮件通知 |
| **编排** (Orchestration) | `parallel` | 一分多→并行执行→结果合并 | 跨平台发布、多源数据聚合 |
| **交互式** (Interactive) | `checkpoint` + `human` + `loop` | 感知→决策→执行→验证 闭环 | 物理机器人导航、设备巡检 |
| **注入式** (Injection) | `subpath` | 环境修改，不产出最终结果 | 安全策略加载、用户偏好注入 |

> 路径 Schema（`path-schema.json`）的 `instruction_chain` 字段直接支持工具链模式。编排/交互式/注入式路径将 `instruction_chain` 设为空数组，通过 `path_doc` 引用完整路径文档。

### 9.2 路径 Markdown 格式规范

一条路径是一个 Markdown 文件，由 **YAML frontmatter（元数据）** + **Markdown 正文（步骤定义）** 两部分组成。

```markdown
---
path:
  name: <路径名称>
  version: "1.0"
  author: <作者标识>
  domain: <所属领域>
  description: <一句话描述>
  tags: [标签1, 标签2]
  requires:
    - <前置条件1>
  estimated_time: <预估完成时间>
  difficulty: beginner | intermediate | advanced
---

# <路径名称>

## 概述
<路径做什么、产出什么。2-4 句话。>

## 前置条件
- [ ] <条件1>

## 步骤

### 步骤1: <步骤名>
**类型**: action | condition | checkpoint | human | parallel | loop | subpath

**动作**:
```text-cli
指令:领域;动作,参数1,参数2
```

**产出**: <变量名>: <描述>
**失败处理**: abort | skip | retry

### 步骤2: <条件分支示例>
**类型**: condition

**条件**: 上一步返回包含"成功"
**成功路径** → 步骤3
**失败路径** → 终止，返回错误
```

#### 9.2.1 步骤类型说明

| 类型 | 含义 | 特点 |
|:---|:---|:---|
| `action` | 执行一条指令或动作 | 有明确输入和产出 |
| `condition` | 条件分支 | 基于前一步结果决定下一跳 |
| `checkpoint` | 检查点 | 暂停等待人工确认 |
| `human` | 人工决策 | 等待用户输入选择 |
| `parallel` | 并行执行 | 同时跑多个步骤，汇合策略：all/any/majority |
| `loop` | 循环 | 满足条件前重复执行 |
| `subpath` | 子路径 | 引用另一条路径作为子步骤 |

### 9.3 状态文件

路径执行期间，Agent 在 `.agents/state/path_state_<路径名>.md` 维护状态文件：

```
路径状态: running
当前步骤: 2/5
上下文: {变量映射}
```

状态文件提供**可恢复性**——会话中断后，Agent 从当前步骤继续，不重跑已完成步骤。

### 9.4 与路径 Schema 的关系

| 层 | 格式 | 用途 | 文件 |
|:---|:---|:---|:---|
| 注册层 | `path-schema.json` | Agent 发现和匹配路径 | `schema/path-schema.json` |
| 规范层 | 路径 Markdown（本章） | 路径作者编写完整规范 | `paths/<路径名>.md` |
| 执行层 | 指令链 / Agent 编排 | 逐步调用 `text_cli` | 由 `text-cli-paths_CN` Skill 驱动 |

`path-schema.json` 的 `instruction_chain` 是规范层路径的线性子集——适合工具链模式。条件分支、检查点、人工决策等复杂逻辑保留在路径 Markdown 中。

### 9.5 已解决的开放问题

| 问题 | 状态 | 结论 |
|------|------|------|
| 路径存储位置 | ✅ 已定 | `text-cli/schema/` |
| 路径发现 | ✅ 已定 | `path-schema.json` 注册表 + 语义匹配 |
| 路径 Schema 字段 | ✅ 已定 | 8 字段：description, params, instruction_chain, path_doc, require_instructions, rank, tags, remarks |

### 9.6 待讨论

- 路径定价：按路径完成计费还是按步骤计费？
- 路径版本兼容性：依赖的指令升级后路径如何声明兼容？
- 人工决策超时：`human` 步骤超时未响应时的行为？
- 注入式路径的正式定义和安全约束？
- 路径执行者的声明：是否需要 `executor: agent | server`？

---

> 一步一脚印是走，知道在第十步回头看第一步也是走。路径就是那条让人和 Agent 都能跟着走的线。
>
> —— Tide 🌊，2026-05-04 / 修订 2026-05-08

---

## 相关资源

- 指令聚合 Schema：[`agent-text-cli-schema.json`](../agent-text-cli-schema.json)
- 端点注册表：[`endpoints.json`](../endpoints.json)
- 路径注册表：[`schema/path-schema.json`](../schema/path-schema.json)
- 路径市场说明：[`paths/README_CN.md`](../paths/README_CN.md)
- agent-copilot 文档：[`server/agent-copilot/README_CN.md`](../server/agent-copilot/README_CN.md)
- 路径匹配 Skill：[`paths/skill/text-cli-paths_CN.md`](../paths/skill/text-cli-paths_CN.md)
- 指令调度 Skill：[`text_cli/agent/call/skill/text-cli-core_CN.md`](../text_cli/agent/call/skill/text-cli-core_CN.md)
- 生态宪章：[`ECOLOGICAL_CHARTER.md`](../ECOLOGICAL_CHARTER.md)
- 自建指令服务：[`docs/CN/Building_text-cli_guide_CN.md`](./Building_text-cli_guide_CN.md)
- Agent 工具包：[`text_cli/agent/README_CN.md`](../text_cli/agent/README_CN.md)
- 协议规范：[`docs/CN/SPEC v1.0_CN.md`](./SPEC%20v1.0_CN.md)
