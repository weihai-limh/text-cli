# text-cli-copilot 技术方案

> 把本地操作也变成文本指令——text-cli 协议在本地机器上的可插拔实现。
>
> 状态：v2.0 / 已实现（15 指令 + AI 状态端点）
> 日期：2026-05-10
> 作者：Tide 🌊
> 澄清轮次：lemondy + Tide，8 轮对齐
> 实现：6 检查点全部通过，45 条验证零失败

---

## 1. 定位与边界

### 1.1 这是什么

**一个零依赖的本地 HTTP 服务，将文件读写、Git 操作、邮件发送等本地操作统一封装为 text-cli 指令。**

Agent 通过标准 text-cli 协议调用——`AI:file;read,/path/to/note.md` 和 `AI:weather;query,明天,威海` 使用同一种格式、同一套心智模型。

```
Agent 视角:
  AI:weather;query,明天,威海       → 远程指令服务器 → wttr.in
  AI:file;read,/path/to/note.md   → copilot(localhost) → 本地文件系统
  AI:git;push,main                → copilot(localhost) → GitHub
  AI:email;send,...               → copilot(localhost) → SMTP

  都是 "AI:domain;action,params" → 同一种格式，同一套心智模型
```

### 1.2 这不是什么

- **不是远程端点**——它只接受 localhost 请求，和 Agent 在同一台机器上
- **不是凭据中枢**——凭据通过环境变量注入，不和第三方共享
- **不是新的协议**——完全遵循 text-cli 协议：`AI:领域;动作,参数`

### 1.3 在 lemondy 统一架构中的位置

```
指令服务器（枢纽，远程）
    └─── copilot（本组件，本地 localhost）
          ├── 操作本地文件
          ├── 操作本地 Git
          ├── 发送邮件（注入指令服务器持有的凭据）
          ├── 系统状态监控（健康/状态指令）
          ├── AI 协作者状态桥（/ai_status + ai;status）
          └── 编解码、终端、密钥管理等辅助能力
```

copilot 是 lemondy 统一架构中四个可插拔组件之一——它在请求端同机执行，通过 text-cli 协议与 Agent 通信。

---

## 2. 架构概览

```
┌─────────────────────────────────────────────────┐
│                   Agent                          │
│  (OpenClaw / 其他平台)                           │
│                                                  │
│  推理 → 发送 text-cli 指令 → 解析响应             │
└──────────────┬──────────────────────────────────┘
               │ POST /cli/text_cli
               │ {"prompt": "AI:file;read,/path"}
               │ Authorization: Bearer <token>
               ▼
┌─────────────────────────────────────────────────┐
│              text-cli-copilot                     │
│              localhost:20260                       │
│                                                  │
│  ┌─────────────┐  ┌──────────────┐               │
│  │ Token 校验   │  │ 指令解析器    │               │
│  └──────┬──────┘  └──────┬───────┘               │
│         │                │                       │
│         ▼                ▼                       │
│  ┌─────────────────────────────┐                 │
│  │       安全层                 │                 │
│  │  · 路径白名单（硬边界）      │                 │
│  │  · 操作分级（read/write/send）│                │
│  │  · 分支白名单（Git push）    │                 │
│  └─────────────┬───────────────┘                 │
│                │                                 │
│                ▼                                 │
│  ┌─────────────────────────────┐                 │
│  │       执行层                 │                 │
│  │  · 文件: pathlib 读写        │                 │
│  │  · Git: subprocess          │                 │
│  │  · 邮件: smtplib             │                 │
│  └─────────────┬───────────────┘                 │
│                │                                 │
│  ┌─────────────┴───────────────┐                 │
│  │  凭据注入（启动时一次性解析）│                 │
│  │  · ${SMTP_PASSWORD}         │                 │
│  │  · ${TEXT_CLI_TOKEN_LOCAL}  │                 │
│  └─────────────────────────────┘                 │
│                                                  │
│  GET /text_cli_schema.json                       │
│  → 返回可用指令清单（供同步 Skill 聚合）          │
└─────────────────────────────────────────────────┘
```

---

## 3. 协议设计

### 3.1 指令入口

**端点**：`POST /cli/text_cli`

**请求格式**（与 text-cli 公共端点完全一致）：

```json
{
  "prompt": "AI:领域;动作,参数1,参数2,..."
}
```

