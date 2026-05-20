# A2 — Agent-Copilot 本地指令服务

部署在终端本地的指令代理骨架。5 个骨架 handler + Skill Bridge + 路径引擎。

> 已升级为骨架架构：包 handler 由运行时安装注入，骨架仅保留结构性代码。

## 目录结构

```
A2-copilot/
├── config/                       ← 路由配置（key_routing / skill_bridge_routes）
├── adapters/                     ← 适配器挂载点（空目录，包安装时注入）
├── text_cli_modules/
│   └── media/                    ← 共享产出目录（空目录，A2 约定）
├── server/
│   ├── core.py                   ← dispatch 引擎
│   ├── text-cli-copilot.py       ← HTTP 服务入口
│   ├── whitelist_loader.py       ← CLI 白名单加载
│   ├── handlers/                 ← 骨架 handler（5 文件）
│   │   ├── __init__.py           ← mixin 聚合
│   │   ├── codec.py              ← 编解码
│   │   ├── key.py                ← 密钥路由层
│   │   ├── adapters.py           ← 响应适配器协议
│   │   └── skill_bridge.py       ← 通用 Skill 桥
│   └── packages/                 ← 包安装目标（空目录）
└── server/README_CN.md           ← 本文档
```

## 骨架 Handler

| 文件 | 职责 |
|------|------|
| `__init__.py` | mixin 聚合，包 handler 由安装时注入 |
| `codec.py` | Base64/Hex 编解码 |
| `key.py` | 密钥路由层（不存储密钥，按 routing 配置分发） |
| `adapters.py` | 通用响应适配器协议 |
| `skill_bridge.py` | 通用桥——一个 handler，N 个 skill 包共享 |

## 包 Handler

以下 handler 不出现在骨架中，由对应的指令包安装时注入 `packages/` 目录：

| 包 | 指令 |
|------|------|
| files | 文件;读写 |
| git | Git;status/push |
| mail | 邮件;发送 |
| system | 系统;健康/状态 |
| media | 媒体;加载/下载 |
| render | 资源渲染 |
| terminal | 终端;命令 |
| mcp-bridge | MCP 桥接 |
| copilot-browser | 浏览器操作 |

## Skill Bridge

Skill Bridge 将 ClawHub skill 桥接为 text-cli 指令。
路由配置在 `config/skill_bridge_routes.json`。
适配器由包安装时注入 `adapters/` 目录。

## 部署

用户 merge A2-copilot/ 到本地系统后：

### 启动前提

1. **配置文件** — `server/auxiliary_config.json` 中的路径使用 `${VAR_NAME}` 占位符，启动时通过环境变量解析
2. **运行时目录** — `data/`（路由偏好）、`whitelists/`（CLI 白名单）启动时自动创建
3. **环境变量（必需）**

| 变量 | 说明 | 示例 |
|------|------|------|
| `TEXT_CLI_HOME` | 项目根目录 | `/home/user/text-cli` |

配置文件中以 `${...}` 形式引用环境变量，未被设置的环境变量会打印警告并使用空字符串。

### 启动

```bash
cd server/
python3 text-cli-copilot.py
```

服务监听 `127.0.0.1:20260`。

### 验证

```bash
curl http://localhost:20260/health
# {"status": "ok"}
```

### 后续

1. `server/handlers/` 提供 5 个骨架 handler
2. `server/packages/` 为空，通过 `AI:co-install,<包名>` 安装所需包
3. 包安装后重启 copilot 激活新 handler
