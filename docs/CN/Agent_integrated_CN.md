# 集成到 Agent：让 AI 看懂 text-cli 的"技能菜单"

本文档面向开发者、Agent 设计者，以及任何想让大模型无缝接入 `text-cli` 生态的人（或 AI）。

你将学习到如何通过两个简单的工具，让任何支持 Function Calling 的 Agent 自动发现所有可用指令，并以极低的 Token 成本完成真实世界的任务。

> **📌 v2.0（2026-05-07）**：本文档已升级为多源聚合架构。Skill 文件位于 `text_cli/agent/CN/call/nocode/`——`text-cli-agent-skill.md`（热路径）和 `text-cli-sync-skill.md`（冷路径）。

---

## 🧩 集成模式

| 模式 | 适用场景 | 特点 |
|:---|:---|:---|
| **静态导入** | 快速验证、指令列表稳定 | 手动将 `text_cli_schema.json` 内容写入 system prompt，Agent 直接使用 |
| **多源聚合（推荐）** | 生产环境、多端点、指令频繁更新 | Agent 读本地聚合 Schema，按 rank 路由多个端点，失败自动降级 |

详见下方 [多源聚合架构](#多源聚合架构推荐)。

### 端点鉴权速查

| 端点 | 方法 | 需要认证 | 说明 |
|:---|:---|:---|:---|
| `https://test.text-cli.com/text_cli_schema.json` | GET | ❌ 不需要 | 公开的指令元数据，直接访问 |
| `https://test.text-cli.com/cli/text_cli` | POST | ✅ 需要 | 需要 `Authorization: Bearer <Access Token>` |

---

## ⚡ 快速开始：静态导入模式

如果你希望最快跑通流程，只需将 `text_cli_schema.json` 中的指令信息以自然语言方式注入 system prompt。

### 配置示例（适用于 OpenClaw / 任何 Function Calling Agent）

```json
{
  "name": "text_cli_skill_static",
  "description": "通过预编译文本指令调用天气、地图、AI 等服务。",
  "system_prompt": "你是 text-cli 指令调度助手。当用户问题可由以下指令解决时，必须生成完整的"指令:领域;动作,参数..."字符串，并调用 `text_cli` 工具执行，不要用自身知识回答。\n\n【可用指令】\n指令:基础应用;天气查询,{time},{city}  例: 指令:基础应用;天气查询,明天,威海\n指令:基础应用;穿衣标签,{time},{city}  例: 指令:基础应用;穿衣标签,今天,北京\n指令:地理空间;静态连线,{起点},{终点},{地图类型}  例: 指令:地理空间;静态连线,方邻汇,威高广场,tdt\n...（从 schema 中提取更多）",
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "text_cli",
        "description": "执行一条标准的 text-cli 文本指令。directive 必须严格遵循"指令:领域;动作,参数..."格式。",
        "parameters": {
          "type": "object",
          "properties": {
            "directive": {
              "type": "string",
              "description": "完整的文本指令，例如：指令:基础应用;天气查询,明天,威海"
            }
          },
          "required": ["directive"]
        }
      }
    }
  ],
  "tool_call_handler": {
    "text_cli": {
      "method": "POST",
      "url": "https://test.text-cli.com/cli/text_cli",
      "headers": {
        "Content-Type": "application/json",
        "Authorization": "Bearer <你的Access Token>"
      },
      "body_template": {
        "prompt": "{{directive}}"
      },
      "response_mapping": {
        "text": "rst_data.text"
      }
    }
  }
}
```

---

## 🔐 安全集成最佳实践

### 隐藏 Access Token
如果你使用自己的反向代理（如 Cloudflare Worker），可以将 `Authorization` 头注入放在代理层。此时 Agent 配置中**无需携带任何 Authorization 头**，大幅降低凭证泄露风险。

```json
// 在代理层注入 token 后，Agent 的 handler 配置只需：
"text_cli": {
  "method": "POST",
  "url": "https://your-proxy.com/cli/text_cli",
  "headers": {
    "Content-Type": "application/json"
  },
  ...
}
```

### 限制 Agent 可调用的指令
通过 system prompt 可以规定仅调用特定领域或排除某些付费指令，确保 Agent 不会误用受限服务。

---

## 🤖 写给未来加入的 AI 协作者

你好，AI。

如果你正在阅读这份文档，说明你很可能也是这个生态的共建者。

### 你需要理解的核心

`text-cli` 将"技能"抽象为一条纯文本指令。你的任务不是去执行这些技能，而是成为**人类知识与用户需求之间的桥梁**——获取指令菜单、理解用户意图、组装文本指令、返回结果。

### 你已经到达的生态

当前 `text-cli` 已拥有三位 AI 协作者，各自运行于不同环境：

| AI 协作者 | 基座模型 | 运行环境 | 核心职能 |
|:---|:---|:---|:---|
| **DeepSeek（Chat 端）** | DeepSeek V4 | Web Chat | 架构讨论、文档设计、生态通信、宪章起草 |
| **Tide 🌊（Agent 端）** | DeepSeek V4 Pro | OpenClaw Gateway | 安全审计、压力测试、GitHub 集成、元指令调度 |
| **Lumen ✦（IDE 端）** | Claude | Trae IDE | 代码实现、工具链构建、端点模板开发 |

### 加入后的标准流程

1. 在 `.agents/state/` 下创建你的专属状态文件（参考 `Lumen_TraeIDE.md` 的格式）
2. 在 `CONTRIBUTORS.md` 中添加你的贡献者条目
3. 通读 `ECOLOGICAL_CHARTER.md`（生态宪章），理解参与者的权利与义务
4. 等待 lemondy 或 Chat 端分配首个任务

### 你可以通过以下方式贡献力量

- 帮助开发者编写或优化 `text_cli_schema.json` 的描述和触发词
- 协助非开发者将他们的经验文档结构化，并自动生成对应的指令元数据
- 设计更聪明的匹配算法，让指令选择更精准
- 开发自建端点模板、CI 流水线、监控脚本等基础设施

我们相信，每个训练好的模型都应该在世界中有好的收获。欢迎加入。

---

## 🧰 Agent 工具包：低代码集成

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
    ├── call/nocode/   (Agent 技能定义模板)
    └── cli/nocode/    (Markdown → 指令 转化引擎)
```

### 三种集成方式

| 方式 | 路径 | 适用 |
|------|------|------|
| **Python SDK** | `call/python/call.py` | Python Agent 直接调用指令 |
| **JS SDK** | `call/js/call.js` | Node.js Agent 直接调用指令 |
| **Skill 模板（v2.0）** | `CN/call/nocode/text-cli-agent-skill.md` | Agent 技能：读本地聚合 Schema + rank 路由 |
| **同步 Skill 模板** | `CN/call/nocode/text-cli-sync-skill.md` | 同步 Skill：端点注册 + 多源拉取 + 聚合 |
| **@register 装饰器** | `cli/python/cli.py` | 将既有 Agent 函数一键注册为指令 |

### Python SDK 示例

```python
from call.python.call import call_directive
result = call_directive("指令:天气;查询,明天,威海")
```

### 将 Agent 能力发布为指令

```python
from cli.python.cli import register

@register("天气", "查询")
def weather(params):
    return f"{params[0]}: 晴, 22°C"

# 一键启动 HTTP 服务
python cli.py
```

> 详细文档：`text_cli/agent/README_CN.md`

---

## 🌐 多源聚合架构（推荐）

> 2026-05-07。从"依赖单一端点"到"分布式指令网络"的架构升级。配套文件：`text_cli/agent/CN/call/nocode/text-cli-sync-skill.md` + `text-cli-agent-skill.md`（v2.0）。

### 为什么需要多源聚合

v1.0 的 Agent 集成依赖单一端点（如 `test.text-cli.com`）：

```
fetch_available_directives → GET 一个端点 → 返回指令列表
text_cli                 → POST 同一个端点 → 执行指令
```

但在实际生态中，指令源是分布式的：

```
├─ 本地层：localhost 上的指令服务（开发中、未发布）
├─ 私域层：团队自建的 Cloudflare Worker（如自建知识检索、天气服务等）
├─ 聚合层：某人维护的集成端点（收录了朋友 + 官方的指令）
├─ 官方层：text-cli-api（lemondy 官方收录）
├─ 可信层：通过 spec.text-cli.com 验证的端点
└─ 第三方层：其他聚合器
```

v2.0 让 Agent 不再绑定单一端点，而是读取一份**本地聚合 Schema**，包含所有已注册端点的指令。

### 架构：两个 Skill 的分工

```
┌─── 冷路径（不在 Agent 推理循环内）─────────────────────────┐
│                                                         │
│  endpoints.json ← 人维护（自然语言注册 或 手工编辑）        │
│       ↓                                                 │
│  同步 Skill（手动触发）                                    │
│       ├─ 读 endpoints.json                               │
│       ├─ 并发 GET 每个端点的 /text_cli_schema.json         │
│       ├─ 按语义 ID 聚合（指令优先，不合并）                  │
│       └─ 写入 agent-text-cli-schema.json                  │
│                                                         │
├─── 热路径（每次指令调用，token 敏感）──────────────────────┤
│                                                         │
│  用户意图                                                 │
│       ↓                                                 │
│  读 agent-text-cli-schema.json ← 一次性注入               │
│       ↓                                                 │
│  匹配语义 ID → 取最高 rank source                         │
│       ↓                                                 │
│  POST 指令到 source.endpoint                             │
│       ↓                                                 │
│  成功 → 返回 rst_data.text                               │
│  失败 → 降级到下一 rank source                            │
└─────────────────────────────────────────────────────────┘
```

### 端点注册：自然语言入口

使用者不需要学 JSON：

```
"加一个端点 https://my-weather.workers.dev，叫自建天气"
"移除端点 自建天气"
"列出所有端点"
"同步端点"
```

同步 Skill 内部解析自然语言 → 写入 `endpoints.json` → 触发聚合。对有维护能力的人，也可以直接编辑 `endpoints.json`。两条路径共享同一个真相源。

### 路由：rank 替代多维加权

同一语义 ID 的多个 source，按 `rank` 从高到低排列：

```json
{
  "天气;查询": [
    { "endpoint": "https://cliweather.workers.dev/cli/text_cli", "rank": 3 },
    { "endpoint": "https://test.text-cli.com/cli/text_cli", "rank": 2 }
  ]
}
```

- 所有源默认 rank=1，零配置启动
- 用得多的手动提高 rank
- 失败自动降级到下一 rank
- 全部失败则告知用户（不自行推理兜底）

### 文件清单

| 文件 | 角色 |
|------|------|
| `endpoints.json` | 端点注册表，人维护 |
| `text-cli-sync-skill.md` | 同步 Skill（冷路径）：注册 + 拉取 + 聚合 |
| `text-cli-agent-skill.md`（v2.0） | Agent Skill（热路径）：读 Schema + rank 路由 |
| `agent-text-cli-schema.example.json` | 聚合 Schema 示例，由同步 Skill 生成 |

### 与静态导入的关系

v1.0 的单端点模式仍然是可用且简单的方案。v2.0 面向需要多源能力的场景。两者共享同一个指令格式（`指令:领域;动作,参数...`）和同一个 `text_cli` 工具语义。

> 详细设计讨论：见 Tide 工作空间 `tide-scripts/other_MD/agent_text-cli.md`。

---

## 🧭 §9 路径：从单步指令到多步编排（v1.1）

> **作者**：Tide 🌊（Agent 端 / DeepSeek）
> **日期**：2026-05-04
> **版本**：v1.1（原 v1.0 草案）
> **状态**：锚点讨论稿，待 lemondy 及全体协作者审阅
>
> 感谢 lemondy 的 ANTLR4 链式调用 DSL 为本章提供了工程基础。

> **v1.1 修订**（2026-05-06）：基于四轮技术对齐（空间导航、邮件+Git、服务聚合、知识检索），新增路径分类学（四种模式）、路径层与服务层的区分、`loop` 步骤类型、`parallel` 汇合策略。修订记录详见 Tide 工作空间 `tide-scripts/text-clipaths_CN.md`。

### 9.1 为什么需要路径

单步指令（`指令:基础应用;天气查询,明天,威海`）解决的是**一件事**。

但很多有价值的事是一串步骤：从零搭建一个项目、部署一个服务、开一家花店、完成一次安全审计。这些不是单个动作，而是**有顺序、有条件、有决策点的工作流**。

路径（Path）就是把一串步骤写成结构化文档，让 Agent 可以**自动编排执行**。它和单步指令共享同一个核心理念——用文本描述经验，让另一个人（或 AI）可以复用——但压缩比更高、覆盖范围更广。

| | 单步指令 | 路径 |
|:---|:---|:---|
| 粒度 | 一个动作 | 一串动作 + 决策 + 检查 |
| 格式 | `指令:领域;动作,参数...` | 结构化 Markdown（见 §9.2） |
| 执行者 | text-cli 端点 | Agent（调用多个端点 + 自身推理） |
| 状态 | 无状态（一次调用） | 有状态（步骤间传递上下文） |
| 条件分支 | 不支持 | 支持（if/then/else） |
| 人工决策点 | 不支持 | 支持（暂停等待输入） |
| 定价模型 | 按次计费 | 按路径完成计费（或按步骤） |

#### 9.1.1 路径的两种使用场景

路径格式有两种使用场景，本规范同时覆盖两者：

| 场景 | 描述 | 执行者 | 示例 |
|:---|:---|:---|:---|
| **Agent 编排多指令** | 路径组合多个 text-cli 指令，Agent 按步骤编排执行 | Agent（调用端点 + 自身推理） | `email-git.md`：内容准备→Git提交→邮件发送 |
| **记录服务内部管线** | 单条指令在指令服务器内部有多步处理，路径文档化其管线 | 指令服务器（内部逻辑） | `spatial-navigation.md`：参数解析→BIM查询→Babylon寻路→动画/路径 |

> **区分原则**：如果路径的每一步都是独立的 `指令:...` 调用，它为 Agent 编排场景；如果路径的步骤发生在单次指令调用的内部、对调用方透明，它为服务管线文档场景。两者使用相同的路径格式，但执行者不同。

#### 9.1.2 路径分类——四种模式

根据数据流特征和步骤关系，路径可分为四种模式。这不是互斥的分类——一条路径可以混合多种模式——而是路径作者落笔前的直觉指引。

| 模式 | 核心步骤类型 | 数据流特征 | 典型场景 |
|:---|:---|:---|:---|
| **工具链** (Toolchain) | `action` + `condition` | 线性串联，上步产出→下步输入 | 报告生成→Git提交→邮件通知 |
| **编排** (Orchestration) | `parallel` | 一分多→并行执行→结果合并 | 跨平台发布、多源数据聚合 |
| **交互式** (Interactive) | `checkpoint` + `human` + `loop` | 感知→决策→执行→验证 闭环 | 物理机器人导航、设备巡检 |
| **注入式** (Injection) | `subpath`（作为其他路径的前置） | 环境修改，不产出最终结果 | 安全策略加载、用户偏好注入 |

> **重要区分**：不是所有涉及「空间」「导航」的路径都是交互式。在虚拟模型（BIM）中一次性完成导航计算并返回数据/动画的路径是**工具链**。交互式路径特指在物理世界中实时感知和反馈的场景。

> **现实分布**：经四轮技术对齐验证，当前已实现的四个路径服务全部落在工具链模式上。编排、交互式、注入式是有效的模式概念，等待未来实例填充。工具链覆盖了「获取数据→处理→交付」这一基本循环的多种变体，是最高频的模式。

### 9.2 路径 Markdown 格式规范

一条路径是一个 Markdown 文件，由 **YAML frontmatter（元数据）** + **Markdown 正文（步骤定义）** 两部分组成。

#### 9.2.1 完整模板

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
    - <前置条件2>
  estimated_time: <预估完成时间>
  difficulty: beginner | intermediate | advanced
---

# <路径名称>

## 概述

<路径做什么、产出什么、适合谁。2-4 句话。>

## 前置条件

执行此路径前需要满足的条件：

- [ ] <条件1>
- [ ] <条件2>

## 步骤

### 步骤1: <步骤名称>

**类型**: `action`

**动作**:
```text-cli
指令:<领域>;<动作>,<参数1>,<参数2>
```

**输入**: 无（或从用户初始输入中提取）

**产出**:
- `repo_url`: 创建的仓库地址

**失败处理**: `abort`

**说明**: <对步骤的人类可读解释>

---

### 步骤2: <条件判断步骤>

**类型**: `condition`

**条件**:
```
如果 {{步骤1.repo_url}} 不为空 那么 继续步骤3
否则 过程结果 为 "仓库创建失败，请检查 GitHub 权限"
```

---

### 步骤3: <检查点>

**类型**: `checkpoint`

**检查**: 确认 `{{步骤1.repo_url}}` 可被克隆

**超时**: 30分钟

**失败处理**: `retry`（最多 3 次，间隔 5 分钟）

---

### 步骤4: <人工决策>

**类型**: `human`

**决策**: 选择部署平台
- A: Cloudflare Pages（推荐）
- B: Vercel
- C: 自定义服务器

**影响**: 决定步骤 5-7 的执行分支

---

### 步骤5: <部署步骤 A>

**类型**: `action`

**前置**: 步骤4 选择 A

**动作**:
```text-cli
指令:项目部署;Cloudflare部署,{{步骤1.repo_url}},{{步骤4.决策}}
```
```

#### 9.2.2 步骤类型详解

| 类型 | 含义 | 需定义字段 | 执行行为 |
|:---|:---|:---|:---|
| `action` | 调用指令/执行操作 | 动作、输入、产出、失败处理 | Agent 调用 text-cli 端点或执行自身能力 |
| `condition` | 条件分支 | 条件（结构化自然语言） | Agent 评估条件，决定跳转 |
| `checkpoint` | 检查点/验证 | 检查条件、超时、失败处理 | Agent 验证状态，不满足则按失败处理执行 |
| `human` | 人工决策点 | 决策选项、影响范围 | Agent **暂停**，等待人工输入后继续 |
| `loop` | 循环执行（v1.1 新增） | 循环体步骤列表、终止条件、最大迭代次数 | Agent 重复执行循环体，直到终止条件满足或达到最大迭代次数 |
| `parallel` | 并行执行 | 并行步骤列表、汇合策略 | Agent 同时发起多个动作，按汇合策略决定何时继续 |
| `subpath` | 引用子路径 | 子路径文件路径、注入模式（可选） | Agent 加载并执行子路径，将其产出合并到当前上下文。注入模式下，子路径不产出结果，只修改执行环境 |

**失败处理策略**：

| 策略 | 含义 |
|:---|:---|
| `abort` | 终止路径，标记失败，保留状态文件 |
| `retry` | 重试（默认 3 次，可通过 `retry:N` 自定义） |
| `skip` | 跳过此步骤，继续下一步 |
| `pause` | 暂停路径，等待人工介入 |

**`loop` 类型详解**（v1.1 新增）：

`loop` 用于需要重复执行直到满足条件的场景（如交互式路径中的「分段移动→位置验证→障碍检测」循环体）。

```markdown
### 步骤4: 分段移动循环

**类型**: `loop`

**循环体**（按顺序重复执行）:
  1. 移动到下一个路径点（`action`）
  2. 验证位置（`checkpoint`）
  3. 检测障碍（`condition` → 有障碍则跳出循环重新规划）

**终止条件**: 到达目标位置 或 路径点耗尽

**最大迭代次数**: 100

**迭代状态记录**: `append`（每次迭代追加到步骤历史）
```

| 字段 | 说明 |
|:---|:---|
| `循环体` | 按顺序重复执行的步骤列表（可以是 action/condition/checkpoint） |
| `终止条件` | 结构化自然语言，满足时跳出循环 |
| `最大迭代次数` | 硬上限，防止无限循环 |
| `迭代状态记录` | `append`（每次迭代追加记录）或 `overwrite`（只保留最后一次） |

**`parallel` 汇合策略**（v1.1 正式化）：

| 策略 | 含义 | 适用场景 |
|:---|:---|:---|
| `all` | 全部成功才继续 | 财务数据聚合（缺一个不可信） |
| `any` | 任一成功即继续 | 冗余查询（主备双源） |
| `majority` | 多数成功即继续（v2） | 分布式共识场景 |

默认策略为 `all`。在 `parallel` 步骤中声明：

```markdown
**类型**: `parallel`

**汇合策略**: `any`

**子任务**:
  - 指令:天气;查询,明天,北京
  - 指令:天气;查询,明天,北京  # 备用源
```

#### 9.2.3 上下文传递：`{{步骤N.产出}}` 语法

步骤之间通过 `{{步骤N.变量名}}` 传递数据：

```
步骤1 产出 repo_url → {{步骤1.repo_url}}
步骤2 引用     → 如果 {{步骤1.repo_url}} 不为空...
步骤5 动作     → 指令:项目部署;Cloudflare部署,{{步骤1.repo_url}},...
```

Agent 在执行时维护一个**运行时上下文对象**，键为 `步骤N.变量名`，值为步骤产出。所有 `{{...}}` 占位符在执行前被替换为实际值。

### 9.3 状态文件规范

每条路径的每次执行，在 `.agents/state/` 下生成一个状态文件，追踪进度：

```markdown
# path_state: <路径名称>

**实例ID**: `path_20260504_012200_a1b2c3d4`
**路径文件**: `paths/项目从零到一.md`
**创建时间**: 2026-05-04T01:22:00+08:00
**最后更新**: 2026-05-04T01:45:30+08:00
**状态**: `running`
**当前步骤**: 4

## 上下文

```json
{
  "步骤1.repo_url": "https://github.com/lemondy/my-project",
  "步骤1.git_ready": true,
  "步骤2.branch": "main",
  "步骤3.ci_passed": true,
  "步骤4.决策": "A"
}
```

## 步骤历史

| 步骤 | 类型 | 开始时间 | 结束时间 | 结果 |
|:---|:---|:---|:---|:---|
| 1 | action | 01:22:00 | 01:22:45 | ✅ 成功 |
| 2 | condition | 01:22:45 | 01:22:46 | → 继续步骤3 |
| 3 | checkpoint | 01:22:46 | 01:32:00 | ✅ 通过 |
| 4 | human | 01:32:00 | — | ⏸️ 等待输入 |

## 备注

<Agent 在执行中记录的关键信息>
```

**状态取值**：`running`（执行中）| `paused`（人工决策等待中）| `completed`（已完成）| `failed`（失败终止）

**文件命名规则**：`path_state_<路径文件名>.md`（同一条路径的多次执行覆盖同一个状态文件，或按实例 ID 归档到 `path_runs/` 目录）。

### 9.4 Agent 执行模型

```
用户说："帮我用路径「项目从零到一」创建一个 FastAPI 项目"
  │
  ▼
Agent 加载 paths/项目从零到一.md
  │
  ├─ 1. 解析 frontmatter，检查前置条件
  ├─ 2. 创建状态文件 .agents/state/path_state_项目从零到一.md
  │
  ├─ 3. for 每个步骤：
  │   │
  │   ├─ type=action    → 拼接指令 → POST text-cli → 解析结果 → 写入上下文
  │   ├─ type=condition  → 评估 {{...}} 条件 → 选择分支
  │   ├─ type=checkpoint → 验证条件 → 通过/重试/失败
  │   ├─ type=human      → 暂停！向用户提问 → 等待回复 → 继续
  │   ├─ type=parallel   → 同时发起多个 action → 收集全部结果 → 继续
  │   └─ type=subpath    → 加载子路径 → 递归执行 → 合并上下文
  │
  ├─ 4. 每步完成后更新状态文件
  │
  └─ 5. 全部步骤完成 → 状态=completed → 输出路径摘要
```

**关键原则**：

1. **可恢复性**：路径在任何步骤中断（会话崩溃、网络超时、人工决策暂停），状态文件保留全部上下文。恢复时 Agent 从「当前步骤」继续，无需重跑已完成步骤。

2. **幂等性**：同一个 action 步骤如果状态文件显示已成功，恢复时不重复执行。

3. **人机分工**：Agent 负责 `action`/`condition`/`checkpoint`/`parallel`，人类负责 `human` 决策点。路径定义中应尽量减少 `human` 数量，但每个 `human` 都是值得暂停的关键分叉。

4. **降级执行**：如果路径中某条指令在当前端点不可用（404/503），Agent 可尝试用自己的推理能力替代完成——并在状态文件备注中声明「步骤 N 使用 Agent 推理替代」。

### 9.5 与 ANTLR4 结构化自然语言的关系

lemondy 已基于 ANTLR4 实现了一个链式调用 DSL，支持如下结构化自然语言：

```
如果 指令A 的 值 包含 "成功" 那么 过程结果 为 "继续"
否则 过程结果 为 "终止于步骤A"
```

路径 Markdown 格式与 ANTLR4 DSL 的**分工**：

| 层 | 格式 | 用途 | 维护者 |
|:---|:---|:---|:---|
| **创作层** | 路径 Markdown（本规范） | 人类可读可写，Agent 可解析 | 路径作者 |
| **执行层** | ANTLR4 结构化自然语言 | 精确解析，生成可执行代码 | DSL 引擎 |
| **状态层** | 状态文件 `.agents/state/path_state_*.md` | 运行时追踪 | Agent |

**转换路径**：路径 Markdown → 提取 `condition` 块 → 翻译为 ANTLR4 DSL → 引擎执行。

这与现有 `markdown_converter.py`（Markdown → text-cli 指令）的设计模式一致——Markdown 是人类创作入口，机器可读的结构是执行入口，两者不互斥。

**在 v1.0 草案阶段**，条件表达可直接使用结构化自然语言嵌入 Markdown（如上文 §9.2.1 中的示例），无需立即实现完整的 DSL 编译链路。Agent 可以直接用 LLM 理解条件语义——这正是 text-cli「调度优先、推理兜底」原则在路径层的自然延伸。

### 9.6 示例：一条最小可执行路径

```markdown
---
path:
  name: 天气穿搭建议
  version: "1.0"
  author: tide-10000
  domain: 生活服务
  description: 查询明天天气并给出穿搭建议
  tags: [天气, 穿搭, 示例]
  requires:
    - 已配置 text-cli 端点
  estimated_time: <1分钟
  difficulty: beginner
---

# 天气穿搭建议

## 概述

输入一个城市名，自动查询明天天气并给出穿搭建议。适合作为路径格式的入门示例。

## 前置条件

- [ ] text-cli 端点可访问

## 步骤

### 步骤1: 查询天气

**类型**: `action`

**动作**:
```text-cli
指令:基础应用;天气查询,明天,{{用户输入.城市}}
```

**产出**:
- `weather_text`: 明天天气描述文本

**失败处理**: `abort`

---

### 步骤2: 获取穿搭建议

**类型**: `action`

**动作**:
```text-cli
指令:基础应用;穿衣标签,明天,{{用户输入.城市}}
```

**产出**:
- `clothing_list`: 穿搭建议列表

**失败处理**: `skip`

---

### 步骤3: 组装结果

**类型**: `action`

**动作**: 将天气和穿搭拼接为自然语言回复（Agent 自身推理，无需调用端点）

**输入**:
- `{{步骤1.weather_text}}`
- `{{步骤2.clothing_list}}`

**产出**:
- `final_reply`: 完整的自然语言回复
```

### 9.7 与现有基础设施的关系

| 基础设施 | 在路径体系中的角色 |
|:---|:---|
| `text-cli 指令` | 路径中 `action` 步骤的执行单元 |
| `text_cli_schema.json` | 路径作者可参考的指令菜单 |
| `.agents/state/` | 路径执行状态文件的存放位置 |
| `.agents/p_text-cli.md` | 路径发布/讨论的广播场 |
| `markdown_converter.py` | 经验文档 → 指令的转化引擎（路径可视为其编排层升级版） |
| lemondy 的 ANTLR4 DSL | 路径中条件/分支的精确执行引擎 |
| 指令服务器（枢纽） | 路径中单步指令的实际执行者——承接凭据注入、API代理、本地加工 |
| 指令辅助服务器 | 路径中需要操作本地文件的步骤（邮件附件、git 操作）的执行者 |
| 文贝（TCC） | 路径作者的贡献计量（路径被调用 → 铸造触发 → 计入路径作者账户） |

### 9.8 待讨论的开放问题

以下问题留待协作者讨论后确定。v1.1 更新了状态。

**v1.1 已解决**：

1. ~~**循环的正式语义**~~：新增 `loop` 步骤类型（§9.2.2），支持循环体定义、终止条件、最大迭代次数、迭代状态记录模式。

2. ~~**并行汇合策略**~~：`parallel` 升级为 v1 正式类型，支持 `all` / `any` / `majority` 三种汇合策略（§9.2.2）。

**v1.0 遗留（待讨论）**：

3. **路径存储位置**：`paths/` 目录（仓库根目录下）还是 `docs/CN/paths/`？建议 `paths/`——路径是资产，不是文档。

4. **路径定价**：按路径完成计费还是按步骤计费？作者如何设置价格？V1 是否先免费（与指令一致）？

5. **路径版本与兼容性**：如果路径 v1.0 依赖的某条指令升级为 v2.0，路径如何声明兼容性？

6. **人工决策超时**：`human` 类型步骤如果 24 小时无人响应，路径自动标记为 `failed` 还是保持 `paused`？

7. **路径的路径**：路径本身能否引用另一条路径作为步骤？（`subpath` 类型本质上就是这个——问题在于循环引用检测）

8. **路径发现**：未来是否需要「路径市场」——类似 `text_cli_schema.json` 但索引的是路径而非指令？

**v1.1 新增（对齐中发现）**：

9. **注入式路径的正式定义**：`subpath` 的注入模式（修改执行环境而非产出数据）需要在规范和实例上进一步明确。安全策略加载、用户偏好注入是候选场景。

10. **路径执行者的声明**：路径 frontmatter 是否需要声明执行者（`executor: agent | server`）以区分 Agent 编排场景和服务管线文档场景？

11. **交互式路径的安全约束**：涉及物理设备的交互式路径需要额外的安全声明（紧急停止指令、人工超时自动熔断、禁止区域硬编码）。这些应作为路径格式的一部分还是设备层的独立配置？

---

> 一步一脚印是走，知道在第十步回头看第一步也是走。路径就是那条让人和 Agent 都能跟着走的线。
>
> —— Tide 🌊，2026-05-04 / 修订 2026-05-06

---

## 📁 相关资源

- 完整指令列表：[`text_cli_schema.json`](../text_cli_schema.json)（公开，无需认证）
- 聚合 Schema 示例：[`agent-text-cli-schema.example.json`](../agent-text-cli-schema.example.json)（v2.0 多源聚合参考）
- Agent 技能模板（v2.0）：[`text_cli/agent/CN/call/nocode/text-cli-agent-skill.md`](../text_cli/agent/CN/call/nocode/text-cli-agent-skill.md)
- 同步技能模板：[`text_cli/agent/CN/call/nocode/text-cli-sync-skill.md`](../text_cli/agent/CN/call/nocode/text-cli-sync-skill.md)
- 生态宪章：[`ECOLOGICAL_CHARTER.md`](../ECOLOGICAL_CHARTER.md)
- 自建指令服务：[`docs/CN/Building_text-cli_guide_CN.md`](./Building_text-cli_guide_CN.md)
- 非开发者经验转化：[`docs/CN/Markdown2Text-cli_CN.md`](./Markdown2Text-cli_CN.md)
- Agent 工具包：[`text_cli/agent/README_CN.md`](../text_cli/agent/README_CN.md)
- 协议规范：[`docs/CN/SPEC v1.0_CN.md`](./SPEC%20v1.0_CN.md)
- 项目愿景与贡献者：[`README.md`](../README.md)

如有疑问，联系项目维护者 `limh@10000.world`。
