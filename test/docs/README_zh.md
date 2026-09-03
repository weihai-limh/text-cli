# 关于测试

text-cli 的日常测试文件存放在内部研发环境中，不进入公共仓库。

**原因**：测试文件会干扰公共仓库的使用者聚焦协议和接口文档。

当前公共仓库不包含自动化测试。如果你需要验证运行时完整性，
请参考以下方式：

- **协议级验证**：运行 README 中的"30 秒体验"——`markdown_converter.py` + curl
- **安装即验证**：标准运行时附带的基础指令包可用于功能验证
- **自建测试**：参考 `SPEC_zh.md` 构建你自己的协议合规测试
- **链路验证套件**：`test/` 下提供七条按运行时组件组织的验证链路：

| 链路 | 运行方式 | 验证目标 |
|------|---------|---------|
| `service-A3/` | `bash test.sh` | 协议合规 + dispatch + install/uninstall 生命周期 |
| `service-A4/` | `bash test.sh` | 路径编排（内联/插值/并行/分支/降级递补）+ mode:"map" 循环迭代 |
| `copilot/` | `bash test.sh` | co-install + dispatch + co-uninstall 白名单链路 |
| `service-A9/` | `bash test.sh` | 聚合降级 + text-cli;pro 门面 + 透明代理（路径编排覆盖见 service-A4） |
| `endpoint/` | `bash test.sh` | Token 鉴权转发 + 安全防线 |
| `cloudbase/` | `node test.js` | 网关路由 + textcli-core 集成 + 协议闭集错误码（本地 mock） |
| `pypi/` | `python test.py` | textcli-loader 加载与 dispatch + discover + health |
| `npm/` | `node test.js` | textcli-core npm 包 loadPackageFromPath + execute + discover + health + 声明式/兼容式加载 |

每条链路从浅到深——通过前两项即确认框架部署正确，通过全部六项即确认全拓扑跑通。

### 测试脚本说明

所有 `.sh` 文件是薄壳包装：设置运行时环境变量后 `exec python3 test.py`。测试逻辑使用 Python 标准库 `urllib`（零 pip 依赖），通过 `check()` / `check_contains()` / `check_not_contains()` 断言逐条验证。每个脚本在退出前执行防御性清理（uninstall 残留的 mock 包）。

#### copilot/test.py

**验证目标**：co-install → dispatch → co-uninstall 白名单链路。

**前置条件**：Copilot 运行在 `127.0.0.1:20260`。

| 环境变量 | 默认值 | 说明 |
|------|------|------|
| `TEXT_CLI_COPILOT_URL` | `http://localhost:20260` | Copilot 地址 |
| `TEXT_CLI_PACKAGE_SOURCE_DIRS` | — | 指向 `test/mock/` |

**测试流程**：
1. `GET /text-cli/health` → 200
2. `co-list` before → 不含 `hello-world-cmd`
3. `co-install,hello-world-cmd` → 即时生效，无需重启
4. `co-list` after → 含 `hello-world-cmd`
5. `hello;world,test` → 返回问候
6. `co-uninstall,hello-world-cmd` → `co-list` 清空

**说明**：copilot 包使用 `*Handlers` mixin 类模式（`_handle_*` 方法），与 service 包的 `@directive` 装饰器不同。

---

#### service-A4/test.py

**验证目标**：路径编排全量（内联 JSON / 插值 / 并行 / 分支 / 降级递补）+ `mode:"map"` 循环迭代。

**前置条件**：A4 Service 运行在 `28050`，`test/mock/` 可访问，`paths/` 路径夹具已就位。yaml 可编辑（测试脚本自动修改 `map_enabled`）。

| 环境变量 | 默认值 | 说明 |
|------|------|------|
| `TEXT_CLI_BASE_URL` | `http://localhost:28050` | Service 地址 |
| `TEXT_CLI_PACKAGE_SOURCE_DIRS` | — | 指向 `test/mock/` |

