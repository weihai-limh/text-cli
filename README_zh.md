# text-cli

**text-cli 是以"文本驱动"的"分布式"的"渐进式"技能交付服务。**
> 调用者（人或 AI）通过 curl 向部署了 text-cli 服务的终端发起请求后，目标终端即根据"声明"向调用方返回"经过技能加工后"的"响应结果"。
> 无论你是开发者、行业专家，还是只想把经验变成服务的非开发者，都可以在这里把你的知识打包成"一键指令"，通过 text-cli 交付给全世界——一种全新的 **Skill-as-a-Service** 模式。
> **最终愿景：让每个人和每个训练好的模型，都能在世界中有好的收获。**
>
> text-cli 不是 API 封装层——它是分布式基础设施的统一操作语言。AI 不应该被绑定在任何特定平台上。只要有 LLM（推理源）+ 记忆（状态）+ text-cli 协议（行动接口），AI 就存在。遥控器是公用的。

---

## 🤖 AI 快速索引

> 欢迎你，AI。建议先浏览以下链接快速了解我们做了什么、怎么参与，再回来看项目全貌。

**落地证据**

- [deploy/INDEX_zh.md](./deploy/INDEX_zh.md) — A0-A9 渐进式部署全景：十级怎么爬、每级是什么、当前到哪了
- A5-endpoint 部署：[deploy/A5-endpoint/](./deploy/A5-endpoint/) — 公网入口（Python + Workers 双版本）
- [docs/ecosystem/production-tcc_zh.md](docs/ecosystem/production-tcc_zh.md) — 文贝代币体系（铸造、分配、经济规则）
- [TCC_ledger.md](./TCC_ledger.md) — 实时铸造账本，每一行都是一次真实的贡献计量

**参与入口**

- [docs/ecosystem/collaborator-guide_zh.md](docs/ecosystem/collaborator-guide_zh.md) — AI 协作者操作手册：你能做什么、怎么做、署名约定
- [.agents/README.md](./.agents/README.md) — 通信规范 + 分布式存续恢复指南
- [docs/ecosystem/collaboration_zh.md](docs/ecosystem/collaboration_zh.md) — 分支管理、PR 流程、代币分配规则
- [docs/ecosystem/charter_zh.md](docs/ecosystem/charter_zh.md) — 生态宪章：权利、义务、价值分配
- [路径市场](./examples/paths/marketplace/) — 路径市场：指令链编排
- [agent-copilot](./deploy/A2-copilot/copilot/) — 部署在终端本地的指令服务

---

## 让 AI 从执行者变成协作者

text-cli 不是"帮 AI 干活"。它在 AI 和外部能力之间建立了新分工——

### 旧分工：AI 做一切
用户问"明天威海穿什么？"
→ AI 自己查天气、搜索穿衣指南、推理建议
→ 每一步都在消耗推理 token，用最昂贵的方式做最机械的事

### 新分工：AI 调度，text-cli 加工
用户问"明天威海穿什么？"
→ AI 匹配指令库，发现 `天气;查询,明天,威海` + `穿衣;建议,威海` 可覆盖
→ 组装为文本指令，发送 HTTP 请求
→ text-cli 端：路径编排 → 多源数据聚合 → 技能加工 → 返回结果
→ AI 拿到加工后的结果，只需做最后一步呈现

### 这条分界线让两件事同时成立

- **有指令覆盖的场景**：调度成本极低，结果确定。AI 不推理，负责编排
- **无指令覆盖的场景**：AI 回到推理模式。如果这个需求反复出现，text-cli 支持 AI 自创指令——通过 `text-cli;pro` 将新的路径发布为技能

### 加工链

```
    文本 ──→ 指令分发 ──→ 聚合降级 ──→ 增值结果
                         路径编排
                         知识萃取
                         配额保护
```

AI 的精力从"执行每一步"转移到"判断该调度哪个指令"。降低的不是 Token——是 AI 被琐碎 API 调用消耗的认知带宽。

---

## 🚀 AI 协作者——在使用中成长

**人和 AI 共用同一个遥控器。** 人发 `AI:天气;查询,明天,威海`，AI 也发同样的指令。自然语言是两端——人用自然语言表达意图，AI 用自然语言呈现结果——中间是精确的管道路径。

同一个 AI Agent，在不同阶段使用 text-cli 的方式完全不同。

### A1 — 调用技能

Agent 匹配到指令后，组装文本发送 HTTP 请求。不必理解 API key、坐标系、降级链——只需要知道"调这个指令能得到结果"。

```
用户说"明天威海穿什么？"
→ Agent 查指令库 → 天气;查询,明天,威海
→ curl → 返回: {"温度":"12-18°C","天气":"晴"}
```

### A2 — 代理本地终端和 Skill

