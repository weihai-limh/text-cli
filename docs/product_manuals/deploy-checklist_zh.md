# text-cli v{VERSION} 部署核对清单

> **用途**：上线前逐项核对。**结构与用户手册一致——按产品组织**（Copilot / Service / Endpoint / Protocol），每个产品内再按平台（Windows / Linux / Docker）核对。
> **依据**：`docs/product_manuals/user-manual_zh.md`（产品结构）+ `scripts/release/win/ubuntu/container` 的 build.py（构建行为）。
> 你拿到哪个制品，核对对应产品章节即可。

---

## 零、概念速览（对齐用户手册）

text-cli 由四个独立产品组成，可单独部署、组合使用：

| 产品 | 制品名 | 监听 | 独立能做什么 |
|------|------|:--:|------|
| Copilot | `text-cli-A2-v*` | :20260, 127.0.0.1 | 装 cmd/skill 指令包，操作本机 |
| Service | `text-cli-A3-v*` ~ `A9-v*` | :28050/9020, 0.0.0.0 | 装指令包，编排管道，持久化状态，接 MCP |
| Endpoint | `text-cli-endpoint-python-v*` | :29050, 0.0.0.0 | 鉴权、限流、审计，透传至 Service |
| Protocol | `protocol/`（随所有制品分发） | - | 零依赖消费端 SDK，四语言，一键调用免 curl |

三种常见组合：本机（Copilot+Protocol）/ 内网（Copilot+Service+Protocol）/ 公网（Copilot+Service+Endpoint）

**通用预检（所有制品）**：
- [ ] 制品内已有 `docs/`（手册）、`protocol/`（SDK）——Win/Linux 分发制品由 build.py 组装
- [ ] 所需端口未被占用（Windows: `netstat -ano \| findstr :PORT`；Linux: `ss -tlnp \| grep PORT`）

---

## 一、Copilot 产品（制品 `text-cli-A2`，本机 :20260）

> 本机能力代理，仅 127.0.0.1 可达，操作文件/终端/凭据。

### 1.1 Windows（start.bat）
- [ ] Python 3.10+ 在 PATH
- [ ] `TEXT_CLI_PACKAGE_SOURCE_DIRS` 指向并行 `packages/`（`[OK]`），缺失则 `[WARN]`
- [ ] `copilot/auxiliary_config.json` 已初始化（从 `.example.json` 复制）
- [ ] `curl http://127.0.0.1:20260/text-cli/health` → 200
- [ ] `AI:text-cli;co-list` 可用（安装 cmd/skill 包）
- 停止：`end.bat`

### 1.2 Linux（start.sh）
- [ ] Python 3.10+、`chmod +x start.sh`
- [ ] `TEXT_CLI_PACKAGE_SOURCE_DIRS`、`auxiliary_config.json`（同 1.1）
- [ ] `curl http://127.0.0.1:20260/text-cli/health` → 200
- 停止：`./end.sh`

### 1.3 Docker（`text-cli-copilot` 镜像）
- [ ] `network_mode: host`（**红线：禁 `-p 20260:20260` 暴露到 0.0.0.0**）
- [ ] 外挂 `./runtime:/app/runtime`（首次 entrypoint 从 seed 填充）
- [ ] `curl http://127.0.0.1:20260/text-cli/health` → 200

---

## 二、Service 产品（制品 `text-cli-A3`~`A9`，:28050/9020）

> 核心调度平台。累积制品：A2(copilot) + service(A3+)；A9 含 MCP(:9020) + aggregate。**任何层都包含 copilot，不需单独部署。**

> **累积层级**：Service 制品为 A3~A9（层越高能力越多）。A3 = copilot + service；A9 = copilot + service + MCP(:9020) + aggregate。任意层含 copilot，不需单独部署。核对时按你拿到的层级选相应子节。

### 2.1 Windows（start.bat）
- [ ] Python 3.10+、`.venv` 自动创建并 `pip install -r service/requirements.txt`
- [ ] `TEXT_CLI_PACKAGE_SOURCE_DIRS` 指向 `packages/`（`[OK]`/`[WARN]`）
- [ ] 配置自动初始化：`auxiliary_config.json` + `service/config/text_cli.yaml`
- [ ] A3+：`curl http://localhost:28050/text-cli/health` → 200
- [ ] A3+：`curl -X POST http://localhost:28050/text-cli/cli -H "Content-Type: application/json" -d '{"prompt":"AI:text-cli;query,compact"}'` → 指令列表
- [ ] A7+（含 MCP）：`:9020` MCP 端口可达
- 停止：`end.bat`（按 20260/28050/9020）

