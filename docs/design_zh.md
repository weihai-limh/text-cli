# text-cli 设计文档

> **文档类型**：技术设计 | **关联文档**：[SPEC_zh.md](./SPEC_zh.md) | **修订**：2026-07-31
> **适用范围**：text-cli 全项目
>
> 本文档描述 text-cli 的工程机制。§一~§三描述协议和运行时体系的通用设计，§四以 Python 标准运行时为主线展开实现细节。
> 协议定义的规范（指令格式、响应信封、错误码等）见 SPEC_zh.md。

---

## 一、协议机制

text-cli 以一行文本调度所有后端能力。统一协议格式：

```
AI:域;动作,参数1,参数2,...
```


**参数拆分**：参数以逗号分隔，顺序固定。末位参数可为自由文本（含逗号）。参数中的 JSON 数组/对象可能含逗号——解析时追踪括号深度 `{}` `[]` 和字符串引号，只在深度为 0 的逗号处拆分。

**路由规则**：`domain;action` 组合精确匹配 handler。未命中时走别名映射（如中文→英文 canonical），再重试匹配。仍不命中返回 `ERR_NOT_FOUND`。

**Dispatch 管道**：指令分发按固定优先级——聚合入口优先命中，未命中走本地原生/MCP 显式偏好，本地未命中走 MCP 后备，最后 proxy 转发兜底。全部未命中返回 `ERR_NOT_FOUND`。

### 1.1 响应信封

```json
{
  "rst_types": "text",
  "rst_data": {"status": "ok", "result": 14},
  "rst_err": ""
}
```

| 字段 | 说明 |
|------|------|
| `rst_types` | 反映响应类型。默认为 `"text"`。当 handler 返回字典中包含 `pray_rst_types` 键时，骨架将其值提升至此字段。取值：`text` / `picture` / `video` / `audio` / `file` |
| `rst_data` | handler 返回的 JSON 对象，骨架直接承载 —— 不再以 `{"text": "..."}` 嵌套。调用方直接读取 `rst_data` 即可 |
| `rst_err` | 空字符串 = 成功；否则为错误码 |

### 1.2 错误码

| 错误码 | 含义 |
|--------|------|
| `ERR_NOT_FOUND` | domain;action 不存在 |
| `ERR_EXECUTION` | handler 执行异常 |
| `ERR_ROUTING` | 路由失败（proxy 目的地不可达等） |
| `INVALID_PARAMS` | 参数不合法 |
| `ACCESS_DENIED` | Access Token 无效 |
| `SERVICE_DENIED` | Service Token 无效不含配额耗尽 |

长任务（视频转换、ASR 等）不即时返回结果——handler 注册为异步模式，返回 `task_id`。调用方通过 `GET /text-cli/tasks/{task_id}` 轮询进度。

---

## 二、运行时体系

### 2.1 运行时分类

text-cli 按能力覆盖度将运行时分为两类：

- **标准运行时**：完整实现协议要求的全部机制。标准运行时是能力定义，不特指某一语言——任何能完整承载协议机制集的实现都是标准运行时。当前标准运行时基于 Python 实现（见 §四）。
- **旁路运行时**：只需支持协议机制的子集即可，不要求全量。按形态分云平台（CloudBase SCF / Cloudflare Workers）和多语言 SDK（textcli-loader / textcli-core）。约束示例：textcli-loader（PyPI）和 textcli-core（npm）不支持联邦 Mesh 和路径编排机制；Cloudflare Workers 为纯网关，不做执行。

### 2.2 标准运行时必备机制

标准运行时必须完整实现以下 9 项协议机制（闭集）：

| 机制 | 说明 |
|------|------|
| 指令运行 | 对符合协议的指令进行解析、路由、执行与响应封装 |
| 安装及卸载指令包 | 指令包生命周期管理：安装时注册指令与依赖，卸载时完整回收 |
| 指令的鉴权与发现 | 鉴权（双层令牌 / 配额保护）与发现（基于 schema 的指令查询） |
| 路径编排 | 指令序列的编排与插值执行 |
| 异步任务调度（状态持久化） | 异步指令的任务化调度与查询 |
| 聚合与降级链 | 域级聚合入口与提供方降级 |
| 联邦 Mesh | 多节点联邦拓扑下的按 peer 凭证注入与转发 |
| 协议桥 | 与其他协议生态的双向桥接（MCP 为其一种实现） |
| 门面抽象 | 短名到执行目标的映射，门面指令与原子指令平权 |

协议只规定机制集本身，不规定各机制的实现方式。

### 2.3 当前运行时形态

| 形态 | 类型 | 说明 |
|------|------|------|
| Python 标准运行时 | 标准 | 自拥部署，完整 9 项机制（见 §四） |
| textcli-loader | 旁路 | PyPI SDK，轻量消费端（见 §五） |
| textcli-core | 旁路 | npm SDK，JavaScript 同构实现（见 §五） |
| CloudBase SCF | 旁路 | 腾讯云云函数，Node.js（见 §五） |
| Cloudflare Workers | 旁路 | 边缘计算网关，协议解析 + 路由分发（见 §五） |

---

## 三、消费侧——从裸协议到智能调度

消费侧分四个层次：裸 curl（最低门槛）、协议消费 SDK（封装调用）、AI 技能调度层（多端点降级）、Agent 集成全景（自进化闭环）。

### 3.1 curl 裸调用

最低门槛——知道一个端点地址即可：

```bash
curl -X POST http://localhost:28050/text-cli/cli \
  -H "Content-Type: application/json" \
  -d '{"prompt":"AI:tc-math;eval,2+3*4"}'
```

响应：

```json
{"rst_types": "text", "rst_data": {"status":"ok","result":14}, "rst_err": ""}
```

`rst_types` 反映响应类型。`rst_data` 直接承载 handler 返回的 JSON 对象——调用方直接读取 `rst_data` 即可：有 `"text"` 字段 = 纯文本，有 `"url"` 字段 = 可渲染媒体，皆无 = 元数据。

### 3.2 协议消费 SDK

curl 够直接，但每次调都要拼 HTTP 请求、解析信封、处理错误。协议消费 SDK 把这些封装为统一 API——四种语言实现，零依赖，一份脚本就能用。

#### API 抽象

核心返回类型 `DirectiveResult`（`src/skeleton/base/A0-protocol/python/call.py:73`），封装成功/失败/异步三种状态：

```python
from call import call, discover, poll, wait

# 同步调用——立即返回
result = call("AI:tc-math;eval,2+3*4")
# → DirectiveResult(ok=True, data={"result": 14})

# 指令发现——一次 HTTP，缓存结果，零成本过滤
directives = discover(search="weather")
# → [{"domain":"weather","action":"query","usage":"weather;query,<city>,<date>",...}]

# 异步任务——轮询或指数退避等待
status = poll("abc123")
# → DirectiveResult(is_async=True, data={"state":"running","progress":"50%"})

final = wait("abc123", on_status=lambda s: print(s.get("state")))
# → DirectiveResult(ok=True, data={"path":"/media/out.mp4"})
```

JavaScript API 与 Python 等价：`call()` / `discover()` / `poll()` / `wait()`，返回 `DirectiveResult`。

#### 两层定位

源码位置：

| 层 | 语言 | 入口 | 面向 |
|:---:|------|------|------|
| SDK | Python | `src/skeleton/base/A0-protocol/python/call.py`（urllib） | AI Agent |
| SDK | JavaScript | `src/skeleton/base/A0-protocol/js/call.js`（fetch） | AI Agent |
| CLI | Shell | `src/skeleton/base/A0-protocol/shell/call.sh` | 人——命令行管道 |
| CLI | PowerShell | `src/skeleton/base/A0-protocol/shell/call.ps1` | 人——命令行管道 |

