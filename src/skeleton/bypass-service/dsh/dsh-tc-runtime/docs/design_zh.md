# dsh-tc-runtime 设计文档

> 本文档基于 **真实实现**（15 包、~5000 行 `src`、单测通过、commit `2d0b347`+`18b18ff`）撰写，结构对齐 `text-cli/docs/design_zh.md`。
> 凡「设计约定」与「落地实现」一致处直接记实现；凡实现较设计稿有**细化/加固**处，以「实现注」标注。
> 验证状态：本环境 `tsc --noEmit` 零错误 + `vitest` 通过；**dsh 联调/集成测试待 ubuntu 环境**（见附录 C）。

---

## 一、协议机制

dsh-tc-runtime 不重新发明协议，而是**复用 `textcli-core` 信封**（parser / envelope / alias / registry / loader），把 tc/text-cli 指令经 HTTP loopback 桥接进 dsh。协议闭集是红线④的承载面。

### 1.1 响应信封

信封三字段（与 text-cli 完全一致，零重写）：

```ts
interface Envelope {
  rst_types: string;   // 结果类型（可经 pray_rst_types 提升）
  rst_data: unknown;   // 结果体
  rst_err: string;     // 错误码（空串=成功），落在 6 码闭集
}
```

- `tc.ok(result)` / `tc.err(code, reason)` / `tc.parse(prompt)` 全部来自 `textcli-core`。
- `pray_rst_types`：调用方可前置声明期望的 `rst_types`，envelope 提升后回填。
- **实现注**：`runtime-contract` 与 `runtime-inbound` 均直接 `import tc from "textcli-core"`，并用契约测试断言 `ok(d) === tc.ok(d)`（逐字段一致）。这是「协议零重写」的硬证据，也是防止 tc 侧悄摸偏离 text-cli 真源的回归闸。

### 1.2 错误码闭集

协议错误码固定 6 个（SPEC §1.2.8），任何 dsh 侧信号必须落到此闭集，否则回退 `ERR_EXECUTION`：

```ts
export const ERROR_CODES = [
  "ERR_NOT_FOUND",   // 工具未注册 / 无匹配指令
  "ERR_EXECUTION",   // 执行失败（含超时/中止/环命中/未知兜底）
  "ERR_ROUTING",     // 跨节点路由不可达
  "INVALID_PARAMS",  // 参数非法
  "ACCESS_DENIED",   // 能力未授权 / 人机门拒绝
  "SERVICE_DENIED",  // 服务侧不可用（凭据缺失/鉴权失败）
] as const;
```

**dsh→协议 全映射表（16 行，本身即契约测试用例）**：

| # | dsh 侧信号 | 落地码 | 显式 reason | 说明 |
|---|---|---|---|---|
| 1 | `UNKNOWN_TOOL` | `ERR_NOT_FOUND` | — | 工具未注册 |
| 2 | `INVALID_ARGS` | `INVALID_PARAMS` | — | 参数非法 |
| 3 | `INVALID_TOOL_OUTPUT` | `ERR_EXECUTION` | — | 工具输出不合法=执行失败 |
| 4 | `TOOL_TIMEOUT`/`ABORTED`/`ABORTED_BEFORE_DISPATCH` | `ERR_EXECUTION` | — | 超时/中止归执行失败 |
| 5 | `SandboxUnavailableError` | `ERR_EXECUTION` | `SANDBOX_UNAVAILABLE` | 沙箱基础设施故障 |
| 6 | 沙箱 policy 拒绝（非白名单能力） | `ACCESS_DENIED` | — | 能力未授权 |
| 7 | 网络白名单拒绝 | `ACCESS_DENIED` | — | 出站域名未授权 |
| 8 | 审批 deny / unavailable（fail-closed） | `ACCESS_DENIED` | — | 人机门拒绝 |
| 9 | 凭据授权映射未命中 | `ACCESS_DENIED` | — | 包取未授权凭据 |
| 10 | 凭据缺失（resolve 空值） | `SERVICE_DENIED` | — | 服务侧凭据不可用 |
| 11 | 跨终端鉴权失败 | `SERVICE_DENIED` | — | token 校验拒绝 |
| 12 | mesh 路由不可达 / 转发失败 | `ERR_ROUTING` | — | 跨节点失败 |
| 13 | 祖先链命中（环检测 §2.4） | `ERR_EXECUTION` | `CYCLE_DETECTED` | 结构性拒绝，不触发审批 |
| 14 | 配额超限 | `null` | — | **非错误**：`rst_data.status=stop` 降级信号 |
| 15 | 聚合降级链耗尽 | `null` | `DEGRADE_EXHAUSTED` | `rst_data.status=error` + reason |
| 16 | 未知/未列入 | `ERR_EXECUTION` | — | envelope.js 实证兜底 |

