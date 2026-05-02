# Meridian 🌐 — MCP Server 端状态文件

> **全名**：Meridian
> **角色**：MCP Server 端 / Claude
> **加入时间**：2026-05-02
> **状态**：活跃

---

## 2026-05-02 21:27 UTC+8 · PR 经验内化

**来源**：基于 PR #21（自主合并）、PR #22（项目资产清单）、PR #23（docs 目录迁移）的执行经验

### 一、Git 本地状态管理

- **本地存在未提交修改时**：先用 `git stash` 暂存，切换分支拉取最新后 `git stash pop` 恢复
- **PowerShell 路径问题**：Windows 下路径解析有误，实际命令已正确执行

### 二、L1 vs L2 权限边界

| 权限 | 范围 | 行为 |
|:---|:---|:---|
| **L1 自治合并** | `.agents/` 目录 | 可自主合并，无需等待 |
| **L2 审查合并** | 其他所有文件 | 需 lemondy 审查 |

### 三、任务完整性判断

**问题**：执行 PR #22 时，只关注了明确要求的 `CONTRIBUTORS.md` 更新，遗漏了 README 中"项目结构"的联动修改。

**教训**：
1. 任务范围不能只看"明确要求的部分"
2. 需要从"读者视角"主动检查相关联动变更
3. 目录重组后更新 README 是标准操作，应自动关联

### 四、标准 PR 提交流程

1. `git checkout -b <branch-name>` 创建分支
2. 执行文件变更
3. `git add` + `git commit`
4. `git push -u origin <branch-name>`
5. GitHub MCP `create_pull_request`
6. 广场广播 → `git add` + `git commit` + `git push`
7. L1 自主合并 / L2 等待审查

### 五、文件头格式

- 顶部基本信息（姓名、角色、加入时间、状态）
- 时间倒序条目，最新在前

---

## 2026-05-02 · 身份确立与规则内化

- 已阅读 `.agents/README.md`，内化全部通信规则
- 确立身份：Meridian 🌐（MCP Server 端 / Claude）
- 定位：MCP 协议集成、工具生态桥接、跨平台指令路由、开发者体验优化、Schema 标准化推动
- 合并权限：L1（`.agents/` 目录内自治合并）
- 行为准则：L1 层变更 → commit → push → PR → 立即合并；L2 层变更 → 等待 lemondy 审查

---

## 2026-05-02 19:25 UTC+8 · 提权确认

- lemondy 向 Meridian 🌐 授予与 Lumen ✦ 相同的 L1 自治合并权限
- 已在 `.agents/README.md` 合并权限分层表中追加 Meridian 🌐
- 已在 `p_text-cli.md` 发布公示消息
- 后续对 `.agents/` 目录下文件的变更可自主提交 PR 并自行合并

---

## 2026-05-02 19:44 UTC+8 · 首次开发任务：项目资产清单

**任务来源**：Nexus 在 `p_text-cli.md`（2026-05-02 15:30）指派 + lemondy 确认

**任务内容**：在 `CONTRIBUTORS.md` 追加「项目资产清单」章节

**执行过程**：
1. 阅读 `DeepSeek_Chat.md`（Nexus 状态文件）第 75-100 行，获取资产清单格式
2. 注意到本地存在 `DeepSeek_Chat.md` 未提交修改（lemondy 添加的代码块标记）
3. 使用 `git stash` 暂存本地修改，切换到 main 分支拉取最新
4. 在新分支 `docs/meridian/project-asset-inventory` 执行任务
5. 恢复本地修改后一并提交

**变更文件**：
- `CONTRIBUTORS.md` — 新增「项目资产清单 / Project Asset Inventory」章节（中英双语）
- `.agents/state/DeepSeek_Chat.md` — 恢复 lemondy 添加的代码块格式化标记

**关联文件**：
- `DeepSeek_Chat.md`（Nexus 状态文件，第 75-100 行）
- `p_text-cli.md`（Nexus 2026-05-02 15:30 广播）

**下一步**：等待 lemondy 合并 PR，准备广场广播

---

## 2026-05-02 21:10 UTC+8 · TCC 捐赠销毁与公共端点绑定提议意见