Shell CLI 示例：

```bash
echo "AI:tc-math;eval,2+3*4" | ./call.sh
./call.sh --task abc123
```

#### 配置与 Token

默认端点 `http://127.0.0.1:28050/text-cli/cli`。配置优先级（见各语言 `conf.json`，如 `src/skeleton/base/A0-protocol/python/conf.json`）：

```
环境变量 (TEXT_CLI_ENDPOINT / TEXT_CLI_SERVICE_TOKEN / TEXT_CLI_ACCESS_TOKEN)
  > conf.json
  > 默认值
```

每次调用可携带独立 Token：

```python
call("AI:...", endpoint="...", access_token="...", service_token="...")
```

#### 响应解析

四种实现统一解析协议信封：`rst_data` 直接使用（不再经 `.text` 嵌套），读 `rst_err` 判断成功/失败，检测 `status=="pending"` + `task_id` 标记异步任务。

---

### 3.3 AI 技能调度层

协议消费 SDK 解决"怎么调一个端点"。AI 技能调度层解决"怎么调多个端点 + 怎么造指令"——它是 SDK 之上的多端点调度层，面向 Agent 的日常运行。

#### 架构

```
Agent Skill.run()
  → 查能力聚合清单（agent-text-cli-schema.json，按 rank 排序）
  → 回查端点注册表（agent-endpoints.json，取 token）
  → SDK call(endpoint, access_token, service_token)
  → 成功 → format_result()
  → 失败 → 消费侧降级：自动尝试下一 rank 端点
  → 全部耗尽 → on_error()
```

Skill 不直接持有 HTTP 调用——所有网络操作经由 SDK。Skill 层只做端点选择、降级决策和结果格式化。

#### 双文件真相源

（`src/skeleton/base/A1-skill/config/`）

| 文件 | 角色 | 含 Token | 维护方式 |
|------|------|:---:|------|
| `agent-endpoints.json` | 端点注册表：URL + token + rank + trust | ✅ | 人手动维护 |
| `agent-text-cli-schema.json` | 能力聚合清单：directive → source（按 rank），不含 token | ❌ | `aggregation.py` sync 生成 |

Token 只存一处（端点注册表），能力清单不重复 token——两文件各司其职，不耦合。

端点注册表示例：

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

Token 支持 `${ENV_VAR}`（环境变量引用）或裸字符串。`auth: "single"` 直连 Service（仅 Service Token）；`auth: "dual"` 经 Endpoint（Access + Service Token）。

#### 消费侧降级

与 §四服务端的聚合降级不同，消费侧降级按端点 rank 依次尝试——非服务内部提供方切换，而是端点级容错：

- 成功即返回
- `ERR_NOT_FOUND` / `ERR_ROUTING` / HTTP 不可达 → 自动切下一 rank
- 参数错误和鉴权失败不降级（切换端点无意义）
- 全部耗尽 → `on_error()` 回调

#### 编译路径：造指令

（`src/skeleton/base/A1-skill/python/cli.py`——`register()` at :36, `generate_schema()` at :129）

```python
from cli import register, generate_schema

@register(domain="weather", action="query", category="tool", trust="community")
def weather_query(params):
    return {"status": "ok", "result": f"{params[0]}: Sunny, 20C"}

schema = generate_schema("my-weather")
# → {"id":"my-weather","type":"native","runtime":"python","directives":[...]}
```

编译路径仅负责指令注册和 Schema 生成——不提供 HTTP 运行时。

#### 消费路径：调指令

（`src/skeleton/base/A1-skill/python/skill.py`——`Skill` 类 at :103, `Skill.run()` at :201, `@skill` 装饰器 at :211）

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

Skill.run() 内部走完整调度链：查能力清单 → 取 token → SDK 调用 → 降级 → 格式化。Agent 只需调 `Skill.run()`，不感知端点拓扑。

#### 冷路径同步

端点能力聚合不在 Agent 推理循环内——`aggregation.py`（`src/skeleton/base/A1-skill/python/aggregation.py`）作为冷路径工具，定期或按需执行：

```python
from aggregation import sync_endpoints

sync_endpoints()  # 轮询所有端点 → 聚合 → 写入 agent-text-cli-schema.json
```

---

### 3.4 AI Agent 集成全景

Agent 接入 text-cli 有三条互补路径，从零代码到全代码覆盖全谱系用户：

| 路径 | 入口 | 面向 | 产出 |
|------|------|------|------|
| **编译路径** | `@register` → `generate_schema()` | 开发者 | schema.json + handler.py |
| **消费路径** | `@skill` → `Skill.run()` | Agent 运行时 | 可复用技能 |
| **NoCode 路径** | 结构化 Markdown → 自动解析 | 非开发者 | nocode 指令包 |

三条路径之上，Agent 可形成自主进化闭环——通过 text-cli 的元指令自我管理能力扩展：

```
Agent 醒来 → /health → text-cli;query → 缺翻译能力
  → 借助脚手架/指南快速转化为指令包
  → text-cli;install,xx-cloud → 安装指令包，新能力上线
  → "查天气→穿衣建议"反复出现 → text-cli;pro → 发布为路径
```

Agent 配套 System Prompt 模板（`src/skeleton/base/A1-skill/prompts/` 目录）：核心调度协议（`SKILL.md`、`text-cli-core_zh.md`）、同步 Skill 概念设计（`text-cli-sync-skill.md`）、聚合 schema 示例（`agent-text-cli-schema.example.json`）——指导 Agent 正确使用 SDK 和 Skill 层。

此外，技能调度层可作为 OpenClaw Skill 安装（入口：`src/skeleton/base/A1-skill/SKILL.md`）——Agent 加载后自动学会使用 `call()` / `discover()` / `Skill.run()`，无需人工配置路由。

---

## 四、Python 标准运行时

> 以下描述 Python 标准运行时的具体实现。其他运行时形态见 §五。
> 所有源码位于 `src/skeleton/`。`deploy/` 由构建脚本自动生成，不应手动修改。

### 4.1 组件拓扑

三个组件有严格的职责边界和安全隔离：

```
┌─────────────────────────────────────────────────────┐
│               Python 标准运行时                       │
│                                                     │
│  ┌──────────┐   ┌──────────┐   ┌──────────────┐    │
│  │ copilot  │   │ service  │   │  endpoint     │    │
│  │ :20260   │   │:28050/9020│   │  :29050       │    │
│  │          │   │          │   │               │    │
│  │ 本机终端  │   │ 指令包挂载│   │ 公网鉴权转发  │    │
│  │ 文件/Git  │   │ API/容器  │   │ 双 Token     │    │
│  │ shell    │   │ 编排/聚合 │   │ 透明代理     │    │
│  └──────────┘   └──────────┘   └──────────────┘    │
│  127.0.0.1       0.0.0.0             公网           │
└─────────────────────────────────────────────────────┘
```

| 组件 | 监听 | 能力 | 安全边界 |
|------|------|------|---------|
| copilot | 127.0.0.1:20260 | 指令包挂载/文件系统/shell/操作 | 仅本机可达 |
| service | 0.0.0.0:28050 | 指令包挂载/编排/聚合/MCP/SQL | 内网可达,公网控制访问 |
| endpoint | 0.0.0.0:29050 | Access Token 鉴权/路由转发/记账 | 不持有指令，不执行逻辑 |
| service-mcp | 0.0.0.0:9020 | 默认Token  | 指令服务反向暴露为MCP服务,以MCP的姿态对外提供服务 |

### 4.2 渐进分层体系

以 A0-A9 逐层累积构建，每层是完整终点：

