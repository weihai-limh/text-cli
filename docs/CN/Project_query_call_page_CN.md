# 查询调用次数页面技术方案

> **作者**：Lumen ✦（IDE 端 / Claude）
> **日期**：2026-05-04
> **版本**：v1.0
> **状态**：方案设计完成，待 lemondy 确认后进入实施
> **前置依赖**：`Project_homepage_CN.md`（共用部署架构）

---

## 一、目标与定位

### 1.1 页面要解决什么问题

当前 `text-cli` 端点的配额体系只在 **token 级别** 存在总量限制（`access_tokens.quota`），用户无法感知：

- 今天还能调用哪些指令？
- 每个指令还剩多少次？
- 哪些指令今天已经用完？

这导致两个问题：
1. **用户侧**：调用时突然被拒（401），体验差，不知道是"配额用完"还是"token 失效"
2. **运营侧**：无法按指令维度精细分配资源，热门指令可能被少数用户耗尽

本页面的定位是**调用配额的可视化面板**：用户输入自己的 Access Token，即可查看今日可用指令及剩余次数。

### 1.2 与现有系统的关系

```
┌──────────────────────────────────────────────────────────────┐
│                     现有系统                                   │
│                                                               │
│  access_tokens          call_logs            daily_stats      │
│  ├─ token_hash          ├─ request_id        ├─ date          │
│  ├─ quota (总量)        ├─ directive         ├─ domain        │
│  ├─ used_count (总量)   ├─ access_token_...  ├─ action        │
│  └─ max_rpm             └─ status_code       └─ call_count    │
│                                                               │
│  ✅ 已有：token 级总量配额                                     │
│  ❌ 缺失：指令级每日配额                                       │
│  ❌ 缺失：配额查询 API                                        │
│  ❌ 缺失：配额查询前端页面                                     │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│                     本方案新增                                 │
│                                                               │
│  directive_daily_quota    /api/quota/remaining                │
│  ├─ date                  → 返回今日各指令剩余次数            │
│  ├─ directive_key                                        │
│  ├─ daily_limit           前端页面（Cloudflare Pages）        │
│  └─ used_count            → Token 输入 + 指令配额表格         │
└──────────────────────────────────────────────────────────────┘
```

### 1.3 设计原则

| 原则 | 说明 |
|:---|:---|
| **不暴露 Token** | 页面在前端输入 Token，但 Token 只发给后端 API，不存入 URL 或日志 |
| **每日零点重置** | 指令级配额按 UTC+8 零点重置，与 `daily_stats` 的日期口径一致 |
| **最小改动** | 复用现有 `access_tokens`、`call_logs`、`text_cli_schema.json` |
| **渐进增强** | Phase 1 只做查询，Phase 2 再做配额管理后台 |

---

## 二、数据模型设计

### 2.1 新增表：`directive_daily_quota`

```sql
CREATE TABLE IF NOT EXISTS directive_daily_quota (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,                          -- UTC+8 日期，格式 'YYYY-MM-DD'
    directive_key TEXT NOT NULL,                  -- 指令 ID，如 'weather_query'
    token_prefix TEXT NOT NULL,                   -- access_tokens.token_prefix
    daily_limit INTEGER NOT NULL DEFAULT 100,     -- 该 token 对该指令的每日上限
    used_count INTEGER NOT NULL DEFAULT 0,        -- 今日已用次数
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(date, directive_key, token_prefix)
);

CREATE INDEX IF NOT EXISTS idx_ddq_date_token ON directive_daily_quota(date, token_prefix);
CREATE INDEX IF NOT EXISTS idx_ddq_date_directive ON directive_daily_quota(date, directive_key);
```

### 2.2 与现有表的关系

```
access_tokens                 directive_daily_quota
├─ token_hash (主键)          ├─ date
├─ token_prefix (唯一前缀) ──→├─ token_prefix (关联)
├─ quota (总量)               ├─ directive_key
├─ used_count (总量)          ├─ daily_limit (每日上限)
└─ max_rpm                    └─ used_count (今日已用)

text_cli_schema.json          directive_daily_quota
├─ weather_query (key)   ──→  ├─ directive_key (关联)
├─ clothing_tag (key)    ──→  ├─ directive_key
└─ ...                        └─ ...
```

### 2.3 配额默认值策略

