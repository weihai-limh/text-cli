# service 分组

## 定位

service 分组下的骨架层绑定 **service 运行时（:28050）**——它是 text-cli 的平台管理核心。从 A3 的基础安装/卸载到 A9 的全量聚合降级，service 是骨架累积链的主干。

## 累积链

```
A3-service（基础平台）
  → A4-paths（路径编排）
    → A6-sql（SQLite 持久层 — "从玩具到工具"的分界线）
      → A7-mcp（MCP 双向桥）
        → A8-discovery（指令发现与聚合入口）
          → A9-advanced（高级指令 — 累积终点）
```

每层在上一层基础上增加新能力。后层同名文件覆盖前层，`build-all.py` 保证累积正确。

---

## A3 — Service 平台管理核心

可被 agent-copilot 代理调用的标准指令服务。10 个骨架 handler + 包安装机制 + 多运行时支持（python / node / mcp / cmd / path / aggregate）。

### 骨架 Handler

| 文件 | 指令 | 说明 |
|------|------|------|
| `text_cli_path.py` | `text-cli;path` | 路径引擎骨架（A4 升级为完整引擎版） |
| `text_cli_pro.py` | `text-cli;pro` | copilot 代理转发 |
| `text_cli_install.py` | `text-cli;install` `文本指令;安装` | 包安装（pip/npm 依赖 + 文件部署 + manifest 注册） |
| `text_cli_export.py` | `text-cli;export` `文本指令;导出` | 包导出 |
| `text_cli_uninstall.py` | `text-cli;uninstall` `文本指令;卸载` | 包卸载（含 DROP TABLE） |
| `text_cli_nocode.py` | `text-cli;nocode` | Markdown 经验文档自动转化 |
| `package_manifest.py` | — | 清单持久化 |
| `schema_query.py` | `text-cli;query` | schema 查询 |
| `proxy.py` | — | 代理路由（含 `sensitive` 脱敏） |
| `js_bridge.py` | — | Node.js 运行时桥 |

### 包分类

以下能力由指令包提供，安装到 `packages/` 目录：

| 类别 | 包（示例） |
|------|----------|
| AI | ai-generate, ai-inference, ai-im |
| 地图 | bd-map, gd-map, tx-map, tdt-map |
| 坐标 | geo-coords, geo-grid, geo-panoramic |
| 媒体 | image, ms-tts, tc-browser |
| 工具 | tc-json, tc-markdown, path-str, sample, template |
| 平台 | key, quota-manage, task-manager |
| 云服务 | bd-cloud, tx-cloud |
| 桥接 | mcp, skill-endpoint, stream-im |

安装：`AI:text-cli;install,<包名>`

### 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `TEXT_CLI_HOME` | `~/text-cli` | 项目根目录 |
| `TEXT_CLI_MODULES_DIR` | `$TEXT_CLI_HOME/text_cli_modules` | 基础设施模块路径 |
| `PORT` | `28050` | 服务端口 |

---

## A4 — Paths 指令路径

### 什么是路径

| 问题 | 答案 |
|------|------|
| 路径是什么 | 将原子指令编排为声明式、可容错的执行管道 |
| 路径解决什么 | "做一件事需要多步，哪步先哪步后，失败了怎么办" |
| 指令回答什么 | "这一个具体操作怎么做" |
| 边界 | 路径编排"做什么"，指令实现"怎么做" |
| 复杂度上限 | 瞬时思考的深度——两次降级就是深度上限 |

路径不是图灵完备的编程语言。它是有序的、可读的、可调试的配方——人和 AI 都能读、能生成、能执行。

### Pre-A4 → Post-A4

```
Pre-A4                          Post-A4
──────────────────────────────────────────
路径 = JSON 声明                 路径 = 引擎执行
AI 读 JSON 理解步骤             引擎解析 if/degradation/timeout
编排负担在 AI                   编排负担转移到引擎
"我做 geocode 然后 offset"      "geocode 失败→降级→超时→断路"
```

两个时代共存。没有 `if` 的路径 AI 仍能通过原生理解力执行。有 `if` 的路径引擎接管容错编排。Post-A4 是 Pre-A4 的超集。

### 能力总览

| 层 | 能力 | 语法 |
|:--:|------|------|
| L0 | 断路保护 | 引擎内置 |
| — | timeout 时间守卫 | `"timeout": <ms>` |
| L1 | 条件分支 | `"if": {...}` + equals/contains/matches/exists |
| — | 降级递补 | `"degradation": [...]` |
| L2 | 并行执行 | `"mode": "parallel"` + first_ok/all |
| L2 | 函数表达式 | count/size/exists + eq/gt/lt/gte/lte/ne |

### 快速开始

```
AI:text-cli;path,examples/paths/geo_panoramic_query.json,威海
```

条件分支示例：

```json
{
  "id": "visual",
  "directive": "geo-panoramic;china,{coord.0},{coord.1}",
  "output_as": "panorama",
  "if": {"step": "road", "field": "status", "equals": "ok"},
  "degradation": [
    {"id": "fallback", "directive": "bd-map;static-map,{lon},{lat},16"}
  ]
}
```

---

## A6 — SQL 数据持久层

