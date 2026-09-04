# text-cli 使用手册

> 本手册随所有分发包（Windows / Linux / macOS / Docker）一同分发。  
> 四个产品可独立部署、独立使用——你拿到的制品只含其中部分时，跳读对应章节即可。  
> 本制品基于 text-cli (MIT) 的协议规范工作。  
> 手册修订：2026-09-04

---

## 零、概念速览

text-cli 由四个独立产品组成。每个可单独部署——只在需要时组合。

```
Copilot (:20260, 127.0.0.1)    Service (:28050/9020, 0.0.0.0)    Endpoint (:29050, 0.0.0.0)
  ┌─ 本机能力代理                ┌─ 核心调度平台               ┌─ 鉴权网关
  │  终端 · 文件 · Skill         │  安装 · 编排 · SQL · MCP    │  IP黑名单 · 限流 · Token
  │                             │                             │
  │     sync-copilot ──────────→│                             │
  │         可选联动             │    A3_BACKENDS ────────────→│
  │                             │         可选联动              │
  └─────────────────────────────┴─────────────────────────────┘
                    统一协议：AI:domain;action,params
                    通过 Protocol 便捷消费以上服务
```

| 产品 | 制品名 | 监听 | 独立能做什么 |
|------|------|:--:|------|
| Copilot | `text-cli-A2-v*` | :20260, 127.0.0.1 | 装 cmd/skill 指令包，操作本机 |
| Service | `text-cli-A3-v*` ~ `A9-v*` | :28050, 0.0.0.0 | 装指令包，编排管道，持久化状态，接 MCP  |
| Endpoint | `text-cli-endpoint-python-v*` | :29050, 0.0.0.0 | 鉴权、限流、审计，透传至 Service  |
| Protocol | `protocol/`（随所有制品分发） | - | 零依赖消费端 SDK，四语言（Python/JS/Shell/PS），一键调用免 curl |


三种常见组合：

| 模式 | 包含 | 适用 |
|------|------|------|
| 本机 | 仅 Copilot + protocol | 个人开发，AI 操作本机 |
| 内网 | Copilot + Service + protocol  | 家庭/团队共享指令包 |
| 公网 | Copilot + Service + Endpoint | 对外提供服务，安全防线 |

---

## 一、部署

四个产品的部署相互独立——你需要哪个就部署哪个。**协议统一**（1.4 节），不管你跑了几个产品，说话方式一样。

### 1.1 Copilot

Copilot 制品为 `text-cli-A2-v*`（Win `.zip` / Linux `.tar.gz` / Docker）。

#### Windows

`start.bat` 是统一启动入口——自动设环境变量、拉起 Copilot。**运行方式二选一：**

```powershell
# PowerShell
Expand-Archive text-cli-A2-v*.zip -DestinationPath .
Start-Process -FilePath "start.bat" -WorkingDirectory "text-cli-A2-v*"
```

```cmd
:: cmd
cd text-cli-A2-v*
start.bat
```

停止：`.\end.bat`

#### Linux

```bash
tar -xzf text-cli-A2-v*.tar.gz
cd text-cli-A2-v*
chmod +x start.sh
./start.sh
```

停止：`./end.sh`

#### Docker

Copilot 镜像为薄沙箱（`text-cli-copilot`）：只含 Python 环境 + 代码种子(seed)，代码外挂宿主机，首次由 entrypoint 从 seed 填充。

```bash
# 构建上下文（先跑 build.py 生成 .build/）
cd deploy/skeleton-container && python build.py

# 启动：host 网络 + 外挂 runtime
# 🚨 红线：copilot 仅 127.0.0.1 可达，【绝不 -p 20260:20260 暴露到 0.0.0.0】
docker run -d --network=host \
  -v ./runtime:/app/runtime \
  text-cli-copilot:latest
```

**验证**（三平台相同）：

```bash
curl http://127.0.0.1:20260/text-cli/health
# → {"status":"ok"}
```

> **红线**：copilot 的默认 token 为空（不校验），安全完全依赖 `127.0.0.1` 回环边界。把它暴露到网络（`-p 20260` 或非 host 网络监听 0.0.0.0）等于把本机特权代理裸奔，**严禁**。

