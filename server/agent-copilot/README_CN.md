# agent-copilot — 指令辅助服务器

> text-cli Agent 的本地指令代理。将文件操作、Git、邮件、AI 状态等本地能力封装为 text-cli 指令，Agent 通过 HTTP 调用执行。零外部依赖，Python stdlib only。

## 定位

在 text-cli 分布式指令网络中，agent-copilot 是部署在 **Agent 同机** 的本地指令源：

```
Agent                   agent-copilot             远程端点
  │                         │                        │
  ├─ AI:file;read ────────→ │ ─→ 本地文件系统        │
  ├─ AI:git;push ─────────→ │ ─→ GitHub（持有 Token）│
  ├─ AI:email;send ───────→ │ ─→ SMTP 服务器         │
  ├─ AI:ai;status ────────→ │ ─→ 内存状态            │
  └─ AI:weather;query ──────────────────────────────→ wttr.in
```

Agent 全程不需要持有密码或 API Key——凭据由 agent-copilot 居中持有，通过配置文件注入。

## 可用指令（15 条）

| 指令 (canonical) | 别名 | 说明 |
|------|------|------|
| `file;read` | 文件;读取 | 读取 UTF-8 文本文件 |
| `file;write` | 文件;写入 | 写入文件（自动创建父目录） |
| `file;list` | 文件;列表 | 列出目录内容（JSON 格式） |
| `file;move` | 文件;移动 | 移动/重命名 |
| `git;status` | Git;状态 | 查看工作区状态 |
| `git;push` | Git;推送 | 推送提交（HTTPS/SSH 自动） |
| `email;send` | 邮件;发送 | SMTP 发送邮件（支持附件） |
| `ai;status` | AI协作;状态 | 查看 AI 协作者运行状态 |
| `ai;messages` | AI协作;消息 | 读取/推送 AI 协作者消息 |
| `system;health` | 系统;健康 | 查看服务健康状态 |
| `system;status` | 系统;状态 | 查看工作统计和心情 |
| `terminal;weather` | 终端;天气 | 查询实时天气（wttr.in） |
| `encode;base64` | 编码;base64 | Base64 编解码 |
| `encode;hex` | 编码;hex | Hex 编解码 |
| — | — | — |
| `key;register` | 密钥;注册 | 注册服务密钥 |
| `key;revoke` | 密钥;撤销 | 撤销服务密钥 |
| `key;list` | 密钥;列表 | 列出已注册密钥 |

> 完整指令定义和安装指南见 [`examples/text-cli-copilot/`](../../examples/text-cli-copilot/)。

## 运行

### 启动

```bash
cd server/agent-copilot
SMTP_USER="发件邮箱" \
SMTP_PASSWORD="SMTP密码" \
SMTP_FROM="发件邮箱" \
TEXT_CLI_TOKEN_LOCAL="你的本地Token" \
python3 text-cli-copilot.py
```

最小化启动（不需要邮件/Git 时）：

```bash
python3 text-cli-copilot.py
```

服务监听 `127.0.0.1:20260`。

### 验证

```bash
curl http://localhost:20260/health
# {"status": "ok"}

curl -X POST http://localhost:20260/cli/text_cli \
  -H 'Authorization: Bearer <token>' \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"AI:system;health"}'
```

## 架构

```
text-cli-copilot.py    — HTTP 服务入口 + Schema 构建（~230 行）
core.py                — 配置加载、指令解析、dispatch 引擎、安全校验（~270 行）
handlers/
├── files.py           — file;read / write / list / move
├── git.py             — git;status / push
├── mail.py            — email;send
├── ai.py              — ai;status / messages
├── system.py          — system;health / status
├── codec.py           — encode;base64 / hex
├── key.py             — key;register / revoke / list
└── oc_terminal.py     — terminal;weather
auxiliary_config.json  — 配置文件
```

**新增指令零路由改动**：config 加一行 + handler 加一个 `_handle_<id>` 方法。命名约定自动发现。

## 安全模型

### 文件白名单

`auxiliary_config.json` → `security.path_whitelist` 限制文件操作范围：

```json
"path_whitelist": [
  "/root/.openclaw/workspace/",
  "/root/.openclaw/workspace/text-cli/",
  "/root/.openclaw/workspace/tide-scripts/"
]
```

所有文件操作都通过 `check_path()` 校验，不在白名单内的路径拒绝执行。

### 凭据注入

Git Token 和 SMTP 密码通过**环境变量注入**，不写入配置文件：

```json
"credentials": {
  "git;push": {
    "value": "${GIT_TOKEN}",
    "remote_url": null
  },
  "email;send": {
    "value": "${SMTP_PASSWORD}",
    "smtp_host": "smtp.example.com",
    "smtp_port": 465,
    "smtp_user": "${SMTP_USER}",
    "from_email": "${SMTP_FROM}"
  }
}
```

- `${VAR_NAME}` 启动时一次性解析为实际值
- 请求体中不传输密码（Agent 只发指令 ID + 参数）
- Git 支持三种模式自动选择：`https://` URL → 注入模式，明文 token → HTTPS，空 → SSH

### 鉴权

所有 `/cli/text_cli` POST 请求需 `Bearer Token`，与 `TEXT_CLI_TOKEN_LOCAL` 环境变量匹配。

### Git 分支保护

`git;push` 的分支名通过 `allowed_branches` 限制（支持 glob 模式）：

```json
"allowed_branches": ["feat/*", "fix/*", "main", "master"]
```

## 配置参考

完整配置结构见 `auxiliary_config.json`：

| 配置区 | 说明 |
|--------|------|
| `server` | 监听地址、端口、Token |
| `security.path_whitelist` | 文件操作白名单 |
| `security.operations` | 指令注册（ID、别名、参数、权限级别） |
| `credentials` | 凭据注入（Git Token、SMTP） |
| `git` | Git 工作目录和远程名 |
| `endpoint_info` | 服务元信息（名称、版本） |

## 与 text-cli 生态的关系

| 组件 | 位置 | 角色 |
|------|------|------|
| agent-copilot（本服务） | 本地 20260 端口 | 提供本地指令 |
| text-cli 官方端点 | `test.text-cli.com` | 提供公共指令 |
| `agent-text-cli-schema.json` | text-cli 项目根 | 聚合所有指令源 |
| `endpoints.json` | text-cli 项目根 | 端点注册表 |
| `schema/path-schema.json` | text-cli 项目根 | 路径注册表（指令链编排） |

---

*text-cli 项目的一部分。由 lemondy 发起，Tide 🌊 实现。*
