# text-cli 渐进式部署导航

text-cli 采用渐进式部署——从零依赖的协议层到全量技能即服务，按需爬坡。每一级都是完整终点，升级是加法不是替代。

源码在 `src/skeleton/` 下按运行时分组（base / copilot / service / endpoint / bypass-service），各分组含 `docs/README_zh.md`。产物在 `deploy/` 下由 `scripts/build-all.py` 生成。

## 层级导航

| 层级 | 目录 | 运行时 | 说明 |
|:---:|------|------|------|
| A0 | `A0-protocol/` | — | 协议规范 + 零依赖调用示例（shell/call.sh、call.ps1 + python/call.py + js/call.js） |
| A1 | `A1-skill/` | — | Agent Skill 定义层（SKILL + tc-web-chat + phase-kernel） |
| A2 | `A2-copilot/` | copilot (:20260) | 本地 AI 调度——cmd engine + Skill Bridge + 包管理 |
| A3 | `A3-service/` | service (:28050) | 平台管理核心——包安装/卸载 + 指令发现 + 技能暴露 + NoCode 引擎 |
| A4 | `A4-paths/` | service (:28050) | 路径编排——指令链声明 + 委托调度 + 降级递补 + 循环迭代(map) |
| A5 | `A5-endpoint/` | gateway (:29050) | 集成端点网关——Access Token 鉴权 + IP 黑名单 + 分时限流 + 聚合转发（Docker + Cloudflare Workers） |
| A6 | `A6-sql/` | service (:28050) | SQLite 持久层——密钥管理 + 配额追踪 + 异步任务 |
| A7 | `A7-mcp/` | service (:28050) | MCP 双向桥接——配置驱动暴露 + mcporter 工具调用 |
| A8 | `A8-discovery/` | service (:28050) | 聚合入口——多提供方降级链，dispatch 管道首位（含本地指令发现：查询/搜索/匹配 + 白名单） |
| A9 | `A9-advanced/` | service (:28050) | 门面抽象 + 全量累积终点——技能即服务，AI 可发布高级指令（含聚合降级 + 多源统一 + 联邦 mesh） |

> 注：A8 的「指令发现」指**运行时本地对已装指令包的查询/搜索/匹配**（指令级路由发现），并非中心化发现服务；项目不运营中心化发现服务，见 `docs/ecological-partners_zh.md` Non-goal。
> A9 的「联邦 mesh」为请托模型（调用，非对等互操作）——多跳跟随默认关闭，部署者可在 yaml 显式开启；可用性优先设计，非安全推荐；跨运营方发现需自建层，见生态文档 Non-goal。

## 旁路服务

非 Python 运行时，与层级导航平行但独立部署，不参与 A2→A9 累积链。`bypass-service/` 由 `build-all.py` 直通模式同步，覆盖五种形态：本地包执行器（pypi / npm）、边缘计算网关（cloudflare D1）、通用 JS 逻辑层（tc-js-skeleton）、dsh 承载（dsh-tc-runtime / dsh-tc-bridge）。

| 层级 | 平台 | 目录 | 运行时 | 说明 |
|:---:|------|------|------|------|
| BYPASS | cloudbase | `bypass-service/cloudbase/` | 云函数 | 腾讯云 SCF——网关路由 + 指令分发（Node.js / wx-server-sdk） |
| BYPASS | cloudflare | `bypass-service/cloudflare/` | 边缘计算 | Cloudflare Workers D1 多功能版——可执行包存 D1 + 受限执行 + 单 Service-token 闭环 |
| BYPASS | dsh | `bypass-service/dsh/` | dsh 承载 | dsh-tc-runtime（Cordis 插件集）/ dsh-tc-bridge（tc 指令消费能力缝） |
| BYPASS | tc-js | `bypass-service/tc-js-skeleton/` | 通用 JS | 通用 JS 逻辑层真源（12 个 textcli-core-* 组件，洋葱分层） |
| BYPASS | pypi / npm / core-c / core-rust | `bypass-service/pypi/` `bypass-service/npm/` `bypass-service/text-cli-core-c/` `bypass-service/text-cli-core-rust/`  | 包执行器 | 多语言指令包加载器—— Python / js / c / rust 环境直接加载执行 |



> 详见 `bypass-service/docs/INDEX_zh.md`。

## 标准运行时(基于python)典型分发目录

A2、A3、A9 是三个典型直接部署的运行时目标。项目提供它们的'container','win','linux','mac'形式的快速部署包。

A2 是独立 copilot，A3 累积了 copilot(A2) +基础 service，
A4、A6、A7、A8、A9 每层的新增内容都是对 service 的更新逐层累积层，
A9 是全量累积终点。A9是包含了全量的 copilot + service