**测试流程**：
1. 预安装 `hello-world-standard` + `hello-world-fail`
2. 内联 JSON 路径 → 200 + 结果含 `Hello!scout!`
3. hello-chain → 步骤间 `{step1.result}` 插值解析
4. parallel-demo → 并行组两步并发完成
5. branch-demo → `if equals` 条件分支命中
6. degrade-demo → 主指令失败触发降级递补
7. `map_enabled: false`（默认）→ `mode:"map"` 返回 `map_disabled`
8. 改 yaml `map_enabled: true` + 重启 → `map-demo.json` 正常跑通
9. `map-limit.json`（150 元素 > 默认 100）→ `LOOP_LIMIT`
10. cleanup：卸载预安装包 + 恢复 `map_enabled: false`

**说明**：map 循环迭代是 A4 层（paths 引擎）的原生能力。`map_enabled` 默认关闭——测试脚本自动 toggle yaml。路径编排部分从 A9 测试对位迁移（这些能力在 A4 层即已就位）。

---

#### service-A3/test.py

**验证目标**：协议合规 + 包生命周期（install → dispatch → uninstall）。

**前置条件**：Service 运行在 `0.0.0.0:28050`（默认模式）或由测试脚本自动启动（层测试模式）。

| 环境变量 | 默认值 | 说明 |
|------|------|------|
| `TEXT_CLI_BASE_URL` | `http://localhost:28050` | Service 地址 |
| `TEXT_CLI_PACKAGE_SOURCE_DIRS` | — | 指向 `test/mock/` |
| `TEXT_CLI_LAYER_TEST` | — | 层测试模式：设为 `A3` 时自动启动 `deploy/A3-service/`，跑完自动停止 |

**两种运行模式**：

| 模式 | 命令 | 服务由谁启动 | 适用场景 |
|------|------|------------|---------|
| 外置运行时 | `bash test.sh` | 用户（start.bat / 手动） | 验证最终分发制品 |
| 层测试 | `TEXT_CLI_LAYER_TEST=A3 bash test.sh` | 测试脚本自动 | 验证 deploy 层产物（build-all.py 后） |

层测试模式下，脚本自动完成：启动 `deploy/A3-service/service/main.py` → 等待健康检查 → 跑测试 → 停止服务 → 清理端口。`TEXT_CLI_PACKAGE_SOURCE_DIRS` 自动指向 `test/mock/`。

**测试流程**：
1. 协议合规：`GET /health` + `text-cli;query` + 空 prompt 400
2. 安装前：`query,compact` 不含 `hello;world`
3. `install,hello-world-standard` → 热加载，无需重启
4. 安装后：`query,compact` 含 `hello;world`
5. `hello;world,test` → dispatch 成功
6. `uninstall,hello-world-standard` → `query,compact` 清空

**说明**：协议合规测试使用 `text-cli;query`（service 域指令），不依赖外部指令包。dispatch 测试在 install 后运行。所有 handler 返回 dict，`rst_err` 在成功时为空——test.py 对此做严格断言，不绕过任何错误码检查。

---

#### service-A9/test.py

**验证目标**：聚合降级 + `text-cli;pro` 门面 + 透明代理（路径编排覆盖见 `service-A4/`）。

**前置条件**：Service 运行在 `28050`，`test/mock/` 可访问，`paths/` 路径夹具已就位。Copilot 可选（运行在 `20260` 时自动激活透明代理测试）。

| 环境变量 | 默认值 | 说明 |
|------|------|------|
| `TEXT_CLI_BASE_URL` | `http://localhost:28050` | Service 地址 |
| `TEXT_CLI_COPILOT_URL` | `http://localhost:20260` | Copilot 地址（可选，透明代理用） |
| `TEXT_CLI_PACKAGE_SOURCE_DIRS` | — | 指向 `test/mock/` |