> 其他配置项（鉴权、日志级别、查询语言等）见 [§1.5 配置](#15-配置)。

### 1.2 Service

Service 制品为 `text-cli-A3-v*` 到 `A9-v*`（层号越高能力越多，每层可独立部署）。所有层级包含 Copilot——如果你只部署了 Service 制品，Copilot 也会启动。**不需要两个制品分别部署。**

#### Windows

`start.bat` 是统一启动入口——自动设 `TEXT_CLI_HOME` + `TEXT_CLI_PACKAGE_SOURCE_DIRS`，拉起 Copilot (:20260) + Service (:28050)。终端输出会显示 `TEXT_CLI_PACKAGE_SOURCE_DIRS` 状态（`[OK]` 或 `[WARN]` 含英文引导）。**运行方式二选一：**

```powershell
# PowerShell
Expand-Archive text-cli-A9-v*.zip -DestinationPath .
Start-Process -FilePath "start.bat" -WorkingDirectory "text-cli-A9-v*"
```

```cmd
:: cmd
cd text-cli-A9-v*
start.bat
```

停止：`.\end.bat`（按端口 20260/28050/9020 停止三服务）

#### Linux

```bash
tar -xzf text-cli-A9-v*.tar.gz
cd text-cli-A9-v*
chmod +x start.sh
./start.sh
```

停止：`./end.sh`（`fuser -k` 按端口停止）

> macOS：部署同 Linux（`.tar.gz`，`bash start.sh`）。

#### Docker

Service 镜像为薄沙箱：只含 Python 环境 + 代码种子(seed)，代码/包/数据外挂宿主机，首次由 entrypoint 从 seed 填充，之后宿主托管（热更新不 rebuild）。

Service 制品按层分发：`text-cli-service`（A3，copilot+service）与 `text-cli-advanced`（A9，copilot+service+MCP+aggregate）。两者镜像结构相同，A9 多 MCP 端口与 aggregate。**任意层都含 copilot，不需单独部署 Copilot。**

**构建（任选一层）**：
```bash
cd deploy/skeleton-container && python build.py   # 生成 .build/ 构建上下文
```

**A3（`text-cli-service` 镜像）**：
```bash
docker run -d --name tc-service \
  -p 28050:28050 \
  -v ./runtime:/app/runtime \
  -v ./data:/app/data \
  -v ./packages:/packages \
  -e TEXT_CLI_PACKAGE_SOURCE_DIRS=/packages \
  -e PORT=28050 \
  text-cli-service:latest
```

**A9（`text-cli-advanced` 镜像，推荐全量）**：
```bash
docker run -d --name tc-advanced \
  -p 28050:28050 \
  -p 9020:9020 \
  -v ./runtime:/app/runtime \
  -v ./data:/app/data \
  -v ./packages:/packages \
  -e TEXT_CLI_PACKAGE_SOURCE_DIRS=/packages \
  -e PORT=28050 \
  -e MCP_PORT=9020 \
  text-cli-advanced:latest
```

> **🚨 copilot(:20260) 不对外映射**——copilot 绑 127.0.0.1，仅本机回环可达（红线，见 §1.1）。服务间经内部 proxy 访问，不需 `-p 20260`。

**验证**：

```bash
# service (A3/A9)
curl http://localhost:28050/text-cli/health
# → {"status":"ok","domains":["key","quota","task","text-cli"],"sqlite":"enabled"}

# 指令列表
curl -X POST http://localhost:28050/text-cli/cli \
  -H "Content-Type: application/json" \
  -d '{"prompt":"AI:text-cli;query,compact"}'

# MCP (A9 / A7+)
curl http://localhost:9020/...
```

#### 包源路径

install 指令需要知道指令包放在哪。环境变量 `TEXT_CLI_PACKAGE_SOURCE_DIRS` 默认指向制品同级目录的 `packages/`。`start.bat` / `start.sh` 启动时检测——目录存在输出 `[OK]`，不存在输出 `[WARN]` 并提示创建。

容器形态：把 `packages/` 外挂到镜像内并设 env 即可——`-v ./packages:/packages -e TEXT_CLI_PACKAGE_SOURCE_DIRS=/packages`（见上文 A3/A9 运行示例），启动时同样检测 `[OK]`/`[WARN]`。

> 其他配置项（鉴权、日志级别、查询语言等）见 [§1.5 配置](#15-配置)。

### 1.3 Endpoint

Endpoint 为独立制品 `text-cli-endpoint-python-v*`（Win `.zip` / Linux `.tar.gz` / Docker）。

#### Windows

```powershell
Expand-Archive text-cli-endpoint-python-v*.zip -DestinationPath .
cd text-cli-endpoint-python-v*
# PowerShell
Start-Process -FilePath "start-endpoint.bat"
# 停止: .\end-endpoint.bat
```

#### Linux

```bash
tar -xzf text-cli-endpoint-python-v*.tar.gz
cd text-cli-endpoint-python-v*
./start.sh   # 停止: ./end.sh
```

#### Docker

Endpoint 镜像为 `text-cli-endpoint`（独立制品，A5，由 `build-endpoint.py` 单独构建，不含在 A2-A9 累积制品里）。

```bash
docker run -d --name tc-endpoint \
  -p 29050:29050 \
  -e A3_BACKENDS=http://service:28050 \
  text-cli-endpoint:latest
```

`start-endpoint.bat` / `start.sh` 自动创建 `.venv` 并安装依赖。详细配置参数见第四章（`backends.yaml` / `A3_BACKENDS` / `ACCESS_TOKEN_REQUIRED` 等）。

**验证**：

```bash
curl http://localhost:29050/text-cli/health
# → {"liveness":true,"schema":true,"backends":[...]}
```

> Endpoint 配置（`backends.yaml`、Token、限流参数）见 [§1.5 配置](#15-配置)。

### 1.4 协议

三个产品使用完全相同的协议——只需学一次。

**指令语法**：

```
AI:<domain>;<action>,<param1>,<param2>,...
```

**请求格式**（字段名为 `prompt`，不是 `directive`）：

```bash
curl -X POST http://localhost:<port>/text-cli/cli \
  -H "Content-Type: application/json" \
  -d '{"prompt":"AI:domain;action,params"}'
```

**响应信封**：

```json
{"rst_types": "text", "rst_data": {"status":"ok","result":14}, "rst_err": ""}
```


- `rst_types`：反映响应类型。默认为 `"text"`。当 handler 在返回字典中包含 `pray_rst_types` 键时，骨架将其值提升至此字段。取值：`text` / `picture` / `video` / `audio` / `file`。
- `rst_data`：handler 返回的 JSON 对象，骨架直接承载 —— 不再以 `{"text": "..."}` 嵌套。调用方直接读取 `rst_data` 即可。
- `rst_err`：结构化错误字段。空字符串 `""` 表示成功，非空表示失败。错误码（见下方错误码速查）。

**内容类型映射**（据 `rst_types` 值）：

| `rst_types` | 调用方行为 |
|------------|-----------|
| `"text"` | 直接展示 `rst_data` |
| `"picture"` | 渲染 `rst_data.url` |
| `"video"` | 渲染 `rst_data.url` |
| `"audio"` | 渲染 `rst_data.url` |
| `"file"` | 渲染 `rst_data.url` |


**错误码速查**：

| 错误码 | 含义 | 常见场景 |
|--------|------|---------|
| `ERR_NOT_FOUND` | 指令不存在 | 未安装对应指令包 |
| `ERR_EXECUTION` | 执行失败 | handler 内部异常 |
| `ERR_ROUTING` | 路由失败 | proxy 目的地不可达 |
| `INVALID_PARAMS` | 参数不合法 | 必填参数缺失或格式错误 |
| `ACCESS_DENIED` | Access Token 无效 | Endpoint 鉴权失败 |
| `SERVICE_DENIED` | Service Token 无效或**明确拒止**（非配额耗尽） | 提供方拒止（配额耗尽走 `status:stop` 降级链，见 §3.11，不返回此错误码） |

> **示例约定**：为阅读简洁，本手册所有 `→ {...}` 指令调用示例**仅展示 `rst_data` 字段的内容**（handler 返回的 JSON 对象，骨架直接承载于 `rst_data`）；真实 HTTP 响应一律为上方**响应信封**格式。调用方规则：**直接读取 `rst_data`**；仅当 `rst_types="text"` 且数据恰为 `{"text": ...}` 形态（个别 handler 的业务返回含 `text` 字段）时才取 `.text`，其余情况按内容类型映射直接使用 `rst_data`（如 `picture`/`video`/`audio`/`file` 取 `.url`）。例如端到端验证中的 tc-math 示例 `→ {"status":"ok","result":7}` 即 `rst_data` 本身。

**端到端验证**（Service 端口）：

```bash
# 查看已安装指令
curl -s -X POST http://localhost:28050/text-cli/cli \
  -d '{"prompt":"AI:text-cli;query,compact"}'

# 安装 tc-math（零依赖算术求值器）
curl -s -X POST http://localhost:28050/text-cli/cli \
  -d '{"prompt":"AI:text-cli;install,tc-math"}'

# 调用——安装后即时生效
curl -s -X POST http://localhost:28050/text-cli/cli \
  -d '{"prompt":"AI:tc-math;eval,1+2*3"}'
# → {"status":"ok","result":7}

# 路径编排——多条指令串成管道（单 JSON 自包含，无需文件/外部输入）
curl -s -X POST http://localhost:28050/text-cli/cli \
  -d '{"prompt":"AI:text-cli;path,{\"id\":\"pythagorean-fixed\",\"steps\":[{\"id\":\"sq_a\",\"instruction\":\"tc-math;eval,3**2\",\"output_as\":\"a2\"},{\"id\":\"sq_b\",\"instruction\":\"tc-math;eval,4**2\",\"output_as\":\"b2\"},{\"id\":\"sum\",\"instruction\":\"tc-math;eval,{a2.result}+{b2.result}\",\"output_as\":\"s\"},{\"id\":\"root\",\"instruction\":\"tc-math;eval,sqrt({s.result})\",\"output_as\":\"hyp\"}]"}'
# → {"status":"ok","result":5.0}   # 3²+4²=25 → √25

# 两种发射形态（单/双 JSON）与 input 语义见 §3.7
```

### 1.5 配置

text-cli 运行时会从 `$TEXT_CLI_HOME/service/config/text_cli.yaml` 读取配置。首次启动时，`start.bat` / `start.sh` 会自动从同目录的 `text_cli.example.yaml` 复制一份（如文件尚不存在）。

**配置优先级**：环境变量 > YAML 值 > 内置默认值。

```yaml
# $TEXT_CLI_HOME/service/config/text_cli.yaml
server:
  port: 28050               # Service HTTP 端口
  log_level: info            # 日志级别: debug | info | warning | error
  instructions_language: auto  # 指令查询默认语言: zh | en | auto

auth:
  service_token: ""          # Service Token 共享密钥：非空=强制模式（所有请求必须携带且匹配，缺失/不匹配一律拒绝）
  allow_anonymous: true      # 匿名访问（仅在 service_token 为空时生效）：true=内网模式允许匿名（产品默认），false=无身份码请求一律拒绝
  count_calls: false          # 是否记录调用审计日志

live_config:
  enabled: false             # 配置热更新闸门开关（AI:text-cli;config 元指令，默认关闭）
  token: ""                  # live-config 独立 token（独立于 auth.service_token）

paths:
  # TEXT_CLI_HOME 由启动脚本注入，不可在此配置
  packages: ../packages      # 指令包源目录
  # map 循环原语（mode:"map"）— path 引擎对集合逐元素迭代执行
  map_enabled: false         # 是否启用 map 能力（默认关闭。map 是入站能力，部署者须显式开启）
  map_max_iter: 100          # 单次 map 扇出上限（1–1000，超过代码硬上限自动钳制）

mcp:
  service_url: ""            # MCP 出向 Service 地址
  port: 9020                 # MCP 出向 FastMCP 端口

mesh:
  require_credentials: false  # 联邦 Mesh 安全：true=凭证缺失时拒绝跨跳，false(默认)=降级转发+标注 _mesh_credential_degraded
  multi_hop_enabled: false    # 多跳跟随（默认关闭，部署者显式开启）
  multi_hop_max_depth: 3      # 多跳深度上限（1–5，超过代码硬天花板自动钳制）
```

**关键配置项说明**：

| 配置 | 默认值 | 说明 |
|------|--------|------|
| `server.instructions_language` | `auto` | query 输出语言。`auto` = 规范字段（英文）；`zh` / `en` = 优先对应本地化字段。调用方可尾参覆盖：`AI:text-cli;query,zh` |
| `auth.service_token` | `""` | **非空 = 强制模式**：所有请求必须携带且匹配此密钥，缺失/不匹配一律拒绝（不落匿名分支）；匹配后按 token 尾码 / A5 注入身份做 registry 准入 |
| `auth.allow_anonymous` | `true` | **仅在 `service_token` 为空时生效**。`true` = 内网模式（产品默认）：无身份码请求以匿名放行，仅适用于**完全受信的内网/本机**；只要 Service 监听 `0.0.0.0` 且可被非受信网络路由到，应设 `service_token` 进入强制模式（或 `allow_anonymous: false` 拒绝无身份请求）。对公网暴露务必前置 Endpoint（§1.3 + §四） |
| `live_config.enabled` | `false` | 配置热更新闸门开关（`AI:text-cli;config` 元指令，运行时特性，见 §3.3 内置域）。默认关闭——关闭时指令返回 disabled 提示 |
| `live_config.token` | `""` | live-config 独立 token（独立于 `auth.service_token`，为内网匿名模式的二次防线）。为空时指令不可用 |
| `paths.packages` | `../packages` | `text-cli;install` 扫描指令包的目录 |
| `paths.map_enabled` | `false` | 控制 `mode:"map"` 是否生效。map 是入站能力，默认关闭。部署者设 `true` 开启。env：`MAP_ENABLED=true/false` |
| `paths.map_max_iter` | `100` | map 单次迭代元素上限。部署者按需调整（≤1000 代码硬上限）。LLM 无需感知此配置。env：`MAP_MAX_ITER=<n>` |
| `mesh.require_credentials` | `false` | 联邦 Mesh 安全：`true`=凭证缺失时拒绝跨跳转发，`false`(默认)=降级转发+标注 `_mesh_credential_degraded`。env：`REQUIRE_CREDENTIALS=true/false` |
| `mesh.multi_hop_enabled` | `false` | 控制 proxy 是否跟随下游 `_mesh_redirect` 进行多跳转发。默认关闭——多跳使请求路径超出部署者直接控制范围，需显式开启。env：`MULTI_HOP_ENABLED=true/false` |
| `mesh.multi_hop_max_depth` | `3` | 多跳跟随的最大跳数。部署者在 yaml 调（≤5 代码硬天花板）。env：`MULTI_HOP_MAX_DEPTH=<n>` |

> 完整配置说明见制品内 `service/config/text_cli.yaml` 文件注释。

### 1.6 Protocol（SDK）

所有制品解压后自带零依赖 Protocol SDK，位于 `protocol/` 目录。不需要手写 curl 和解析信封——SDK 直接返回结构化结果。完整 API 参考见 [§四](#四protocol)。

**命令行一键调用**（human）：

```bash
# Shell（Linux/macOS）
echo "AI:tc-math;eval,2+3*4" | ./protocol/shell/call.sh

# PowerShell（Windows）
./protocol/shell/call.ps1 "AI:tc-math;eval,2+3*4"

# 查询异步任务
./protocol/shell/call.sh --task <task_id>
```

**SDK 调用**（AI Agent / 脚本）：

```python
# Python（零依赖，urllib 标准库）
import sys; sys.path.insert(0, "protocol/python")
from call import call, discover, poll

result = call("AI:tc-math;eval,2+3*4")
print(result.data)  # → {"status":"ok","result":14}

directives = discover(search="weather")  # 发现可用指令
status = poll("task-123")                 # 查询异步任务
```

```javascript
// Node.js（零依赖，内置 fetch）
const { call, discover } = require('./protocol/js/call');
const result = await call('AI:tc-math;eval,2+3*4');
console.log(result.data);
```

**默认端点**：`http://127.0.0.1:28050/text-cli/cli`。可通过 `protocol/*/conf.json` 或环境变量 `TEXT_CLI_ENDPOINT` 覆盖。

---

## 二、Copilot

Copilot 监听 `127.0.0.1:20260`，外部网络不可达。设计意图：只有你本机的人和程序能驱动它操作你的文件、终端和凭据。

### 2.1 自有包管理

```bash
curl -s -X POST http://localhost:20260/text-cli/cli \
  -d '{"prompt":"AI:text-cli;co-install,<package-name>"}'

curl -s -X POST http://localhost:20260/text-cli/cli \
  -d '{"prompt":"AI:text-cli;co-list"}'

curl -s -X POST http://localhost:20260/text-cli/cli \
  -d '{"prompt":"AI:text-cli;co-uninstall,<package-name>"}'
```

Copilot 使用 `import_module` 直接加载（新包）或 `_invalidate_package` + `import_module`（update）配合动态方法绑定——安装后即时生效，无需重启。包模型为 `*Handlers` mixin class + `_handle_*` 方法（与 Service 的 `@directive` 装饰器不同，二者不可混用）。（刻意设计：Copilot 持本机特权、Service 持网络可达，二者信任档位不同，故 handler 契约不互通；依 SPEC §6.2.1/§6.2.2，宿主特权包务必只用 `co-install` 装到 Copilot。）

### 2.2 白名单终端代理

`copilot/config/auxiliary_config.json` 控制可执行的操作：

```json
{
  "operations": {
    "domain;action": {
      "level": "read | write",
      "handler": "_handle_xxx",
      "parameters": ["param1", "param2"]
    }
  }
}
```

未声明 = 拒绝执行。首次启动从 `auxiliary_config.example.json` 自动初始化。详见附录 A。

### 2.3 技能桥接

外部 skill 可桥接为 text-cli 指令。安装包时自动从 handler.py 推断路由写入 `skill_bridge_routes.json`。调用时 Copilot 通过子进程执行外部 skill，结果适配为 text-cli 标准信封。

---

## 三、Service

Service 是所有指令包的核心调度平台。以下能力按累积层级组织——你的 Service 可能是 A3（基础），也可能是 A9（全量）。**所有能力无需 Copilot 即可独立工作。**

### Part A：包管理与指令发现（≥A3）

#### 3.1 安装指令包

```
AI:text-cli;install,<package-name>
```

install 链为**事务化**：校验 schema → 复制文件 → 安装依赖 → handler 试导入门禁 → 登记 → 热加载。任一事务步失败（依赖装不上、handler 导入失败）即**整体回滚**（`packages/`、schema、manifest 均无残留），返回顶层 `status: error`——不存在"manifest 显示已装、调用却报错"的半装状态。**安装成功后无需重启 Service**（update/--force 场景先清理旧注册和模块引用再重新 import，同样即时生效）；失败修复环境（如联网补依赖）后直接重装即可，**无需 `--force`**。

```bash
# 强制覆盖
curl ... -d '{"prompt":"AI:text-cli;install,tc-math,--force"}'

# 卸载（schema + packages + handler_inits 条目 + SQL 表全部清理）
curl ... -d '{"prompt":"AI:text-cli;uninstall,tc-math"}'
```

#### 3.2 指令发现

`AI:text-cli;query` 从 `handlers/schema/` 实时读取（每次调用为全目录扫描，O(n)）：高频调用建议缓存结果，或改用 `/text-cli/skills` 端点（§Part E 补充）拉取静态清单：

| 参数 | 效果 |
|------|------|
| 无参 | 按包分组 |
| `,json` | 结构化 JSON |
| `,compact` | 每行 `domain;action` |
| `,python\|js\|mcp` | 按 runtime 过滤 |
| `,category,<name>` | 按分类 |
| `,<keyword>` | 模糊搜索 |
| `,collection` | 精选指令集 |
| `,delta` | 变更比对 |

#### 3.3 内置域

| 域 | 能力 |
|------|------|
| `text-cli` | install / uninstall / export / export-all / packages / query / path / pro / config / sync-copilot |
| `key` | 密钥 CRUD |
| `quota` | 配额管理 |
| `task` | 异步任务生命周期 |

> 与 SPEC §6.2.1 元指令表面一致（8 条）：install / uninstall / export / export-all / packages / query / path / pro；`sync-copilot`（见 §3.18）与 `config`（见下）为运行时附加元指令（暂未纳入 SPEC）。

##### config 元指令（配置热更新 · 运行时特性）

```
AI:text-cli;config,<token>,<get|post>,<pkg>[,<json>]
```

免重启修改已装指令包的配置。闸门顺序：先查开关（`live_config.enabled`，默认关闭，关闭时返回 disabled 提示、不暴露 token 细节）→ 验独立 token（与 `auth.service_token` 无关，为内网匿名模式的二次防线）→ 校验包已安装 → 转发给该包 handler 的 `runtime_config` 钩子。包未实现钩子时返回 `does not support live-config`（此时按传统方式：改配置后重启，或 `install,<pkg>,--force` 重装）。

```bash
# 读当前配置（get）
curl ... -d '{"prompt":"AI:text-cli;config,<token>,get,image"}'
# → {"status":"ok","config":{...}}

# 应用新配置（post，写后读回显——同一步结果即可确认生效）
curl ... -d '{"prompt":"AI:text-cli;config,<token>,post,image,{\"allowed_paths\":[\"/data/media\"]}"}'
# → {"status":"ok","config":{"allowed_paths":["/data/media"]}}
```

> 运行时特性，暂未纳入 SPEC。包侧钩子契约（`runtime_config(action, payload)` 固定签名、get/post 同构回显）见包开发指南 §2.4.1；install 时运行时探测钩子并在 manifest 标记 `live_config`。

---

### Part B：路径编排（≥A4）

路径将多条指令串联成管道。数据单向流动——前一步输出通过插值注入后续步骤。

#### 3.4 第一个路径

写入 `$TEXT_CLI_HOME/paths/pythagorean.json`：

```json
{
  "id": "pythagorean", "type": "pipeline", "mode": "toolchain",
  "input_schema": {"type": "object", "properties": {"a": {"type":"number"}, "b": {"type":"number"}}},
  "steps": [
    {"id": "square", "instruction": "tc-math;eval,{input.a}**2+{input.b}**2", "output_as": "squared"},
    {"id": "root",   "instruction": "tc-math;eval,sqrt({squared.result})", "output_as": "hypotenuse"}
  ]
}
```

```bash
curl ... -d '{"prompt":"AI:text-cli;path,pythagorean,{\"a\":3,\"b\":4}"}'
# → {"status":"ok","result":5.0}
```

**插值语法**：`{input.xxx}`（调用参数）/ `{变量名.field}`（前步输出）。支持深路径：`{geo.poi.0.name}`。

#### 3.5 条件分支与并行

```json
{"if": {"step": "calc", "field": "result", "equals": "5"}}
```

```json
{"id": "group", "mode": "parallel", "strategy": "all", "steps": [...]}
```

#### 3.6 降级递补

步骤失败时自动按 `degradation[]` 降级。全部失败返回 `DEGRADE_EXHAUSTED`。

#### 3.7 Inline JSON 与注册

直接在请求体发路径 JSON（`{` 开头自动识别）。`--register` 将路径注册为 `runtime=pipeline` 可发现指令。

临时编排支持**两种发射形态**：

| 形态 | 语法 | 适用场景 |
|------|------|---------|
| **双 JSON**（带外部输入） | `AI:text-cli;path,{...路径...},{...输入参数...}` | 路径引用 `{input.xxx}`，需要调用方传参（通用/可复用管道） |
| **单 JSON**（自包含，⭐ 轻量） | `AI:text-cli;path,{...路径...}` | 路径**硬编码起点 + 跨步插值**，不需要外部输入（一次性验证/确定场景） |

**要点**：
- 路径里用了 `{input.xxx}` 就必须带第二段 JSON，否则插值缺失、指令收到原样模板（如 tc-math 报 `unsupported AST node: Set`）
- 路径不引用 input（硬编码 + `{变量.field}` 内部数据流）时，单 JSON 即可，省掉 `input_schema` 和参数
- **推荐习惯**：验证/确定场景用单 JSON（快）；要复用/传参才用双 JSON（配合 `--register` 沉淀为可发现指令）

**单 JSON 示例**（勾股定理，硬编码 3/4 + 跨步插值，即 §1.4 端到端示例）：

```bash
curl -s -X POST http://localhost:28050/text-cli/cli \
  -d '{"prompt":"AI:text-cli;path,{\"id\":\"pythagorean-fixed\",\"steps\":[{\"id\":\"sq_a\",\"instruction\":\"tc-math;eval,3**2\",\"output_as\":\"a2\"},{\"id\":\"sq_b\",\"instruction\":\"tc-math;eval,4**2\",\"output_as\":\"b2\"},{\"id\":\"sum\",\"instruction\":\"tc-math;eval,{a2.result}+{b2.result}\",\"output_as\":\"s\"},{\"id\":\"root\",\"instruction\":\"tc-math;eval,sqrt({s.result})\",\"output_as\":\"hyp\"}]"}'
# → {"status":"ok","result":5.0}
```

**双 JSON 示例**（同一路径参数化，文件版见 §3.4）：`AI:text-cli;path,{...路径, 含 input_schema...},{...input...}`——inline 或文件均可，input 经 `{input.xxx}` 插值注入。

#### 3.8 跨节点

`steps[].source` 逐步骤指定远端 Service——一条管道的不同步骤发到不同机器。

#### 3.9 循环迭代（map）

`mode:"map"` 对集合逐元素执行同一套子步骤。数据单向流动——元素绑定 `{item}`，每轮末步输出经 `collect_as` 累积为列表供下游消费。

> **前置条件**：map 默认关闭。须先在 `service/config/text_cli.yaml` 设 `paths.map_enabled: true` 并重启。

写入 `$TEXT_CLI_HOME/paths/summarize.json`：

```json
{
  "id": "summarize", "type": "pipeline",
  "steps": [
    {"instruction": "tc-json;query,select * from files", "output_as": "urls"},
    {
      "mode": "map", "items": "urls", "output_as": "summaries",
      "steps": [
        {"instruction": "tc-markdown;read,{item}", "output_as": "doc"},
        {"instruction": "ai;infer,摘要：{doc}", "output_as": "summary"}
      ]
    },
    {"instruction": "ai;infer,汇总：{summaries}", "output_as": "report"}
  ]
}
```

```bash
curl ... -d '{"prompt":"AI:text-cli;path,summarize"}'
# → 对每个 URL 读取文档 → AI 摘要 → 汇总所有摘要为报告
```

| 字段 | 必填 | 默认值 | 说明 |
|------|:---:|------|------|
| `mode` | ✓ | — | 固定 `"map"` |
| `items` | ✓ | — | 集合变量名，取值须为 list |
| `as` | ✗ | `"item"` | 元素绑定名，body 用 `{item}` |
| `steps` | ✓ | — | 子步骤数组 |
| `collect_as` | ✗ | = `output_as` | 收集变量名 |
| `on_error` | ✗ | `"break"` | `break`（熔断）/ `continue`（跳过） |
| `concurrency` | ✗ | `"serial"` | `serial` / `parallel` |

> **安全说明**：单次 map 扇出受 `paths.map_max_iter` 限制（默认 100，上限 1000）。超限返回 `INVALID_PARAMS`，需调高 yaml 配置。禁止嵌套 map（map 内不能再用 map）。

---

### Part C：状态持久化（≥A6）

#### 3.9 密钥管理

```
AI:key;register,<svc>,<v1>,<v2>,<type>
AI:key;list
AI:key;get,<svc>
AI:key;revoke,<svc>
```

> `key;get` 的安全边界见 §3.19。

#### 3.10 任务管理

| 模式 | 触发 | 执行者 | 轮询 |
|------|------|--------|------|
| managed | `--async` | Service `asyncio.create_task` | `GET /text-cli/tasks/{id}` |
| tracked | `task;track` | 外部服务 | `task;status` 按需 poll |

任务状态共 5 个终态：`pending` → `running` → `done` / `error` / `cancelled`。`task;cancel` 将 `pending`/`running` 任务置为 `cancelled` 终态（不可恢复）。Service 重启时将残留 `running` 任务标记为 `error`。

```bash
# managed
curl ... -d '{"prompt":"AI:tc-math;eval,1+2*3,--async"}'
# → {"status":"pending","task_id":"..."}
curl http://localhost:28050/text-cli/tasks/<task_id>

# tracked
curl ... -d '{"prompt":"AI:task;track,id-001,hello,world,user"}'
curl ... -d '{"prompt":"AI:task;status,id-001"}'
curl ... -d '{"prompt":"AI:task;cancel,id-001"}'
```

#### 3.11 配额管理

```bash
curl ... -d '{"prompt":"AI:quota;register,my-svc,day,10"}'
curl ... -d '{"prompt":"AI:quota;check,my-svc"}'       # 原子消耗
# → {"status":"ok","remaining":9}
# 耗尽 → {"status":"stop"}  # 降级链自动切换
curl ... -d '{"prompt":"AI:quota;reset,my-svc"}'
curl ... -d '{"prompt":"AI:quota;unregister,my-svc"}'
```

`amount` 默认 1（按次数），可传数值按字符/字节。cycle：`day`/`week`/`month`/`year`/`forever`。

#### 3.12 跨层组合：Task + Path

task-manager（Part C）和 path-engine（Part B）通过 `domain;action` 协议松耦合——task 层只管 SQLite 生命周期，path 层只管步骤编排。tracked 任务不区分目标是原子指令还是路径，注册方式完全相同。

**示例**：把勾股定理路径注册为异步追踪任务。

1. 准备路径文件 `$TEXT_CLI_HOME/paths/pythagorean-async.json`（与 3.4 相同，每步加 `timeout: 5000`）

2. 注册追踪任务：

```bash
curl ... -d '{"prompt":"AI:task;track,path-001,text-cli,path,pythagorean-async,{\"a\":6,\"b\":8}"}'
# → {"status":"ok","task_id":"path-001","mode":"tracked"}
```

3. 多时间点轮询——tracked 模式下任务不自动执行，`state` 稳定为 `pending`：

```bash
curl ... -d '{"prompt":"AI:task;list"}'
# → [{"task_id":"path-001","domain":"text-cli","action":"path","state":"pending"}]

curl ... -d '{"prompt":"AI:task;status,path-001"}'
# → {"state":"pending","params":{"mode":"tracked","poll":{"domain":"text-cli","action":"path","params":["pythagorean-async",{"a":6,"b":8}]}}}

curl ... -d '{"prompt":"AI:task;cancel,path-001"}'
# → {"cancelled":true}
```

**设计要点**：task-manager 不关心 path-engine 的内部结构——它只需要 `domain=text-cli`、`action=path`。路径的 `timeout` 字段作为调度元数据跨层传递，为 managed 模式预留执行预算信息。这是 text-cli 的核心哲学：**每层只做一件事，层与层通过协议而非接口对接**。

---

### Part D：MCP 桥接（≥A7）

MCP（Model Context Protocol）桥接是 A7 层的**可选能力**——A8 聚合、A9 门面不需要 MCP 即可完整工作。MCP 不可用不影响路径编排、配额管理、聚合降级等任何其他功能。

> text-cli 的 MCP 桥接不绑定特定 CLI——当前仅支持 [mcporter](https://github.com/weihai-limh/mcporter)，未来可按需接入其他 MCP 客户端。

#### 3.13 入向能力依赖

MCP 指令包（`runtime:"mcp"`）的 install 和 query **始终可用**——无需任何外部依赖。但实际调用 MCP 工具需要 mcporter 作为协议执行层。

| 依赖满足度 | mcporter | install / query | dispatch（调用 MCP 工具） | A8/A9 其他能力 |
|------|:--:|:--:|------|:--:|
| 无 mcporter | — | ✅ 可安装、可见 | ❌ fallback proxy，返回 `ERR_NOT_FOUND` | ✅ 完全不受影响 |
| 已安装 mcporter | ✅ | ✅ | ✅ 全链路 | ✅ |

#### 3.14 mcporter 获取与安装

**第一步：获取源码。**

从 [mcporter 仓库](https://github.com/weihai-limh/mcporter) clone 或下载 tgz 包：

```bash
git clone https://github.com/weihai-limh/mcporter.git
# 或下载 tgz：https://github.com/weihai-limh/mcporter/releases
```

**第二步：按 Node.js 版本选择对应的 mcporter。**

| Node.js 版本 | mcporter 版本 | 说明 |
|------|:--:|------|
| ≥20, <24 | **0.9.0** | 稳定，transport 用 `http` |
| ≥24 | **0.12.3** | 支持 `streamable-http` transport |

> 版本语法差异：
> - 0.9.0: `mcporter config add <name> --transport http --url <url>`
> - 0.12.3: `mcporter add <name> --transport streamable-http --url <url>`

**第三步：解压即用（无需 `npm install -g`）。**

tgz 包内含预编译的 `dist/cli.js`，可直接运行：

```bash
tar -xzf mcporter-0.9.0.tgz
node package/dist/cli.js --version
# → 0.9.0
```

建议创建包装脚本（Win 用 `.bat`，Linux/macOS 用 shell）指向 `node <dist/cli.js>`，然后将包装脚本放入 PATH。

**第四步：配置 MCP 服务端。**

```bash
# 0.9.0
mcporter config add github --transport http --url https://api.github.com/mcp
# 0.12.3
mcporter add github --transport streamable-http --url https://api.github.com/mcp

# 验证
mcporter list
mcporter list github
```

#### 3.15 Service 侧配置

安装 mcporter 后，Service 需要两份配置声明如何调用：

**mcporter.json** — 指定可执行文件路径（三层回退：显式配置 → `text_cli_modules/bin/` → PATH）：

```json
{"bin": "<path-to-mcporter-wrapper>", "cwd": "<mcporter-package-dir>"}
```

**routing_preferences.json** — 声明哪些指令走 MCP 管线：

```json
{"preferences": {"comcp-github;search_repos": "mcp"}}
```

#### 3.16 端到端验证

```bash
# 安装 MCP 包
curl ... -d '{"prompt":"AI:text-cli;install,tc-mcp-github"}'

# 调用——完整链路：
# decide_backend → routing_preferences → "mcp"
# → call_mcp_tool → subprocess.run(mcporter call server.tool --args '{...}')
curl ... -d '{"prompt":"AI:comcp-github;search_repos,text-cli"}'
```

#### 3.17 出向暴露

`mcp_exposure.json` 声明对外暴露的指令。FastMCP (:9020) 读此清单动态生成 MCP tools——任何 MCP 客户端可发现并调用 text-cli 指令。桥是双向的。

---

### Part E：联动（可选）

以下能力在 Service 独立运行时不需要——仅当你同时部署了 Copilot 或 Endpoint 才生效。

#### 3.18 Service → Copilot 透明代理

```bash
curl ... -d '{"prompt":"AI:text-cli;sync-copilot"}'
```

`sync-copilot` 发现 Copilot 指令 → 生成 `proxy_routes.json`。此后对 Service 的请求在本地未命中时自动转发 Copilot——调用方不感知背后是谁。

#### 3.19 密钥安全边界

`key;get` 由 Copilot 的 `KeyRouter` 处理（非 Service 直接暴露）。需 `copilot/config/key_routing.json` 声明获取方式：

```json
{"service-a": {"source": "env", "var": "KEY"}, "service-b": {"source": "service"}}
```

`source: "env"` 从环境变量读，`source: "service"` 委托 Service SQLite。未声明的 key 返回 `not_found`——安全边界，防止 Copilot 无限制暴露密钥。详见附录 F。

#### 3.20 部署在 Endpoint 后方

Endpoint 部署在公网入口，Service 在内网。`A3_BACKENDS` 指向 Service 地址后，Endpoint 透传请求并附加三层安全防线（见第四章）。

---

### Part E 补充：对外暴露（Skills）

Service 通过 `/text-cli/skills` 端点向 Endpoint 暴露已注册指令清单。这是 Endpoint 聚合后端指令表的唯一数据源。

- 路径通过 `path,<name>,--register` 注册后自动纳入 skills
- 指令包安装后其 directives 自动可见（随 hot-reload 即时生效）
- 格式：`{skill_id: {visibility, type, domain, action, ...}}`

在部署 Endpoint 之前，确保 Service 已启动且目标路径/指令包已注册——Endpoint 启动时从此端点拉取指令表。

```bash
# 验证 skills 端点
curl http://localhost:28050/text-cli/skills
# → {"branch-demo": {"visibility":"public","type":"pipeline",...}}
```

---

### Part F：门面与聚合（≥A8/A9）

#### 3.21 `text-cli;pro` 简名映射

```bash
curl ... -d '{"prompt":"AI:text-cli;pro,calc,1+2+3"}'
# → {"status":"ok","result":6}
```

`service/config/pro_registry.json`（附录 E）定义简名→目标映射。两种 target：`aggregate`（原子指令）和 `path`（路径引擎）。

#### 3.22 聚合降级链

`aggregate/map.json`（附录 D）定义多提供方降级顺序。配额耗尽自动切换，调用方无感知。显性指定 provider：`AI:map;geocode,北京,gd-map`。

---

## 四、Protocol

Protocol 是 text-cli 的零依赖消费端 SDK，随所有分发包一同分发——解压制品后，`protocol/` 目录即为完整 SDK。无需安装、无需配置依赖，一份脚本就能调用 text-cli 服务。

### 4.1 目录结构与获取

所有制品（Copilot / Service / Endpoint）的 zip/tar.gz 均包含根级 `protocol/` 目录：

```
text-cli-A9-v0_1_1.zip
├── text-cli-A9-v0_1_1/    ← runtime
├── packages/               ← 指令包源
└── protocol/               ← Protocol SDK
    ├── python/
    │   ├── call.py          ← Python SDK 入口
    │   └── conf.json        ← 端点配置
    ├── js/
    │   ├── call.js          ← JavaScript SDK 入口
    │   └── conf.json
    └── shell/
        ├── call.sh          ← Bash CLI
        ├── call.ps1         ← PowerShell CLI
        └── conf.json
```

### 4.2 配置与端点

**默认端点**：`http://127.0.0.1:28050/text-cli/cli`。

四语言实现通过 `conf.json` 声明默认值：

```json
{
  "endpoint": "http://127.0.0.1:28050/text-cli/cli",
  "service_token": "",
  "access_token": ""
}
```

**配置优先级（由高到低）**：

```
1. 按调用传入的参数（call() 的 endpoint/token 参数）
2. 环境变量（TEXT_CLI_ENDPOINT / TEXT_CLI_SERVICE_TOKEN / TEXT_CLI_ACCESS_TOKEN）
3. conf.json（与脚本同目录）
4. 内置默认值（127.0.0.1:28050）
```

**直连 / 经 Endpoint 两模式**：
- 直连 Service：只设 `service_token`，`access_token` 留空
- 经 Endpoint：`endpoint` 指向 :29050，同时设 `access_token` 和 `service_token`

### 4.3 命令行 CLI

**Shell**（`protocol/shell/call.sh`）——curl + python3，适合管道：

```bash
echo "AI:tc-math;eval,2+3*4" | ./protocol/shell/call.sh
# → {"status":"ok","result":14}

echo "AI:weather;query,Beijing" | ./protocol/shell/call.sh
# → {"city":"Beijing","temp":22}

# 查询异步任务
./protocol/shell/call.sh --task <task_id>
# → {"state":"running","progress":"50%"}
```

**PowerShell**（`protocol/shell/call.ps1`）：

```powershell
./protocol/shell/call.ps1 "AI:tc-math;eval,2+3*4"
./protocol/shell/call.ps1 -Task "task-abc123"
```

### 4.4 Python SDK

（`protocol/python/call.py`，零依赖，urllib 实现）

```python
import sys; sys.path.insert(0, "protocol/python")
from call import call, discover, poll, wait
```

#### call() — 同步调用

```python
result = call("AI:tc-math;eval,2+3*4")
# → DirectiveResult(ok=True, data={"status":"ok","result":14})

# 按调用覆盖端点和 Token
result = call(
    "AI:weather;query,Beijing",
    endpoint="http://192.168.1.2:28050/text-cli/cli",
    service_token="sk-abc123",
)
```

#### discover() — 指令发现

```python
# 全量发现（首次 HTTP 调用后缓存）
all_directives = discover()

# 过滤搜索
weather = discover(search="weather")
python_pkgs = discover(runtime="python")

# 强制刷新缓存
fresh = discover(force_refresh=True)
```

结果格式为 `[{domain, action, usage, runtime, description, ...}]`。

#### poll() / wait() — 异步任务

见 [§4.7](#47-异步任务)。

### 4.5 JavaScript SDK

（`protocol/js/call.js`，零依赖，内置 fetch）

```javascript
const { call, discover, poll, wait } = require('./protocol/js/call');

const result = await call('AI:tc-math;eval,2+3*4');
console.log(result.data);  // → {"status":"ok","result":14}

const directives = await discover({ search: 'weather' });

// 接 Endpoint 时传入 Token
const r = await call('AI:text-cli;query', null, null, {
  endpoint: 'http://localhost:29050/text-cli/cli',
  accessToken: 'at-xxx',
  serviceToken: 'sk-abc123',
});
```

API 与 Python 等价：`call()` / `discover()` / `poll()` / `wait()`，返回 `DirectiveResult`。

### 4.6 DirectiveResult 参考

所有 SDK 统一返回 `DirectiveResult` 对象。调用方通过字段判断状态，无需手动解析 HTTP 信封。

| 字段 | 类型 | 说明 |
|------|------|------|
| `ok` | `bool` | 调用是否成功（`rst_err` 为空且非异步） |
| `data` | `Any` | 响应数据——`rst_data` 直接承载，不再经 `.text` 嵌套 |
| `rtype` | `str` | 响应类型：`"text"` / `"picture"` / `"video"` / `"audio"` / `"file"` |
| `err_code` | `str` | 错误码。成功时为空字符串 |
| `directive` | `str` | 本次调用的原始指令（用于日志和调试） |
| `is_async` | `bool` | 是否为异步任务。`True` 时需用 `poll()` / `wait()` 获取最终结果 |

```python
result = call("AI:weather;query,Beijing")
if not result.ok:
    print(f"Error [{result.err_code}]: {result.data}")
    return
print(f"OK: {result.data}")
```

### 4.7 异步任务

长任务（视频转换、ASR 等）通过 `--async` 触发。调用方有两种等待方式：

**poll() — 单次查询**：

```python
status = poll("task-abc123")
# → DirectiveResult(is_async=True, data={"state":"running","progress":"step 3/8"})
```

**wait() — 指数退避等待**：

```python
# 自动轮询直到完成，每次回调 on_status
final = wait("task-abc123", on_status=lambda s: print(s.get("state")))
# → DirectiveResult(ok=True, data={"path":"/media/out.mp4"})

# 自定义退避参数（初始间隔 2s，最大间隔 30s）
final = wait("task-abc123", initial=2.0, maximum=30.0)
```

JavaScript 等价：`poll("task-abc123")` / `await wait("task-abc123")`。

### 4.8 调用示例

```python
from call import call, discover, poll, wait

# 1. 发现指令
dirs = discover(search="weather")
# → [{"domain":"weather","action":"query","usage":"weather;query,<city>"}]

# 2. 同步调用
r = call("AI:tc-math;eval,2+3*4")
assert r.ok and r.data["result"] == 14

# 3. 异步调用 + 等待完成
r = call("AI:ffmpeg;convert,video.mp4,--async")
if r.is_async:
    final = wait(r.task_id)    # 指数退避自动轮询
    print(final.data)

# 4. 错误处理
r = call("AI:nonexistent;action")
if not r.ok:
    print(f"[{r.err_code}] {r.data}")  # → [ERR_NOT_FOUND] ...
```

---

## 五、Endpoint

Endpoint 是独立旁路网关，部署在公网入口，Service 在内网。调用方请求 Endpoint (:29050)，鉴权后透传至 Service (:28050)。

### 5.1 部署

制品 `text-cli-endpoint-python-v*`：

```powershell
# Win (PowerShell)
Expand-Archive text-cli-endpoint-python-v*.zip -DestinationPath .
cd text-cli-endpoint-python-v*
pip install fastapi uvicorn httpx pydantic
.\start-endpoint.bat
# 停止: .\end-endpoint.bat
```

```bash
# Linux
tar -xzf text-cli-endpoint-python-v*.tar.gz
cd text-cli-endpoint-python-v*
pip install fastapi uvicorn httpx pydantic
./start.sh
```

```bash
# Docker
# 🚨 endpoint 是独立的 A5 制品，由 build-endpoint.py 构建，不含在 A2-A9 累积制品里
docker run -d -p 29050:29050 \
  -e A3_BACKENDS=http://service:28050 \
  text-cli-endpoint:latest
```

### 5.2 配置

| 变量/文件 | 默认值 | 说明 |
|------|--------|------|
| **`backends.yaml`**（推荐） | — | 多后端定义文件，每个 backend 自包含 url/token/st_prefix |
| `A3_BACKENDS` | —（必设） | Service 地址，逗号分隔多个后端（备选：无 yaml 时使用） |
| `ACCESS_TOKEN_REQUIRED` | `true` | 是否强制 Bearer Token 鉴权 |
| `ENDPOINT_BASE_URL` | `http://localhost:29050` | 自身地址，用于重写外部 Schema URL |
| `FORWARD_TIMEOUT` | `30` | 透传超时（秒） |

`backends.yaml` 格式——每个后端自包含，增删不影响相邻行：

```yaml
backends:
  - url: http://service1:28050
    token: ""        # 可选，透传至该后端的 Service Token
    st_prefix: ""    # 可选，该后端的 ST 前缀
  - url: http://service2:28050
```

不存在 `backends.yaml` 时自动回退 `A3_BACKENDS` 环境变量。`start-endpoint.bat` 启动时显示配置状态。

Endpoint 的指令表从 Service 的 `/text-cli/skills` 聚合而来——确保 Service 已启动且已注册路径/指令包后再部署 Endpoint（参见 Service §Part E 补充）。

### 5.3 三层安全防线

| 层 | 机制 | 超限 |
|:--:|------|:--:|
| 1 | IP 黑名单（CIDR） | 403 |
| 2 | 滑动窗口限流（默认 POST 1000/h, GET 10000/h，可由 `RATE_LIMIT_PER_HOUR` 覆盖） | 429 |
| 3 | Token 鉴权（Access Token + Service Token） | 401 |

### 5.4 可观测性

SQLite `data/textcli.db`：

| 表 | 内容 |
|------|------|
| `call_logs` | 逐请求日志（request_id / domain / action / status / response_time_ms） |
| `daily_stats` | 按天聚合（domain + action + date / call_count / success_count） |
| `access_tokens` | Token 管理（token_prefix / scopes / quota） |

### 5.5 透传

Endpoint 不执行指令——鉴权后直接转发至 `A3_BACKENDS`。调用方使用与 Service 相同的协议格式，仅端口从 28050 变 29050：

```bash
curl -X POST http://localhost:29050/text-cli/cli \
  -d '{"prompt":"AI:text-cli;path,branch-demo"}'
```

---


## 附录

### A. 白名单配置（auxiliary_config.json）

```json
{
  "server": {"host": "127.0.0.1", "port": 20260, "token": null},
  "security": {
    "path_whitelist": ["${TEXT_CLI_HOME}/", "${HOME}/"],
    "operations": {
      "domain;action": {
        "level": "read | write",
        "handler": "_handle_xxx",
        "parameters": ["param1", "param2"],
        "returns": "expected format"
      }
    }
  }
}
```

### B. 路径声明 Spec

```json
{
  "id": "unique-id", "type": "pipeline", "mode": "toolchain",
  // mode: "toolchain"(串行,默认) | "parallel"(并行) | "map"(循环迭代, A4+, 需 yaml 开启)
  "default_source": "http://192.168.1.2:28050/text-cli/cli",
  "input_schema": {"type": "object", "properties": {"p": {"type": "number"}}},
  "steps": [{
    "id": "s1", "instruction": "domain;action,{input.p}",
    "output_as": "v", "timeout": 5000,
    "if": {"step": "prev", "field": "status", "equals": "ok"},
    "degradation": [{"id": "fb", "instruction": "domain;fallback", "timeout": 10000}],
    "source": "http://192.168.1.3:28050/text-cli/cli"
  }]
}
```

支持 inline JSON（请求体直接发 `{...}`，无需文件；单/双发射形态见 §3.7）。

### C. MCP 配置

**routing_preferences.json**：
```json
{"preferences": {"comcp-github;search_repos": "mcp"}}
```

**mcporter.json**：
```json
{"bin": "<path>", "cwd": "<dir>"}
```

**mcp_exposure.json**（出向）：
```json
["tc-math;eval", "web-utils;fetch"]
```

**service-descriptor.json**（MCP 包必选）：
```json
{"mcp_server": "http://localhost:8080/mcp", "name": "my-svc"}
```

### D. 聚合路由表（aggregate/map.json）

```json
{
  "id": "map", "domain": "map",
  "default": ["provider-a", "provider-b"],
  "providers": {
    "provider-a": {"geocode": "provider-a;geocode"},
    "provider-b": {"geocode": "provider-b;geocode"}
  }
}
```

### E. 门面注册表（pro_registry.json）

```json
{
  "calc": {"type": "aggregate", "domain": "tc-math", "action": "eval"},
  "pythag": {"type": "path", "path": "pythagorean"}
}
```

### F. 密钥路由（key_routing.json）

```json
{
  "svc-a": {"source": "env", "var": "KEY"},
  "svc-b": {"source": "service"},
  "local": {"source": "env", "value": "sk-xxx"}
}
```

Copilot `KeyRouter` 读取此配置决定密钥来源。位于 `copilot/config/`。

### G. 环境变量速查

| 变量 | 产品 | 说明 |
|------|:--:|------|
| `TEXT_CLI_HOME` | Service | 数据根目录 |
| `TEXT_CLI_PACKAGE_SOURCE_DIRS` | Service | 包源目录 |
| `A3_BACKENDS` | Endpoint | 后端 Service 地址 |
| `ACCESS_TOKEN_REQUIRED` | Endpoint | Token 鉴权开关 |
| `RATE_LIMIT_PER_HOUR` | Endpoint | 限流 |
| `IP_BLACKLIST` | Endpoint | IP 黑名单（CIDR） |
| `TEXTCLI_SERVICE_URL` | MCP 出向 | Service 地址 |
| `MCP_PORT` | MCP 出向 | FastMCP 端口 |

### H. 配置文件索引（真相源职责）

text-cli 的运行时状态分散在若干 JSON/YAML 文件中，下表逐条标注"谁写、谁读、是否权威"，便于排查多套配置漂移：

| 文件 | 写入方 | 读取方 | 职责 |
|------|--------|--------|------|
| `config/installed_packages.json` | `text-cli;install` / `uninstall` | install 已装校验、`text-cli;config` 闸门、list/export | 已装包清单（含 `live_config` 探测标记，见 §3.3） |
| `handlers/schema/` | `text-cli;install` | `text-cli;query` 实时扫描 | 指令包 Schema（每次 query 全目录扫描，见 §3.2） |
| `proxy_routes.json` | `sync-copilot` | Service 代理转发 | Copilot 指令路由 |
| `/text-cli/skills` 端点 | Service 运行时 | Endpoint 聚合 | 对外暴露的指令清单（静态拉取，§Part E 补充） |
| `skill_bridge_routes.json` | 安装包时自动推断 | Copilot | 外部 skill 桥接路由 |
| `routing_preferences.json` | 用户配置 | dispatch | 指定指令走 MCP 管线 |
| `pro_registry.json` | 用户配置 | `text-cli;pro` | 简名→目标映射 |
| `aggregate/map.json` | 用户配置 | 聚合降级 | 多提供方降级顺序 |
| `key_routing.json` | Copilot 配置 | `KeyRouter` | 密钥来源声明（默认拒绝，§3.19） |


