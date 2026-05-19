# quota-manage · 配额管理

函数级 API 配额追踪器，支持原子性周期重置与消耗。

## 安装

```
AI:text-cli;install,quota-manage
```

## 依赖

零外部依赖。仅使用 Python 标准库（`sqlite3`、`json`、`logging`、`pathlib`）。

## 指令

| 指令 | 说明 |
|------|------|
| `quota;register,<目标>,<周期>,<上限>` | 注册配额规则。周期：`day`(日)/`week`(周)/`month`(月)/`year`(年)/`forever`(永久) |
| `quota;check,<目标>[,<数量>]` | 原子性检查并消耗。返回 `remaining` 或 `stop` 信号 |
| `quota;list` | 列出所有规则及当前用量 |
| `quota;reset,<目标>` | 手动归零计数器 |
| `quota;unregister,<目标>` | 移除规则 |

中文别名：`配额;注册` `配额;检查` `配额;列表` `配额;重置` `配额;注销`

## 示例

```
AI:配额;注册,my-api,day,100
AI:配额;检查,my-api
→ {"status":"ok","remaining":99,"used":1,"cycle":"day","limit":100}

AI:配额;列表
→ {"status":"ok","count":1,"quotas":[{"target":"my-api","cycle":"day","limit":100,"used":1,"remaining":99}]}
```

## 架构

```
A6 SQL 模块
  ├── handler.py     — @directive 注册 + 业务逻辑
  └── schema.json    — 指令声明（中英双语）
```

SQLite 表结构：`quota(func_name, cycle_type, cycle_limit, usage_count, usage_date, created_at)`

原子性通过 SQLite `UPDATE ... WHERE usage_count = ?` 乐观锁保证。
