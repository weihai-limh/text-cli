# A3 — Service 平台管理核心

可被 agent-copilot 代理调用的标准指令服务骨架。10 个骨架 handler + 包安装机制。

> 已升级为骨架架构：包 handler 由运行时安装注入 packages/，骨架仅保留结构性代码。

## 目录结构

```
A3-service/
├── main.py                          ← FastAPI 入口（lifespan + 指令分发）
├── requirements.txt
├── Dockerfile / docker-compose.yml
├── config/
│   ├── service_manifest.json        ← 服务清单
│   ├── system_schema.json           ← 系统 schema
│   └── *.example.json               ← 示例配置
├── core/
│   ├── parser.py                    ← 指令文本解析
│   ├── registry.py                  ← @directive 装饰器注册表 + dispatch
│   ├── auth.py                      ← Service Token 鉴权
│   ├── response.py                  ← ok() / error() 标准响应
│   └── mcp_dispatch.py              ← MCP 调度
├── handlers/                        ← 骨架（10 文件 + installer/）
│   ├── __init__.py                  ← 自动扫描 packages/ + JS 注册
│   ├── text_cli_path.py             ← 路径引擎
│   ├── text_cli_pro.py              ← copilot 代理
│   ├── text_cli_install.py          ← 包安装器
│   ├── text_cli_export.py           ← 包导出器
│   ├── text_cli_uninstall.py        ← 包卸载器
│   ├── package_manifest.py          ← 清单注册
│   ├── schema_query.py              ← schema 查询
│   ├── proxy.py                     ← 代理路由
│   ├── js_bridge.py                 ← JS 运行时桥
│   └── installer/                   ← 安装器子模块
└── packages/                        ← 包安装目标（空目录）
```

## 骨架 Handler

| 文件 | 指令 | 说明 |
|------|------|------|
| `text_cli_path.py` | `text-cli;path` | 路径引擎，条件执行 + 降级 + 并行 |
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
cd A3-service/
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
