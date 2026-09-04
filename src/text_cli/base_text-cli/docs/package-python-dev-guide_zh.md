# Python 标准运行时 — 指令包开发指南

> 本文档是 Python 标准运行时（service 和 copilot）指令包的完整开发指南。
> schema.json 字段规范见 [package-publish-guide_zh.md](package-publish-guide_zh.md)。
> nocode 文档型指令包见 [package-nocode-guide_zh.md](package-nocode-guide_zh.md)。

---

## 一、指令包分类

### 1.1 按部署目标分类

service 与 copilot 是同一 Python 标准运行时的两个组件形态，指令包发布时需要明确目标组件：

| 组件 | 监听地址 | 安装指令 | 定位 |
|------|------|------|------|
| **service** | `0.0.0.0:28050` | `text-cli;install,<包名>` | 平台服务——可供网络内多个调用方访问 |
| **copilot** | `127.0.0.1:20260` | `text-cli;co-install,<包名>` | 本地代理——锁在本机，暴露操作系统能力 |

> 同一个包不会同时安装到两个组件。开发前先确定目标组件。copilot 特有的开发细节见 §六。

### 1.2 按能力形态分类

| 形态 | 能力来源 | 本文档覆盖 | 说明 |
|------|------|:--:|------|
| **工具函数** | 本地 Python 函数 | §二 | 纯计算/处理，零外部依赖 |
| **在线 API** | 云服务商 API | §三 | 需要 API key 和网络访问 |
| **容器 API** | 自托管服务 API | §四 | 需要 Docker 环境和自托管服务 |
| **MCP 桥接** | MCP server 的 tool | §五 | 零 Python 代码——将已注册的 MCP tool 映射为指令 |
| **文档型** | 人的经验笔记 | 见 [package-nocode-guide_zh.md](package-nocode-guide_zh.md) | 零代码——Markdown 即指令 |

> 本文档 §二 以 **工具函数 / service 目标** 为主线走完全流程。其他形态见对应章节。

---

## 二、工具函数包：从零到一

> 以"日期计算器"为例——输入日期和天数，输出偏移后的新日期。目标运行时：service。

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
      "usage": "date-calc;add,<date>,<days>",
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
from core.registry import directive

@directive("date-calc", "add", domain_alias="日期计算", action_aliases={"add": "加天数"})
def add(params: list[str]) -> dict:
    """date-calc;add,<date>,<days>"""
    try:
        date_str = params[0].strip()
        days = int(params[1])
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        result = dt + timedelta(days=days)
        return {
            "status": "ok",
            "result": result.strftime("%Y-%m-%d"),
            "detail": f"{date_str} + {days}d = {result.strftime('%Y-%m-%d')}"
        }
    except Exception as e:
        return {
            "status": "error",
            "reason": f"date calculation failed: {str(e)}"
        }
```

### 2.4 handler.py 关键约定

| 约定 | 说明 |
|------|------|
| `@directive(domain, action, ...)` 分参注册 | 第一、二参数为规范 `domain` / `action`（与 schema.json 一致）；中文路由通过 `domain_alias` / `action_aliases` 关键字参数声明，运行时别名归一化后路由（双向、大小写不敏感） |
| `usage` 仅供发现 | `usage` 是纯文档字段，供 AI/用户发现指令用；**不参与路由、不参与参数解析** |
| handler 统一入参 | `def <action>(params: list[str])`——运行时按顶层逗号把参数拆成列表传入；handler 自己按位取值（`params[0]`…）、自己给默认值 |
| 返回类型是 `dict` | handler 必须返回 **dict**——运行时将其直接放入响应信封的 `rst_data` 中 |
| 返回信封约定 | 成功 `{"status": "ok", ...}`；失败 `{"status": "error", "reason": "..."}`。错误字段名统一为 **`reason`** |
| 媒体响应 | 对于图片、视频、音频、文件等媒体响应，在返回 dict 中加入 `"pray_rst_types": "picture"` / `"video"` / `"audio"` / `"file"`，运行时据此设置 `rst_types` |
| 业务数据不嵌套 | 不要 `{"data": {"data": ...}}`，展开在 `status` 同级 |
| `init_<name>_handler()` 初始化钩子（可选） | 包可定义模块级初始化函数，运行时装载包时调用并注入运行环境（如 `db_path` / `project_root`） |
| 错误消息本地化 | 错误文案与正常输出一样进包内 i18n 表、按 `lang` 返回（默认语言 `zh`）；不要硬编码单一语言 |
| 不存密钥 | 密钥走框架的 key registry，不硬编码在 handler 中 |
| `runtime_config(action, payload)` 配置钩子（可选，运行时特性） | 包可定义模块级配置热更新钩子，配合运行时 `text-cli;config` 元指令实现免重启 get/post 包配置（见 §2.4.1） |

### 2.4.1 可选钩子：runtime_config（配置热更新 · 运行时特性）

> 说明：本钩子是**运行时特性**，暂未纳入 SPEC 协议规范；运行时稳定运行一段时间后另行评估是否升级为协议。

运行时提供平台自管理元指令 `AI:text-cli;config,<token>,<get|post>,<pkg>[,<json>]`（默认关闭，需在 `text_cli.yaml` 的 `live_config` 段开启并设置独立 token）。包若希望支持配置热更新（免重启 / 免 `--force` 重装），在 handler.py 定义模块级固定签名函数：

```python
def runtime_config(action: str, payload: dict | None) -> dict | None:
    ...
