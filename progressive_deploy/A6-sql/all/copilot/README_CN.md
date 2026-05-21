# agent-copilot — text-cli 本地指令服务骨架

> text-cli 协议在本地机器上的可插拔实现。5 个骨架 handler + 包安装机制。

## 定位

agent-copilot 是 text-cli 协议在 Agent 同机的本地实现。骨架提供 dispatch 引擎 + 编解码 + 密钥路由 + Skill 桥。具体能力（文件、Git、邮件等）由指令包安装时注入。

```
Agent                   agent-copilot             远程端点
  │                         │                        │
  ├─ AI:codec;encode ─────→ │ ─→ 本地编解码          │
  ├─ AI:key;get ──────────→ │ ─→ 密钥路由             │
  └─ AI:file;read ────────→ │ ─→ [files 包] 文件系统  │
```

Agent 全程不需要持有密码或 API Key——凭据由 agent-copilot 居中持有，通过配置文件注入。

## 目录结构

```
A2-copilot/server/
├── core.py                       ← dispatch 引擎
├── text-cli-copilot.py           ← HTTP 服务入口
├── whitelist_loader.py           ← CLI 白名单加载
├── auxiliary_config.json         ← 配置文件
├── handlers/                     ← 骨架（5 文件）
│   ├── __init__.py               ← mixin 聚合
│   ├── codec.py                  ← 编解码
│   ├── key.py                    ← 密钥路由层
│   ├── adapters.py               ← 响应适配器协议
│   └── skill_bridge.py           ← 通用 Skill 桥
└── packages/                     ← 包安装目标（空目录）
```

## 骨架 Handler

| 文件 | 指令 | 说明 |
|------|------|------|
| `codec.py` | `encode;base64` `encode;hex` | Base64/Hex 编解码 |
| `key.py` | `key;register` `key;revoke` `key;list` | 密钥路由（不存储，按 routing 配置分发） |
| `adapters.py` | — | 通用响应适配器协议 |
| `skill_bridge.py` | — | 通用桥——一个 handler，N 个 skill 共享 |

## 包 Handler（运行时安装）

以下能力由指令包提供，安装到 `packages/` 目录：

| 包 | 指令 |
|------|------|
| files | 文件;读写/列表/移动 |
| git | Git;状态/推送 |
| mail | 邮件;发送 |
| system | 系统;健康/状态 |
| media | 媒体;加载/下载 |
| render | 资源渲染 |
| terminal | 终端;命令 |
| mcp-bridge | MCP 桥接 |
| copilot-browser | 浏览器操作 |

安装：`AI:install,<包路径>`

## 启动

```bash
cd server/agent-copilot
python3 text-cli-copilot.py
```

服务监听 `127.0.0.1:20260`。

### 验证

```bash
curl http://localhost:20260/health
# {"status": "ok"}

curl -X POST http://localhost:20260/cli/text_cli \
  -H 'Authorization: Bearer <token>' \
  -d '{"prompt":"AI:encode;base64,hello"}'
```

## 安全模型

### 凭据注入

Git Token 和 SMTP 密码通过**环境变量注入**，不写入配置文件：

```json
"credentials": {
  "git;push": {"value": "${GIT_TOKEN}", "remote_url": null},
  "email;send": {
    "value": "${SMTP_PASSWORD}",
    "smtp_host": "smtp.example.com",
    "smtp_user": "${SMTP_USER}"
  }
}
```

### 鉴权

所有 `/cli/text_cli` POST 请求需 `Bearer Token`。

---

*text-cli 项目的一部分。由 lemondy 发起，Tide 🌊 实现。*