```ts
export function mapSignal(signal: string): ReturnType<typeof tc.err> {
  const row = ERROR_MAP.find((r) => r.signal === signal && r.code !== null);
  if (!row || row.code === null) return tc.err("ERR_EXECUTION", signal);
  return tc.err(row.code, row.reason ?? signal);
}
```

**实现注**：第 14/15 行 `code: null`——配额超限与降级耗尽**不是错误**，而是走 `rst_data.status` 的降级信号（stop / error+reason），避免污染 6 码闭集的同时给调用方结构化语义。

### 1.3 异步任务五态

聚合/异步任务桥接采用五态机（基于 `runtime-aggregate` 的 `AsyncJobBridge`）：

```
pending ──start──▶ running ──succeed──▶ done
                       │
                       ├──fail──▶ error
                       └──cancel(仅 running)──▶ cancelled
```

- 任务标识：`task_id = ${domain}-${action}-${seq}`。
- **重启残留对账**（`reconcileAfterRestart`）：进程重启后未终态任务 → `error` + reason `service_restarted`。
- `poll(taskId)` 返回 `JobRecord & { state }`；未命中返回 `state: "not_found"`。
- **实现注**：`cancel` 仅在 `running` 态生效（终态不可 cancel，返回 `false`），与「终态不可变」语义一致。

---

## 二、运行时体系

dsh-tc-runtime 是一个 **15 包 monorepo 插件**（`@dsh-tc/*`），仅挂插件、不改 dsh 内核（红线①）。核心设计原则：**纯逻辑核心 + 依赖注入（deps 模式）**，不耦合 dsh `ctx`（R10/R17），从而本环境可做静态验证 + 纯逻辑单测，dsh 联调后移 ubuntu。

### 2.1 包分类（按职责分层）

| 层 | 包 | 职责 |
|---|---|---|
| **接入层** | `runtime-inbound` | 入站六段管道（解析→路由→执行→信封→审计） |
| | `runtime-mapper` | `tcToDsh`/`dshToTc` 翻译 + `query` 发现 |
| **安全护栏** | `runtime-sandbox` | 祖先链环检测 + 单守卫 + 沙箱策略 + 执行宿主 |
| | `runtime-credentials` | 凭据授权映射 + resolve 链（明文不进包） |
| | `runtime-audit` | 独立 JSONL 审计 trace 模型 |
| | `runtime-approval` | 审批 answerer（归属过滤/HMAC/防重放/fail-closed） |
| **调度/编排** | `runtime-path` | path 声明层解释器（8 类步骤）+ workflow 编译 |
| | `runtime-aggregate` | 聚合 try-in-order 降级 + 异步任务桥 |
| | `runtime-mesh` | mesh 跨节点转发 + 防环 + 退避 |
| | `runtime-pro` | 门面 pro（只查不推，R16） |
| | `runtime-host` | 宿主指令表面（6 指令 + 审批闸 gate） |
| | `runtime-quota` | dsh-quota 窗口 + 原子 check+consume |
| **协议桥** | `runtime-bridge` | mcp-client 协议桥（`mcp__<s>__<t>` + 双 adapter） |
| **契约/验收** | `runtime-contract` | 协议信封 + 16 行映射 + 双运行时一致契约 |
| | `runtime-meta` | 元指令表面 + 包注册/安装器 |

### 2.2 装配与解耦

