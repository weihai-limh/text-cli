# A3 — Service 平台管理核心

可被 agent-copilot 代理调用的标准指令服务骨架。10 个骨架 handler + 包安装机制。

> `all/copilot/` 自 A2 累积，`all/service/` 为本层新增。`add/service/` 完整呈现 A3 的纯增量。

## 目录结构

```
A3-service/
├── all/                               ← 本层完整可部署产物
│   ├── copilot/                       ← 自 A2 累积（本地代理服务全部文件）
│   ├── service/                       ← A3 新增 — 平台管理核心
│   │   ├── main.py                    ← FastAPI 入口（lifespan + 指令分发）
│   │   ├── requirements.txt
│   │   ├── Dockerfile / docker-compose.yml
│   │   ├── config/
│   │   │   ├── handler_inits.py       ← handler 初始化注册表（安装时自动生成）
│   │   │   ├── service_manifest.json  ← 服务清单
│   │   │   ├── system_schema.json     ← 系统 schema
│   │   │   └── *.example.json         ← 示例配置
│   │   ├── core/
│   │   │   ├── parser.py              ← JSON 感知指令解析
│   │   │   ├── registry.py            ← @directive 装饰器注册表 + dispatch
│   │   │   ├── auth.py                ← Service Token 鉴权
│   │   │   ├── response.py            ← ok() / error() 标准响应
│   │   │   └── mcp_dispatch.py        ← MCP 调度
│   │   ├── handlers/
│   │   │   ├── installer/             ← 安装器子模块（5 文件）
│   │   │   ├── __init__.py            ← 自动扫描 packages/
│   │   │   ├── text_cli_path.py       ← 路径引擎（骨架版，A4 升级）
│   │   │   ├── text_cli_pro.py        ← copilot 代理
│   │   │   ├── text_cli_install.py    ← 包安装器
│   │   │   ├── text_cli_export.py     ← 包导出器
│   │   │   ├── text_cli_uninstall.py  ← 包卸载器
│   │   │   ├── text_cli_nocode.py     ← nocode 支持
│   │   │   ├── package_manifest.py    ← 清单持久化
│   │   │   ├── schema_query.py        ← schema 查询
│   │   │   ├── proxy.py               ← 代理路由
│   │   │   ├── js_bridge.py           ← JS 运行时桥
│   │   │   ├── key.py                 ← 密钥 handler
│   │   │   ├── task_manager.py        ← 任务管理
│   │   │   └── schema/                ← 骨架 schema（2 文件）
│   │   ├── packages/__init__.py        ← 包安装目标（空目录）
│   │   ├── text_cli_modules/           ← 基础设施模块
│   │   │   ├── key/                   ← 密钥注册表
│   │   │   └── sqlite/                ← SQLite 数据库
│   │   └── .gitignore
│   └── media/                         ← 共享基础设施占位
└── add/
    └── service/                        ← A3 纯增量（与 all/service/ 内容相同）
```

## 骨架 Handler

| 文件 | 指令 | 说明 |
|------|------|------|
| `text_cli_path.py` | `text-cli;path` | 路径引擎骨架（A4 升级为完整引擎版） |
| `text_cli_pro.py` | `text-cli;pro` | copilot 代理转发 |
| `text_cli_install.py` | `text-cli;install` `文本指令;安装` | 包安装（注册到 manifest） |
| `text_cli_export.py` | `text-cli;export` `文本指令;导出` | 包导出 |
| `text_cli_uninstall.py` | `text-cli;uninstall` `文本指令;卸载` | 包卸载 |
| `package_manifest.py` | — | 清单持久化 |
| `schema_query.py` | `text-cli;query` | schema 查询 |
| `proxy.py` | — | 代理路由 |
| `js_bridge.py` | — | Node.js 运行时桥 |

## 包 Handler（运行时安装）

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

安装：`AI:text-cli;install,<包路径>`

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `TEXT_CLI_HOME` | `/root/text-cli` | 项目根目录 |
| `TEXT_CLI_MODULES_DIR` | `$TEXT_CLI_HOME/text_cli_modules` | 基础设施模块路径 |
| `PORT` | `28050` | 服务端口 |

## 快速启动

```bash
cd A3-service/all/service/
pip install -r requirements.txt
PORT=28050 python3 main.py
```

验证：

```bash
curl http://localhost:28050/health
# {"status":"ok"}
```

---

*text-cli 项目的一部分。由 lemondy 发起，Tide 🌊 实现。*
