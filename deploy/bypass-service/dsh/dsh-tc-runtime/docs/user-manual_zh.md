# dsh-tc-runtime 使用手册

> 本手册面向 **dsh 操作者 / Agent**——你通过 dsh 驱动 text-cli（tc）指令能力时，读这一份即可。  
> 手册随 dsh-tc-runtime 插件分发。修订：2026-08-19。  
> 本插件基于 text-cli (MIT) 的**协议规范**工作，协议部分与 text-cli 完全一致（信封、错误码、指令语法零差异）。  
> 风格参考：`text-cli/docs/product_manuals/user-manual_zh.md`。

---

## 零、概念速览

dsh-tc-runtime 是**外挂于 dsh 的 Cordis 插件集**，把 text-cli（tc）的指令能力桥接进 dsh，使 dsh 的 Agent 能像调用原生工具一样调用 tc 指令包、path 管道、MCP 工具，并获得沙箱、凭据隔离、审批、审计、配额、聚合降级、mesh 转发等工程护栏。

它采取**旁路运行时**形态：只挂插件、不侵入 dsh 内核；九类机制（指令运行 / 指令发现 / 协议端点 / 沙箱 / 环检测 / 凭据隔离 / 审计 / 元指令 + 生命周期 / mesh 联邦）全部以插件层能力提供，不宣称"标准运行时"身份。

```
                        dsh（宿主）
   ┌──────────────────────────────────────────────────┐
   │  agent-loop / tools / sandbox / credentials / ...  │
   │                                                    │
   │   dsh-tc-runtime 插件集（旁路，零内核侵入）          │
   │   ┌──────────── 入站 ────────────┐                 │
   │   │ POST /text-cli/cli (loopback)│                 │
   │   │   → 解析 → 路由 → 执行 → 信封  │                 │
   │   └─────────────┬────────────────┘                 │
   │        ┌────────┴─────────┐  ┌──────────────────┐ │
   │        │ tc 指令包         │  │ 宿主指令 dsh-*     │ │
   │        │ (tc__<d>__<a>)    │  │ sandbox/cred/...  │ │
   │        ├──────────────────┤  ├──────────────────┤ │
   │        │ path 引擎         │  │ dsh-quota         │ │
   │        │ pro 门面          │  │ 审批 answerer     │ │
   │        ├──────────────────┤  ├──────────────────┤ │
   │        │ mcp 桥            │  │ mesh 转发         │ │
   │        │ (mcp__<s>__<t>)   │  │ (跨节点 delegated)│ │
   │        └──────────────────┘  └──────────────────┘ │
   └──────────────────────────────────────────────────┘
            统一协议：AI:<domain>;<action>,<params>
```

| 名词 | 含义 |
|------|------|
| **tc 指令** | 任意已安装的 text-cli 指令包，经桥接以 `tc__<domain>__<action>` 命名进入 dsh `ctx.tools` |
| **保留域元指令** | `text-cli;*`（install / uninstall / query / path / pro / export …），由插件直接拦截，不污染第三方命名空间 |
| **宿主指令** | `dsh-*`（沙箱 / 凭据 / 审批 / 日志 / 任务 / 技能目录），仅在插件侧执行 |
| **协议端点** | `POST /text-cli/cli`（主入口）+ `GET /text-cli/{health,skills,tasks/{id}}` |
| **信封** | 所有响应统一为 `{rst_types, rst_data, rst_err}`，与 text-cli 逐字节一致 |

**红线（7 条，操作者也受益）**：① 不侵入 dsh 内核；② 凭据明文不进 JS 执行环境；③ 沙箱默认拒绝未授权能力；④ 协议闭集（6 错误码 / 五态）；⑤ 保留域不污染 `ctx.tools`；⑥ 审批按归属过滤（dsh agent 审批不被外部 webhook 劫持）；⑦ 审计独立 JSONL，不写 `ctx.sessions`。

---

## 一、部署

dsh-tc-runtime 以 **profile** 方式挂载，不修改 dsh 任何内核文件。

### 1.1 挂载机制（profile 组合包）

`dsh-tc` profile = 组合包 **`[dsh-base, dsh-host-webserver, dsh-tc-runtime-bundle]`**。

- `dsh-host-webserver` 提供 `POST /text-cli/cli` 回环端点（webServer 例外实证：webServer 能力不被禁用）。
- `dsh-tc-runtime-bundle` 即本插件集。

同时 `cordis.patch.yml` 整行禁用 `agent` / `agent-default-model` / `llm` 三行（`Config | false`）——tc 运行时只提供指令执行能力，不接管 dsh 的对话/模型内核。

