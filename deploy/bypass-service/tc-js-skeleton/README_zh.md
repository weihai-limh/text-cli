# tc-js-skeleton — textcli-core 可插拔骨架



## 洋葱分层与组件全景

```
骨架/门面：textcli-core-compose   ← 内建 装配 + 包生命周期(install/uninstall+JSON索引) + 多包消费(懒加载)
交互层(最外)：mesh / approval / credentials   ← 绑外部能力，deps 注入
护栏层：quota / audit                          ← dispatch 前拦/记
编排层：path / aggregate / contract            ← 声明层逻辑，内部自带 path:/agg: 环检
核心守卫(最内)：guard                          ← native:<d>;<a> 环检测（共享 ancestorChain 实例）
核心(不变薄)：textcli-core                     ← parser/envelope/alias/registry/loader
```

| 组件 | 来源母包 | 抽象路径 | 开关 | deps 契约 |
|---|---|---|---|---|
| `textcli-core` | text-cli 薄核心 | 原样搬入 | 常驻 | — |
| `textcli-core-compose` | （新造，内建 meta 简化核心） | 重写物理生命周期 | 常驻 | `{ root, sourceDir, middleware, deleter }` |
| `textcli-core-contract` | runtime-contract | A 纯搬运 | 外挂 | 纯函数，零 deps（复用 core ok/err） |
| `textcli-core-guard` | runtime-sandbox/ancestor-chain | A 纯搬运 | `guard.on` | `{ ancestorChain }` 注入共享实例 |
| `textcli-core-path` | runtime-path → **协议 SPEC §4 对齐改造**（instruction 模板形态，参照原版 A4-paths） | B deps 重绑定 | `path.on` | `{ dispatch, httpDispatch?, mapEnabled?=false, now? }` + `PathRegistry`（register/resolve/schemaEntries） |
| `textcli-core-aggregate` | runtime-aggregate | B deps 重绑定 | `aggregate.on` | `{ dispatch, ancestorChain, approval?, quota?, now? }` |
| `textcli-core-quota` | runtime-quota | A 纯搬运 | `quota.on` | `{ storage, now? }` 构造注入 |
| `textcli-core-audit` | runtime-audit | A 纯搬运 | `audit.on` | `{ writer }` 注入（内存/JSONL） |
| `textcli-core-storage` | （新造） | 地基 | `storage.on` | `{ adapter }`：内存 / 文件（Node）/ D1（Cloudflare） |
| `textcli-core-auth` | runtime-approval（鉴权面） | C 接口重设计 | `auth.on` | `{ tokenStore }`：storage 模态 或 加密 JSON 模态 |
| `textcli-core-approval` | runtime-approval | C 接口重设计 | `approval.on` | `{ httpPost, hmacSign, audit?, now? }` |
| `textcli-core-credentials` | runtime-credentials | C 接口重设计 | `credentials.on` | `{ resolve }` 凭据源注入 |
| `textcli-core-mesh` | runtime-mesh | C 接口重设计 | `mesh.on` | `{ localHas, dispatch, remote, now? }` |

> 明确不抽象（留母本）：runtime-mapper / runtime-meta 装配面 / runtime-host / runtime-bridge。

## path 声明层（instruction 模板形态，协议 SPEC §4）

步骤形态对齐协议与原版 A4-paths——**`instruction` 字符串模板**，不再是结构化步骤 DSL：

```json
{
  "id": "route-map", "name": "地图连线", "version": "0.1.0", "type": "pipeline",
  "steps": [
    { "id": "start", "instruction": "map;geocode,{input.address}", "output_as": "start" },
    { "id": "route", "instruction": "map;route,{start.lat},{start.lon}", "output_as": "route",
      "if": {"step": "start", "field": "status", "equals": "ok"} },
    { "id": "backup", "instruction": "map;geocode,{input.address}",
      "degradation": [{"id": "b1", "instruction": "geo2;geocode,{input.address}"}] },
    { "id": "remote", "instruction": "tc-ffmpeg;info,{video.path}",
      "source": "http://host/text-cli/cli", "timeout": 30000 },
    { "id": "para", "mode": "parallel", "strategy": "first_ok", "steps": [...] },
    { "id": "loop", "mode": "map", "items": "input", "steps": [...],
      "as": "item", "collect_as": "collected", "on_error": "continue", "concurrency": "serial" }
  ]
}
```

- **步骤字段**：`instruction`（指令模板）/ `if`（字符串式 `==`/`!=` 或对象式 equals/contains/matches/exists/op/all/any）/ `mode`（toolchain 默认 / parallel / map）/ `output_as` / `degradation`（降级链，禁止嵌套）/ `source`（跨节点，继承 `default_source`）/ `timeout`。
- **变量模型**：`{input.key}` 用户输入 JSON；`{output_as.field[.0.path]}` 命名变量深路径。两阶段插值：`{var}` 未定义 → 空串 + WARNING；`{var.field}` 取不到 → 保留原样（对齐 A4）。
- **执行语义**：`ok` / `error`（handler error、降级链耗尽 DEGRADE_EXHAUSTED、熔断 CIRCUIT_BREAK、if 跳过致引用悬空 BRANCH_NO_MATCH）/ `delegated`（指令未注册，非错误，返回 `partial` + 委托清单）。
- **map**：`items` 是**变量名**（指向数组 JSON 输出）；`MAP_HARD_CAP=1000`；嵌套深度 ≤2；默认关（`mapEnabled` 注入，对齐原版 `paths.map_enabled` 默认 False）。
- **五入口**：`text-cli;path,<inline-json|file|name>[,<input>][,--register][,--json]`；`--register` 校验必填（id/name/version/type/steps）并注册，注册后经 `PathRegistry.schemaEntries()` **进 query 发现**（`text-cli;path,<id>,<input>` 成为可发现指令）。

## 统一中间件契约与组合顺序

```js
const runtime = compose(
  withMesh,              // 最外：跨节点优先转发
  withApproval,          // 审批闸（deny → ACCESS_DENIED 短路）
  withCredentials,       // 凭据按包隔离注入 context.env
  withQuota,             // 配额（耗尽 → status:stop 降级信号）
  withAudit,             // 审计（traceId+seq 归组）
  withPath, withAggregate, // 编排（内部 path:/agg: 环检）
  withNativeGuard,       // 最内守卫（native: 键，贴核心）
)(coreDispatch);
```

- 环检测三层（`native:` / `path:` / `agg:`）**必须注入同一个 `ancestorChain` 实例**，
  否则跨类型互环（agg→path→agg）漏检——`textcli-core-guard` 导出该共享基座。
- 中间件返回协议信封（`rst_err/rst_data/rst_types` 三字段）时 `run()` 原样透传不二次包裹。

## 协议红线（对齐 SPEC_zh.md，已源码级实证）

1. 三字段信封，`rst_err` 空串 = 成功；6 错误码闭集，未知码回退 `ERR_EXECUTION`。
2. **配额耗尽 ≠ 错误**：`{status:"stop"}` 走降级链（聚合层消费），绝不出 `SERVICE_DENIED`。
3. 同步 `status:stop` = 降级信号（非终态）；异步任务终态才是 `error + quota_exhausted`。
4. 包生命周期走 `text-cli` 保留域（`install/uninstall/packages`），不污染第三方命名空间。
5. 组件内不 import 任何宿主（dsh/express），只用注入 deps。
