# text-cli-copilot 技术方案

> 指令辅助服务器的正式实现——把本地操作也变成文本指令。
>
> 状态：v1.3 / 已实现（8 指令 + AI 状态端点）
> 日期：2026-05-07
> 作者：Tide 🌊
> 澄清轮次：lemondy + Tide，8 轮对齐
> 实现：6 检查点全部通过，45 条验证零失败

---

## 1. 定位与边界

### 1.1 这是什么

**一个零依赖的本地 HTTP 服务，将文件读写、Git 操作、邮件发送等本地操作统一封装为 text-cli 指令。Agent 通过标准 text-cli 协议调用，无需持有任何凭据。**

### 1.2 这不是什么

- **不是指令服务器**——它不是凭据中枢，不持有映射表，不转发请求
- **不是远程端点**——它只接受 localhost 请求，和 Agent 在同一台机器上
- **不是新的协议**——它完全遵循 text-cli 的 `指令:领域;动作,参数` 格式

### 1.3 在 lemondy 统一架构中的位置

```
指令服务器（枢纽，远程）
    └─── 辅助服务器（本组件，本地 localhost）
          ├── 操作本地文件
          ├── 操作本地 Git
          ├── 发送邮件（注入指令服务器持有的凭据）
          ├── 系统状态监控（健康/状态指令）
          └── AI 协作者状态桥（/ai_status + AI协作;状态）
```

辅助服务器是四个可插拔组件中**唯一跨机器边界运行的**——它在请求端同机执行，接收指令服务器的凭据注入。

### 1.4 与现有代码的关系

`port_20260.py`（`old_code/`）是本项目的**工作原型**——在 text-cli 项目启动前已经验证了"本地操作代理"的可行性。本方案是它的**正式替代**：

| 维度 | port_20260.py（原型） | text-cli-copilot（本方案） |
|------|----------------------|---------------------------|
| 协议 | 自定义 JSON schema（每个端点不同） | text-cli 统一格式 |
| 依赖 | FastAPI + uvicorn | Python stdlib 单文件 |
| 安全 | SMTP 密码在请求体中传递 | env var 占位符 + config 驱动 |
| 端口 | 20260 | **20260**（继承） |
| 发现 | 无 | GET /text_cli_schema.json |

**替换策略**：copilot 跑通后，port_20260 自然退役。`old_code/` 目录保留作为设计参考。copilot 继承端口 20260 和 SMTP 默认配置（mxhichina.com:465），不继承物品管理、容器管理能力（延后到万能代理阶段）。

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
               │ {"prompt": "指令:文件;读取,/path"}
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
  "prompt": "指令:领域;动作,参数1,参数2,..."
}
```

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
    "text": "[错误] 路径不在白名单内: /etc/passwd"
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
    "version": "1.0.0"
  },
  "directives": [
    {
      "id": "文件;读取",
      "aliases": ["file;read"],
      "description": "读取本地文件内容",
      "description_en": "Read local file content",
      "parameters": ["文件路径"],
      "parameters_en": ["file_path"],
      "returns": "rst_data.text = 文件内容"
    },
    {
      "id": "文件;写入",
      "aliases": ["file;write"],
      "description": "写入内容到本地文件",
      "description_en": "Write content to local file",
      "parameters": ["文件路径", "内容"],
      "parameters_en": ["file_path", "content"],
      "returns": "rst_data.text = 写入确认"
    },
    {
      "id": "Git;状态",
      "aliases": ["git;status"],
      "description": "查看 Git 工作区状态",
      "description_en": "Check Git working tree status",
      "parameters": [],
      "parameters_en": [],
      "returns": "rst_data.text = git status 输出"
    },
    {
      "id": "Git;推送",
      "aliases": ["git;push"],
      "description": "推送本地提交到远程仓库",
      "description_en": "Push local commits to remote",
      "parameters": ["分支名"],
      "parameters_en": ["branch_name"],
      "returns": "rst_data.text = 推送结果"
    },
    {
      "id": "邮件;发送",
      "aliases": ["email;send", "mail;send"],
      "description": "通过预配置 SMTP 发送邮件",
      "description_en": "Send email via pre-configured SMTP",
      "parameters": ["收件人", "主题", "正文"],
      "parameters_en": ["recipient", "subject", "body"],
      "returns": "rst_data.text = 发送状态"
    }
  ]
}
```

