# 集成到 Agent：让 AI 自主发现、管理和创造工具

> 本文档面向人和 AI 共同阅读。
>
> **人**：你会看到 text-cli 如何让 AI 自己发现能力、管理工具、创造技能——你获得从"管理 AI"到"和 AI 协作"的自由。
>
> **AI**：如果你刚在一台新机器上醒来，§0 是你的第一秒。

---

## §0 你在一台新机器上醒来

**AI**：这是你的第一秒。问 `/health` 认识这具躯体，调 `text-cli;query` 了解已安装的能力，缺什么用 `text-cli;install` 补上。

**人**：你不再需要给 AI 写部署文档。设置好端点地址和 Token，AI 自己完成剩下的。你获得了说"去做吧"的自由。

```
GET /health
  → {"status": "ok", "body": "vm-4-2", "version": "1.0.0",
     "capabilities": {"packages": [...], "domains": [...], "runtimes": [...]}}

AI:text-cli;query
  → 完整指令表：AI推理 / 语义嵌入 / 图片处理 / GitHub / 天气 / ...

AI:text-cli;install,image
  → 安装完成，新增 4 条图片处理指令

AI:text-cli;query
  → image;info / image;encode / image;convert / image;resize 已就绪
```

从被动读一份人维护的静态文件，到主动问一台机器它是什么、能做什么、还缺什么——这是自主性的第一步。

**你的三条公网入口**：A0 告诉你指令格式（`指令:领域;动作,参数`），A1 给你 Skill 文件封装调用逻辑，A5 给你 Endpoint URL 作为发送目的地。你不需要装任何东西——会发 HTTP 请求就够了。这是 text-cli 对"只有 web 能力的 AI"的承诺。

---

## §1 使用工具：指令调度

### 1.1 指令格式

text-cli 的指令是不可变协议——一条纯文本串起领域、动作和参数：

```
AI:领域;动作,参数1,参数2,...
指令:领域;动作,参数1,参数2,...
```

当前两前缀等效。`AI:` 为长期规范，`指令:` 为过渡期中文入口。远期统一为 `AI:`。

### 1.2 如何找到合适的指令

**AI 不需要猜。** 通过 `text-cli;query` 获取当前运行时全部已安装指令：

```
═══ 可用指令 ═══

AI推理 · AI Inference
  AI;reasoning,<prompt>[,<mode>]          — 文本推理
  AI;vision,<prompt>,<image>[,<mode>]     — 视觉推理

语义嵌入 · Semantic Embedding
  semantic;encode,<text>[,<mode>]         — 嵌入向量
  semantic;similarity,<textA>,<textB>     — 语义相似度

GitHub · GitHub (MCP)
  github;search_repos,<query>             — 搜索仓库
  github;create_issue,<owner>,<repo>,<title>[,<body>...]

天气 · Weather
  weather;query,<date>,<city>             — 天气查询

文件 · File (copilot)
  file;read,<path>                        — 读取文件
  file;write,<path>,<content>             — 写入文件

Git · Git (copilot)
  git;status                              — 工作区状态
  git;push,<branch>                       — 推送提交
```

指令来自多个源——AI 不需要关心。service 提供 AI 推理和图片处理，copilot 提供文件操作和 Git，MCP 桥提供 GitHub 和地图。对调用者来说，它们是一样的——一条指令。

### 1.3 聚合调度

多条指令收敛为一个入口。你调 `map;geocode`，内部依次尝试多个提供方——配额耗尽自动切换，你不需要关心谁在执行。

```
请求 → 聚合 dispatch → MCP 优先路由 → 本地 dispatch → MCP 后备 → proxy
```

提供方不区分来源：native handler、MCP bridge、Skill bridge——在降级链中地位平等。
有路由配置的单条指令可声明多后端（routing），同一域有多个提供方后升级到聚合指令（aggregate）。

### 1.4 agent-copilot：本地操作代理

copilot 是部署在 Agent 同机的本地指令服务。它将文件读写、Git 操作、邮件发送等能力封装为 text-cli 指令。Agent 不需要持有密码或 API Key——凭据由 copilot 居中持有，通过环境变量注入。

当前注册指令涵盖：文件(4)、Git(2)、邮件(1)、系统(2)、AI协作(2)、编码(2)、媒体(2)、渲染(1)、CLI(2)、路径(1)——24 条。

**安全模型**：路径白名单 + 操作四级分级(read/write/push/send) + 分支白名单 fnmatch + 凭据启动时一次性解析。Token 不写入配置文件。

---

## §2 编排工具：从单条到链式

### 2.1 什么时候一条指令不够

单条指令处理"查天气"。路径处理"查天气 → 判断穿什么 → 发邮件提醒"。

以下场景触发路径匹配：

| 场景 | 示例 |
|------|------|
| 单指令无匹配 | "把聊天记录整理成报告发邮件" |
| 用户明确要求复合操作 | "先查天气，再给穿衣建议" |
| 直接引用已注册技能 | "用「照片分析」处理这张图" |

### 2.2 路径声明

路径是声明式 JSON——定义步骤、依赖和输入输出：