```

契约要点：

| 项 | 约定 |
|----|------|
| 固定签名 | `runtime_config(action: str, payload: dict \| None) -> dict \| None`；模块级函数（非 `init_` 命名推断，运行时探测只需一次 `getattr`） |
| `action` | `"get"` 读当前配置；`"post"` 应用新配置 |
| `payload` | `get` 时为 `None`；`post` 时为调用方传入的 JSON 对象 |
| 返回 `None` | = 不支持（该 action 或整体），运行时回 `does not support live-config` |
| 回显外壳 | `get` / `post` 同构返回 `{"status": "ok", "config": <配置>}`；`post` 为**写后读回显**（应用后配置），调用方可在同一步结果确认生效 |
| `config` 键 | 回显规范键；包自行脱敏（如密钥类字段）。个别无法回显的包允许省略（契约明示降级，调用方自行确认） |
| 错误 | 走 `{"status": "error", "reason": "..."}`（§2.4 信封惯例），不得把错误塞进业务字段 |
| post 语义 | 包自定全量替换或 merge、自行校验与落盘；`post` 直接更新模块态（承担"重载"），不必回调 `init_*` |
| 模块态更新 | `post` 更新模块级变量时**必须 `global` 声明**——Python 函数内赋值即局部变量，缺声明则整个函数（含 get 分支）抛 `UnboundLocalError` |
| 路径类配置 | 配置含路径时，**落盘校验与消费检查须同基解析**——明确相对路径的解析基准（相对哪个目录）并两侧一致，避免"post 成功、消费失效" |
| 前置约定 | 包的 `init_*_handler()` 应可重复调用且幂等（框架可能在配置重载后重新 init） |
| 探测标记 | install 时运行时探测一次钩子是否存在，并在 manifest 标记 `live_config: true/false` |

### 2.5 多语言

`locales` 声明包支持的输出语言（ISO 639-1，中文 `zh`）。`schema.json` 中 canonical 字段为英文 / 中立；以 `_zh` 为本地化覆盖示例：

- 包级：`name` / `description` 为 canonical，`name_zh` / `description_zh` 提供中文覆盖
- 指令级：`domain` / `action` / `usage` / `description` 为 canonical，`domain_zh` / `action_zh` / `usage_zh` / `description_zh` 提供中文覆盖

`_zh` 字段缺失时回退 canonical。指令可通过末位 `lang` 位置参数显式指定输出语言，越界时优雅降级到默认语言。

### 2.6 安装与验证（service 运行时）

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
# {"rst_types":"text","rst_data":{"status":"ok","result":"2026-01-31","detail":"2026-01-01 + 30d = 2026-01-31"},"rst_err":""}
```

### 2.7 字段速查

**包级必填**：`id` / `type` / `name` / `runtime` / `version` / `category` / `locales` / `trust` / `description`

**包级推荐**：`name_zh` / `description_zh`

**指令级必填**：`domain` / `action` / `usage` / `description`

**指令级推荐**：`domain_zh` / `action_zh` / `usage_zh` / `description_zh`

**可选**：`params` / `params_desc` / `outputs` / `estimated_time` / `estimated_time_note` / `requires` / `credentials`

### 2.8 常见问题