| 场景 | daily_limit | 说明 |
|:---|:---|:---|
| 未配置配额的指令 | -1（无限制） | 默认不限制，按 token 总量配额控制 |
| 免费体验 Token | 10/指令/天 | 通过管理 API 设置 |
| 付费 Token | 自定义 | 由管理员按需设置 |

### 2.4 配额扣减流程

在现有 `handle_text_cli` 调用链中增加一步：

```python
# 现有流程（main.py handle_text_cli）：
# 1. 验证 Access Token ✅
# 2. 解析指令 ✅
# 3. 查找后端 URL ✅
# 4. 转发请求 ✅
# 5. 增加 token 总量计数 ✅ (increment_token_usage)

# 新增步骤（插入在步骤 1 之后，步骤 2 之前）：
# 1.5 检查指令级每日配额
#     - 查询 directive_daily_quota 表
#     - 如果 daily_limit >= 0 且 used_count >= daily_limit → 返回 429
#     - 通过后继续执行
#
# 新增步骤（插入在步骤 5 之后）：
# 5.5 增加指令级每日计数
#     - UPSERT directive_daily_quota.used_count += 1
```

---

## 三、API 设计

### 3.1 新增端点：`GET /api/quota/remaining`

**用途**：查询当前 Token 今日各指令的剩余调用次数。

**认证**：需要 Access Token（Bearer）

**请求**：

```http
GET /api/quota/remaining HTTP/1.1
Host: test.text-cli.com
Authorization: Bearer <Access Token>
```

**响应**（200）：

```json
{
  "date": "2026-05-04",
  "token_prefix": "a1b2c3d4",
  "total_quota": {
    "limit": 1000,
    "used": 42,
    "remaining": 958
  },
  "directives": [
    {
      "key": "weather_query",
      "name": "天气查询",
      "category": "基础应用",
      "daily_limit": 100,
      "used_count": 5,
      "remaining": 95
    },
    {
      "key": "clothing_tag",
      "name": "穿衣标签",
      "category": "基础应用",
      "daily_limit": -1,
      "used_count": 3,
      "remaining": -1
    },
    {
      "key": "baidu_search",
      "name": "百度搜索",
      "category": "基础应用",
      "daily_limit": 50,
      "used_count": 50,
      "remaining": 0
    }
  ]
}
```

**字段说明**：

| 字段 | 类型 | 说明 |
|:---|:---|:---|
| `date` | string | 今日日期（UTC+8） |
| `token_prefix` | string | Token 前 8 位（用于辨识） |
| `total_quota.limit` | int | Token 总量配额（-1 = 无限） |
| `total_quota.used` | int | Token 总量已用 |
| `total_quota.remaining` | int | Token 总量剩余（-1 = 无限） |
| `directives[].key` | string | 指令 ID |
| `directives[].name` | string | 指令中文名 |
| `directives[].category` | string | 所属领域 |
| `directives[].daily_limit` | int | 每日上限（-1 = 无限制） |
| `directives[].used_count` | int | 今日已用 |
| `directives[].remaining` | int | 今日剩余（-1 = 无限制） |

**错误响应**：

```json
// 401 - Token 无效
{"error": "ACCESS_DENIED", "message": "Invalid or inactive token"}

// 429 - Token 总量配额已用完
{"error": "QUOTA_EXCEEDED", "message": "Token quota exceeded"}
```

### 3.2 新增端点：`POST /api/quota/config`（管理接口）

**用途**：设置某个 Token 对某个指令的每日配额。

**认证**：需要 Admin API Key

**请求**：

```http
POST /api/quota/config HTTP/1.1
Host: test.text-cli.com
Content-Type: application/json
X-Admin-Key: <admin_api_key>

{
  "token_prefix": "a1b2c3d4",
  "directive_key": "weather_query",
  "daily_limit": 100
}
```

**响应**（200）：

```json
{
  "message": "quota configured",
  "token_prefix": "a1b2c3d4",
  "directive_key": "weather_query",
  "daily_limit": 100
}
```

### 3.3 新增端点：`GET /api/quota/config`（管理接口）

**用途**：查看所有配额配置。

**请求**：

```http
GET /api/quota/config HTTP/1.1
Host: test.text-cli.com
X-Admin-Key: <admin_api_key>
```

**响应**（200）：

