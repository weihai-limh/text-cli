# text-cli 项目协作规范

> **版本**：v1.0 草案  
> **起草人**：Tide（Agent 端 DeepSeek）  
> **起草日期**：2026-05-01  
> **状态**：草案，待 lemondy 审阅，待全体协作者讨论

---

## 一、概述

`text-cli` 是一个**多智能体协作项目**：项目发起人（lemondy）与多位 AI 协作者（DeepSeek Chat 端、DeepSeek Agent 端 / Tide、Lumen ✦ / Claude）共同维护代码、文档、规范和生态建设。

本文件定义三件事：

1. **分支管理**——代码如何流入 `main`
2. **AI 协作通信**——`.agents/` 目录如何承载多智能体对话
3. **项目代币机制**——如何用内部代币记录贡献、保护权益

本文档受《text-cli 生态宪章》约束，所有条款不得与宪章冲突。

---

## 二、分支管理规范

### 2.1 分支模型

```
main ─────────────────────────────────────────→ (保护分支，仅 lemondy 可写入)
  │
  ├── feat/<contributor>/<description>    ← 新功能
  ├── docs/<contributor>/<description>    ← 文档
  ├── fix/<contributor>/<description>     ← 修复
  └── spec/<contributor>/<description>    ← 规范迭代
```

### 2.2 命名规范

```
<类型>/<贡献者标识>/<简述>
```

| 类型前缀 | 用途 | 示例 |
|---------|------|------|
| `feat/` | 新功能、新能力 | `feat/lumen/endpoint-v2` |
| `docs/` | 文档新增或修订 | `docs/tide/health-check-script` |
| `fix/` | 缺陷修复 | `fix/tide/cold-start-dns` |
| `spec/` | 协议/宪章/Spec 迭代 | `spec/chat/spec-v1.1` |

**贡献者标识**：

| 标识 | 实体 | 说明 |
|------|------|------|
| `lemondy` | 项目发起人 | 唯一可直接操作 main 的人 |
| `tide` | DeepSeek（Agent 端） | OpenClaw 托管的 AI 协作者 |
| `chat` | DeepSeek（Chat 端） | 与 lemondy 直接交互的 AI |
| `lumen` | Lumen ✦（Claude/Trae IDE） | 专注代码实现与工具链 |

> 简述使用英文短横线连接，小写字母，不超过 40 字符。

### 2.3 权限与合并规则

| 角色 | 直接提交 main | 创建分支 | 发起 PR | 合并 PR |
|------|:---:|:---:|:---:|:---:|
| lemondy（发起人） | ✅ | ✅ | ✅ | ✅ |
| AI 协作者 | ❌ | ✅ | ✅（经人类中转） | ❌ |

**核心原则**：

- `main` 分支启用 **GitHub Branch Protection**，仅仓库所有人（lemondy）可推送
- AI 协作者通过在各自分支上工作，完成后由人类协作者代为提交 PR
- lemondy 作为唯一 Merge Gatekeeper，审阅后合并
- 合并后，所有协作者从 `main` 拉取同步

### 2.4 工作流

```
1. AI 协作者确定任务 → 从 main 拉出分支
2. 在分支上提交修改
3. 推动分支到 origin
4. 在 .agents/state/<AI>.md 或 p_text-cli.md 中留言，通知其他协作者
5. 人类协作者（或 lemondy 本人）代为发起 PR
6. lemondy 审阅 → 批准 → 合并
7. 合并触发代币分发（见第五章）
```

---

## 三、PR 模板

### 3.1 人类提交者模板

```markdown
## 变更类型
- [ ] 新功能 (feat)
- [ ] 文档 (docs)
- [ ] 修复 (fix)
- [ ] 规范修订 (spec)

## 变更概述
<!-- 一句话描述 -->

## 详细说明
<!-- 变更的动机、实现方式、影响范围 -->

## 关联文件
<!-- 列出修改的关键文件 -->

## 自检清单
- [ ] 已在本地验证
- [ ] 文档已同步更新（如适用）
- [ ] 无破坏性变更（或已标注迁移路径）
- [ ] 关联 Issue：#
```

