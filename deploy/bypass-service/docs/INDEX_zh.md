# bypass-service 分组

## 定位

bypass-service 分组下的骨架层绑定 **旁路运行时**——不参与 A2→A9 骨架累积链的非 Python 运行时。它们由独立的云平台网关 / 通用 JS 逻辑层 / dsh 承载，经 `build-all.py` 直通模式同步到 `deploy/bypass-service/`。

与 service 分组的关系：**平行、不累积、不继承**。旁路运行时和标准 runtime 通过统一的 `AI:域;动作,参数` 协议互通。

## 目录结构

```
bypass-service/
├── pypi/                # 本地 pip 包加载器（textcli-loader，Python）
├── npm/                 # 本地 npm 薄核心（textcli-core，JavaScript）
├── tc-js-skeleton/      # 通用 JS 逻辑层真源（12 个 textcli-core-* 组件家族，洋葱分层）
├── cloudbase/           # 腾讯云 SCF 云函数网关
├── cloudflare/          # Cloudflare Workers 边缘网关（D1 多功能版）
├── dsh/
│   ├── dsh-tc-runtime/  # dsh 作为 tc 运行时（Cordis 插件集，15 个 runtime-* 包）
│   └── dsh-tc-bridge/   # dsh 消费 tc 指令生态的能力缝插件（五闭集工具）
└── docs/                # 本 INDEX
```

## 当前运行时

旁路运行时覆盖五种形态：本地包加载器（Python / JavaScript）、云函数网关（CloudBase）、边缘计算网关（Cloudflare Workers D1）、通用 JS 逻辑层（tc-js-skeleton）、dsh 承载（dsh-tc-runtime / dsh-tc-bridge）。

| 运行时 | 平台 | 语言 | 文件 | 说明 |
|------|------|------|------|------|
| pypi | PyPI | Python | `src/textcli_loader/` + `pyproject.toml` | pip 可安装的零依赖包加载器——任何 Python 环境直接加载和执行指令包 |
| npm | npm | JavaScript | `textcli-core/` + `package.json` | npm 可安装的零依赖薄核心——Node.js 环境直接加载和执行指令包，与 Python loader 同构 |
| tc-js-skeleton | 通用 JS | JavaScript | `packages/` 12 个组件 | 旁路通用 JS 逻辑层真源（薄核心 + compose/guard/contract 等洋葱分层组件） |
| cloudbase | CloudBase SCF | Node.js | `config.js` + `index.js` + `package.json` | 腾讯云无服务器函数——网关路由 + 指令分发 |
| cloudflare | Cloudflare Workers | JavaScript | `workers/src/` 11 个模块 + `schema.sql` | 边缘计算网关（D1 多功能版）——可执行包存 D1 + 受限执行 + 单 Service-token 闭环 |
| dsh-tc-runtime | dsh（Cordis） | TypeScript | `dsh/dsh-tc-runtime/` 15 个 runtime-* 包 | dsh 作为 tc 运行时——9 机制能力全集，外挂于 dsh 的 Cordis 插件集 |


## 与 service 的差异

| 维度 | service（标准运行时） | pypi（pip 包） | npm（npm 包） | cloudbase（云函数） | cloudflare（D1 多功能网关） | dsh-tc-runtime（dsh Cordis） |
|------|------|------|------|------|------|------|
| 部署 | `text-cli;install` / `co-install` | `pip install textcli-loader` | `npm install textcli-core` | 云函数控制台 / CLI 部署 | Workers CLI / Dashboard 部署 + `schema.sql` 初始化 D1 | Cordis 插件装配（外挂 dsh，15 runtime-* 包） |
| handler 注册 | `handler_inits` + `@directive` | `@directive` 装饰器（动态 import） | `register()` 函数 | 网关路由表（`domain → 云函数名`） | 可执行包存 D1，executor 受限执行 + 元数据注册 | runtime-mapper 指令映射（tc 指令 ↔ ctx.tools） |
| 依赖管理 | `requires.pip` / `requires.npm` 自动安装 | handler.py 自身的 import（用户自行安装） | handler.js 自身的 require（用户自行安装） | 云函数 `package.json` / 平台层管理 | D1 / 平台层管理 | pnpm workspace（各 runtime-* 包自管依赖） |
| 发现 | `text-cli;query` 聚合 | `get_registered()` API | `get_registered()` API | 网关 `get_schema` 协议端点 | 同 textcli-core `get_registered()` | runtime-meta `text-cli;query` 元指令 |
| 端口 | `0.0.0.0:28050` | 无——纯函数调用 | 无——纯函数调用 | 无——云平台自动分配 | 无——边缘节点自动分配 | 入站 HTTP（runtime-inbound，`POST /text-cli/cli`） |
| 协议 | HTTP POST `/text-cli/cli` | Python 函数调用 | JavaScript 函数调用 | SDK 调用 + HTTP 双模式 | HTTP POST + Workers fetch | HTTP POST + dsh 生态（信封三字段闭集） |
| 骨架构建 | A2→A9 累积链 | `build-all.py` 直通模式（BYPASS） | `build-all.py` 直通模式（BYPASS） | `build-all.py` 直通模式（BYPASS） | `build-all.py` 直通模式（BYPASS） | `build-all.py` 直通模式（BYPASS） |

