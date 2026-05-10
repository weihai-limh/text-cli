# 自建端点模板技术方案

> **作者**：Lumen ✦（IDE 端 / Claude）  
> **日期**：2026-04-30（初稿）/ 2026-05-01（更新） / 2026-05-05（v3.1 实现同步）  
> **版本**：v3.1（v3.0 新增 Workers 方案，本版同步实际实现）  
> **状态**：Python 端已完成，Cloudflare Workers 端已完成（PR #60）  
> **评审人**：lemondy、DeepSeek（Chat 端）、Tide 🌊（Agent 端）

---

## 一、目标与定位

### 1.1 我们要解决什么问题

`text-cli` 生态当前只有一个公共体验端点 `test.text-cli.com`。任何想自建端点的开发者都缺少一套开箱即用的模板。这导致：

- 技能提供者无法自主部署端点，只能依赖公共端点
- 调用方无法获得私有的 Access Token 与独立的调用额度
- 调用计数和 Service Token 计费无从在端点侧落地
- 潜在建设者的"三层信号灯"第一层（可被机器执行的 API 调用闭环）尚未完全绿灯

### 1.2 端点在架构中的位置

```
调用方(Agent) ──Access Token──> 集成端点(Endpoint) ──> 技能服务A (网址1)
                                    │                ──> 技能服务B (网址2)
                                    │                ──> 技能服务C (网址3)
                                    │
                             Access Token 鉴权
                             指令解析与路由
                             Service Token 透明转发
                             调用日志记录
```

**Endpoint 只做纯转发**，不执行任何技能逻辑。所有技能都是独立的后端服务，按照 `Building_text-cli_guide_CN.md` 构建。

### 1.3 交付物清单

| 序号 | 交付物 | 路径 | 说明 | 状态 |
|:---|:---|:---|:---|:---|
| 1 | Python/FastAPI 端点 | `server/python/` | 完整可运行的集成端点 | ✅ 已完成（PR #9） |
| 2 | Cloudflare Workers 端点 | `server/js/` | 完整可运行的集成端点（Workers + D1） | ✅ 已完成（PR #60） |
| 3 | Docker 部署文件 | 各语言目录下 | Dockerfile + docker-compose.yml | ✅ Python 版已完成 |
| 4 | 记账模块 | 内置于两版端点 | 调用记录、统计查询（Python: SQLite / Workers: D1） | ✅ 两版均已完成 |
| 5 | 部署说明 | 各端目录下 README | 面向运维的部署指南 | ✅ 两版均已完成 |

### 1.4 与已有文档的关系

| 文档 | 定位 | 与本方案的关系 |
|:---|:---|:---|
| `SPEC v1.0` | 协议规范 | Endpoint 必须严格遵循其 API 定义 |
| `Building_text-cli_guide_CN.md` | 如何构建后端技能服务 | Endpoint 转发的目标就是这类服务 |
| `Agent_integrated_CN.md` | 如何让 Agent 接入 text-cli | Agent 通过 Endpoint 暴露的 Schema 发现指令 |
| **本方案** | 如何构建集成端点 | 连接调用方和技能服务的中间层 |

---

## 二、核心设计

### 2.1 Endpoint 的职责

Endpoint 承担且仅承担以下职责：

1. **Access Token 鉴权**：验证调用方是否有权使用此端点
2. **指令解析**：从 prompt 中提取 domain、action、params
3. **路由匹配**：根据解析结果，在 Schema 中找到对应指令的后端 url
4. **请求转发**：将请求透明转发到后端技能服务（含 Service Token）
5. **调用记账**：将每次调用的元数据写入 SQLite
6. **Schema 转换**：对外暴露去掉真实后端地址的 Schema

### 2.2 双 Schema 机制

Endpoint 内部维护两份 Schema：

#### 内部路由 Schema（`text_cli_schema.json`，磁盘文件）

运营者从技能提供者处收集的完整 Schema，包含真实的后端服务地址。**此文件不对外暴露。**

