# text-cli 标准指令包开发指南

> **版本**：v1.0 | **基于 SPEC**：v1.3.2 | **日期**：2026-07-22
> **本文档教你如何开发和发布 text-cli 标准指令包。**

> 💡 如果你的能力来源是 Postman Collection 或 MCP server，可以先用 `converter/` 下的脚本生成脚手架，再参考本指南完成开发。

---

## 一、标准指令包分类

### 1.1 按部署目标分类

标准 text-cli 有两个独立的运行时，指令包发布时需要明确目标：

| 运行时 | 监听地址 | 安装指令 | 定位 |
|------|------|------|------|
| **service** | `0.0.0.0:28050` | `text-cli;install,<包名>` | 平台服务——可供网络内多个调用方访问 |
| **copilot** | `127.0.0.1:20260` | `text-cli;co-install,<包名>` | 本地代理——锁在本机，暴露操作系统能力（文件/终端/Git） |

> 同一个包不能同时安装到两个运行时。开发前先确定目标运行时。
> copilot 特有的开发细节见[附录 A](#附录-a-copilot-运行时)。

### 1.2 按能力形态分类

| 形态 | 能力来源 | 示例场景 | 核心特点 |
|------|------|------|------|
| **工具函数** | 本地 Python 函数 | JSON 处理、日期计算、数学运算 | 纯计算/处理，零外部依赖 |
| **在线 API** | 云服务商 API | 天气查询、地图地理编码、AI 推理 | 需要 API key 和网络访问 |
| **容器 API** | 自托管服务 API | 家庭 NAS 管理、Docker 服务操作 | 需要 Docker 环境和自托管服务 |
| **文档型** | 人的经验笔记 | 盆栽病害诊断、配置速查 | 零代码——Markdown 即指令 |

### 1.3 按 runtime 分类

每种形态通过 `schema.json` 中的 `runtime` 字段声明执行方式：

| runtime | 形态 | 实现方式 |
|------|------|------|
| `python` | 工具函数 / 在线 API / 容器 API | handler.py + `@directive` 装饰器 |
| `node` | 工具函数 / 在线 API | `<entry>.js` + Node.js |
| `path` | 文档型 | 纯 JSON 声明，无代码文件 |
| `aggregate` | 降级路由 | 纯 JSON 声明，收敛多个提供方 |
| `mcp` | MCP 桥接 | MCP 协议映射 |
| `cmd` | 命令行包装 | shell 命令 + whitelist.json |

> 本文档 §2 以 **python / 工具函数 / service 目标** 为主线走完全程。其他形态见 §3。

---

## 二、工具函数包：从零到一

> 以"日期计算器"为例——输入日期和天数，输出偏移后的新日期。
> 目标运行时：service。

### 2.1 目录结构

```
date-calc/
├── schema.json    ← 对外声明：我是谁、能做什么
└── handler.py     ← 内部实现：实际执行的代码
```

### 2.2 schema.json

```json
{
  "id": "date-calc",
  "type": "native",
  "name": "Date Calculator",
  "name_zh": "日期计算器",
  "runtime": "python",
  "version": "1.0.0",
  "category": "数据处理",
  "locales": ["zh", "en"],
  "trust": "community",
  "description": "Date offset calculation utilities.",
  "description_zh": "日期偏移计算工具。",
  "directives": [
    {
      "domain": "date-calc",
      "domain_zh": "日期计算",
      "action": "add",
      "action_zh": "加天数",
      "usage": "date-calc;add,<日期>,<天数>",
      "usage_zh": "日期计算;加天数,<日期>,<天数>",
      "description": "Add N days to a date. Returns the result date string.",
      "description_zh": "给指定日期加上 N 天，返回结果日期",
      "params": ["date", "days"],
      "params_desc": {
        "date": "Date in YYYY-MM-DD format",
        "days": "Number of days to add (can be negative)"
      },
      "outputs": ["result"]
    }
  ]
}
```

### 2.3 handler.py

```python
from datetime import datetime, timedelta

def handler_add(date_str, days_str):
    """日期偏移：date-calc;add,<日期>,<天数>"""
    try:
        days = int(days_str)
        dt = datetime.strptime(date_str.strip(), "%Y-%m-%d")
        result = dt + timedelta(days=days)
        return {
            "status": "ok",
            "result": result.strftime("%Y-%m-%d"),
            "detail": f"{date_str} + {days}天 = {result.strftime('%Y-%m-%d')}"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"日期计算失败: {str(e)}"
        }

# ── 注册为 text-cli 指令 ──

from core.registry import directive

@directive("date-calc;add,<日期>,<天数>")
def add(date_str, days_str):
    return handler_add(date_str, days_str)
```

### 2.4 handler.py 关键约定

| 约定 | 说明 |
|------|------|
| `@directive` 签名与 `usage` 一致 | `"date-calc;add,<日期>,<天数>"` 必须与 schema.json 中 `usage` 字符串完全相同 |
| 返回信封 | `{"status": "ok", ...}` 或 `{"status": "error", "message": "..."}` |
| 业务数据不嵌套 | 不要 `{"data": {"data": ...}}`，展开在 `status` 同级 |
| 错误消息用中文 | 调用方（含用户）能看到，方便排查 |
| 不存密钥 | 密钥走框架的 key registry，不硬编码在 handler 中 |

### 2.5 安装与验证（service 运行时）

```bash
# 1. 启动 service 运行时

# 2. 安装包
curl -X POST http://localhost:28050/text-cli/cli \
  -H "Content-Type: application/json" \
  -d '{"prompt": "AI:text-cli;install,date-calc"}'

# 3. 验证指令
curl -X POST http://localhost:28050/text-cli/cli \
  -H "Content-Type: application/json" \
  -d '{"prompt": "AI:date-calc;add,2026-01-01,30"}'

# 期望响应
# {"rst_types":"text","rst_data":{"text":"{"status":"ok","result":"2026-01-31",...}"},"rst_err":""}
```

### 2.6 字段速查

完整字段定义见 [SPEC §4](../../../docs/SPEC_zh.md)。以下为快速参考：

**包级必填**：`id` / `type` / `name` / `name_zh` / `runtime` / `version` / `category` / `locales` / `trust` / `description`

**指令级必填**：`domain` / `action` / `usage` / `description` / `description_zh`

**推荐填写**：`domain_zh` / `action_zh` / `usage_zh`（支持中文 Agent 意图匹配）

**可选**：`params` / `params_desc` / `outputs` / `estimated_time` / `estimated_time_note` / `requires` / `credentials`

### 2.7 常见问题

**Q: 我的函数需要额外的 Python 库怎么办？**

在 schema.json 中声明 `requires.pip`：

```json
"requires": {
  "pip": ["Pillow>=10.0"]
}
```

安装时 text-cli 会自动执行 `pip install`。

**Q: `@directive` 签名和 `usage` 不一致会怎样？**

安装成功但运行时报错。框架按 `usage` 字符串解析参数顺序传给 handler，不一致会导致参数错位。

**Q: 中文域和动作名是怎么起作用的？**

用户发 `AI:日期计算;加天数,2026-01-01,30` 时，框架通过 `domain_zh`/`action_zh` 匹配到 `date-calc;add`，然后路由到正确的 handler。

**Q: 如何让 AI Agent 发现我的包？**

安装后 AI 调 `AI:text-cli;query` 获取全量指令清单（含 `domain_zh`/`action_zh` 中文别名）。不需要额外注册。

**Q: 一个包可以有多个指令吗？**

可以。在 `directives` 数组中加多条即可，每条对应 handler.py 中一个 `@directive` 注册。

---

## 三、其他形态介绍

### 3.1 在线 API 包

在线 API 包将云服务商的 API 封装为 text-cli 指令。与工具函数包相比，核心差异是**需要 API 凭据和网络访问**。

以"腾讯云翻译"为例——用户发 `AI:tx-cloud;translation,Hello,zh`，背后调腾讯云 TMT API。

**schema.json 特有字段**：

```json
{
  "requires": {
    "pip": ["tencentcloud-sdk-python"]
  },
  "credentials": [
    {
      "name": "tencent_cloud_secret_id",
      "description_en": "Tencent Cloud SecretId",
      "description_zh": "腾讯云 SecretId",
      "storage": "key_registry",
      "register_cmd": "AI:key;register,tx,<secret_id>,access_key_secret=<secret_key>,api_key"
    }
  ]
}
```

**关键差异**：

| 维度 | 工具函数包 | 在线 API 包 |
|------|------|------|
| `requires.pip` | 无或标准库 | SDK 依赖（如 `tencentcloud-sdk-python`） |
| `credentials` | 无 | 必须声明——`storage` 指定存储位置 + `register_cmd` 告诉用户如何注册 |
| handler.py 逻辑 | 本地计算 | HTTP 客户端 + SDK 鉴权 |
| 安装后额外步骤 | 无 | 用户需先执行 `AI:key;register,...` 注册凭据 |

**handler.py 核心模式**：

```python
from core.registry import directive

def _get_client():
    """懒加载 SDK 客户端（读取框架注入的凭据）"""
    import json, os
    from tencentcloud.common import credential
    from tencentcloud.tmt.v20180321 import tmt_client, models

    # 凭据由框架从 key_registry 注入到环境变量
    cred = credential.Credential(
        os.environ["TENCENT_CLOUD_SECRET_ID"],
        os.environ["TENCENT_CLOUD_SECRET_KEY"]
    )
    return tmt_client.TmtClient(cred, "ap-guangzhou")

@directive("tx-cloud;translation,<text>[,<target>]")
def translation(text, target="en"):
    client = _get_client()
    req = models.TextTranslateRequest()
    req.SourceText = text
    req.Target = target
    req.ProjectId = 0
    resp = client.TextTranslate(req)
    return {
        "status": "ok",
        "result": resp.TargetText,
        "source": resp.Source,
        "target": resp.Target
    }
```

**安装后用户操作**：

```bash
# 1. 注册 API 凭据（仅一次）
curl -X POST http://localhost:28050/text-cli/cli \
  -H "Content-Type: application/json" \
  -d '{"prompt": "AI:key;register,tx,<your_secret_id>,access_key_secret=<your_secret_key>,api_key"}'

# 2. 安装包
curl -X POST http://localhost:28050/text-cli/cli \
  -H "Content-Type: application/json" \
  -d '{"prompt": "AI:text-cli;install,tx-cloud"}'

# 3. 调用
curl -X POST http://localhost:28050/text-cli/cli \
  -H "Content-Type: application/json" \
  -d '{"prompt": "AI:tx-cloud;translation,Hello,zh"}'
```

### 3.2 容器 API 包

容器 API 包将自托管服务的 REST API 封装为 text-cli 指令。服务运行在本地 Docker 容器中，handler.py 作为 HTTP 客户端调用它。

以"Jellyfin 媒体服务器"为例——用户通过 text-cli 浏览家庭媒体库。

**目录结构**：

```
jellyfin/
├── schema.json
├── handler.py
└── config/
    └── jellyfin.json      ← 服务地址配置
```

**config/jellyfin.json**：

```json
{
  "url": "http://localhost:8096",
  "api_key": "your_jellyfin_api_key"
}
```

**schema.json 特有字段**：

```json
{
  "requires": {
    "pip": ["requests"]
  }
}
```

**关键差异**：

| 维度 | 在线 API 包 | 容器 API 包 |
|------|------|------|
| 服务位置 | 公网云服务 | 本地 `localhost` 或内网地址 |
| `credentials` | 需要（云服务商凭据） | 不需要（服务为本地认证） |
| `config/` 目录 | 通常不需要 | 必须有——存放服务地址和本地认证信息 |
| 前置条件 | 注册 API key | 启动 Docker 容器 |

**handler.py 核心模式**：

```python
import json, requests
from core.registry import directive

def _load_config():
    """读取服务地址配置"""
    with open("config/jellyfin.json") as f:
        return json.load(f)

def _api(path):
    """调用 Jellyfin REST API"""
    config = _load_config()
    headers = {"X-Emby-Token": config["api_key"]}
    resp = requests.get(f"{config['url']}{path}", headers=headers)
    return resp.json()

@directive("jellyfin;library")
def library():
    """列出所有媒体库"""
    data = _api("/Library/VirtualFolders")
    libraries = [{"name": lib["Name"], "type": lib["CollectionType"]}
                 for lib in data]
    return {"status": "ok", "libraries": libraries, "count": len(libraries)}
```

**安装后用户操作**：

```bash
# 1. 启动自托管服务（如 Jellyfin Docker 容器）
docker run -d --name jellyfin -p 8096:8096 jellyfin/jellyfin

# 2. 配置服务地址
# 编辑 config/jellyfin.json，填入正确的 url 和 api_key

# 3. 安装包
curl -X POST http://localhost:28050/text-cli/cli \
  -H "Content-Type: application/json" \
  -d '{"prompt": "AI:text-cli;install,jellyfin"}'
```

### 3.3 MCP 桥接包

> 零 Python 代码——将已注册的 MCP server 的 tool 映射为 text-cli 指令。

**核心思路**：你已经在 mcporter 中配好了一个 MCP server（如 GitHub），现在只需要写两个 JSON 文件，告诉 text-cli "这个 domain 下的 action 对应 mcporter 的哪个 server 的哪个 tool"。

**目录结构**：

```
my-package/
├── schema.json                 ← 指令声明 + runtime:"mcp"
└── service-descriptor.json     ← mcporter 路由映射
```

> MCP 包不需要 handler.py——调用链是 text-cli 指令 → mcp_dispatch → mcporter → MCP server，text-cli 不执行任何用户代码。

**schema.json**：

```json
{
    "id": "tcco-mcp-github",
    "name_zh": "GitHub MCP 桥",
    "runtime": "mcp",
    "type": "native",
    "locales": ["zh", "en"],
    "trust": "community",
    "category": "开发工具",
    "directives": [
        {
            "domain": "comcp-github",
            "domain_zh": "GitHub",
            "action": "search_repos",
            "action_zh": "搜索仓库",
            "usage": "comcp-github;search_repos,<query>,<page>,<perPage>",
            "usage_zh": "GitHub;搜索仓库,<关键词>,<页码>,<每页数量>",
            "description": "Search GitHub repositories by keyword",
            "description_zh": "按关键词搜索 GitHub 仓库",
            "params": ["query", "page", "perPage"],
            "params_desc": {
                "query": "搜索关键词",
                "page": "页码（默认 1）",
                "perPage": "每��数量（默认 30）"
            },
            "mcp_tool": "search_repositories"
        },
        {
            "domain": "comcp-github",
            "domain_zh": "GitHub",
            "action": "get_file",
            "action_zh": "获取文件",
            "usage": "comcp-github;get_file,<owner>,<repo>,<path>,<branch>",
            "usage_zh": "GitHub;获取文件,<所有者>,<仓库>,<路径>,<分支>",
            "description": "Get file contents from a repository",
            "description_zh": "获取仓库文件内容",
            "params": ["owner", "repo", "path", "branch"],
            "params_desc": {
                "owner": "仓库所有者",
                "repo": "仓库名",
                "path": "文件路径",
                "branch": "分支名（默认 main）"
            },
            "mcp_tool": "get_file_contents"
        }
    ]
}
```

**service-descriptor.json**：

```json
{
    "mcp_server": "github",
    "tools": [
        {
            "name": "search_repos",
            "tool": "search_repositories"
        },
        {
            "name": "get_file",
            "tool": "get_file_contents"
        }
    ]
}
```

| 字段 | 说明 |
|------|------|
| `mcp_server` | mcporter 中配置的 server 名称（安装前必须先配好） |
| `tools[].name` | 对应 schema.json 中的 `action` 字段 |
| `tools[].tool` | mcporter 中该 server 的实际 tool 名称 |

**前置条件**：

安装 MCP 包之前，必须先在 mcporter 中配置好对应的 server 连接。安装器会调用 `mcporter list <server_name>` 验证——如果 server 未配置，安装会失败并提示。

```bash
# 先配置 mcporter server
mcporter add github --transport streamable-http --url https://api.github.com/mcp
```

**安装与验证**：

```bash
# 安装包（仅 service 运行时，不可安装到 copilot）
curl -X POST http://localhost:28050/text-cli/cli \
  -H "Service-token: <token>" \
  -d '{"prompt":"AI:text-cli;install,tcco-mcp-github"}'

# 安装后路由表即时刷新，无需重启

# 调用
curl -X POST http://localhost:28050/text-cli/cli \
  -H "Service-token: <token>" \
  -d '{"prompt":"AI:comcp-github;search_repos,text-cli"}'
```

**降级链自动参与**：MCP 指令安装后自动出现在 mcp_dispatch 路由表中。如果 mcporter 不可达，degrade 信号会让降级链继续走到下一级（proxy / federation mesh），不会终端报错。

**卸载**：

```bash
curl -X POST http://localhost:28050/text-cli/cli \
  -H "Service-token: <token>" \
  -d '{"prompt":"AI:text-cli;uninstall,tcco-mcp-github"}'
```

> 卸载仅移除路由表条目和 schema 文件，不会删除 mcporter 中的 server 配置。

### 3.4 文档型包

> 零代码——把领域经验写成 Markdown，用路径引擎编排。详见 [package-nocode-guide_zh.md](package-nocode-guide_zh.md)。

---

## 附录 A：copilot 运行时

copilot 是 text-cli 的本地运行时（`127.0.0.1:20260`），专门暴露本机操作系统能力——截屏、音频、终端命令、文件操作。与 service 不同，copilot 不能（也不应该）被网络中的其他机器访问。

### A.1 什么时候用 copilot 而不是 service

| 场景 | 用哪个 |
|------|:---:|
| JSON 处理、数学计算、Markdown 转换 | service |
| 调用云服务 API（翻译、地图、语音识别） | service |
| 截屏、拍照、音量控制 | **copilot** |
| 执行本地终端命令 | **copilot** |
| 读写本机文件 | **copilot** |
| 操作 Git 仓库 | **copilot** |

> **判断标准**：如果指令的执行需要直接操控本机硬件、文件系统或终端——用 copilot。`127.0.0.1` 的锁是安全机制，不是限制。

### A.2 安全模型：白名单闸门

copilot 包的每条指令可能执行 shell 命令——这对安全性提出了更高要求。text-cli 通过 **白名单闸门** 保证安全：

- 每条被允许执行的命令需要显式登记在 `whitelist.json` 中
- 命令的固定参数（`args`）和可变参数（`args_pattern`）均需声明
- 每条命令有独立的超时时间（`timeout`）
- 未登记的命令——拒绝执行

**whitelist.json 结构**：

```json
{
  "tool": "tc-ubuntu",
  "commands": [
    {
      "action": "screenshot",
      "action_zh": "截屏",
      "args": ["gnome-screenshot", "-f"],
      "args_pattern": "^.+screenshot_\\d+_\\d+\\.png$",
      "timeout": 10,
      "description": "Full-screen screenshot"
    },
    {
      "action": "volume-set",
      "action_zh": "音量设置",
      "args": ["pactl", "set-sink-volume", "@DEFAULT_SINK@"],
      "args_pattern": "^\\d{1,2}%$",
      "timeout": 5
    }
  ]
}
```

**字段说明**：

| 字段 | 说明 |
|------|------|
| `action` | 对应 schema.json 中的 `action` 字段 |
| `args` | 允许执行的固定命令和参数（如 `["gnome-screenshot", "-f"]`） |
| `args_pattern` | 正则表达式——校验传给命令的可变参数（如文件路径只允许 `.png` 后缀） |
| `timeout` | 超时秒数——防止命令挂死 |

### A.3 完整示例：tc-ubuntu（桌面硬件控制）

以"屏幕截图"指令为例，展示 copilot 包的三文件结构。

**目录结构**：

```
tc-ubuntu/
├── schema.json
├── handler.py
└── tc_ubuntu_whitelist.json    ← 白名单（copilot 包独有）
```

**schema.json 特有字段**：

```json
{
  "runtime": "python",
  "requires": {
    "modules": ["whitelist_loader"]
  },
  "directives": [
    {
      "domain": "tc-ubuntu",
      "domain_zh": "tc-ubuntu",
      "action": "screenshot",
      "action_zh": "截屏",
      "usage": "tc-ubuntu;screenshot",
      "usage_zh": "tc-ubuntu;截屏",
      "outputs": ["path"]
    }
  ]
}
```

**handler.py 核心模式**：

```python
import subprocess
from core import error, ok

# 懒加载白名单索引
_whitelist_index = None

def _get_index():
    global _whitelist_index
    if _whitelist_index is None:
        from whitelist_loader import WhitelistIndex
        _whitelist_index = WhitelistIndex(WHITELIST_DIR)
    return _whitelist_index

# 所有指令执行前通过白名单校验
def _exec_whitelist(action, extra_args=None):
    index = _get_index()
    entry = index.lookup("tc-ubuntu", action)
    if not entry:
        return error(f"action not in whitelist: {action}")

    cmd = entry["args"].copy()
    if extra_args:
        # 校验可变参数符合 args_pattern
        import re
        arg_str = " ".join(str(a) for a in extra_args)
        if not re.match(entry["args_pattern"], arg_str):
            return error(f"args rejected: {arg_str}")

        cmd.extend([str(a) for a in extra_args])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True,
                                timeout=entry["timeout"])
        return ok(result.stdout.strip()) if result.returncode == 0 \
          else error(result.stderr.strip())
    except subprocess.TimeoutExpired:
        return error(f"timeout after {entry['timeout']}s")
```

**关键差异总结**：

| 维度 | service 包 | copilot 包 |
|------|------|------|
| `requires.modules` | 无 | `["whitelist_loader"]` — 必须 |
| 额外文件 | — | `whitelist.json` — 必须 |
| 执行方式 | Python 函数 | `subprocess.run()` — 白名单校验后 |
| 安全约束 | 凭据隔离 | 白名单 + regex + timeout |
| 防御性设计 | 无特殊要求 | 音量上限 50%、录音最长 30 秒 |

### A.4 安装与验证（copilot 运行时）

```bash
# 1. 启动 copilot 运行时

# 2. 安装包（注意：co-install）
curl -X POST http://localhost:20260/text-cli/cli \
  -H "Content-Type: application/json" \
  -d '{"prompt": "AI:text-cli;co-install,tc-ubuntu"}'

# 3. 验证
curl -X POST http://localhost:20260/text-cli/cli \
  -H "Content-Type: application/json" \
  -d '{"prompt": "AI:tc-ubuntu;screenshot"}'

# 4. 卸载
curl -X POST http://localhost:20260/text-cli/cli \
  -H "Content-Type: application/json" \
  -d '{"prompt": "AI:text-cli;co-uninstall,tc-ubuntu"}'
```

### A.5 安全红线

| 红线 | 说明 |
|------|------|
| **不在 service 运行时注册系统指令** | service 监听 `0.0.0.0`——任何人可调。系统操控能力只能在 copilot (`127.0.0.1`) 中暴露 |
| **白名单最小化** | 只声明指令需要的命令和参数。不要放通配命令（如 `["bash", "-c"]` 不加 regex 限制） |
| **超时必须设** | 每条白名单条目必须设 `timeout`。没有超时的子进程是潜在的资源泄漏 |
| **参数校验必须严格** | `args_pattern` 用正则限制文件路径、数值范围——tc-ubuntu 的音量用 `^\d{1,2}%$` 保证不超过 99% |

---

_文档版本：v1.0｜2026-07-22｜全文结构完整：分类 + 工具主线 + 三种形态 + copilot 附录_
