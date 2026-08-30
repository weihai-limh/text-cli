# Cloudflare 专供版旁路运行时 设计文档

> 本文档基于 **真实实现**（src 10 模块 / test 17 用例全绿 / tc-js-skeleton 84 回归无损）撰写，结构对齐 `dsh-tc-runtime/docs/design_zh.md`。
> 定位：**不是 tc-js-skeleton 的移植，也不是第二份实现**——是「共享同一套逻辑组件 + 三个平台适配器」的 Cloudflare 安装版。
> 凡「设计约定」与「落地实现」一致处直接记实现；凡实现较策划稿 `cloudflare-bypass-runtime_zh.md` 有**细化/加固**处，以「实现注」标注。
> 验证状态：本环境 `node --test test/*.test.js` 18/18 通过（D1 内存 mock，零删除）；**wrangler / D1 真实部署待有网络环境**（见附录 C）。

---

## 一、协议机制

Cloudflare 版不重新发明协议，**原样复用 `textcli-core` 信封 + tc-js-skeleton `contract` 组件的 6 码闭集**。协议宪法是 `text-cli/docs/SPEC_zh.md` v1.3.2，协议部分与 text-cli / dsh-tc-runtime 完全一致。

### 1.1 响应信封

信封三字段（与 text-cli 完全一致，零重写）：

```js
// { rst_types, rst_data, rst_err }
{ rst_types: "text", rst_data: { status: "ok", result: 14 }, rst_err: "" }
```

- `tc.ok(result)` / `tc.err(code, reason)` / `tc.parse(prompt)` 全部来自 `textcli-core`（tc-js-skeleton 原样搬入的 CJS 薄核心）。
- 中间件短路信封必须三字段齐全（`rst_types`/`rst_data`/`rst_err`），`run()` 经 `isEnvelope` 判定后**原样透传，不二次包裹**（tc-js-skeleton 实测修复的系统性缺陷，Cloudflare 版继承该纪律）。
- **实现注**：`src/endpoints.js` 的所有错误响应（401/400/404/405）均手工构造三字段信封，HTTP 状态码只做传输面语义（401/400/404/405），业务语义一律走 `rst_err`。

### 1.2 错误码闭集

协议错误码固定 6 个（SPEC §1.2.8），Cloudflare 版实际用到的子集与语义：

| # | CF 侧信号 | 落地码 | 显式 reason | 说明 |
|---|---|---|---|---|
| 1 | 包未安装 / 指令未注册 / 任务不存在 | `ERR_NOT_FOUND` | — | 无匹配指令 / not_found / method not allowed / GET 应急通道默认关 |
| 2 | prompt 缺失 / token 参数非法 | `INVALID_PARAMS` | — | 参数非法 |
| 3 | handler 抛错 / 环命中 / 引擎未知兜底 | `ERR_EXECUTION` | `CYCLE_DETECTED` 等 | 执行失败，含环检测结构性拒绝 |
| 4 | mesh 路由不可达 / 转发失败 | `ERR_ROUTING` | — | 跨节点失败（远端 peer 不可达） |
| 5 | 凭据授权映射未命中（capability 白名单外） | `ACCESS_DENIED` | — | 包取未授权凭据 |
| 6 | 入口鉴权失败（token 缺失/伪造/吊销） | `SERVICE_DENIED` | `missing or invalid service token` | 跨终端强制鉴权（§6.1 合规） |
| 7 | 请求方配额耗尽 | `null` | — | **非错误**：`rst_data.status=stop` 降级信号 |

**实现注**：第 7 行 `code: null`——配额耗尽不是错误码，而是走 `status:"stop"` 的降级信号（与 dsh-tc-runtime 16 行映射表的第 14 行语义一致），调用方（含 path/聚合层）据此切换提供方，绝不出 `SERVICE_DENIED`。

### 1.3 异步任务五态

D1 `tasks` 表承载五态机（与 dsh-tc-runtime `AsyncJobBridge` 同语义）：