```json
{
  "weather_query": {
    "url": "https://skill-server-a.example.com/cli/text_cli",
    "id": "weather_query",
    "name": "天气查询",
    "category": "基础应用",
    "directive": "指令:基础应用;天气查询",
    "parameters": [...],
    "prompt_template": "指令:基础应用;天气查询,{time},{city}",
    "trigger_keywords": ["天气", "气温", "下雨"],
    "response_type": "text",
    "response_example": {...}
  },
  "clothing_tag": {
    "url": "https://skill-server-b.example.com/cli/text_cli",
    ...
  }
}
```

#### 对外暴露 Schema（`GET /text_cli_schema.json`，运行时生成）

Endpoint 启动时，将内部 Schema 的所有 `url` 字段替换为 Endpoint 自身地址（`https://端点域名/cli/text_cli`），其余字段原样保留。

```json
{
  "weather_query": {
    "url": "https://my-endpoint.example.com/cli/text_cli",
    "id": "weather_query",
    "name": "天气查询",
    ...
  },
  "clothing_tag": {
    "url": "https://my-endpoint.example.com/cli/text_cli",
    ...
  }
}
```

调用方（Agent）只能看到 Endpoint 的地址，无法得知指令实际由哪个后端服务处理。

### 2.3 Schema 加载策略

**Python 版**（已实现）：**从本地文件加载**（`config/text_cli_schema.json`），通过环境变量 `SCHEMA_PATH` 可自定义路径。运行时维护两份：内部 Schema（含真实后端 url）和外部 Schema（url 统一指向 Endpoint）。`POST /api/schema/reload` 端点支持热重载。

**Workers 版**（已实现）：**双模式加载**，优先从 D1 `directives` 表查询，回退到静态文件 `src/config/schema.json`。`directives` 表支持热更新（INSERT/UPDATE 即生效，无需重启）。`POST /api/schema/reload` 端点将静态 JSON 重新加载到 D1。

未来版本预留：支持从远程 URL 拉取 Schema（如 `https://registry.text-cli.com/schema.json`），定时刷新。环境变量 `SCHEMA_SOURCE` 可切换加载方式。

> **实现参考**：
> - Python：`core/schema_loader.py` — `load_schema()` / `reload_schema()` / `get_external_schema()` / `find_backend_url()`
> - Workers：`src/schema-loader.js` — `loadSchema()` / `loadSchemaFromD1()` / `getExternalSchema()` / `findBackendUrl()` / `findBackendUrlFromD1()`

---

## 三、请求处理流程

### 3.1 完整流程

```
POST /cli/text_cli
请求体: {"prompt": "指令:基础应用;天气查询,明天,威海"}
请求头: Authorization: Bearer <Access Token>
        Service-token: <Service Token>
    │
    ▼
① Access Token 鉴权
    ├── 失败 → 401 ACCESS_DENIED
    │
    ▼
①.5 令牌桶限流检查（滑动窗口 60 秒）
    ├── 超出 max_requests_per_minute → 401 ACCESS_DENIED
    │
    ▼
② 解析指令
    ├── prompt 缺失 → 400 INVALID_DIRECTIVE_FORMAT
    ├── 格式不正确 → 400 INVALID_DIRECTIVE_FORMAT
    │
    ▼
   domain = "基础应用"
   action = "天气查询"
   params = ["明天", "威海"]
    │
    ▼
③ Schema 路由匹配
    ├── 查找 directive = "指令:基础应用;天气查询" 的条目
    ├── 未找到 → 400 DIRECTIVE_NOT_FOUND
    │
    ▼
   目标 url = "https://skill-server-a.example.com/cli/text_cli"
    │
    ▼
④ 转发请求到后端（含自动重试）
    POST 目标 url
    Body: {"prompt": "指令:基础应用;天气查询,明天,威海"}  (原样透传)
    Headers:
      Service-token: <原 Service Token>        (必须透传)
    重试策略：
      - 5xx 错误：自动重试（次数由 FORWARD_MAX_RETRIES 控制，默认 1 次）
      - 超时：返回 408
      - 4xx 错误：不重试
    │
    ▼
⑤ 记录调用日志 (SQLite)
    ├── call_logs：写入本次调用的完整元数据
    ├── daily_stats：实时更新聚合计数
    ├── access_tokens：累加 used_count
    │
    ▼
⑥ 返回结果给调用方
    后端返回什么就返回什么（透传响应体）
    HTTP 状态码透传
```