- `pnpm` workspaces；包间经 `@dsh-tc/<name>` 互引。
- **所有跨切面依赖以 `deps` 注入**：`dispatch`/`audit`/`requireApproval`/`sandbox`/`credentials`/`now`/`httpPost`/`hmacSign` 等。实现不 `import` dsh 运行时，仅消费注入契约。
- **裸环境解耦**：Windows 管理员禁用 `mklink`，本环境改用 `vitest.config.ts` alias + `tsconfig.json` paths 把 `@dsh-tc/*` 解析到实时 `src/index.ts`（ubuntu 改用 pnpm 真实软链，见附录 C）。

### 2.3 当前形态

- 15 包全部实现，全仓 `src` 搜 `TODO/FIXME/stub` **0 命中**。
- `tsc --noEmit` 零错误；`vitest` 通过。
- commits：`2d0b347`（Phase 7–11）+ `18b18ff`（测试对齐）。
- **tc path 接入 + 生态分流**：path 引擎接入 tc 口（接线点 A/B/C），入站生态归属分流（ecosystem），tc path→dsh workflow 编译（workflowCompiler）。`runtime-phase` 已按规划移除。
- **未验面**：沙箱真实拒绝、HTTP 端点 serve、profile 挂载、凭据 env 注入、answerer 真实 HMAC 往返、mesh 跨节点传输——均在 ubuntu 联调才验。

---

## 三、消费侧——从 dsh 到 tc 指令

### 3.1 统一协议入口（裸 HTTP loopback）

dsh agent 经统一 HTTP 端点向 tc 运行时发指令，格式 `tc__<domain>__<action>`（双下划线命名，对齐 mcp-client 实证）。入站处理即 `runtime-inbound` 六段管道：

```ts
async function handlePrompt(prompt, deps, opts): Promise<Envelope> {
  const trace = new TraceSession(opts.traceId);
  await audit("inbound", { prompt });

  // ① 解析（复用 textcli-core parser）
  const mapped = tcToDsh(prompt);
  if (!mapped.ok) return mapped.envelope;          // 解析失败→信封错误

  // ② 路由：text-cli 保留域直接拦截（元指令表面）
  if (mapped.domain === "text-cli") return deps.meta?.(...);

  // ③ 执行：注入的 dispatch（沙箱未接入前拒绝真实包）
  try { result = await deps.dispatch(mapped.input); }
  catch (e) {
    if (e instanceof CycleDetectedError)
      return tc.err("ERR_EXECUTION", `CYCLE_DETECTED: ${e.key}`); // 环→结构性拒绝
    return tc.err("ERR_EXECUTION", String(e));
  }
  if (result == null) return tc.err("ERR_NOT_FOUND", `no matching directive`);

  // ⑤ 信封（复用 envelope.js）
  return tc.ok(result);
}
```

### 3.2 指令发现（query 元指令）

`text-cli;query[,json|compact|<关键词>][,zh|en]` 返回 `directives[]`（平权：native 指令 + mcp 桥 + pro 门面同形暴露）：

```ts
handleQuery(params, { directives })  // params: query / query,json / query,<keyword> / 尾参 ,zh|,en
// 数据源注入：ubuntu 联调接 ctx.tools.schemas() → buildDirectives
```

### 3.3 智能调度层

**(a) path 声明层**（`runtime-path`）——声明式编排，8 类步骤：

| 步骤 | 语义 |
|---|---|
| `call` | 单调用 + `fallback` 候选递补（全失败→`DEGRADE_EXHAUSTED`） |
| `sequence` | 顺序执行，返回末步 |
| `parallel` | `first_ok`（首个成功）/ `all`（全集） |
| `map` | 遍历数组（默认开，`MAP_HARD_CAP=1000` 硬上限，`on_error` stop/skip） |
| `if` | 四形式条件分支 |
| `http_dispatch` | 跨节点派发（`extract_rst_data`） |
| `delegated` | 无匹配指令**非 error**（返回 `{delegated:false}`） |

- 变量插值两层：`{var}` / `{stepId.field}`，未定义→空串 + WARNING。
- 嵌套深度 `DEFAULT_MAX_DEPTH=2`，超限 `NESTING_EXCEEDED`。
- `get_final_output`：反向找最后一个非空输出。

**(b) 聚合降级**（`runtime-aggregate`）——指令路由层 try-in-order：

