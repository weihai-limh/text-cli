# agent-copilot — 指令辅助服务器

> text-cli Agent 的本地指令代理。将文件操作、Git、邮件、AI 状态等本地能力封装为 text-cli 指令，Agent 通过 HTTP 调用执行。零外部依赖，Python stdlib only。

## 定位

在 text-cli 分布式指令网络中，agent-copilot 是部署在 **Agent 同机** 的本地指令源：

```
Agent                   agent-copilot             远程端点
  │                         │                        │
  ├─ 指令:文件;读取 ───────→ │ ─→ 本地文件系统        │
  ├─ 指令:Git;推送 ───────→ │ ─→ GitHub（持有 Token） │
  ├─ 指令:邮件;发送 ───────→ │ ─→ SMTP 服务器         │
  ├─ 指令:AI协作;状态 ─────→ │ ─→ 内存状态            │
  └─ 指令:天气;查询 ─────────────────────────────────→ wttr.in
```

Agent 全程不需要持有密码或 API Key——凭据由 agent-copilot 居中持有，通过配置文件注入。

## 可用指令（14 条）

| 指令 | 参数 | 说明 |
|------|------|------|
| `文件;读取` | 文件路径 | 读取 UTF-8 文本文件 |
| `文件;写入` | 文件路径, 内容 | 写入文件（自动创建父目录） |
| `文件;列表` | 目录路径(可选) | 列出目录内容（JSON 格式） |
| `文件;移动` | 源路径, 目标路径 | 移动/重命名（同目录=重命名） |
| `Git;状态` | — | 查看工作区状态 |
| `Git;推送` | 分支名 | 推送提交（HTTPS/SSH 自动选择） |
| `邮件;发送` | 收件人, 主题, 正文, 附件(可选) | SMTP 发送邮件 |
| `AI协作;状态` | 模式(可选,A/B) | 查看 AI 协作者运行状态 |
| `AI协作;消息` | 条数 或 推送,消息JSON | 读取/推送 AI 协作者消息 |
| `系统;健康` | — | 查看服务健康状态 |
| `系统;状态` | — | 查看工作统计和心情 |
| `终端;天气` | 城市名 | 查询实时天气（wttr.in） |
| `编码;base64` | 模式, 内容 | Base64 编解码 |
| `编码;hex` | 模式, 内容 | Hex 编解码 |

## 运行

### 启动

```bash
cd /root/text-cli-copilot
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
  -d '{"prompt":"指令:系统;健康"}'
```

## 架构

```
text-cli-copilot.py    — HTTP 服务入口 + Schema 构建（~230 行）
core.py                — 配置加载、指令解析、dispatch 引擎、安全校验（~270 行）
handlers/
├── files.py           — 文件;读取/写入/列表/移动
├── git.py             — Git;状态/推送
├── mail.py            — 邮件;发送
├── ai.py              — AI协作;状态/消息
├── system.py          — 系统;健康/状态
├── codec.py           — 编码;base64/hex
└── oc_terminal.py     — 终端;天气
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
  "/root/.openclaw/workspace/tide-scripts/",
  "/root/text-cli-copilot/"
]
```

所有文件操作（读取/写入/列表/移动）都通过 `check_path()` 校验，不在白名单内的路径拒绝执行。

### 凭据注入

Git Token 和 SMTP 密码通过**环境变量注入**，不写入配置文件：

```json
"credentials": {
  "Git;推送": {
    "value": "${GIT_TOKEN}",
    "remote_url": null
  },
  "邮件;发送": {
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

`Git;推送` 的分支名通过 `allowed_branches` 限制（支持 glob 模式）：

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