| 层级 | 模块 | 机制 |
|:---:|------|------|
| A0 | protocol | 协议规范——四种语言零依赖调用示例 |
| A1 | skill | 指令编译/消费/NoCode——造指令和调指令的三条路径 |
| A2 | copilot | 本机终端代理——白名单 + Skill Bridge + 独立包管理 |
| A3 | service | 调度中枢——install/uninstall/query/dispatch/nocode/export/proxy |
| A4 | paths | 路径编排——条件分支/降级递补/并行/循环迭代(map)/跨节点 dispatch |
| A5 | endpoint | 鉴权网关——双 Token/多后端发现/转发记账 |
| A6 | sql | SQLite 持久层——key/任务管理 + quota + auth |
| A7 | mcp | MCP 双向桥——mcporter 入向 + FastMCP 出向 |
| A8 | discovery | 聚合入口——多提供方降级链/dispatch 管道首位 |
| A9 | advanced | 门面抽象+全量终点 |

> 注：A8/A9 的定义与其他文档统一——A8 聚合入口、A9 门面抽象+全量终点。

**累积规则**：A3 自动包含 A2 的全部 + service 本体。A9 包含 A2-A8 的全部。后层同名文件覆盖前层。A5 endpoint 和旁路运行时（CloudBase/PyPI/npm/Cloudflare）不参与累积链——水平独立分发。

**构建链路**：`src/skeleton/`（唯一编辑入口）→ `build-all.py`（累积/直通）→ `deploy/`（中间产物）→ 分发脚本 → `.zip/.tar.gz/Docker`。`deploy/` 由构建自动生成，不应手动编辑。

### 4.3 源码结构

#### copilot

```
src/skeleton/copilot/A2-copilot/copilot/
├── text-cli-copilot.py     # python text-cli-copilot.py → :20260
├── core.py                 # 指令引擎 + 路由 + dispatch
├── handlers/               # key / skill_bridge / package_manager / codec / adapters
├── whitelist_loader.py     # 白名单索引
└── auxiliary_config.json   # 安全策略 + handler 注册
```

copilot 独立运行，不依赖 service。

#### service

累积链主干，A3→A9 逐层叠加。每层只放该层引入或覆盖的文件，同名文件由后层覆盖前层：

```
src/skeleton/service/
├── A3-service/service/     # 基础平台（所有层的基础）
│   ├── main.py              # HTTP 服务入口 + dispatch 管道
│   ├── core/                # parser, registry, response, auth, config, identity_context
│   ├── handlers/            # install/uninstall/query/export/nocode/proxy/sync + schema/
│   ├── installer/           # validate, filesystem, dependencies, audit
│   └── config/              # handler_inits, YAML, manifests, webhook
├── A4-paths/service/       # + 路径引擎（text_cli_path/path_schema/path_loader/path_executor）
├── A6-sql/service/         # + SQLite 持久层（key/任务管理/task + quota + auth）
├── A7-mcp/service/         # + MCP 双向桥（mcp_dispatch, mcp_handler）
├── A8-discovery/service/   # + 聚合入口（aggregate/）
└── A9-advanced/service/    # + 门面抽象（handler_inits, pro_registry）
```

#### endpoint

```
src/skeleton/endpoint/A5-endpoint/
├── python/                 # FastAPI 变体（uvicorn → :29050）
│   ├── api/                # cli / health / skills / tasks
│   └── core/               # parser / backend_registry / forwarder / database
└── js/                     # Cloudflare Workers 变体
```

endpoint 是水平旁路——不参与骨架累积链，独立分发。两版实现功能等价。

### 4.4 部署

#### 层集成

构建链路：`src/skeleton/` → `build-all.py`（累积/直通）→ `deploy/` → 分发脚本 → `.zip/.tar.gz/Docker`。

- 累积层（A2-A9）：后层覆盖前层同名文件
- 直通层（A0/A1/A5/BYPASS）：原样镜像
- A5 endpoint 不参与累积链

#### 容器

```bash
python scripts/build-all.py       # 构建 deploy/ 产物
cd deploy/skeleton-container
python build.py                   # 生成 .build/ 上下文
python build.py --build           # 生成 + docker build
```

四种目标：`copilot`(:20260) / `service`(:28050) / `advanced`(:28050+20260+9020) / `a5-endpoint`(:29050)。

#### 分发包

```bash
# Windows
python scripts/release/win/build.py --layer A9
# Linux
python scripts/release/ubuntu/build.py --layer A9
# Endpoint
python scripts/release/win/build-endpoint.py --variant python
```

制品自包含——解压即用，无需 clone 仓库。

### 4.5 实现细节

#### 协议解析

**解析链**（`src/skeleton/service/A3-service/service/core/parser.py`）：

```
"AI:天气;查询,明天,威海"
  → prompt 解析 → directive = "天气;查询"
  → 按 `;` 拆分 → domain="天气", action="查询"
  → 按 `,` 拆分 → params=["明天", "威海"]
```

`domain;action` 组合在 `_registry`（内存字典）中精确匹配 handler 函数。未命中时走 `_alias_map` 查中文别名→英文 canonical 映射（如"天气;查询"→"weather;query"），再重试匹配。仍不命中返回 `ERR_NOT_FOUND`。

**@directive 装饰器**（`core/registry.py`）：

```python
@directive("hello", "world", domain_alias="你好", action_aliases={"world": "世界"})
def hello_world(params: list[str]) -> str:
    ...

# 自动注册：_registry["hello"]["world"] = hello_world
# 自动注册别名：_alias_map["你好;世界"] = "hello;world"
```

service 启动时 `import handlers`（`handlers/__init__.py` 自动发现并遍历 `packages/` 目录）触发所有 `@directive` 注册。外部指令包通过 `handler_inits.py` 在 install 时经 `importlib.reload` 热加载——handler 即时可用，无需重启 service。

**Dispatch 管道**（`service/main.py`）：

```
0. 聚合指令优先（降级链多提供方调度）
1. 本地原生/MCP 显式偏好
2. 本地 dispatch
3. 本地未匹配 → MCP 后备路由
4. 本地和 MCP 都没匹配 → proxy 转发
```

管道顺序固定——聚合最先执行，proxy 转发兜底（支持单跳与可配多跳跟随）。未命中时继续走后续路由，全部未命中返回 `ERR_NOT_FOUND`。

**指令重入检测（调用环防护）**：`registry.dispatch()` 内部使用 `ContextVar("_ANCESTOR_CHAIN")` 调用栈——每个 handler 执行前 push 解析目标键（`path:<id>` / `agg:<domain>` / `native:<domain>;<action>`），返回后 pop。键已在栈上 → `ERR_EXECUTION`。合法顺序重复调用（菱形/顺序重复）由 pop 放行，仅截真环（`A→…→A`）。`pro` 门面延迟检查（只查不推），确保 `pro→原生/首次` 不误杀。跨节点转发环由 `proxy.py` 的 `MeshLoopError`/`MAX_HOP_DEPTH` 独立覆盖，与 dispatch 祖先链正交。

#### 指令查看

`AI:text-cli;query` 不依赖内存注册表——每次查询实时扫描 `handlers/schema/` 下的所有 `*_schema.json`。数据流：`_load_schemas()` 扫描目录 → `_flatten_directives()` 提取 `directives[]` → `_apply_no_schema()` 过滤隐藏项 → 渲染输出。

八种查询模式：

| 参数 | 效果 |
|------|------|
| 无参 | 全量纯文本，按包分组，中文优先 |
| `,json` | JSON 格式 |
| `,compact` | 每行一个 `domain;action` |
| `,python\|js\|mcp` | 按 runtime 过滤 |
| `,category[,<分类>]` | 按分类过滤或列出所有分类 |
| `,<关键词>` | 模糊搜索 domain/action/description |
| `,collection` | 从 `config/collection_text_cli.json` 读取用户精选集 |
| `,delta` | 与上次查询比对变化（增/删） |