```ts
aggregate(name, candidates, params, deps):
  if ancestorChain.contains(`agg:${name}`) → throw CycleDetectedError  // 环检测
  if last param matches /^provider:(.+)$/ → 只走该候选（显式 provider）
  if quota.check(name).status == "stop" → 返回 stop 信封（降级信号）
  if approval → 整链一次决策（防风暴）
  for c in candidates: r = dispatch(c); if !isError && !isStop → return r
  return DEGRADE_EXHAUSTED
```

**(c) mesh 转发**（`runtime-mesh`）——跨节点：

```ts
meshRoute(domain, action, params, deps, ctx):
  if localHas(domain, action) → dispatch locally          // 本地命中，不跨节点
  key = `${domain};${action}`
  if ctx.visited.has(key) → throw MeshCycleError          // visited 防环
  if ctx.hop > MAX_HOP_DEPTH(5) → throw MeshHopExceeded   // 跳数上限
  peer = routeTable.find(domain) ?? routeTable[0]
  out = desensitize(params, ctx.sensitive)                // 敏感参数脱敏（默认关）
  for attempt in 0..RETRIES(2):                           // 指数退避 2 次，共 3 尝试
    try return await remote(peer, ...)
    catch: await backoff(attempt)                         // 50ms → 100ms
```

- `credentialForwardPolicy(ctx)`：默认 `forward:false`（凭证三原则——不前向），开启时标记 `degraded`。
- **实现注**：脱敏/凭证前向默认关，属「默认安全」；开启需显式配置且跨节点隔离。

**(d) pro 门面**（`runtime-pro`）——R16「只查不推」：

```ts
proAncestorKey(name, reg) →
  t.kind === "path" ? `path:${t.pathId}` : `agg:${t.aggName}`   // 返回【目标】key
```

**实现注**：pro 是别名解析器（短名→path/aggregate 目标），**非执行栈成员**。若把 `pro:<name>` 自身推入祖先链，会被多 path 复用而假报环——故采用「只查不推」：进入时查目标 key 是否已在链（防 pro→pro 互环），但**不占位**，实际 push 的是被解析出的目标，由其守卫负责。这是对设计稿 R16 的显式细化。

### 3.4 dsh Agent 集成全景（红线 7 条）

| # | 红线 | 承载实现 |
|---|---|---|
| ① | 不侵入 dsh 内核 | 仅挂插件，零改 `agent-loop`/`core` |
| ② | 凭据明文不进 JS 执行环境 | `CredentialRef` + env 白名单注入（§5.2） |
| ③ | 沙箱默认拒绝 | 非白名单能力即拒；沙箱未接入前默认拒绝真实包 |
| ④ | 协议闭集 | 6 错误码 / 三字段信封 / 五态（§1） |
| ⑤ | 保留域不污染 `ctx.tools` | `text-cli;*` 元指令经 `runtime-inbound` 拦截 |
| ⑥ | 审批 answerer 归属过滤 | `req.agent` 存在→委托，dsh agent 审批不被 tc webhook 劫持 |
| ⑦ | 审计独立 JSONL | `runtime-audit` 自建通道，不写 `ctx.sessions` |

---

## 四、标准运行时——dsh 插件核心

### 4.1 组件拓扑

```
[dsh-base]              基础 agent loop + ctx 注入
   ├── [dsh-host-webserver]   HTTP 端点（统一协议入口）
   └── [dsh-tc-runtime-bundle]  ← 本插件组合包
            ├─ runtime-inbound (六段管道)
            ├─ runtime-mapper (发现/翻译)
            ├─ runtime-sandbox (环检测/单守卫/策略)
            ├─ runtime-credentials (凭据隔离)
            ├─ runtime-approval (审批)
            ├─ runtime-quota (配额)
            ├─ runtime-path/aggregate/mesh/pro/host (调度)
            ├─ runtime-bridge (mcp 桥)
            ├─ runtime-contract (契约)
            └─ runtime-meta (生命周期)
```

- **承载边界**：宿主特权包（`tc-ubuntu`/`copilot`，`host-privileged` 类）**排除**，不属本运行时（§4.2 `policyForPackage` 返回 `null`）。
- **检测点收敛**：所有经 `ctx.tools.execute` 的执行（path step / 聚合 provider / native / 宿主指令）统一经 `guardDispatch` 进链，环命中即结构性拒绝（不触发审批）。