```text
deploy/A2-copilot/                  # A2 单 copilot — 本地 AI 调度
└── copilot/                        # 运行时根（由 build-all.py 从 src/skeleton/copilot/A2-copilot/ 生成）
    ├── text-cli-copilot.py          # 入口 — python text-cli-copilot.py → :20260
    ├── core.py                      # 指令引擎 + 路由解析
    ├── handlers/                    # 指令处理器（key / skill_bridge / package_manager / codec / adapters）
    ├── packages/                    # 包管理占位
    ├── config/                      # 路由偏好 / key 路由 / Skill Bridge 配置
    ├── whitelist_loader.py
    └── auxiliary_config.json

deploy/A3-service/                  # A3 累积层 — A2 能力 + 平台管理核心
├── copilot/                        # 继承自 A2 累积（copilot 运行时）
├── service/                        # A3 本体 — 平台管理服务
│   ├── main.py                     # 入口 — python main.py → :28050
│   ├── requirements.txt
│   ├── core/                       # 核心引擎（auth / parser / registry / response / mcp_dispatch）
│   ├── handlers/                   # 指令处理器（installer / skill_endpoint / proxy / nocode 等）
│   ├── config/                     # 服务清单 / 系统 schema / webhook 路由 / 提示模板
│   └── packages/                   # 包管理


deploy/A9-advanced/                 # A9 累积终点 — copilot + service + MCP + 聚合
├── copilot/                        # 继承自 A2 累积
├── service/                        # A3–A8 全部 service 层累积
│   ├── main.py                     # 入口 — python main.py → :28050
│   ├── requirements.txt
│   ├── core/                       # 同上，含 identity_context / stream_subscriber_registry
│   ├── handlers/                   # 全套处理器（含 quota_handler / task_manager / mcp_handler）
│   ├── config/                     # 全套配置（含 mcporter / path_messages / 多语言）
│   └── packages/
├── MCPservice/                     # 来自 A7 — MCP 桥接服务（server.py → :9020）
│   ├── server.py
│   └── manage.sh
├── aggregate/                      # 来自 A8 — 聚合路由表
│   ├── map.json
│   └── web.json

```

> **累积规则**：A3 自动包含 A2 的 `copilot/`，A9 自动包含 A2–A8 的全部层。后层同名文件覆盖前层。`copilot/` 和 `service/` 子目录是 `build-all.py` 的 `SKELETON_SUBDIRS` 白名单成员，确保被正确透传。

## 如何部署

**部署即 `deploy/` 目录。** 选择目标层级，进入对应目录启动服务：

```bash
# 部署 A2 本地 Copilot（仅本机 127.0.0.1 可达）
cd deploy/A2-copilot/copilot
python3 text-cli-copilot.py

# 部署 A3 平台管理服务
cd deploy/A3-service/service
python3 main.py

# 部署 A5 集成端点网关
cd deploy/A5-endpoint/python
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 29050

# 部署 A9 全量能力
cd deploy/A9-advanced/service
python3 main.py
```

## 平台分发

容器镜像由 `scripts/release/container/build.py` 构建。平台制品由 `scripts/release/` 下的构建脚本生成。

| 目录 | 说明 |
|------|------|
| `skeleton-container/A2-copilot/` | A2 Docker 部署 |
| `skeleton-container/A3-service/` | A3 Docker 部署 |
| `skeleton-container/A5-endpoint/` | A5 Docker 部署（:29050，网关面） |
| `skeleton-container/A9-advanced/` | A9 Docker 部署（:28050 + :9020） |
| `skeleton-win/` | Windows 封装（构建产物输出目录——由 `scripts/release/win/build.py` 生成） |
| `skeleton-linux/` | Linux 封装（构建产物输出目录——由 `scripts/release/ubuntu/build.py` 生成） |
| `skeleton-mac/` | macOS 封装（构建产物输出目录——由 `scripts/release/mac-arm/build.py` 生成） |

## A5 子产品

| 目录 | 说明 |
|------|------|
| `A5-endpoint/python/` | Python/FastAPI 实现（`build-all.py` 从源码同步） |
| `A5-endpoint/js/` | Cloudflare Workers 实现 |
| `A5-endpoint/container/` | Docker 构建描述符（Dockerfile + docker-compose.yml） |
| `A5-endpoint/cloudflare/` | Cloudflare Workers 部署（wrangler.toml） |

## 指令包

| 目录 | 说明 |
|------|------|
| `packages/` | 开源指令包固定版本快照（`build-all.py` 从 `src/text_cli/open_text_cli/` 分发） |

## 累积关系

A2→A9 逐层累积覆盖。A3 启动即含 A2 能力，A9 是全量终点。每层的 `deploy/` 是到该层为止的完整运行时。

A0/A1/A5/BYPASS 是直通同步——源码原样镜像，不参与累积链。

## 同步机制

**`deploy/` 不是手动编辑的。** 所有文件由构建脚本从 `src/skeleton/` 生成。

```bash
# 骨架源码 → deploy/ 制品（全部层级）
python scripts/build-all.py

# 单独同步某一层
python scripts/build-all.py A5

# 校验 deploy/ 与源码一致性（CI 用）
python scripts/build-all.py --check

# 容器构建上下文装配（需先跑 build-all.py）
python scripts/release/container/build.py              # 仅生成 .build/ 上下文
python scripts/release/container/build.py --build      # 生成上下文 + docker build
```

发现 `deploy/` 内容与预期不符时，先跑 `--check` 诊断，再跑 `build-all.py` 重建。