### 3.3 指令解析规则

输入 `指令:领域;动作,参数列表`，按以下规则解析：

1. 以 `指令:` 前缀识别
2. 分号 `;` 分割领域和动作
3. 逗号 `,` 分割参数
4. **最后一个参数贪婪匹配**——解决参数内容含逗号的问题（如邮件正文含逗号）

```
"指令:邮件;发送,limh@10000.world,项目更新,这是一段正文，有逗号，没问题"
         → 领域=邮件, 动作=发送, params=["limh@10000.world", "项目更新", "这是一段正文，有逗号，没问题"]
```

每条指令的参数数量由配置中的 `operations` 定义确定。

### 3.4 多语言支持

遵循 SPEC v1.0 §8 的原则——**服务方用母语注册，提供 aliases，翻译在端点层做。**

#### 3.4.1 指令前缀

接受两个等价前缀，不参与语义：

```python
PREFIXES = ['指令:', 'directive:']
```

- `指令:文件;读取,/path`（中文）
- `directive:file;read,/path`（英文）

两者在解析器中走同一路径，前缀仅用于识别，不参与 handler 路由。

#### 3.4.2 语义 ID 的 alias 映射

内部规范 ID 是中文（如 `文件;读取`），配置中的 `aliases` 数组定义等价英文标识：

```json
{
  "operations": {
    "文件;读取": { "level": "read", "aliases": ["file;read"] },
    "文件;写入": { "level": "write", "path_check": true, "aliases": ["file;write"] },
    "Git;状态": { "level": "read", "aliases": ["git;status"] },
    "Git;推送": { "level": "push", "allowed_branches": ["feat/*", "fix/*", "main", "master"], "aliases": ["git;push"] },
    "邮件;发送": { "level": "send", "aliases": ["email;send", "mail;send"] }
  }
}
```

Dispatch 时通过 `alias_map` 查规范 ID：

```
英文请求: "directive:file;read,/path"
  解析 → domain=file, action=read
  dispatch → alias_map["file;read"] = "文件;读取"
  handler → _handle_文件_读取(params)
```

英文和中文请求走到同一个 handler，只是入口不同。多条 alias 可指向同一个规范 ID（如 `email;send` 和 `mail;send` 都指向 `邮件;发送`）。

#### 3.4.3 多语言的边界

| 层 | 多语言 | 说明 |
|:---|:---|:---|
| 指令前缀 | ✅ `指令:` / `directive:` | 两个足够，不引入第三个 |
| 语义 ID | ✅ aliases 映射 | config 驱动，零代码改动 |
| Schema 返回 | ✅ `description_en` + `aliases` | 帮助英文 Agent 理解指令 |
| 错误消息 | ⚠️ 后续 | 第一版中文，后续从 config 读 `messages` 字典 |
| 内部函数名 | ❌ | `_handle_文件_读取` 是内部实现，不对外暴露 |

多语言的成本集中在 config 的 `aliases` 数组和 Schema 的 `description_en` 字段——两个地方，不需要动 handler 代码。

---

## 4. 安全模型

### 4.1 凭据隔离

| 凭证 | 存储位置 | 注入方式 | Agent 可见 |
|------|---------|---------|-----------|
| Access Token | 环境变量 `TEXT_CLI_TOKEN_LOCAL` | 请求头校验 | 是（请求头传递） |
| SMTP 密码 | 环境变量 `SMTP_PASSWORD` | 服务启动时解析 | **否** |
| SMTP 用户名 | 环境变量 `SMTP_USER` | 服务启动时解析 | **否** |
| Git 远程 URL | 环境变量 `GIT_REMOTE_URL` | 服务启动时解析 | **否** |

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

白名单支持两种匹配模式：
- **前缀匹配**：`/root/.openclaw/workspace/` 匹配该目录下所有子路径
- **精确匹配**：不以 `/` 结尾的路径精确匹配