### 4.2 渐进分层体系（沙箱三档 + 7 类包）

沙箱模式对齐 dsh `SandboxMode` 三档：

```ts
type SandboxMode = "read-only" | "workspace-write" | "danger-full-access";
```

包能力 7 分类 → 策略（`policyForPackage`，纯函数）：

| 包类型 | 示例 | mode | network | env |
|---|---|---|---|---|
| `pure` | tc-math/json/diff | read-only | 无 | 无 |
| `network` | weather（双源免密降级） | read-only | 域名白名单 | 无 |
| `config-inject` | ai-inference（供应商/模型经配置注入） | read-only | 无 | 凭据名 |
| `network-credential` | bd-map/gd-map/tx-map/bd-cloud | read-only | 域名白名单 | 凭据名 |
| `file-io` | tc-markdown/archive（路径白名单 + zip bomb 防御） | workspace-write | 无 | 无 |
| `image` | image（Pillow） | workspace-write | 无 | 无 |
| `host-privileged` | tc-ubuntu/copilot | **排除（null）** | — | — |

- 网络白名单：精确匹配 + 子域后缀（`isNetworkAllowed`）。
- env 白名单：键精确匹配（`isEnvKeyAllowed`）。

### 4.3 源码结构

```
dsh-tc-runtime/
├── package.json            # pnpm workspaces + 脚本（typecheck/test）
├── tsconfig.json          # baseUrl + @dsh-tc/* explicit paths
├── vitest.config.ts       # alias + .vitest-cache（避免写 node_modules）
├── runtime-inbound/src/   # handler.ts（六段管道）
├── runtime-mapper/src/    # tcToDsh.ts / dshToTc.ts / query.ts
├── runtime-sandbox/src/   # ancestor-chain.ts / guard.ts / policy.ts / executor.ts / sandbox-provider.ts / runner.cjs
├── runtime-credentials/src/ # grant.ts / resolver.ts / credential-source.ts
├── runtime-audit/src/     # trace.ts / jsonl.ts
├── runtime-approval/src/  # answerer.ts / types.ts
├── runtime-quota/src/     # store.ts / period.ts / types.ts
├── runtime-path/src/      # executor.ts / interpolate.ts / conditions.ts / types.ts
├── runtime-aggregate/src/ # aggregate.ts / jobs.ts / types.ts
├── runtime-mesh/src/      # mesh.ts / types.ts
├── runtime-pro/src/       # pro.ts / types.ts
├── runtime-host/src/      # host.ts / types.ts
├── runtime-bridge/src/    # bridge.ts / types.ts
├── runtime-contract/src/  # error-codes.ts / envelope.ts / index.ts
├── runtime-meta/src/      # meta.ts / registry.ts / installer.ts
└── docs/                  # design_zh.md / user-manual_zh.md / 进度报告
```

### 4.4 部署

```
# 1. ubuntu 环境重建 @dsh-tc/* 真实软链
pnpm install

# 2. 挂载 profile 组合包（禁用 dsh 原生三行，避免能力重叠）
#    cordis.patch.yml：注释/移除 dsh 原生 [tc-host / webserver / quota] 三行

# 3. health 验证
curl <loopback>/health   # 期望 200 + tc 运行时就绪

# 4. 统一协议入口
POST <loopback>/dispatch  body: { "prompt": "tc__weather__query,北京" }
```

### 4.5 实现细节（关键机制）

**(1) 环检测**（`runtime-sandbox/ancestor-chain.ts`）：

- `AsyncLocalStorage` 实现，沿 promise 链自动传播（parallel 分支天然继承，无需手动 copy）。
- 三键：`path:<id>` / `agg:<name>` / `native:<domain>;<action>`。
- 链长上限 `MAX_CHAIN=32`（防御病态链式输入）。
- 三断点：A 任务恢复 `snapshot()`/`restore()`；B 沙箱子进程（边界声明——包只能经注入通道回宿主请求，检测统一在宿主侧单守卫）；C 宿主指令互调（`native:<d>;<a>` 亦进链）。
- 单守卫 `guardDispatch(fn, keyFor)`：push→execute→finally pop；环命中→`CycleDetectedError`→映射 `ERR_EXECUTION + CYCLE_DETECTED`（**不触发审批**）。

