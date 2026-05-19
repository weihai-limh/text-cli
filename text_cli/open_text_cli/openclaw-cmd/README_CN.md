# openclaw-cmd · openclaw命令

通过 CLI 管理 OpenClaw 网关、技能和会话。

## 安装

```
AI:text-cli;install,openclaw-cmd
```

## 依赖

**运行时**：`cmd`。需要 copilot 主机上已安装 `openclaw` CLI。
Copilot 通过白名单机制执行 shell 命令。

## 指令

| 指令 | 说明 |
|------|------|
| `openclaw;gateway-status` | 查看 OpenClaw 网关运行状态 |
| `openclaw;session-list` | 列出活跃的 OpenClaw 会话 |

中文别名：`openclaw;网关状态` `openclaw;会话列表`

## 示例

```
AI:openclaw;网关状态
→ Gateway is running (pid 12345, uptime 3d 2h)

AI:openclaw;会话列表
→ 3 active sessions: main, nexus, tide
```

## 架构

```
cmd runtime 包（白名单机制）
  ├── schema.json      — 指令声明
  └── whitelist.json   — 动作 → shell 命令映射

执行流程：copilot 读取 whitelist.json，校验参数模式，运行 shell 命令，返回 stdout。
```