### 4.3 操作分级

| 操作 | 级别 | 路径检查 | 分支检查 | 第一版 confirm |
|------|------|---------|---------|---------------|
| `文件;读取` | read | 是 | — | 否 |
| `Git;状态` | read | — | — | 否 |
| `文件;写入` | write | 是 | — | 否 |
| `Git;推送` | push | — | 是 | 否 |
| `邮件;发送` | send | — | — | 否 |

**第一版不做 confirm 机制**。理由见 §7.1。

### 4.4 隐含的信任假设

当前安全模型基于一个前提：**辅助服务器和调用方在同一台机器上，且 localhost 网络接口受操作系统保护。** 这个假设在单人部署场景下成立。当辅助服务器支持远程部署时，需要追加传输层加密（TLS）和独立的鉴权体系。

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
      "/root/.openclaw/workspace/",
      "/root/.openclaw/workspace/text-cli/",
      "/root/.openclaw/workspace/tide-scripts/"
    ],
    "operations": {
      "文件;读取": { "level": "read", "aliases": ["file;read"] },
      "Git;状态":   { "level": "read", "aliases": ["git;status"] },
      "文件;写入": { "level": "write", "path_check": true, "aliases": ["file;write"] },
      "Git;推送":   { "level": "push", "allowed_branches": ["feat/*", "fix/*", "main", "master"], "aliases": ["git;push"] },
      "邮件;发送": { "level": "send", "aliases": ["email;send", "mail;send"] }
    }
  },
  "credentials": {
    "Git;推送": {
      "value": "${GIT_TOKEN}",
      "remote_url": null
    },
    "邮件;发送": {
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
    "version": "1.0.0"
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

凭据解析逻辑：

```python
def _resolve_credential(self, cred_value):
    if cred_value is None or cred_value == '':
        return {'mode': 'ssh'}
    if cred_value.startswith('${') and cred_value.endswith('}'):
        resolved = os.environ.get(cred_value[2:-1])
        if resolved is None:
            return {'mode': 'ssh', 'warn': f'env var {cred_value} not set'}
        return {'mode': 'https', 'token': resolved}
    if cred_value.startswith('http://') or cred_value.startswith('https://'):
        return {'mode': 'inject', 'url': cred_value}
    return {'mode': 'https', 'token': cred_value}
```

### 5.3 配置解析规则

- `${VAR_NAME}` 占位符在服务启动时一次性从环境变量中解析
- 环境变量不存在的占位符 → 打印警告，降级到 Mode 3（不中断启动）
- 配置中不存任何真实凭据——它们只在环境变量中

### 5.4 Git 工作目录

`git.workdir`：
- `null`（默认）：使用服务启动时的当前工作目录
- `"/path/to/repo"`：明确指定 Git 仓库路径

---

## 6. 8 条指令详设

首批 5 条（§6.1-6.5）为原方案核心指令。§6.6-6.8 为研发过程中新增的元指令。

### 6.1 `文件;读取`

```
指令:文件;读取,/path/to/file.md
```

**参数**：
1. `path`（必填）：相对于白名单的路径，或绝对路径

**流程**：
1. 校验路径是否在白名单内 → 越界拒绝
2. `Path.read_text(encoding='utf-8')`
3. 返回文件内容

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

---

### 6.2 `文件;写入`

```
指令:文件;写入,/path/to/file.md,<内容>
```

**参数**：
1. `path`（必填）：目标文件路径
2. `content`（必填）：写入内容（贪婪匹配，可含逗号）

**流程**：
1. 校验路径是否在白名单内 → 越界拒绝
2. 自动创建父目录（如果不存在）
3. `Path.write_text(content, encoding='utf-8')`
4. 返回确认

**返回**：
```json
{
  "rst_types": "text",
  "rst_data": {
    "text": "写入成功: /path/to/file.md (1234 字节)"
  }
}
```

---

### 6.3 `Git;状态`

```
指令:Git;状态
```

**参数**：无

**流程**：
1. `subprocess.run(['git', 'status'], cwd=workdir, capture_output=True, text=True)`
2. 返回 stdout

**返回**：
```json
{
  "rst_types": "text",
  "rst_data": {
    "text": "On branch main\nnothing to commit, working tree clean"
  }
}
```

---

### 6.4 `Git;推送`

```
指令:Git;推送,main
```

**参数**：
1. `branch`（必填）：要推送的分支名

**完整执行流**：

```
1. 校验分支名 ∈ allowed_branches（支持通配符 feat/*）
2. _resolve_credential(config.credentials["Git;推送"].value)
3. 分支 A: mode=inject（指令服务器注入）
   → POST 指令服务器 → 获取 git token → git push https://TOKEN@remote branch
   → 失败 → git push remote branch (SSH 降级)
4. 分支 B: mode=https（config/env/明文 token）
   → git push https://TOKEN@remote branch
   → 失败 → git push remote branch (SSH 降级)
5. 分支 C: mode=ssh（无凭据）
   → git push remote branch (SSH)
```

**remote URL 获取**：优先读 `config.credentials["Git;推送"].remote_url`，若为 `null` 则自动从 `git remote get-url origin` 获取。

**HTTPS push 实现**：使用 inline URL（`git push https://TOKEN@github.com/user/repo.git branch`），不修改仓库的 remote 配置。

**返回**：
```json
{
  "rst_types": "text",
  "rst_data": {
    "text": "推送成功: main → origin/main (3 commits) [via HTTPS]",
    "auth_mode": "https"
  }
}
```

`auth_mode` 字段透传实际使用的认证方式（`https` / `ssh`），便于调试。

**第一版实现**：只验证 Mode 2（`${GIT_TOKEN}`）和 Mode 3（SSH）。Mode 1（指令服务器注入）代码预留，验证延后到远程部署场景。

---

### 6.5 `邮件;发送`

```
指令:邮件;发送,limh@10000.world,项目更新,PR #78 已合并，请查阅。
```

**参数**：
1. `to`（必填）：收件人邮箱
2. `subject`（必填）：邮件主题
3. `body`（必填）：邮件正文（贪婪匹配，可含逗号）
4. `attachment`（可选）：附件文件路径

**流程**：
1. 从 `config.credentials` 中读取 SMTP 配置（密码为启动时解析的 env var）
2. 如果提供附件路径 → 校验白名单 → 附加文件
3. `smtplib.SMTP_SSL` 连接 → 登录 → 发送 → 退出
4. 返回发送状态

**返回**：
```json
{
  "rst_types": "text",
  "rst_data": {
    "text": "邮件已发送至 limh@10000.world"
  }
}
```

**注意**：收件人的 SMTP 密码由配置中 `smtp_password` 提供——Agent 在指令中不传递密码。这是和 `port_20260.py` 原型最关键的差异。

---

### 6.6 `系统;健康`

```
指令:系统;健康
```

**参数**：无

**流程**：
1. 计算运行时间（启动时间戳差值）
2. 读取进程 RSS 内存（`resource.getrusage`）
3. 检查 SMTP / Git Token 配置状态
4. 检查 Git 工作目录和远程 URL
5. 格式化报告

**返回**：
```json
{
  "rst_types": "text",
  "rst_data": {
    "text": "text-cli-copilot v1.0.0 运行中\n...",
    "uptime_seconds": 3600,
    "memory_mb": 23.4,
    "handlers": 8,
    "smtp_configured": true,
    "git_token_configured": false
  }
}
```

**定位**：运维视角——配置状态、资源占用、端点信息。供人阅读，也供监控系统程序化消费结构化字段。

---

### 6.7 `系统;状态`

```
指令:系统;状态
```

**参数**：无

**流程**：
1. 读取请求计数器（`_request_count` / `_error_count`）
2. 计算错误率、活跃度（req/h）
3. 根据阈值判断心情和忙碌度
4. 格式化带 emoji 的报告

**心情阈值**：

| 错误率 | 心情 |
|--------|------|
| 0% | 😊 一切顺利 |
| <10% | 🙂 偶有小错 |
| <30% | 😐 有些坎坷 |
| <50% | 😟 不太顺利 |
| ≥50% | 😵 需要帮助 |

**活跃度阈值**：

| 请求/h | 忙碌度 |
|--------|--------|
| >60 | 🔥 忙不过来了 |
| >10 | ⚡ 节奏正好 |
| >1 | 🌊 不紧不慢 |
| ≤1 | 🍃/💤 悠闲/空闲 |

**返回**：
```json
{
  "rst_types": "text",
  "rst_data": {
    "text": "😊 一切顺利  ⚡ 节奏正好\n...",
    "mood": "😊",
    "busy_level": "⚡",
    "total_requests": 42,
    "error_count": 1,
    "error_rate": 0.024,
    "requests_per_hour": 12.5
  }
}
```

**定位**：心情视角——比 `系统;健康` 更轻量、更有"个性"。请求计数和错误率由 HTTP 层和 dispatch 层自动维护，handle 不参与。

---

### 6.8 `AI协作;状态`

```
指令:AI协作;状态      → A 模式（默认，精简）
指令:AI协作;状态,A    → A 模式（显式）
指令:AI协作;状态,B    → B 模式（要点）
```

**参数**：
1. `mode`（可选）：`A` = 精简一行，`B` = 完整报告

**数据来源**：copilot 内存中的 `_ai_status` 字典。不主动拉取——由 AI 协作者在检查点通过 `POST /ai_status` 写入。

**A 模式返回**：
```
Tide 🌊  36% ctx  0 compactions  healthy
```

**B 模式返回**：
```
Tide 🌊  Collaborator Status
─────────────────────────
Model:       deepseek-v4-pro
Context:     73k / 200k (36%)
Compactions: 0
Tokens:      17k in / 29k out
Cache:       81% hit, 73k cached
─────────────────────────
Health:      healthy
```

**健康判断**：

| 条件 | 评级 |
|------|------|
| ctx < 60% AND compactions = 0 | healthy |
| ctx ≥ 60% OR compactions ≥ 1 | warning |
| ctx ≥ 80% OR compactions ≥ 3 | critical |

**定位**：跨进程状态桥——copilot 自己不感知 OpenClaw，由 AI 协作者主动写入。"查看是一种关心"——不设过期标记，返回的是最后一次签到状态。

**写入端点**：

```
POST /ai_status
Authorization: Bearer <token>
Content-Type: application/json

{
  "model": "deepseek-v4-pro",
  "context_used": "73k",
  "context_max": "200k",
  "context_pct": 36,
  "compactions": 0,
  "tokens_in": "17k",
  "tokens_out": "29k",
  "cache_hit": "81%",
  "cache_cached": "73k"
}
```

数据存入内存，覆盖前一条。重启丢失——这符合"签到"语义：重启 = 新 session，旧状态自然失效。

---

## 7. 设计决策

### 7.1 confirm 机制：第一版不做

原型 `port_20260.py` 没有 confirm 机制，运行良好。

**第一版不做的理由**：
1. localhost 服务——调用方和服务器在同一信任域，不需要防自己
2. Agent Skill 模型目前没有内置的 confirm→重发逻辑，引入 confirm 会增加 Agent 侧的复杂度
3. 路径白名单 + 分支白名单已经提供了足够的硬防护

**后续再做的触发条件**：辅助服务器支持远程部署（非 localhost 访问）。

### 7.2 文件过大保护

`文件;读取` 设置 10MB 上限。超过上限返回错误而非截断——截断让 Agent 看到不完整数据，比直接报错更危险。

### 7.3 Git 凭据策略：统一字段 + 全模式 SSH 降级

Git 推送的凭据由 `credentials["Git;推送"].value` 统一管理，字段值格式决定行为：

- **`value = "https://..."`** → Mode 1：向指令服务器请求 token → HTTPS push → 失败降级 SSH
- **`value = "${GIT_TOKEN}"`** → Mode 2：从环境变量读取 → HTTPS push → 失败降级 SSH
- **`value = "ghp_xxxx"`（明文）** → Mode 2：直接用明文 token → HTTPS push → 失败降级 SSH
- **`value = null`** → Mode 3：纯 SSH push

三种模式的终端保障都是 SSH——push 不会因为 token 问题而断路。

和邮件的凭据设计对称：
- `Git;推送` 的 `value` = HTTPS token（env var/明文/注入）
- `邮件;发送` 的 `value` = SMTP 密码（env var）
- 同一个字段名 `value`，同一个解析函数 `_resolve_credential()`，语义由操作定义

**第一版只验证 Mode 2（`${GIT_TOKEN}`）+ Mode 3（SSH）。** Mode 1（指令服务器注入）代码预留。

### 7.4 端口选择：继承 20260

选择 20260 而非 8900——继承自 port_20260 原型，用户已经知道这个端口。且 20260 是一个不常见的端口号（非系统保留、非流行服务默认端口），冲突概率低。

---

## 8. 内部架构

### 8.1 Handler 注册表

新增指令的成本恒定——不需要改路由逻辑。

```python
class Copilot:
    def __init__(self, config_path):
        self.config = self._load_config(config_path)
        self.token = self._resolve_env(self.config['server']['token'])
        self._handlers = {}        # canonical_id → handler
        self._alias_map = {}       # alias → canonical_id
        
        for op_id, op_config in self.config['security']['operations'].items():
            handler_name = '_handle_' + op_id.replace(';', '_').replace(':', '_')
            if hasattr(self, handler_name):
                self._handlers[op_id] = getattr(self, handler_name)
            # 注册 alias → 规范 ID
            for alias in op_config.get('aliases', []):
                self._alias_map[alias] = op_id
            self._alias_map[op_id] = op_id  # 规范 ID 自身也是有效入口
```

**新增一条指令只需两步**：
1. 在 `config.operations` 加一行配置（安全级别、路径检查、凭据绑定、`aliases`）
2. 在 `Copilot` 类加一个 `_handle_xxx_xxx()` 方法

注册由命名约定自动完成，dispatch 通过 `_alias_map` 查规范 ID——英文和中文走同一个 handler。

### 8.2 凭据解析器

`_resolve_credential(value)` 是 `credentials` 配置的唯一入口。所有 handler 通过它获取凭据，不直接读 `os.environ`。返回值统一为 `{'mode': 'https'|'ssh'|'inject', 'token'?: str, 'url'?: str, 'warn'?: str}`。

### 8.3 指令解析器

`_parse_instruction(prompt)` → `{'domain': str, 'action': str, 'params': list}`。最后一个参数贪婪匹配，解决正文含逗号问题。

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
- [x] `文件;读取`：UTF-8，10MB 上限，越界/不存在/编码错误
- [x] `文件;写入`：自动创建父目录，写入确认 + 字节数
- [x] 英文 alias（`file;read` / `file;write`）

### 阶段 3：Git 操作 ✅

- [x] `Git;状态`：`subprocess.run`，30s 超时
- [x] 凭据解析器 `_resolve_credential()`（Mode 1 预留 / Mode 2 env/明文 / Mode 3 SSH）
- [x] `Git;推送`：HTTPS inline URL → 失败降级 SSH
- [x] 分支白名单（`fnmatch` 通配符）
- [x] 远程 URL 自动获取

### 阶段 4：邮件发送 ✅

- [x] SMTP_SSL（mxhichina.com:465）
- [x] MIME 邮件（UTF-8）+ 附件支持
- [x] 真实发送验证通过（含附件）

### 阶段 5：发现端点 ✅

- [x] `GET /text_cli_schema.json`（无需鉴权）
- [x] 8 条指令完整字段（多语言）

### 阶段 6：集成验证 ✅

- [x] 45 条验证零失败（8 指令 × 中英双语 + 错误路径）
- [x] README + 聚合 Schema 注册（`endpoints.json` + `agent-text-cli-schema.json`）

### 研发中新增（超出原方案）

- [x] `系统;健康` — 运维视角状态
- [x] `系统;状态` — 工作心情 + 请求统计
- [x] `AI协作;状态` + `POST /ai_status` — 跨进程 AI 协作者状态桥

### 交付物

```
tide-scripts/text-cli-copilot/
├── text-cli-copilot.py              # 主程序（stdlib only，~700 行）
├── auxiliary_config.json            # 完整配置
├── text-cli-copilot_programme_CN.md # 本文件 v1.3
├── DEVELOPMENT_CHECKLIST.md         # 开发任务清单
├── README.md                        # 快速开始文档
└── old_code/                        # port_20260.py 原型（已退役）
```

---

## 10. 与多源聚合架构的咬合

辅助服务器在聚合 Schema 中的位置：

```
同步 Skill（冷路径）
  ├── 拉取 test.text-cli.com/text_cli_schema.json
  ├── 拉取 cliweather.instantiated.space/text_cli_schema.json
  ├── 拉取 hero-fragments.instantiated.space/text_cli_schema.json
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
  "文件;读取": [
    {"endpoint": "http://localhost:20260/cli/text_cli", "rank": 1}
  ],
  "天气;查询": [
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
| §2 首批 5 条指令 | §6 指令详设 |
| §3 多源聚合咬合 | §10 咬合设计 |
| §4 分工线 | §1.3 架构位置 |
| §5 + §5.3 安全边界与信任假设 | §4 + §7.1 安全模型与设计决策 |
| §6 部署模式 | §9 实现路线（集成模式） |
| §10 + §10.3 万能代理与凭据对称 | §5.2 统一凭据字段、§8.1 注册模式 |
| §11 概念咬合 | §2 架构图体现 Skill+路径+指令三位一体 |
| §12 降级链 | §6.4 Git HTTPS→SSH 降级、§4.1 凭据隔离 |
| §14 触感预演 | §1.4 与 port_20260.py 的对比 |
| §16 前向问题 | §7.1 confirm 推迟、万能代理推迟 |

---

## 12. 已澄清的决策汇总

| # | 决策 | 状态 |
|---|------|------|
| 1 | 主文件名 `text-cli-copilot.py` | ✅ |
| 2 | 端口 20260（继承 port_20260） | ✅ |
| 3 | copilot 是 port_20260 的正式替代 | ✅ |
| 4 | 统一凭据字段 `credentials.<op>.value`，值格式决定行为 | ✅ |
| 5 | Git 全模式 → SSH 降级（Mode 1/2 HTTPS 失败后自动切 SSH） | ✅ |
| 6 | 第一版验证 Mode 2（env）+ Mode 3（SSH），Mode 1 代码预留 | ✅ |
| 7 | confirm 推迟—localhost 信任域不需要 | ✅ |
| 8 | 万能代理推迟——首批 5 条核心指令 | ✅ |
| 9 | Handler 注册表模式——新增指令两步完成，dispatch 不需改 | ✅ |
| 10 | SMTP 默认对齐 port_20260（mxhichina.com:465） | ✅ |
| 11 | Git workdir = 启动时 cwd（`null`），可通过 config 覆盖 | ✅ |
| 12 | HTTPS push 用 inline URL，不修改仓库 remote 配置 | ✅ |
| 13 | 多语言：`指令:` + `directive:` 双前缀，aliases 映射，`description_en` | ✅ |
| 14 | 元指令走同一套注册/解析/Dispatch 管道，不在外面开特殊路径 | ✅ |
| 15 | AI 状态用主动写入模式（检查点 POST /ai_status），非轮询 | ✅ |
| 16 | `AI协作;状态` 不设过期标记——"查看是一种关心" | ✅ |
| 17 | 所有返回内容英文化（A/B 模式均英文输出） | ✅ |

---

*本文档由 Tide 🌊 基于 lemondy 的统一架构、port_20260.py 原型分析、2026-05-07 思维路标文档、以及 lemondy + Tide 八轮澄清综合撰写。v1.1 当晚更新配置+Git凭据+内部架构。v1.2 加入多语言支持（§3.4）。v1.3 更新为已实现状态，新增 3 条元指令（§6.6-6.8）和 AI 状态端点，17 项决策全部定稿。*
