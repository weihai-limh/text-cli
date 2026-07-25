# A5-endpoint/js — 集成端点（Cloudflare Workers）

`text-cli` 的纯转发集成端点。位于调用方与指令服务之间，负责 IP 黑名单、ST 前缀校验、分时限流、Access Token 鉴权、指令路由转发、调用日志和用量统计。支持 1+N 聚合模式——从多个 A3 后端动态拉取 skills 并聚合为统一入口。基于 Cloudflare Workers + D1 构建，全球边缘部署。

---

## 目录结构

```
src/skeleton/endpoint/A5-endpoint/js/
├── src/
│   ├── index.js              # Worker 入口（路由 + 安全防线 + 指令转发 + 人道主义通道）
│   ├── parser.js             # 指令文本解析（正则 → ParsedDirective）
│   ├── schema-loader.js      # Schema 加载（动态 skills 聚合 / D1 回退）
│   ├── backend-registry.js   # 1+N 聚合引擎（拉取 skills → 聚合 → 来源追踪）
│   ├── auth.js               # Access Token 鉴权（D1 多 Token + 令牌桶限流）+ ST 前缀校验
│   ├── forwarder.js          # 请求转发器（fetch API、重试、记账）
│   ├── admin.js              # 管理 API（Token CRUD / 统计查询 / Schema 重载）
│   ├── ip-guard.js           # IP 黑名单（CIDR 匹配，无条件拒绝）
│   └── rate-limiter.js       # 分时限流器（D1 持久化，POST/GET 独立计数）
├── migrations/
│   ├── 0001_init.sql         # D1 初始迁移（Token / 调用日志 / 日统计 / 指令表）
│   └── 0002_rate_limits.sql  # D1 限流计数器表
├── test/
│   ├── parser.test.js        # 指令解析器测试
│   ├── auth.test.js          # Token 工具函数测试
│   └── schema-loader.test.js # Schema 加载器测试
├── api-proxy.js
├── package.json
└── vitest.config.js
```

---

## 核心模块职责

| 模块 | 职责 |
|:---|:---|
| `src/parser.js` | 将 `指令:领域;动作,参数...` 解析为结构化数据，含参数转义字符校验 |
| `src/auth.js` | 校验 `Authorization: Bearer <token>` + 频率限制 + ST 前缀注册校验 + 黑名单 |
| `src/schema-loader.js` | Skills 聚合加载：优先从 A3_BACKENDS 动态拉取，回退到 D1 指令表 |
| `src/backend-registry.js` | 1+N 聚合引擎：从 N 个 A3 拉取 `/text-cli/skills` → 合并 → 来源追踪 → ST 前缀自动登记 |
| `src/forwarder.js` | 转发到后端指令服务，支持超时和自动重试（5xx），D1 记账 |
| `src/admin.js` | 管理 API 路由：健康检查、统计查询、Token CRUD、Schema 重载 |
| `src/ip-guard.js` | IP 黑名单（支持 CIDR），所有请求入口处检查 |
| `src/rate-limiter.js` | 全端点小时级计数器（D1 持久化，POST/GET 独立阈值） |
| `src/index.js` | Worker 入口，请求路由分发 + 安全防线 + 人道主义通道 |

---

## 安全防线体系

```
请求到达 A5 (Workers)
    │
    ▼
① IP 黑名单          ← 无条件拒绝（CF-Connecting-IP）
    │ 通过
    ▼
② ST 前缀注册校验      ← A3 注册时提供 ST 前缀，未注册 → 403
    │ 通过
    ▼
③ 分时限流           ← D1 持久化小时级计数器（POST/GET 独立）
    │ 通过
    ▼
④ Access Token 鉴权   ← D1 验证
    │
    ▼
⑤ 令牌桶限流          ← per-token (call_logs 滑动窗口)
    │
    ▼
   正常处理
```

---

## 端点全景

| 端点 | 方法 | Token | 三道防线 | 默认 | 用途 |
|------|------|-------|---------|------|------|
| `/text-cli/cli` | POST | 双 Token | ✅ 全部生效（1000/h） | 开 | 业务执行 |
| `/text_cli_schema.json` | GET | 无 | ① 仅 IP | 开 | 聚合 Schema |
| `/text-cli/cli` | GET | 无 | ①+③（放宽到10000/h） | 关 | 人道主义通道 |

