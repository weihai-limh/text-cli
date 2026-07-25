# text-cli 渐进式部署导航

text-cli 采用渐进式部署——从零依赖的协议层到全量技能即服务，按需爬坡。每一级都是完整终点，升级是加法不是替代。

源码在 `src/skeleton/` 下按运行时分组（base / copilot / service / endpoint / bypass-service），各分组含 `docs/README_zh.md`。产物在 `deploy/` 下由 `scripts/build-all.py` 生成。

## 层级导航

| 层级 | 目录 | 运行时 | 说明 |
|:---:|------|------|------|
| A0 | `A0-protocol/` | — | 协议规范 + 零依赖调用示例（shell/call.sh、call.ps1 + python/call.py + js/call.js） |
| A1 | `A1-skill/` | — | Agent Skill 定义层（SKILL.md + skill.py + 示例 skills） |
| A2 | `A2-copilot/` | copilot (:20260) | 本地 AI 调度——cmd engine + Skill Bridge + 包管理 |
| A3 | `A3-service/` | service (:28050) | 平台管理核心——包安装/卸载 + 指令发现 + 技能暴露 + NoCode 引擎 |
| A4 | `A4-paths/` | service (:28050) | 路径编排——指令链声明 + 委托调度 + 降级递补 |
| A5 | `A5-endpoint/` | gateway (:29050) | 集成端点网关——Access Token 鉴权 + IP 黑名单 + 分时限流 + 聚合转发（Docker + Cloudflare Workers） |
| A6 | `A6-sql/` | service (:28050) | SQLite 持久层——密钥管理 + 配额追踪 + 异步任务 |
| A7 | `A7-mcp/` | service (:28050) | MCP 双向桥接——配置驱动暴露 + mcporter 工具调用 |
| A8 | `A8-discovery/` | service (:28050) | 指令发现——查询/搜索/匹配 + 聚合入口 + 白名单 |
| A9 | `A9-advanced/` | service (:28050) | 累积终点——聚合降级 + 多源统一 + 联邦 mesh + 技能即服务 |

## 旁路服务

非 Python 运行时，与层级导航平行但独立部署，不参与 A2→A9 累积链。

| 层级 | 平台 | 目录 | 运行时 | 说明 |
|:---:|------|------|------|------|
| BYPASS | cloudbase | `bypass-service/` | 云函数 | text-cli 路由 + 指令分发（Node.js / wx-server-sdk） |

> 后续云函数平台（Cloudflare Workers / AWS Lambda / 阿里云函数计算）按需追加。

## 如何部署

**部署即 `deploy/` 目录。** 选择目标层级，进入对应目录启动服务：

```bash
# 部署 A2 本地 Copilot（仅本机 127.0.0.1 可达）
cd deploy/A2-copilot
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

容器镜像由 `skeleton-container/build.py` 构建。平台制品由 `release-script/` 下的构建脚本生成。

| 目录 | 说明 |
|------|------|
| `skeleton-container/A2-copilot/` | A2 Docker 部署 |
| `skeleton-container/A3-service/` | A3 Docker 部署 |
| `skeleton-container/A5-endpoint/` | A5 Docker 部署（:29050，网关面） |
| `skeleton-container/A9-advanced/` | A9 Docker 部署（:28050 + :9020） |
| `skeleton-win/` | Windows 封装（空桩——由 `scripts/release/win/build.py` 填充，详见目录内 `README_zh.md`） |
| `skeleton-linux/` | Linux 封装（空桩——由 `scripts/release/ubuntu/build.py` 填充，详见目录内 `README_zh.md`） |

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
cd deploy/skeleton-container
python build.py              # 仅生成 .build/ 上下文
python build.py --build      # 生成上下文 + docker build
```

发现 `deploy/` 内容与预期不符时，先跑 `--check` 诊断，再跑 `build-all.py` 重建。