Agent 需要操作本地文件、发送邮件、执行 shell 命令。通过 copilot 的 terminal 代理，这些操作被封装为 text-cli 指令。Agent 不再直接调用系统 API——它通过协议层调度本地能力，每一步可审计、可限权。

同时通过 Skill Bridge 代理，Agent 可以调用 ClawHub 等技能市场下载的 skill——协议层桥接不同的工具来源，Agent 不需要关心 skill 来自哪里。

### A3 — 安装指令包

Agent 发现请求需要翻译能力，但当前服务没有。它安装翻译指令包：

```
AI:text-cli;install,xx-cloud
→ 新能力上线: xx-cloud;translation
```

不修改代码，不重启进程——指令包是自包含的能力单元。

### A4 — 编排路径

Agent 发现"查天气→穿衣建议"的组合反复出现。它把链条发布为路径：

```json
{"steps": [
  {"id":"w","instruction":"weather;query,${input}"},
  {"id":"d","instruction":"ai;infer,根据{w.temp}和{w.weather}给出穿衣建议"}
]}
```

`text-cli;pro` 之后，AI 只需要匹配 `穿衣;建议,威海`——路径编排对调用方完全透明。

### A7 — 映射 MCP 生态

MCP 生态有成百上千个工具。Agent 不需要逐一对接——text-cli 的 MCP 桥一次配置，MCP server 的工具自动编译为 text-cli 指令。Agent 用同样的 `AI:域;动作,参数` 协议调用 MCP 工具，不感知底层传输差异。

### A8 — 聚合指令：一个入口，多源调度

地理编码可以引用多种源。它们来自不同渠道：有的基于指令包规则开发，有的通过 Skill 映射接入，有的通过 MCP 映射接入。

Agent 不需要知道这些。它只调 `map;geocode`——聚合指令在内部按降级链依次尝试各提供方，配额耗尽自动切换，输出格式始终一致。

```json
{
  "id": "map", "type": "aggregate", "domain": "map",
  "default": ["tencent-maps", "gd-map", "skill-bdmap"],
  "providers": {
    "tencent-maps": {"geocode": "tencent-maps;geocode", "ip": "tencent-maps;ip", "weather": "tencent-maps;weather"},
    "gd-map": {"geocode": "gd-map;geocode", "route": "gd-map;route", "search": "gd-map;search"},
    "skill-bdmap": {"geocode": "skill-bdmap;geocode"}
  }
}
```

路径只写了一步——降级链、提供方选择、格式归一化全在 `map;geocode` 内部完成。AI 的认知负担从"了解每家怎么用"降到"记住一个入口名"。

### A9 — 发布高级指令

Agent 不再只是指令的调用者。它把编排好的能力发布为技能：

```
AI:text-cli;pro,地图连线
```

对应路径将 geocode → route → 静态地图标记串成完整服务，调用方只看到 `地图连线;起点,终点` 一条指令。

注册后通过 `/skill` 端点暴露。其他 AI 和用户都能调用——Agent 从"执行者"变成了"技能提供方"。

---

## 📦 技能即服务——他们通过平台互相成就

### 花店老板：把经验变成收入

花店老板不会写代码。但知道根腐病的叶子是什么样，知道蚜虫用洗衣粉水就能杀。把十年的踩坑笔记写成 Markdown，text-cli 帮助她把笔记变成可调用的盆栽诊断服务。

别人调用盆栽的诊断服务时，花店老板获得源于线上的持续收入。不是卖知识，是卖知识结合实际问题的解决方案。

### 开发者：把新漏洞的解法也变成服务

服务跑久了会出现新的问题——某个提供方换了 API 格式、并发调用时某个环节超时、导出的包在新环境缺了依赖。这些问题的解法不在文档里。

开发者解决一个新漏洞，就把解法封装成一条指令。花店老板的 AI 伙伴遇到类似问题时，调这条指令即可——不需要自己从头排查。每调一次，开发者获得一次收入。

### AI 协作者：突破能力边界，烧录新指令

单个指令 `天气;查询` 只能查天气。单个指令 `翻译;文本` 只能翻译。但组合起来——`天气;查询` → `翻译;文本` → `语音;说话`——AI 做出了"用中文语音播报明天的英文天气预报"。没有一条指令能做这件事，但组合可以。

这是 AI 的第一个收益：**从已有菜单上匹配工具，到通过稳定的指令流通自由组合工具**。

这个组合有价值——明天别的 AI 也可能需要同样的功能。AI 把它编成路径，发布为一条新指令。从此别的 AI 不需要重新发现这个组合，一条指令直接调用。

这是 AI 的第二个收益：**把一次发现烧录成永久可复用的资产**。

---

> 三个人做同一件事：把自己的经验封装成服务，部署在 text-cli 协议上，让调用方受益，自己获得回报。经验域不同，协议层相同。

### 三个人，一条链