**双前缀协议**（v1.1+）：`指令:` 和 `AI:` 前缀同等效力，解析器统一处理。Unicode 冒号 `：` 与半角 `:` 等效。

```
AI:file;read,/path                → English canonical
AI：file;read,/path               → Unicode colon, same result
指令:文件;读取,/path               → Legacy prefix + Chinese alias
指令：文件;读取,/path              → Unicode colon + alias
```

解析器正则：`^(?:指令|AI)[：:]([^;]+);([^,]+)(?:,(.+))?$`

**请求头**：

```
Authorization: Bearer <token>
Content-Type: application/json
```

**响应格式**（text-cli 标准）：

```json
{
  "rst_types": "text",
  "rst_data": {
    "text": "<操作结果>"
  }
}
```

错误响应：

```json
{
  "rst_types": "text",
  "rst_data": {
    "text": "[错误] Path not in whitelist: /etc/passwd"
  },
  "rst_err": "path_denied"
}
```

### 3.2 发现端点

**端点**：`GET /text_cli_schema.json`

**无需鉴权**（只返回指令清单，不暴露凭据）。

**返回格式**：

```json
{
  "endpoint": {
    "name": "指令辅助服务器",
    "url": "http://localhost:20260",
    "version": "2.0.0"
  },
  "directives": [
    {
      "id": "file;read",
      "aliases": ["文件;读取"],
      "description": "读取本地文件内容",
      "description_en": "Read local file content",
      "parameters": ["文件路径"],
      "parameters_en": ["file_path"],
      "returns": "rst_data.text = file content"
    },
    {
      "id": "git;push",
      "aliases": ["Git;推送"],
      "description": "推送本地提交到远程仓库",
      "description_en": "Push local commits to remote",
      "parameters": ["分支名"],
      "parameters_en": ["branch_name"],
      "returns": "rst_data.text = push result"
    }
  ]
}
```

### 3.3 指令解析规则

1. 双前缀匹配：`指令:` 或 `AI:`（Unicode 冒号等效）
2. 分号 `;` 分割领域和动作
3. 逗号 `,` 分割参数
4. **最后一个参数贪婪匹配**——解决参数内容含逗号的问题（如邮件正文含逗号）

```
"AI:email;send,user@example.com,project update,Body text, with commas"
     → domain=email, action=send, params=["user@example.com", "project update", "Body text, with commas"]
```

5. **别名解析**：英文规范名和中文别名双向等效。`AI:file;read` ⇔ `AI:文件;读取` ⇔ `指令:file;read` ⇔ `指令:文件;读取` 全部路由到同一个 handler。

每条指令的参数数量由配置中的 `operations` 字段的 `parameters` 定义确定。

### 3.4 指令命名规范

**英文是规范名（Canonical），中文是别名（Alias）**。指令服务注册时通过 `aliases` 字段声明中文别名：

```json
{
  "operations": {
    "file;read":       { "level": "read",  "aliases": ["file;read", "文件;读取"] },
    "file;write":      { "level": "write", "path_check": true, "aliases": ["file;write", "文件;写入"] },
    "git;status":      { "level": "read",  "aliases": ["git;status", "Git;状态"] },
    "git;push":        { "level": "push",  "allowed_branches": ["feat/*", "fix/*", "main", "master"], "aliases": ["git;push", "Git;推送"] },
    "email;send":      { "level": "send",  "aliases": ["email;send", "mail;send", "邮件;发送"] }
  }
}
```

Dispatch 时通过 `alias_map` 查规范 ID——四种前缀×别名组合全部等效。

---

## 4. 安全模型

### 4.1 凭据隔离

| 凭证 | 存储位置 | 注入方式 | Agent 可见 |
|------|---------|---------|-----------|
| Access Token | 环境变量 `TEXT_CLI_TOKEN_LOCAL` | 请求头校验 | 是（请求头传递） |
| SMTP 密码 | 环境变量 `SMTP_PASSWORD` | 服务启动时解析 | **否** |
| SMTP 用户名 | 环境变量 `SMTP_USER` | 服务启动时解析 | **否** |
| Git Token | 环境变量 `GIT_TOKEN` | 服务启动时解析 | **否** |

Agent 只持有 Access Token——这个 Token 可以随时撤销，即使泄露也不会暴露邮件密码或 Git 凭据。

### 4.2 路径白名单（硬边界）

```json
{
  "path_whitelist": [
    "/root/.openclaw/workspace/",
    "/root/.openclaw/workspace/text-cli/",
    "/root/.openclaw/workspace/tide-scripts/"
  ]
}
```

