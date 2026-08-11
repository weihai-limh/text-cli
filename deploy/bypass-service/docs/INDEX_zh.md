# bypass-service 分组

## 定位

bypass-service 分组下的骨架层绑定 **旁路运行时**——不走标准 `text-cli;install` 管线、不参与 A2→A9 骨架累积链的非 Python 运行时。它们由独立的云平台网关承载，经 `build-all.py` 直通模式同步到 `deploy/bypass-service/`。

与 service 分组的关系：**平行、不累积、不继承**。旁路运行时和标准 runtime 通过统一的 `AI:域;动作,参数` 协议互通——调用方不感知执行方是标准服务还是云函数。

## 当前运行时

旁路运行时覆盖三种部署形态：本地包加载器（Python / JavaScript）、云函数网关（CloudBase）、边缘计算网关（Cloudflare Workers）。

| 运行时 | 平台 | 语言 | 文件 | 说明 |
|------|------|------|------|------|
| pypi | PyPI | Python | `src/textcli_loader/` + `pyproject.toml` | pip 可安装的零依赖包加载器——任何 Python 环境直接加载和执行指令包 |
| npm | npm | JavaScript | `textcli-core/` + `package.json` | npm 可安装的零依赖运行时——Node.js 环境直接加载和执行指令包，与 Python loader 同构 |
| cloudbase | CloudBase SCF | Node.js | `config.js` + `index.js` + `package.json` | 腾讯云无服务器函数——网关路由 + 指令分发 |
| cloudflare | Cloudflare Workers | JavaScript | `workers/gateway.js` | 边缘计算网关——从 KV Store 加载包，协议解析 + 路由分发 + 信封封装 |

## 与 service 的差异

| 维度 | service（标准运行时） | pypi（pip 包） | npm（npm 包） | cloudbase（云函数） | cloudflare（边缘网关） |
|------|------|------|------|------|------|
| 部署 | `text-cli;install` / `co-install` | `pip install textcli-loader` | `npm install textcli-core` | 云函数控制台 / CLI 部署 | Workers CLI / Dashboard 部署 |
| handler 注册 | `handler_inits` + `@directive` | `@directive` 装饰器（动态 import） | `register()` 函数 | 网关路由表（`domain → 云函数名`） | 元数据模式（handler 为 null，委托后端执行） |
| 依赖管理 | `requires.pip` / `requires.npm` 自动安装 | handler.py 自身的 import（用户自行安装） | handler.js 自身的 require（用户自行安装） | 云函数 `package.json` / 平台层管理 | KV Store / 平台层管理 |
| 发现 | `text-cli;query` 聚合 | `get_registered()` API | `get_registered()` API | 网关 `get_schema` 协议端点 | 同 textcli-core `get_registered()` |
| 端口 | `0.0.0.0:28050` | 无——纯函数调用 | 无——纯函数调用 | 无——云平台自动分配 | 无——边缘节点自动分配 |
| 协议 | HTTP POST `/text-cli/cli` | Python 函数调用 | JavaScript 函数调用 | SDK 调用 + HTTP 双模式 | HTTP POST + Workers fetch |
| 骨架构建 | A2→A9 累积链 | `build-all.py` 直通模式（BYPASS） | `build-all.py` 直通模式（BYPASS） | `build-all.py` 直通模式（BYPASS） | `build-all.py` 直通模式（BYPASS） |

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

Cloudflare Workers 边缘计算网关。只使用 textcli-core 的纯逻辑模块（parser、envelope、alias、registry），把文件 IO 替换为 Workers KV Store。

### 架构

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

gateway 是纯网关——不做执行，只做协议解析 + 路由 + 信封封装。和 endpoint 的纯管道原则一致，但 endpoint 是 HTTP 层面的转发，gateway 是协议层面的分发。

### 文件

| 文件 | 说明 |
|------|------|
| `workers/gateway.js` | Workers 入口——协议解析 + KV 包加载 + 路由分发 + 信封封装 |

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

## 扩展规划

以下云函数运行时已预留扩展入口，按需追加：

| 平台 | 状态 | 备注 |
|------|:--:|------|
| PyPI（textcli-loader） | ✅ 已发布 | pip 包运行时——`pip install textcli-loader` |
| npm（textcli-core） | ✅ 已实现 | npm 包运行时——`npm install textcli-core`，与 Python loader 同构 |
| CloudBase SCF | ✅ 已实现 | 腾讯云云函数运行时 |
| Cloudflare Workers | ✅ 已实现 | 边缘计算网关——从 KV Store 加载包，协议解析 + 路由分发 |
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