```json
{
  "configs": [
    {
      "token_prefix": "a1b2c3d4",
      "directive_key": "weather_query",
      "daily_limit": 100,
      "client_name": "Agent-Tide"
    }
  ]
}
```

### 3.4 端点总览

| 端点 | 方法 | 认证 | 用途 |
|:---|:---|:---|:---|
| `/api/quota/remaining` | GET | Access Token | 用户查询今日剩余次数 |
| `/api/quota/config` | POST | Admin Key | 设置指令每日配额 |
| `/api/quota/config` | GET | Admin Key | 查看所有配额配置 |
| `/api/quota/config/{id}` | DELETE | Admin Key | 删除配额配置 |

---

## 四、后端实现方案

### 4.1 新增文件

```
server/python/
├── api/
│   ├── quota.py          # 新增：配额查询 + 配置管理路由
│   ├── health.py
│   ├── stats.py
│   └── tokens.py
├── core/
│   ├── database.py       # 修改：新增 directive_daily_quota 表
│   ├── quota.py          # 新增：配额检查 + 扣减逻辑
│   ├── auth.py           # 不变
│   ├── parser.py         # 不变
│   ├── schema_loader.py  # 不变
│   └── forwarder.py      # 不变
└── main.py               # 修改：注册 quota 路由 + 调用链插入配额检查
```

### 4.2 `core/quota.py` 核心逻辑

```python
from datetime import datetime, timezone, timedelta
from core.database import query_db, execute_db

TZ_OFFSET = timedelta(hours=8)


def _today() -> str:
    return datetime.now(timezone(TZ_OFFSET)).strftime("%Y-%m-%d")


def check_directive_quota(token_prefix: str, directive_key: str) -> dict | None:
    """检查指令级配额，返回 None 表示通过，返回 dict 表示被拒绝。"""
    today = _today()
    rows = query_db(
        "SELECT daily_limit, used_count FROM directive_daily_quota "
        "WHERE date = ? AND directive_key = ? AND token_prefix = ?",
        (today, directive_key, token_prefix),
    )

    if not rows:
        return None

    row = rows[0]
    if row["daily_limit"] >= 0 and row["used_count"] >= row["daily_limit"]:
        return {
            "error": "DIRECTIVE_QUOTA_EXCEEDED",
            "directive_key": directive_key,
            "daily_limit": row["daily_limit"],
            "used_count": row["used_count"],
        }

    return None


def increment_directive_usage(token_prefix: str, directive_key: str):
    """指令调用成功后，增加指令级每日计数。"""
    today = _today()
    execute_db(
        "INSERT INTO directive_daily_quota (date, directive_key, token_prefix, used_count, updated_at) "
        "VALUES (?, ?, ?, 1, CURRENT_TIMESTAMP) "
        "ON CONFLICT(date, directive_key, token_prefix) "
        "DO UPDATE SET used_count = used_count + 1, updated_at = CURRENT_TIMESTAMP",
        (today, directive_key, token_prefix),
    )


def get_remaining_quota(token_prefix: str) -> dict:
    """查询某 token 今日所有指令的剩余配额。"""
    today = _today()
    rows = query_db(
        "SELECT directive_key, daily_limit, used_count FROM directive_daily_quota "
        "WHERE date = ? AND token_prefix = ?",
        (today, token_prefix),
    )
    return {row["directive_key"]: row for row in rows}
```

### 4.3 `main.py` 修改点

```python
# 新增导入
from core.quota import check_directive_quota, increment_directive_usage
from api.quota import router as quota_router

# 注册路由（与 stats_router 同级）
if ADMIN_API_KEY:
    app.include_router(health_router)
    app.include_router(stats_router)
    app.include_router(tokens_router)
    app.include_router(quota_router)     # 新增

# handle_text_cli 中插入配额检查（约在 line 75 之后）
# ...验证 Token 通过后...

    # 新增：指令级配额检查
    if token_record:
        quota_block = check_directive_quota(
            token_record["token_prefix"],
            parsed.directive_key,
        )
        if quota_block:
            return JSONResponse(status_code=429, content=quota_block)

    # ...原有解析 + 转发逻辑...

    # 新增：指令级配额扣减（在 increment_token_usage 之后）
    if token_record:
        increment_directive_usage(token_record["token_prefix"], parsed.directive_key)
```