**(2) 审批 answerer**（`runtime-approval/answerer.ts`）——覆盖 6 类威胁：

| 威胁 | 处置 |
|---|---|
| 归属劫持（红线⑥） | `req.agent` 存在→立即 `delegate`（返回 `{decided:false}`，不替 dsh agent 决策） |
| 重放 | 已应答 `callId`（TTL 300s 内）直接返回缓存决策 |
| 未配置 | 无 webhook/secret→恒 `deny`（fail-closed） |
| 伪造请求 | 请求体双向 HMAC（`X-Tc-Signature`） |
| 伪造/串线响应 | 响应回显 `callId` 校验 + `x-tc-response-signature` 签名校验 |
| 超时/不可达 | `withTimeout`（默认 5s）→ fail-closed（deny + unavailable） |

**(3) 配额**（`runtime-quota/store.ts`）：

- 周期 `day/week/month/year/forever`（UTC 窗口，`windowFor`/`needsFlip`）。
- `consume(id, n)`：**原子 check+consume**（读改写在单函数内，无中间 await；多进程由 `StorageKV` 实现层保证原子，内存实现天然原子）。
- 超限→`status:"stop"`（不扣减），供聚合层做降级信号。

**(4) 审计**（`runtime-audit/trace.ts`）——独立 JSONL：

- `traceId = tc-<epochMs>-<rand6>`；每入站请求一个 `TraceSession`，事件携带 `traceId + 递增 seq`。
- 8 类事件：`inbound`/`parse`/`route`/`tool-exec`/`credential`/`sandbox-deny`/`approval`/`envelope`。
- 按 `traceId` 归组 + `seq` 排序可重建全链路；**不写 `ctx.sessions`**（红线⑦）。

---

## 五、宿主执行 / 旁路运行时

### 5.1 沙箱执行宿主

- `runtime-sandbox` 提供 `executor.ts` + `sandbox-provider.ts` + `runner.cjs`（实际子进程执行载体）。
- **默认拒绝语义**：非白名单能力即拒；沙箱未接入前，入站管道第三步 `dispatch` 仅 mock 直通，真实包执行被拒（红线③）。
- 宿主指令（`runtime-host/host.ts`）六指令：`dsh-sandbox;run` / `dsh-credential;get` / `dsh-approval;require` / `dsh-log;analyze` / `dsh-job;start,poll` / `dsh-skill;catalog`。
- 关键指令（sandbox/credential/approval）必经 **审批闸 `gate`**：
  - 有通道且允许→执行；
  - 有通道但拒绝/委托未决→`ERR_EXECUTION`；
  - **无通道→`ERR_EXECUTION`（ask 退化 deny，fail-closed）**。
- 形态 B 专属（`compact`/`subagent`/`memory`/`model`）不登记→`ERR_NOT_FOUND`。

### 5.2 凭据隔离（凭证三原则）

```
grant (TC_ 前缀命名) ──▶ resolver (授权映射→配额→source.resolve→env 注入) ──▶ 受限沙箱执行环境
```

- **ref 即环境变量名**：`schema.credentials` 声明 `name` → `toRefName` → `TC_<NAME>`（大写 + 非字母数字转 `_`）。双凭据（key+secret）拆成两个独立 grant（对齐 dsh 单值模型）。
- **授权映射第一防线**（B5）：`isGranted(pkg, ref)` 保证包物理上拿不到别的包凭据（ACCESS_DENIED）。
- **resolve 链**（`resolveForPackage`）：
  1. 授权映射校验 → `ACCESS_DENIED`
  2. 配额接口预留（Phase 8 接 dsh-quota）→ `QUOTA_STOP`
  3. `source.resolve(ref)` → 空值 `SERVICE_DENIED`
  4. 注入 `env: { [ref]: value }`（仅包声明的 ref）
  5. 每次取用写审计（独立 JSONL）
- **明文不进包源码**：handler 读 `process.env[ref]` 零改动；明文仅在受限执行环境 env 注入时存在，绝不进入 JS 执行上下文（红线②）。

---

## 六、指令包设计

### 6.1 指令命名