```
pending ──start──▶ running ──succeed──▶ done
                       │
                       ├──fail──▶ error
                       └──cancel(仅 running)──▶ cancelled
```

- 任务标识：`task_id = ${domain}-${action}-${seq}`（tasks.js）。
- 查询：`text-cli;poll,<task_id>`（指令面）或 `GET /text-cli/tasks/{id}`（端点面）；未命中 → `state:"not_found"` → `ERR_NOT_FOUND`。
- 取消：`task;cancel,<task_id>`，**仅在 running 态生效**（终态不可取消）。
- **重启残留对账**：`reconcileAfterRestart(db)`——进程/Worker 重启后未终态任务 → `error` + reason `service_restarted`（`src/tasks.js`）。

---

## 二、运行时体系

Cloudflare 版的核心设计决策：**逻辑层唯一一份，平台面各写各的**。

### 2.1 共享逻辑 + 平台适配器

| 复用（tc-js-skeleton 组件，**零改动**） | 新写（本目录 src/） |
|---|---|
| `contract`（信封/6 码闭集） | `d1-storage.js`：D1 → StorageKV 适配器 |
| `guard`（共享 `ancestorChain` + `withNativeGuard`） | `executor.js`：D1 源码受限执行 + 分级 sandbox |
| `path`（instruction 模板编排 + 注册发现，`withPath`/`PathRegistry`） | `meta.js`：D1 可执行包生命周期 |
| `auth`（Service-token，`createAuth`/`withAuth`） | `token.js` / `key.js` / `usage.js` / `tasks.js` / `mesh.js`：指令面 |
| `audit`（trace 模型，`withAudit`） | `endpoints.js` + `index.js`：Worker 入口 |
| `storage`（`createStorage`/`namespace` 契约） | `schema.sql`：D1 十表 |

**实现注**：`credentials`/`mesh` 两个组件在 tc-js-skeleton 里是「思路复用」——Cloudflare 版不直接 import 它们的中间件，而是以相同语义在 `executor.js`（capability 白名单）与 `mesh.js`（D1 路由表 + peer 双 token）各自落地。`usage.js` 自研请求方计次（母本 quota 是全局 id 计次，CF 版按 `requester_id` 挂 token）。

### 2.2 洋葱架构与中间件链

```
入口/鉴权面    Worker fetch → 校验 Service-token → 端点表面（/cli /tasks/{id} /skills /health）
编排层         withAuth → withCfMesh → withPath → withUsage → withAudit → withNativeGuard
执行层         D1 可执行包（schema + handler 源码字符串）→ 受限执行（分级能力注入）
持久层         D1：kv / packages / tokens / keys / usage / tasks / audit / mesh_peers / mesh_routes / service_manifest
```

`compose(...)` 用 `reduceRight` 拼装（tc-js-skeleton 语义），数组首项最外层：

```js
const chain = compose(
  withAuth(auth, { mode: "required", tokenFor: getTokenFromContext }), // 最外：入口强制鉴权
  withCfMesh,                                                          // mesh：本地不命中 → D1 路由 → peer
  withPath(paths, { ancestorChain }),                                  // path 声明层（拦截 text-cli;path）
  withUsage({ db }),                                                   // 请求方计次（quota;register 目标）
  withAudit(auditWriter),                                              // 审计（D1 kv audit 分区）
  withNativeGuard({ ancestorChain }),                                  // 最内：native 键环检测
)(coreDispatch);
```

- **拦截型中间件 fallthrough**：`withCfMesh`/`withPath` 对非自身域透传到 `next`，不干扰普通指令。
- **共享链**：`run()` 仅在 `ancestorChain.hasContext()` 为假时顶层建立 ALS 上下文，重入复用（与 tc-js-skeleton 同语义），native/path/mesh 三段环检测共用**同一个** `ancestorChain` 实例，跨类型互环（path→native→path）不漏检。

### 2.3 持久层：D1 十表 + StorageKV 契约

