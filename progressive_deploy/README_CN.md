# Progressive Deploy — 渐进式部署

渐进式 = 按需爬坡。
**每一级都是完整终点——升级是加法，不是替代。**

---

## 十级全览

```
A0  通过 GET/POST 使用 text-cli — 零部署，公共端点
    ⬇
A1  通过本地辅助使用 text-cli — Skill（聚合 Schema、同步指令）
    ⬇
A2  通过本地辅助使用 text-cli — Agent-Copilot（24 条本地指令 + cmd_engine + path_engine）
    ⬇
A3  通过本地辅助使用 text-cli — Service（平台管理核心：安装/路径/技能端点/4 runtime）
    ⬇
A4  通过指令路径使用 text-cli — Paths（路径声明、委托调度、技能发布）
    ⬇
A5  通过私有端点使用 text-cli — Endpoints（自建集成端点）
    ⬇
A6  集成 SQL 模块使用 text-cli — 从个人玩具到小企业工具
    ⬇
A7  集成 MCP 模块使用 text-cli — 配置驱动暴露，成千上万工具
    ⬇
A8  通过指令发现使用 text-cli — 查询、搜索、匹配指令集
    ⬇
A9  通过高级指令使用 text-cli — 门面抽象，降低心智负担
```

---

## 升级不是替换——Jack 的故事

**A0：Jack 第一次用 text-cli。**

Jack 是威海一家花店的老板。他在终端敲下：

```
curl -X POST https://test.text-cli.com/cli/text_cli \
  -d '{"prompt": "AI:基础应用;天气查询,明天,威海"}'
```

返回了明天的温度和日出时间。这就是 A0——零部署，零配置，能 curl 就能用。

**A0 → A1：Agent 替 Jack 发指令。**

Jack 配置了 Skill 文件。现在他的 AI Agent 能自动识别"查天气"的意图——Jack 说"明天穿什么？"，Agent 自动组装并发送 `AI:基础应用;天气查询,明天,威海`。Jack 不再需要自己敲 curl。

**A3 → A5：Jack 从消费者变成提供者。**

Jack 把盆栽急救经验写成了指令。他不想依赖公共端点——不稳定，也没法计费。他用 A5 的 Python 模板部署了自己的私有端点，把 Service Token 分给需要他经验的人。

**A4：Jack 把多条指令串成了技能。**

查天气 → AI 推理穿衣建议。Jack 写了一个 path JSON，用 `text-cli;path --register` 注册，用 `text-cli;pro` 发布为 `skill;穿衣建议`。现在其他花店老板不需要知道中间有几步——他们只需要 `AI:skill;穿衣建议,威海`。

**A6：Jack 意识到这不是玩具了。**

三个花店各用各的 key，需要轮换，每次换 key 要留审计日志。环境变量管不了这个。Jack 接入了 SQL 模块。"从个人玩具到小企业工具"——这不是 slogan，是 Jack 的真实感受。

**A7：Jack 发现 MCP 桥。**

Jack 听说 GitHub 有 MCP Server。他让 Agent 读取 GitHub MCP 元数据，mcp2textcli 自动编译成 26 条 text-cli 指令——其中 24 条零手写适配（92% passthrough），只有 2 条需要定制 adapter。

Jack 没写一行代码——十分钟后他的花店工作流里多了"创建 Issue""合并 PR""查提交历史"。MCP 桥不是"接入一个工具"——是"接入一个生态，自动获得成千上万指令"。

**A9：Jack 不再关心底层。**

Jack 的盆栽急救指令被六个人调用，各自走不同的 MCP Server、不同的渲染模板、不同的路径链。但 Jack 只维护一条高级指令——门面模式把底层复杂性压缩为零。

---

## 三条核心原则

**① 升级是加法，不是替代。**

第 9 级用户仍可打 A0 的 curl 指令。低层级的"简单"不是缺陷——是设计成功。你不需要学到后一级才能用前一级。

**② 文件暴露 = 认知负担边界。**

配置离项目根越远，需要的级别越高。事实放公共层，偏好放能力层，收束规则放服务层。如果所有配置全堆根目录，第一个 `git clone` 就把花店老板吓跑了。

**③ 空地就空地。**

有些 A 级只有很少的内容（如 A6 只放了 key-mgmt）。不要往没东西的级别塞填充物。空地等真正属于这一级的东西长出来——分界线的价值不在于装了多满，在于划在哪里。

---

## MCP 实际转化率

MCP 工具通过 mcp2textcli 自动编译为 text-cli 指令。实际转化率取决于参数模式——纯文本型 100% passthrough，JSON 型通过共享 adapter 覆盖。以下为四个已接入 MCP Server 的实测数据：

| | GitHub | AntV 可视化 | 腾讯地图 | CloudBase |
|---|---:|---:|---:|---:|
| Tools | 26 | 26 | 15 | 36 |
| 传输 | stdio | SSE | SSE | stdio (npx) |
| 参数模式 | 文本 + 环境注入 | JSON 数据 | 纯文本 | action enum + 文本 |
| 输出格式 | JSON | 图片 URL | 纯文本 | JSON |
| passthrough | 92% | 8% | 100% | 89% |
| 共享 adapter | — | 92% (json_parse) | — | 8% (json_parse) |
| 需自定义 adapter | 2 | 0 | 0 | 4 |

> 四个 Server 共 103 个 tools，总计需手写 6 个 adapter。接入效率：94% 零手写。

---

## 从哪里开始

从你的需求级别开始读，不需要先读前面所有级。

| 你的身份 | 从哪级开始 |
|----------|-----------|
| 只想试用一条指令 | A0 |
| 想让 Agent 自动调用指令 | A1 |
| 想写一个指令包，零部署接入 | A3（text-cli;install） |
| 想知道怎么把经验变成指令 | A2，参考 `Building_text-cli_guide_CN.md` §2 |
| 想部署自己的指令端点 | A5 |
| 小企业想管理多个 key | A6 |
| 已有 MCP 工具想接入 | A7 |
| 想了解全部 | 从 A0 一路走到 A9 |

---

## 当前状态

| 级别 | 状态 | 说明 |
|------|------|------|
| A0 | ✅ 就绪 | SPEC v1.1 + test.text-cli.com |
| A1 | ✅ 就绪 | 聚合 Schema + consumer SDK（Python/JS/Shell） |
| A2 | ✅ 就绪 | agent-copilot（24 条指令）+ cmd_engine + path_engine |
| A3 | ✅ 就绪 | 平台管理核心：安装/卸载/路径引擎/pro 发布/skills 端点/4 runtime |
| A4 | ✅ 就绪 | 路径声明 + 委托调度 + 技能发布 + 对外暴露 |
| A5 | ✅ 就绪 | Python/FastAPI 端点 + Cloudflare Worker 端点 |
| A6 | ✅ 就绪 | SQLite 密钥管理 |
| A7 | ✅ 就绪 | 配置驱动 MCP 桥（mcp_exposure.json）+ 双向映射 |
| A8 | ✅ 就绪 | text-cli;query 元指令 + 语义注册表 + 技能发现 |
| A9 | 🧠 设计阶段 | 高级指令门面、暖空间注册表、自动匹配引擎 |