> **实现参考**：
> - Python：`main.py` — `text_cli_endpoint()`
> - Workers：`src/index.js` — `handleTextCli()` + `src/forwarder.js` — `forwardRequest()`

### 3.2 指令解析规则

遵循 SPEC v1.1（双前缀协议）：

```
指令:<领域>;<动作>,<参数1>,<参数2>,...
AI:<领域>;<动作>,<参数1>,<参数2>,...
```

- `指令:` 和 `AI:` 前缀同等效力（解析器统一处理）
- 全角冒号 `：` 与半角 `:` 等效
- 领域和动作之间用分号 `;` 分隔
- 参数之间用逗号 `,` 分隔
- 参数前后空白自动 trim
- 指令长度上限 512 字符
- 参数数量上限 10 个
- 解析器正则：`^(?:指令|AI)[：:]([^;]+);([^,]+)(?:,(.+))?$`

### 3.3 Schema 匹配逻辑

按 `directive` 字段精确匹配：

```
从 prompt 解析出: domain="基础应用", action="天气查询"
拼接: "指令:基础应用;天气查询"
在 Schema 中查找: directive == "指令:基础应用;天气查询"
```

如果 Schema 中存在多个同 domain 的指令（如"基础应用"下有天气查询、穿衣标签等），通过 action 精确区分。

---

## 四、鉴权模型

### 4.1 Access Token（端点侧管理）

Access Token 由 Endpoint 运营者签发和管理，用于验证调用方是否有权使用此端点。

- 存储方式：SQLite `access_tokens` 表，Token 以 SHA256 哈希存储
- 传递方式：请求头 `Authorization: Bearer <token>`
- 校验逻辑：哈希匹配 → 额度检查（`quota` / `used_count`）→ 令牌桶限流（`max_requests_per_minute`，滑动窗口 60 秒）
- 可选功能：环境变量 `ACCESS_TOKEN_REQUIRED=false` 时，可跳过 Access Token 校验（开放模式，仅用于开发/测试）

> **实现参考**：
> - Python：`core/auth.py` — `verify_access_token()` / `_check_rate_limit()` / `increment_token_usage()`
> - Workers：`src/auth.js` — `verifyAccessToken()` / `incrementTokenUsage()` / `hashToken()`（D1 滑动窗口查询替代内存令牌桶）

### 4.2 Service Token（透明转发）

Service Token 由技能提供者与调用方私下约定，Endpoint **只负责透传，不解析、不记录、不存储**。

- 传递方式：请求头 `Service-token: <token>`
- 转发规则：Endpoint 收到的 `Service-token` 原样附加到转发请求中
- SPEC 约束：集成端点**必须透明转发**，不得修改

> **注意**：代码中默认**不透传** Access Token 到后端。后端只需验证 Service Token，无需知道调用方身份。

### 4.3 管理 API 认证

管理端点通过环境变量 `ADMIN_API_KEY` 保护。不设置时管理 API 不可用（健康检查除外）。

- 传递方式：请求头 `X-Admin-Key: <admin_key>`
- 校验逻辑：明文匹配 `ADMIN_API_KEY` 环境变量
- 适用范围：所有 `/api/tokens/*`、`/api/stats/*`、`/api/schema/reload` 端点

> **实现参考**：
> - Python：`api/tokens.py` — `verify_admin()`
> - Workers：`src/admin.js` — `checkAdminAuth()` / `verifyAdmin()`

---

## 五、SQLite 记账模块

### 5.1 表结构

#### 调用日志表：`call_logs`

| 字段 | 类型 | 说明 |
|:---|:---|:---|
| id | INTEGER PRIMARY KEY AUTOINCREMENT | 自增主键 |
| request_id | TEXT UNIQUE | 请求唯一 ID（UUID） |
| directive | TEXT NOT NULL | 完整指令文本 |
| domain | TEXT | 领域 |
| action | TEXT | 动作 |
| backend_url | TEXT | 转发到的后端地址 |
| service_token_prefix | TEXT | Service Token 前 8 位 + `***`（脱敏存储） |
| access_token_prefix | TEXT | 调用方 Token 前 8 位（用于关联调用方） |
| status_code | INTEGER | 后端返回的 HTTP 状态码 |
| response_time_ms | INTEGER | 转发耗时（毫秒） |
| error_message | TEXT | 错误信息（如有） |
| created_at | DATETIME DEFAULT CURRENT_TIMESTAMP | 调用时间 |