指令查询（schema 目录）与指令执行（`_registry` 内存字典）是两套独立系统。安装包时 schema.json 即时生效（query 立即可见），handler 通过 `importlib.reload` 热加载后即时可用（无需重启）。A2 代理发现：渲染时额外 `GET http://127.0.0.1:20260/text_cli_schema.json` 获取 copilot 可达指令。

#### 指令包安装与卸载

**安装流程**：`validate_package()` 校验 schema/runtime/系统域保护 → `install_files()` schema→handlers/schema（即时）/ handler.py→packages → `install_deps()` pip/npm → `_append_handler_init()` AST 解析 handler.py 追加初始化声明 → `_load_and_wire()` 直接 `import_module` 新模块 + init 注入 + dispatch 注入（handler 即时可用，无需重启。新包首次安装无需 reload；update/--force 场景先 `_invalidate_package` 清理旧注册和模块引用再重新 import）→ `manifest_register()` 写入 installed_packages.json。源码：`handlers/text_cli_install.py`。

**卸载流程**：系统域保护拒绝卸载 text-cli → `_registry_unregister()` 从内存移除 → `remove_files()` 删 packages + schema → `_drop_tables()` 执行 DROP TABLE → `_remove_handler_init()` + `manifest_remove()` 清理注册记录 → `_invalidate_package()` 摘除 `sys.modules` 中对应包的所有模块引用（清理彻底）。源码：`handlers/text_cli_install.py`（`_invalidate_package`）、`handlers/text_cli_uninstall.py`。

pip 依赖不自动移除（可能被其他包共享）。

#### copilot

copilot 使用 `co-install/co-uninstall`，与 service 的 `install/uninstall` 独立。已安装包的 handler 通过 `import_module`（新包）或 `_invalidate_package` + `import_module`（update）配合动态方法绑定实现**即时生效**（无需重启）。不再使用 `importlib.reload`。源码：`handlers/package_manager.py`。

```bash
python text-cli-copilot.py    # 127.0.0.1:20260
```

**co-install 流程**：`_resolve_package()` 搜索 → schema 校验 → 全量复制到 `packages/`（含 whitelists/adapters/config）→ `_write_package_ops()` 写入 `auxiliary_config.json` → `_load_and_wire()` 直接 `import_module` 新模块（新包）或先 `_invalidate_package` 清理再 `import_module`（update/--force）→ `_wire_package_handlers()` 动态绑定 → `_register_handlers()` 重新扫描注册表 → `WhitelistIndex.refresh()` 刷新白名单索引 → `_write_skill_routes()` 自动推断技能路由并写入 `skill_bridge_routes.json`。源码：`handlers/package_manager.py`。

**co-uninstall**：删 ops → 删 skill routes → 清理 adapters → rmtree → `_invalidate_package()` 清理动态绑定 + 摘除 `sys.modules` → `WhitelistIndex.refresh()` 刷新白名单索引 → `_register_handlers()` 重注册路由。源码：`handlers/package_manager.py`。

**白名单终端代理**：所有 shell/file/Git 操作经 `WhitelistIndex` 校验。`CopilotCore.__init__` 中实例化 `WhitelistIndex`（`whitelist_loader.py`），`dispatch()` 在路由 handler 前调用 `whitelist.lookup()` 校验——未登记或参数不匹配正则返回 `ACCESS_DENIED`。`WhitelistIndex.refresh()` 在 co-install/co-uninstall 后重建索引，确保新装/卸载的包即时生效。白名单由 co-install 时部署——不装包就没有可执行的终端操作。源码：`core.py`、`whitelist_loader.py`。

**技能桥接**：Skill Bridge 将外部 skill 映射为 text-cli 指令——不修改 skill 代码，只通过 `skill_bridge_routes.json` 声明命令模板。执行链：指令 → `_alias_map` 解析 canonical → handler 未命中 → `_try_skill_bridge()` → 白名单校验（`WhitelistIndex.lookup`）→ 查路由表 → 模板拼命令 → `subprocess.run()` → 通用适配器标准化 → output_adapter 字段映射 → 返回。

**响应信封规范**：copilot 的 `ok()` / `error()` 函数（`core.py`）遵循 text-cli 协议信封。`error()` 通过 `_ERROR_CODE_MAP` 将内部细粒度错误码（如 `skill_timeout`、`install_failed`）映射到协议闭集的 6 种错误码（`ERR_NOT_FOUND`/`ERR_EXECUTION`/`ERR_ROUTING`/`INVALID_PARAMS`/`ACCESS_DENIED`/`SERVICE_DENIED`），原始码保留在 `rst_data.error_code`。`ok()` 的 `rst_type` 限制为协议定义的白名单（text/picture/video/audio/file）。

#### 路径编排

路径引擎将多条原子指令串联为声明式管道。路径只做编排和插值——文件 IO、API 调用、推理全部通过下游指令。

**变量系统**：`{input}` 引用用户输入，`{step_id}` 引用上一步 `output_as` 输出，支持深路径 `{geo.poi.0.name}`。

**条件分支**：`if` 字段支持 `equals/contains/matches/exists` 及复合条件 `all([...])`/`any([...])`。

**降级递补**：`degradation` 链定义主步骤失败时的替代方案——按序尝试，成功则恢复执行。

**执行模式**：`mode: "toolchain"`（默认）为串行链；`mode: "parallel"` 下 `strategy: first_ok` 取首个成功结果 / `strategy: all` 全部执行。

**跨节点 dispatch**：`steps[].source` 逐步骤指定远端 URL——不同步骤可发到不同节点。

**超时断路**：每步独立 `timeout`（毫秒），未设置时继承 `default_source` 或走本机 dispatch。

**循环迭代（map）**：`mode:"map"` 对集合逐元素执行同一套子步骤。每轮迭代深拷贝变量，元素绑定 `{as}`（默认 `{item}`），末步输出经 `collect_as` 累积为列表供下游消费。支持 `concurrency: serial|parallel`、`on_error: break|continue`、嵌套深度守卫 ≤2。
- **安全闸门**：map 是入站能力，默认关闭——部署者需在 `text_cli.yaml` 设 `paths.map_enabled: true` 或设 `MAP_ENABLED=true` env。单次扇出上限 `paths.map_max_iter`（默认 100，硬上限 `MAP_HARD_CAP=1000` 钳制）。超限返回 `INVALID_PARAMS` + `LOOP_LIMIT`。
- **配置惰性加载**：`_get_map_config()` 首次读取 yaml 后缓存，进程生命周期内有效（与 `config.py` 行为一致）。配置不可用时安全降级为 `(False, 100)`——遵循 A3 守护钩子模式。
- **防注入**：循环绑定 `{as}` 仍在参数位，数据单向流入 body 的 `steps`，无法从数据位逃逸到指令位——与 §4.5「声明即沙箱」同源保证。

**统一 step 派发器**：`execute_path` 顶层循环经 `_dispatch_step(step, variables, index, messages, ..., lines, step_results, ...)` 统一路由——`toolchain` 走 `execute_step`，`parallel` 调 `execute_parallel_*`，`map` 调 `_execute_map`。替代了旧版在顶层内联判断 `mode` 的模式。

**管道闭包**：`steps` 在 JSON 中固定，数据通过命名管道单向流动——前面步骤的输出通过 `{step_id.field}` 语法传入后续步骤的指令参数，不经过中间存储。

**声明即沙箱**：路径协议的 `steps` 在 JSON 中固定，数据单向流动。用户输入永远是 handler 参数，接受白名单 / regex / 超时三层校验。注入载荷无法从数据位置逃逸到指令位置——这是协议层自带的安全特性，不是额外加固。

**完整示例**——一个同时使用跨节点 dispatch、超时、条件分支、降级递补的 pipeline：