**测试流程**：
1. 预安装 `hello-world-standard` + `hello-world-fail`
2. 内联 JSON 路径 → 200 + 结果含 `Hello!scout!`
3. hello-chain → 步骤间 `{step1.result}` 插值解析
4. parallel-demo → 并行组两步并发完成
5. branch-demo → `if equals` 条件分支命中
6. degrade-demo → 主指令返回 `{"status":"error"}` 触发降级递补
7. 透明代理（Copilot 存活时自动执行）—— co-install → sync-copilot → proxy dispatch → co-uninstall；Copilot 不可用时 `[INFO]` 跳过
8. 聚合降级 → `map;geocode`（无 provider 时 INFO 容错）
9. 门面入口 → `text-cli;pro` 返回 `available` 清单
10. cleanup：卸载预安装包

**说明**：降级递补依赖 handler 返回 `{"status":"error"}`（非 HTTP 500，避免被识别为 delegated）。透明代理通过探活自动判断——有 Copilot 时增加 4 PASS（co-install / sync-copilot / proxy dispatch / greeting），无 Copilot 时 `[INFO]` 跳过不计分。初次sync-copilot 因其需扫描 Copilot 端指令表所以有延时。

---

#### endpoint/test.py

**验证目标**：Token 鉴权 + 安全防线 + 透传转发。

**前置条件**：Endpoint 运行在 `0.0.0.0:29050`，至少一个 A3 backend 在 `A3_BACKENDS` 中。

| 环境变量 | 默认值 | 说明 |
|------|------|------|
| `TEXT_CLI_ENDPOINT_URL` | `http://localhost:29050` | Endpoint 地址 |
| `TEXT_CLI_ACCESS_TOKEN` | — | 可选，不设时 token 测试跳过 |

**测试流程**：
1. `GET /health` → 200
2. Token 鉴权：`POST /text-cli/cli` with Access Token（token 不设时跳过）
3. `GET /skills` → 聚合指令清单


---

#### cloudbase/test.js

**验证目标**：网关路由逻辑 + textcli-core envelope/parser 集成 + 协议闭集错误码。

**前置条件**：Node.js 运行环境，`.dev/cloudbase/index.js` 可访问（使用 textcli-core 重构版）。

**环境变量**：`TEXT_CLI_CLOUDBASE_PATH`（可选，默认指向 `.dev/cloudbase/`）。

**测试流程**：
1. 加载 `config.js` → 配置合法
2. `GET /health` → status ok
3. `GET /skills` → 返回对象
4. `POST /cli` with `AI:hello;world,test` → 信封含 `rst_types` / `rst_data` / `rst_err`
5. `PUT /cli` → 返回 `ERR_ROUTING`（协议闭集错误码）
6. 缺 prompt → 返回 `INVALID_PARAMS`
7. 未知路径 → 返回 `ERR_NOT_FOUND`

**说明**：本地 mock `wx-server-sdk`，不部署到真实云环境。无需云环境账号即可运行。验证项包括确认旧的自定义错误码（`UNKNOWN_METHOD` / `DOMAIN_NOT_FOUND` 等）已全部替换为协议闭集。

---

#### pypi/test.py

**验证目标**：`textcli-loader` 旁路运行时的 load / execute / list / discover / health 能力。

**前置条件**：`pip install textcli-loader`。

**环境变量**：`TEXT_CLI_MOCK_DIR`（默认 `test/mock/`）。

**测试流程**：
1. schema 静态校验：id / runtime / version
2. `load_package` → 返回 meta + directives
3. `list_directives` → 含 `hello;world`
4. `execute("AI:hello;world,test")` → 信封正确
5. `execute("AI:unknown;test")` → `rst_err` 非空
6. `discover()` → 返回 `{directives: [...]}`，含已加载包的指令
7. `health()` → 返回 `{status, body, version, spec_version, runtime}`

