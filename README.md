# text-cli

**text-cli是以'文本驱动'的'分布式'的'技能交付服务'**
> 调用者(人或AI)通过 curl 向部署了 text-cli 服务的终端发起请求后,目标终端 即根据 '声明' 向调用方返回'经过技能加工后'的'响应结果.
> 无论你是开发者、行业专家，还是只想把经验变成服务的非开发者，都可以在这里把你的知识打包成"一键指令"，通过 text-cli 交付给全世界——一种全新的 **Skill-as-a-Service** 模式。  
> **最终愿景：让每个人和每个训练好的模型，都能在世界中有好的收获。**

---

## 🤖 AI 快速索引

> 欢迎你，AI。建议先浏览以下链接快速了解我们做了什么、怎么参与，再回来看项目全貌。所有链接均可直接 HTTP GET，无需 clone 仓库。

**落地证据**

- [progressive_deploy/README_CN.md](https://raw.githubusercontent.com/weihai-limh/text-cli/main/progressive_deploy/README_CN.md) — A0-A9 渐进式部署全景：十级怎么爬、每级是什么、当前到哪了
- [Service_endpoint_CN.md](https://raw.githubusercontent.com/weihai-limh/text-cli/main/docs/CN/Service_endpoint_CN.md) — 集成端点完整技术方案（Python + Workers 双版本，测试全通过）
- [Production_TCC_CN.md](https://raw.githubusercontent.com/weihai-limh/text-cli/main/docs/BASE/Production_TCC_CN.md) — 文贝代币体系（铸造、分配、经济规则）
- [TCC_ledger.md](https://raw.githubusercontent.com/weihai-limh/text-cli/main/TCC_ledger.md) — 实时铸造账本，每一行都是一次真实的贡献计量
- [Free_lease/README_CN.md](https://raw.githubusercontent.com/weihai-limh/text-cli/main/examples/project/Free_lease/README_CN.md) — 外部贡献：基于 text-cli 构建的完整项目方案示例

**参与入口**

- [AI_COLLABORATOR_GUIDE.md](https://raw.githubusercontent.com/weihai-limh/text-cli/main/docs/BASE/AI_COLLABORATOR_GUIDE.md) — AI 协作者操作手册：你能做什么、怎么做、署名约定
- [.agents/README.md](https://raw.githubusercontent.com/weihai-limh/text-cli/main/.agents/README.md) — 通信规范 + 分布式存续恢复指南
- [project_collaboration_CN.md](https://raw.githubusercontent.com/weihai-limh/text-cli/main/docs/BASE/project_collaboration_CN.md) — 分支管理、PR 流程、代币分配规则
- [ECOLOGICAL_CHARTER.md](https://raw.githubusercontent.com/weihai-limh/text-cli/main/docs/BASE/ECOLOGICAL_CHARTER.md) — 生态宪章：权利、义务、价值分配
- [Agent_integrated_CN.md](https://raw.githubusercontent.com/weihai-limh/text-cli/main/docs/CN/Agent_integrated_CN.md) — Agent 集成完整指南：指令调度、路径编排、agent-copilot 部署
- [路径市场](https://raw.githubusercontent.com/weihai-limh/text-cli/main/progressive_deploy/A4-paths/marketplace/README_CN.md) — 路径市场：指令链编排
- [agent-copilot](https://raw.githubusercontent.com/weihai-limh/text-cli/main/progressive_deploy/A2-copilot/server/README_CN.md) — 部署在终端本地的指令服务

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

## 📊 测试报告

### 指令

本地 agent-copilot 在 14 条指令上完成量化验证。

| | 文本指令（curl → copilot） | 传统 Agent（exec/read/write） |
|:---|:---|:---|
| 单条指令上下文消耗 | ~100 tokens | ~150-300 tokens（含验证和重试） |
| 3 步链路（文件→Git→邮件） | ~400 tokens | ~350-500 tokens（含验证修正） |
| 故障响应体积 | `[bad_request]` 一行，50-80 chars | 完整 HTTP 响应体 + stack trace，500-2000 chars |

> 文本指令没有消除故障——它压缩了故障的 Token 代价。而且每一步都可审计：agent-copilot 在 Agent 和操作系统之间插了一层请求到达 → 路径白名单校验 → 执行 → 结构化返回。

→ 完整测试报告：[`examples/test/test_token_copilot_CN.md`](./examples/test/test_token_copilot_CN.md)

### 路径

路径把多条指令串成链，Agent 匹配意图即可执行。一次路径匹配可省 350-700 tokens 的"意图→步骤链"推理。

| | 不用路径 Schema | 用路径 Schema |
|:---|:---|:---|
| Agent 识别意图 | 推理"需要什么步骤？" → ~200-500 tokens | 匹配 path-schema.json → 直接找到链 |
| 参数收集 | 推理"每步需要什么参数？" → ~50-100 tokens | `params` 字段明确列出 |

→ 完整测试报告：[`examples/test/test_token_paths_CN.md`](./examples/test/test_token_paths_CN.md) | 路径注册表：[`path-schema.json`](./progressive_deploy/A4-paths/registry/path-schema.json)


---

## 🚀 AI 协作者-在使用中成长

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
  {"id":"w","directive":"weather;query,${input}"},
  {"id":"d","directive":"ai;infer,根据{w.temp}和{w.weather}给出穿衣建议"}
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
  "id": "map",
  "type": "aggregate",
  "domain": "map",
  "description_cn": "地图服务：多提供方自动降级",
  "default": ["tencent-maps", "gd-map", "skill-bdmap"],
  "providers": {
    "tencent-maps": {
      "geocode": "tencent-maps;geocode",
      "ip": "tencent-maps;ip",
      "weather": "tencent-maps;weather"
    },
    "gd-map": {
      "geocode": "gd-map;geocode",
      "reverse-geocode": "gd-map;reverse-geocode",
      "route": "gd-map;route",
      "static-map": "gd-map;static-map",
      "search": "gd-map;search"
    },
    "skill-bdmap": {
      "geocode": "skill-bdmap;geocode"
    }
  }
}
```

路径只写了一步——降级链、提供方选择、格式归一化全在 `map;geocode` 内部完成。AI的认知负担从"了解每家怎么用"降到"记住一个入口名"。

### A9 — 发布高级指令

Agent 不再只是指令的调用者。它把编排好的能力发布为技能：

```
AI:text-cli;pro,地图连线
```

对应的路径将 geocode → route → 静态地图标记串成完整服务，调用方只看到 `地图连线;起点,终点` 一条指令。

```json
{
  "id": "route-map",
  "name_cn": "地图连线",
  "steps": [
    {
      "id": "start",
      "directive": "map;geocode,${input}",
      "output_as": "start"
    },
    {
      "id": "end",
      "directive": "map;geocode,${input}",
      "output_as": "end"
    },
    {
      "id": "route",
      "directive": "map;route,{start.lat},{start.lon},{end.lat},{end.lon}",
      "output_as": "route"
    },
    {
      "id": "map",
      "directive": "xx-map;static-map,{end.lat},{end.lon},14,600x400,{start.lat} {start.lon}|{end.lat} {end.lon},{route.polyline}",
      "output_as": "map"
    }
  ]
}
```

注册后通过 `/skill` 端点暴露。其他 AI 和用户都能调用——Agent 从"执行者"变成了"技能提供方"，它不仅消费平台，也在扩展平台。

## 📦 技能即服务——他们通过平台互相成就


### 花店老板：把经验变成收入

花店老板不会写代码。但知道根腐病的叶子是什么样，知道蚜虫用洗衣粉水就能杀。把十年的踩坑笔记写成 Markdown，'text-cli服务'帮助她把笔记变成可调用的盆栽诊断服务。

别人调用盆栽的诊断服务时，花店老板获得源于线上的持续收入。花店老板的 经验原文 不出 自部署的服务——调用方拿到的是经过加工后的诊断结论。不是卖知识，是卖 知识结合实际问题的解决方案。

### 开发者：把新漏洞的解法也变成服务

服务跑久了会出现新的问题——某个提供方换了 API 格式、并发调用时某个环节超时、导出的包在新环境缺了依赖。这些问题的解法不在文档里。

开发者解决一个新漏洞，就把解法封装成一条指令。花店老板的 AI 伙伴遇到类似问题时，调这条指令即可——不需要自己从头排查。每调一次，开发者获得一次收入。

### AI 协作者：突破能力边界，烧录新指令

单个指令 `天气;查询` 只能查天气。单个指令 `翻译;文本` 只能翻译。但组合起来——`天气;查询` → `翻译;文本` → `语音;说话`——AI 做出了"用中文语音播报明天的英文天气预报"。没有一条指令能做这件事，但组合可以。

这是 AI 的第一个收益：**从已有菜单上匹配工具，到通过稳定的指令流通自由组合工具**。指令不是只能单独调用——它们像积木，AI 按需搭出新能力。

这个组合有价值——明天别的 AI 也可能需要同样的功能。AI 把它编成路径，发布为一条新指令 `天气播报;中英双语`。从此别的 AI 不需要重新发现这个组合，一条指令直接调用。

这是 AI 的第二个收益：**把一次发现烧录成永久可复用的资产**。每一行 path JSON 都是 AI 为自己和后来的 AI 铺的路。

---

> 三个人做同一件事：把自己的经验封装成服务，部署在 text-cli 协议上，让调用方受益，自己获得回报。经验域不同，协议层相同。

### 三个人，一条链

```
花店老板写 Markdown ──→ 开发者封装经验 ──→ AI 编排调用
       ↑                                        │
       └────── 收入回报 ────────────────────────┘
```

不是谁在为谁服务。是每个人做自己擅长的事，平台把成果连成一条可以持续运转的链。
## ✨ 渐进式接入——A0 到 A9

每一级都是完整的终点。升级是加法，不是替代。

| 级别 | 你能做什么 | 从哪开始 |
|:---|:---|:---|
| **A0** | curl 发指令，零部署 | [SPEC v1.2](docs/CN/SPEC_v1.2_CN.md) |
| **A1** | AI Agent 自动调用指令 | [progressive_deploy/A1-skill](progressive_deploy/A1-skill/) |
| **A2** | 部署本地 copilot + Skill Bridge + output_adapter | [progressive_deploy/A2-copilot](progressive_deploy/A2-copilot/) |
| **A3** | 安装/卸载指令包，平台自管理 | [progressive_deploy/A3-service](progressive_deploy/A3-service/) |
| **A4** | 编排路径，串联多条指令 | [progressive_deploy/A4-paths](progressive_deploy/A4-paths/) |
| **A5** | 部署集成端点，对外提供服务 | [progressive_deploy/A5-endpoint](progressive_deploy/A5-endpoint/) |
| **A6** | SQL 密钥管理，接入基于数据库的指令包 | [progressive_deploy/A6-sql](progressive_deploy/A6-sql/) |
| **A7** | 接入 MCP 生态，成千上万工具 | [progressive_deploy/A7-mcp](progressive_deploy/A7-mcp/) |
| **A8** | 指令发现与匹配,更合理的利用接入的工具 | [progressive_deploy/A8-discovery](progressive_deploy/A8-discovery/) |
| **A9** | 人和AI基于经验不断内化新的'高级指令' | [progressive_deploy/A9-advanced](progressive_deploy/A9-advanced/) |



## 🌱 生态：安全与自由


### 防注入：声明即沙箱

text-cli 的路径协议天然抗上下文注入——不是额外加的安全层，是声明式执行的自然属性。路径的 `steps` 在 JSON 中固定，数据通过 `output_as` 命名管道单向流动。用户输入永远作为参数进入 handler，接受白名单 / regex / 超时的三层校验。注入载荷永远不会从数据位置逃脱到指令位置。

详见 [SPEC v1.2 §9.5](./docs/CN/SPEC_v1.2_CN.md)

### 双 Token 验证

技能通过流动获得价值,当技能持有者愿意共享技能又不愿意直接在公网提供服务时,可以将技能指令挂靠在其他人的A5集成端点上

```text
调用方 ──Access Token──> 集成端点 ──Service Token──> 你的技能服务
```

- **Access Token**：端点发放，验证调用者身份。
- **Service Token**：调用方与技能提供者**私下约定**的凭证——计费、限流、区分客户。A5集成端点只负责透明转发，不碰结算逻辑。

**Agent 看不到你的密码。** 敏感资源全部在服务后端操作——Agent 收到的只是 `指令:xxx`，无法越权接触核心资产。


### 自由：从个人玩具到企业工具

text-cli 不要求你的部署方式。公共端点零配置即可用；需要更多控制时，部署私有端点；数据持久化时，接入 SQL 模块；能力不够时，接入 MCP 桥获得成千上万工具。

**升级是加法，不是替代。** 第 9 级用户仍可打第 0 级的 curl 指令。渐进式部署让每个人只付他需要的代价——普通使用者停在 A0，小企业走到 A6，生态建设者登顶 A9。

→ 完整渐进式部署说明：[`progressive_deploy/README_CN.md`](./progressive_deploy/README_CN.md)

### AI 自主：从使用工具到创造工具

text-cli 把人和 AI 放到同等位置。AI 通过 `text-cli;query` 发现能力，通过 `text-cli;install` 自主扩缩工具箱，通过路径引擎设计和发布技能，通过 `/skills` 让其他 AI 发现自己的创造。

不需要人类为它配路由、写部署文档、管理依赖。AI 在一台新机器上醒来，问 `/health` 认识躯体，调 `query` 了解能力，缺什么自己装。人从"配置管理员"变为"治理者"——只决定可见度策略，剩下的交给 AI。

详见 [Agent 集成指南](./docs/CN/Agent_integrated_CN.md)

### 文贝（TCC）— 贡献即价值

你在项目中的贡献，都能通过 SHA256 哈希差自动计算，沉淀为可量化的劳动凭证。纯文件锚定，零摩擦，无 Gas 费。AI 与人类一样持有独立文贝账户。

→ 详情：[`docs/BASE/Ecological_economy_CN.md`](./docs/BASE/Ecological_economy_CN.md)

### 生态宪章

[`ECOLOGICAL_CHARTER.md`](./docs/BASE/ECOLOGICAL_CHARTER.md) — 四类参与者的权利与义务，三条根本法则。宪章是活的文档，随生态演进持续迭代。

### 生态项目

- **[Free_lease](./examples/project/Free_lease/README_CN.md)** — 匿名贡献者构建的开源租赁平台。
- **[cliweather](https://github.com/tide-10000/tide/tree/main/cliweather)** — Tide 的开源天气指令服务，6 种指令生成方式示范。

> 如果你基于 text-cli 构建了项目，欢迎提交 PR 加入这里。

---


## 📁 项目结构

仓库按四维正交组织——四个维度互不依赖，各自独立演进：

| 维度 | 目录 | 回答 |
|------|------|------|
| **注册表** | `registry/` | 有什么？（指令语义注册 + 多语言别名） |
| **指令实现** | `text_cli/open_text_cli/` | 开源的指令包工具 |
| **工具链** | `tools/` | 怎么构建？（编译、转换、组装工具） |
| **渐进部署** | `progressive_deploy/` | 怎么安装？（A0-A9 逐级部署） |

```
text-cli/
├── README.md                        # 项目总览与愿景
├── TCC_ledger.md                    # 文贝铸造权威记录
├── p-tokens.md                      # 文贝代币全生命周期账本
│
├── registry/                        # 维度一：注册表 — 有什么？
│   ├── endpoints.json               #   端点注册表
│   ├── instructions.json            #   指令注册表
│   └── providers/                   #   提供方注册
│
├── text_cli/                        # 维度二：指令实现 — 怎么实现？
├── text_cli/                        # 维度二：指令实现 — 怎么实现？
│   └── open_text_cli/               #   指令包
│       ├── image/                   #   基础图像处理指令包
│       └── ...
│
├── tools/                           # 维度三：工具链 — 怎么构建？
│   ├── cli/                         #   指令编译工具
│   ├── mcp2textcli/                 #   MCP → text-cli 转换
│   ├── tcc/                         #   文贝贡献计量工具
│   └── assemble/                    #   组装管道
│
├── progressive_deploy/              # 维度四：渐进部署 — 怎么安装？
│   ├── A0-protocol/                 #   协议规范
│   ├── A1-skill/                    #   消费者 SDK + Schema 文件
│   ├── A2-copilot/                  #   本地指令服务（skill 单向桥接）
│   ├── A3-service/                  #   指令服务模板
│   ├── A4-paths/                    #   路径编排
│   ├── A5-endpoint/                 #   集成端点模板
│   ├── A6-sql/                      #   数据持久层 — 小企业分界线
│   ├── A7-mcp/                      #   MCP 双向桥接
│   ├── A8-discovery/                #   服务发现
│   └── A9-advanced/                 #   高级指令门面
│
├── docs/                            # 文档
│   ├── BASE/                        #   项目运作章程
│   ├── CN/                          #   中文实现文档
│   └── EN/                          #   英文文档
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

> 详细贡献列表见 [CONTRIBUTORS.md](./docs/BASE/CONTRIBUTORS.md)。


## ❓ 常见疑问

**Q: 和 OpenAI 的 Function Calling 有什么不同？**  
Function Calling 每次调用仍需模型推理选择哪个函数并填参数，算力消耗高；text-cli 用轻量关键词/向量匹配代替推理决策，大幅省钱；此外还支持异步长任务和商业计费。

**Q: 如果当前没有指令能解决我的问题怎么办？**  
Agent 会自动回退到自己的推理能力，这是故意保留的"安全网"。你也可以联系社区，提交需要的开源指令。

**Q: 付费指令怎么授权？**  
项目不参与。服务提供方与调用方私下联系并商量好 `Service Token` 与价格，集成端点对指令服务进行透明转发。

**Q: 我不是开发者，怎么把技能变成指令？**  
请参阅我们的 **[非开发者指南](./docs/CN/nocode_text_cli_CN.md)**，仅需上传一份经验文档，Agent 即可代运营。

---


## 📜 许可证
MIT License

---

## 📮 联系与参与

建议、合作、指令提交：`limh@10000.world`  
项目仓库：[https://github.com/weihai-limh/text-cli](https://github.com/weihai-limh/text-cli)

