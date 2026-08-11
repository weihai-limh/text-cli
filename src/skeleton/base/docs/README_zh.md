# base 分组

## 定位

base 分组下的骨架层**不绑定任何运行时**——它们是所有上层的基础。A0 提供零依赖的协议级调用，A1 提供 Agent 可消费的 Skill 封装和指令编译工具。

## 层级

| 层 | 名称 | 内容 | 备注 |
|:---:|------|------|------|
| A0 | protocol | 协议规范 + 零依赖调用示例（shell/python/js/ps1） | 不参与骨架累积链，直通模式 |
| A1 | skill | Agent Skill 调度层——编译（cli.py）+ 消费（skill.py）+ 多端点降级 | 依赖组装（先铺 A0，再铺 A1） |

## A0 与 A1 的关系

A0 是"怎么调"（单端点 SDK），A1 是"怎么调多个端点 + 怎么造"（多端点调度 + 指令编译）。

---

## A0 — 协议消费 SDK / CLI

零依赖——一份脚本就能调 text-cli 服务。四语言实现分为两层：Python/JS 面向 AI Agent（SDK 层），Shell/PowerShell 面向人（CLI 层）。

### API 速览（Python）

```python
from call import call, discover, poll, wait

# Call directive — always returns immediately
result = call("AI:tc-math;eval,2+3*4")
# → DirectiveResult(ok=True, data={"result":14})

# Discover capabilities — one HTTP call, cached, zero-cost filtering
directives = discover(search="weather")
# → [{"domain":"weather","action":"query","usage":"weather;query,<city>,<date>",...}]

# Async poll — single query
status = poll("abc123")
# → DirectiveResult(is_async=True, data={"state":"running","progress":"50%"})

# Async wait — exponential backoff + progress callback
final = wait("abc123", on_status=lambda s: print(s.get("state")))
# → DirectiveResult(ok=True, data={"path":"/media/out.mp4"})
```

JavaScript API is identical: `call()` / `discover()` / `poll()` / `wait()`, returning `DirectiveResult`.

Per-call token overrides supported: `call("AI:...", endpoint="...", access_token="...", service_token="...")`.

### CLI Quick Start (Shell)

```bash
echo "AI:tc-math;eval,2+3*4" | ./call.sh
./call.sh --task abc123
```

PowerShell: `./call.ps1 "AI:..."` / `./call.ps1 -Task abc123`.

### Four Implementations

| Tier | Language | File | Zero-deps | API |
|:---:|------|------|:---:|------|
| SDK | Python | `A0-protocol/python/call.py` | urllib | call, discover, poll, wait, call_batch |
| SDK | JavaScript | `A0-protocol/js/call.js` | fetch | call, discover, poll, wait, callBatch |
| CLI | Shell | `A0-protocol/shell/call.sh` | curl+python3 | call, --task |
| CLI | PowerShell | `A0-protocol/shell/call.ps1` | Invoke-WebRequest | call, -Task |

### Configuration

Default endpoint `http://127.0.0.1:28050/text-cli/cli`:

```json
{
  "endpoint": "http://127.0.0.1:28050/text-cli/cli",
  "service_token": "",
  "access_token": ""
}
```

Priority: env vars (`TEXT_CLI_ENDPOINT` / `TEXT_CLI_SERVICE_TOKEN` / `TEXT_CLI_ACCESS_TOKEN`) > `conf.json` > defaults.

### 响应解析

四种实现统一解析协议信封：`rst_data` 直接使用（不再经 `.text` 嵌套），读取 `rst_err` 判断成功/失败，检测 `status=="pending"` + `task_id` 标记异步任务。

### 目录结构

```
A0-protocol/
├── python/
│   ├── call.py                    ← Python SDK：DirectiveResult + discover + poll + wait
│   └── conf.json                  ← 默认端点配置
├── js/
│   ├── call.js                    ← JavaScript SDK
│   └── conf.json
└── shell/
    ├── call.sh                    ← Bash CLI
    ├── call.ps1                   ← PowerShell CLI
    └── conf.json
```

---

## A1 — Agent Skill 调度层

A1 是 A0 之上的多端点调度层，面向多个 Service 和 Endpoint。每个 A1 消费者定义自己的可信端点集。A1 不提供运行时——所有 HTTP 调用经由 A0 SDK。

```
A1 = Skill + 端点注册表 + 聚合清单 + 消费侧降级 + 多 Token 路由
```

两条路径：
- **消费**：Skill.run() → 查聚合清单 → 择最高 rank 端点（含 token 解析） → A0.call() → 失败降级下一 rank
- **生产**：@register → generate_schema() → 安装为指令包

### 端点与降级

A1 维护两份端点文件——token 只存一处，聚合清单不重复 token：

| 文件 | 角色 | 维护者 |
|------|------|------|
| `agent-endpoints.json` | **单一真相源**：URL + token + rank + trust | 人 |
| `agent-text-cli-schema.json` | 聚合能力清单：directive → [source by rank]，不含 token | `aggregation.py` sync |