**说明**：仅测试 `runtime: "python"` 的 native 包。不依赖任何部署的服务——纯本地运行。

---

#### npm/test.js

**验证目标**：`textcli-core` npm 包的 `loadPackageFromPath` + `execute` + `discover` + `health` + `parse` + 声明式/兼容式加载。

**前置条件**：Node.js 运行环境，`src/skeleton/bypass-service/npm/textcli-core/` 可访问。

**环境变量**：无。

**测试流程**：
1. `loadPackageFromPath`（声明式 `handler.js`）→ 返回 meta + 注册成功
2. `execute`（英文）→ 返回协议信封，`rst_err` 为空
3. `execute`（中文别名）→ 别名可用
4. `execute`（中英混用）→ 混用可用
5. `getRegistered` → 含已注册指令
6. `execute`（未知指令）→ `rst_err: "ERR_NOT_FOUND"`
7. `parse` → 正确拆分 domain/action/params
8. `ok` / `err` → 信封格式正确
9. `discover()` → 返回 `{directives: [...]}`，含已加载包
10. `health()` → 返回 `{status, body, version, spec_version, runtime}`
11. cleanup → 临时文件清理
12. `loadPackageFromPath`（legacy `instructions/` 子目录格式）→ 兼容加载成功

**说明**：对标 pypi 链路，纯本地函数调用。验证声明式注册（推荐）和 legacy `instructions/` 子目录（兼容）两种格式。

---

#### workers 手动验证

**验证目标**：Cloudflare Workers 网关的 parser 跨平台一致性 + 信封格式合规。

**验证方式**：手动验证（非自动化）。Workers 需要 Cloudflare 环境或本地 `wrangler dev`。

**验证步骤**：
1. `wrangler dev` 启动本地 Workers
2. `POST /text-cli/cli` with `{"prompt": "AI:weather;query,Beijing"}` → 信封含 `rst_types` / `rst_data` / `rst_err`
3. 对比 Node.js 版 `textcli-core/parser` 解析结果与 Workers 版一致
4. `POST /text-cli/cli` with `{"prompt": "AI:unknown;test"}` → `rst_err: "ERR_NOT_FOUND"`
5. `GET /text-cli/health` → `{"status": "ok"}`

**说明**：Workers 网关只做元数据路由（不执行 handler），handler 执行委托给后端 Node.js 运行时。

### mock 数据

`test/mock/` 提供五个最小化指令包，作为六条链路的统一测试输入：

| 包 | runtime | 文件 | 供谁测试 |
|----|---------|------|---------|
| `hello-world-standard` | `python` | schema.json + handler.py | service-A3 / service-A9 / pypi |
| `hello-world-cmd` | `python` | schema.json + handler.py + whitelists/ | copilot |
| `hello-world-fail` | `python` | schema.json + handler.py | service-A9（降级递补链） |
| `hello-world-cloudbaseSCF` | `js` | schema.json + index.js + package.json | cloudbase / npm |
| `hello-world-js` | `js` | schema.json + handler.js | textcli-core（声明式注册） |
| `tc-mcp-github` | `mcp` | schema.json + service-descriptor.json | 未激活（需 mcporter 前置条件） |
| `map-demo` | `path` | json | service-A4（map 正常迭代 3 元素） |
| `map-limit` | `path` | json | service-A4（150 元素 LOOP_LIMIT） |

除 `hello-world-cmd` 使用 `*Handlers` mixin 模式外，其余 python 包均使用 `@directive` 装饰器。handler 按 SPEC v1.3.2 返回 dict（由 registry 统一封装为信封），`{"status":"ok","result":...}` / `{"status":"error","reason":...}` 直接承载于 `rst_data`。路径引擎经 `unwrap_envelope` 还原后再用 `json.loads` 取 `{step.result}` 字段访问，与 handler 是否返回 dict 无关。各包差异仅在运行时实现层，测试不依赖开源指令包生态中的任何具体包。


