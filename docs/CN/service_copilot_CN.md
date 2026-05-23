# service 和 copilot — 服务模块说明

text-cli 有两个运行时角色：**service**（能力提供方）和 **copilot**（本地代理）。它们通过协议对话，各自独立部署。

---

## 一、service — 能力提供方

service 是 text-cli 的核心运行时。它持有指令包、执行调度、加工输出。

### 请求管道

```
请求 → 聚合 dispatch → MCP 优先路由 → 本地 dispatch → MCP 后备 → proxy
```

每一步的分工：

| 步骤 | 做什么 | 归属 A 级 |
|------|--------|----------|
| 聚合 dispatch | 匹配 aggregate/*.json → 按降级链尝试提供方 | A8 |
| MCP 优先路由 | 显式偏好 MCP 时优先调 MCP server | A7 |
| 本地 dispatch | 查 registry → 调 @directive handler | A3 |
| MCP 后备 | 本地未匹配 → 尝试 MCP 作为后备路由 | A7 |
| proxy | 转发到 copilot 或其他 service | A2 |

### 自管理能力

- `text-cli;install` — 安装指令包 + handler_inits 自动注册
- `text-cli;export` — 导出指令包到 text-cli-package/
- `text-cli;packages` — 列出已安装包

### 对外暴露

- `/health` — 健康检查 + 已注册指令
- `/skills` — 白名单过滤的技能列表（只暴露 service_manifest.json 中的条目）
- `/cli/text_cli` — 指令执行端点

---

## 二、copilot — 本地代理

copilot 部署在终端本地。通过 `text-cli;co-install` 管理自己的指令包（files、git、mail、terminal、browser 等），也通过 proxy 转发到 service。

### 核心能力

| 模块 | 做什么 |
|------|--------|
| cmd_engine | 白名单校验 → subprocess 执行 CLI 命令 |
| path_engine | 匹配路径 schema → 执行多步指令链 |
| skill_bridge | 桥接 ClawHub 等技能市场下载的 skill |
| terminal | 代理本地终端操作（文件、邮件、shell） |
| co-install | 安装 copilot 指令包，importlib.reload 立即生效 |

### dispatch 三层匹配

copilot 的指令匹配分三层：

1. **显式 handler** — `auxiliary_config.json` 里有 `handler` 字段的直接注册
2. **@directive 自动发现** — 遍历 `_handle_*` 方法，从方法名反推 op_id
3. **skill bridge fallback** — 从 `skill_bridge_routes.json` 读路由，统一指向 `_try_skill_bridge`

三层独立互补。co-install 安装的包通过 importlib.reload 立即加入第 2 层。skill 包通过 `skill_bridge_routes.json` 自动加入第 3 层（启动时注册）。

### 指令包管理

```
AI:text-cli;co-install,<包名>        → 安装 copilot 指令包
AI:text-cli;co-uninstall,<包名>      → 卸载
AI:text-cli;co-list                  → 列出已安装
```

与 service 的 `text-cli;install` 对比：

| | A3 service | A2 copilot |
|------|------|------|
| 安装指令 | `text-cli;install` | `text-cli;co-install` |
| 重启生效 | 需要 | 不需要（importlib.reload） |
| 覆盖安装 | 否 | `--force` |
| handler 注册 | handler_inits.py | importlib.reload |

### skill_bridge 流程

```
Agent 调用 skill-bdmap;geocode
  → copilot 查 skill_bridge_routes.json
  → 找到对应的 skill 命令模板
  → subprocess 执行 skill 脚本
  → 通用适配器（status 归一化）
  → output_adapter（字段映射）
  → 返回规范格式
```

---

## 三、service 和 copilot 的协作

```
用户 → AI Agent → copilot（本地） → proxy → service（远端）
                       │                        │
                  终端操作（文件/麦克风）      指令包（翻译/地图/配额）
```

- copilot 做**本地操作**——文件读写、shell 命令(操作opencli,终端的麦克风,摄像头等)
- service 做**远端能力**——翻译、地图、搜索、OCR


### 关键交互点

- **proxy_dispatch** — copilot 的指令如果本地未匹配，转发到 service
- **skill_bridge output_adapter** — service 的聚合降级链可以包含 copilot 桥接的 skill
- **双 Token 认证** — 调用方 → Access Token → 集成端点 → Service Token → service

---

## 四、部署关系

```
                    ┌─────────────┐
                    │  调用方(AI)  │
                    └──────┬──────┘
                           │
              ┌────────────┴────────────┐
              │                         │
        ┌─────┴─────┐            ┌──────┴──────┐
        │  copilot   │            │   service   │
        │ (本地代理)  │──proxy──→ │ (能力提供方) │
        │            │←──result──│             │
        └────────────┘            └─────────────┘
```

两者独立部署、独立升级。copilot 的升级不中断 service，反之亦然。