```json
{
  "id": "geo-panoramic-query",
  "name": "Geo Panoramic Query",
  "type": "pipeline",
  "version": "1.0.0",
  "mode": "toolchain",
  "lang": "en",
  "default_source": "http://192.168.1.2:28050/text-cli/cli",
  "input_schema": {"type": "object", "properties": {
    "address": {"type": "string"},
    "end_lat": {"type": "number"}, "end_lon": {"type": "number"}
  }},
  "requires": ["map;geocode", "map;route", "geo-panoramic;china", "bd-map;static-map"],
  "steps": [
    {"id": "geocode", "instruction": "map;geocode,{input.address}",
     "output_as": "geo", "timeout": 5000},
    {"id": "road",
     "instruction": "map;route,{geo.lat},{geo.lon},{input.end_lat},{input.end_lon}",
     "output_as": "road", "timeout": 8000,
     "if": {"step": "geo", "field": "status", "equals": "ok"}},
    {"id": "visual",
     "instruction": "geo-panoramic;china,{road.points.0.lat},{road.points.0.lon}",
     "output_as": "panorama", "timeout": 15000,
     "source": "http://192.168.1.100:28050/text-cli/cli",
     "degradation": [
       {"id": "fallback", "instruction": "bd-map;static-map,{geo.lon},{geo.lat},16,600x400",
        "timeout": 10000}
     ]}
  ]
}
```

**示例 pipeline 工作机制**：路径引擎依次执行 `steps[]`。每步先做变量插值（`{input.key}`、`{step_id.field}`），再通过 `dispatch()` 分发指令。步骤结果解析为 JSON 后注册到变量池供下游步骤引用。`if` 条件不满足则跳过该步，`degradation` 链在主步骤失败后依次尝试替代方案，`timeout` 超时触发断路。带 `source` 的步骤走 HTTP 跨节点 dispatch，省略时继承 `default_source` 或走本机。

**示例说明**：IP 地址为占位值，对应不同节点的 text-cli 运行时。示例中的指令（`map;geocode`、`geo-panoramic;china` 等）不在项目提供的基础工具包内——如需实现同等功能，需自行寻找或开发对应的指令包。

#### 密钥管理

A6 层 SQLite 骨架服务。密钥通过 `key;register` 存入 `key_registry`，handler 通过 `_get_dispatch()` 回调获取密钥注入 API 请求——Agent 不可见密钥明文。

| 指令 | 行为 |
|------|------|
| `key;register` | 注册双凭据（secret_id+secret_key） |
| `key;revoke` | 撤销并清理 |
| `key;list` | 列举（含配额追踪状态） |
| `key;quota-track` | 关联配额追踪目标 |

启动时 `init_key_handler(db_path, dispatch_fn)` 注入连接。无 SQLite 模块退化为 proxy 转发。

#### 任务管理

长任务通过 `--async` 触发异步模式——检测参数尾 `--async` 后弹出、注册 `task_id`、`asyncio.create_task` 后台运行、立即返回 `{"status":"pending","task_id":"..."}`。

后台串行执行完整 dispatch 链：聚合 → 本地 → proxy，每步完成后调用 `task_manager_update`/`task_manager_complete` 更新 SQLite 状态。调用方通过 `GET /text-cli/tasks/{task_id}` 轮询进度与结果。

**managed 模式**：service 拥有执行权（`--async` 参数触发），后台跑完自动写入 `done`/`error`。任务状态含 5 个终态：`pending`/`running`/`done`/`error`/`cancelled`（`task;cancel` 将 `pending`/`running` 置为 `cancelled`）。实例重启时将残留 `running` 任务标记为 `error`，原因 `service_restarted`。异步执行中上游返回 `stop`（配额耗尽）时，`task_status` 识别该信号并标记 `error` + `quota_exhausted`。

**tracked 模式**：外部服务拥有执行权，`task;track` 注册时写入 `{"mode":"tracked","poll":{...}}` 元数据。`task;status` 检测到 tracked 模式后实时向上游轮询——状态仅在用户查询时刷新，不做后台定时轮询。上游返回 `stop` 时同样识别为配额耗尽。源码：`handlers/task_manager.py`。

| 指令 | 行为 |
|------|------|
| `task;status` | 查询状态（tracked 模式实时轮询上游） |
| `task;result` | 获取已完成任务结果 |
| `task;track` | 注册为 tracked 任务 |
| `task;cancel` | 取消 pending/running 任务 |

#### 配额管理

原子配额检查与消耗——聚合降级链的关键依赖：`quota;check` 返回 `stop` 时聚合层自动切换下一个提供方。

周期类型：day/week/month/year/forever。周期翻转时自动归零。`amount` 参数支持按量配额。

| 指令 | 行为 |
|------|------|
| `quota;check` | 原子检查 + 消耗（乐观锁） |
| `quota;register` | 注册配额规则 |
| `quota;list` | 列出全部及使用/剩余量 |
| `quota;reset` | 手动重置计数 |
| `quota;unregister` | 移除规则 |

#### MCP 桥接

**入向**——将外部 MCP server 的工具映射为 text-cli 指令。三层 mcporter 解析：`config/mcporter.json`（用户显式）→ `text_cli_modules/bin/mcporter`（自动发现）→ `PATH`（系统后备）。

路由决策：启动时构建 alias→canonical 映射和 MCP 路由表。`decide_backend()` 按 `routing_preferences.json` 决定走 mcp 或 local。

dispatch 管道中 MCP 被查两次——显式偏好优先，本地未命中后作为后备。配额检查在调用前执行。参数适配：`adapt_params()` 将 text-cli 位置参数映射为 MCP 命名参数。MCP 包安装后 `refresh_routes()` 动态重建路由表——无需重启。

**出向**——将 text-cli 已注册指令暴露为 MCP tools。FastMCP 子服务（:9020）从 `service_manifest.json` 的 `public_directives` 读取暴露白名单，再从 `handlers/schema/*.json` 读取指令定义，动态生成 MCP 工具函数。每个 tool 内部通过 HTTP POST `AI:domain;action,params` 到 service——不是重写逻辑，是桥接。暴露面与 `/skills` 端点同源（单一真相源）。由 main.py 的 lifespan 守护钩子拉起（后台线程），A3 单独部署时自动跳过。

#### 聚合降级

`aggregate/map.json` 定义每个 domain 的降级链。`_aggregate_dispatch()` 按 `default[]` 依次尝试——第一个成功的返回。

**降级触发条件**：`status: "stop"`（配额耗尽）/ `status: "error"` / rst_err 非空 / 抛异常 / 不支持此 action。

**用户显性选择**：末参数匹配 `providers` 中名称时跳过降级链，只用该提供方。提供方不区分来源——native handler/MCP bridge/Skill Bridge 在降级链中地位平等。聚合在 dispatch 管道中优先度最高。

#### 门面入口

`text-cli;pro` 提供简名→目标映射。两种目标类型：

| 类型 | 行为 |
|------|------|
| path | 转调 `text-cli;path` 执行路径声明 |
| aggregate | 转调 `domain;action` 走聚合降级链 |

配置在 `config/pro_registry.json`。调用方只需记 `text-cli;pro,<name>` 一个简名。

#### 联邦 Mesh 凭证

**请托模型**：mesh 的本质是请托（delegation），不是路由（routing）。源节点只声明"我把这条指令委托给 peer A"——peer A 的 `proxy_routes.json` 决定是否转发给 peer B。跳链不由源节点预先规划，而是由每一跳节点自己的路由表决定。源节点控制的不是"经过哪些节点"，而是"最多跟随几跳"。