### 1.2 验证挂载

```bash
dsh --profile dsh-tc --dump-config
# 应看到：agent / agent-default-model / llm 三行被禁；dsh-tc-runtime 插件行在位
```

启动后健康检查：

```bash
curl http://127.0.0.1:<port>/text-cli/health
# → {"status":"ok","spec_version":"...","mechanism":"..."}
```

### 1.3 开发者：裸环境验证（无需 dsh 运行）

本仓库支持"裸开发"——只做静态验证，不依赖 dsh 运行环境：

```bash
pnpm install
pnpm -w typecheck     # tsc --noEmit（strict，零错误为门禁）
pnpm -w test          # vitest run（纯逻辑单测，278 passed / 29 files）
```

### 1.4 调用入口（统一协议）

所有指令经 dsh webServer 回环端点，协议与 text-cli 完全相同：

```bash
curl -X POST http://<host>:<port>/text-cli/cli \
  -H "Content-Type: application/json" \
  -d '{"prompt":"AI:<domain>;<action>,<param1>,<param2>,..."}'
```

> 字段名为 `prompt`（不是 `directive`）。所有响应都是统一信封（见 §三）。

---

## 二、指令表面

下面按命名空间列出 dsh 操作者/Agent 实际可用的指令。

### 2.1 tc 指令包（原生能力）

任意已安装的 text-cli 指令包，桥接后以 `tc__<domain>__<action>` 命名进入 `ctx.tools`，与 dsh 原生工具平权、可被 path / 聚合 / mesh 引用。

```bash
curl ... -d '{"prompt":"AI:tc-math;eval,2+3*4"}'
# → {"rst_types":"text","rst_data":{"status":"ok","result":14},"rst_err":""}
```

未安装对应包 → `ERR_NOT_FOUND`。

### 2.2 保留域元指令（`text-cli;*`）

由插件直接拦截处理，**不进入 `ctx.tools` 指令表**（红线⑤）。元指令含：

| 指令 | 作用 |
|------|------|
| `text-cli;install,<pkg>` | 安装指令包（解析 schema + handler → 注册 + 沙箱 policy + 凭据授权，返回 disposer） |
| `text-cli;uninstall,<pkg>` | 卸载（注册项 / 策略 / 凭据授权 / 文件全回收） |
| `text-cli;query[,json\|compact\|<kw>]` | 指令发现（按包分组 / 结构化 JSON / 紧凑 / 模糊搜索） |
| `text-cli;packages` | 列出已安装包 |
| `text-cli;path,<name>[,<input>]` | 执行命名 path（声明层管道，见 §2.6） |
| `text-cli;pro,<name>[,<input>]` | 门面简名调用（见 §2.7） |
| `text-cli;export,<pkg>` | 导出包源文件（不含私有策略） |
| `text-cli;export-all` | 导出全部包 |

> **`text-cli;path` 已实现**（2026-08-19，P0 接线点 A/B/C）——经 tc 口可执行命名 path，path 引擎 dispatch 桥接 dsh 工具表。

```bash
curl ... -d '{"prompt":"AI:text-cli;query,compact"}'
curl ... -d '{"prompt":"AI:text-cli;install,tc-math"}'
curl ... -d '{"prompt":"AI:text-cli;packages"}'
```

### 2.3 宿主指令（`dsh-*`）

仅运行在插件侧，经注入的 dsh 能力执行。**关键指令（sandbox / credential / approval）必经审批闸**——无审批通道时退化为 `deny`（`ERR_EXECUTION`）。形态 B 专属指令（`dsh-compact` / `dsh-subagent` / `dsh-memory` / `dsh-model`）不登记，返回 `ERR_NOT_FOUND`。

| 指令 | 作用 | 审批 |
|------|------|:---:|
| `dsh-sandbox;run,<...>` | 在受限沙箱执行 | 需 |
| `dsh-credential;get,<ref>` | 取用授权凭据（env 注入，明文不落 JS） | 需 |
| `dsh-approval;require,<reason>` | 发起一次人机审批；经闸后回传决策 | 自身即审批 |
| `dsh-log;analyze,<...>` | 日志分析 | 否 |
| `dsh-job;start,<...>` | 启动异步任务 | 否 |
| `dsh-job;poll,<task_id>` | 轮询异步任务五态 | 否 |
| `dsh-skill;catalog` | 技能目录 | 否 |