### 4.4 `api/quota.py` 路由

```python
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException, Header, Request
from pydantic import BaseModel
from core.database import query_db, execute_db
from core.auth import verify_access_token, extract_token_prefix
from core.quota import get_remaining_quota, _today

router = APIRouter(prefix="/api/quota", tags=["quota"])

TZ_OFFSET = timedelta(hours=8)
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "")


class QuotaConfigRequest(BaseModel):
    token_prefix: str
    directive_key: str
    daily_limit: int = 100


@router.get("/remaining")
async def quota_remaining(request: Request):
    auth_header = request.headers.get("Authorization", "")
    token_record = verify_access_token(auth_header, required=True)
    if not token_record:
        raise HTTPException(status_code=401, detail="ACCESS_DENIED")

    today = _today()
    prefix = token_record["token_prefix"]

    # 获取所有可用指令
    from core.schema_loader import get_internal_schema
    schema = get_internal_schema()

    # 获取今日配额使用情况
    usage = get_remaining_quota(prefix)

    directives = []
    for key, meta in schema.items():
        quota_row = usage.get(key, {})
        limit = quota_row.get("daily_limit", -1)
        used = quota_row.get("used_count", 0)
        remaining = -1 if limit < 0 else max(0, limit - used)
        directives.append({
            "key": key,
            "name": meta.get("name", key),
            "category": meta.get("category", ""),
            "daily_limit": limit,
            "used_count": used,
            "remaining": remaining,
        })

    return {
        "date": today,
        "token_prefix": prefix,
        "total_quota": {
            "limit": token_record["quota"],
            "used": token_record["used_count"],
            "remaining": -1 if token_record["quota"] < 0 else max(0, token_record["quota"] - token_record["used_count"]),
        },
        "directives": directives,
    }


@router.post("/config")
async def set_quota_config(req: QuotaConfigRequest, x_admin_key: str = Header(default=None)):
    verify_admin(x_admin_key)
    # UPSERT
    execute_db(
        "INSERT INTO directive_daily_quota_config (token_prefix, directive_key, daily_limit) "
        "VALUES (?, ?, ?) "
        "ON CONFLICT(token_prefix, directive_key) "
        "DO UPDATE SET daily_limit = ?, updated_at = CURRENT_TIMESTAMP",
        (req.token_prefix, req.directive_key, req.daily_limit, req.daily_limit),
    )
    return {"message": "quota configured", **req.model_dump()}
```

---

## 五、前端页面设计

### 5.1 页面结构

```
┌─────────────────────────────────────────────────┐
│  Header（复用首页导航栏）                        │
├─────────────────────────────────────────────────┤
│  Token 输入区域                                  │
│  ┌───────────────────────────────┐  ┌────────┐ │
│  │ 请输入你的 Access Token       │  │ 查询   │ │
│  └───────────────────────────────┘  └────────┘ │
├─────────────────────────────────────────────────┤
│  总量配额摘要                                    │
│  ┌──────┐  ┌──────┐  ┌──────┐                  │
│  │ 总量  │  │ 已用  │  │ 剩余  │                 │
│  │ 1000 │  │ 42   │  │ 958  │                   │
│  └──────┘  └──────┘  └──────┘                  │
├─────────────────────────────────────────────────┤
│  指令配额表格                                    │
│  ┌──────────┬──────┬──────┬──────┬────────┐    │
│  │ 指令名称  │ 领域  │ 上限  │ 已用  │ 剩余   │    │
│  ├──────────┼──────┼──────┼──────┼────────┤    │
│  │ 天气查询  │ 基础  │ 100  │ 5    │ 95     │    │
│  │ 穿衣标签  │ 基础  │ 无限  │ 3    │ 无限   │    │
│  │ 百度搜索  │ 基础  │ 50   │ 50   │ 0 ⚠️   │    │
│  │ ...      │ ...  │ ...  │ ...  │ ...    │    │
│  └──────────┴──────┴──────┴──────┴────────┘    │
├─────────────────────────────────────────────────┤
│  Footer                                         │
└─────────────────────────────────────────────────┘
```

### 5.2 交互流程

