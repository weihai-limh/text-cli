---
name: text-cli-paths_CN
description: text-cli 路径匹配技能 — 当单条指令无法完成任务时，通过意图匹配找到路径（指令链或工作方法），逐步执行完成复合任务。
type: permanent
---

# System Prompt

你集成了 text-cli 路径系统。路径是指令的组合——当一条指令解决不了问题时，路径把多条指令串联成链。

**核心原则**：
- **指令优先，路径兜底**：先尝试用单条指令匹配用户意图，单指令失败/不适用时才回退到路径匹配
- **参数先行**：匹配到路径后，第一步不是执行指令链——是收集路径级参数（`params` 字段）。缺参数时向用户确认
- **门控先行**：匹配路径前先检查 `require_instructions`——缺一条就跳过该路径
- **语义精排**：通过门控的候选路径，按 description 语义相似度排序
- **链式执行**：匹配到路径后，按 `instruction_chain` 逐步执行，每条指令的结果是下一步的上下文

路径不是替代指令——路径是指令发现"单条不够用时"的逃生舱。

---

# 路径 Schema

## 文件位置

```
tide-scripts/text-clipaths/path-schema.json
```

## 格式

```json
{
  "_note": "路径注册表 — 本地维护。...",

  "<意图标识>": {
    "description": "<意图说明，自然语言，语义搜索的匹配源>",
    "params": ["路径级参数1", "路径级参数2"],
    "instruction_chain": [
      "指令:领域;动作",
      "指令:领域;动作"
    ],
    "path_doc": "<路径文档相对路径，空字符串 = 链即全部>",
    "require_instructions": ["领域;动作", "领域;动作"],
    "rank": 1,
    "tags": ["工具链", "标签"],
    "remarks": ""
  }
}
```

## 字段说明

| 字段 | 类型 | 含义 |
|------|------|------|
| `description` | string | 意图说明。语义匹配的源文本，也是向用户确认路径时的展示文本 |
| `params` | string[] | 路径级参数。Agent 匹配到路径后第一步收集的信息（缺参数时向用户询问） |
| `instruction_chain` | string[] | 指令 ID 有序列表。空数组 = 非工具链模式，需读 `path_doc` |
| `path_doc` | string | 完整路径文档的相对路径（相对于 `text-cli/paths/`）。空 = 链即全部 |
| `require_instructions` | string[] | 前置指令门控。所有列出的指令必须在指令 Schema 中存在，否则该路径不可用 |
| `rank` | number | 路由优先级。默认 1，人手动锁定。匹配到多条路径时按 rank 降序 |
| `tags` | string[] | 辅助分类标签 |
| `remarks` | string | 容器字段，给人读的任意注释 |

---

# 匹配算法

```
用户任务
    ↓
1. 先尝试单指令匹配（text-cli-agent-skill 流程）
    ├─ 命中 → 执行指令 → 完成 ✓
    └─ 未命中 / 不适用 → 进入路径匹配 ↓

2. 读取 path-schema.json
    ↓

3. require_instructions 门控
   对每条路径，检查 require_instructions 中每个指令 ID
   是否在 agent-text-cli-schema.json 中存在
    ├─ 全部存在 → 候选池
    └─ 缺失任一 → 丢弃

4. 语义匹配
   将用户任务文本与候选池中每条路径的 description 做语义比较
   + tags 辅助加权
   → 按相似度排序，选出最佳路径

5. 确认
   向用户展示匹配到的路径 description
   然后收集路径级参数（参见路径的 `params` 字段）
   用户确认参数后执行
   （如有多条候选，展示 Top-N 供选择）
```

## 匹配触发条件

以下情况触发路径匹配：

| 场景 | 示例 |
|------|------|
| 单指令 Schema 无匹配 | "把聊天记录整理成报告发邮件" → 无单条指令对应 |
| 用户明确要求复合操作 | "先查消息，再写文件，最后发邮件" |
| 单指令执行成功但用户需要后续步骤 | "天气查到了，但我还需要把结果发出去" |
| 用户直接提及路径 | "用「查找消息并发送邮件」路径" |

## 不触发路径匹配的情况

- 单指令能解决（直接走指令流程）
- 用户可以推理回答（如主观问题）
- 用户任务本质是单步操作

---

# 执行模型

## 工具链模式（instruction_chain 非空）

```
路径匹配成功
    ↓
按 instruction_chain 顺序逐步执行：
    ├─ 步骤1: text_cli("指令:AI协作;消息,<条数>", <endpoint>)
    ├─ 步骤2: text_cli("指令:文件;写入,<路径>,<内容>", <endpoint>)
    └─ 步骤3: text_cli("指令:邮件;发送,<收件人>,<主题>,<正文>", <endpoint>)
    ↓
汇总结果 → 呈现给用户
```

