# text-cli 渐进式部署导航

text-cli 采用渐进式部署——从零依赖的协议层到全量技能即服务，按需爬坡。每一级都是完整终点，升级是加法不是替代。

源码在 `src/skeleton/` 下按运行时分组（base / copilot / service / endpoint），各分组含 `docs/README_zh.md`。产物在 `deploy/` 下由 `tools/build-all.py` 生成。

## 层级导航

| 层级 | 目录 | 运行时 | 说明 |
|:---:|------|------|------|
| A0 | `A0-protocol/` | — | 协议规范 + 零依赖调用示例（shell/call.sh、call.ps1 + python/call.py + js/call.js） |
| A1 | `A1-skill/` | — | Agent Skill 定义层（SKILL.md + skill.py + 示例 skills） |
| A2 | `A2-copilot/` | copilot (:20260) | 本地 AI 调度——cmd engine + Skill Bridge + MCP 桥 + 包管理 |
| A3 | `A3-service/` | service (:28050) | 平台管理核心——包安装/卸载 + 指令发现 + 技能暴露 + NoCode 引擎 |
| A4 | `A4-paths/` | service (:28050) | 路径编排——指令链声明 + 委托调度 + 技能发布 |
| A5 | `A5-endpoint/` | 独立子产品 | 公网入口——Docker (Python/FastAPI) + Cloudflare Workers (JS) |
| A6 | `A6-sql/` | service (:28050) | SQLite 持久层——密钥管理 + 配额追踪 + 异步任务 |
| A7 | `A7-mcp/` | service (:28050) | MCP 双向桥接——配置驱动暴露 + mcporter 工具调用 |
| A8 | `A8-discovery/` | service (:28050) | 指令发现——查询/搜索/匹配 + 聚合入口 + 白名单 |
| A9 | `A9-advanced/` | service (:28050) | 累积终点——聚合降级 + 多源统一 + 技能即服务 |

## 如何部署

**部署即 `deploy/` 目录。** 选择目标层级，进入对应目录启动服务：

```bash
# 部署 A2 本地 Copilot
cd deploy/A2-copilot/copilot
python3 text-cli-copilot.py

# 部署 A3 平台管理服务
cd deploy/A3-service/service
python3 main.py

# 部署 A9 全量能力
cd deploy/A9-advanced/service
python3 main.py
```

**源码在 `src/skeleton/`**——只改不部署。`tools/build-all.py` 将源码同步到 `deploy/`。

## 平台分发

| 目录 | 说明 |
|------|------|
| `skeleton-container/A3-service/` | A3 Docker 部署（Dockerfile + compose + init_config.sh） |
| `skeleton-container/A9-advanced/` | A9 Docker 部署（同上） |
| `skeleton-win/` | Windows 封装（空桩，构建时填充） |
| `skeleton-linux/` | Linux 封装（空桩，构建时填充） |

## A5 子产品

| 目录 | 说明 |
|------|------|
| `A5-endpoint/container/` | Python/FastAPI Docker 部署 |
| `A5-endpoint/cloudflare/` | Cloudflare Workers 部署（wrangler.toml） |
| `A5-endpoint/docs/` | A5 专属文档（README / 用户手册 / 部署清单 / 隐私基线） |

## 指令包

| 目录 | 说明 |
|------|------|
| `packages/` | 开源指令包固定版本快照（分发脚本独立设计） |

## 累积关系

A2→A9 逐层累积覆盖。A3 启动即含 A2 能力，A9 是全量终点。每层的 `deploy/` 是到该层为止的完整运行时。