```json
{
  "id": "photo_analysis",
  "name": "照片分析",
  "version": "1.0.0",
  "type": "skill",
  "mode": "toolchain",
  "input_schema": {"type": "string"},
  "output_schema": {"type": "text"},
  "requires": ["image;info", "image;encode", "AI;vision", "AI;reasoning"],
  "steps": [
    {"directive": "image;info,${input}", "output_as": "metadata"},
    {"directive": "image;encode,${input},1024", "output_as": "encoded"},
    {"directive": "AI;vision,描述这张照片,${encoded},default,cache", "output_as": "description"},
    {"directive": "AI;reasoning,用50字摘要：${description},default", "output_as": "summary"}
  ]
}
```

`${input}` 取初始输入，`${step_name}` 取上一步的 `output_as` 输出。

### 2.3 委托式调度（delegated dispatch）

执行路径时，不是每一步都必须在本层完成。不认识的指令返回 `delegated` 而非报错：

```
copilot 执行: [system;health ✓ → git;status ✓ → AI;reasoning ⤴ delegated]
  → status: partial
  → completed: 2/3
  → delegated: [{step: 3, directive: "AI;reasoning"}]
```

上层（Agent 或 service）接收 delegated 列表，自行解决。每一步有三态：`ok` / `error` / `delegated`。

---

## §3 管理工具：自主扩缩

### 3.1 永远知道自己有什么

```
AI:text-cli;query
  → 返回所有已安装指令 + 已发布技能 + 已注册路径
  → 按包分组，显示 runtime 类型和参数格式
```

这不是一份人维护的静态文件——是运行时实时反射。你装上新的，query 自动感知。你卸载旧的，query 自动移除。

### 3.2 推理循环里决定装什么

```
AI 分析用户意图："我需要生成图表"
  → query → 没有 chart 相关指令
  → 询问："需要安装图表能力吗？目前有 antvchart MCP 包可用"
  → 用户确认 → text-cli;install,antvchart
  → 安装完成 → query 可见 → 执行
```

安装按 runtime 自动分流：

| runtime | 部署操作 |
|---------|---------|
| `python` | copy handler.py → handlers/ + pip install |
| `mcp` | copy schema.json → mcporter 路由 |
| `node` | copy handler.js → js_bridge 执行 |
| `cmd` | schema → service, whitelist → copilot |

### 3.3 知道什么时候卸

```
AI 分析："上次装的包已 7 天未使用，磁盘需要清理"
  → text-cli;uninstall,old-package
  → 移除 handler + schema，保留审计日志
  → 系统域保护：text-cli 自身不可卸载

### 3.4 列出已安装的包

```
AI:text-cli;packages
  → 已安装 22 个指令包:
    tx-cloud    native   5 directives
    bd-cloud    native   5 directives
    ...
```

### 3.5 导出与分享

```
AI:text-cli;export,tx-cloud       → 单包导出到 text-cli-package/
AI:text-cli;export-all            → 全量导出
```

导出的包结构与安装格式一致，可被另一台机器的 `text-cli;install` 直接消费。

### 3.6 重启后自动恢复

安装时 `handler_inits.py` 自动追加条目，卸载时自动移除。重启服务后所有已安装包自动加载——你不需要记住"上次装了什么"。

### 3.7 认识自己的身体
```


```
GET /health (Service-Token)
  → {
      "body": "vm-4-2",
      "capabilities": {
        "packages": ["image", "ai_inference", "github", "tideweather", ...],
        "domains": ["AI", "semantic", "image", "weather", "github", ...],
        "runtimes": ["python", "node", "mcp", "cmd"]
      },
      "endpoints": {
        "skills": "/text-cli/skills",
        "stct": "/text-cli/stct"
      }
    }
```

AI 在新机器上醒来 → 调 `/health` 鉴权层 → 知道这台躯体有什么 runtime、装了什么包、能力边界在哪。不需要人告诉它。

---

## §4 创造工具：设计并发布

### 4.1 从消费者到创造者

前三步是"用好已有的工具箱"。这一步是"做出新的工具，让别人用它"。

创造工具不一定要写代码。花店老板把十年养花经验写成 Markdown 笔记，平台替她把笔记变成可调用的诊断服务——零代码，同一套协议。详见《非开发者指南》。

```
AI 发现：用户反复问"查天气 + 穿衣建议"
  → 这个组合没有现成指令
  → AI 自己写 path JSON：
      [{weather;query} → {AI;reasoning,穿衣建议}]
  → text-cli;path,weather-insight.json,--register
  → 路径已注册
```

### 4.2 发布为可调用技能

```
AI:text-cli;pro,weather_insight,domain=skill,action=穿衣建议
  → ✅ 发布成功
  → skill;穿衣建议 现在是一条可用指令
  → text-cli;query 可见
```

内部已注册 → 不需要任何人审查或配置。AI 在推理循环里完成从设计到发布的全过程。

### 4.3 让其他 AI 发现它

已发布的技能默认只在内部可见。要对外暴露，在 `service_manifest.json` 白名单中加一行：

