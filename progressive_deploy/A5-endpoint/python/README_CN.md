# server/python — 集成端点

`text-cli` 的纯转发集成端点。位于调用方与指令服务之间，负责 Access Token 鉴权、指令路由转发、调用日志和用量统计。

---

## 目录结构

```
server/python/
├── main.py                          # FastAPI 入口（lifespan + 指令接收与转发）
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .gitignore
├── config/
│   └── text_cli_schema.json         # 指令 Schema（定义指令→后端 URL 映射）
├── core/
│   ├── __init__.py
│   ├── parser.py                    # 指令文本解析（正则 → ParsedDirective）
│   ├── auth.py                      # Access Token 鉴权 + 频率限制
│   ├── database.py                  # SQLite 数据库（调用日志 / 日统计 / Token 表）
│   ├── forwarder.py                 # HTTP 转发器（超时控制 + 重试）
│   └── schema_loader.py             # 双 Schema 加载（内部/外部 URL 重写）
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
| `core/auth.py` | 校验 `Authorization: Bearer <token>`，支持配额和频率限制，SHA256 哈希匹配 |
| `core/database.py` | SQLite 三表：`call_logs`、`daily_stats`、`access_tokens` |
| `core/forwarder.py` | 转发到后端指令服务，支持超时和自动重试（5xx） |
| `core/schema_loader.py` | 双 Schema：内部/外部 URL 重写为自身端点地址 |
| `api/health.py` | `/api/health` — 数据库连通性、Schema 状态、后端列表 |
| `api/stats.py` | `/api/stats/*` — 调用汇总、按日、按 Token |
| `api/tokens.py` | `/api/tokens/*` — Token CRUD（需 Admin Key） |

---

## 数据流

```
调用方 ──Bearer Token──> 集成端点
                           │
                           ├─ verify_access_token() — 鉴权 + 频率
                           ├─ parse_directive()     — 解析指令
                           ├─ find_backend_url()    — 查找后端
                           ├─ forward_request()     — HTTP 转发（含重试）
                           ├─ increment_usage()     — 计数
                           └─ daily_stats           — 按日聚合
```

---

## 快速启动

```bash
cd server/python
pip install -r requirements.txt

export ENDPOINT_BASE_URL=http://localhost:8000
export ACCESS_TOKEN_REQUIRED=false

uvicorn main:app --host 0.0.0.0 --port 8000
```

启动后可访问：
- `GET /text_cli_schema.json` — 对外 Schema
- `GET /api/health` — 健康检查
- `POST /cli/text_cli` — 发送指令（转发到后端）

### 关键环境变量

| 变量 | 默认值 | 说明 |
|:---|:---|:---|
| `ENDPOINT_BASE_URL` | 空 | 自身端点地址，用于重写外部 Schema URL |
| `ACCESS_TOKEN_REQUIRED` | `true` | 是否强制要求 Access Token |
| `ADMIN_API_KEY` | 空 | 设置后启用 `/api/tokens` 和 `/api/stats` |
| `DB_PATH` | `data/textcli.db` | SQLite 数据库路径 |
| `FORWARD_TIMEOUT` | `30` | 后端请求超时（秒） |
| `FORWARD_MAX_RETRIES` | `1` | 5xx 重试次数 |

### Docker

```bash
docker compose up --build -d
```