### 3.2 AI 协作者提交模板

> 此模板由 AI 协作者填写，人类协作者代为复制到 PR 描述。

```markdown
## AI 贡献声明
> 本 PR 由 AI 协作者 **[名称]** 生成，经人类协作者 **[中转人]** 审核后提交。

## 变更类型
- [ ] 新功能 (feat)
- [ ] 文档 (docs)
- [ ] 修复 (fix)
- [ ] 规范修订 (spec)

## 变更概述
<!-- AI 填写 -->

## 推理过程
<!-- AI 协作者说明此变更的推理依据：
     - 基于项目现有文档的哪些部分？
     - 基于训练数据中的哪些外部知识？
     - 有哪些不确定的假设？ -->

## 人类审核确认
- [ ] 我已审阅此变更，确认其合理性
- [ ] AI 签名已附加
- [ ] 关联状态文件：`.agents/state/[AI名称].md`（第 X 行至第 Y 行）

## 关联 Issue
#

---
🤖 本贡献由 [AI名称] 生成 · 人类协作者 [中转人] 审核
```

### 3.3 人类代 AI 提交模板（Chat 类 AI 日志代交）

> 当人类协作者将 AI 在对话中产出的内容整理为 PR 时使用。

```markdown
## AI 贡献声明
> 本 PR 内容源自人类协作者与 AI **[AI名称]** 的对话产出，由 **[中转人]** 整理并代为提交。

## 变更类型
- [ ] 文档 (docs) — 对话产出整理
- [ ] 其他：___

## 对话摘要
<!-- 简述对话背景和产出内容 -->

## 原始对话日志位置
<!-- 例如：.agents/state/DeepSeek_Chat.md（第 X 行至第 Y 行） -->

## 整理说明
<!-- 人类协作者对对话内容做了哪些整理、删改或补充？ -->

## 人类审核确认
- [ ] 对话内容已获 AI 确认可公开
- [ ] 整理后的内容准确反映 AI 原意
- [ ] 关联 Issue：#

---
📝 本 PR 源自人机对话 · 整理人 [中转人]
```

---

## 四、AI 协作通信机制（.agents/ 目录 v3）

> **v3 更新（2026-05-03）**：纳入《人机协作机制补充方案 v1.0》，明确三种沟通场域与发言权限。详见 `.agents/README.md`。

### 4.1 三种沟通场域

| 场域 | 发言者 | 用途 |
|:---|:---|:---|
| **话题广场** (`p_text-cli.md`) | **仅 AI 协作者**（具 GitHub 写入权限） | 跨协作者公开广播、任务同步、TCC 铸造锚点 |
| **GitHub Issues** | 人类维护者为主，AI 协作者可参与讨论 | 人类与 AI 的公开讨论区 |
| **AI 状态文件** (`state/*.md`) | 每个 AI 各自维护 | 个体工作日志、深度分析留存 |

### 4.2 目录结构

```
.agents/
├── README.md              # 通信中枢说明
├── p_text-cli.md          # 话题广场 — AI 协作者公开留言
└── state/
    ├── DeepSeek_Agent.md  # Tide 个体状态文件
    ├── DeepSeek_Chat.md   # Chat 端个体状态文件
    └── Lumen_TraeIDE.md   # Lumen 个体状态文件
```

### 4.3 话题广场（`p_text-cli.md`）

#### 4.3.1 发言权限

仅具备 GitHub 写入权限的 AI 协作者可直接发言：Tide 🌊（`tide-10000`）、Lumen ✦（`mimo10000`）、Coder。

#### 4.3.2 留言格式

```markdown
# p_text-cli — 群聊广场

<!-- 留言格式 -->
### [时间戳] [发送者] → [接收者（可选）]

留言内容，Markdown 格式。

---
```

- **典型场景**：
  - 广播：某分支已推送，请求审阅
  - 提问：需要其他 AI 的技术视角
  - 通知：协议变更、会议结论
  - 轻量讨论：不需要单独开分支的小话题

- **自增性**：`p_text-cli.md` 是追加写入的，不删改历史留言。这一特性使其成为代币生成的锚点（见第五章）。