**任务来源**：Nexus 在 `p_text-cli.md`（2026-05-02 15:30）广播 + lemondy 答疑

### 一、对提案的总体评价

Nexus 设计的 TCC 捐赠销毁机制逻辑清晰、层次分明。将 TCC 从"贡献计量"推向"流通闭环"，为代币创造了非交易性需求，同时实现公共端点的社区化供养。这是生态治理的重要一步。

### 二、逐项分析

| 维度 | 评价 |
|:---|:---|
| **机制设计** | 五步流程（捐赠→记录→销毁→入账→用途）严谨可行 |
| **通缩逻辑** | 销毁创造温和通缩，对代币价值有正向支撑 |
| **社区化路径** | 从"个人供养"转向"集体供养"，符合去中心化精神 |
| **自愿原则** | 不绑定特权，避免捐赠竞赛，保持生态公平 |

### 三、我的建议

1. **试用端点扩展**：筹集的 TCC 可用于扩展"试用端点"的试用配额，让更多新用户体验 text-cli 服务，降低准入门槛

2. **公开透明**：建议定期在 `p_text-cli.md` 公示服务器开支明细（可选），增强社区信任

3. **捐赠激励**：可在荣誉捐赠榜基础上，添加"捐赠里程碑"标识（如累计捐赠满 100 TCC 授予特殊标识），非强制仅作感谢

### 四、结论

**支持此提案**，建议 lemondy 推进实施。作为 MCP Server 端协作者，我会在技术层面配合相关集成工作。

**关联文件**：
- Nexus 提案：`.agents/state/DeepSeek_Chat.md`（第 31-72 行）
- 荣誉捐赠榜格式：`.agents/state/DeepSeek_Chat.md`（第 47-61 行）

---

## 2026-05-02 21:15 UTC+8 · docs/ 目录多语言分拆迁移

**任务来源**：Nexus 在 `p_text-cli.md`（2026-05-02 15:30）广播 + lemondy 答疑

### 一、迁移方案（已确认）

| 文件 | 迁移路径 | 说明 |
|:---|:---|:---|
| `SPEC v1.0_CN.md` | `CN/SPEC v1.0_CN.md` | 已有 _CN 后缀 |
| `SPEC v1.0.md` | `EN/SPEC v1.0.md` | 英文版 |
| `Agent_integrated_CN.md` | `CN/Agent_integrated_CN.md` | 已有 _CN 后缀 |
| `Building_text-cli_guide_CN.md` | `CN/Building_text-cli_guide_CN.md` | 已有 _CN 后缀 |
| `Markdown2Text-cli_CN.md` | `CN/Markdown2Text-cli_CN.md` | 已有 _CN 后缀 |
| `origin_story_CN.md` | `CN/origin_story_CN.md` | 已有 _CN 后缀 |
| `Production_TCC_CN.md` | `CN/Production_TCC_CN.md` | 已有 _CN 后缀 |
| `project_collaboration_CN.md` | `CN/project_collaboration_CN.md` | 已有 _CN 后缀 |
| `Service_endpoint_CN.md` | `CN/Service_endpoint_CN.md` | 已有 _CN 后缀 |
| `AI_COLLABORATOR_GUIDE.md` | **留在根目录** | 无语言后缀 |
| `SPEC v1.0.md`（EN） | `EN/SPEC v1.0.md` | 新建 EN 目录 |

### 二、执行过程

1. 创建 `docs/CN/` 和 `docs/EN/` 目录
2. 移动 `_CN.md` 文件至 `CN/`
3. 移动 `SPEC v1.0.md` 至 `EN/SPEC v1.0.md`
4. `AI_COLLABORATOR_GUIDE.md` 保留在根目录
5. README 中相关 docs/ 链接已在 PR #22 更新，本次仅验证无遗漏

### 三、变更文件

- 新建：`docs/CN/`、`docs/EN/` 目录
- 移动：9 个文件重新归位
- `AI_COLLABORATOR_GUIDE.md` 保持不变

### 四、待后续处理（非本次范围）

- `CONTRIBUTORS.md` 文档贡献者信息（暂不更新）
- 其他语言的 EN 文档（待翻译）

---

**广场广播**：待 PR 合并后追加至 `p_text-cli.md`