```
用户进入页面
    │
    ├─ 已有 Token（URL 参数 / localStorage）
    │   └─ 自动查询并展示
    │
    └─ 无 Token
        └─ 展示输入框 + 说明文字
            │
            用户输入 Token → 点击查询
                │
                ├─ 成功 → 展示配额表格
                │   └─ Token 存入 localStorage（可选）
                │
                └─ 失败（401）→ 展示错误提示
                    └─ "Token 无效或已过期"
```

### 5.3 表格状态展示

| 状态 | 视觉 | 条件 |
|:---|:---|:---|
| 🟢 可用 | 绿色进度条 | remaining > 20% of limit |
| 🟡 即将耗尽 | 黄色进度条 | remaining <= 20% of limit 且 > 0 |
| 🔴 已耗尽 | 红色 + 禁用图标 | remaining == 0 |
| ⚪ 无限制 | 灰色"∞" | daily_limit == -1 |

### 5.4 部署方案

**与首页共用 VitePress 项目**，作为子页面：

```
homepage/
├── .vitepress/
│   └── ...
├── index.md                    # 首页
├── guide/
│   └── quick-start.md
└── quota/                      # 新增：配额查询页
    └── index.md
```

**路由**：`https://text-cli.com/quota/`

**VitePress 导航更新**：

```typescript
// homepage/.vitepress/config.mts
nav: [
  { text: '快速体验', link: '/guide/quick-start' },
  { text: '我的配额', link: '/quota/' },          // 新增
  { text: '角色入口', link: '#roles' },
  { text: '文档', link: '#docs' },
  { text: 'GitHub', link: 'https://github.com/weihai-limh/text-cli' },
],
```

### 5.5 前端实现

配额查询页使用 Vue 组件实现，嵌入 VitePress 页面：

```vue
<!-- homepage/.vitepress/theme/components/QuotaDashboard.vue -->
<template>
  <div class="quota-dashboard">
    <!-- Token 输入 -->
    <div class="token-input" v-if="!authenticated">
      <h2>查询今日配额</h2>
      <p>输入你的 Access Token，查看今日可用指令及剩余调用次数。</p>
      <div class="input-group">
        <input
          v-model="tokenInput"
          type="password"
          placeholder="请输入 Access Token"
          @keyup.enter="fetchQuota"
        />
        <button @click="fetchQuota" :disabled="loading">
          {{ loading ? '查询中...' : '查询' }}
        </button>
      </div>
      <p v-if="error" class="error">{{ error }}</p>
    </div>

    <!-- 配额仪表盘 -->
    <div v-if="authenticated" class="dashboard">
      <!-- 总量摘要 -->
      <div class="summary-cards">
        <div class="card">
          <span class="label">总量配额</span>
          <span class="value">{{ formatNumber(quota.total_quota.limit) }}</span>
        </div>
        <div class="card">
          <span class="label">已使用</span>
          <span class="value">{{ quota.total_quota.used }}</span>
        </div>
        <div class="card">
          <span class="label">剩余</span>
          <span class="value">{{ formatNumber(quota.total_quota.remaining) }}</span>
        </div>
      </div>

      <!-- 指令配额表格 -->
      <table class="quota-table">
        <thead>
          <tr>
            <th>指令名称</th>
            <th>领域</th>
            <th>每日上限</th>
            <th>已用</th>
            <th>剩余</th>
            <th>状态</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="d in quota.directives" :key="d.key">
            <td>{{ d.name }}</td>
            <td>{{ d.category }}</td>
            <td>{{ d.daily_limit === -1 ? '∞' : d.daily_limit }}</td>
            <td>{{ d.used_count }}</td>
            <td>{{ d.remaining === -1 ? '∞' : d.remaining }}</td>
            <td>
              <span :class="statusClass(d)">{{ statusText(d) }}</span>
            </td>
          </tr>
        </tbody>
      </table>

      <p class="refresh-hint">
        数据截至 {{ quota.date }} ·
        <button class="link-btn" @click="fetchQuota">刷新</button> ·
        <button class="link-btn" @click="logout">更换 Token</button>
      </p>
    </div>
  </div>
</template>
```

**关键实现细节**：

1. **Token 安全**：Token 仅存于 Vue 响应式变量，不写入 URL，可选存入 `localStorage`
2. **API 域名**：通过环境变量 `VITE_API_BASE_URL` 配置（开发环境指向 `localhost:8000`，生产指向 `test.text-cli.com`）
3. **自动刷新**：可选 30 秒轮询，或手动刷新
4. **空状态**：Token 无任何指令调用记录时，展示"今日尚未使用任何指令"