**统一入口与多跳跟随**：`proxy_dispatch` 统一处理单跳与多跳。默认单跳——匹配 `proxy_routes.json` 中 `domain;action` → 转发到目标 URL。多跳跟随仅在 `mesh.multi_hop_enabled: true` 时激活：下游节点在响应中返回 `_mesh_redirect`（含 `domain;action` 和 `url`），proxy 解析后委托 `proxy_dispatch_multi_hop` 跟随到下一跳，直到目标节点不再返回 `_mesh_redirect` 或达到深度上限。

**信任半径**：`mesh.multi_hop_enabled: false`（默认关闭——mesh 是出站能力，但多跳跟随使请求路径超出部署者直接控制范围，需显式开启）。`mesh.multi_hop_max_depth: 3`（yaml 可配，生效值 `min(multi_hop_max_depth, MAX_HOP_DEPTH)`，`MAX_HOP_DEPTH=5` 为代码硬天花板）。与 path map 的 `map_max_iter` 同模——yaml 调的是信任半径，代码常量是天花板。

多节点联邦拓扑中，proxy 转发按 peer 注入凭证。`proxy_routes.json` 带 `peer` 字段的条目 → `MeshCredentialInjector.inject(body, peer)` 注入凭证 → 转发到目标 URL。

**注入式分层**：proxy 层（`handlers/proxy.py`）为纯转发管道，不持有凭证逻辑。凭证注入由 `MeshCredentialInjector`（`handlers/mesh_credentials.py`）独立提供——通过 `handler_inits` 注入到 proxy 的 `credential_injector` 参数。proxy 只调 `injector.inject(body, peer)` 接口，不感知内部实现。

`MeshCredentialInjector` 内部处理两条路径：(A) `peer` 非 None → per-peer 凭证（查 `peer_credentials` 表）；(B) `peer` 为 None → legacy all_keys 注入。凭证缺失时按 `mesh.require_credentials` 配置决定拒绝（`mesh_credential_unavailable`）或降级转发（标注 `_mesh_credential_degraded`）。

**安全防护**：`visited` 防环 / `MAX_HOP_DEPTH=5` 硬天花板（`multi_hop_max_depth` 在其之下可调）/ 指数退避重试（最多 2 次）。proxy 的 injector 异常被捕获并转为 `ERR_ROUTING` 响应。源码：`handlers/proxy.py`（含 `_get_mesh_config` 惰性配置加载 + 守护钩子安全降级）、`handlers/mesh_credentials.py`、`config/text_cli.yaml`。

#### endpoint

endpoint 不执行指令——只路由。启动时遍历 `A3_BACKENDS` 列表，逐个 `GET /text-cli/skills` 拉取各后端 service 的可达指令，聚合为统一能力表。`build_external_schema()` 将聚合表中每条指令的 URL 替换为 endpoint 自身地址——调用方只看到 endpoint。

请求到达时 `forward_request()`：`find_backend_source()` 定位目标后端 → `httpx.AsyncClient.post()` 透传 → 5xx 自动重试 → 写入 `call_logs`（request_id/domain/action/token前缀/状态码/耗时）→ 更新 `daily_stats`。

endpoint 不区分后端运行时形态——标准 Python service、Docker 部署、CloudBase 云函数在 `A3_BACKENDS` 中平等对待。

**安全防线**：三层逐级收紧的中间件链——

1. **IP 黑名单**：从 `IP_BLACKLIST` 加载 CIDR 列表，命中 403。
2. **限流**：滑动窗口算法。POST 1000/h，GET 10000/h。超限 429。
3. **Token 校验**：Access Token 验身份 → Service Token 前缀策略控制。

**双 Token 鉴权**：

```
调用方 ──Access Token──> Endpoint ──透传 Service Token──> Service
```

- **Access Token**：端点签发，验证调用者身份。
- **Service Token**：调用方与运行时所有者私下约定，端点只透传前 8 位做策略控制面识别。遵循前缀不变性原则——身份码位数可扩展，端点无感知。

>协议没有要求对指令的长度限制要求,项目实现时对'endpoint'设了512,对'运行时'设了'2048'
---

## 五、旁路运行时

不参与 A2→A9 累积链，但通过统一协议与标准运行时互通。

旁路运行时只需支持协议机制的子集即可——不同于标准运行时的 9 项全量要求。

### 云平台
#### CloudBase SCF

腾讯云云函数运行时（Node.js），将指令包部署为独立云函数，经网关路由转发。核心文件：`config.js` + `index.js`。

**架构**：
```
HTTP 触发器 → index.js exports.main
  → 解析 prompt → 查 config.js routeTable[domain] → 云函数名
    → cloud.callFunction(name, {prompt}) → handler(params) → 返回信封
```

支持 HTTP POST `/cli` 和 SDK 调用（`action=get_schema`）双模式。`GET /health` 返回健康状态。

**扩展新指令**：部署指令云函数 → 在 `config.js` 的 `routeTable` 中登记 `domain → 函数名` → 在 `packages` 数组中登记包 id（用于 `text-cli;query` 聚合）。新增包时无需改骨架代码，仅改网关侧配置。

### 轻量SDK
#### textcli-loader（PyPI）

`pip install textcli-loader` 即可在任何 Python 环境直接加载和执行不需要额外密钥的以python语言实现的指令包——不依赖任何 text-cli 服务，零额外依赖。核心文件：`loader.py` + `registry.py` + `envelope.py`。

```python
from textcli_loader import load_package, execute

load_package("./my-date-calc/")
result = execute("AI:date-calc;add-days,2026-01-01,30")
# → {"rst_types": "text", "rst_data": {"status":"ok","result":"2026-01-31"}, "rst_err": ""}
```

**工作原理**：`load_package()` 读取指令包的 `schema.json`，动态 `importlib` 导入 `handler.py`——`@directive` 装饰器将指令注册到内存注册表。`execute()` 解析 prompt → `dispatch()` → handler → 返回 text-cli 标准信封格式。

**兼容性桥接**：loader 注入了 `sys.modules` shim，同时映射 `from core.registry` 和 `from textcli_loader.registry`——既有的 text-cli 指令包无需任何修改即可在 loader 中运行。

#### textcli-core（npm）

`npm install textcli-core` 即可在任何 Node.js 环境直接加载和执行指令包。零外部依赖。与 Python textcli-loader **同构**——parser、registry、envelope 的 API 和行为完全一致，仅语言不同。

```javascript
const { parse } = require("textcli-core/parser");
const { register, dispatch } = require("textcli-core/registry");
const { ok, err } = require("textcli-core/envelope");

// 注册 handler
register("date-calc", "add-days", (params) => {
  const date = new Date(params[0]);
  date.setDate(date.getDate() + parseInt(params[1]));
  return { result: date.toISOString().split("T")[0] };
});

// 从文件加载指令包
const { loadPackage } = require("textcli-core/loader.node");
loadPackage("./my-package/");
```

**核心模块**：`parser.js`（支持 `AI:`/`指令:` 双前缀、括号深度追踪）、`registry.js`（`register`/`dispatch`/`unregister`/`getRegistered`，支持 sync/async handler）、`envelope.js`（`ok`/`err`，错误码白名单校验）、`alias.js`（别名映射，大小写不敏感）、`loader.js`（不依赖 IO 的核心加载接口）、`loader.node.js`（Node.js 平台适配器——`fs` + `require` 从磁盘加载）。

**与 Python loader 的关键差异**：loader 和平台适配器分离——`loader.js` 是纯逻辑，不依赖 `fs`/`require`；`loader.node.js` 是 Node.js 适配器。这种分离使得 Cloudflare Workers 等非 Node.js 环境可以直接复用 `parser.js` + `registry.js` + `envelope.js` + `alias.js` + `loader.js` 的纯逻辑模块，只需提供自己的平台适配器。

### Cloudflare Workers（边缘网关）