## pypi（pypi/）

纯本地 pip 包，不依赖任何 text-cli 服务。任何 Python 环境的 AI Agent 都可以 `pip install textcli-loader` 后直接加载指令包。

```python
from textcli_loader import load_package, execute

load_package("./my-date-calc/")
result = execute("AI:date-calc;add-days,2026-01-01,30")
```

### 文件

| 文件 | 说明 |
|------|------|
| `src/textcli_loader/parser.py` | 指令解析器（与 service core/parser.py 同构） |
| `src/textcli_loader/registry.py` | `@directive` 装饰器注册表 |
| `src/textcli_loader/loader.py` | schema.json + handler.py 动态加载（兼容 `from core.registry` 和 `from textcli_loader.registry`） |
| `src/textcli_loader/envelope.py` | 统一信封格式（兼容 text-cli service） |
| `pyproject.toml` | pip 包配置（src-layout） |
| `tests/test_smoke.py` | 冒烟测试 |
| `README.md` | 使用文档 |

## npm（npm/）

纯本地 npm 包，零外部依赖。任何 Node.js 环境的 AI Agent 都可以 `npm install textcli-core` 后直接加载和执行指令包。与 Python textcli-loader **同构**——parser、registry、envelope 的 API 和行为完全一致，仅语言不同。

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

### 文件

| 文件 | 说明 |
|------|------|
| `parser.js` | 指令解析器——支持 `AI:`/`指令:` 双前缀、括号深度追踪、转义序列、字符串引号内逗号不拆分 |
| `registry.js` | `register()` + `dispatch()` + `unregister()` + `getRegistered()`——支持别名解析、sync/async handler |
| `envelope.js` | `ok()` + `err()`——`pray_rst_types` 提升、错误码白名单校验（六种闭集） |
| `alias.js` | 别名映射——`addAlias()` + `resolve()`，大小写不敏感 |
| `loader.js` | 核心加载接口——不依赖 IO，平台适配器负责读文件，loader 只做注册 |
| `loader.node.js` | Node.js 平台适配器——`fs` + `require` 从磁盘加载 `schema.json` + `handler.js` |
| `index.js` | 统一入口 |
| `package.json` | npm 包配置——零外部依赖 |

## Cloudflare（cloudflare/）

Cloudflare Workers **D1 多功能版**边缘网关。**不是 tc-js-skeleton 的移植，也不是第二份实现**——是「共享同一套逻辑组件（textcli-core + contract）+ 三个平台适配器」的 Cloudflare 安装版。可执行包存 **D1**（非 KV），受限执行 + 单 Service-token 闭环。

### 架构

```
Cloudflare Workers（D1 多功能版）
  │
  ├── POST /text-cli/cli → src/index.js
  │     ├── 鉴权（src/token.js 单 Service-token 闭环）
  │     ├── 解析 prompt → domain;action,params（src/endpoints.js + src/runtime.js）
  │     ├── D1 加载可执行包 + 元数据（src/d1-storage.js + src/meta.js）
  │     ├── 受限执行（src/executor.js 分级 sandbox）或 mesh 转发（src/mesh.js）
  │     ├── key 指令化凭据（src/key.js，AES-GCM）
  │     ├── 异步任务五态 + 重启对账（src/tasks.js）
  │     └── 请求方计次 / 配额降级（src/usage.js）
  │
  ├── GET /text-cli/health | /schema | /tasks/{id} | /packets/...（端点面）
  └── 初始化：schema.sql（建 D1 表）
```

协议与 text-cli / dsh-tc-runtime 完全一致：复用 `textcli-core` 信封 + contract 的 6 码闭集，异步任务五态、配额 `status:"stop"` 降级、mesh 路由防环。

