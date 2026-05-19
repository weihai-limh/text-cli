# task-manager · 任务管理

异步任务生命周期管理，基于 SQLite 持久化。供长耗时指令（如 bim-ifc）使用。

## 安装

```
AI:text-cli;install,task-manager
```

## 依赖

**运行时模块**（需部署到服务）：
- `text_cli_modules/sqlite/` — 数据库层

**存储**：结果写入 `TEXT_CLI_MEDIA_DIR/tasks/`（环境变量，默认服务媒体目录）。

## 指令

| 指令 | 说明 |
|------|------|
| `task;status,<任务ID>` | 查询任务状态（pending/running/done/error） |
| `task;result,<任务ID>` | 获取已完成任务的结果 |
| `task;list` | 列出所有任务 |
| `task;track,<任务ID>` | 获取缓存追踪键 |
| `task;cancel,<任务ID>` | 取消等待中/进行中的任务 |

中文别名：`任务;状态` `任务;结果` `任务;列表` `任务;追踪` `任务;取消`

## 示例

```
AI:任务;列表
→ 3 tasks: a1b2c3 (running), d4e5f6 (done), g7h8i9 (error)

AI:任务;状态,a1b2c3
→ {"status": "running", "progress": "step 2/5"}

AI:任务;结果,d4e5f6
→ {"status": "done", "result": {...}}
```

## 架构

```
A6 SQL 模块
  ├── handler.py          — @directive 注册 + 任务生命周期
  ├── schema.json         — 5 条指令
  └── text_cli_modules/sqlite/ — 数据库层（运行时依赖）
```
