# A5-endpoint/python — 集成端点（FastAPI）

`text-cli` 的纯转发集成端点。位于调用方与指令服务之间，负责 IP 黑名单、ST 前缀校验、分时限流、Access Token 鉴权、指令路由转发、调用日志和用量统计。支持 1+N 聚合模式——从多个 A3 后端动态拉取 skills 并聚合为统一入口。

---

## 目录结构

```
src/skeleton/endpoint/A5-endpoint/python/
├── main.py                          # FastAPI 入口（lifespan + 指令接收与转发 + 安全中间件）
├── requirements.txt
├── .gitignore
├── core/
│   ├── __init__.py
│   ├── parser.py                    # 指令文本解析（正则 → ParsedDirective）
│   ├── auth.py                      # Access Token 鉴权 + 频率限制 + ST 前缀校验
│   ├── database.py                  # SQLite 数据库（调用日志 / 日统计 / Token 表）
│   ├── forwarder.py                 # HTTP 转发器（超时控制 + 重试 + skills 转发）
│   ├── schema_loader.py             # Schema 加载（动态 skills 聚合 / 静态回退）
│   ├── backend_registry.py          # 1+N 聚合引擎（拉取 skills → 聚合 → 来源追踪）
│   ├── ip_guard.py                  # IP 黑名单（CIDR 匹配，无条件拒绝）
│   └── rate_limiter.py              # 分时限流器（POST/GET 独立小时级计数器）
└── api/
    ├── __init__.py
    ├── health.py                    # 健康检查（数据库 + Schema + 后端连通性）
    ├── stats.py                     # 调用统计（汇总 / 按日 / 按 Token）
    └── tokens.py                    # Access Token 管理（CRUD）
```

---

## 核心模块职责

| 模块 | 职责 |
|:---|:---|
| `core/parser.py` | 将 `指令:领域;动作,参数...` 解析为结构化数据，含参数转义字符校验 |
| `core/auth.py` | Access Token 鉴权 + 令牌桶限流；ST 前缀注册校验 + 黑名单 |
| `core/database.py` | SQLite 三表：`call_logs`、`daily_stats`、`access_tokens` |
| `core/forwarder.py` | 转发到后端指令服务 + skills 转发，支持超时和自动重试（5xx） |
| `core/schema_loader.py` | Skills 聚合加载：优先从 A3_BACKENDS 动态拉取，回退到静态文件 |
| `core/backend_registry.py` | 1+N 聚合引擎：从 N 个 A3 拉取 `/text-cli/skills` → 合并 → 来源追踪 → ST 前缀自动登记 |
| `core/ip_guard.py` | IP 黑名单（支持 CIDR），所有请求入口处检查 |
| `core/rate_limiter.py` | 全端点小时级计数器（POST 1000/h + GET 10000/h 独立配置） |
| `api/health.py` | `/api/health` — 数据库连通性、Schema 状态、后端列表 |
| `api/stats.py` | `/api/stats/*` — 调用汇总、按日、按 Token |
| `api/tokens.py` | `/api/tokens/*` — Token CRUD（需 Admin Key） |

---

## 安全防线体系

```
请求到达 A5
    │
    ▼
① IP 黑名单          ← 无条件拒绝——黑名单 IP 永远不可访问
    │ 通过
    ▼
② ST 前缀注册校验      ← A3 注册时提供 ST 前缀，未注册 → 403
    │ 通过
    ▼
③ 分时限流           ← 全端点小时级计数器（POST/GET 独立）
    │ 通过
    ▼
④ Access Token 鉴权   ← 现有
    │
    ▼
⑤ 令牌桶限流          ← per-token
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
调用方 ──Bearer Token──> A5 Endpoint
                           │
                           ├─ ① is_ip_blocked()       — IP 黑名单
                           ├─ ② is_st_prefix_*()      — ST 前缀校验
                           ├─ ③ check_rate_limit()    — 分时限流
                           ├─ verify_access_token()   — 鉴权 + 频率
                           ├─ parse_directive()       — 解析指令
                           ├─ find_backend_url()      — 查聚合表找来源 A3
                           ├─ forward_request()       — HTTP 转发（含重试）
                           ├─ increment_usage()       — 计数
                           └─ daily_stats             — 按日聚合
```

---

## 快速启动

```bash
cd src/skeleton/endpoint/A5-endpoint/python
pip install -r requirements.txt

export ENDPOINT_BASE_URL=http://localhost:29050
export ACCESS_TOKEN_REQUIRED=false

# 1+N 模式（配置一个或多个 A3 后端）
export A3_BACKENDS=http://a3-service:28050,http://a3-service2:28050

uvicorn main:app --host 0.0.0.0 --port 29050
```

启动后可访问：
- `GET /text_cli_schema.json` — 对外 Schema（动态聚合）
- `GET /health` — 健康检查
- `GET /api/health` — 详细健康检查
- `POST /text-cli/cli` — 发送指令（转发到后端）
- 历史：v1.2 使用 `/cli/text_cli`，v1.3 起统一为 `/text-cli/cli`
- `GET /text-cli/cli?skill_id=xxx` — 人道主义通道（需 `ENABLE_PUBLIC_CLI=true`）

---

## 全部环境变量

| 变量 | 默认值 | 说明 |
|:---|:---|:---|
| `ENDPOINT_BASE_URL` | 空 | 自身端点地址，用于重写外部 Schema URL |
| `ACCESS_TOKEN_REQUIRED` | `true` | 是否强制要求 Access Token |
| `ENABLE_PUBLIC_CLI` | `false` | 开启人道主义 GET 通道 |
| `ADMIN_API_KEY` | 空 | 设置后启用管理 API |
| `DB_PATH` | `data/textcli.db` | SQLite 数据库路径 |
| `FORWARD_TIMEOUT` | `30` | 后端请求超时（秒） |
| `FORWARD_MAX_RETRIES` | `1` | 5xx 重试次数 |
| `A3_BACKENDS` | 空 | 逗号分隔的 A3 URL（含端口） |
| `A3_BACKEND_TOKENS` | 空 | 对应的 Service Token（逗号分隔） |
| `A3_REGISTERED_PREFIXES` | 空 | A3 注册的 ST 前缀（逗号分隔，与 BACKENDS 对应） |
| `ST_PREFIX_BLACKLIST` | 空 | ST 前缀黑名单（覆写注册表） |
| `IP_BLACKLIST` | 空 | 逗号分隔 IP/CIDR，无条件拒绝 |
| `RATE_LIMIT_PER_HOUR` | `1000` | POST 通道全局限流 |
| `RATE_LIMIT_GET_PER_HOUR` | `10000` | GET 通道独立限流 |

### Docker

Docker 部署文件在 `deploy/A5-endpoint/container/`：

```bash
cd deploy/A5-endpoint/container
docker compose up --build -d
```