**Q: 我的函数需要额外的 Python 库怎么办？**

在 schema.json 中声明 `requires.pip`：

```json
"requires": {
  "pip": ["Pillow>=10.0"]
}
```

安装时 text-cli 会自动执行 `pip install`。

**Q: `@directive` 注册和 `usage` 不一致会怎样？**

路由不受影响——`usage` 是纯文档字段，不参与路由和参数解析。路由只看 `@directive(domain, action, ...)` 的注册与别名；参数由运行时按顶层逗号拆成 `list[str]` 传入 handler。但 `usage` 与实际实现漂移会误导 AI/用户发现和调用，应保持二者同步。

**Q: 中文域和动作名是怎么起作用的？**

用户发 `AI:日期计算;加天数,2026-01-01,30` 时，运行时通过 `@directive` 注册的 `domain_alias` / `action_aliases` 归一化到 `date-calc;add`，然后路由到 handler。别名匹配双向且大小写不敏感。schema.json 的 `domain_zh`/`action_zh` 是声明面（供发现与意图匹配展示），与装饰器别名应保持一致。

**Q: 如何让 AI Agent 发现我的包？**

安装后 AI 调 `AI:text-cli;query` 获取全量指令清单（含 `domain_zh`/`action_zh` 中文别名）。不需要额外注册。

**Q: 一个包可以有多个指令吗？**

可以。在 `directives` 数组中加多条即可，每条对应 handler.py 中一个 `@directive` 注册。

---

## 三、在线 API 包

在线 API 包将云服务商的 API 封装为 text-cli 指令。与工具函数包相比，核心差异是**需要 API 凭据和网络访问**。

以"腾讯云翻译"为例——用户发 `AI:tx-cloud;translation,Hello,zh`，背后调腾讯云 TMT API。

### 3.1 schema.json 特有字段

```json
{
  "requires": {
    "pip": ["tencentcloud-sdk-python"]
  },
  "credentials": [
    {
      "name": "tencent_cloud_secret_id",
      "description": "Tencent Cloud SecretId",
      "description_zh": "腾讯云 SecretId",
      "storage": "key_registry",
      "register_cmd": "AI:key;register,tx,<secret_id>,access_key_secret=<secret_key>,api_key"
    }
  ]
}
```

### 3.2 关键差异

| 维度 | 工具函数包 | 在线 API 包 |
|------|------|------|
| `requires.pip` | 无或标准库 | SDK 依赖（如 `tencentcloud-sdk-python`） |
| `credentials` | 无 | 必须声明——`storage` 指定存储位置 + `register_cmd` 告诉用户如何注册 |
| handler.py 逻辑 | 本地计算 | HTTP 客户端 + SDK 鉴权 |
| 安装后额外步骤 | 无 | 用户需先执行 `AI:key;register,...` 注册凭据 |

### 3.3 handler.py 核心模式

```python
from core.registry import directive

def _get_client():
    """懒加载 SDK 客户端（按需读取凭据）"""
    import os
    from tencentcloud.common import credential
    from tencentcloud.tmt.v20180321 import tmt_client, models

    cred = credential.Credential(
        os.environ["TENCENT_CLOUD_SECRET_ID"],
        os.environ["TENCENT_CLOUD_SECRET_KEY"]
    )
    return tmt_client.TmtClient(cred, "ap-guangzhou")

@directive("tx-cloud", "translation", domain_alias="腾讯云", action_aliases={"translation": "翻译"})
def translation(params: list[str]) -> dict:
    """tx-cloud;translation,<text>[,<target>]"""
    text = params[0]
    target = params[1].strip() if len(params) > 1 and params[1].strip() else "en"
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

### 3.4 安装后用户操作

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

---

## 四、容器 API 包

容器 API 包将自托管服务的 REST API 封装为 text-cli 指令。服务运行在本地 Docker 容器中，handler.py 作为 HTTP 客户端调用它。

以"Jellyfin 媒体服务器"为例——用户通过 text-cli 浏览家庭媒体库。

### 4.1 目录结构

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

### 4.2 handler.py 核心模式

```python
import json, requests
from pathlib import Path
from core.registry import directive

# 相对本文件定位配置，不依赖进程 CWD
_CONFIG_PATH = Path(__file__).parent / "config" / "jellyfin.json"

def _load_config():
    """读取服务地址配置"""
    with open(_CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)

