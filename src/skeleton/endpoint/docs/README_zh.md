# endpoint 分组

## 定位

endpoint 分组下是 text-cli 的**水平旁路子产品**——不参与骨架累积链，独立分发。

A5 是 service 的公网门面。不暴露 service IP，不执行指令逻辑，只做鉴权 + 路由 + 转发。A1-A4 构建能力，A5 将能力外溢到公网——让更多的 AI 和人可以调用指令，而不需要知道 service 部署在哪。

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

## 层级

| 层 | 名称 | 类型 | 部署方式 |
|:---:|------|------|------|
| A5 | endpoint | 公网入口 | Docker (Python/FastAPI) + Cloudflare Workers (JS) |

## 为什么是独立子产品

A5 不是垂直叠加层——不参与骨架累积链，不参与 `build-all.py`。它是水平旁路，独立于整个垂直栈部署。A2-A9 的累积累积对它不适用。

详见 `deploy/A5-endpoint/docs/` 下的专属文档。

## Endpoint 职责

| 职责 | 说明 |
|------|------|
| Access Token 鉴权 | 验证调用方身份，支持额度控制 + 令牌桶限流 |
| 指令解析 | 从 prompt 中提取 domain、action、params（双前缀协议） |
| Schema 路由匹配 | 根据指令找到对应后端 service 的地址 |
| 请求转发 | 透传 Service Token 到后端，含自动重试 |
| 调用记账 | 记录每次调用的元数据（call_logs + daily_stats） |
| Schema 转换 | 对外暴露的 Schema 中，真实后端 url 替换为 Endpoint 自身地址 |

Endpoint **不持有指令包，不执行任何指令逻辑**。收到请求 → 鉴权 → 路由 → 转发 → 记账 → 返回。

## 双实现

两版功能等价——相同的协议、相同的职责。差异在部署场景和数据存储：

| | Python 版 | Workers 版 |
|---|---|---|
| 运行时 | FastAPI（ASGI） | Cloudflare Workers（V8） |
| 部署方式 | Docker + VM | `wrangler deploy` |
| 数据库 | SQLite（文件） | D1（SQLite at edge） |
| 适用场景 | 自有服务器、Docker 集群 | Serverless、全球边缘节点 |

详细部署指南：
- Python 版：[`README_zh.md`](../A5-endpoint/python/README_zh.md)
- Workers 版：[`README_zh.md`](../A5-endpoint/js/README_zh.md)

## A0、A1、A5：公网可达性的三条路径

| 层 | 给的什么 | 没有它会怎样 |
|----|---------|------------|
| A0 | 指令格式（协议规范） | 调用方不知道 prompt 怎么写 |
| A1 | Skill 封装（消费入口） | Agent 不知道调哪个 URL、传什么 body |
| A5 | Endpoint（公网入口） | 有协议有 skill，但没地方发请求 |

---

_2026-07-16_
