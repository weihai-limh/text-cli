# base 分组

## 定位

base 分组下的骨架层**不绑定任何运行时**——它们是所有上层的基础。A0 提供零依赖的协议级调用；A1 是 A0 之上的**能力集成封装层**，由三个平级子模块组成：skill/（Agent 可消费的 Skill 能力封装与指令编译）、phase-kernel（基于 text-cli 的生态上游编排内核）、tc-web-chat（单文件完整的现代 agent 前端）。

## 层级

| 层 | 名称 | 内容 | 备注 |
|:---:|------|------|------|
| A0 | protocol | 协议规范 + 零依赖调用示例（shell/python/js/ps1） | 不参与骨架累积链，直通模式 |
| A1 | skill | A1 的 Skill 能力封装子模块——编译（cli.py）+ 消费（skill.py）+ 多端点降级 | A1 平级子模块；构建时 A0 注入其 `skill/` 子目录 |
| A1 | phase-kernel | 基于 text-cli 的生态上游编排组件（相位推理调度内核） | A1 平级子模块 |
| A1 | tc-web-chat | 单文件现代 agent（对话 + 外部推理 + 指令工具调用 + 人闸） | A1 平级子模块 |

## A0 与 A1 的关系

A0 是"怎么调"（单端点 SDK，零依赖）；A1 在 A0 之上做能力集成封装——skill/ 负责"怎么调多个端点 + 怎么造"（多端点调度 + 指令编译，经 A0 SDK 发 HTTP），phase-kernel 负责"怎么编排多步推理"（经 adapters/ 适配器对接 tc 运行时），tc-web-chat 负责"怎么让人与 agent 交互"（单文件 agent 前端，连外部 LLM + 调 text-cli 指令）。

---

## A0 — 协议消费 SDK / CLI

零依赖——一份脚本就能调 text-cli 服务。四语言实现分为两层：Python/JS 面向 AI Agent（SDK 层），Shell/PowerShell 面向人（CLI 层）。

### API 速览（Python）

```python
from call import call, discover, poll, wait

# 调用指令——总是立即返回
result = call("AI:tc-math;eval,2+3*4")
# → DirectiveResult(ok=True, data={"result":14})

# 发现能力——一次 HTTP 调用，带缓存，零成本过滤
directives = discover(search="weather")
# → [{"domain":"weather","action":"query","usage":"weather;query,<city>,<date>",...}]

# 异步轮询——单次查询
status = poll("abc123")
# → DirectiveResult(is_async=True, data={"state":"running","progress":"50%"})

# 异步等待——指数退避 + 进度回调
final = wait("abc123", on_status=lambda s: print(s.get("state")))
# → DirectiveResult(ok=True, data={"path":"/media/out.mp4"})
```

JavaScript API 与 Python 完全一致：`call()` / `discover()` / `poll()` / `wait()`，返回 `DirectiveResult`。

支持按次调用的 token 覆盖：`call("AI:...", endpoint="...", access_token="...", service_token="...")`。

### CLI 快速上手（Shell）

```bash
echo "AI:tc-math;eval,2+3*4" | ./call.sh
./call.sh --task abc123
```

PowerShell：`./call.ps1 "AI:..."` / `./call.ps1 -Task abc123`。

### 四种实现

| 层 | 语言 | 文件 | 零依赖 | API |
|:---:|------|------|:---:|------|
| SDK | Python | `A0-protocol/python/call.py` | urllib | call, discover, poll, wait, call_batch |
| SDK | JavaScript | `A0-protocol/js/call.js` | fetch | call, discover, poll, wait, callBatch |
| CLI | Shell | `A0-protocol/shell/call.sh` | curl+python3 | call, --task |
| CLI | PowerShell | `A0-protocol/shell/call.ps1` | Invoke-WebRequest | call, -Task |

### 配置

默认端点 `http://127.0.0.1:28050/text-cli/cli`：

