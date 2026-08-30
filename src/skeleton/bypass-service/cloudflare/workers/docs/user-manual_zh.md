# Cloudflare 专供版旁路运行时 使用手册

> 本手册面向 **Cloudflare Workers 上的运行时操作者 / Agent**——你通过 HTTP 端点驱动 tc 指令能力时，读这一份即可。
> 手册随 textcli-core-cloudflare 分发。修订：2026-08-17。
> 本运行时基于 text-cli (MIT) 的**协议规范**工作，协议部分与 text-cli / dsh-tc-runtime 完全一致（信封、错误码、指令语法零差异）。
> 逻辑组件与 tc-js-skeleton（node 版）共享同一份实现，本手册只描述 Cloudflare 平台面的差异。

---

## 零、概念速览

Cloudflare 专供版是把 tc 指令运行时搬到 **Cloudflare Workers + D1** 的旁路实现。它**不是第二份实现**——协议、编排、护栏、鉴权、存储契约全部复用 tc-js-skeleton 的 13 个逻辑组件，本仓库只新写三块平台面：**Worker 入口**（fetch 端点）、**D1 受限执行**（源码字符串 + 分级能力注入）、**D1 持久化**（十表 + StorageKV 契约）。

```
            Cloudflare Worker（本运行时）
   ┌────────────────────────────────────────────────┐
   │  fetch 入口（端点表面）                           │
   │   POST /text-cli/cli（Service-token 强制鉴权）   │
   │        → withAuth → mesh → path → usage →       │
   │          audit → native-guard → 执行层           │
   │   ├─ D1 可执行包（schema + handler 源码）         │
   │   │   → new Function + 分级 sandbox 受限执行     │
   │   └─ D1 持久化（kv/packages/tokens/keys/...）    │
   └────────────────────────────────────────────────┘
            统一协议：AI:<domain>;<action>,<params>
```

| 名词 | 含义 |
|------|------|
| **D1 可执行包** | `schema.json`（能力声明）+ `handler.js`（**源码字符串**存 D1），经受限构造执行，真·热装 |
| **Service-token** | 入口强制鉴权令牌，`token;issue` 签发，hash 落库可吊销 |
| **请求方计次** | `quota;register` 目标 + 按 token 的 requester_id 周期计次，耗尽 → `status:"stop"` 降级信号 |
| **key 指令化凭据** | `key;register` 录入，AES-GCM 加密落 D1，handler 经 `sandbox.credential.get` 按能力白名单取用 |
| **mesh 代理** | 本地不命中 → D1 `mesh_routes` → 对等 Worker（peer 双 token，凭证按 peer 隔离） |
| **协议端点** | `POST /text-cli/cli`（主入口）+ `GET /text-cli/{health,skills,tasks/{id}}` |
| **信封** | 所有响应统一为 `{rst_types, rst_data, rst_err}`，与 text-cli 逐字节一致 |

**红线（7 条，操作者也受益）**：① 不侵入宿主内核；② 凭据明文不进 JS 执行环境（也不落 D1）；③ 受限执行默认只给声明能力；④ 协议闭集（6 错误码 / 五态）；⑤ 保留域 `text-cli;*` 直接拦截不污染第三方命名空间；⑥ mesh 凭证按 peer 隔离不前向；⑦ 审计独立（D1 audit 表 + kv 分区），不写宿主会话。

---

## 一、部署

### 1.1 前置

```bash
npm i -g wrangler        # 或 npx wrangler
wrangler login
```

### 1.2 建库与建表

```bash
wrangler d1 create tc-bypass            # 记下返回的 database_id
wrangler d1 execute tc-bypass --file=schema.sql
```

`schema.sql` 建十表：`kv` / `packages` / `tokens` / `keys` / `usage` / `tasks` / `audit` / `mesh_peers` / `mesh_routes` / `service_manifest`。

### 1.3 绑定与密钥

`wrangler.toml`：

```toml
name = "tc-bypass"
main = "src/index.js"
compatibility_date = "2024-01-01"

[[d1_databases]]
binding = "DB"
database_name = "tc-bypass"
database_id = "<上一步的 database_id>"
```

Secrets（Worker 密钥，非明文进代码）：

```bash
wrangler secret put AUTH_SECRET        # Service-token 签名密钥
wrangler secret put KEY_ENC_SECRET     # key 凭据 AES-GCM 加密密钥
```

包源：`packages-src/` 作内联资源或 KV，`env.PACKAGE_SOURCE_DIR` 指向（本地测试默认 `./packages-src`）。

### 1.4 部署与验证