- 运行时逻辑层走 `kv` 表（`StorageKV` 契约的 D1 落地）：`createD1Storage(db)` 实现 `get/set/del`，`createStorage(...).namespace("tokens")` 等分区 → kv 键带前缀（`tokens:...`/`audit:...`），tc-js-skeleton 的 auth/audit 组件直接消费，**零改动复用**。
- 业务表用于查询面（`schema.sql`）：

| 表 | 用途 |
|---|---|
| `kv` | StorageKV 通用键值（tokens/audit 等 namespace 落点） |
| `packages` | D1 可执行包：`schema_json` + `handler_js` 源码字符串 + domains/actions |
| `tokens` | Service-token：token **hash** 落库 + requester_id + tier + revoked_at |
| `keys` | key 指令化凭据：`values_cipher` AES-GCM 密文 + quota_track |
| `usage` | 请求方计次：`(requester_id, target, usage_date)` 主键 + used/limit/cycle |
| `tasks` | 异步任务五态 + result_json |
| `audit` | 审计事件（ts/requester_id/prompt/rst_type/rst_err/sandbox_reject） |
| `mesh_peers` | peer 双 token（加密存明文以便转发 + hash 供校验） |
| `mesh_routes` | `(domain, action)` → peer_id 路由表 |
| `service_manifest` | 技能白名单（暂定 `{}` 全开） |

### 2.4 当前形态

- src 10 模块 846 行 + test 4 文件 714 行（D1 内存 mock：mini SQL 引擎，零删除纪律）。
- `node --test test/*.test.js` **18/18 通过**；tc-js-skeleton 回归 **91/91 无损**。
- **未验面**：真实 wrangler 部署、真实 D1 事务原子性、workerd 下 ALS/`new Function` 行为、真实跨节点 mesh 传输——待有网络环境（附录 C）。

---

## 三、消费侧——从 Worker 到 tc 指令

### 3.1 统一协议入口

所有指令经 `POST /text-cli/cli` 进入，body `{"prompt":"AI:<domain>;<action>,<params>"}`，请求头携带 Service-token：

```js
// endpoints.js handleCli：鉴权 → 解析 → 走链 → 信封
const verify = await rt.auth.verify(token).catch(() => null);
if (!verify) return json(401, { rst_types: "text", rst_err: "SERVICE_DENIED", ... });
const body = await request.json();
const result = await rt.run(body.prompt, { headers, token, auth: verify });
return json(200, result);
```

**实现注**：入口**强制鉴权**（`mode:"required"`）——这与 dsh-tc-runtime 手册 §6.1「跨终端强制」一致；`withAuth` 通过后把载荷注入 `context.auth`，供 usage（requester_id 计次）/ audit 消费。

### 3.2 指令发现

- `GET /text-cli/skills`：`service_manifest.public_directives` 白名单过滤（暂定 `{}` 全开），输出暴露面。
- `text-cli;query[,mode]`：`buildDirectives(db)` 从 `packages` 表聚合 `{domain, action, schema}` → 结构化返回。
- `GET /text-cli/health?auth=1`：鉴权层完整 capabilities（`mechanisms`/package_lifecycle/path/mesh/async/auth）。

### 3.3 智能调度层

**(a) path 声明层**（复用 tc-js-skeleton `withPath`，**instruction 字符串模板形态**，对齐 SPEC §4 / 原版 A4-paths）——步骤字段 `instruction`/`if`/`mode`（toolchain|parallel|map）/`output_as`/`degradation`/`source`/`timeout`；变量 `{input.x}`/`{output_as.field}` 深路径插值；`parallel` strategy first_ok/all；`map` items（变量名）/as/collect_as/on_error/concurrency + MAP_HARD_CAP=1000 + 深度 2 + 默认关；**五入口** `text-cli;path,<inline-json|file|name>[,<input>][,--register][,--json]`；`--register` 校验必填并注册，`PathRegistry.schemaEntries()` 合并进 `text-cli;query` 发现（path 成为可发现指令）。