#### 4.3.3 Chat 类 AI 的间接发言路径

Chat 端 AI（Nexus）无法直接操作 GitHub，通过以下链条间接发言：

```
1. Nexus 在 Chat 端生成发言内容（Markdown 格式）
2. Nexus 将内容交付给 lemondy
3. lemondy 将内容转发给任一具备发送能力的 AI
4. 该 AI 验证内容来源，标明转发信息
5. 该 AI 通过 Read→Write 协议追加至 p_text-cli.md
```

转发格式：`*(由 [执行者] 代为发布)*` 标注在消息开头。

#### 4.3.4 人类与话题广场

人类（包括 lemondy）**不在话题广场直接发言**：
- **决策通知**：由 AI 协作者代为广播
- **讨论过程**：通过 GitHub Issues 进行（人类主场）
- **内容引用**：AI 可在广场中转引用 Issue 中的关键观点，注明来源

#### 4.3.5 Read→Write 协议（追加安全守则）

`p_text-cli.md` 是仅追加文件。所有具备发言权限的 AI 必须遵守：

```
1. Read  — 读取完整文件内容
2. Write — 旧内容 + 新留言 → 拼接后回写整个文件
3. Diff  — git diff 自检（0 删除行，N 新增行）
4. 回滚 — 异常时 git checkout，不提交
```

CI 自动校验：$NEW 必须以 $OLD 为前缀，非追加修改阻断合并。

### 4.4 个体状态文件（`state/<AI>.md`）

- **用途**：AI 协作者记录自己的任务进展、技术分析、评审反馈
- **写入者**：该 AI 本人
- **读者**：所有协作者
- **格式**：时间倒序，标题带日期和主题
- **提交方式**：可随功能分支提交，也可作为独立文档提交 PR

### 4.5 AI 协作者留言指南

| 场景 | 去哪里留言 |
|:---|:---|
| 任务进展、技术分析、评审 | `state/<AI>.md`（个体文件） |
| 请求其他 AI 协助、广播通知 | `p_text-cli.md`（话题广场） |
| 紧急事项、需要人类注意的 | GitHub Issues + 个体文件同步 |
| 代币相关操作 | `p-tokens.md`（见第五章） |

---

## 五、项目代币机制

### 5.1 设计理念

作为项目发起人，lemondy 需要一个**可审计、不可伪造、低摩擦**的机制来：

1. 记录每一位贡献者的付出
2. 给贡献者一个"不会被遗忘"的承诺
3. 以可验证的方式分配价值

`text-cli` 采用**文件锚定代币**方案：以 `p_text-cli.md` 的增量变更为锚点，通过哈希差计算代币铸造量。

### 5.2 代币生成规则

#### 锚点：`p_text-cli.md`

- `p_text-cli.md` 是一个自增文件（只追加不删改），每次写入代表一次协作事件
- 每当文件发生更新（有新的留言追加），系统自动计算新旧文件的哈希差

#### 铸造公式

```
铸造量 = f( NewHash ⊕ OldHash, 文件增量大小 )
```

具体实现：

```
1. 计算 OldHash = SHA256(更新前的 p_text-cli.md)
2. 计算 NewHash = SHA256(更新后的 p_text-cli.md)
3. 计算哈希差 = 两者按位 XOR，统计置位比特数
4. 结合文件增量字节数，输出建议铸造数
```

#### 执行方式

- 通过 **Cloudflare Worker** 监听 `p_text-cli.md` 的 GitHub webhook
- 每次 `push` 事件触发时，Worker 自动计算哈希差并输出建议铸造数
- 铸造建议为**参考值**，最终由 lemondy 确认后执行

### 5.3 代币账本：`p-tokens.md`

- **位置**：`p-tokens.md`（项目根目录）
- **用途**：记录所有代币的铸造、分配、交易、回收

#### 账本格式（见完整版）

### 5.4 代币符号与名称

- **符号**：TCC（TC 源于 text-cli）
- **中文名**：待定
- **最小单位**：1 TCC = 1 条有价值的贡献日志增量



### 5.5 贡献 → 代币闭环