```bash
wrangler deploy    # 入口 src/index.js（export default { fetch }）

# 健康检查（公开层）
curl https://<worker>/text-cli/health
# → {"status":"ok","body":"textcli-cloudflare","version":"0.1.1","spec_version":"1.3.2","public_skills":[...]}
```

### 1.5 本地测试（无需网络 / 无 wrangler）

```bash
node --test test/*.test.js     # 18/18（D1 用内存 mock 走真实代码路径）
cd ../tc-js-skeleton && node --test test/*.test.js   # 91/91 共享逻辑层回归
```

---

## 二、指令表面

所有指令经 `POST /text-cli/cli`，请求头 `Service-token: <token>`（或 `Authorization: Bearer <token>`），body `{"prompt":"AI:<domain>;<action>,<params>"}`。

```bash
curl https://<worker>/text-cli/cli \
  -H "Content-Type: application/json" -H "Service-Token: <token>" \
  -d '{"prompt":"AI:weather;query,北京"}'
```

### 2.1 保留域元指令（`text-cli;*`）

由运行时直接拦截处理，**不进入第三方命名空间**（红线⑤）：

| 指令 | 作用 |
|------|------|
| `text-cli;install,<pkg>` | 安装 D1 可执行包（从包源读 schema+handler → **源码字符串存 D1** → 注册指令） |
| `text-cli;uninstall,<pkg>` | 卸载（注销注册项 + D1 删行，对称回收） |
| `text-cli;packages` | 列出已安装包 |
| `text-cli;query[,mode]` | 指令发现（`mode`: text/json/compact 等，返回 `directives[]`，含 domain_zh/usage/params/outputs） |
| `text-cli;path,<inline-json\|file\|name>[,<input>][,--register][,--json]` | 执行/注册 path（instruction 模板声明层，见 §2.7） |
| `text-cli;poll,<task_id>` | 轮询异步任务五态（指令面） |

```bash
curl ... -d '{"prompt":"AI:text-cli;install,weather"}'
# → {"rst_types":"text","rst_data":{"status":"ok","installed":"weather","directives":[...]},"rst_err":""}
curl ... -d '{"prompt":"AI:text-cli;query,json"}'
```

未安装对应包 → `ERR_NOT_FOUND`。

### 2.2 内置示例包

| 包 | 指令 | 能力 |
|---|---|---|
| `weather` | `weather;query,<city>[,<lang>]` / `天气;查询,<城市>`（别名） | `network-credential`：sandbox.fetch 查天气 + sandbox.credential.get("api_key") 取凭据；包内 i18n（zh/en，lang 越界降级默认） |
| `tc-math` | `tc-math;eval,<expr>` / `计算;求值,<表达式>`（别名） | `pure`：纯计算，零能力通道 |

### 2.3 Service-token（`token;*`）

运行时 = 能力提供方，**单 token 闭环**：

| 指令 | 作用 |
|------|------|
| `token;issue,<requester_id>[,<tier>]` | 签发 Service-token（返回 `token`/`requester_id`/`tier`；hash 落 D1） |
| `token;revoke,<token>` | 吊销（置 `revoked_at`，立即失效） |
| `token;list` | 列出有效 token |

```bash
curl ... -d '{"prompt":"AI:token;issue,alice,premium"}'
# → {"rst_types":"text","rst_data":{"status":"ok","token":"<jwt-like>","requester_id":"alice","tier":"premium"},"rst_err":""}
```

> 每个请求必须携带有效 token：缺失/伪造/吊销 → HTTP 401 + `SERVICE_DENIED`（跨终端强制鉴权）。

### 2.4 key 指令化凭据（`key;*`）

| 指令 | 作用 |
|------|------|
| `key;register,<service>,<key_type>,<value>[,<quota_track>]` | 录入凭据（AES-GCM 加密落 D1，**明文不落盘**） |
| `key;revoke,<service>` | 删除 |
| `key;list` | 列出已登记 service |

```bash
curl ... -d '{"prompt":"AI:key;register,weather_api,api_key,sk-abc123,weather;query"}'
```

handler 侧取用：`sandbox.credential.get("weather_api")`——**仅当包 schema 声明了该凭据**（capability 白名单），白名单外拒绝。

### 2.5 请求方计次（`quota;*`）

| 指令 | 作用 |
|------|------|
| `quota;register,<target>,<limit>,<cycle>` | 注册计次目标（cycle: `day`/`week`/`month`/`year`/`forever`） |

```bash
curl ... -d '{"prompt":"AI:quota;register,weather;query,5,day"}'
```