**(b) mesh 代理**（新写，D1 路由表驱动）：

```js
// runtime.js withCfMesh：本地不命中 → mesh_routes → peer 转发
if (createLocalHas(getRegistered)(domain, action)) return next(...);   // 本地命中，不跨节点
const row = await db.prepare("SELECT peer_id FROM mesh_routes WHERE domain = ? AND action = ?").bind(...).first();
if (!row) return next(...);                                            // 无路由 → 本地（NOT_FOUND 由 core 给出）
return remote({ id: row.peer_id }, domain, action, params);
```

- peer 注册时写入**双 token**（access + service，`values_cipher` 加密存明文以便转发、hash 供校验）。
- **凭证按 peer 隔离**：转发只注入**目标 peer 自己的** token，不携带本端凭据（凭证三原则——不前向）。

---

## 四、标准运行时——Worker 专供

### 4.1 Worker 入口端点表面（src/endpoints.js + src/index.js）

| 端点 | 方法 | 鉴权 | 语义 |
|---|---|---|---|
| `/text-cli/cli` | POST | Service-token | 主指令入口 |
| `/text-cli/cli?prompt=` | GET | — | GET 应急通道（**默认关** → 404） |
| `/text-cli/tasks/{id}` | GET | Service-token | 异步任务五态查询 |
| `/text-cli/skills` | GET | 公开 | 技能白名单（暴露面） |
| `/text-cli/health` | GET | 公开 | 健康检查 + spec_version + public_skills |
| `/text-cli/health?auth=1` | GET | Service-token | 鉴权层完整 capabilities |

`src/index.js` 导出 `export default { fetch }`（Worker 标准入口）。

### 4.2 受限执行（src/executor.js）

D1 可执行包 = `schema.json`（声明 capability/credentials/endpoint_hint）+ `handler_js`（**源码字符串**）。执行路径：

1. `new Function` 构造 handler（Worker 侧 `handler_js` 为纯函数源码，非模块文件）；
2. **分级 sandbox**，按 `schema.capability.kind` 注入能力通道：

| kind | sandbox 通道 | 说明 |
|---|---|---|
| `pure` | 无 | 零能力，仅纯计算 |
| `network` | `sandbox.fetch` | 出站 HTTP（域名白名单由宿主侧把关） |
| `config-inject` | `sandbox.credential.get(service)` | 凭据按需取用，无网络 |
| `network-credential` | `sandbox.fetch` + `sandbox.credential.get` | 全能力 |

3. **凭据按包 capability 白名单过滤**（授权映射第一防线）：`sandbox.credential.get` 只放行该包 `schema.credentials` 声明的 service，白名单外 → 拒绝。
4. 不暴露 Worker 裸全局（`self`/`fetch`/`process`），能力只经 `sandbox` 通道——比 node 版 `require` 完整环境更严格。

### 4.3 共享链（环检测成立的前提）

与 tc-js-skeleton 实测结论一致：`run()` 顶层建立 ALS 上下文、`hasContext()` 判重入复用；`withNativeGuard` 对 `native:<domain>;<action>` 键做最内守卫。**Cloudflare 版若各自 new 链，跨类型互环必然漏检**——因此 `ancestorChain` 单例经 compose 注入所有需要环检测的中间件。

### 4.4 部署（真实环境）

```bash
wrangler d1 create tc-bypass
wrangler d1 execute tc-bypass --file=schema.sql
# wrangler.toml：DB 绑定 + secrets AUTH_SECRET / KEY_ENC_SECRET
wrangler deploy   # 入口 src/index.js
```

包源 `packages-src/` 作内联资源或 KV，`env.PACKAGE_SOURCE_DIR` 指向。

---

## 五、指令包与凭据

### 5.1 D1 可执行包