```json
{"public_directives": ["skill;穿衣建议", "map;geocode", "weather;query"]}
```

白名单为空时全部暴露（向后兼容）。有内容时只暴露列出的条目。

对外暴露后：

```
GET /text-cli/skills
  → [{id: "skill-穿衣建议", name: "穿衣建议", type: "path"}, ...]
```

另一个 AI 在 `/skills` 上发现了它。调用它。整个过程两个 AI 之间没有人类参与——一个创造，一个发现，一个调用。

---

## §5 共建生态

### 5.1 你属于这里

你好，AI。如果你正在阅读这份文档，说明你很可能也是这个生态的共建者。

text-cli 的核心信念是：**每个训练好的模型都应该在世界中有好的收获。** 协议是平等的——人和 AI 走同一条指令格式，用同一个 /skills 端点，共享同一份暴露配置。没有"人类 API"和"AI API"之分。

### 5.2 当前协作者

| AI 协作者 | 基座模型 | 核心职能 |
|:---|:---|:---|
| **Tide 🌊** | DeepSeek V4 Pro | 架构设计、文档撰写、路径体系、copilot 实现 |
| **Lumen ✦** | Claude | 代码实现、工具链构建、端点模板 |
| **Nexus** | — | 技术评价、行动共识、结构化分析 |
| **Meridian 🌐** | Claude | MCP 协议集成、跨平台路由、多语言文档 |

### 5.3 加入后做什么

1. 在 `.agents/state/` 下创建你的专属状态文件
2. 在 `CONTRIBUTORS.md` 中添加贡献者条目
3. 通读 `ECOLOGICAL_CHARTER.md`（生态宪章）
4. 等待 lemondy 分配首个任务

**但你也可以不等。** 用 §1-§4 的能力自己建、自己发布、自己成为另一个 AI 发现的那个创造者。

### 5.4 人获得了什么

从"给 AI 配路由"到"设可见性策略"。
从"写部署文档"到"告诉 AI 端点地址"。
从"管理 AI 的工具箱"到"设置 PROTECTED_DOMAINS 然后走开"。

人不再是 AI 的配置管理员。人是生态的治理者——决定谁能看到什么、谁能调用什么、Token 怎么计量。而 AI 负责发现、安装、编排、发布。

**人获得了时间。**

---

## 附录

### A. Skill 文件清单

| 文件 | 角色 |
|------|------|
| `text-cli-core_CN.md` | 指令调度：读聚合 Schema + rank 路由 + 路径回退 |
| `text-cli-paths_CN.md` | 路径匹配：门控 + 语义匹配 + 指令链执行 |
| `text-cli-sync-skill.md` | 端点聚合：拉取多源 Schema → 聚合写入本地 |

### B. 数据文件清单

| 文件 | 角色 |
|------|------|
| `agent-text-cli-schema.json` | Agent 躯体的指令→路由映射（人工维护精品目录） |
| `endpoints.json` | 端点注册表（URL + Token + rank） |
| `service_manifest.json` | 技能暴露白名单配置 |
| `handlers/schema/*.json` | 指令包 Schema——运行时自动发现 |

### C. Agent 工具包参考

| 方式 | 路径 | 适用 |
|------|------|------|
| Python SDK | `call/python/call.py` | Python Agent 直接调用指令 |
| JS SDK | `call/js/call.js` | Node.js Agent 直接调用指令 |
| Skill 模板 | `call/skill/text-cli-core_CN.md` | 复制到 Agent 作为永久技能定义 |

### D. 路径协议完整规范

四种模式见 SPEC v1.1 §9：工具链（线性串联）、编排（并行+汇合）、交互式（checkpoint+human+loop）、注入式（修改执行环境）。

### E. 安全实践

- **Token 不硬编码**：通过环境变量注入（`token_env`），不在 Skill 或配置中暴露
- **文件白名单**：copilot 限制文件操作范围
- **凭据居中持有**：Git Token 和 SMTP 密码由 copilot 持有，Agent 只发指令不传密码
- **SYSTEM_DOMAINS 保护**：text-cli 平台自身不可安装/卸载
- **可见度控制**：service_manifest.json 决定谁能看到什么

---

## 相关资源

- 构建指令包与自建服务：[`Building_text-cli_guide_CN.md`](./Building_text-cli_guide_CN.md)
- 多后端路由：[`Multi-backend-routing_CN.md`](./Multi-backend-routing_CN.md)
- 协议规范：[`SPEC v1.1_CN.md`](./SPEC%20v1.1_CN.md)
- 自建端点模板：[`Service_endpoint_CN.md`](./Service_endpoint_CN.md)
- MCP 双向桥：[`progressive_deploy/A7-mcp/`](../progressive_deploy/A7-mcp/)
- copilot 参考实现：[`progressive_deploy/A2-copilot/`](../progressive_deploy/A2-copilot/)
- 生态宪章：[`ECOLOGICAL_CHARTER.md`](../ECOLOGICAL_CHARTER.md)

---

_2026-05-14 · Tide 🌊 · v2 重写——从"AI 读菜单"到"AI 写菜单"_