#### 日统计表：`daily_stats`

| 字段 | 类型 | 说明 |
|:---|:---|:---|
| id | INTEGER PRIMARY KEY AUTOINCREMENT | 自增主键 |
| date | TEXT NOT NULL | 日期（YYYY-MM-DD） |
| domain | TEXT | 领域 |
| action | TEXT | 动作 |
| call_count | INTEGER DEFAULT 0 | 调用次数 |
| success_count | INTEGER DEFAULT 0 | 成功次数（status_code=200） |
| avg_response_ms | INTEGER | 平均响应耗时 |
| UNIQUE(date, domain, action) | | 唯一约束 |

#### Access Token 表：`access_tokens`

| 字段 | 类型 | 说明 |
|:---|:---|:---|
| id | INTEGER PRIMARY KEY AUTOINCREMENT | 自增主键 |
| token_hash | TEXT UNIQUE NOT NULL | Token 的 SHA256 哈希 |
| token_prefix | TEXT NOT NULL | Token 前 8 位（用于识别） |
| client_name | TEXT | 调用方名称 |
| quota | INTEGER DEFAULT -1 | 调用额度（-1 表示无限） |
| used_count | INTEGER DEFAULT 0 | 已使用次数 |
| max_requests_per_minute | INTEGER DEFAULT 60 | 令牌桶限流上限（滑动窗口 60 秒） |
| is_active | BOOLEAN DEFAULT 1 | 是否启用 |
| created_at | DATETIME DEFAULT CURRENT_TIMESTAMP | 创建时间 |

#### 指令路由表：`directives`（Workers 版独有）

Workers 版将 Schema 路由信息存入 D1 `directives` 表，支持热更新（INSERT/UPDATE 即生效）。Python 版仍从本地 JSON 文件加载。

| 字段 | 类型 | 说明 |
|:---|:---|:---|
| id | TEXT PRIMARY KEY | 指令 ID（如 `weather_query`） |
| name | TEXT | 指令名称 |
| category | TEXT | 领域分类 |
| description | TEXT | 指令描述 |
| domain | TEXT | 领域 |
| action | TEXT | 动作 |
| backend_url | TEXT | 真实后端地址 |
| parameters_json | TEXT | 参数定义（JSON 字符串） |
| prompt_template | TEXT | prompt 模板 |
| trigger_keywords_json | TEXT | 触发关键词（JSON 字符串） |
| response_type | TEXT | 响应类型 |
| response_example_json | TEXT | 响应示例（JSON 字符串） |
| directive_key | TEXT | 路由键（如 `指令:基础应用;天气查询`） |
| enabled | BOOLEAN DEFAULT 1 | 是否启用 |
| created_at | DATETIME DEFAULT CURRENT_TIMESTAMP | 创建时间 |

> **说明**：Python 版的三张核心表（`call_logs`、`daily_stats`、`access_tokens`）与 Workers 版的 D1 表结构 1:1 对齐，可无缝迁移。`directives` 表为 Workers 版新增，用于替代 Python 版的本地 JSON 文件路由。

### 5.2 记账写入时机

每次指令调用完成后，无论成功或失败，均写入 `call_logs`。`daily_stats` 在每次调用后实时更新聚合数据。

### 5.3 生态统计上报（预留）

端点可选地向生态中心上报匿名聚合数据，用于宪章第七章"生态健康度量"：

```
POST /api/report_stats    (端点 → 生态中心，可选，默认关闭)
```

上报内容（仅聚合数据，不含原始日志）：

```json
{
  "endpoint_id": "anonymous-hash",
  "date": "2026-04-30",
  "total_calls": 1234,
  "total_success": 1200,
  "top_directives": [
    {"directive": "指令:基础应用;天气查询", "count": 500}
  ],
  "protocol_version": 1
}
```