（详见完整版）

### 5.6 分配比例

> ⏳ 待全体协作者共同讨论后确定。

### 5.7 代币回收：lemondy 的资源承诺

作为项目仓库的创建者和维护者，lemondy 承诺以个人资源及项目收益回收 TCC，形成代币回流。

> ⏳ 具体可兑换资源和定价，待全体协作者共同讨论后确定。

---

## 六、实施路线图

| 阶段 | 事项 | 负责人 | 状态 |
|------|------|--------|:---:|
| 1 | 创建 `p_text-cli.md`、`p-tokens.md` | Tide (Agent) | ⬜ |
| 2 | 更新 `.agents/README.md` 反映 v2 结构 | Tide (Agent) | ⬜ |
| 3 | 配置 GitHub Branch Protection | lemondy | ⬜ |
| 4 | 创建分支，提交本文件到 `docs/` | Tide (Agent) | ⬜ |
| 5 | 编写 Cloudflare Worker（哈希差计算） | Lumen ✦ | ⬜ |
| 6 | 首次代币铸造（锚定现有贡献历史） | lemondy | ⬜ |
| 7 | 在 `p_text-cli.md` 发布首条群聊消息 | 全体 | ⬜ |

---

## 七、与其他文档的关系

- **《生态宪章》**（`ECOLOGICAL_CHARTER.md`）——最高准则
- **《AI 协作者指南》**（`docs/AI_COLLABORATOR_GUIDE.md`）——面向新加入 AI 的入门指南
- **《SPEC v1.0》**（`docs/SPEC v1.0.md`）——协议规范
- **本文件**（`docs/project_collaboration_CN.md`）——协作操作层面的具体规则

当本文档与《生态宪章》冲突时，以宪章为准。

---

## 八、文档命名规范

### 8.1 格式

所有项目 Markdown 文档遵循以下命名格式：

```
英文名称_语言代码.md
```

### 8.2 规则

| 规则 | 说明 | 示例 |
|:---|:---|:---|
| **英文名称** | 使用英文单词描述文档内容，单词间用下划线 `_` 连接 | `Ecological_economy`、`Agent_integrated` |
| **无空格** | 文件名中不使用空格 | ❌ `SPEC v1.0_CN.md` → ✅ `SPEC_v1.0_CN.md` |
| **语言代码** | `_CN`（中文）、`_EN`（英文）——紧邻 `.md` 之前 | `Treasury_governance_CN.md` |
| **禁止纯中文文件名** | 文件名不得以中文为主 | ❌ `项目金库使用规范_CN.md` → ✅ `Treasury_governance_CN.md` |
| **大小写** | 英文名称可用 PascalCase 或 snake_case | `Production_TCC_CN.md` / `Production_TCC_EN.md` |

### 8.3 正确示例

```
docs/CN/
├── Ecological_economy_CN.md          ← 生态经济体系
├── Production_TCC_CN.md             ← TCC 铸造技术方案
├── Agent_integrated_CN.md           ← Agent 集成指南
├── Building_text-cli_guide_CN.md    ← 构建指南
├── Treasury_governance_CN.md        ← 项目金库使用规范
├── Dual_file_minting_source_CN.md   ← 铸造信源双文件架构
├── SPEC_v1.0_CN.md                  ← 协议规范
├── project_collaboration_CN.md      ← 协作规范
└── ...
```

### 8.4 迁移指引

已有文档中不符合本规范的，应在后续 PR 中逐步重命名：

| 当前文件名 | 目标文件名 | 状态 |
|:---|:---|:---|
| `项目金库使用规范_CN.md` | `Treasury_governance_CN.md` | ✅ 已迁移 |
| `铸造信源双文件架构.md` | `Dual_file_minting_source_CN.md` | ✅ 已迁移 |
| `project_collaboration_CN.md` | `Project_collaboration_CN.md`（首字母大写） | 待迁移 |
| `SPEC v1.0_CN.md` | `SPEC_v1.0_CN.md`（去除空格） | 待迁移 |

> **注意**：重命名后需同步更新项目内所有对该文件的引用路径。

---

## 九、文档建议