```bash
curl ... -d '{"prompt":"AI:dsh-credential;get,TC_OCR_KEY"}'
# 审批通过 → {"rst_types":"text","rst_data":{...},"rst_err":""}
# 无通道/被拒 → {"rst_types":"text","rst_data":{},"rst_err":"ERR_EXECUTION"}
```

### 2.4 配额（`dsh-quota;*`）

周期窗口 + 原子 check+consume；超限返回 `status:"stop"`（降级信号，非错误码）。周期：`day` / `week` / `month` / `year` / `forever`。

| 指令 | 作用 |
|------|------|
| `dsh-quota;register,<id>,<period>,<limit>` | 注册配额 |
| `dsh-quota;check,<id>` | 只读探测（超限 → `status:"stop"`） |
| `dsh-quota;reset,<id>` | 清零已用 + 重设窗口 |
| `dsh-quota;list` | 列出全部配额 |
| `dsh-quota;unregister,<id>` | 注销 |

```bash
curl ... -d '{"prompt":"AI:dsh-quota;register,my-svc,day,10"}'
curl ... -d '{"prompt":"AI:dsh-quota;check,my-svc"}'
# → {"status":"ok","remaining":9}
# 耗尽 → {"status":"stop","remaining":0}   # 聚合降级链据此自动切换提供方
```

### 2.5 审批工作流

关键宿主指令（sandbox / credential / approval）触发人机审批：

- 有通道且**允许** → 执行；
- 有通道但**拒绝 / 委托未决** → `deny`（`ERR_EXECUTION`）；
- **无通道** → `deny`（`ERR_EXECUTION`，ask 退化为 deny）。

审批回调（answerer）按 `req.agent` 归属过滤：**dsh agent 的审批永不被 tc webhook 劫持**（红线⑥）；未配置 webhook 时 ask 恒 deny；响应需 HMAC 签名且回显 `callId`；超时 / 不可达 / 非预期 → fail-closed 拒止；已应答 `callId` 设 TTL 防重放。

### 2.6 path 引擎（`text-cli;path,<name>[,<input>]`）

声明层解释器，将多条指令串成管道。数据单向流动——前步输出经插值注入后续步骤。每步都天然过护栏 / 审计 / 审批 / 凭据 / 环检测。

**插值语法**：`{var}`（调用参数）/ `{stepId.field}`（前步输出，支持深路径 `{geo.poi.0.name}`）；未定义 → 空串 + WARNING。

**步骤类型**：

| 类型 | 语义 |
|------|------|
| `call`（默认） | 单指令调用；`fallback:[{domain,action}]` 降级候选 |
| `sequence` | 顺序管线 |
| `parallel` | 并行，`strategy: first_ok`（首个成功）/ `all`（全收集） |
| `map` | 遍历数组（默认**关闭**，`enabled:true` 才执行；`MAP_HARD_CAP=1000`） |
| `if` | 条件分支（`equals` / `contains` / `matches` / `exists` / `all` / `any`） |
| `http_dispatch` | 跨节点派发（走信封，提取 `rst_data`） |
| `delegated` | 委托（无匹配指令**非 error**，继续） |

**降级**：步骤失败按 `fallback[]` 递补；全部失败返回 `DEGRADE_EXHAUSTED`（落到 `rst_data.status=error` + reason）。**嵌套深度上限 2**（`maxDepth`），超出 → `NESTING_EXCEEDED`。

```bash
curl ... -d '{"prompt":"AI:text-cli;path,pythagorean,{\"a\":3,\"b\":4}"}'
# → {"status":"ok","result":5.0}
```

### 2.7 pro 门面（`text-cli;pro,<name>[,<input>]`）

门面注册表把简名映射到 path / aggregate 目标，与原子指令平权。关键语义 **"只查不推"**：查询一个 pro 时，只把目标键（`path:<id>` / `agg:<name>`）放入祖先链，**不把 pro 自身键 push 进链**——根治多 path 复用同一 pro 时假报环检测的问题（R16）。

```bash
curl ... -d '{"prompt":"AI:text-cli;pro,calc,1+2+3"}'
# → {"status":"ok","result":6}
```

### 2.8 MCP 桥（`mcp__<server>__<tool>`）

挂载 mcp-client 后，MCP tool 自动注册进 `ctx.tools`，命名 `mcp__<server>__<tool>`，与 native 指令**平权**，可被聚合 / path 引用。`adapt_params` 双 adapter：

- `passthrough`：按 `paramNames` 顺序映射 `args[name] = params[i]`；
- `json_parse`：首参 JSON 解析 + 逗号重组 + `_raw` 兜底。

### 2.9 mesh 转发