```json
{
  "endpoint": "http://127.0.0.1:28050/text-cli/cli",
  "service_token": "",
  "access_token": ""
}
```

优先级：环境变量（`TEXT_CLI_ENDPOINT` / `TEXT_CLI_SERVICE_TOKEN` / `TEXT_CLI_ACCESS_TOKEN`）> `conf.json` > 默认值。

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

## A1 — 能力集成封装层

A1 是 A0 之上的**能力集成封装层**：在 A0 协议能力之上，把"可消费的能力"封装、调度、呈现给 Agent 与人。由三个同级子模块组成：

```
A1 = skill/（Skill 能力封装 + 端点调度） + phase-kernel（调度内核）+ tc-web-chat（单文件现代 agent）
```

- **`skill/`**：Skill 能力封装——端点注册表 + 聚合清单 + 消费侧降级 + 多 Token 路由，Agent 可消费（本节的 §skill 部分详述）。
- **`phase-kernel/`**：相位推理调度内核（见下文专章）。
- **`tc-web-chat/`**：单文件完整的现代 agent（对话 + 外部推理 + 指令工具调用，见下文专章）。

A1 不提供运行时——所有 HTTP 调用经由 A0 SDK。

### A1 全景目录

```
A1-skill/
├── skill/                         ← OpenClaw Skill 入口容器（SKILL.md 在此）
│   ├── SKILL.md                   ← OpenClaw Skill 入口——快速开始
│   ├── README_zh.md
│   ├── python/
│   │   ├── skill.py               ← Skill 基类 + @skill + 降级链
│   │   ├── aggregation.py         ← 端点管理 + sync_endpoints
│   │   ├── cli.py                 ← @register + generate_schema
│   │   ├── handlers/sample.py     ← 编译路径示例
│   │   └── call.py                ← A0 SDK（构建时注入，见下「A0 SDK 注入」）
│   ├── prompts/                   ← Agent System Prompt 模板
│   │   ├── SKILL.md
│   │   ├── text-cli-core_zh.md
│   │   ├── text-cli-sync-skill.md
│   │   └── agent-text-cli-schema.example.json
│   └── config/
│       ├── agent-endpoints.json       ← 端点注册表（手动维护）
│       └── agent-text-cli-schema.json ← 聚合清单（sync 生成）
├── phase-kernel/                  ← 相位推理调度内核（core/ports 零依赖）
│   ├── docs/                      ← design_zh.md + user-manual_zh.md
│   └── phase_kernel/              ← core / ports / adapters / serve 六边形
└── tc-web-chat/                   ← 单文件现代 agent
    ├── docs/                      ← README_zh.md + user-manual_zh.md
    ├── tc-web-chat-src/           ← 源文件（build.js + 各 tc-*.js 模块）
    └── tc-web-chat.html           ← both/zh/en 三件套制品
```

**A0 SDK 注入（构建时）**：源码 `A1-skill/` 内**不含** `call.py`——`build-all.py` 的依赖构建把 `base/A0-protocol` 注入到 `deploy/A1-skill/skill/` 子目录，使 `call.py` 与 `skill.py` **同目录**（`skill/python/`），`skill.py` 用 `__file__` 相对定位即可导入 A0。

### skill/ — Skill 能力封装（Agent 可消费）

`skill/` 是 A1 的核心能力容器：面向多个 Service 和 Endpoint 的多端点调度层。每个 A1 消费者定义自己的可信端点集。**skill/ 内部结构与 A0 SDK 注入见上「A1 全景目录」。**

```
skill = Skill + 端点注册表 + 聚合清单 + 消费侧降级 + 多 Token 路由
```

两条路径：
- **消费**：Skill.run() → 查聚合清单 → 择最高 rank 端点（含 token 解析） → A0.call() → 失败降级下一 rank
- **生产**：@register → generate_schema() → 安装为指令包

#### 端点与降级

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

#### 编译路径（cli.py）

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