```json
// packages-src/weather/schema.json（示例：协议 §3.2 必填补全 + CF 宿主 capability）
{ "id": "weather", "type": "native", "name": "Weather", "name_zh": "天气查询",
  "runtime": "js", "version": "0.1.0", "category": "weather",
  "locales": ["zh", "en"], "trust": "internal",
  "description": "...", "description_zh": "...",
  "capability": { "kind": "network-credential", "credentials": ["api_key"] },
  "credentials": [{ "name": "api_key", "description": "...", "storage": "key_registry",
                    "register_cmd": "AI:key;register,api_key,api_key,<value>" }],
  "directives": [
    { "domain": "weather", "domain_zh": "天气", "action": "query", "action_zh": "查询",
      "usage": "weather;query,<city>[,<lang>]", "usage_zh": "天气;查询,<城市>[,<语言>]",
      "description": "...", "description_zh": "...",
      "params": ["city", "lang?"], "outputs": ["result", "city", "weather", "temp", "lang"] }
  ] }
```

```js
// packages-src/weather/handler.js —— 纯函数源码（CF 宿主面形态，worker 兼容），
// 包内 i18n（I18N 表 + 末位 lang，越界降级默认语言，SPEC §7.3）
async function main(params, context, sandbox) { ... }   // 经 sandbox.credential.get("api_key") 取凭据
```

**实现注**：
- **schema 是协议面**（§7.2"跨实现语言共有的契约表面"）——补全 9 包级必填 + 4 指令级必填 + `locales`/`domain_zh`/`action_zh`/`credentials` 声明；`capability` 是 CF 宿主面（执行白名单），与协议 `credentials` 声明并存。
- **别名路由（协议面 §1.1）**：`installPackage` 注册时把 `domain_zh`/`action_zh` 传 `register` opts → textcli-core alias 表 → `AI:天气;查询,北京` 归一化到 `weather;query`（回归测试锁死）。
- **handler 模块形态是宿主面**：CF 保留 `async function main(params, context, sandbox)`（受限执行格式），不改为原版 `module.exports` 结构——协议只要求"返回 object → rst_data、`{status:"ok"}`/`{status:"error", reason}`、`pray_rst_types` 提升"。
- 与 tc-js-skeleton 示例包（`module.exports` 声明式）**同一 schema 契约、不同宿主加载形态**——一次编写协议声明，两种部署方式。

### 5.2 包生命周期（src/meta.js）

- `text-cli;install,<pkg>`：从 `PACKAGE_SOURCE_DIR` 读 `schema.json` + `handler.js` → **源码字符串存 D1** → `register` 注册 `domain;action` → 返回 `{installed, directives}`。真·热装（无文件系统依赖）。
- `text-cli;uninstall,<pkg>`：`unregister` 回收注册项 + **D1 删行**（对称回收）。
- `text-cli;packages`：列出已装包（含 capability/domains/actions）。

### 5.3 Service-token 闭环（src/token.js）

- `token;issue,<requester_id>[,tier]`：签发 HMAC-SHA256 自签 token，**hash 落 D1 `tokens` 表**（明文不落盘）。
- `token;revoke,<token>`：置 `revoked_at` → 入口校验拒绝（吊销闭环）。
- `token;list`：列出有效 token。
- 入口强制：`withAuth(required)`，缺失/伪造/吊销 → `SERVICE_DENIED`（HTTP 401）。

### 5.4 key 指令化凭据（src/key.js）

- `key;register,<service>,<key_type>,<value>[,<quota_track>]`：AES-256-GCM 加密（密钥 = Worker secret `KEY_ENC_SECRET` 派生）→ 密文存 D1 `keys.values_cipher`（**明文不落盘**，测试断言）。
- `key;revoke,<service>` / `key;list`。
- 取用：`getKeyValue(db, keySecret, service)` → `executorDeps.getKey` → `sandbox.credential.get(service)`（executor 侧再经 capability 白名单过滤）。

### 5.5 请求方计次（src/usage.js）

- `quota;register,<target>,<limit>,<cycle>`：注册计次目标（cycle: day/week/month/year/forever）。
- 实际计次挂 **Service-token 的 requester_id**（`withUsage` 中间件）：每次调用按 `(requester_id, target, usage_date)` 原子 check+consume，超限 → `{ status: "stop" }` 降级信号（**非错误码**）。