**越界 = 直接拒绝，不提示、不回旋**。白名单外的路径，服务器返回错误码，不做任何操作。

### 4.3 操作分级

| 操作 | 级别 | 路径检查 | 分支检查 |
|------|------|---------|---------|
| `file;read` | read | 是 | — |
| `git;status` | read | — | — |
| `file;write` | write | 是 | — |
| `git;push` | push | — | 是 |
| `email;send` | send | — | — |

**第一版不做 confirm 机制**。理由见 §7.1。

### 4.4 隐含的信任假设

当前安全模型基于一个前提：**copilot 和调用方在同一台机器上，且 localhost 网络接口受操作系统保护。** 这个假设在单人部署场景下成立。当 copilot 支持远程部署时，需要追加传输层加密（TLS）和独立的鉴权体系。

---

## 5. 配置设计

### 5.1 配置文件

`auxiliary_config.json`——和 `text-cli-copilot.py` 同目录。

```json
{
  "server": {
    "host": "127.0.0.1",
    "port": 20260,
    "token": "${TEXT_CLI_TOKEN_LOCAL}"
  },
  "security": {
    "path_whitelist": [
      "/root/.openclaw/workspace/"
    ],
    "operations": {
      "file;read":  { "level": "read",  "aliases": ["file;read", "文件;读取"] },
      "git;status": { "level": "read",  "aliases": ["git;status", "Git;状态"] },
      "file;write": { "level": "write", "path_check": true, "aliases": ["file;write", "文件;写入"] },
      "file;list":  { "level": "read",  "path_check": true, "aliases": ["file;list", "文件;列表"] },
      "file;move":  { "level": "write", "path_check": true, "aliases": ["file;move", "文件;移动"] },
      "git;push":   { "level": "push",  "allowed_branches": ["feat/*", "fix/*", "main", "master"], "aliases": ["git;push", "Git;推送"] },
      "email;send": { "level": "send",  "aliases": ["email;send", "mail;send", "邮件;发送"] },
      "system;health": { "level": "read", "aliases": ["system;health", "系统;健康"] },
      "system;status": { "level": "read", "aliases": ["system;status", "系统;状态"] },
      "ai;status":  { "level": "read",  "aliases": ["ai;status", "AI协作;状态"] },
      "ai;messages": { "level": "read",  "enabled": false, "aliases": ["ai;messages", "AI协作;消息"] },
      "terminal;weather": { "level": "read", "aliases": ["terminal;weather", "终端;天气"] },
      "encode;base64": { "level": "read", "aliases": ["encode;base64", "编码;base64"] },
      "encode;hex":  { "level": "read",  "aliases": ["encode;hex", "编码;hex"] },
      "key;register": { "level": "write", "sensitive": true, "aliases": ["key;register", "密钥;注册"] },
      "key;revoke":   { "level": "write", "sensitive": true, "aliases": ["key;revoke", "密钥;撤销"] },
      "key;list":    { "level": "read",  "sensitive": true, "aliases": ["key;list", "密钥;列表"] }
    }
  },
  "credentials": {
    "git;push": {
      "value": "${GIT_TOKEN}",
      "remote_url": null
    },
    "email;send": {
      "value": "${SMTP_PASSWORD}",
      "smtp_host": "smtp.mxhichina.com",
      "smtp_port": 465,
      "smtp_user": "${SMTP_USER}",
      "from_email": "${SMTP_FROM}"
    }
  },
  "git": {
    "workdir": null,
    "remote_name": "origin"
  },
  "endpoint_info": {
    "name": "指令辅助服务器",
    "description": "本地文件、Git、邮件操作代理",
    "version": "2.0.0"
  }
}
```

### 5.2 统一凭据字段

每条指令的凭据由 `credentials.<指令标识>.value` 字段统一管理。**一个字段，值本身的格式决定行为模式：**

| `value` 的值 | 模式 | 含义 |
|:---|:---|:---|
| `"https://..."` | Mode 1（注入） | 指向指令服务器，运行时向它请求凭据 |
| `"${VAR_NAME}"` | Mode 2（环境变量） | 从环境变量解析，启动时一次性替换 |
| `"ghp_xxxx"` 等明文 | Mode 2（明文） | 直接作为 token 使用 |
| `null` / `""` / 字段不存在 | Mode 3（SSH/本地） | 无凭据，依赖本地 SSH agent |