#### 消费路径（skill.py）

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

#### sync 工具（aggregation.py）

```python
from aggregation import sync_endpoints, register_endpoint

register_endpoint("add endpoint https://my-api.example.com/text-cli/cli, token MY_TOKEN")
sync_endpoints()  # 轮询所有端点 → 聚合 → 写入 agent-text-cli-schema.json
```

sync 是冷路径——不在 Agent 推理循环内。定期或按需执行。

#### Agent Skill 定义（prompts/）

| 文件 | 内容 |
|------|------|
| `SKILL.md` | Agent 调度 System Prompt——A0 SDK + A1 降级 |
| `text-cli-core_zh.md` | 核心调度 v2.0——A0 call() + DirectiveResult |
| `text-cli-sync-skill.md` | 同步 Skill 概念设计 |
| `agent-text-cli-schema.example.json` | 聚合 Schema 示例 |

#### 做为 OpenClaw Skill 安装

**`skill/` 可作为 OpenClaw Skill 安装**（它是 A1 的 Skill 本体，`SKILL.md` 在此）。phase-kernel、tc-web-chat 是 A1 的平级子模块，非 Skill 本体，不参与安装：

```bash
# Git 安装
git clone https://github.com/weihai-limh/text-cli.git
cp -r text-cli/deploy/A1-skill/skill ~/.openclaw/skills/text-cli

# ClawHub（发布后）
clawhub install text-cli
```

OpenClaw 加载 `skill/SKILL.md` → Agent 学会使用 `call()` / `discover()` / `Skill.run()`。

### phase-kernel — 基于 text-cli 的生态上游编排组件

A1 子模块，text-cli 生态上游的多步可干预调度内核（入口指令 `tc-phase;run`，经 adapters/ 的 TCExecutor 接入 text-cli 运行时）。

- **机制**：相位推理 = "多次推理 + 多次上下文重组"在规划层的投影。**核心机制（`core/` + `ports/`）零外部依赖**（仅标准库 + 自身），所有 tc/strata/LLM 差异收口于 `adapters/`——即"相位机制通用、tc 对接在适配层"。
- **与 tc 对应**：一维契约可递归收敛 → 相位递归分层（`Planner` → `PhasePlan` 相位树 → `Executor`）；统一信封状态可知 → 相位闸门与回退（`PhaseResult{status}` 闭集）；query/install 内省 → 相位工具目录。
- **文档**：`phase-kernel/docs/design_zh.md`（设计 + 实现真源）、`user-manual_zh.md`（使用手册）。
- **验证**：Python 15 测试全绿，node 核心同构通过；dsh 内化未立项。

### tc-web-chat — 单文件完整的现代 agent

A1 子模块，一个**单文件自包含的现代 agent**——遵循"编排 + 消费外部能力"的现代范式：不自带模型、不自带工具实现，推理连外部 LLM、指令执行委托 text-cli 运行时。

- **形态**：单文件自包含。`tc-web-chat.html`（both 版，内嵌中英双语）+ `tc-web-chat_zh.html` / `tc-web-chat_en.html`（单语版）三件套制品——所有源模块（config/chat/parser/approval/quiet/cache/integrate）由 `build.js` 内联进单个 html，打开即用，零外部 JS 依赖。
- **agent 能力**：对话与上下文；连外部 LLM 后端推理（Base URL）；经 text-cli 运行时消费指令（`discover` 发现能力 + `runTool` 发 `AI:` 原语）；人闸审批（Tool Gate + 人闸卡片 + 熔断器）；多模态上传；tc 离线降级为纯聊天；中英双语。
- **使用**：打开 html → 填聊天后端 Base URL + 请求头 → 可选勾选 `tc_enabled` 起 tc 指令消费（指向 text-cli 运行时）。
- **文档**：`tc-web-chat/docs/README_zh.md` + `user-manual_zh.md`。

---

_2026-08-28_