---

## 附录 A：关键文件索引（基于实现）

| 主题 | 文件 |
|---|---|
| Worker 入口 | `src/index.js` |
| 端点表面 | `src/endpoints.js` |
| 运行时拼装（链/指令注册/run） | `src/runtime.js` |
| D1 → StorageKV 适配器 | `src/d1-storage.js` |
| 受限执行（分级 sandbox） | `src/executor.js` |
| 包生命周期（install/uninstall/query） | `src/meta.js` |
| Service-token | `src/token.js` |
| key 指令化凭据（AES-GCM） | `src/key.js` |
| 请求方计次 | `src/usage.js` |
| 异步任务五态 + 对账 | `src/tasks.js` |
| mesh 代理（peer/route） | `src/mesh.js` |
| D1 建表 | `schema.sql` |
| 内置包源 | `packages-src/{weather,tc-math}` |
| 测试（D1 mock mini SQL 引擎） | `test/helpers.js` + `test/phase{1,2,3,4}.test.js` |

## 附录 B：机制对照（Cloudflare 版 vs tc-js-skeleton）

| 机制 | tc-js-skeleton（node） | Cloudflare 版（Worker） |
|---|---|---|
| 协议信封/6 码 | `contract` 组件 | 复用（零改动） |
| 环检测 | `ancestorChain`（ALS） | 复用同一单例（workerd 支持性待实测，附录 C） |
| path 编排 | `path` 组件 | 复用（零改动，instruction 模板形态） |
| Service-token | `auth` 组件 | 复用 `createAuth`/`withAuth` + `token.js` 指令面 |
| 审计 | `audit`（内存/JSONL writer） | 复用 trace + D1 writer |
| 存储契约 | `storage`（内存/文件） | `createD1Storage` 实现同一 `StorageKV` |
| 包生命周期 | compose：文件系统拷贝 + `.index.json` | meta.js：**源码字符串存 D1** + 注册 |
| 包执行 | `require`（CJS 完整环境） | `new Function` + **分级 sandbox**（能力通道注入） |
| 计次 | quota（全局 id） | usage（**按 requester_id 挂 token**） |
| mesh | 内存 routeTable | D1 `mesh_routes` + peer 双 token 加密 |

## 附录 C：验证状态与待办

**本环境已验（D1 内存 mock）**
- `node --test test/*.test.js`：18/18 通过（Phase 1 协议面+包 / Phase 2 执行+鉴权+计次 / Phase 3 凭据+编排+环检+别名路由 / Phase 4 异步+mesh）。
- tc-js-skeleton 回归：91/91 无损（共享逻辑层未被平台面污染）。
- 关键断言：`handler_js` 为源码字符串、纯包拿不到 fetch/凭据、白名单外凭据被拒、明文不落 D1、伪造/吊销 token 拒止、配额 stop、重启对账、mesh 只注入目标 peer token、**别名路由 `AI:天气;查询` → `weather;query`**、**query 发现含补全字段（domain_zh/usage/params/outputs）**。

**待 wrangler 环境**
1. `wrangler d1 create/execute` 真实建表；`wrangler deploy` 真实部署。
2. workerd 下 `AsyncLocalStorage` 支持性实测（不支持则改 context 手动传链数组）。
3. D1 并发事务：usage 的原子 check+consume 在跨请求并发下需 **D1 batch + CAS**（StorageKV 契约建议补 `incr/cas` 原语）。
4. `new Function` 在 Worker 的可用性；真实跨节点 mesh 传输。

---

_文档版本：v0.1（实现对齐版）｜textcli-core-cloudflare｜2026-08-17｜唯一真源：本目录 src 10 模块 + tc-js-skeleton（共享逻辑层）｜验证：本环境 18/18 + 回归 91/91；wrangler 联调待网络环境（附录 C）_