def _api(path):
    """调用 Jellyfin REST API"""
    config = _load_config()
    headers = {"X-Emby-Token": config["api_key"]}
    resp = requests.get(f"{config['url']}{path}", headers=headers)
    return resp.json()

@directive("jellyfin", "library", domain_alias="家庭媒体", action_aliases={"library": "媒体库"})
def library(params: list[str]) -> dict:
    """jellyfin;library —— 列出所有媒体库"""
    data = _api("/Library/VirtualFolders")
    libraries = [{"name": lib["Name"], "type": lib["CollectionType"]}
                 for lib in data]
    return {"status": "ok", "libraries": libraries,
            "count": len(libraries)}
```

### 4.3 与在线 API 包的差异

| 维度 | 在线 API 包 | 容器 API 包 |
|------|------|------|
| 服务位置 | 公网云服务 | 本地 `localhost` 或内网地址 |
| `credentials` | 需要（云服务商凭据） | 不需要（服务为本地认证） |
| `config/` 目录 | 通常不需要 | 必须有——存放服务地址和本地认证信息 |
| 前置条件 | 注册 API key | 启动 Docker 容器 |

### 4.4 安装后用户操作

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

---

## 五、MCP 桥接包

> 零 Python 代码——将已注册的 MCP server 的 tool 映射为 text-cli 指令。

**核心思路**：你已经在 mcporter(或其他管理和调用 MCP 服务器的工具) 中配好了一个 MCP server（如 GitHub），现在只需要写两个 JSON 文件，告诉 text-cli "这个 domain 下的 action 对应 mcporter 的哪个 server 的哪个 tool"。

### 5.1 目录结构

```
my-package/
├── schema.json                 ← 指令声明 + runtime:"mcp"
└── service-descriptor.json     ←  MCP 服务器的(mcporter) 路由映射
```

> MCP 包不需要 handler.py——调用链是 text-cli 指令 → mcp_dispatch → mcporter → MCP server，text-cli 不执行任何用户代码。

### 5.2 schema.json

```json
{
    "id": "tc-mcp-github",
    "name": "GitHub MCP Bridge",
    "name_zh": "GitHub MCP 桥",
    "runtime": "mcp",
    "type": "native",
    "version": "0.1.0",
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
                "perPage": "每页数量（默认 30）"
            },
            "mcp_tool": "search_repositories"
        }
    ]
}
```

### 5.3 service-descriptor.json

```json
{
    "mcp_server": "github",
    "tools": [
        {
            "name": "search_repos",
            "tool": "search_repositories"
        }
    ]
}
```

| 字段 | 说明 |
|------|------|
| `mcp_server` | mcporter 中配置的 server 名称（安装前必须先配好） |
| `tools[].name` | 对应 schema.json 中的 `action` 字段 |
| `tools[].tool` | mcporter 中该 server 的实际 tool 名称 |

### 5.4 前置条件

安装 MCP 包之前，必须先在 mcporter 中配置好对应的 server 连接。安装器会调用 `mcporter list <server_name>` 验证——如果 server 未配置，安装会失败并提示。

```bash
# 先配置 mcporter server
mcporter add github --transport streamable-http --url https://api.github.com/mcp
```

### 5.5 安装与验证

```bash
# 安装包（仅 service 运行时，不可安装到 copilot）
curl -X POST http://localhost:28050/text-cli/cli \
  -H "Service-token: <token>" \
  -d '{"prompt":"AI:text-cli;install,tc-mcp-github"}'

# 安装后路由表即时刷新，无需重启

# 调用
curl -X POST http://localhost:28050/text-cli/cli \
  -H "Service-token: <token>" \
  -d '{"prompt":"AI:comcp-github;search_repos,text-cli"}'
```

**降级链自动参与**：MCP 指令安装后自动出现在 mcp_dispatch 路由表中。如果 mcporter 不可达，degrade 信号会让降级链继续走到下一级（proxy / federation mesh），不会终端报错。

### 5.6 卸载

```bash
curl -X POST http://localhost:28050/text-cli/cli \
  -H "Service-token: <token>" \
  -d '{"prompt":"AI:text-cli;uninstall,tc-mcp-github"}'