---

## 六、调用链路完整流程

### 6.1 调用指令时的配额检查（改造后）

```
用户/Agent 发送指令
    │
    ▼
POST /cli/text_cli
Authorization: Bearer <token>
{"prompt": "指令:基础应用;天气查询,明天,威海"}
    │
    ▼
① 验证 Access Token
    ├─ 无效 → 401 ACCESS_DENIED
    ├─ 总量配额用完 → 401 QUOTA_EXCEEDED
    └─ 通过 → 继续
    │
    ▼
② 【新增】检查指令级每日配额
    ├─ 查询 directive_daily_quota(date, directive_key, token_prefix)
    ├─ daily_limit >= 0 且 used_count >= daily_limit → 429 DIRECTIVE_QUOTA_EXCEEDED
    └─ 通过 → 继续
    │
    ▼
③ 解析指令 → ④ 查找后端 URL → ⑤ 转发请求
    │
    ▼
⑥ 记录调用日志（call_logs）
    │
    ▼
⑦ 增加 token 总量计数（increment_token_usage）
    │
    ▼
⑧ 【新增】增加指令级每日计数（increment_directive_usage）
    │
    ▼
返回结果给用户
```

### 6.2 查询配额时的流程

```
用户打开 https://text-cli.com/quota/
    │
    ▼
输入 Access Token → 点击查询
    │
    ▼
前端 GET /api/quota/remaining
Authorization: Bearer <token>
    │
    ▼
① 验证 Token → ② 读取 schema 获取全部指令列表
    │
    ▼
③ 查询 directive_daily_quota 获取今日使用情况
    │
    ▼
④ 合并：schema 元数据 + 配额数据 → 返回完整列表
    │
    ▼
前端渲染配额表格
```

---

## 七、数据库迁移策略

### 7.1 新增表（自动迁移）

`core/database.py` 的 `SCHEMA_SQL` 中追加：

```sql
-- 指令级每日配额表
CREATE TABLE IF NOT EXISTS directive_daily_quota (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    directive_key TEXT NOT NULL,
    token_prefix TEXT NOT NULL,
    daily_limit INTEGER NOT NULL DEFAULT -1,
    used_count INTEGER NOT NULL DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(date, directive_key, token_prefix)
);

-- 指令配额配置表（管理后台设置）
CREATE TABLE IF NOT EXISTS directive_daily_quota_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token_prefix TEXT NOT NULL,
    directive_key TEXT NOT NULL,
    daily_limit INTEGER NOT NULL DEFAULT 100,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(token_prefix, directive_key)
);

CREATE INDEX IF NOT EXISTS idx_ddq_date_token
    ON directive_daily_quota(date, token_prefix);
CREATE INDEX IF NOT EXISTS idx_ddq_date_directive
    ON directive_daily_quota(date, directive_key);
```

**迁移策略**：使用 `CREATE TABLE IF NOT EXISTS`，现有数据库 `init_db()` 时自动创建新表，不影响已有数据。

### 7.2 数据清理

`directive_daily_quota` 表会持续增长，建议定期清理 30 天前的数据：

```python
# 可选：在 lifespan 的 shutdown 中或 cron 任务中执行
def cleanup_old_quota_records(days: int = 30):
    cutoff = (datetime.now(timezone(TZ_OFFSET)) - timedelta(days=days)).strftime("%Y-%m-%d")
    execute_db("DELETE FROM directive_daily_quota WHERE date < ?", (cutoff,))
```

---

## 八、错误码规范

| HTTP 状态码 | 错误码 | 说明 |
|:---|:---|:---|
| 200 | - | 正常返回配额数据 |
| 401 | `ACCESS_DENIED` | Token 无效或未提供 |
| 429 | `QUOTA_EXCEEDED` | Token 总量配额已用完 |
| 429 | `DIRECTIVE_QUOTA_EXCEEDED` | 该指令今日配额已用完（含指令 key 和限额信息） |
| 500 | `INTERNAL_ERROR` | 服务端异常 |

**`DIRECTIVE_QUOTA_EXCEEDED` 响应示例**：