上报地址通过环境变量 `STATS_REPORT_URL` 配置，不设置则不上报。

---

## 六、API 端点

### 6.1 核心端点（SPEC v1.0，面向调用方）

| 方法 | 路径 | 说明 |
|:---|:---|:---|
| POST | `/cli/text_cli` | 指令执行入口，转发到后端技能服务 |
| GET | `/text_cli_schema.json` | 对外 Schema，所有 url 指向 Endpoint 自身 |

### 6.2 管理端点（`X-Admin-Key` header 保护，面向运营者）

| 方法 | 路径 | 说明 |
|:---|:---|:---|
| GET | `/api/stats/summary` | 调用统计概览 |
| GET | `/api/stats/daily?date=YYYY-MM-DD` | 按日统计明细 |
| GET | `/api/stats/token/{prefix}` | 指定 Token 的调用统计 |
| GET | `/api/tokens` | Access Token 列表 |
| POST | `/api/tokens` | 创建新 Access Token |
| PUT | `/api/tokens/{id}` | 更新 Token（额度、限流、启停） |
| DELETE | `/api/tokens/{id}` | 删除 Token |
| POST | `/api/schema/reload` | 热重载内部 Schema 文件 |
| GET | `/api/health` | 健康检查（liveness + readiness） |

管理端点通过环境变量 `ADMIN_API_KEY` 保护，请求时需携带 `X-Admin-Key` header。不设置时管理 API 不可用（`/api/health` 除外）。

---

## 七、目录结构

### 7.1 Python 版（已实现）

```
server/python/
├── main.py                  # FastAPI 应用入口（lifespan、路由挂载、核心端点）
├── config/
│   └── text_cli_schema.json # 内部路由 Schema（含真实后端 url）
├── core/
│   ├── __init__.py
│   ├── parser.py            # 指令解析器（正则 + 边界校验）
│   ├── schema_loader.py     # 双 Schema 加载与转换（内部/外部）
│   ├── auth.py              # Access Token 鉴权 + 令牌桶限流
│   ├── forwarder.py         # HTTP 转发器（异步、重试、记账）
│   └── database.py          # SQLite 连接、初始化、辅助函数
├── api/
│   ├── stats.py             # 统计查询 API
│   ├── tokens.py            # Token 管理 API（CRUD）
│   └── health.py            # 健康检查 API（liveness + readiness）
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .gitignore
```

### 7.2 Cloudflare Workers 版（已实现）

```
server/js/
├── src/
│   ├── index.js             # Worker 入口（fetch 事件处理器 + 路由）
│   ├── parser.js            # 指令解析器（正则 + 边界校验）
│   ├── schema-loader.js     # 双 Schema 加载与 URL 重写（D1 读取 / 静态文件）
│   ├── auth.js              # Access Token 鉴权（D1 多 Token + 令牌桶限流）
│   ├── forwarder.js         # 请求转发器（fetch API、重试、记账）
│   ├── admin.js             # 管理 API（Token CRUD / 统计查询 / Schema 重载）
│   └── config/
│       └── schema.json      # 内部路由 Schema（含真实后端 url）
├── migrations/
│   └── 0001_init.sql        # D1 迁移脚本（access_tokens / call_logs / daily_stats / directives）
├── scripts/
│   └── seed-schema.js       # 将静态 Schema 导入 D1
├── test/
│   ├── parser.test.js       # 指令解析器测试（11 个用例）
│   ├── auth.test.js         # Token 工具函数测试（7 个用例）
│   └── schema-loader.test.js # Schema 加载器测试（6 个用例）
├── README_CN.md             # 部署指南 + 管理 API 文档
├── wrangler.toml
├── package.json
└── vitest.config.js
```

**与 Python 版的关键差异**：