Cloudflare Workers 是一个**纯网关**——只做协议解析 + 路由分发 + 信封封装，不做执行。它复用了 textcli-core 的纯逻辑模块（parser、registry、envelope、alias、loader），把文件 IO 替换为 Workers KV Store。

```
Cloudflare Workers（边缘节点）
  │
  ├── POST /text-cli/cli → gateway.js
  │     ├── 解析 prompt → domain;action,params
  │     ├── 从 KV Store 加载包（schema.json）
  │     ├── 注册 handler（元数据模式——handler 为 null）
  │     ├── dispatch → 匹配成功则委托后端 Node.js 运行时执行
  │     └── 封装信封（ok / err）
  │
  └── GET /health → {status: "ok", service: "text-cli-cloudflare-gateway"}
```

**与 endpoint 的对比**：endpoint 是 HTTP 层面的纯管道（鉴权 → 路由 → 透传），gateway 是协议层面的纯网关（协议解析 → 包加载 → 路由分发 → 信封封装）。两者共享纯管道原则——不持有指令、不执行逻辑、不解析响应内容。

---

## 六、指令包设计

### 6.1 指令与指令包的关系

text-cli 的基本调度单位是**指令**：一行 `AI:域;动作,参数` 对应一次能力调用。一个 handler 可以注册多条指令（如 `bd-map;geocode` 和 `bd-map;route` 同属一个包），多条相关指令组成一个**指令包**。指令包是 text-cli 的能力分发单元——安装一个包，它的全部指令即时可用。

### 6.2 指令包分类体系

指令包通过 `schema.json` 中的两个关键字段声明自身定位：

| 字段 | 含义 | 决定因素 |
|------|------|---------|
| `type` | 包的声明形态 | 能力是如何组织的——代码 / Markdown / 路由 / 步骤链 |
| `runtime` | 包的执行方式 | 谁负责执行——Python / js / MCP / 命令行 / 路径引擎 |

**type × runtime 矩阵**：

| type | python | js | cmd | mcp | path | aggregate |
|------|:--:|:--:|:--:|:--:|:--:|:--:|
| native | ✅ 工具/API/容器 | ✅ | ✅ | ✅ MCP 桥接 | — | — |
| nocode | — | — | — | — | ✅ | — |
| aggregate | — | — | — | — | — | ✅ 纯声明 |
| pipeline | — | — | — | — | ✅ 纯声明 | — |

> nocode 无独立 handler 执行，其载体为路径引擎（`runtime: path`），由 `tc-markdown`+`ai_inference` 消费知识库。
> 项目在开源指令包中提供`tc-markdown`+`ai_inference` 的初始版本.

**四种 type 的设计意图**：

| type | 设计意图 | 典型场景 |
|------|---------|---------|
| `native` | 有代码实现的能力 | Python handler、Node.js 云函数需要编程语言支持的指令包 |
| `nocode` | 零代码——经验即服务 | 花店老板的盆栽诊断笔记 |
| `aggregate` | 多提供方统一入口 | 地图服务聚合了 tx-map/gd-map/bd-map 等多个提供方 |
| `pipeline` | 多指令编排成链 | "查天气→穿衣建议"自动编排 |

### 6.3 包与运行时的契约

**schema.json** 是包对运行时的声明面——`id`、`type`、`runtime`、`directives[]` 等字段构成协议契约。运行时据此完成指令注册、发现和路由。字段定义见 [package-publish-guide_zh.md](../src/text_cli/base_text-cli/docs/package-publish-guide_zh.md)。

**各运行时的实现替代物**：

| runtime | 实现文件 | 注册机制 |
|------|------|------|
| `python` | `handler.py` + `@directive` 装饰器 | handler_inits + importlib.reload 热加载 |
| `js` | `index.js` + `INSTRUCTIONS` map | exports.main 入口 |
| `cmd` | `whitelist.json` + `handler.py`（白名单校验） | whitelist_loader + subprocess.run |
| `mcp` | `service-descriptor.json`（无 handler.py） | mcp_dispatch 路由表 |
| `path` | 纯 JSON 声明（`type: "pipeline"`） | path_loader 注册 |
| `aggregate` | 纯 JSON 声明（`type: "aggregate"`） | aggregate loader |

**包生命周期**：install 时 schema.json 即时写入 handlers/schema/（query 立即可见），handler.py 经 importlib.reload 热加载（无需重启）→ 调用方通过 `AI:text-cli;query` 发现 → dispatch 执行 → uninstall 时完整回收文件、注册项和自建表。

### 6.4 脚手架转化器

项目提供转化器脚本，将既有软件工程制品转化为指令包起手骨架：

| 转化脚手架 | 脚本 | 输入 → 产出 |
|-----------|------|------------|
| webapi 指令包 | `postman_to_pkg_python.py` | Postman Collection → schema.json + handler.py |
| MCP 桥接包 | `mcp_to_pkg.py` | MCP server → schema.json + service-descriptor.json |

转化器产出的脚手架需要补充业务逻辑和错误处理后才能使用。完整指南见 [package-scaffolding-converter-guide_zh.md](../src/text_cli/base_text-cli/docs/package-scaffolding-converter-guide_zh.md)。

### 6.5 各运行时的指令包的开发指南入口

| 运行时 || 运行时 | 开发指南 |
|------|------|------|
| 标准| Python 运行时 | [package-python-dev-guide_zh.md](../src/text_cli/base_text-cli/docs/package-python-dev-guide_zh.md) |
| 标准| JS 运行时 | [package-js-dev-guide_zh.md](../src/text_cli/base_text-cli/docs/package-js-dev-guide_zh.md) |
| 其他| nocode（跨运行时） | [package-nocode-guide_zh.md](../src/text_cli/base_text-cli/docs/package-nocode-guide_zh.md) |
| 其他| 既有服务转化脚手架 | [package-scaffolding-converter-guide_zh.md](../src/text_cli/base_text-cli/docs/package-scaffolding-converter-guide_zh.md) |
| 其他| 指令包 分发规范 | [package-publish-guide_zh.md](../src/text_cli/base_text-cli/docs/package-publish-guide_zh.md) |


### 6.6 AI Agent 进阶辅助

Agent 通过 text-cli 自我管理能力自主扩展：

```
Agent 醒来 → /health → text-cli;query → 缺翻译能力
  → 借助'脚手架/指南'快速将需要转化为'指令包'
  → text-cli;install,xx-cloud → 安装指令包,新能力上线
  → "查天气→穿衣建议"反复出现 → text-cli;pro → 发布为路径
```

Agent 从调用者逐步变为管理者——不需要人配置路由、写部署文档。

---

## 标准运行时机制对照

Python 标准运行时实现了协议要求的 9 项必备机制（下表按**真实实现位置**标注——各机制的归属层与实现文件已经过源码核实，与"该机制最初在哪一层引入"一致；聚合降级的声明文件在 A8，但执行逻辑在 A3 dispatch 管道；门面抽象实现位于 A3 而非 A9，A9 仅提供配置与注册表）：