```

> 卸载仅移除路由表条目和 schema 文件，不会删除 mcporter 中的 server 配置。

---

## 六、copilot 开发

copilot 是 Python 标准运行时的本地组件（`127.0.0.1:20260`），专门暴露本机操作系统能力——截屏、音频、终端命令、文件操作。与 service 不同，copilot 不能（也不应该）被网络中的其他机器访问。

### 6.1 什么时候用 copilot 而不是 service

| 场景 | 用哪个 |
|------|:---:|
| JSON 处理、数学计算、Markdown 转换 | service |
| 调用云服务 API（翻译、地图、语音识别） | service |
| 截屏、拍照、音量控制 | **copilot** |
| 执行本地终端命令 | **copilot** |
| 读写本机文件 | **copilot** |


> **判断标准**：如果指令的执行需要直接操控本机硬件、文件系统或终端——用 copilot。`127.0.0.1` 的锁是安全机制，不是限制。

### 6.2 安全模型：白名单闸门

copilot 包的每条指令可能执行 shell 命令——这对安全性提出了更高要求。text-cli 通过 **双重白名单闸门** 保证安全：

**闸门一（dispatch 层硬闸）**：`CopilotCore.dispatch()` 在路由 handler 前调用 `WhitelistIndex.lookup()` 校验——未登记的 domain/action 直接返回 `ACCESS_DENIED`，不进入 handler。此闸门由运行时强制执行，开发者不可绕过。

**闸门二（handler 层自检）**：handler 内部通过 `WhitelistIndex` 二次校验参数——`args_pattern` 正则匹配可变参数、`timeout` 限制执行时长。此闸门由开发者在 handler 中自行调用（见 §6.3 示例）。

- 每条被允许执行的命令需要显式登记在 `whitelist.json` 中
- 命令的固定参数（`args`）和可变参数（`args_pattern`）均需声明
- 每条命令有独立的超时时间（`timeout`）
- 未登记的命令——dispatch 层直接拒绝，不到达 handler

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

| 字段 | 说明 |
|------|------|
| `action` | 对应 schema.json 中的 `action` 字段 |
| `args` | 允许执行的固定命令和参数（如 `["gnome-screenshot", "-f"]`） |
| `args_pattern` | 正则表达式——校验传给命令的可变参数（如文件路径只允许 `.png` 后缀） |
| `timeout` | 超时秒数——防止命令挂死 |

### 6.3 完整示例：tc-ubuntu（桌面硬件控制）

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
  }
}
```

**handler.py 核心模式**：

```python
import subprocess
from pathlib import Path

def ok(result):
    return {"status": "ok", "result": result}

def error(reason):
    return {"status": "error", "reason": reason}

WHITELIST_DIR = Path(__file__).parent

_whitelist_index = None

def _get_index():
    global _whitelist_index
    if _whitelist_index is None:
        from whitelist_loader import WhitelistIndex
        _whitelist_index = WhitelistIndex(WHITELIST_DIR)
    return _whitelist_index

def _exec_whitelist(action, extra_args=None):
    index = _get_index()
    entry = index.lookup("tc-ubuntu", action)
    if not entry:
        return error(f"action not in whitelist: {action}")

    cmd = entry["args"].copy()
    if extra_args:
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

### 6.4 service 包 vs copilot 包

| 维度 | service 包 | copilot 包 |
|------|------|------|
| `requires.modules` | 无 | `["whitelist_loader"]` — 必须 |
| 额外文件 | — | `whitelist.json` — 必须 |
| 执行方式 | Python 函数 | `subprocess.run()` — 白名单校验后 |
| 安全约束 | 凭据隔离 | 白名单 + regex + timeout |
| 防御性设计 | 无特殊要求 | 音量上限 50%、录音最长 30 秒 |

### 6.5 安装与验证（copilot 运行时）

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

### 6.6 安全红线

| 红线 | 说明 |
|------|------|
| **不在 service 运行时注册系统指令** | service 监听 `0.0.0.0`——任何人可调。系统操控能力只能在 copilot (`127.0.0.1`) 中暴露 |
| **白名单最小化** | 只声明指令需要的命令和参数。不要放通配命令（如 `["bash", "-c"]` 不加 regex 限制） |
| **超时必须设** | 每条白名单条目必须设 `timeout`。没有超时的子进程是潜在的资源泄漏 |
| **参数校验必须严格** | `args_pattern` 用正则限制文件路径、数值范围——tc-ubuntu 的音量用 `^\d{1,2}%$` 保证不超过 99% |