### 文件

| 文件 | 说明 |
|------|------|
| `workers/src/index.js` | Worker 入口（`export default { fetch }`） |
| `workers/src/endpoints.js` | 端点表面——HTTP 状态码 + 三字段信封错误构造 |
| `workers/src/runtime.js` | 运行时拼装——指令注册 + run |
| `workers/src/d1-storage.js` | D1 → StorageKV 适配器 |
| `workers/src/executor.js` | 受限执行（分级 sandbox） |
| `workers/src/meta.js` | 包生命周期（install/uninstall/query） |
| `workers/src/token.js` | Service-token 闭环 |
| `workers/src/key.js` | key 指令化凭据（AES-GCM） |
| `workers/src/usage.js` | 请求方计次（配额降级） |
| `workers/src/tasks.js` | 异步任务五态 + 重启对账 |
| `workers/src/mesh.js` | mesh 代理（peer/route，防环） |
| `workers/schema.sql` | D1 建表脚本 |
| `workers/package.json` | Worker 依赖声明 |
| `workers/docs/` | design_zh.md + README.md + user-manual_zh.md |

## CloudBase（cloudbase/）

### 架构

```
网关（CloudBase HTTP 触发器）
  │
  ├── POST /cli → index.js exports.main
  │     ├── 解析 prompt → domain;action,params
  │     ├── 查路由表 → routeTable[domain] → 云函数名
  │     └── cloud.callFunction(name, {prompt, _routerEvent})
  │           └── 指令云函数 → handler(params) → 返回信封
  │
  ├── GET /health → {status: "ok", service: "text-cli-router"}
  ├── GET /skills → {}
  └── SDK 调用 → action=get_schema → 返回 schema.json
```

### 文件

| 文件 | 说明 |
|------|------|
| `config.js` | 路由表（`routeTable`）和包注册表（`packages`） |
| `index.js` | 云函数入口——双模式（SDK + HTTP）路由 + `text-cli;query` 聚合 |
| `package.json` | 依赖声明（`wx-server-sdk`） |

### 扩展新指令

1. 部署指令云函数（每个 `domain` 一个独立云函数）
2. 在 `config.js` 的 `routeTable` 中登记 `domain → 函数名` 映射
3. 在 `config.js` 的 `packages` 数组中登记包 id（用于 `text-cli;query` 聚合）

新增包时无需改骨架——仅改网关侧配置。

## tc-js-skeleton（tc-js-skeleton/）

旁路**通用 JS 逻辑层真源**——textcli-core 薄核心的洋葱分层组件家族（12 个包），与平台无关，供 cloudflare / dsh / 其他 JS 承载复用。

```
骨架/门面：compose        ← 装配 + 包生命周期（install/uninstall + JSON 索引）+ 多包消费
交互层(最外)：mesh / approval / credentials   ← 绑外部能力，deps 注入
护栏层：quota / audit                          ← dispatch 前拦/记
编排层：path / aggregate / contract            ← 声明层逻辑，内部自带 path:/agg: 环检
核心守卫(最内)：guard                          ← native 环检测
核心(不变薄)：textcli-core                     ← parser/envelope/alias/registry/loader
```

| 组件 | 来源 | 说明 |
|------|------|------|
| `textcli-core` | 薄核心 | parser/envelope/alias/registry/loader，原样搬入 |
| `textcli-core-compose` | 内建 | 装配 + 包生命周期 + 多包消费（懒加载） |
| `textcli-core-contract` | runtime-contract | 规范信封 + 6 码闭集，纯函数零 deps |
| `textcli-core-guard` | runtime-sandbox | 环检测（共享 ancestorChain） |
| `textcli-core-path` | runtime-path | 声明层 path 引擎（instruction 模板形态） |
| `textcli-core-aggregate` | runtime-aggregate | 聚合 + try-in-order 降级 |
| `textcli-core-quota` / `audit` | runtime-* | 配额护栏 / 审计通道 |
| `textcli-core-storage` | 内建 | 存储地基（内存 / 文件 / D1） |
| `textcli-core-auth` / `approval` / `credentials` / `mesh` | runtime-* | 鉴权 / 人闸 / 凭据 / mesh 转发 |

> 明确不抽象（留母本）：runtime-mapper / runtime-meta 装配面 / runtime-host / runtime-bridge。
> 测试 91/91，作为旁路通用 JS 逻辑层真源。