---

## 数据流

```
调用方 ──Bearer Token──> Cloudflare Workers
                           │
                           ├─ ① isIPBlocked()          — IP 黑名单
                           ├─ ② isSTPrefix*()          — ST 前缀校验
                           ├─ ③ checkRateLimit()       — D1 分时限流
                           ├─ verifyAccessToken()      — D1 鉴权 + 频率
                           ├─ parseDirective()         — 解析指令
                           ├─ findBackendUrl()         — 查聚合表找来源 A3
                           ├─ forwardRequest()         — fetch() 转发（含重试）
                           ├─ incrementUsage()         — D1 计数
                           └─ dailyStats               — D1 按日聚合
```

---

## 快速启动

```bash
cd src/skeleton/endpoint/A5-endpoint/js
npm install

wrangler dev
```

启动后可访问：
- `GET /text_cli_schema.json` — 对外 Schema（动态聚合）
- `GET /health` — 健康检查
- `POST /text-cli/cli` — 发送指令（转发到后端）
- 历史：v1.2 使用 `/cli/text_cli`，v1.3 起统一为 `/text-cli/cli`
- `GET /text-cli/cli?skill_id=xxx` — 人道主义通道（需 `ENABLE_PUBLIC_CLI=true`）

---

## 部署

### 1. 创建 D1 数据库

```bash
wrangler d1 create text-cli-endpoint-db
```

将输出的 `database_id` 填入 `wrangler.toml` 的 `[[d1_databases]]` 部分。

### 2. 执行数据库迁移

```bash
wrangler d1 execute text-cli-endpoint-db --file=migrations/0001_init.sql
wrangler d1 execute text-cli-endpoint-db --file=migrations/0002_rate_limits.sql
```

### 3. 配置 A3 后端

编辑 `wrangler.toml`，设置 `A3_BACKENDS` 变量：

```toml
[vars]
A3_BACKENDS = "http://a3-service1:28050,http://a3-service2:28050"
```

Skills 将在首次请求时自动从后端拉取并聚合。不需手动导入 Schema。

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
| POST | `/api/schema/reload` | 重载 skills（重新从所有 A3 拉取） |

---

## wrangler 配置

```toml
[vars]
ENDPOINT_BASE_URL = "https://my-endpoint.workers.dev"
ACCESS_TOKEN_REQUIRED = "true"
ENABLE_PUBLIC_CLI = "false"
FORWARD_TIMEOUT = "30"
FORWARD_MAX_RETRIES = "1"
A3_BACKENDS = ""
A3_BACKEND_TOKENS = ""
A3_REGISTERED_PREFIXES = ""
ST_PREFIX_BLACKLIST = ""
IP_BLACKLIST = ""
RATE_LIMIT_PER_HOUR = "1000"
RATE_LIMIT_GET_PER_HOUR = "10000"
```

---

## 测试

```bash
npm test
```

---

## 与 Python 版的对应关系

| Python 模块 | Workers 模块 | 差异 |
|:---|:---|:---|
| `core/parser.py` | `src/parser.js` | 逻辑一致，正则相同 |
| `core/auth.py` | `src/auth.js` | Python 内存令牌桶 → D1 滑动窗口查询；均含 ST 前缀校验 |
| `core/database.py` | D1（无需代码） | SQLite 文件 → D1 binding |
| `core/forwarder.py` | `src/forwarder.js` | httpx → fetch() |
| `core/schema_loader.py` | `src/schema-loader.js` | 均支持动态聚合 + 静态回退模式 |
| `core/backend_registry.py` | `src/backend-registry.js` | 1+N 聚合引擎，拉取 `/text-cli/skills` |
| `core/ip_guard.py` | `src/ip-guard.js` | 均支持 CIDR 匹配 |
| `core/rate_limiter.py` | `src/rate-limiter.js` | 内存滑动窗口 → D1 持久化 |
| `api/*.py` | `src/admin.js` | FastAPI 路由 → 单文件路由分发 |
| `main.py` | `src/index.js` | ASGI 入口 → fetch 事件处理器 |