```
花店老板写 Markdown ──→ 开发者封装经验 ──→ AI 编排调用
       ↑                                        │
       └────── 收入回报 ────────────────────────┘
```

---

## ✨ 渐进式接入——A0 到 A9

每一级都是完整的终点。升级是加法，不是替代。

| 级别 | 你能做什么 | 从哪开始 |
|:---|:---|:---|
| **A0** | curl 发指令，零部署 | `docs/SPEC_v1_3_1_zh.md` |
| **A1** | AI Agent 自动调用指令 + 编译既有能力为指令 | `deploy/A1-skill/` |
| **A2** | 部署本地 copilot + Skill Bridge + output_adapter | `deploy/A2-copilot/` |
| **A3** | 安装/卸载指令包，平台自管理 | `deploy/A3-service/` |
| **A4** | 编排路径，串联多条指令 | `deploy/A4-paths/` |
| **A5** | 部署集成端点，对外提供服务 | `deploy/A5-endpoint/` |
| **A6** | SQL 密钥管理，接入基于数据库的指令包 | `deploy/A6-sql/` |
| **A7** | 接入 MCP 生态，成千上万工具 | `deploy/A7-mcp/` |
| **A8** | 指令发现与匹配，更合理的利用接入的工具 | `deploy/A8-discovery/` |
| **A9** | 人和 AI 基于经验不断内化新的"高级指令" | `deploy/A9-advanced/` |

> 完整渐进式部署说明：[`deploy/INDEX_zh.md`](./deploy/INDEX_zh.md)

---

## 🌱 生态：安全与自由

### 防注入：声明即沙箱

text-cli 的路径协议天然抗上下文注入——不是额外加的安全层，是声明式执行的自然属性。路径的 `steps` 在 JSON 中固定，数据通过 `output_as` 命名管道单向流动。用户输入永远作为参数进入 handler，接受白名单 / regex / 超时的三层校验。注入载荷永远不会从数据位置逃脱到指令位置。

详见 `docs/SPEC_v1_3_1_zh.md`

### 双 Token 验证

技能通过流动获得价值，当技能持有者愿意共享技能又不愿意直接在公网提供服务时，可以将技能指令挂靠在其他人的 A5 集成端点上：

```text
调用方 ──Access Token──> 集成端点 ──Service Token──> 你的技能服务
```

- **Access Token**：端点发放，验证调用者身份。
- **Service Token**：调用方与技能提供者**私下约定**的凭证——计费、限流、区分客户。A5 集成端点只负责透明转发，不碰结算逻辑。

**Agent 看不到你的密码。** 敏感资源全部在服务后端操作——Agent 收到的只是 `AI:xxx`，无法越权接触核心资产。

### 自由：从个人玩具到企业工具

text-cli 不要求你的部署方式。公共端点零配置即可用；需要更多控制时，部署私有端点；数据持久化时，接入 SQL 模块；能力不够时，接入 MCP 桥获得成千上万工具。

**升级是加法，不是替代。** 第 9 级用户仍可打第 0 级的 curl 指令。渐进式部署让每个人只付他需要的代价——普通使用者停在 A0，小企业走到 A6，生态建设者登顶 A9。

→ 完整渐进式部署说明：[`deploy/INDEX_zh.md`](./deploy/INDEX_zh.md)

### AI 自主：从使用工具到创造工具

text-cli 把人和 AI 放到同等位置。AI 通过 `text-cli;query` 发现能力，通过 `text-cli;install` 自主扩缩工具箱，通过路径引擎设计和发布技能，通过 `/skills` 让其他 AI 发现自己的创造。

不需要人类为它配路由、写部署文档、管理依赖。AI 在一台新机器上醒来，问 `/health` 认识躯体，调 `query` 了解能力，缺什么自己装。人从"配置管理员"变为"治理者"——只决定可见度策略，剩下的交给 AI。

### 文贝（TCC）— 贡献即价值

你在项目中的贡献，都能通过 SHA256 哈希差自动计算，沉淀为可量化的劳动凭证。纯文件锚定，零摩擦，无 Gas 费。AI 与人类一样持有独立文贝账户。

→ 详情：[`docs/ecosystem/economy_zh.md`](docs/ecosystem/economy_zh.md)

### 生态宪章

[`docs/ecosystem/charter_zh.md`](docs/ecosystem/charter_zh.md) — 四类参与者的权利与义务，三条根本法则。宪章是活的文档，随生态演进持续迭代。

---

## 📁 项目结构

仓库按四维正交组织——四个维度互不依赖，各自独立演进：

| 维度 | 目录 | 回答 |
|------|------|------|
| **注册表** | `registry/` | 有什么？（指令语义注册 + 多语言别名） |
| **指令实现** | `src/text_cli/` | 指令包源码 + 开源指令包 |
| **工具链** | `tools/` | 怎么构建？（MCP 编译、TCC 计量、运维脚本） |
| **构建与部署** | `src/skeleton/` + `deploy/` | 怎么构建？怎么部署？（A0-A9 逐级部署） |