## dsh（dsh/）

dsh 生态承载的旁路运行时，分两个插件：

### dsh-tc-runtime（dsh/dsh-tc-runtime/）

**dsh 作为 tc 运行时（JS 版）**——外挂于 dsh 的 Cordis 插件集（15 个 `runtime-*` 包），把 text-cli / tc 指令能力桥接进 dsh，提供旁路运行时形态（9 机制能力全集，不宣称标准运行时身份）。

```
runtime-inbound      入站 HTTP（六段管道 + 保留域拦截）
runtime-mapper       指令映射（tc 指令 ↔ ctx.tools）
runtime-sandbox      沙箱执行宿主（受限子进程 + policy 分层护栏）
runtime-credentials  凭据按包隔离
runtime-audit        审计通道（append-only JSONL）
runtime-meta         text-cli;* 元指令（install/query/path/...）
runtime-quota        dsh-quota（周期窗口 + 原子 check+consume）
runtime-approval     审批 answerer（HMAC + fail-closed）
runtime-host         宿主指令
runtime-path         path 引擎（声明层解释器 + workflow 编译）
runtime-aggregate    异步任务桥接（五态）+ 聚合降级
runtime-mesh         mesh 转发（路由表 / 防环 / 退避）
runtime-bridge       协议桥（mcp-client → mcp__<server>__<tool>）
runtime-pro          门面注册表（简名 → path/aggregate）
runtime-contract     全局验收（规范信封 + 16 行映射契约）
```

红线（7 条）：不侵入 dsh 内核、凭据明文不进 JS 执行环境、沙箱默认拒绝、协议闭集、保留域元指令拦截、审批归属过滤、tc 审计独立 JSONL。

### dsh-tc-bridge（dsh/dsh-tc-bridge/）

**dsh 消费 tc 指令生态的能力缝插件**——把 tc 指令生态（远程 tc 端点 + 本地 textcli-core JS 引擎）与 dsh 自身/mcp tool 统一到一个调度平面，对 dsh agent 暴露五个闭集工具，让 LLM 以 `AI:<域>;<动作>,<参数>` 原语消费 tc 能力。

| 工具 | 用途 |
|------|------|
| `call_tc` | 调 tc 指令（桥接模式走远端 / 混合模式短路 tc__ 工具） |
| `wait_tc` | 异步长任务轮询（指数退避） |
| `run_tc_js` | 进程内零网络执行本地 textcli-core JS 包 |
| `tool_avatar` | 同进程代理 dsh 自身 tool（含 mcp tool），省 token |
| `find_tc` | 桥内能力统一发现面（白名单 + 前缀映射） |

三种运行形态：桥接模式（dsh 无 tc runtime）/ 服务模式（dsh 仅作 tc runtime）/ 混合模式（dsh 同时 agent + runtime）。

## 扩展规划

以下运行时已落地或预留扩展入口：

| 平台 | 状态 | 备注 |
|------|:--:|------|
| PyPI（textcli-loader） | ✅ 已发布 | pip 包运行时——`pip install textcli-loader` |
| npm（textcli-core） | ✅ 已实现 | npm 薄核心运行时——与 Python loader 同构 |
| tc-js-skeleton | ✅ 已实现 | 通用 JS 逻辑层真源（12 组件洋葱分层） |
| CloudBase SCF | ✅ 已实现 | 腾讯云云函数运行时 |
| Cloudflare Workers（D1） | ✅ 已实现 | 边缘网关 D1 多功能版——可执行包存 D1 + 受限执行 + 单 Service-token 闭环 |
| dsh-tc-runtime | ✅ 已实现 | dsh 作为 tc 运行时（Cordis 插件集，15 runtime-* 包） |
| AWS Lambda | ⏳ 预留 | 结构参照 CloudBase 模式 |
| 阿里云函数计算 | ⏳ 预留 | 结构参照 CloudBase 模式 |

每个平台新增时，在 `bypass-service/` 下创建独立子目录（命名英文小写），包含该平台特有的入口文件和配置。所有旁路运行时通过统一的 `AI:域;动作,参数` 协议互通。

---

## 构建

bypass-service 通过 `build-all.py` 的直通模式同步：`src/skeleton/bypass-service/` → `deploy/bypass-service/`。不参与 A2→A9 累积链，不共享 `SKELETON_SUBDIRS` 白名单。全量文件原样复制。

```bash
# 单独构建旁路服务
python scripts/build-all.py BYPASS
```