此后每个 token（requester_id）对 `weather;query` 每日计次，**第 6 次调用返回**：

```json
{"rst_types":"text","rst_data":{"status":"stop","reason":"quota_exhausted"},"rst_err":""}
```

> 配额耗尽是 **`status:"stop"` 降级信号，不是错误码**（绝不出 `SERVICE_DENIED`）——调用方可据此切换提供方。

### 2.6 异步任务（`task;*` + `text-cli;poll`）

| 指令 | 作用 |
|------|------|
| `text-cli;poll,<task_id>` | 查询任务五态（pending/running/done/error/cancelled） |
| `task;cancel,<task_id>` | 取消（仅 running 态生效） |

五态：

```
pending ──start──▶ running ──succeed──▶ done
                       ├──fail──▶ error
                       └──cancel──▶ cancelled
```

> Worker 重启后未终态任务自动置 `error` + reason `service_restarted`（重启对账）。

### 2.7 path 引擎（`text-cli;path,...`）

与 tc-js-skeleton 共享同一 `path` 组件，**instruction 字符串模板形态**（对齐协议 SPEC §4）：

```bash
# ① 按注册名执行
curl ... -d '{"prompt":"AI:text-cli;path,route-map,{"address":"威海"}"}'
# ② inline-json 直接执行
curl ... -d '{"prompt":"AI:text-cli;path,{...path 声明 JSON...},<input>"}'
# ③ 注册（校验必填 id/name/version/type/steps → 进 query 发现）
curl ... -d '{"prompt":"AI:text-cli;path,route-map,--register"}'
```

步骤字段：`instruction`（指令模板）/ `if`（字符串式 `==`/`!=` 或对象式 equals/contains/matches/exists/op/all/any）/ `mode`（toolchain 默认/parallel/map）/ `output_as` / `degradation`（降级链）/ `source`（跨节点）/ `timeout`。插值 `{input.x}` / `{output_as.field}` 深路径；map 默认关（需宿主开启）；注册后 `text-cli;query` 可发现该 path。

### 2.8 mesh 代理（`mesh;*`）

| 指令 | 作用 |
|------|------|
| `mesh;peer-register,<peer_id>,<endpoint>[,<access_token>][,<service_token>]` | 注册对等 Worker（双 token 加密存 D1） |
| `mesh;route-add,<domain>,<action>,<peer_id>` | 添加转发路由 |
| `mesh;peer-list` | 列出 peer |

本地不命中的指令：查 `mesh_routes` → 有路由 → 携带**该 peer 自己的 token** 转发（凭证按 peer 隔离，不携本端凭据）；无路由 → 本地 `ERR_NOT_FOUND`。

---

## 三、协议与信封

所有响应统一为信封（与 text-cli `textcli-core` 逐字节一致）：

```json
{"rst_types": "text", "rst_data": {"status":"ok","result":14}, "rst_err": ""}
```

- `rst_types`：`text` / `picture` / `video` / `audio` / `file`；handler 返回含 `pray_rst_types` 键时提升至此。
- `rst_data`：handler 返回的 JSON 对象。
- `rst_err`：空串 `""` = 成功；非空 = 失败。

**错误码闭集（6 码）**：`ERR_NOT_FOUND` / `ERR_EXECUTION` / `ERR_ROUTING` / `INVALID_PARAMS` / `ACCESS_DENIED` / `SERVICE_DENIED`。未知码兜底 `ERR_EXECUTION`——**协议永不静默放行**。

**本运行时实际触发场景**：

| 错误码 | 触发场景 |
|--------|---------|
| `ERR_NOT_FOUND` | 包未安装 / 指令未注册 / 任务不存在 / GET 应急通道默认关 |
| `ERR_EXECUTION` | handler 抛错 / 环检测 `CYCLE_DETECTED` / 未知兜底 |
| `ERR_ROUTING` | mesh 目的地不可达 |
| `INVALID_PARAMS` | prompt 缺失 / token/key/usage/mesh 参数非法 |
| `ACCESS_DENIED` | 包取 capability 白名单外凭据 |
| `SERVICE_DENIED` | 入口 token 缺失/伪造/吊销 |

> 调用方规则：**直接读取 `rst_data`**；配额耗尽读 `rst_data.status === "stop"`。

---

## 四、配置