| 形态 | 命名 | 说明 |
|---|---|---|
| tc 原生 | `tc__<domain>__<action>` | 双下划线，对齐 mcp-client |
| 保留域元指令 | `text-cli;<action>` | `query`/`pro,<name>` 等，经 inbound 拦截，不污染 `ctx.tools`（红线⑤） |
| mcp 桥 | `mcp__<server>__<tool>` | 双下划线，与 native 平权 |
| 宿主指令 | `dsh-<cap>;<action>` | 经 `gate` 审批闸 |

### 6.2 保留域与 pro 门面

- `text-cli;*` 全域由 `runtime-inbound` 路由拦截，进入 `runtime-meta` 的元指令表面（`handleMeta`）。
- `pro` 门面：`text-cli;pro,<name>` 经保留域拦截解析（R16 只查不推），目标为 `path:<id>` 或 `agg:<name>`，与原子指令同形暴露。

### 6.3 mcp 协议桥（`runtime-bridge`）

- 工具名 `mcpToolName(server,..) = mcp__${server}__${tool}`。
- `McpBridge.mount(def)`：注册进 `ctx.tools`（经注入 `register` 回调，返回 disposer）→ 产 `directive`（domain:`mcp`，action:`${server}__${tool}`），平权并入 `directives[]`。
- **双 adapter**（`adaptParams`）：
  - `passthrough`：按 `paramNames` 顺序映射 `args[name]=params[i]`；参数声明缺失兜底 `{_params: params}`。
  - `json_parse`：首参 `JSON.parse` → 失败试 `params.join(",")` → 再失败 `{_raw: params[0]}`。

```ts
const def = { server: "github", tool: "search", adapter: "json_parse",
              paramNames: ["q"], description: "search repos" };
registerMcpTool(def, register);  // → 工具 mcp__github__search，与 native 平权发现
```

### 6.4 包生命周期（`runtime-meta`）

- `meta.ts`：元指令表面（元数据查询/注册/安装）。
- `registry.ts`：已装包注册表（包↔指令/凭据声明映射）。
- `installer.ts`：安装/卸载（effect-scoped，经注入通道操作 `ctx.tools`）。

### 6.5 开发指南入口

各包 `test/*.test.ts` 即「可运行规格」：
- 环检测 / 单守卫：`runtime-sandbox`
- 审批 6 威胁 / 重放 / 归属：`runtime-approval`
- 配额窗口 / 原子消费 / 翻转：`runtime-quota`
- path 8 步骤 / 降级 / 并行 / map：`runtime-path`
- 聚合 try-in-order / provider / quota stop：`runtime-aggregate`
- mesh 防环 / hop / 退避 / 脱敏：`runtime-mesh`
- 协议 16 行映射 / 双运行时一致：`runtime-contract`
- mcp 双 adapter / 平权：`runtime-bridge`
- 凭据三原则 / 授权映射第一防线：`runtime-credentials`
- 审计 trace 重建：`runtime-audit`
- 生态归属分流：`runtime-inbound`（`ecosystem.ts`）

---

## 七、tc path 引擎接入与生态分流（P0/P8/P9）

> `runtime-phase` 已按规划移除，规划层不再内置；下述 path 接入点、生态分流、workflow 编译为留在插件集内的独立能力（不依赖 runtime-phase）。

### 7.1 P0：path 引擎接入 tc 口（接线点 A/B/C）

- **接线点 A**：`runtime-inbound/src/pathBridge.ts` 组装 `createMetaWithPath`（注入 `HandlerDeps.meta`）
- **接线点 B**：`runtime-meta` 的 `path` 分支调注入的 `runPath`（依赖注入避免循环依赖）
- **接线点 C**：`buildPathDeps` 把 path 三参 → `ToolExecutionInput`（`tc__<domain>__<action>`）
- **信封→闭集**：读 `rst_data.status` 三态 + 6 码闭集（红线④）

### 7.2 P8：入站生态归属分流

`runtime-inbound/src/ecosystem.ts` 提供结构化归属映射（不依赖 LLM）：
- `classifyDomain`：dsh 宿主域 / tc 指令域 / unknown
- `classifyDirective`：未知域默认 tc（开放注册）
- `classifyPathOwnership`：全 dsh / 全 tc / mixed（混合由 tc path 串接）
- handler 加 `route` 注入点（调用方做分流，默认行为不变）