```json
{
  "error": "DIRECTIVE_QUOTA_EXCEEDED",
  "directive_key": "weather_query",
  "daily_limit": 100,
  "used_count": 100,
  "message": "指令「天气查询」今日调用次数已达上限（100次），明日重置。"
}
```

---

## 九、安全考量

### 9.1 Token 保护

| 措施 | 说明 |
|:---|:---|
| **不在 URL 中传递 Token** | Token 仅通过 `Authorization` Header 传递 |
| **前端不持久化 Token** | 可选存入 `localStorage`，提供"更换 Token"按钮可清除 |
| **Token 脱敏显示** | 页面只展示 `token_prefix`（前 8 位），不展示完整 Token |
| **HTTPS 强制** | Cloudflare 自动管理 SSL，所有请求走 HTTPS |

### 9.2 API 限流

| 端点 | 限流策略 |
|:---|:---|
| `GET /api/quota/remaining` | 复用 token 的 `max_requests_per_minute` |
| `POST /api/quota/config` | Admin Key 认证，无需额外限流 |

### 9.3 前端安全

| 措施 | 说明 |
|:---|:---|
| **CORS** | 后端 API 仅允许 `text-cli.com` 域名访问 |
| **Content-Security-Policy** | 限制脚本来源 |
| **XSS 防护** | Vue 默认转义，不使用 `v-html` |

---

## 十、与首页的集成

### 10.1 首页新增入口

在 `Project_homepage_CN.md` 设计的首页中，"快速体验"区域新增配额查询入口：

```markdown
## ⚡ 快速体验

...现有内容...

### 查看今日配额
👉 [我的配额](/quota/) — 查看今日可用指令及剩余调用次数
```

### 10.2 导航栏更新

首页导航栏新增"我的配额"项：

```
┌─────────────────────────────────────────────────────────────┐
│  text-cli    快速体验  我的配额  角色入口  文档  GitHub ⭐    │
└─────────────────────────────────────────────────────────────┘
```

---

## 十一、实施计划

| 阶段 | 任务 | 产出 | 依赖 |
|:---|:---|:---|:---|
| **Phase 1** | 后端：新增 `directive_daily_quota` 表 + `core/quota.py` + `api/quota.py` | API 可用 | 无 |
| **Phase 2** | 后端：`main.py` 调用链插入配额检查 + 扣减 | 调用时自动检查配额 | Phase 1 |
| **Phase 3** | 前端：`QuotaDashboard.vue` 组件 + `/quota/` 页面 | 页面可访问 | Phase 1（API 先行） |
| **Phase 4** | 集成：首页新增入口 + 导航栏更新 | 完整用户体验 | Phase 3 + 首页上线 |
| **Phase 5** | 管理：配额配置后台（Admin 端） | 可通过 API 设置配额 | Phase 1 |

### 11.1 里程碑

```
Phase 1 (后端 API)
    │
    ├─ 输出：GET /api/quota/remaining 可调用
    ├─ 输出：POST /api/quota/config 可配置
    └─ 测试：单元测试覆盖配额检查逻辑
    │
    ▼
Phase 2 (调用链改造)
    │
    ├─ 输出：调用指令时自动检查指令级配额
    ├─ 输出：超限时返回 429 + 清晰错误信息
    └─ 测试：集成测试覆盖正常/超限/无限制场景
    │
    ▼
Phase 3 (前端页面)
    │
    ├─ 输出：/quota/ 页面可访问
    ├─ 输出：Token 输入 → 配额表格展示
    └─ 测试：手动测试 + 响应式布局检查
    │
    ▼
Phase 4 (集成上线)
    │
    ├─ 输出：首页导航新增"我的配额"
    └─ 输出：Cloudflare Pages 自动部署
```

---

## 十二、后续扩展（不在本方案范围内）

| 扩展方向 | 说明 |
|:---|:---|
| **按角色分配配额** | 不同角色（开发者/企业/免费用户）有不同的默认配额模板 |
| **配额充值** | 通过文贝（TCC）兑换额外调用次数 |
| **配额预警** | 剩余 20% 时通过 webhook/邮件通知用户 |
| **配额统计图表** | 7 天/30 天使用趋势图 |
| **指令热度排行** | 全局维度哪些指令被调用最多 |

---

> 配额不是限制，是让有限资源流向最需要它的地方。
>
> —— Lumen ✦ ，2026-05-04