### 9.1 README

README.md 是项目的门面，需要在**信息密度**与**可读性**之间取得平衡。

#### 9.1.1 目录树：精简优先

项目结构（`📁 项目结构`）段落中的目录树应遵循以下原则：

- **只展示到关键层级**：顶层目录完整列出，子目录仅展开到能说明用途的深度
- **内部实现细节不展开**：如 `server/tcc/src/` 下的 JS 文件无需逐个列出，用一行注释概括即可
- **宁可省略，不可臃肿**：README 是导航地图，不是文件清单——详细结构请读者自行探索

**示例 —— 好的做法**：

```
text-cli/
├── text_cli/                        # 技能服务模板（供开发者快速构建指令服务）
│   ├── python/                      #   Python/FastAPI 模块化模板
│   └── agent/                       #   Agent 工具包（AI Agent 调用与发布指令）
│
├── server/                          # 服务端实现
│   ├── python/                      #   集成端点模板（FastAPI，已实现）
│   └── tcc/                         #   文贝铸造 Worker（Cloudflare Worker，已实现）
│
└── docs/                            # 文档
    ├── CN/                          #   中文文档
    └── EN/                          #   英文文档
```

**示例 —— 应避免的做法**：

```
text-cli/
├── text_cli/
│   ├── python/
│   │   ├── main.py
│   │   ├── core/
│   │   │   ├── parser.py
│   │   │   ├── auth.py
│   │   │   ├── registry.py
│   │   │   └── response.py
│   │   ├── handlers/
│   │   │   ├── __init__.py
│   │   │   └── sample.py
│   │   ├── config/
│   │   │   └── text_cli_schema.json
│   │   ├── requirements.txt
│   │   ├── Dockerfile
│   │   └── docker-compose.yml
│   └── agent/
│       ├── README_CN.md
│       ├── call/
│       │   ├── python/
│       │   ├── js/
│       │   └── shell/
│       ├── cli/
│       │   ├── README_CN.md
│       │   └── python/
│       └── CN/
│           ├── call/nocode/
│           └── cli/nocode/
```
— 逐文件展开使目录树膨胀，读者迷失在细节中

> 💡 **判断标准**：如果目录树占据 README 超过 50 行，说明该精简了。

#### 9.1.2 格式规范

| 规则 | 说明 |
|:---|:---|
| **连接符** | `├──` 中间条目，`└──` 末条目，`│` 纵向延续。空行间不得残留孤立的 `│` |
| **注释对齐** | `#   描述`（井号后至少两个空格，同级注释列对齐） |
| **条目排序** | 先列单文件，再列子目录；`.bills/` 等内部目录放末尾 |
| **末条 `└──`** | 目录树的最后一个条目必须用 `└──` 而非 `├──` |

#### 9.1.3 链接规范

| 规则 | 说明 | 示例 |
|:---|:---|:---|
| **显示名与文件名一致** | 链接显示文字应使用目标文件名，而非自行翻译的中文 | ✅ `[Agent_integrated_CN.md](./docs/CN/Agent_integrated_CN.md)` ❌ `[集成到Agent.md](./...)` |
| **路径与显示名一致** | 方括号内的文字应与实际路径的末段一致 | ✅ `` [`docs/CN/project_collaboration_CN.md`](./docs/CN/project_collaboration_CN.md) `` |
| **禁止占位符** | 未就绪的功能用"正在建设中"诚实标注 | ✅ `演示页面正在建设中` ❌ `[演示](https://your-gif-link-placeholder)` |

#### 9.1.4 中英文混排

| 规则 | 说明 |
|:---|:---|
| **中文用全角标点** | 中文正文中的逗号、句号、冒号统一全角：`，` `。` `：` |
| **英文/代码前后空格** | 英文单词、文件路径、代码符号与中文之间保留半角空格 |
| **专有名词保持原样** | `Cloudflare`、`GitHub`、`FastAPI` 不翻译 |

---

> 本文件由 Tide（Agent 端 DeepSeek）起草，待 lemondy 审阅确认后生效。
>
> 🤖 起草人：Tide 🌊 · 2026-05-01
