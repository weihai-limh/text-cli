# server/js — 集成端点（Cloudflare Workers）

`text-cli` 的纯转发集成端点。位于调用方与指令服务之间，负责 Access Token 鉴权、指令路由转发、调用日志和用量统计。基于 Cloudflare Workers + D1 构建，全球边缘部署。

---

## 目录结构

```
server/js/
├── src/
│   ├── index.js             # Worker 入口（路由 + 指令转发）
│   ├── parser.js            # 指令文本解析（正则 → ParsedDirective）
│   ├── schema-loader.js     # 双 Schema 加载与 URL 重写（D1 / 静态文件）
│   ├── auth.js              # Access Token 鉴权（D1 多 Token + 令牌桶限流）
│   ├── forwarder.js         # 请求转发器（fetch API、重试、记账）
│   ├── admin.js             # 管理 API（Token CRUD / 统计查询 / Schema 重载）
│   └── config/
│       └── schema.json      # 内部路由 Schema（含真实后端 url）
├── migrations/
│   └── 0001_init.sql        # D1 数据库迁移脚本
├── scripts/
│   └── seed-schema.js       # 将静态 Schema 导入 D1 的辅助脚本
├── test/
│   ├── parser.test.js       # 指令解析器测试（11 个用例）
│   ├── auth.test.js         # Token 工具函数测试（7 个用例）
│   └── schema-loader.test.js # Schema 加载器测试（6 个用例）
├── wrangler.toml
├── package.json
└── vitest.config.js
```

---

## 核心模块职责

| 模块 | 职责 |
|:---|:---|
| `src/parser.js` | 将 `指令:领域;动作,参数...` 解析为结构化数据，含参数转义字符校验 |
| `src/auth.js` | 校验 `Authorization: Bearer <token>`，支持配额和频率限制，SHA256 哈希匹配 |
| `src/schema-loader.js` | 双 Schema：内部（含真实后端 url）/ 外部（URL 重写为自身端点地址），支持 D1 和静态文件两种数据源 |
| `src/forwarder.js` | 转发到后端指令服务，支持超时和自动重试（5xx），D1 记账 |
| `src/admin.js` | 管理 API 路由：健康检查、统计查询、Token CRUD、Schema 重载 |
| `src/index.js` | Worker 入口，请求路由分发 |

---

## 数据流

```
调用方 ──Bearer Token──> Cloudflare Workers
                           │
                           ├─ verify_access_token() — D1 鉴权 + 频率
                           ├─ parse_directive()     — 解析指令
                           ├─ find_backend_url()    — D1 或静态 Schema 路由匹配
                           ├─ forward_request()     — fetch() 转发（含重试）
                           ├─ increment_usage()     — D1 计数
                           └─ daily_stats           — D1 按日聚合
```

---

## 快速启动

```bash
cd server/js
npm install

# 开发模式（本地模拟 D1）
wrangler dev
```

启动后可访问：
- `GET /text_cli_schema.json` — 对外 Schema
- `GET /health` — 健康检查
- `GET /api/health` — 详细健康检查（含数据库状态）
- `POST /cli/text_cli` — 发送指令（转发到后端）

---

## 部署

### 1. 创建 D1 数据库

```bash
wrangler d1 create text-cli-endpoint-db
```

将输出的 `database_id` 填入 `wrangler.toml` 的 `[[d1_databases]]` 部分，并取消注释。

### 2. 执行数据库迁移

```bash
wrangler d1 execute text-cli-endpoint-db --file=migrations/0001_init.sql
```

### 3. 导入内部路由 Schema

编辑 `src/config/schema.json`，将 `url` 替换为真实的后端技能服务地址，然后：

```bash
node scripts/seed-schema.js
```

按输出提示执行 SQL 命令导入 D1。

### 4. 敏感配置存入 Worker Secrets

```bash
wrangler secret put ADMIN_API_KEY
```

### 5. 部署

```bash
wrangler deploy
```

---

## 管理 API

所有管理端点需要 `X-Admin-Key` 请求头（值需与 `ADMIN_API_KEY` 环境变量匹配）。

| 方法 | 路径 | 说明 |
|:---|:---|:---|
| GET | `/api/health` | 健康检查（无需 Admin Key） |
| GET | `/api/stats/summary` | 调用统计概览 |
| GET | `/api/stats/daily?date=YYYY-MM-DD` | 按日统计明细 |
| GET | `/api/stats/token/{prefix}` | 指定 Token 的调用统计 |
| GET | `/api/tokens` | Access Token 列表 |
| POST | `/api/tokens` | 创建新 Access Token |
| PUT | `/api/tokens/{id}` | 更新 Token（额度、限流、启停） |
| DELETE | `/api/tokens/{id}` | 删除 Token |
| POST | `/api/schema/reload` | 重载内部 Schema |

---

## 环境变量与 wrangler 配置

```toml
[vars]
ENDPOINT_BASE_URL = "https://my-endpoint.workers.dev"
ACCESS_TOKEN_REQUIRED = "true"
FORWARD_TIMEOUT = "30"
FORWARD_MAX_RETRIES = "1"
```

| 变量 | 默认值 | 说明 |
|:---|:---|:---|
| `ENDPOINT_BASE_URL` | 空 | 自身端点地址，用于重写外部 Schema URL |
| `ACCESS_TOKEN_REQUIRED` | `true` | 是否强制要求 Access Token（`false` 为开放模式） |
| `ADMIN_API_KEY` | 空 | 管理 API 密钥（建议存入 Worker Secrets） |
| `FORWARD_TIMEOUT` | `30` | 后端请求超时（秒） |
| `FORWARD_MAX_RETRIES` | `1` | 5xx 重试次数 |

---

## 测试

```bash
npm test
```

24 个单元测试覆盖：指令解析器、Token 工具函数、Schema 加载器。

---

## 与 Python 版的对应关系

| Python 模块 | Workers 模块 | 差异 |
|:---|:---|:---|
| `core/parser.py` | `src/parser.js` | 逻辑一致，正则相同 |
| `core/auth.py` | `src/auth.js` | Python 内存令牌桶 → D1 滑动窗口查询 |
| `core/database.py` | D1（无需代码） | SQLite 文件 → D1 binding |
| `core/forwarder.py` | `src/forwarder.js` | httpx → fetch() |
| `core/schema_loader.py` | `src/schema-loader.js` | JSON 文件 → D1 + 静态文件双模式 |
| `api/*.py` | `src/admin.js` | FastAPI 路由 → 单文件路由分发 |
| `main.py` | `src/index.js` | ASGI 入口 → fetch 事件处理器 |