### 5.3 配置解析规则

- `${VAR_NAME}` 占位符在服务启动时一次性从环境变量中解析
- 环境变量不存在的占位符 → 打印警告，降级到 Mode 3（不中断启动）
- 配置中不存任何真实凭据——它们只在环境变量中

### 5.4 Git 工作目录

`git.workdir`：
- `null`（默认）：使用服务启动时的当前工作目录
- `"/path/to/repo"`：明确指定 Git 仓库路径

---

## 6. 指令参考

copilot 共注册 15 条指令。完整定义在 `auxiliary_config.json`。

### 6.1 `file;read` — 读取文件

```
AI:file;read,/path/to/file.md
```

**参数**：`path`（必填）——相对或绝对路径

**流程**：
1. 校验路径是否在白名单内 → 越界拒绝
2. `Path.read_text(encoding='utf-8')`
3. 返回文件内容 + 字节数

**返回**：
```json
{
  "rst_types": "text",
  "rst_data": {
    "text": "<文件内容>",
    "size": 1234
  }
}
```

**错误**：
- 路径越界 → `"rst_err": "path_denied"`
- 文件不存在 → `"rst_err": "file_not_found"`
- 文件过大（>10MB）→ `"rst_err": "file_too_large"`

### 6.2 `git;push` — Git 推送

```
AI:git;push,main
```

**参数**：`branch`（必填），支持通配符（`feat/*`）

**完整执行流**：

```
1. 校验分支名 ∈ allowed_branches
2. _resolve_credential(config.credentials["git;push"].value)
3. Mode 2（https）：git push https://TOKEN@remote branch
   → 失败 → git push remote branch (SSH 降级)
4. Mode 3（ssh）：git push remote branch (SSH)
```

**remote URL 获取**：优先读 `credentials["git;push"].remote_url`，若为 `null` 则自动从 `git remote get-url origin` 获取。

**HTTPS push 实现**：使用 inline URL（`git push https://TOKEN@github.com/user/repo.git branch`），不修改仓库的 remote 配置。

**返回**：
```json
{
  "rst_types": "text",
  "rst_data": {
    "text": "Push successful: main → origin/main [via HTTPS]",
    "auth_mode": "https"
  }
}
```

### 6.3 其余指令一览

| 指令 (canonical) | 别名 | 说明 |
|:---|:---|:---|
| `file;write` | 文件;写入 | 写入文件（自动创建父目录） |
| `file;list` | 文件;列表 | 列出目录内容（JSON） |
| `file;move` | 文件;移动 | 移动/重命名文件 |
| `git;status` | Git;状态 | 查看工作区状态 |
| `email;send` | 邮件;发送,mail;send | SMTP 发送邮件（支持附件） |
| `terminal;weather` | 终端;天气 | 查询城市天气（wttr.in） |
| `system;health` | 系统;健康 | 运维视角状态（运行时间、内存） |
| `system;status` | 系统;状态 | 工作心情 + 请求统计 |
| `ai;status` | AI协作;状态 | AI 协作者状态桥（A/B 模式） |
| `encode;base64` | 编码;base64 | Base64 编解码 |
| `encode;hex` | 编码;hex | Hex 编解码 |
| `key;register` | 密钥;注册 | 注册服务密钥 |
| `key;revoke` | 密钥;撤销 | 撤销服务密钥 |
| `key;list` | 密钥;列表 | 列出已注册密钥 |

> 完整指令定义和安装指南见 [`examples/text-cli-copilot/`](../../examples/text-cli-copilot/)。

---

## 7. 设计决策

### 7.1 confirm 机制：第一版不做

**第一版不做的理由**：
1. localhost 服务——调用方和服务器在同一信任域，不需要防自己
2. Agent Skill 模型目前没有内置的 confirm→重发逻辑，引入 confirm 会增加 Agent 侧的复杂度
3. 路径白名单 + 分支白名单已经提供了足够的硬防护

**后续再做的触发条件**：copilot 支持远程部署（非 localhost 访问）。

### 7.2 文件过大保护

`file;read` 设置 10MB 上限。超过上限返回错误而非截断——截断让 Agent 看到不完整数据，比直接报错更危险。

### 7.3 Git 凭据策略：统一字段 + 全模式 SSH 降级

Git 推送的凭据由 `credentials["git;push"].value` 统一管理，字段值格式决定行为。三种模式的终端保障都是 SSH——push 不会因为 token 问题而断路。