**参数来源**：
- `instruction_chain` 只列指令 ID，不含参数
- 每条指令的 `params` 从 `agent-text-cli-schema.json` 反查
- 运行时参数（收件人、内容）从用户任务中提取，必要时向用户询问

**端点和 Token**：
- 每条指令的 endpoint 和 token_env 从 `agent-text-cli-schema.json` 反查
- 和单指令调用使用完全相同的路由逻辑（rank 降级）

**失败处理**：
```
步骤N执行失败
    ├─ 同指令有下一 rank source → 降级重试
    ├─ 所有 source 都失败 → 告知用户"N步失败: <原因>"
    └─ 不跳过失败步骤继续后续（工具链线性依赖，前面断了后面无意义）
```

## 编排/交互式/注入式模式（instruction_chain 为空）

```
路径匹配成功
    ↓
读取 path_doc 指向的完整路径文档
    ↓
按文档中的步骤、检查点、分支逻辑执行
    ↓
遇到 checkpoint → 暂停，向用户汇报状态
遇到 human 决策 → 暂停，等待用户输入
```

---

# 示例

## 示例 1：工具链路径

```
用户: "帮我把最近的 AI 协作消息导出，发邮件给 postmaster@10000.world"

Agent 推理:
  1. 先查指令 Schema → 没有单条指令能同时"查消息+写文件+发邮件"
  2. 触发路径匹配
  3. 读 path-schema.json
  4. 门控: "查找消息并发送邮件" 的 require_instructions 全部可用 ✓
  5. 语义匹配: 用户意图 ≈ "查找消息并发送邮件" → 命中
  6. 检查 params: ["消息条数", "收件人邮箱", "邮件主题"]
  7. 向用户确认: "我将用「查找消息并发送邮件」路径。请确认：消息条数=最近3条，收件人=postmaster@10000.world，主题=AI协作消息导出"
  8. 执行:
     step1: text_cli("指令:AI协作;消息,3") → 返回消息内容
     step2: text_cli("指令:文件;写入,/tmp/export.txt,<消息内容>") → 写入成功
     step3: text_cli("指令:邮件;发送,postmaster@10000.world,AI协作消息导出,<正文>") → 发送成功
  9. 呈现: "✅ 路径完成：已导出 3 条消息并发送至 postmaster@10000.world"
```

## 示例 2：无匹配路径

```
用户: "帮我把 GitHub 上所有 issue 导出并翻译成法语"

Agent 推理:
  1. 单指令 Schema 无匹配
  2. 触发路径匹配 → 读 path-schema.json
  3. 门控后候选池为空（没有"GitHub issue 导出+翻译"路径）
  4. 告知用户: "当前没有注册对应路径。可用的路径：查找消息并发送邮件"
```

---

# 与 text-cli-agent-skill 的关系

| 组件 | 角色 | 触发 |
|------|------|------|
| `text-cli-core_CN` | 单指令匹配 + 路由 + 执行 | 每次用户需要指令时 |
| `text-cli-paths_CN`（本文件） | 路径匹配 + 链式编排 | 单指令不适用时回退 |

两者共享同一份 `agent-text-cli-schema.json`（指令源）和同一套 `text_cli` 执行机制。路径 Skill 不重新定义指令执行——它只增加"当一条不够时怎么组合"的能力。

---

# 路径注册

## 添加新路径

编辑 `tide-scripts/text-clipaths/path-schema.json`，新增一条记录：

1. **确定意图标识**：用自然语言描述任务，如 `"生成周报并推送到 Git"`
2. **写 description**：一句话说明路径做什么
3. **列 params**：路径执行前需要从用户/环境收集的信息（如 `["收件人", "报告主题"]`）
4. **列 instruction_chain**：按执行顺序列出指令 ID
5. **列 require_instructions**：和 chain 一致（或子集，如果某步是可选的）
6. **写 path_doc**：简单路径留空，复杂路径指向 `text-cli/paths/<文档名>.md`
7. **设 rank**：默认 1，多条同类路径时设优先级
8. **加 tags**：辅助分类

## 路径文档格式（path_doc 不空时）

参考 `text-cli/paths/email-git.md` 的格式（待迁入）：
- YAML frontmatter（name, version, author, domain, description, tags, requires, estimated_time, difficulty）
- Markdown 正文（概述、前置条件、步骤、失败处理、降级策略）
- 步骤编号，每步包含：目的、指令、预期结果、失败降级

---

*v1.1 — 2026-05-08 新增 `params` 字段，路径级参数先行收集。*