| 项 | 默认 | 说明 |
|------|------|------|
| `env.DB` | — | D1 绑定（必须） |
| `env.AUTH_SECRET` | `dev-secret` | Service-token 签名密钥（生产必换，`wrangler secret put`） |
| `env.KEY_ENC_SECRET` | `dev-key-secret` | key 凭据 AES-GCM 加密密钥（生产必换） |
| `env.PACKAGE_SOURCE_DIR` | `./packages-src` | D1 可执行包源目录 |
| `service_manifest.public_directives` | `{}` 全开 | `/skills` 白名单（只做输出过滤，不兼作执行准入） |
| GET 应急通道 | 关 | `GET /text-cli/cli?prompt=` 默认 404，需显式开启 |

---

## 五、红线与安全

| # | 红线 | 操作者可见表现 |
|:---:|------|------|
| ① | 不侵入宿主内核 | 纯 Worker 旁路，零改 Cloudflare 平台 |
| ② | 凭据明文不进 JS 执行环境 | 明文只在受限执行 env 注入瞬间存在；D1 存 AES-GCM 密文（测试断言） |
| ③ | 受限执行默认只给声明能力 | pure 包拿不到 fetch/凭据；白名单外凭据被拒 |
| ④ | 协议闭集 | 仅 6 错误码 / 五态；未知码兜底 `ERR_EXECUTION` |
| ⑤ | 保留域不污染第三方命名空间 | `text-cli;*` / `token;*` / `key;*` / `mesh;*` 直接拦截 |
| ⑥ | mesh 凭证按 peer 隔离 | 转发只注入目标 peer token，不携本端凭据 |
| ⑦ | 审计独立 | D1 `audit` 表 + kv 分区（traceId + seq），不写宿主会话 |

**兜底原则**：任何未预见失败都走 `ERR_EXECUTION` 而非静默成功；鉴权/凭据缺失一律 fail-closed 拒止。

---

## 附录

### A. 指令速查

| 命名空间 | 形态 | 示例 |
|------|------|------|
| 指令包 | `<domain>;<action>` | `AI:weather;query,北京` / `AI:天气;查询,北京`（别名） |
| 保留域 | `text-cli;<action>` | `AI:text-cli;install,weather` |
| path | `text-cli;path,<inline-json\|file\|name>[,<input>][,--register][,--json]` | `AI:text-cli;path,route-map,{"address":"威海"}` |
| token | `token;<action>` | `AI:token;issue,alice,premium` |
| key | `key;<action>` | `AI:key;register,weather_api,api_key,sk-abc123` |
| quota | `quota;<action>` | `AI:quota;register,weather;query,5,day` |
| task | `task;<action>` / `text-cli;poll` | `AI:text-cli;poll,task-1` |
| mesh | `mesh;<action>` | `AI:mesh;route-add,ghost,search,peer-a` |

### B. 错误码速查

| 错误码 | 含义 | 常见场景 |
|--------|------|---------|
| `ERR_NOT_FOUND` | 指令不存在 | 包未安装 / 任务不存在 |
| `ERR_EXECUTION` | 执行失败 / 环检测 / 兜底 | handler 异常、`CYCLE_DETECTED` |
| `ERR_ROUTING` | 路由失败 | mesh 目的地不可达 |
| `INVALID_PARAMS` | 参数不合法 | prompt 缺失、注册参数非法 |
| `ACCESS_DENIED` | 能力/凭据未授权 | 白名单外凭据 |
| `SERVICE_DENIED` | 服务侧明确拒止 | 入口 token 无效 |

> 配额耗尽走 `rst_data.status="stop"`，不返回 `SERVICE_DENIED`。

### C. 端点 / 环境变量

| 项 | 说明 |
|------|------|
| `POST /text-cli/cli` | 主指令入口（Service-token；body `{"prompt":"AI:..."}`） |
| `GET /text-cli/tasks/{id}` | 异步任务五态查询（Service-token） |
| `GET /text-cli/skills` | 技能白名单（公开） |
| `GET /text-cli/health` | 健康检查 + spec_version + public_skills（公开） |
| `GET /text-cli/health?auth=1` | 鉴权层完整 capabilities（Service-token） |
| `DB` / `AUTH_SECRET` / `KEY_ENC_SECRET` / `PACKAGE_SOURCE_DIR` | Worker env（见 §四） |

### D. 构建 / 验证命令

```bash
node --test test/*.test.js                 # 18/18（D1 mock，零删除）
cd ../tc-js-skeleton && node --test test/*.test.js   # 91/91 回归
wrangler d1 execute tc-bypass --file=schema.sql      # 真实建表
wrangler deploy                                       # 部署
```

> 当前进度（2026-08-17）：实现完成，本环境 18/18 + 回归 91/91；wrangler/D1 真实部署待网络环境（见 `docs/design_zh.md` 附录 C）。
