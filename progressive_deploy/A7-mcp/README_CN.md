# A7 — MCP 双向桥接

配置驱动暴露，成千上万工具。通过 MCP 桥将 MCP server 的工具自动编译为 text-cli 指令。

> `all/` 自 A6 累积。本层新增：`service/` 内 MCP dispatch/handler/module + `MCPservice/` 独立子服务。`add/other/` 收纳待消解的 bridge/consumer/tools。

## 目录结构

```
A7-mcp/
├── all/                               ← 本层完整可部署产物
│   ├── copilot/                       ← 自 A6 累积
│   ├── service/                       ← 自 A6 累积 + A7 MCP 代码
│   │   ├── core/
│   │   │   └── mcp_dispatch.py        ← A7 版 MCP 调度（替换 A3/A6 stub）
│   │   ├── handlers/
│   │   │   └── mcp_handler.py         ← A7 新增 — MCP handler
│   │   ├── text_cli_modules/
│   │   │   └── mcp/
│   │   │       └── server.py          ← A7 新增 — MCP 运行时模块
│   │   └── [其余 A6 service 文件不变]
│   ├── MCPservice/                    ← A7 新增 — 独立 MCP 服务
│   │   ├── manage.sh                  ← 服务管理脚本
│   │   └── server.py                  ← MCP 服务入口
│   └── media/                         ← 共享基础设施占位
├── add/                               ← A7 纯增量
│   ├── service/                       ← MCP dispatch + handler + module
│   ├── MCPservice/                    ← 独立 MCP 服务文件
│   ├── media/                         ← 占位
│   └── other/                         ← 待消解
│       ├── bridge/                    ← MCP 桥独立服务（后续消解）
│       ├── consumer/                  ← MCP 消费者（后续消解）
│       ├── tools/                     ← MCP 工具转换（后续消解）
│       └── main_extended.py           ← A3 main.py 扩展版（后续消解）
└── README_CN.md                       ← 本文档
```

## MCP 桥核心概念

text-cli 通过 MCP 桥实现双向映射：

```
MCP server  ←→  text-cli 指令
    工具      =      指令
   server    →    handler
```

一次配置，MCP server 的所有工具自动映射为 text-cli 指令。调用方用同样的 `AI:域;动作,参数` 协议调用，不感知底层传输差异。

## MCPservice — 独立 MCP 子服务

`MCPservice/`（原名 `reverse/`）是一个独立的反向代理 MCP 服务。它与 `copilot/` 和 `service/` 平级——作为运行时进程之一：

```bash
cd A7-mcp/all/MCPservice/
bash manage.sh start
```

## 文件分流

| 文件 | 归入 | 状态 |
|------|------|------|
| `mcp_dispatch.py` | `all/service/core/` | ✅ 已融入 |
| `mcp_handler.py` | `all/service/handlers/` | ✅ 已融入 |
| `text_cli_modules/mcp/` | `all/service/text_cli_modules/mcp/` | ✅ 已融入 |
| `reverse/` → `MCPservice/` | `all/MCPservice/` | ✅ 独立子服务 |
| `bridge/` | `add/other/bridge/` | ⏳ 待消解 |
| `consumer/` | `add/other/consumer/` | ⏳ 待消解 |
| `tools/` | `add/other/tools/` | ⏳ 待消解 |
| `main_extended.py` | `add/other/` | ⏳ 待消解 |

## 依赖

- A6：SQL 持久化（密钥管理 + 配额追踪）
- A6 累积：copilot + service + path engine

---

*text-cli 项目的一部分。*