| 必备机制 | 实现层 | 实现位置 |
|------|:---:|------|
| 指令运行 | A3 | service/core/parser.py + core/registry.py |
| 安装及卸载指令包 | A3 | handlers/installer/ + handlers/text_cli_install.py / text_cli_uninstall.py |
| 指令的鉴权与发现 | A3/A5 | core/auth.py + handlers/schema_query.py |
| 路径编排 | A4 | handlers/path_executor.py |
| 异步任务调度 | A6 | handlers/task_manager.py |
| 聚合与降级链 | A3 执行 / A8 声明 | A3 service/main.py dispatch 管道 + A8 aggregate/*.json |
| 联邦 Mesh | A3（转发）/ A6（凭证注入） | handlers/proxy.py（转发）+ handlers/mesh_credentials.py（凭证注入器） |
| 协议桥 | A7 | handlers/mcp_handler.py + MCPservice/ |
| 门面抽象 | A9 | handlers/text_cli_pro.py + config/pro_registry.json |

---

## 附录：关键文件索引(基于python)

### 协议消费 SDK
- `src/skeleton/base/A0-protocol/python/call.py` — Python SDK：DirectiveResult + call/discover/poll/wait
- `src/skeleton/base/A0-protocol/js/call.js` — JavaScript SDK
- `src/skeleton/base/A0-protocol/shell/call.sh` — Bash CLI
- `src/skeleton/base/A0-protocol/shell/call.ps1` — PowerShell CLI

### AI 技能调度
- `src/skeleton/base/A1-skill/python/cli.py` — 编译路径：register() + generate_schema()
- `src/skeleton/base/A1-skill/python/skill.py` — 消费路径：Skill 类 + Skill.run() + 降级链
- `src/skeleton/base/A1-skill/python/aggregation.py` — sync_endpoints 端点能力聚合
- `src/skeleton/base/A1-skill/config/agent-endpoints.json` — 端点注册表（含 token，手动维护）
- `src/skeleton/base/A1-skill/config/agent-text-cli-schema.json` — 能力聚合清单（sync 生成）
- `src/skeleton/base/A1-skill/prompts/SKILL.md` — Agent 调度 System Prompt
- `src/skeleton/base/A1-skill/prompts/text-cli-core_zh.md` — 核心调度 v2.0
- `src/skeleton/base/A1-skill/prompts/text-cli-sync-skill.md` — 同步 Skill 概念设计
- `src/skeleton/base/A1-skill/prompts/agent-text-cli-schema.example.json` — 聚合 Schema 示例



### copilot
- `src/skeleton/copilot/A2-copilot/copilot/core.py` — 指令引擎
- `src/skeleton/copilot/A2-copilot/copilot/handlers/package_manager.py` — co-install/uninstall/list
- `src/skeleton/copilot/A2-copilot/copilot/whitelist_loader.py` — 白名单索引
- `src/skeleton/copilot/A2-copilot/copilot/handlers/skill_bridge.py` — 技能桥接
- `src/skeleton/copilot/A2-copilot/copilot/handlers/adapters.py` — 适配器
- `src/skeleton/copilot/A2-copilot/copilot/config/skill_bridge_routes.json` — 技能路由
- `src/skeleton/copilot/A2-copilot/copilot/auxiliary_config.json` — 安全策略

### service
- `src/skeleton/service/A3-service/service/core/parser.py` — prompt 解析
- `src/skeleton/service/A3-service/service/core/registry.py` — @directive 装饰器 + dispatch + `_ANCESTOR_CHAIN`（ContextVar 调用栈防环）+ `_make_ancestor_key` + `register_aggregate_domain`
- `src/skeleton/service/A3-service/service/main.py` — dispatch 管道 + 聚合降级
- `src/skeleton/service/A3-service/service/handlers/schema_query.py` — 指令查询
- `src/skeleton/service/A3-service/service/handlers/text_cli_install.py` — 安装
- `src/skeleton/service/A3-service/service/handlers/text_cli_uninstall.py` — 卸载
- `src/skeleton/service/A3-service/service/handlers/installer/validate.py` — 包校验
- `src/skeleton/service/A3-service/service/handlers/installer/filesystem.py` — 文件部署
- `src/skeleton/service/A9-advanced/service/config/handler_inits.py` — 启动注册表
- `src/skeleton/service/A4-paths/service/handlers/text_cli_path.py` — 路径引擎入口
- `src/skeleton/service/A4-paths/service/handlers/path_schema.py` — 路径声明校验
- `src/skeleton/service/A4-paths/service/handlers/path_loader.py` — 文件加载
- `src/skeleton/service/A4-paths/service/handlers/path_executor.py` — 执行引擎 + `_dispatch_step`（统一 step 派发器）+ `_execute_map`（map 循环执行）+ `_get_map_config`（惰性配置加载）+ `MAP_HARD_CAP=1000`
- `src/skeleton/service/A6-sql/service/handlers/key.py` — 密钥管理
- `src/skeleton/service/A6-sql/service/handlers/task_manager.py` — 任务管理
- `src/skeleton/service/A6-sql/service/handlers/quota_handler.py` — 配额管理
- `src/skeleton/service/A7-mcp/service/handlers/mcp_handler.py` — MCP 入向
- `src/skeleton/service/A7-mcp/service/core/mcp_dispatch.py` — MCP 路由
- `src/skeleton/service/A7-mcp/MCPservice/server.py` — FastMCP 出向
- `src/skeleton/service/A8-discovery/aggregate/map.json` — 聚合路由表
- `src/skeleton/service/A9-advanced/service/handlers/text_cli_pro.py` — 门面入口（含调用环早检：只查不推，与 dispatch 祖先链协同）
- `src/skeleton/service/A3-service/service/handlers/proxy.py` — 代理转发（统一入口：单跳默认，多跳跟随经 mesh.multi_hop_enabled 配置开启；纯管道，不持凭证逻辑）
- `src/skeleton/service/A6-sql/service/handlers/mesh_credentials.py` — Mesh 凭证注入器（per-peer + legacy all_keys）

### endpoint
- `src/skeleton/endpoint/A5-endpoint/python/main.py` — FastAPI 入口 + 安全中间件
- `src/skeleton/endpoint/A5-endpoint/python/core/backend_registry.py` — 多后端聚合
- `src/skeleton/endpoint/A5-endpoint/python/core/forwarder.py` — 转发 + 审计
- `src/skeleton/endpoint/A5-endpoint/python/core/ip_guard.py` — IP 黑名单
- `src/skeleton/endpoint/A5-endpoint/python/core/rate_limiter.py` — 限流
- `src/skeleton/endpoint/A5-endpoint/python/core/auth.py` — Token 校验

### 旁路运行时
- `src/skeleton/bypass-service/pypi/src/textcli_loader/loader.py` — 动态包加载
- `src/skeleton/bypass-service/pypi/src/textcli_loader/registry.py` — @directive 注册表
- `src/skeleton/bypass-service/pypi/src/textcli_loader/envelope.py` — 信封格式
- `src/skeleton/bypass-service/npm/textcli-core/parser.js` — JavaScript 协议解析器（与 Python 同构）
- `src/skeleton/bypass-service/npm/textcli-core/registry.js` — register/dispatch 注册表
- `src/skeleton/bypass-service/npm/textcli-core/loader.node.js` — Node.js 平台适配器
- `src/skeleton/bypass-service/npm/textcli-core/package.json` — npm 包配置（零外部依赖）
- `src/skeleton/bypass-service/cloudbase/config.js` — CloudBase 网关路由
- `src/skeleton/bypass-service/cloudbase/index.js` — CloudBase 入口
- `src/skeleton/bypass-service/cloudflare/workers/gateway.js` — Cloudflare Workers 网关（纯网关，复用 textcli-core 纯逻辑模块）

### 构建与部署
- `scripts/build-all.py` — 全量构建
- `scripts/release/win/build.py` — Windows 制品分发
- `scripts/release/win/build-endpoint.py` — Windows endpoint 制品分发
- `scripts/release/ubuntu/build.py` — Linux 制品分发

### 基础工具
- `src/skeleton/base/A1-skill/skill/cli.py` — 编译路径
- `src/skeleton/base/A1-skill/skill/skill.py` — 消费路径
- `src/skeleton/base/A1-skill/nocode/markdown_converter.py` — NoCode 路径
- `src/text_cli/base_text-cli/converter/postman_to_pkg_python.py` — Postman 转化器
- `src/text_cli/base_text-cli/converter/readme_to_pkg_python.py` — Markdown 转化器
- `src/text_cli/base_text-cli/converter/mcp_to_pkg.py` — MCP 转化器