本地不命中的指令，按路由表转发至对等 dsh 节点（Typert Remote / Connection RPC），回传为 `delegated` 信封：

- `visited` 防环（同 key 不重复转发）；
- `MAX_HOP_DEPTH=5` 跳数上限（超出 → `MESH_HOP_EXCEEDED`）；
- 指数退避重试 2 次（共 3 次尝试）；
- sensitive 脱敏（默认**关** → 不脱敏）；
- **凭证三原则**（默认**关**）：开启时 peer 隔离 + 标注 `_mesh_credential_degraded`，不前向凭据。

---

## 三、协议与信封

所有响应统一为信封（与 text-cli `textcli-core` 逐字节一致）：

```json
{"rst_types": "text", "rst_data": {"status":"ok","result":14}, "rst_err": ""}
```

- `rst_types`：响应类型。`text` / `picture` / `video` / `audio` / `file`。当 handler 返回含 `pray_rst_types` 键时，其值被提升至此字段。
- `rst_data`：handler 返回的 JSON 对象，骨架直接承载。
- `rst_err`：结构化错误字段。空串 `""` = 成功；非空 = 失败（见错误码）。

**错误码闭集（6 码）**：`ERR_NOT_FOUND` / `ERR_EXECUTION` / `ERR_ROUTING` / `INVALID_PARAMS` / `ACCESS_DENIED` / `SERVICE_DENIED`。未知码经 `textcli-core` 兜底回退 `ERR_EXECUTION`——**协议永不静默放行**。

**dsh→协议 全映射（16 行，契约测试覆盖）**：

| dsh 侧信号 | 协议码 | reason / 说明 |
|------|------|------|
| UNKNOWN_TOOL | `ERR_NOT_FOUND` | 工具未注册 |
| INVALID_ARGS | `INVALID_PARAMS` | 参数非法 |
| INVALID_TOOL_OUTPUT | `ERR_EXECUTION` | 工具输出不合法 = 执行失败 |
| TOOL_TIMEOUT / ABORTED | `ERR_EXECUTION` | 超时 / 中止归执行失败 |
| SandboxUnavailableError | `ERR_EXECUTION` | `SANDBOX_UNAVAILABLE` 基础设施故障 |
| 沙箱 policy 拒绝 | `ACCESS_DENIED` | 能力未授权 |
| 网络白名单拒绝 | `ACCESS_DENIED` | 出站域名未授权 |
| 审批 deny / unavailable | `ACCESS_DENIED` | 人机门拒绝 |
| 凭据授权映射未命中 | `ACCESS_DENIED` | 包取未授权凭据 |
| 凭据缺失（resolve 空值） | `SERVICE_DENIED` | 服务侧凭据不可用 |
| 跨终端鉴权失败 | `SERVICE_DENIED` | token 校验拒绝 |
| mesh 路由不可达 | `ERR_ROUTING` | 跨节点失败 |
| 祖先链命中（环检测） | `ERR_EXECUTION` | `CYCLE_DETECTED` 结构性拒绝，不触发审批 |
| 配额超限 | _(null)_ | 非错误：`rst_data.status="stop"` 降级信号 |
| 聚合降级链耗尽 | _(null)_ | `DEGRADE_EXHAUSTED`：`rst_data.status="error"` + reason |
| 未知 / 未列入 | `ERR_EXECUTION` | envelope.js 实证兜底 |

> 调用方规则：**直接读取 `rst_data`**；仅当 `rst_types="text"` 且数据恰为 `{"text": ...}` 形态时才取 `.text`，其余按内容类型映射直接使用 `rst_data`（`picture`/`video`/`audio`/`file` 取 `.url`）。

---

## 四、配置

### 4.1 挂载配置（profile）

`cordis.patch.yml` 禁用 `agent` / `agent-default-model` / `llm` 三行；`dsh-tc` profile 组合包 `[dsh-base, dsh-host-webserver, dsh-tc-runtime-bundle]`。部署者一般不改动。

### 4.2 审批 webhook

关键宿主指令的人机审批回调地址（answerer 出站）：`tcRuntime.approval.webhook_url`。请求携带 `agent` / `toolName` / `callId` / `reason` + HMAC 签名；响应须回显 `callId` 且带 `x-tc-response-signature`。未配置 → ask 恒 deny。

### 4.3 mesh 配置

| 项 | 默认 | 说明 |
|------|------|------|
| 跳数上限 `MAX_HOP_DEPTH` | `5` | 超出拒绝转发（`MESH_HOP_EXCEEDED`） |
| sensitive 脱敏 | `false` | `true` = 跨节点遮蔽 `secret/password/token/...` 值 |
| 凭证前向（凭证三原则） | `false` | `true` = peer 隔离 + `_mesh_credential_degraded`；`false` = 不前向凭据 |