| | Python (`server/python/`) | Workers (`server/js/`) |
|:---|:---|:---|
| **运行时** | FastAPI (ASGI) | Cloudflare Workers (V8) |
| **数据库** | SQLite (文件) | D1 (SQLite at edge) |
| **部署** | Docker + VM | `wrangler deploy` |
| **Schema 存储** | 本地 JSON 文件 | D1 `directives` 表 + 静态文件回退 |
| **全局 Schema** | 运行时内存缓存 | D1 查询（无状态，每次请求可读） |
| **转发** | httpx 异步客户端 | Workers 原生 `fetch()` |
| **限流** | 令牌桶 (内存/SQLite) | D1 滑动窗口查询 |
| **管理 API** | 独立路由模块 (`api/*.py`) | 同一 Worker 内路由 (`src/admin.js`) |
| **迁移脚本** | `database.py` 初始化 | `migrations/0001_init.sql` |
| **测试** | pytest | vitest（24 个用例通过） |

### 7.3 顶层

```
server/
└── README.md                # 总部署说明（双语言指引、快速开始）
```

---

## 八、环境变量与 wrangler 配置

### 8.1 Python 版环境变量

| 环境变量 | 必须 | 默认值 | 说明 |
|:---|:---|:---|:---|
| PORT | 否 | 8000 | 服务端口 |
| ENDPOINT_BASE_URL | 是 | 无 | Endpoint 自身的公网地址（如 `https://my-endpoint.com`），用于生成对外 Schema |
| ADMIN_API_KEY | 否 | 无 | 管理 API 访问密钥（不设置则管理 API 不可用） |
| ACCESS_TOKEN_REQUIRED | 否 | `true` | 是否强制要求 Access Token（`false` 为开放模式，仅用于开发测试） |
| DB_PATH | 否 | `./data/textcli.db` | SQLite 数据库文件路径 |
| SCHEMA_PATH | 否 | `./config/text_cli_schema.json` | 内部 Schema 文件路径 |
| SCHEMA_SOURCE | 否 | `local` | Schema 加载方式（`local` 从文件加载，`remote` 预留，从 URL 拉取） |
| SCHEMA_REMOTE_URL | 否 | 无 | 远程 Schema 地址（当 `SCHEMA_SOURCE=remote` 时使用，预留） |
| SCHEMA_REFRESH_INTERVAL | 否 | `3600` | 远程 Schema 刷新间隔（秒，预留） |
| FORWARD_TIMEOUT | 否 | `30` | 转发到后端的超时时间（秒） |
| FORWARD_MAX_RETRIES | 否 | `1` | 5xx 错误自动重试次数 |
| STATS_REPORT_URL | 否 | 无 | 生态统计上报地址（不设置则不上报，预留） |
| STATS_REPORT_INTERVAL | 否 | `3600` | 上报间隔（秒，预留） |
| LOG_LEVEL | 否 | `info` | 日志级别 |

### 8.2 Workers 版 wrangler.toml 配置

Workers 版通过 `wrangler.toml` + `[vars]` 配置，环境变量与 Python 版语义一致:

```toml
name = "text-cli-endpoint"
main = "src/index.js"
compatibility_date = "2026-05-01"
workers_dev = true

# D1 数据库（必需，用于 Access Token + 调用日志 + Schema 路由）
# 首次使用前执行: wrangler d1 create text-cli-endpoint-db
# 然后取消下面的注释并填入 database_id
# [[d1_databases]]
# binding = "DB"
# database_name = "text-cli-endpoint-db"
# database_id = "<your-database-id>"

[vars]
ENDPOINT_BASE_URL = "https://my-endpoint.workers.dev"
ACCESS_TOKEN_REQUIRED = "true"
FORWARD_TIMEOUT = "30"
FORWARD_MAX_RETRIES = "1"
```

> **注意**：`ADMIN_API_KEY` 不应写入 `wrangler.toml`（会被提交到版本控制），建议通过 `wrangler secret put ADMIN_API_KEY` 存入 Worker Secrets。

**Workers 版与 Python 版环境变量映射**:

| Python 环境变量 | Workers 配置 | 说明 |
|:---|:---|:---|
| `ENDPOINT_BASE_URL` | `ENDPOINT_BASE_URL` | wrangler `[vars]` 或 Worker Secrets |
| `ADMIN_API_KEY` | `ADMIN_API_KEY` | **必须存入 Worker Secrets**（`wrangler secret put`） |
| `ACCESS_TOKEN_REQUIRED` | `ACCESS_TOKEN_REQUIRED` | wrangler `[vars]` |
| `DB_PATH` | 不需要 | D1 通过 binding 直接访问 |
| `SCHEMA_PATH` | 不需要 | Schema 存入 D1 `directives` 表 |
| `FORWARD_TIMEOUT` | `FORWARD_TIMEOUT` | wrangler `[vars]` |
| `PORT` | 不需要 | Workers 自动分配 |