从个人玩具到小企业工具的分界线。SQLite 为密钥管理、配额追踪、异步任务提供持久化。

### quota-manage：amount 扩展

`quota;check,<target>[,<amount>]` — amount 默认 1（按调用次数），可传具体数值实现用量维度配额：

```
quota;check,tx-cloud-translation,128  # 消耗 128 字符（翻译配额 500 万字符/月）
quota;check,tx-cloud-asr              # 消耗 1 次调用
```

`cycle_limit` 承担量纲——limit=5000000 对翻译是字符数，limit=1000 对 ASR 是调用次数。SQLite 层不用改 schema，`usage_count` 语义由调用方赋予。

### task-manager：tracked 模式

| 模式 | 执行权 | 查询行为 | 适用 |
|------|--------|---------|------|
| managed | task-manager 拥有 | 查本地状态 | bim-ifc 本地进程 |
| tracked | 外部服务拥有 | 实时 dispatch 指令查上游 | tx-cloud ASR、MCP async |

用户调 `task;status,<id>` → task-manager 判断 mode=tracked → 实时 dispatch 对应指令向上游查询。不做后台轮询——只在用户查询时才请求外部服务。

### Token 身份管理

A6 骨架新增两张表。请求入口中间件提取 Service-token 后 6 位 → 查 `token_registry` 准入 → 注入 identity_code。

**`token_registry`** — token 准入控制：

| 字段 | 类型 | 说明 |
|------|------|------|
| token | TEXT PK | 身份码（token 后 6 位） |
| enabled | INTEGER | 0=吊销 |
| quota_limit | INTEGER | -1=无限 |
| used_count | INTEGER | 已用次数 |
| expires_at | DATETIME | NULL=永不过期 |

**`token_call_logs`** — 调用审计记录（token + domain + action + status + duration_ms）。

**应用自建表**：每个包在 `schema.json` 中声明 `tables`，install 时自动 CREATE TABLE，uninstall 时自动 DROP TABLE。支持 `requires.service_db` 声明骨架表依赖。

### 实例级配置

| 配置 | 默认 | 控制 |
|------|------|------|
| `A3_ALLOW_ANONYMOUS` | `true` | 无 token 请求是否放行 |
| `A3_COUNT_CALLS` | `false` | `true`=写 log + 扣配额 |

---

## A7 — MCP 双向桥接

配置驱动暴露，成千上万工具。一次映射，MCP server 的所有工具自动编译为 text-cli 指令：

```
MCP server  ←→  text-cli 指令
    工具      =      指令
   server    →    handler
```

调用方用同样的 `AI:域;动作,参数` 协议调用，不感知底层传输差异（MCP、native handler、Skill Bridge 地位平等）。

`MCPservice/` 是独立的反向代理 MCP 子服务，与 copilot/service 平级运行。

---

## A8 — 指令发现与聚合入口

不只"能找到什么指令"，还要"用一个入口收敛多个来源"。

### 聚合 dispatch 流水线

```
请求 → 聚合 dispatch → MCP 优先路由 → 本地 dispatch → MCP 后备 → proxy
```

聚合命中 → 遍历 default 降级链 → 每个提供方调 dispatch() → 返回第一个成功结果。

### aggregate 路由表

纯路由表，无执行逻辑。JSON 声明聚合域和降级链：

```json
{
  "id": "map", "type": "aggregate", "domain": "map",
  "default": ["tx-map", "tencent-maps", "gd-map", "bd-map"],
  "providers": {
    "tx-map": {"geocode": "tx-map;geocode"},
    "tencent-maps": {"geocode": "tencent-maps;geocode"}
  }
}
```

### 服务清单白名单

`config/service_manifest.json` 控制对外暴露。`/skill` 端点只暴露白名单中的指令。有内容时只暴露列出的条目——外部调用方只看到聚合入口，看不到原子提供方。

---

## A9 — 高级指令与技能即服务

渐进式部署的最后一层。门面抽象——调用方不需要知道背后有几家提供方、走的是 MCP 还是原生 handler——一个入口收敛所有。

### 降级链

`default` 列表定义了降级序。每个提供方按序尝试，成功即返回，失败自动切下一个：

```
map;geocode,威海
  → tx-map;geocode     → 配额耗尽 → 跳过
  → tencent-maps;geocode → MCP 不可用 → 跳过
  → gd-map;geocode     → ok → 返回结果
```

**三个条件全部消耗后才返回失败**——保证最大可用性：

1. dispatch 返回 `{"status":"stop"}`（配额耗尽）
2. dispatch 抛异常或返回错误
3. 指令未注册（该提供方不支持此 action）

### 多源统一

聚合不区分来源类型。`tx-map` 是 native handler，`tencent-maps` 是 MCP bridge，`skill-bdmap` 是 Skill Bridge——三者在降级链中地位平等。新的提供方接入只需在 aggregate JSON 中加一行，不影响任何已有调用方。

### 认知负担削减

```
之前：Agent 需要知道 tx-map/gd-map/bd-map 三家域名和参数格式
之后：Agent 只需要记住 map;geocode 一个入口
```

---

## 构建

service 分组下的骨架层参与 `build-all.py` 的标准累积链。后层的真源覆盖前层同名文件。

---

_2026-07-16_
