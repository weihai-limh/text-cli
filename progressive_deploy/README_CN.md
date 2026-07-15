# Progressive Deploy — 渐进式部署

渐进式 = 按需爬坡。
**每一级都是完整终点——升级是加法，不是替代。**

---

## 目录约定

从 A2 起，每层使用 `all/` + `add/` 双文件夹结构：

```
A2-copilot/
├── all/       ← 本层完整可部署产物（直接可用）
│   ├── copilot/    ← 本地代理服务
│   └── media/      ← 共享基础设施占位
└── add/       ← 本层相比上一层的纯增量（A2 基础层为空）
```

```
A7-mcp/
├── all/       ← 累积 A6 全量 + 本层新增
│   ├── copilot/    ← 本地代理（自 A2 累积）
│   ├── service/    ← 平台核心（自 A3 累积）
│   ├── MCPservice/ ← MCP 独立子服务（A7 新增）
│   └── media/      ← 共享基础设施占位
└── add/       ← A7 纯增量
    ├── service/    ← 融入 service 的 MCP 代码
    ├── MCPservice/ ← 独立 MCP 服务
    ├── media/      ← 占位
    └── other/      ← 待消解文件
```

**任何一层用户只拿 `all/` 就能跑，不用去下层找文件。审查者只看 `add/` 就知道这层贡献了什么。**

---

## 十级全览

```
A0  协议规范 — 定义指令格式（prompt 怎么拼、参数怎么传），通过公共端点调用
    ⬇
A1  调用封装 — Skill 让 Agent 学会消费指令（封装调哪个 URL、传什么 body）
    ⬇
A2  通过本地辅助使用 text-cli — Agent-Copilot（本地指令 + cmd_engine + path_engine + Skill Bridge + output_adapter）
    ⬇
A3  通过本地辅助使用 text-cli — Service（平台管理核心：安装/卸载/导出/包生命周期/4 runtime/nocode 支持）
    ⬇
A4  通过指令路径使用 text-cli — Paths（路径声明、委托调度、技能发布）
    ⬇
A5  公网入口 — Endpoint（自建集成端点）：鉴权 + 路由 + 转发，任意 HTTP AI 可调用
    ⬇
A6  集成 SQL 模块使用 text-cli — 从个人玩具到小企业工具（密钥管理 + 配额追踪 + 异步任务）
    ⬇
A7  集成 MCP 模块使用 text-cli — 配置驱动暴露，成千上万工具
    ⬇
A8  通过指令发现使用 text-cli — 查询、搜索、匹配指令集 + 聚合入口 + 白名单暴露
    ⬇
A9  通过高级指令使用 text-cli — 聚合降级 + 多源统一 + 技能即服务
```

---

## 升级不是替换——Jack 的故事

**A0：Jack 第一次用 text-cli。**

Jack 是威海一家花店的老板。他在终端敲下：

```
curl -X POST https://test.text-cli.com/text-cli/cli \
  -d '{"prompt": "AI:基础应用;天气查询,明天,威海"}'
```

返回了明天的温度和日出时间。这就是 A0——零部署，零配置，能 curl 就能用。

**A0 → A1：Agent 替 Jack 发指令。**

Jack 配置了 Skill 文件。现在他的 AI Agent 能自动识别"查天气"的意图——Jack 说"明天穿什么？"，Agent 自动组装并发送指令。Jack 不再需要自己敲 curl。

**A3 → 花店老板从消费者变成提供者。**

Jack 把盆栽急救经验写成了 Markdown——六篇笔记，一份症状索引。平台把她的笔记变成可调用的诊断服务，通过 handler_inits 自动加载，manifest 追踪来源，export 导出为可分发的包。非代码经验成为一等指令包类型。

**A6：Jack 意识到这不是玩具了。**

三个花店各用各的 key，需要配额管理。Jack 接入了 SQL 模块——密钥管理、配额追踪（按字符数或调用次数）、异步任务追踪。"从个人玩具到小企业工具"——这不是 slogan，是 Jack 的真实感受。

**A8：Agent 不再需要记住三个地图入口。**

聚合指令把 `tx-map;geocode`、`gd-map;geocode`、`bd-map;geocode` 收敛为 `map;geocode`。Agent 只记住一个入口，降级链在内部自动切换。白名单对外只暴露聚合入口——调用方不需要知道背后有几家提供方。

**A9：Jack 不再关心底层。**

Jack 的盆栽急救指令被六个人调用，各自走不同的路径链。但 Jack 只维护一条高级指令——门面模式把底层复杂性压缩为零。聚合降级让调用方在多个提供方之间无感知切换。

---

## 当前状态

| 级别 | 状态 | 说明 |
|------|------|------|
| A0 | ✅ 就绪 | SPEC v1.1 + test.text-cli.com |
| A1 | ✅ 就绪 | 聚合 Schema + consumer SDK（Python/JS/Shell） |
| A2 | ✅ 就绪 | agent-copilot + cmd_engine + path_engine + Skill Bridge + output_adapter |
| A3 | ✅ 就绪 | 平台管理核心：安装/卸载/导出/manifest/nocode/handler_inits 自动加载 |
| A4 | ✅ 就绪 | 路径声明 + 委托调度 + 技能发布 + 对外暴露 |
| A5 | ✅ 就绪 | Python/FastAPI 端点 + Cloudflare Worker 端点 |
| A6 | ✅ 就绪 | SQLite 密钥管理 + quota-amount 扩展 + task-tracked 异步模式 |
| A7 | ✅ 就绪 | 配置驱动 MCP 桥 + 双向映射 |
| A8 | ✅ 就绪 | 指令发现 + 聚合入口 + 白名单服务清单 |
| A9 | ✅ 就绪 | 聚合降级 + 多源统一（native/MCP/Skill Bridge）+ 技能即服务 |