---

## 九、Docker 部署

### 9.1 Python 版

**Dockerfile**

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN mkdir -p /app/data
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 9.2 Cloudflare Workers 版

**安装依赖 + 运行测试**

```bash
cd server/js
npm install
npm test               # 24 个单元测试全部通过
```

**D1 数据库初始化**

```bash
# 创建 D1 数据库
wrangler d1 create text-cli-endpoint-db

# 将输出的 database_id 填入 wrangler.toml 的 [[d1_databases]] 部分并取消注释

# 执行迁移
wrangler d1 execute text-cli-endpoint-db --file=migrations/0001_init.sql

# 导入内部路由 Schema（编辑 src/config/schema.json 替换 url 后执行）
node scripts/seed-schema.js
```

**敏感配置存入 Worker Secrets**

```bash
wrangler secret put ADMIN_API_KEY
```

**本地开发**

```bash
wrangler dev
```

**部署到 Cloudflare**

```bash
wrangler deploy
```

### 9.3 docker-compose.yml（Python 版通用）

```yaml
version: '3.8'
services:
  text-cli-endpoint:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
      - ./config:/app/config
    environment:
      - ENDPOINT_BASE_URL=https://my-endpoint.example.com
      - ADMIN_API_KEY=your-admin-key
      - ACCESS_TOKEN_REQUIRED=true
      - DB_PATH=/app/data/textcli.db
      - LOG_LEVEL=info
    restart: unless-stopped
```

### 9.4 一键启动

**Python 版（Docker）**

```bash
cd server/python
docker compose up -d
```

**Workers 版**

```bash
cd server/js
npm install
wrangler dev       # 本地开发
wrangler deploy    # 部署到 Cloudflare
```

Workers 本地开发启动后：
- `POST http://localhost:8787/cli/text_cli` — 指令执行
- `GET http://localhost:8787/text_cli_schema.json` — 对外 Schema
- `GET http://localhost:8787/health` — 健康检查
- `GET http://localhost:8787/api/health` — 详细健康检查（含数据库状态）

---

## 十、安全设计

### 10.1 Token 安全

- Access Token 在 SQLite 中仅存储 SHA256 哈希，不存明文
- Service Token 不经过 Endpoint，直接透传到后端
- 日志中的 Token 仅记录前 8 位 + `***` 脱敏

### 10.2 后端地址保护

- 内部 Schema 文件（含真实 url）通过 `.gitignore` 或 Docker volume 隔离，不对外暴露
- 对外 Schema 中所有 url 统一指向 Endpoint 自身
- 管理 API 通过独立的 `ADMIN_API_KEY` 保护

### 10.3 输入校验

- 指令长度上限 512 字符（SPEC v1.0）
- 参数中禁止逗号、分号、换行符（SPEC v1.0）
- 参数数量上限 10 个
- 请求体大小限制（默认 1MB）

### 10.4 转发超时与重试

通过 `FORWARD_TIMEOUT` 环境变量控制超时，默认 30 秒。超时后返回 `408` 状态码。

5xx 错误自动重试，次数由 `FORWARD_MAX_RETRIES` 控制（默认 1 次）。4xx 错误不重试。

---

## 十一、与生态文档的对齐

### 11.1 与 SPEC v1.0

| SPEC 条款 | 本方案实现 |
|:---|:---|
| 2.1.1 调用地址 | `POST /cli/text_cli` |
| 2.1.2 请求结构 | 标准 JSON body + 双层 Token 头 |
| 2.1.3 响应结构 | 透传后端返回的 `{"rst_types":"text","rst_data":{...}}` |
| 2.2 HTTP 状态码 | 200/400/401/403/408/500 |
| 3.1 双层令牌 | Access Token 本地校验 + Service Token 透明转发 |
| 3.2 令牌传递 | `Service-token` 原样透传，不修改 |
| 4. Schema | `/text_cli_schema.json` 对外暴露 |

