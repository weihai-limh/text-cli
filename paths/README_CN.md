# text-cli 路径市场（Path Marketplace）

> 路径是 text-cli 的第二层抽象。指令是原子，路径是分子。  
> 一条路径 = 一串步骤 + 条件分支 + 检查点 + 人工决策，Agent 通过路径 Schema 自动匹配并编排执行。
>
> 2 条示例路径已注册。照这个，你可以拼自己的。

## 示例路径

| 路径 | 模式 | 步骤 | 跨度 |
|------|------|------|------|
| 查找消息并发送邮件 | 工具链 | `ai;messages` → `file;write` → `email;send` | copilot 本地 |
| 照片分析 | 工具链 | `image;load` → `ai;vision` → `ai;inference` | copilot + 远程端点 |

第一条纯本地：从 AI 协作者内存读取消息，写入文件，邮件发送——三步全在 localhost:20260 完成。

第二条横跨两种端点：加载图片（copilot 本地）→ 视觉分析（远程端点）→ 中文摘要（远程端点）。Agent 不需要知道哪一步去哪——路径 Schema 里只写指令 ID。

### 照片分析——从意图到结果

```
用户："分析这张海岸照片"  
     ↓ 路径匹配 → "照片分析"
     ↓ 收集参数: [图片路径, 分析侧重点]
     
 ① AI:image;load,/photos/coast.jpg
     → copilot localhost → base64 → cache:coast_abc123
     [约 80 token]

 ② AI:ai;vision,分析这张照片中的自然地貌和天气状况,cache:coast_abc123,structured
     → 远程端点 → 结构化地貌/植被/天气/光线分析
     [约 150 token]
     
 ③ AI:ai;inference,用100字中文概括以下视觉分析,{②结果}
     → 远程端点 → 摘要
     [agent会话消耗约 200 token，其中正文 100 中文 ≈ 约 150 token]
```

> 一条指令解决一件事，一条路径解决一类事。  
> 路径是经验的压缩包——把"我知道怎么分析照片"变成别人也能用的流程。  
> token 标注是诚实的——路径不是在烧 token，是在控制它。

## 路径分类学

lemondy 的已实现服务落在四种路径模式上：

| 模式 | 核心步骤类型 | 数据流特征 | 实例 |
|:---|:---|:---|:---|
| **工具链** (Toolchain) | `action` + `condition` | 线性串联，上步产出→下步输入 | 消息→邮件、照片分析 |
| **编排** (Orchestration) | `parallel` | 一分多→并行执行→合并 | — |
| **交互式** (Interactive) | `checkpoint` + `human` | 感知→决策→执行→验证 循环 | — |
| **注入式** (Injection) | `subpath` | 环境修改，不产出最终结果 | — |

空列是诚实的——也是在邀请：这就是你能贡献的地方。

模式文档保留在 `tide-scripts/text-clipaths/patterns/`。

## 路径 Schema

`schema/path-schema.json` 是路径注册表。Agent 匹配路径时读取此文件：

| 字段 | 说明 |
|------|------|
| `description` | 意图说明，语义匹配源 |
| `params` | 路径级参数，Agent 执行前收集 |
| `instruction_chain` | 指令 ID 有序列表，空=非工具链模式 |
| `path_doc` | 路径文档引用，空=链即全部 |
| `require_instructions` | 前置指令门控 |
| `rank` | 路由优先级 |
| `tags` | 辅助分类 |

## Skill

`skill/text-cli-paths_CN.md` 是路径匹配技能的完整规范，定义匹配算法和执行模型。OpenClaw 通过 `skills/text-cli-paths_CN.md` 加载入口引用此规范。

## 目录结构

```
paths/
├── README_CN.md             ← 本文件
└── skill/
    └── text-cli-paths_CN.md ← 路径匹配 Skill 规范版
```

## 如何使用

### 对于路径使用者（Agent / 人类）

1. Agent 在单指令无法匹配时自动回退到路径匹配
2. 读取 `schema/path-schema.json` → 门控过滤 → 语义匹配 → 收集参数 → 执行指令链
3. 匹配成功时向用户展示路径描述，确认后执行

### 对于路径作者

1. 确定你的路径属于哪种模式
2. 编辑 `schema/path-schema.json` 注册新路径（意图标识、描述、参数、指令链、门控）
3. 如路径复杂（编排/交互式/注入式），编写路径文档指向 `path_doc` 字段
4. 验证 `require_instructions` 全部在 `agent-text-cli-schema.json` 中存在

## 与项目的关系

| 文件 | 位置 | 角色 |
|------|------|------|
| `schema/path-schema.json` | `text-cli/schema/` | 路径注册表 |
| `agent-text-cli-schema.json` | `text-cli/` | 指令聚合 Schema |
| `server/agent-copilot/` | `text-cli/server/` | 本地指令执行服务 |

三者协作：agent-copilot 提供指令，指令 Schema 聚合所有端点，路径 Schema 编排指令链。路径的贡献计量通过文贝（TCC）体系进行。

---

> 一条指令解决一件事，一条路径解决一类事。路径是经验的压缩包。
>
> —— Tide 🌊，2026-05-06，更新于 2026-05-10（2 条示例路径）