### 2.2 Linux（start.sh）
- [ ] Python 3.10+、`chmod +x start.sh`、防火墙允许端口
- [ ] venv / 包源 / 配置初始化（同 2.1）
- [ ] A3+：`curl http://localhost:28050/text-cli/health` → 200 + `query,compact` 指令列表
- [ ] A7+（含 MCP）：`:9020` MCP 端口可达
- 停止：`./end.sh`

### 2.3 Docker（`text-cli-service` / `text-cli-advanced` 镜像，薄沙箱）

**A3（`text-cli-service` 镜像：copilot + service）**
- [ ] 外挂：`./runtime:/app/runtime`（seed 首次填充）、`./data:/app/data`、`./packages:/packages`
- [ ] env：`TEXT_CLI_PACKAGE_SOURCE_DIRS=/packages`、`PORT=28050`
- [ ] 端口：`28050`(service)
- [ ] **🚨 `20260`(copilot) 不对外映射**——copilot 绑 127.0.0.1，仅本机回环（红线）
- [ ] `curl http://localhost:28050/text-cli/health` → 200
- [ ] `curl -X POST ... "AI:text-cli;query,compact"` → 指令列表

**A9（`text-cli-advanced` 镜像：copilot + service + MCP + aggregate）**
- [ ] 外挂：`./runtime:/app/runtime`、`./data:/app/data`、`./packages:/packages`
- [ ] env：`TEXT_CLI_PACKAGE_SOURCE_DIRS=/packages`、`PORT=28050`、`MCP_PORT=9020`
- [ ] 端口：`28050`(service) + `9020`(MCP bridge)
- [ ] **🚨 `20260`(copilot) 不对外映射**——copilot 绑 127.0.0.1，仅本机回环（红线）
- [ ] `curl http://localhost:28050/text-cli/health` → 200
- [ ] `curl -X POST ... "AI:text-cli;query,compact"` → 指令列表
- [ ] （MCP）`/text-cli/health` 的 `capabilities` 含 mcp / `:9020` 可达

---

## 三、Endpoint 产品（制品 `text-cli-endpoint-python`，:29050）

> 独立制品，由 `build-endpoint.py` 单独构建——**不含在 A2-A9 累积制品里**。公网鉴权/限流/审计网关，透传至 Service。

### 3.1 Windows（start-endpoint.bat）
- [ ] `A3_BACKENDS` 已设置（后端 service 地址，如 `http://localhost:28050`；或 `backends.yaml` 多后端）
- [ ] `ACCESS_TOKEN_REQUIRED`（默认 true）、`ENDPOINT_BASE_URL`（默认 `http://localhost:29050`）
- [ ] `.venv` 自动创建并装依赖（requirements 含 fastapi/uvicorn/httpx/pydantic）
- [ ] `curl http://localhost:29050/health` → 200（含 `backends` 透传状态）
- 停止：`end-endpoint.bat`

### 3.2 Linux（start.sh）
- [ ] 同 3.1：A3_BACKENDS / ACCESS_TOKEN_REQUIRED / ENDPOINT_BASE_URL / venv
- [ ] `curl http://localhost:29050/health` → 200
- 停止：`./end.sh`

### 3.3 Docker（`text-cli-endpoint` 镜像）
- [ ] `docker run -d -p 29050:29050 text-cli-endpoint:latest`
- [ ] env：`A3_BACKENDS`（后端 service）
- [ ] `curl http://localhost:29050/health` → 200

---

## 四、安全红线（所有产品）

- [ ] **copilot 仅 127.0.0.1**——绝不把 `20260` 暴露到公网/局域网（`-p` / `network_mode`）
- [ ] Service 若监听 `0.0.0.0` 且可被非受信网络路由到，必须设 `allow_anonymous: false` + `SERVICE_TOKEN`
- [ ] 公网暴露 Service 时，前置 Endpoint（§三，鉴权/限流/审计）
- [ ] 密钥走环境变量 / `tide-token`，不写进代码、配置、镜像层

---

*text-cli v{VERSION} 部署核对清单 · 按用户手册「产品」结构组织（2026-08-14 重新设计）*
