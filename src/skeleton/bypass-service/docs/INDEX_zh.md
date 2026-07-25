# bypass-service 分组

## 定位

bypass-service 分组下的骨架层绑定 **旁路运行时**——不走标准 `text-cli;install` 管线、不参与 A2→A9 骨架累积链的非 Python 运行时。它们由独立的云平台网关承载，经 `build-all.py` 直通模式同步到 `deploy/bypass-service/`。

与 service 分组的关系：**平行、不累积、不继承**。旁路运行时和标准 runtime 通过统一的 `AI:域;动作,参数` 协议互通——调用方不感知执行方是标准服务还是云函数。

## 当前运行时

| 运行时 | 平台 | 语言 | 文件 | 说明 |
|------|------|------|------|------|
| cloudbase | CloudBase SCF | Node.js | `config.js` + `index.js` + `package.json` | 腾讯云无服务器函数——网关路由 + 指令分发 |
| pypi | PyPI | Python | `src/textcli_loader/` + `pyproject.toml` | pip 可安装的零依赖包加载器——任何 Python 环境直接加载和执行指令包 |

## 与 service 的差异

| 维度 | service（标准运行时） | cloudbase（云函数） | pypi（pip 包） |
|------|------|------|------|
| 部署 | `text-cli;install` / `co-install` | 云函数控制台 / CLI 部署 | `pip install textcli-loader` |
| handler 注册 | `handler_inits` + `@directive` | 网关路由表（`domain → 云函数名`） | `@directive` 装饰器（动态 import） |
| 依赖管理 | `requires.pip` / `requires.npm` 自动安装 | 云函数 `package.json` / 平台层管理 | handler.py 自身的 import（用户自行安装） |
| 发现 | `text-cli;query` 聚合 | 网关 `get_schema` 协议端点 | `get_registered()` API |
| 端口 | `0.0.0.0:28050` | 无——云平台自动分配 | 无——纯函数调用 |
| 协议 | HTTP POST `/text-cli/cli` | SDK 调用 + HTTP 双模式 | Python 函数调用 |
| 骨架构建 | A2→A9 累积链 | `build-all.py` 直通模式（BYPASS） | `build-all.py` 直通模式（BYPASS） |

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
| CloudBase SCF | ✅ 已实现 | 云函数运行时 |
| PyPI（textcli-loader） | ✅ 已发布 | pip 包运行时——`pip install textcli-loader` |
| Cloudflare Workers | ⏳ 预留 | A5 已有 Cloudflare Workers 部署（`deploy/A5-endpoint/cloudflare/`），可参照移植指令包模式 |
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