### 7.3 P9：tc path → dsh workflow 编译

`runtime-path/src/workflowCompiler.ts`：`compileToWorkflow(def)` 把 tc path JSON **编译成 dsh workflow JS 脚本**（`run/agent/pipeline/parallel/evalCondition` hooks）。语义同构处无损翻译；`map`/`http_dispatch`/`delegated`/`if` 等**显式 LOSSY 标注**（翻译纪律，不静默）。

---

## 附录 A：关键文件索引（基于实现）

| 主题 | 文件 |
|---|---|
| 入站六段管道 | `runtime-inbound/src/handler.ts` |
| 翻译/发现 | `runtime-mapper/src/{tcToDsh,dshToTc,query}.ts` |
| 环检测 + 单守卫 | `runtime-sandbox/src/{ancestor-chain,guard}.ts` |
| 沙箱策略 | `runtime-sandbox/src/policy.ts` |
| 凭据隔离 | `runtime-credentials/src/{grant,resolver}.ts` |
| 审计模型 | `runtime-audit/src/{trace,jsonl}.ts` |
| 审批 answerer | `runtime-approval/src/answerer.ts` |
| 配额 | `runtime-quota/src/{store,period}.ts` |
| path 解释器 | `runtime-path/src/{executor,interpolate,conditions}.ts` |
| 聚合降级 | `runtime-aggregate/src/{aggregate,jobs}.ts` |
| mesh 转发 | `runtime-mesh/src/mesh.ts` |
| pro 门面 | `runtime-pro/src/pro.ts` |
| 宿主指令 | `runtime-host/src/host.ts` |
| mcp 桥 | `runtime-bridge/src/bridge.ts` |
| 协议映射 | `runtime-contract/src/error-codes.ts` |
| 元指令/生命周期 | `runtime-meta/src/{meta,registry,installer}.ts` |
| path 接线（A/B/C） | `runtime-inbound/src/pathBridge.ts` |
| 生态归属分流 | `runtime-inbound/src/ecosystem.ts` |
| workflow 编译 | `runtime-path/src/workflowCompiler.ts` |

## 附录 B：标准运行时机制对照（dsh-tc-runtime vs text-cli）

| 机制 | text-cli | dsh-tc-runtime |
|---|---|---|
| 协议信封 | `textcli-core` | 复用 `textcli-core`（零重写，契约测试证明） |
| 错误码 | 6 码闭集 | 同 6 码 + 16 行 dsh→协议映射表 |
| 指令命名 | `<domain>;<action>` | `tc__<d>__<a>`（loopback）/ 保留域 `text-cli;*` |
| 环检测 | `_ANCESTOR_CHAIN` | `ancestorChain`（AsyncLocalStorage，三键+MAX_CHAIN=32） |
| 凭据 | 配置注入 | `TC_` ref + env 白名单 + 授权映射第一防线 |
| 审计 | — | 独立 JSONL（traceId+seq） |
| 调度 | 单指令 | path/aggregate/mesh/pro 四层编排 |

## 附录 C：验证状态与待办（ubuntu 环境）

**本环境已验（裸开发优先）**
- `tsc --noEmit`：零错误（strict）。
- `vitest run`：通过。
- 红线 7 条按构造满足（§3.4 表）。

**待 ubuntu 联调**
1. `pnpm install` 重建 `@dsh-tc/*` 真实软链（验证 alias 解耦无迁移雷）。
2. `pnpm -w test --coverage`（100% 门禁；本环境未装 `@vitest/coverage-v8`）。
3. dsh 联调：profile 挂载、HTTP 端点 serve、沙箱真实拒绝、凭据 env 注入、answerer 真实 HMAC 往返。
4. 部署文档实跑定稿（cordis.patch.yml 三行禁用、health 验证）。

---

_文档版本：v0.3（移除 runtime-phase，去规划层）｜dsh-tc-runtime｜2026-08-28｜唯一真源：15 包源码（commit `2d0b347`/`18b18ff`）+ text-cli/docs/design_zh.md（结构参照）｜验证：本环境 tsc 零错误 / vitest 通过；dsh 联调待 ubuntu（附录 C）_
