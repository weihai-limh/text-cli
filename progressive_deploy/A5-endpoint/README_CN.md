# A5 — 集成端点

service 的公网门面。不暴露 service IP，不执行指令逻辑，只做鉴权 + 路由 + 转发。

> A1-A4 构建能力，A5 将能力外溢到公网——让更多的 AI 和人可以调用你的指令，而不需要知道 service 部署在哪、由谁提供。

## 为什么没有 all/add

A5 不是垂直叠加层。Endpoint 是**独立部署单元**——它不和 copilot、service、paths 运行在同一进程，不持有指令包，不参与 `text-cli;install` 管线。

A2-A9 的 `all/` = 自下层累积的全量产物，`add/` = 本层纯增量。Endpoint 不叠加在任何一层之上——它是水平旁路，独立于整个垂直栈部署。因此不适用 `all/add` 结构。

## 目录结构

```
A5-endpoint/
├── python/                        ← FastAPI 版（Docker / VM 部署）
│   ├── main.py                    ← 应用入口（lifespan + 核心端点）
│   ├── config/
│   │   └── text_cli_schema.json   ← 内部路由 Schema（含真实后端 url）
│   ├── core/
│   │   ├── parser.py              ← 指令解析器（双前缀协议）
│   │   ├── schema_loader.py       ← 双 Schema 加载与转换
│   │   ├── auth.py                ← Access Token 鉴权 + 令牌桶限流
│   │   ├── forwarder.py           ← HTTP 转发器（异步 + 重试 + 记账）
│   │   └── database.py            ← SQLite 连接与初始化
│   ├── api/
│   │   ├── health.py              ← 健康检查
│   │   ├── stats.py               ← 调用统计查询
│   │   └── tokens.py              ← Token 管理（CRUD）
│   ├── handlers/                  ← 后端 handler（本地路由用）
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── README_CN.md               ← Python 版部署指南
├── js/                            ← Cloudflare Workers 版（Edge 部署）
│   ├── src/
│   │   ├── index.js               ← Worker 入口（fetch + 路由）
│   │   ├── parser.js              ← 指令解析器
│   │   ├── schema-loader.js       ← 双 Schema 加载（D1 + 静态文件）
│   │   ├── auth.js                ← Access Token 鉴权（D1 滑动窗口）
│   │   ├── forwarder.js           ← 请求转发器（fetch + 重试 + 记账）
│   │   ├── admin.js               ← 管理 API
│   │   └── config/
│   │       └── schema.json        ← 内部路由 Schema
│   ├── migrations/
│   │   └── 0001_init.sql          ← D1 表结构迁移
│   ├── test/                      ← vitest 测试套件
│   ├── wrangler.toml
│   ├── package.json
│   └── README_CN.md               ← Workers 版部署指南
└── README_CN.md                   ← 本文档
```

## Endpoint 做什么

Endpoint 是 service 的网络边界代理。service 部署在内网/Docker 网络，不直接向公网暴露 IP。Endpoint 站在公网入口，替 service 完成：

```
陌生调用方（人 / AI）            熟悉调用方（人 / AI）
     │                               │
     │  Access Token                 │ Service Token 
     ▼                               ▼
┌──────────┐    Service Token   ┌──────────┐
│ Endpoint │ ─────────────────→ │ service  │
│ (公网门面)│ ←──────────────── │ (能力方)  │
└──────────┘    透传响应        └──────────┘
```

| 职责 | 说明 |
|------|------|
| Access Token 鉴权 | 验证调用方身份，支持额度控制 + 令牌桶限流 |
| 指令解析 | 从 prompt 中提取 domain、action、params（双前缀协议） |
| Schema 路由匹配 | 根据指令找到对应后端 service 的地址 |
| 请求转发 | 透传 Service Token 到后端，含自动重试 |
| 调用记账 | 记录每次调用的元数据（call_logs + daily_stats） |
| Schema 转换 | 对外暴露的 Schema 中，真实后端 url 替换为 Endpoint 自身地址 |

**Endpoint 不持有指令包，不执行任何指令逻辑。** 收到请求 → 鉴权 → 路由 → 转发 → 记账 → 返回。所有业务逻辑在 service 侧完成。

## 双实现

两版功能等价——相同的协议、相同的职责。差异在部署场景和数据存储：

| | Python 版 | Workers 版 |
|---|---|---|
| 运行时 | FastAPI（ASGI） | Cloudflare Workers（V8） |
| 部署方式 | Docker + VM | `wrangler deploy` |
| 数据库 | SQLite（文件） | D1（SQLite at edge） |
| Schema 存储 | 本地 JSON 文件 | D1 `directives` 表 + 静态文件回退 |
| 限流 | 令牌桶（内存/SQLite） | D1 滑动窗口查询 |
| 适用场景 | 自有服务器、Docker 集群 | Serverless、全球边缘节点 |

**选型指南**：已有服务器基础设施 → Python 版。零运维、全球低延迟 → Workers 版。

## A0、A1、A5：公网可达性的三条路径

Endpoint 不是孤立组件。它与 A0 和 A1 共同构成 text-cli 的公网消费入口——三层合力，任意具备 HTTP 能力的 AI 都能执行指令。

| 层 | 给的什么 | 没有它会怎样 |
|----|---------|------------|
| **A0** | 指令格式（协议规范） | 调用方不知道 prompt 怎么写 |
| **A1** | Skill 封装（消费入口） | Agent 不知道调哪个 URL、传什么 body |
| **A5** | Endpoint（公网入口） | 有协议有 skill，但没地方发请求 |

chat 型 AI 只需一个 Endpoint URL 和一个 Access Token，就能通过 A0 的格式 + A1 的封装发起调用。A0 定义"怎么调"，A1 封装"怎么调"，A5 提供"往哪调"。

### 与其他层的关系

Endpoint 的 parser 与 A3 `core/parser.py` 遵循同一协议（双前缀、全角兼容、参数拆分）。Endpoint 的 Schema 路由匹配与 A8 聚合降级链概念对齐——Endpoint 做静态匹配，A8 做动态降级。

## 快速开始

详见各实现目录下的部署指南：

- **Python 版**：[`python/README_CN.md`](python/README_CN.md) — Docker 一键部署 + 环境变量配置
- **Workers 版**：[`js/README_CN.md`](js/README_CN.md) — wrangler 部署 + D1 数据库绑定

完整技术方案见 [`docs/CN/Service_endpoint_CN.md`](../../docs/CN/Service_endpoint_CN.md)。

---

*text-cli 项目的一部分。由 lemondy 发起。*