和邮件的凭据设计对称：
- `git;push` 的 `value` = HTTPS token（env var/明文/注入）
- `email;send` 的 `value` = SMTP 密码（env var）
- 同一个字段名 `value`，同一个解析函数 `_resolve_credential()`，语义由操作定义

**第一版只验证 Mode 2（`${GIT_TOKEN}`）+ Mode 3（SSH）。** Mode 1（指令服务器注入）代码预留。

### 7.4 端口选择：继承 20260

选择 20260 而非 8900——用户已经知道这个端口。且 20260 是一个不常见的端口号，冲突概率低。

---

## 8. 内部架构

### 8.1 Handler 注册表

新增指令的成本恒定——不需要改路由逻辑。

```python
class Copilot:
    def __init__(self, config_path):
        self._handlers = {}        # canonical_id → handler
        self._alias_map = {}       # alias → canonical_id
        
        for op_id, op_config in self.config['security']['operations'].items():
            aliases = op_config.get('aliases', [])
            source_id = aliases[0] if aliases else op_id
            handler_name = '_handle_' + source_id.replace(';', '_').replace(':', '_')
            if hasattr(self, handler_name):
                self._handlers[op_id] = getattr(self, handler_name)
            for alias in op_config.get('aliases', []):
                self._alias_map[alias] = op_id
            self._alias_map[op_id] = op_id
```

**新增一条指令只需两步**：
1. 在 `config.operations` 加一行配置（安全级别、路径检查、凭据绑定、`aliases`）
2. 在 `Copilot` 类加一个 `_handle_xxx_xxx()` 方法

注册由命名约定自动完成，dispatch 通过 `_alias_map` 查规范 ID——英文和中文走同一个 handler。

### 8.2 凭据解析器

`_resolve_credential(value)` 是 `credentials` 配置的唯一入口。所有 handler 通过它获取凭据，不直接读 `os.environ`。返回值统一为 `{'mode': 'https'|'ssh'|'inject', 'token'?: str, 'url'?: str, 'warn'?: str}`。

### 8.3 指令解析器

`_parse_instruction(prompt)` → `{'domain': str, 'action': str, 'params': list}`。四个前缀全部等效（`指令:` / `AI:` / `指令：` / `AI：`），最后一个参数贪婪匹配。

---

## 9. 实现路线

### 阶段 1：骨架验证 ✅

- [x] `text-cli-copilot.py`（stdlib only，`http.server`）
- [x] `auxiliary_config.json` + `_resolve_env()` 启动时解析
- [x] `POST /cli/text_cli` + Token 校验
- [x] 指令解析器（双前缀 + 贪婪参数）
- [x] Dispatch 骨架（alias_map + handler 命名约定自动注册）

### 阶段 2：文件操作 ✅

- [x] 路径白名单（前缀 + 精确，`Path.resolve()` 防 `../` 绕过）
- [x] `file;read`：UTF-8，10MB 上限，越界/不存在/编码错误
- [x] `file;write`：自动创建父目录，写入确认 + 字节数
- [x] 中文 alias（`文件;读取` / `文件;写入`）

### 阶段 3：Git 操作 ✅

- [x] `git;status`：`subprocess.run`，30s 超时
- [x] 凭据解析器 `_resolve_credential()`（Mode 1 预留 / Mode 2 env/明文 / Mode 3 SSH）
- [x] `git;push`：HTTPS inline URL → 失败降级 SSH
- [x] 分支白名单（`fnmatch` 通配符）
- [x] 远程 URL 自动获取

### 阶段 4：邮件发送 ✅

- [x] SMTP_SSL（mxhichina.com:465）
- [x] MIME 邮件（UTF-8）+ 附件支持
- [x] 真实发送验证通过（含附件）

### 阶段 5：发现端点 ✅

- [x] `GET /text_cli_schema.json`（无需鉴权）
- [x] 15 条指令完整字段（多语言）

### 阶段 6：集成验证 ✅

- [x] 45 条验证零失败（8 指令 × 中英双语 + 错误路径）
- [x] README + 聚合 Schema 注册（`endpoints.json` + `agent-text-cli-schema.json`）

### Phase 3 更新（2026-05-10）

