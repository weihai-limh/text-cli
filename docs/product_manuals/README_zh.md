# text-cli v{VERSION} — 分发制品

## 你拿到了什么

text-cli 由四个独立产品组成，各自可单独部署、组合使用。有两种分发形态：**传统分发包**（Windows / Linux，解压看目录）和**容器镜像**（Docker）。

### 形态一：传统分发包（Windows / Linux）

解压后看根目录有什么文件夹，判断层级：

| 你的文件夹 | 对应层级/产品 | 可用能力 |
|-----------|:------:|---------|
| `copilot/` | Copilot（A2） | 本机文件/Git/shell 代理 |
| 以上 + `service/` | Service（A3+）| 以上 + 指令调度 + 包管理 |
| 以上 + `service/aggregate/` | Service（A8+）| 以上 + 聚合降级 |
| 以上 + `service/pro_registry.json` | Service（A9）| 全量——路径编排 + MCP + 门面 |

> 如果根目录有 `start-endpoint.bat`（或 `start-endpoint.sh`）而非 `start.bat`，这是 **Endpoint 网关制品**——独立鉴权转发服务，端口 29050。

### 形态二：容器镜像（Docker）

镜像由 `scripts/release/container/build.py` 从 `deploy/{layer}` + 文档 + 标准包 + SDK 装配。按镜像名判断产品/层级：

| 镜像名 | 产品/层级 | 端口 |
|--------|:------:|------|
| `text-cli-copilot` | Copilot（A2）| :20260（仅本机 127.0.0.1）|
| `text-cli-service` | Service（A3）| :28050 |
| `text-cli-advanced` | Service（A9，+ MCP + aggregate）| :28050 + :9020 |
| `text-cli-endpoint` | Endpoint（A5，独立制品）| :29050 |

> 每层镜像都含 copilot（:20260，仅本机回环可达），Resource 制品含 Service、MCP 等扩展能力。

## 三步上手

### 传统分发包（Windows / Linux）

**1. 启动**：运行启动脚本，自动适配层级——A2 仅启 copilot(:20260)，A3+ 额外启 service(:28050)。
```
Windows: 双击 start.bat
Linux:   chmod +x start.sh && ./start.sh
```
Endpoint 网关制品：
```
Windows: 双击 start-endpoint.bat
Linux:   chmod +x start-endpoint.sh && ./start-endpoint.sh
```

**2. 验证**：
```bash
# Copilot（A2）
curl http://127.0.0.1:20260/text-cli/health
# Service（A3+）
curl http://localhost:28050/text-cli/health
# Endpoint（网关制品）
curl http://localhost:29050/health
```

**3. 查看可用指令**：
```bash
# Service（A3+，已装指令即查）
curl -X POST http://localhost:28050/text-cli/cli -H "Content-Type: application/json" -d '{"prompt":"AI:text-cli;query"}'
# Copilot（A2，需先装包）
curl -X POST http://127.0.0.1:20260/text-cli/cli -H "Content-Type: application/json" -d '{"prompt":"AI:text-cli;co-list"}'
```

### 容器镜像（Docker，薄沙箱）

镜像为薄沙箱：只含 Python 环境 + 代码种子(seed)，代码/包/数据**外挂宿主机**。首次运行由 entrypoint 从 seed 填充到外挂目录，之后宿主托管（热更新不 rebuild）。

**1. 构建**：
```bash
cd deploy/skeleton-container
python build.py          # 生成 .build/ 构建上下文
docker compose -f A9-advanced/docker-compose.yml up -d   # 例：A9
```

**2. 验证**：
```bash
curl http://localhost:28050/text-cli/health    # service
curl http://localhost:9020/...                  # MCP（A9）
```

**3. 外挂与红线**：
- 外挂目录：`./runtime:/app/runtime`（首次 seed 填充）、`./data:/app/data`、`./packages:/packages`（标准包源）
- **🚨 copilot(:20260) 仅本机回环**——绝不 `-p 20260:20260` 暴露到网络（容器用 `--network=host` / 不映射）

---

## 制品信息

| 项 | 值 |
|----|-----|
| 版本 | v{VERSION} |
| 协议 | SPEC v1.3.2 |
| Copilot | 端口 20260（仅 127.0.0.1）|
| Service | 端口 28050（0.0.0.0）|
| Service MCP | 端口 9020（0.0.0.0，A7+）|
| Endpoint | 端口 29050（0.0.0.0）|

## 配套文档

- `user-manual_zh.md` — 完整使用手册与配置参考
- `deploy-checklist_zh.md` — 上线前核对清单
- `privacy-checklist_zh.md` — 数据流向与安全声明
