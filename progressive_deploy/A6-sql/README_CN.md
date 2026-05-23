# A6 — SQL 数据持久层

从个人玩具到小企业工具的分界线。SQLite 为密钥管理、配额追踪、异步任务提供持久化。

> `all/` 自 A4 累积。本层新增：handler 升级版（key/task_manager）、quota_handler、key_registry v2、schema.sql。`add/other/` 收纳待消解的 scripts/ 和 key-mgmt/。

## 目录结构

```
A6-sql/
├── all/                               ← 本层完整可部署产物
│   ├── copilot/                       ← 自 A4 累积
│   ├── service/                       ← 自 A4 累积 + A6 升级
│   │   ├── handlers/
│   │   │   ├── key.py                 ← A6 升级版（重构版，含 dispatch 注入）
│   │   │   ├── task_manager.py        ← A6 升级版（含 _set_task_dispatch）
│   │   │   └── quota_handler.py       ← A6 新增 — 配额 handler
│   │   └── text_cli_modules/
│   │       ├── key/
│   │       │   ├── key_registry.py    ← A6 升级版（v2，双凭据 + 配额追踪）
│   │       │   └── key_registry_init.py ← A6 新增
│   │       └── sqlite/
│   │           └── schema.sql         ← A6 新增 — 数据库 schema
│   └── media/                         ← 共享基础设施占位
├── add/                               ← A6 纯增量
│   ├── service/                       ← A6 handler + text_cli_modules 升级
│   ├── media/                         ← 占位
│   └── other/                         ← 待消解（scripts/ + key-mgmt/）
├── README_CN.md                       ← 本文档
└── README.md                          ← 已删除
```

## quota-manage：amount 扩展

`quota;check,<target>[,<amount>]` — amount 默认 1（按调用次数），可传具体数值实现用量维度配额：

```
quota;check,tx-cloud-translation,128  # 消耗 128 字符（翻译配额 500 万字符/月）
quota;check,tx-cloud-asr              # 消耗 1 次调用
```

`cycle_limit` 承担量纲——limit=5000000 对翻译是字符数，limit=1000 对 ASR 是调用次数。SQLite 层不用改 schema，`usage_count` 语义由调用方赋予。

## task-manager：tracked 模式

异步任务有两种模式：

| 模式 | 执行权 | 查询行为 | 适用 |
|------|--------|---------|------|
| managed | task-manager 拥有 | 查本地状态 | bim-ifc 本地进程 |
| tracked | 外部服务拥有 | 实时 dispatch 指令查上游 | tx-cloud ASR、MCP async |

用户调 `task;status,<id>` → task-manager 判断 mode=tracked → 实时 dispatch 对应指令向上游查询。不做后台轮询——只在用户查询时才请求外部服务。

```
task;track,asr-A1,tx-cloud,asr_result,12873421
→ 注册追踪任务，用户查 task;status,asr-A1 时实时调 tx-cloud;asr_result
```

dispatch_fn 通过 `_set_task_dispatch()` 注入，与 key_registry 的 dispatch 注入同构。

## 安装层级

task-manager 和 quota-manage 均为 A6+ 指令包。依赖它们的包（如 tx-cloud）必须在 A6 就绪后安装。

## Token 身份管理

A6 骨架新增两张表，A3 中间件在请求入口提取身份码，应用通过各自的 identity 表映射 token → 外部服务凭据。

### 骨架表（A6 基础设施）

**`token_registry`** — token 准入控制。管理员直接 SQLite 管理，无配套指令包。

```sql
CREATE TABLE IF NOT EXISTS token_registry (
    token       TEXT PRIMARY KEY,   -- 身份码（token 后 6 位）
    enabled     INTEGER DEFAULT 1,  -- 0=吊销
    quota_limit INTEGER DEFAULT -1, -- 调用次数上限，-1=无限
    used_count  INTEGER DEFAULT 0,  -- 已用次数
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at  DATETIME            -- NULL=永不过期
);
```

**`token_call_logs`** — 调用审计记录。token 是跨应用聚合 key。

```sql
CREATE TABLE IF NOT EXISTS token_call_logs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    token       TEXT    NOT NULL,   -- 身份码
    domain      TEXT    NOT NULL,   -- 领域
    action      TEXT    NOT NULL,   -- 动作
    status      TEXT    NOT NULL,   -- ok / error
    error_msg   TEXT,
    duration_ms INTEGER,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### 应用自建表

每个应用在 `schema.json` 中声明 `tables`，安装时自动建表，卸载时自动 `DROP TABLE`。
字段由应用自行定义——syno-file 需要 `user + password`，ai-im 只需要 `im_user`。

```json
{
  "requires": {
    "service_db": ["token_registry", "token_call_logs"]
  },
  "tables": [
    {
      "name": "syno_identity",
      "sql": "CREATE TABLE IF NOT EXISTS syno_identity (token TEXT PRIMARY KEY, user TEXT NOT NULL, password TEXT NOT NULL)"
    }
  ]
}
```

### A3 中间件

请求入口提取 `Service-token` 后 6 位 → 查 `token_registry` 准入 → 注入 `identity_code` 到 ContextVar。
兼容 `X-Text-CLI-Identity` header（A5 未来注入）。

### 实例级配置

| 配置 | 默认值 | 控制 |
|------|--------|------|
| `A3_ALLOW_ANONYMOUS` | `true` | 无 token 请求是否放行。人道主义通道——灾害时管理员本地开启 |
| `A3_COUNT_CALLS` | `false` | `true`=写 `token_call_logs` + 扣配额。`false`=只做准入检查 |