**agent-endpoints.json**：
```json
{
  "endpoints": {
    "home-service": {
      "url": "http://192.168.1.2:28050/text-cli/cli",
      "service_token": "${HOME_SERVICE_TOKEN}",
      "auth": "single",
      "rank": 1,
      "trust": "internal"
    },
    "cloud-endpoint": {
      "url": "https://tide.agentbot.space/text-cli/cli",
      "access_token": "${TIDE_ACCESS_TOKEN}",
      "service_token": "sk-abc123",
      "auth": "dual",
      "rank": 2,
      "trust": "community"
    }
  }
}
```

Token 支持 `${ENV_VAR}`（环境变量引用）或裸字符串。`auth: "single"` 直连 Service（仅 Service Token）；`auth: "dual"` 通过 Endpoint（Access + Service Token）。

**降级逻辑**：Skill.run() 内部沿 rank 降序尝试端点——成功即返回，失败（ERR_NOT_FOUND / ERR_ROUTING / HTTP 不可达）自动切下一源。参数错误和鉴权失败不降级。

### 目录结构

```
A1-skill/
├── SKILL.md                       ← OpenClaw Skill 入口——快速开始
├── python/
│   ├── call.py                    ← A0 SDK（构建时从 A0-protocol 复制）
│   ├── call.js                    ← A0 SDK JS
│   ├── conf.json                  ← A0 默认配置
│   ├── skill.py                   ← Skill 基类 + @skill + 降级链
│   ├── aggregation.py             ← 端点管理 + sync_endpoints
│   ├── cli.py                     ← @register + generate_schema
│   └── handlers/sample.py         ← 编译路径示例
├── prompts/                       ← Agent System Prompt 模板
│   ├── SKILL.md
│   ├── text-cli-core_zh.md
│   ├── text-cli-sync-skill.md
│   └── agent-text-cli-schema.example.json
├── config/
│   ├── agent-endpoints.json       ← 端点注册表（手动维护）
│   └── agent-text-cli-schema.json ← 聚合清单（sync 生成）
└── README_zh.md
```

### 编译路径（cli.py）

Agent 开发者用 `@register` 装饰器将既有函数包装为指令，自动生成 SPEC 兼容的 `schema.json`：

```python
from cli import register, generate_schema

@register(domain="weather", action="query", category="tool", trust="community")
def weather_query(params):
    return {"status": "ok", "result": f"{params[0]}: Sunny, 20C"}

schema = generate_schema("my-weather")
# → {"id":"my-weather","type":"native","runtime":"python","directives":[...]}
```

cli.py 仅负责指令注册和 Schema 生成——不提供 HTTP 运行时。

### 消费路径（skill.py）

Agent 用 `@skill` 装饰器封装指令为可复用技能。Skill 通过 A0 SDK 完成所有调用：

```python
from skill import Skill, skill

@skill("weather", domain="weather", action="query")
class WeatherSkill(Skill):
    def format_result(self, data):
        return f"[OK] {data['result']}"

    def on_error(self, params, err_code):
        return f"Cannot query {params[0]} weather ({err_code})"

result = WeatherSkill.run("Beijing", "tomorrow")
```

Skill.run() 内部流程：
1. 查 `agent-text-cli-schema.json` 获取所有可用源（按 rank 排序）
2. 回查 `agent-endpoints.json` 取 token
3. 通过 A0 `call(endpoint, access_token, service_token)` 发指令
4. 成功 → `DirectiveResult.data` → `format_result()`
5. 失败 → 消费侧降级：自动尝试下一 rank 端点
6. 全部耗尽 → `on_error()` 回调

### sync 工具（aggregation.py）

```python
from aggregation import sync_endpoints, register_endpoint

register_endpoint("add endpoint https://my-api.example.com/text-cli/cli, token MY_TOKEN")
sync_endpoints()  # 轮询所有端点 → 聚合 → 写入 agent-text-cli-schema.json
```

sync 是冷路径——不在 Agent 推理循环内。定期或按需执行。

### Agent Skill 定义（prompts/）

| 文件 | 内容 |
|------|------|
| `SKILL.md` | Agent 调度 System Prompt——A0 SDK + A1 降级 |
| `text-cli-core_zh.md` | 核心调度 v2.0——A0 call() + DirectiveResult |
| `text-cli-sync-skill.md` | 同步 Skill 概念设计 |
| `agent-text-cli-schema.example.json` | 聚合 Schema 示例 |

### 做为 OpenClaw Skill 安装

A1-skill 可作为 OpenClaw Skill 安装。根目录的 `SKILL.md` 是入口：

```bash
# Git 安装
git clone https://github.com/weihai-limh/text-cli.git
cp -r text-cli/deploy/A1-skill ~/.openclaw/skills/text-cli

# ClawHub（发布后）
clawhub install text-cli
```

OpenClaw 加载 `SKILL.md` → Agent 学会使用 `call()` / `discover()` / `Skill.run()`。

---

_2026-07-31_