### 4.4 配额

由 `dsh-quota;register` 动态建；周期窗口自动翻转（day/week/month/year/forever），`forever` 不翻转。

---

## 五、红线与安全

| # | 红线 | 操作者可见表现 |
|:---:|------|------|
| ① | 不侵入 dsh 内核 | 只挂插件；`agent-loop`/`core` 零 diff |
| ② | 凭据明文不进 JS 执行环境 | 凭据经 `CredentialRef` + env 白名单注入；包代码只读 `process.env` |
| ③ | 沙箱默认拒绝 | 非白名单能力即拒；沙箱未接入前默认拒绝真实包执行 |
| ④ | 协议闭集 | 仅 6 错误码 / 五态；未知码兜底 `ERR_EXECUTION`，不静默放行 |
| ⑤ | 保留域不污染 `ctx.tools` | `text-cli;*` 直接拦截，不进第三方命名空间 |
| ⑥ | 审批归属过滤 | dsh agent 审批不被 tc webhook 劫持；未配置恒 deny |
| ⑦ | 审计独立 JSONL | 事件写独立 JSONL（traceId + seq），不写 `ctx.sessions` |

**兜底原则**：任何未预见失败都走 `ERR_EXECUTION` 而非静默成功；审批/沙箱/凭据缺失在缺能力时一律 fail-closed 拒止。

---

## 附录

### A. 指令速查

| 命名空间 | 形态 | 示例 |
|------|------|------|
| tc 指令包 | `tc__<domain>__<action>` | `AI:tc-math;eval,2+3*4` |
| 保留域 | `text-cli;<action>` | `AI:text-cli;query,compact` |
| 宿主指令 | `dsh-<cap>;<action>` | `AI:dsh-credential;get,TC_OCR_KEY` |
| 配额 | `dsh-quota;<action>` | `AI:dsh-quota;check,my-svc` |
| path | `text-cli;path,<name>` | `AI:text-cli;path,pythagorean,{"a":3,"b":4}` |
| pro 门面 | `text-cli;pro,<name>` | `AI:text-cli;pro,calc,1+2+3` |
| mcp 桥 | `mcp__<server>__<tool>` | `AI:mcp__github__search_repos,text-cli` |
| mesh | 自动转发 | 本地不命中 → 路由表 peer |

### B. 错误码速查

| 错误码 | 含义 | 常见场景 |
|--------|------|---------|
| `ERR_NOT_FOUND` | 指令不存在 | 未安装对应指令包 |
| `ERR_EXECUTION` | 执行失败 / 环检测 / 沙箱不可用 / 审批 deny / 兜底 | handler 异常、结构拒绝 |
| `ERR_ROUTING` | 路由失败 | mesh 目的地不可达 |
| `INVALID_PARAMS` | 参数不合法 | 必填缺失或格式错误 |
| `ACCESS_DENIED` | 能力/凭据/审批未授权 | 沙箱拒、网络拒、审批拒 |
| `SERVICE_DENIED` | 服务侧明确拒止（非配额耗尽） | 凭据缺失、跨终端鉴权失败 |

> 配额耗尽走 `rst_data.status="stop"` 降级链，不返回 `SERVICE_DENIED`。

### C. 环境变量 / 端点

| 项 | 说明 |
|------|------|
| `POST /text-cli/cli` | 主指令入口（body `{"prompt":"AI:..."}`） |
| `GET /text-cli/health` | 健康检查（status / spec_version / mechanism） |
| `GET /text-cli/skills` | 已注册指令白名单（对外暴露面） |
| `GET /text-cli/tasks/{task_id}` | 异步任务五态查询；`task;cancel` 经 `ctx.jobs.kill` |
| `tcRuntime.approval.webhook_url` | 审批回调地址（answerer 出站） |

### D. 构建 / 验证命令

```bash
pnpm install           # 重建 @dsh-tc/* 软链（ubuntu）
pnpm -w typecheck     # tsc --noEmit（strict 零错误门禁）
pnpm -w test          # vitest（278 passed / 29 files）
pnpm -w test --coverage # 覆盖门禁（目标 100%，dsh CI）
```

> 当前进度（2026-08-28）：Phase 0~11 全部 ✅（`runtime-phase` 已按规划移除）；本环境静态验证通过。dsh 联调 / 覆盖门禁 / A9 对测待 ubuntu 收尾。