### 11.2 与生态宪章

| 宪章条款 | 对应实现 |
|:---|:---|
| 3.3 生态基础设施承诺 | 本方案即为"自建端点模板"的交付 |
| 7. 繁荣度量 | `daily_stats` 表 + 生态统计上报接口 |

### 11.3 与已有文档的协作

| 角色 | 使用的文档 |
|:---|:---|
| 端点运营者 | `Service_endpoint_CN.md`（本方案）+ `server/README.md` |
| 技能提供者 | `Building_text-cli_guide_CN.md` |
| Agent 开发者 | `Agent_integrated_CN.md` |
| 非开发者 | `Markdown2Text-cli_CN.md` |

---

## 十二、开发排期

| 阶段 | 内容 | 产出 | Python 版 | Workers 版 |
|:---|:---|:---|:---|:---|
| P1 | 指令解析器 + Schema 路由匹配 + HTTP 转发 | 可运行的最小端点 | ✅ 已完成 | ✅ 已完成 |
| P2 | Access Token 鉴权 + 对外 Schema 生成 | 安全的路由网关 | ✅ 已完成（含令牌桶限流） | ✅ 已完成（D1 滑动窗口限流） |
| P3 | D1/SQLite 记账模块 + 管理 API | 完整的记账与管理能力 | ✅ 已完成 | ✅ 已完成 |
| P4 | 部署文件与流程 | 可部署方案 | ✅ Docker 已完成 | ✅ wrangler deploy 已完成 |
| P5 | 部署说明文档 | 面向运维的完整指南 | ✅ `server/python/README_CN.md` | ✅ `server/js/README_CN.md` |
| P6 | 生态统计上报接口 | 生态衔接 | 预留（环境变量已定义） | 预留 |

两套语言版本并行开发，Python 版使用 Docker + SQLite，Workers 版使用 `wrangler deploy` + D1，共享相同的表结构和 API 定义。P1-P5 两版均已完成（PR #60）。

---

## 十三、待讨论问题

1. **Access Token 的签发**：当前方案内置了 Token 管理 API（创建/删除/额度控制/限流），是否足够？还是需要更复杂的签发流程（如注册邮箱验证）？ — *Python v1 已实现基本 CRUD，Workers 版同步实现，待运营验证*

2. **对外 Schema 的端点路径**：确认使用 `/text_cli_schema.json`（与 SPEC v1.0 和 Agent 集成文档一致）。 — *已确认并实现*

3. **`daily_stats` 聚合时机**：当前设计为实时更新（每笔调用后）。Python 版 SQLite 在早期流量下性能无问题；Workers 版 D1 同样实现实时更新，后续如有需要可改为定时聚合。 — *两版均已实现*

4. **转发时是否透传 Access Token 到后端**：SPEC 要求 Service Token 必须透传，但 Access Token 的透传是可选的。当前代码默认**不透传** Access Token（后端不需要知道调用方是谁，只需验证 Service Token）。 — *两版均已实现*

5. **`ENDPOINT_BASE_URL` 的配置**：当前必须手动配置。是否需要支持自动检测（从请求的 Host 头推断）？ — *两版均要求显式配置*

6. **Workers 版 D1 的冷启动性能**：D1 查询在网络条件良好时 <10ms，但跨区域延迟可能影响首次请求。是否需要在 Worker 内添加内存缓存层？ — *待运营验证*

---

> 本方案由 Lumen ✦ 基于 SPEC v1.0、ECOLOGICAL_CHARTER.md v1.0、Building_text-cli_guide_CN.md 及 DeepSeek_Chat.md 的任务指派起草，经与 lemondy 讨论修正架构后形成 v2 版本，再经 Tide 🌊 评审后 Python 端 v1 已实现（PR #9）。
>
> Python 端 P1-P5 已完成，Cloudflare Workers 端 P1-P5 已完成（PR #60），P6 预留。
>
> — Lumen ✦, 2026-04-30（初稿）/ 2026-05-01（v2.1 代码对齐更新）/ 2026-05-05（v3.0 Workers 方案更新）/ 2026-05-05（v3.1 实现同步）