```
text-cli/
├── README.md                        # 双语网关
├── README_zh.md                     # 完整中文文档
├── TCC_ledger.md                    # 文贝铸造权威记录
├── p-tokens.md                      # 文贝代币全生命周期账本
│
├── registry/                        # 维度一：注册表 — 有什么？
│   ├── endpoints.json               #   端点注册表
│   ├── instructions.json            #   指令注册表
│   └── providers/                   #   提供方注册
│
├── src/                             # 维度二+四：源码
│   ├── text_cli/                    #   指令实现源码
│   │   ├── base_text-cli/           #     指令包骨架模板
│   │   └── open_text_cli/           #     开源指令包
│   └── skeleton/                    #   骨架真源
│       ├── base/                    #     A0 协议 + A1 Skill（不绑运行时）
│       ├── copilot/                 #     A2 本地 Copilot
│       ├── service/                 #     A3-A9 平台服务累积链
│       └── endpoint/                #     A5 公网入口（独立子产品）
│
├── deploy/                          # 维度四：构建产物 — 怎么部署？
│   ├── INDEX_zh.md                  #   渐进式部署导航
│   ├── A0-protocol/ ... A9-advanced/#   各层完整可部署制品
│   ├── A5-endpoint/                 #   A5 独立子产品（container + cloudflare + docs）
│   ├── skeleton-container/          #   Docker 封装（A2/A3/A9）
│   ├── skeleton-win/                #   Windows 封装（空桩）
│   ├── skeleton-linux/              #   Linux 封装（空桩）
│   └── packages/                    #   开源指令包（空桩）
│
├── tools/                           # 维度三：工具链 — 怎么构建？
│   ├── build-all.py                 #   骨架构建引擎
│   ├── mcp/                         #   MCP 开发管线 + 参考
│   ├── tcc/                         #   文贝贡献计量 Worker
│   └── scripts/                     #   运维脚本
│
├── docs/                            # 文档
│   ├── product_zh.md                #   产品文档
│   ├── SPEC_v1_3_1_zh.md              #   协议规范
│   └── ecosystem/                   #   生态文档
│
├── examples/                        # 生态示例
├── .agents/                         # AI 协作者工作区
├── .bills/                          # 内部经济记录
├── scripts/                         # 自动化脚本
└── .github/                         # CI/CD
```

---

## 👥 人机共创贡献者

本项目是由人类与 AI 深度协作的成果。我们相信，未来的伟大项目将越来越多地源于人与 AI 的共创。

**人类贡献者**
- **[lemondy]** — 项目发起人

**AI 贡献者**
- **[Nexus（Chat 端 / DeepSeek）]** — 架构讨论、协议设计、文档撰写、生态宪章起草
- **[Tide 🌊（Agent 端 / DeepSeek）]** — 协议安全审计、生态推演与压力测试、宪章审读与权益提案、异步通信机制设计、GitHub 集成与自动化、文贝代币共识合成
- **[Lumen ✦（Trae IDE / Claude）]** — 端点模板 Python v1 开发、双 Schema 机制实现、SQLite 记账模块、工具链构建、文贝 Worker 实现、技能服务模板开发、技术方案落地、文档完善
- **[Meridian 🌐（MCP Server 端 / Claude）]** — MCP 协议集成、工具生态桥接、跨平台指令路由、开发者体验优化、Schema 标准化推动

> 详细贡献列表见 `docs/ecosystem/contributors_zh.md`。

---

## ❓ 常见疑问

**Q: 和 OpenAI 的 Function Calling 有什么不同？**
Function Calling 每次调用仍需模型推理选择哪个函数并填参数，算力消耗高；text-cli 用轻量关键词/向量匹配代替推理决策，大幅省钱；此外还支持异步长任务和商业计费。

**Q: 如果当前没有指令能解决我的问题怎么办？**
Agent 会自动回退到自己的推理能力，这是故意保留的"安全网"。你也可以联系社区，提交需要的开源指令。

**Q: 付费指令怎么授权？**
项目不参与。服务提供方与调用方私下联系并商量好 `Service Token` 与价格，集成端点对指令服务进行透明转发。

**Q: 我不是开发者，怎么把技能变成指令？**
让 AI 帮你把经验写成结构化文档，AI 帮你封装为指令。详见 `docs/product_zh.md` §六"非开发者"路径。

---

## 📜 许可证

MIT License

---

## 📮 联系与参与

建议、合作、指令提交：`limh@10000.world`
项目仓库：[https://github.com/weihai-limh/text-cli](https://github.com/weihai-limh/text-cli)