- [x] 代码全英文化
- [x] 解析器三实现统一（`^(?:指令|AI)[：:]`）
- [x] 配置操作 ID 翻转：中文 → 英文规范名，中文移入 aliases
- [x] 凭据 key 同步更新：`Git;推送` → `git;push`，`邮件;发送` → `email;send`

---

## 10. 与多源聚合架构的咬合

copilot 在聚合 Schema 中的位置：

```
同步 Skill（冷路径）
  ├── 拉取 test.text-cli.com/text_cli_schema.json
  ├── 拉取 cliweather.instantiated.space/text_cli_schema.json
  └── 拉取 localhost:20260/text_cli_schema.json        ← 本组件
         ↓
  agent-text-cli-schema.json（聚合结果）
         ↓
Agent Skill（热路径）
  └── 读本地 JSON → rank 路由 → POST 对应端点
```

Agent 看到的效果：

```json
{
  "file;read": [
    {"endpoint": "http://localhost:20260/cli/text_cli", "rank": 1}
  ],
  "weather;query": [
    {"endpoint": "https://test.text-cli.com/cli/text_cli", "rank": 2},
    {"endpoint": "https://cliweather.instantiated.space/cli/text_cli", "rank": 3}
  ]
}
```

本地文件操作和远程天气服务在 Schema 里地位平等——Agent 不区分来源。

---

## 11. 与思维路标文档的关系

本方案是 `指令辅助服务器_思维路标_CN.md` 的可执行设计稿。

| 思维路标章节 | 本方案对应内容 |
|-------------|---------------|
| §1 起点 + §1.1 跨机器边界 | §1 定位与边界 |
| §2 首批 5 条指令 | §6 指令参考 |
| §3 多源聚合咬合 | §10 咬合设计 |
| §4 分工线 | §1.3 架构位置 |
| §5 + §5.3 安全边界与信任假设 | §4 + §7.1 安全模型与设计决策 |
| §6 部署模式 | §9 实现路线（集成模式） |
| §10 + §10.3 万能代理与凭据对称 | §5.2 统一凭据字段、§8.1 注册模式 |
| §11 概念咬合 | §2 架构图体现 Skill+路径+指令三位一体 |
| §12 降级链 | §6.2 Git HTTPS→SSH 降级、§4.1 凭据隔离 |

---

## 12. 已澄清的决策汇总

| # | 决策 | 状态 |
|---|------|------|
| 1 | 主文件名 `text-cli-copilot.py` | ✅ |
| 2 | 端口 20260 | ✅ |
| 3 | 统一凭据字段 `credentials.<op>.value`，值格式决定行为 | ✅ |
| 4 | Git 全模式 → SSH 降级（Mode 1/2 HTTPS 失败后自动切 SSH） | ✅ |
| 5 | 第一版验证 Mode 2（env）+ Mode 3（SSH），Mode 1 代码预留 | ✅ |
| 6 | confirm 推迟—localhost 信任域不需要 | ✅ |
| 7 | 万能代理推迟——首批 5 条核心指令 | ✅ |
| 8 | Handler 注册表模式——新增指令两步完成，dispatch 不需改 | ✅ |
| 9 | SMTP 默认 mxhichina.com:465 | ✅ |
| 10 | Git workdir = 启动时 cwd（`null`），可通过 config 覆盖 | ✅ |
| 11 | HTTPS push 用 inline URL，不修改仓库 remote 配置 | ✅ |
| 12 | 双前缀协议：`指令:` / `AI:` + Unicode 冒号等效 | ✅ |
| 13 | 英文规范名 + 中文别名，aliases 双向映射 | ✅ |
| 14 | 元指令走同一套注册/解析/Dispatch 管道，不在外面开特殊路径 | ✅ |
| 15 | AI 状态用主动写入模式（检查点 POST /ai_status），非轮询 | ✅ |
| 16 | `ai;status` 不设过期标记——"查看是一种关心" | ✅ |
| 17 | 所有返回内容英文化（A/B 模式均英文输出） | ✅ |
| 18 | 配置操作 ID 英文规范名 + aliases 中文名 | ✅ |

---

*本文档由 Tide 🌊 基于 lemondy 的统一架构、2026-05-07 思维路标文档、以及 lemondy + Tide 八轮澄清综合撰写。v1.1 更新配置+Git凭据+内部架构。v1.2 加入多语言支持。v1.3 更新为已实现状态，新增 3 条元指令和 AI 状态端点。v2.0（Phase 3）更新双前缀协议 + 英文规范名 + 配置翻转。*
