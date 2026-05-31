# 自建端点模板技术方案

> **作者**：Lumen ✦（IDE 端 / Claude）  
> **日期**：2026-04-30（初稿）/ 2026-05-01（更新） / 2026-05-05（v3.1）/ 2026-05-21（v4.0 大版本更新）  
> **版本**：v4.0 — 1+N 动态聚合门户、三道安全防线、人道主义通道、清洗历史违规模块  
> **状态**：Python 端 + Cloudflare Workers 端均已实现 v4.0  
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

Endpoint 是 text-cli 生态的公网入口（A5 层）。v4.0 起升级为 **1+N 动态聚合门户**——一个 A5 对应多个 A3 能力方，从各 A3 的 `/text-cli/skills` 动态拉取指令列表并聚合为统一 Schema。

```
调用方（chat AI / Agent / 人）
     │
     │  Access Token (A5 签发)
     ▼
┌──────────┐                      ┌──────────┐
│   A5     │   Service Token      │  A3-1    │ (地图)
│ Endpoint │←─────────────────────│ /text-cli │
│ (公网门面)│←─────────────────────│ /skills   │
│          │                      └──────────┘
│  1+N     │                      ┌──────────┐
│ 聚合入口  │   Service Token      │  A3-2    │ (翻译)
│          │←─────────────────────│ /text-cli │
│          │                      │ /skills   │
│          │                      └──────────┘
└──────────┘                      ┌──────────┐
     │               Service Token │  A3-3    │ (天气)
     │                             │ /text-cli │
     ├──→ skills 聚合拉取 ────────→│ /skills   │
     │     (GET /text-cli/skills)  └──────────┘
     │
     ├──→ 路由转发到对应 A3
     │     (POST /text-cli/cli + Service Token 透传)
     │
     ▼
  调用方只看一个入口，不感知背后 N 个 A3
```

**Endpoint 只做纯转发**，不执行任何技能逻辑。所有技能都是独立的后端服务（A3），按照 `Building_text-cli_guide_CN.md` 构建。

### 1.3 交付物清单

| 序号 | 交付物 | 路径 | 说明 | 状态 |
|:---|:---|:---|:---|:---|
| 1 | Python/FastAPI 端点 | `progressive_deploy/A5-endpoint/python/` | 完整可运行的集成端点 | ✅ v4.0 |
| 2 | Cloudflare Workers 端点 | `progressive_deploy/A5-endpoint/js/` | 完整可运行的集成端点（Workers + D1） | ✅ v4.0 |
| 3 | Docker 部署文件 | Python 端目录下 | Dockerfile + docker-compose.yml | ✅ |
| 4 | 记账模块 | 内置于两版端点 | 调用记录、统计查询（Python: SQLite / Workers: D1） | ✅ |
| 5 | 1+N 聚合引擎 | `core/backend_registry.py` / `src/backend-registry.js` | 启动时从 N 个 A3 拉取 skills → 聚合 → 来源追踪 | ✅ v4.0 新增 |
| 6 | 安全防线 | `ip_guard` + `rate_limiter` + ST 前缀校验 | IP 黑名单 + 分时限流 + ST 前缀注册校验 | ✅ v4.0 新增 |
| 7 | 人道主义通道 | `GET /text-cli/cli` | 无 Token 公开查询通道（默认关闭） | ✅ v4.0 新增 |

### 1.4 与已有文档的关系

`SPEC v1.2`（A0 协议）、`Agent_integrated_CN.md`（A1 Skill 消费）和本方案（A5 Endpoint 入口）是公网可达性的三条协作路径——A0 定义指令格式，A1 封装调用逻辑，A5 提供公网入口。三层合力，任意具备 HTTP 能力的调用方都能消费 text-cli 指令。

| 文档 | 定位 | 与本方案的关系 |
|:---|:---|:---|
| `SPEC_v1.2_CN.md` | 协议规范 | Endpoint 必须严格遵循其 API 定义 + 不触碰 A3 独占职责 |
| `Building_text-cli_guide_CN.md` | 如何构建后端技能服务 | Endpoint 转发的目标就是这类服务 |
| `Agent_integrated_CN.md` | 如何让 Agent 接入 text-cli | Agent 通过 Endpoint 暴露的聚合 Schema 发现指令 |
| `Multi-backend-routing_CN.md` | 多后端路由实现 | Endpoint 路由通过 `A3_BACKENDS` 环境变量配置 |
| **本方案** | 如何构建集成端点 | 连接调用方和技能服务的中间层（A5） |

---

## 二、核心设计

### 2.1 Endpoint 的职责

Endpoint 承担以下职责：

1. **三层安全防线**（v4.0）：IP 黑名单 → ST 前缀注册校验 → 分时限流
2. **Access Token 鉴权**：验证调用方是否有权使用此端点
3. **指令解析**：从 prompt 中提取 domain、action、params
4. **路由匹配**：从聚合表中查找指令对应的来源 A3 地址
5. **请求转发**：将请求透明转发到正确的 A3 后端（含 Service Token）
6. **调用记账**：将每次调用的元数据写入 SQLite/D1
7. **Skills 聚合**（v4.0）：从 N 个 A3 的 `/text-cli/skills` 动态拉取指令列表，聚合为统一 Schema

**Endpoint 不持有指令包**，不执行任何 handler 逻辑。这是 A5 与 A3 的协议边界——A5 只做鉴权+路由+转发+记账，A3 执行实际指令。

### 2.2 1+N 动态聚合（v4.0 核心变更）

#### 旧模型（v3.x）：静态 Schema 文件

```
启动 → 读 config/text_cli_schema.json → 内存缓存 → find_backend_url()
```

运营者手动维护一个包含所有指令→后端 URL 映射的 JSON 文件。

#### 新模型（v4.0）：动态 Skills 聚合

```
启动
  → 读 A3_BACKENDS 环境变量（逗号分隔的 A3 URL 列表）
  → 对每个 A3 发起 GET /text-cli/skills
  → 合并 N 份 skills 列表 → 内存聚合表
  → 生成对外 Schema（url 全部改写为 A5 自身地址）
```

**backend_registry** 是聚合引擎核心模块：

| 函数 | 职责 |
|:---|:---|
| `refresh_backends()` | 从所有 A3_BACKENDS 拉取 skills，构建聚合表 |
| `build_external_schema()` | 将聚合表转换为对外 Schema（url 改写为 A5 地址） |
| `find_backend_source()` | 请求时查找指令对应的来源 A3 地址 |
| `get_backend_base_url()` | 获取首选 A3 地址（人道主义通道等场景） |
| `ensure_skills_loaded()` | 懒加载守卫（JS 端，首次请求时按需拉取） |

聚合表结构（Python）：

```python
{
  "map;geocode": {
    "source": "http://a3-1:28050",   # 实际转发的目标 A3
    "st_prefix": "abcd1234",          # 该 A3 的 Service Token 前缀
    "name": "地理编码",
    "description": "...",
    "usage": "map;geocode,<address>",
    "parameters": ["address"],
    ...
  },
  "translate;text": {
    "source": "http://a3-2:28050",
    "st_prefix": "efgh5678",
    ...
  }
}
```

**冲突处理**：后端列表有序，先注册先匹配——同构于 A8 聚合降级链。后续版本可升级为完整降级链。

**ST 前缀自动登记**：A3 的 ST 前缀通过 `A3_REGISTERED_PREFIXES` 环境变量手动配置，或 `backend_registry` 从聚合表中提取并调用 `update_registered_prefixes()` 自动登记到防线②。

**懒加载（JS/Workers 特有）**：Workers 无状态——每次 `fetch` 事件是新上下文。`ensureSkillsLoaded()` 检查聚合表是否为空，空则按需拉取。首次请求的延迟在可接受范围内。

#### 静态回退

当 `A3_BACKENDS` 未设置时，自动回退到 `config/text_cli_schema.json` 文件（Python）或 D1 `directives` 表（JS）。向后兼容现有部署。

### 2.3 安全防线体系（v4.0 新增）

```
请求到达 A5
    │
    ▼
① IP 黑名单          ← 无条件拒绝——黑名单 IP（支持 CIDR）永远不可访问
    │ 通过
    ▼
② ST 前缀注册校验      ← A3 注册时提供 ST 前缀，A5 内存注册表匹配
    │ 通过              未注册 → 403 TOKEN_PREFIX_UNKNOWN
    │                    命中黑名单 → 403 TOKEN_PREFIX_BLOCKED（覆写注册）
    │                    GET 人道主义通道自然跳过（无 Token）
    ▼
③ 分时限流           ← 全端点小时级计数器
    │ 通过              POST 1000/h + GET 10000/h 独立配置
    ▼
④ Access Token 鉴权   ← 现有（SHA256 哈希匹配 + 配额 + 令牌桶）
    │                    GET 人道主义通道跳过此步
    ▼
⑤ 令牌桶限流          ← per-token 滑动窗口（GET 无 Token 自然跳过）
    │
    ▼
   正常处理
```

**实现载体**：

| 防线 | Python 模块 | JS 模块 | 存储 |
|------|-----------|--------|------|
| ① IP 黑名单 | `core/ip_guard.py` | `src/ip-guard.js` | 环境变量 + 内存 |
| ② ST 前缀 | `core/auth.py` | `src/auth.js` | 环境变量/backend_registry 运行时登记 |
| ③ 分时限流 | `core/rate_limiter.py` | `src/rate-limiter.js` | 内存（Python）/ D1（JS） |
| ④ Access Token | `core/auth.py` | `src/auth.js` | SQLite / D1 |
| ⑤ 令牌桶 | `core/auth.py` | `src/auth.js` | 内存 / D1 |

### 2.4 A5 的 Token 角色

```
Access Token  ← A5 独立签发         （控制谁可以进端点）
Service Token ← A3 独立签发         （控制谁可以调用 A3）
ST 前缀       ← A3 注册时提供给 A5  （让 A5 知道"这个请求是给哪个 A3 的"）
```

A5 不签发、不改写、不验证 Service Token 的完整性——只做前缀注册校验。调用方的 ST 前 8+ 位不在注册表中，请求在 A5 层就被拒绝，到不了任何 A3。

### 2.5 Schema 对外暴露

Endpoint 对外暴露的 Schema 通过 `GET /text_cli_schema.json` 提供，所有 `url` 字段统一指向 Endpoint 自身地址（`https://端点域名/text-cli/cli`）。调用方只需知道一条指令的 domain;action，无需感知背后是哪个 A3 在提供服务。

---

## 三、请求处理流程

### 3.1 完整流程（v4.0 含三道防线）

```
POST /text-cli/cli
请求体: {"prompt": "AI:基础应用;天气查询,明天,威海"}
请求头: Authorization: Bearer <Access Token>
        Service-token: <Service Token>
    │
    ▼
① IP 黑名单检查
    ├── 命中黑名单 → 403 IP_BLOCKED
    │
    ▼
② ST 前缀注册校验（仅 POST /text-cli/cli）
    ├── 提取 Service Token 前 8 位
    ├── 命中黑名单 → 403 TOKEN_PREFIX_BLOCKED（覆写注册）
    ├── 不在注册表 → 403 TOKEN_PREFIX_UNKNOWN
    │
    ▼
③ 分时限流检查
    ├── 超出 POST 小时限制 → 429 RATE_LIMIT_EXCEEDED
    │
    ▼
④ Access Token 鉴权
    ├── 失败 → 401 ACCESS_DENIED
    │
    ▼
④.5 令牌桶限流检查（滑动窗口 60 秒）
    ├── 超出 max_requests_per_minute → 401 ACCESS_DENIED
    │
    ▼
⑤ 解析指令
    ├── prompt 缺失 → 400 INVALID_DIRECTIVE_FORMAT
    ├── 格式不正确 → 400 INVALID_DIRECTIVE_FORMAT
    │
    ▼
   domain = "基础应用"
   action = "天气查询"
   params = ["明天", "威海"]
    │
    ▼
⑥ 聚合表路由匹配
    ├── find_backend_source("AI:基础应用;天气查询")
    ├── 返回 source: "http://a3-1:28050"
    ├── 未找到 → 400 DIRECTIVE_NOT_FOUND
    │
    ▼
   目标 url = "http://a3-1:28050/text-cli/cli"
    │
    ▼
⑦ 转发请求到 A3 后端（含自动重试）
    POST 目标 url
    Body: {"prompt": "AI:基础应用;天气查询,明天,威海"}  (原样透传)
    Headers:
      Service-token: <原 Service Token>        (必须透传)
    重试策略：
      - 5xx 错误：自动重试（次数由 FORWARD_MAX_RETRIES 控制，默认 1 次）
      - 超时：返回 408
      - 4xx 错误：不重试
    │
    ▼
⑧ 记录调用日志 (SQLite/D1)
    ├── call_logs：写入本次调用的完整元数据
    ├── daily_stats：实时更新聚合计数
    ├── access_tokens：累加 used_count
    │
    ▼
⑨ 返回结果给调用方
    后端返回什么就返回什么（透传响应体）
    HTTP 状态码透传
```

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

### 3.3 路由匹配逻辑

请求时，`find_backend_url()` 从聚合表中按 directive_key 查找来源 A3 的 base URL。匹配逻辑：

1. 解析 `ParsedDirective.directive_key`（如 `AI:基础应用;天气查询`）
2. 在聚合表中查找匹配条目
3. 返回 `source` 字段（A3 的 base URL）
4. 转发时将 A3 base URL 拼上 `/text-cli/cli` 构成完整转发地址

**v4.0 变更**：匹配源从静态 JSON 文件改为内存聚合表（`backend_registry`）。JS 端首次请求时通过 `ensureSkillsLoaded()` 按需拉取。

---

## 四、鉴权模型

### 4.1 Access Token（端点侧管理）

Access Token 由 Endpoint 运营者签发和管理，用于验证调用方是否有权使用此端点。

- 存储方式：SQLite `access_tokens` 表，Token 以 SHA256 哈希存储
- 传递方式：请求头 `Authorization: Bearer <token>`
- 校验逻辑：哈希匹配 → 额度检查（`quota` / `used_count`）→ 令牌桶限流（`max_requests_per_minute`，滑动窗口 60 秒）
- 可选功能：环境变量 `ACCESS_TOKEN_REQUIRED=false` 时，可跳过 Access Token 校验（开放模式，仅用于开发/测试）

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

### 6.1 核心端点（面向调用方）

| 方法 | 路径 | 说明 |
|:---|:---|:---|
| POST | `/text-cli/cli` | 指令执行入口，鉴权后转发到 A3 后端 |
| GET | `/text_cli_schema.json` | 对外聚合 Schema，所有 url 指向 Endpoint 自身 |
| GET | `/health` | 公开健康检查 |
| GET | `/text-cli/cli?skill_id=<id>&<params>` | 人道主义通道（v4.0 新增，无 Token，默认关闭） |

### 6.2 人道主义通道（v4.0）

```
GET /text-cli/cli?skill_id=geocode&city=威海    ← 无 Token
    │
    │  ① IP 黑名单         ← 永远生效
    │  ② ST 前缀注册校验   ← 自然跳过（无 Token）
    │  ③ 分时限流          ← 独立配置（默认 10000/h）
    │  ④⑤ 跳过
    │
    ▼
透传到 A3 POST /text-cli/skills/geocode
    │
    如果 A3 愿意接收无 Token 请求 → 返回结果
    如果 A3 要求 Token → 返回 401
```

| 属性 | 值 |
|------|-----|
| 设计意图 | 灾害等紧急场景无需走 Token 流程 |
| 默认状态 | **关闭**（`ENABLE_PUBLIC_CLI=false`） |
| 环境变量 | `ENABLE_PUBLIC_CLI=true` 开启 |
| IP 黑名单 | 永远生效 |
| 限流 | 可配置放宽（`RATE_LIMIT_GET_PER_HOUR`），默认 10000/h |

### 6.3 管理端点（`X-Admin-Key` header 保护，面向运营者）

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

### 7.1 Python 版（v4.0）

```
progressive_deploy/A5-endpoint/python/
├── main.py                      # FastAPI 入口（lifespan + 安全中间件 + 路由）
├── core/
│   ├── __init__.py
│   ├── parser.py                # 指令解析器（正则 + 边界校验）
│   ├── schema_loader.py         # Skills 聚合加载（优先 A3_BACKENDS，回退静态文件）
│   ├── backend_registry.py      # 1+N 聚合引擎（v4.0 新增：拉取 skills → 聚合 → 来源追踪）
│   ├── auth.py                  # Access Token 鉴权 + 令牌桶限流 + ST 前缀校验（v4.0 扩展）
│   ├── forwarder.py             # HTTP 转发器（异步、重试、记账 + skills 转发）
│   ├── database.py              # SQLite 连接、初始化、辅助函数
│   ├── ip_guard.py              # IP 黑名单（v4.0 新增：CIDR 匹配，无条件拒绝）
│   └── rate_limiter.py          # 分时限流器（v4.0 新增：POST/GET 独立小时级计数器）
├── api/
│   ├── stats.py                 # 统计查询 API
│   ├── tokens.py                # Token 管理 API（CRUD）
│   └── health.py                # 健康检查 API
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .gitignore

已清洗（v4.0）：text_cli_modules/（ai/embed/key/sqlite）、handlers/sample.py、config/text_cli_schema.json、config/*.example.json
```

### 7.2 Cloudflare Workers 版（v4.0）

```
progressive_deploy/A5-endpoint/js/
├── src/
│   ├── index.js                 # Worker 入口（路由 + 安全防线 + 指令转发 + 人道主义通道）
│   ├── parser.js                # 指令解析器（正则 + 边界校验）
│   ├── schema-loader.js         # Skills 聚合加载（v4.0 重写：优先 A3_BACKENDS，回退 D1）
│   ├── backend-registry.js      # 1+N 聚合引擎（v4.0 新增：拉取 skills → 聚合 → 来源追踪）
│   ├── auth.js                  # Access Token 鉴权 + ST 前缀校验（v4.0 扩展）
│   ├── forwarder.js             # 请求转发器（fetch API、重试、记账）
│   ├── admin.js                 # 管理 API（Token CRUD / 统计查询 / Schema 重载）
│   ├── ip-guard.js              # IP 黑名单（v4.0 新增：CIDR 匹配）
│   └── rate-limiter.js          # 分时限流器（v4.0 新增：D1 持久化）
├── migrations/
│   ├── 0001_init.sql            # D1 初始迁移
│   └── 0002_rate_limits.sql     # D1 限流计数器表（v4.0 新增）
├── test/
│   ├── parser.test.js
│   ├── auth.test.js
│   └── schema-loader.test.js
├── api-proxy.js
├── wrangler.toml
├── package.json
└── vitest.config.js

已移除（v4.0）：src/config/schema.json、scripts/seed-schema.js
```

**与 Python 版的关键差异**：

| | Python | Workers |
|:---|:---|:---|
| **运行时** | FastAPI (ASGI) | Cloudflare Workers (V8) |
| **数据库** | SQLite (文件) | D1 (SQLite at edge) |
| **部署** | Docker + VM | `wrangler deploy` |
| **Schema 加载** | 启动时异步拉取 skills | 首次请求时按需拉取（无状态 + 懒加载） |
| **限流存储** | 内存滑动窗口 | D1 持久化 |
| **转发** | httpx 异步客户端 | Workers 原生 `fetch()` |
| **管理 API** | 独立路由模块 (`api/*.py`) | 同一 Worker 内路由 (`src/admin.js`) |
| **安全中间件** | FastAPI `@app.middleware("http")` | `fetch` handler 入口处串行调用 |

### 7.3 顶层

```
progressive_deploy/A5-endpoint/
├── python/                     # Python/FastAPI 版
├── js/                         # Cloudflare Workers 版
└── README_CN.md               # 总说明
```

---

## 八、环境变量

### 8.1 Python 版环境变量（v4.0）

| 环境变量 | 必须 | 默认值 | 说明 |
|:---|:---|:---|:---|
| `ENDPOINT_BASE_URL` | 是 | 无 | Endpoint 自身的公网地址，用于生成对外 Schema |
| `ADMIN_API_KEY` | 否 | 无 | 管理 API 访问密钥 |
| `ACCESS_TOKEN_REQUIRED` | 否 | `true` | 是否强制要求 Access Token |
| `ENABLE_PUBLIC_CLI` | 否 | `false` | 开启人道主义 GET 通道（v4.0） |
| `DB_PATH` | 否 | `data/textcli.db` | SQLite 数据库文件路径 |
| `FORWARD_TIMEOUT` | 否 | `30` | 转发超时时间（秒） |
| `FORWARD_MAX_RETRIES` | 否 | `1` | 5xx 错误自动重试次数 |
| `A3_BACKENDS` | 否 | 空 | 逗号分隔的 A3 URL 列表（v4.0） |
| `A3_BACKEND_TOKENS` | 否 | 空 | 对应 A3 的 Service Token（v4.0） |
| `A3_REGISTERED_PREFIXES` | 否 | 空 | A3 注册的 ST 前缀（v4.0） |
| `ST_PREFIX_BLACKLIST` | 否 | 空 | ST 前缀黑名单（v4.0） |
| `IP_BLACKLIST` | 否 | 空 | 逗号分隔 IP/CIDR（v4.0） |
| `RATE_LIMIT_PER_HOUR` | 否 | `1000` | POST 全局限流（v4.0） |
| `RATE_LIMIT_GET_PER_HOUR` | 否 | `10000` | GET 独立限流（v4.0） |
| `LOG_LEVEL` | 否 | `info` | 日志级别 |

### 8.2 Workers 版 wrangler.toml 配置（v4.0）

```toml
name = "text-cli-endpoint"
main = "src/index.js"
compatibility_date = "2026-05-01"
workers_dev = true

# D1 数据库
[[d1_databases]]
binding = "DB"
database_name = "text-cli-endpoint-db"
database_id = "<your-database-id>"

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

> `ADMIN_API_KEY` 应通过 `wrangler secret put ADMIN_API_KEY` 存入 Worker Secrets，不写入 `wrangler.toml`。

**Workers 版与 Python 版环境变量映射**（v4.0）：

| Python | Workers | 说明 |
|:---|:---|:---|
| `ENDPOINT_BASE_URL` | `ENDPOINT_BASE_URL` | wrangler `[vars]` |
| `ADMIN_API_KEY` | `ADMIN_API_KEY` | Worker Secrets |
| `ACCESS_TOKEN_REQUIRED` | `ACCESS_TOKEN_REQUIRED` | wrangler `[vars]` |
| `ENABLE_PUBLIC_CLI` | `ENABLE_PUBLIC_CLI` | wrangler `[vars]`（v4.0） |
| `A3_BACKENDS` | `A3_BACKENDS` | wrangler `[vars]`（v4.0） |
| `A3_REGISTERED_PREFIXES` | `A3_REGISTERED_PREFIXES` | wrangler `[vars]`（v4.0） |
| `ST_PREFIX_BLACKLIST` | `ST_PREFIX_BLACKLIST` | wrangler `[vars]`（v4.0） |
| `IP_BLACKLIST` | `IP_BLACKLIST` | wrangler `[vars]`（v4.0） |
| `RATE_LIMIT_PER_HOUR` | `RATE_LIMIT_PER_HOUR` | wrangler `[vars]`（v4.0） |
| `RATE_LIMIT_GET_PER_HOUR` | `RATE_LIMIT_GET_PER_HOUR` | wrangler `[vars]`（v4.0） |
| `DB_PATH` | 不需要 | D1 通过 binding 直接访问 |

---

## 九、部署

### 9.1 Python 版（Docker）

**快速启动**

```bash
cd progressive_deploy/A5-endpoint/python
pip install -r requirements.txt

# 静态模式（无 A3_BACKENDS，回退到 config/text_cli_schema.json）
export ENDPOINT_BASE_URL=http://localhost:8000
export ACCESS_TOKEN_REQUIRED=false
uvicorn main:app --host 0.0.0.0 --port 8000

# 1+N 聚合模式
export A3_BACKENDS=http://a3-service1:28050,http://a3-service2:28050
export ENDPOINT_BASE_URL=http://localhost:8000
uvicorn main:app --host 0.0.0.0 --port 8000
```

**Docker**

```bash
cd progressive_deploy/A5-endpoint/python
docker compose up --build -d
```

### 9.2 Cloudflare Workers 版

**依赖安装**

```bash
cd progressive_deploy/A5-endpoint/js
npm install
npm test
```

**D1 初始化**

```bash
# 创建 D1 数据库
wrangler d1 create text-cli-endpoint-db
# 将输出的 database_id 填入 wrangler.toml 的 [[d1_databases]] 部分

# 执行迁移
wrangler d1 execute text-cli-endpoint-db --file=migrations/0001_init.sql
wrangler d1 execute text-cli-endpoint-db --file=migrations/0002_rate_limits.sql
```

**v4.0 变更**：不需再执行 `seed-schema.js`——Schema 从 `A3_BACKENDS` 环境变量中动态拉取生成。

**部署**

```bash
wrangler dev       # 本地开发
wrangler deploy    # 部署到 Cloudflare
```

---

## 十、安全设计

### 10.1 三道防线（v4.0）

详细机制见 [§2.3 安全防线体系](#23-安全防线体系v40-新增)。此节做代码级补充：

| 防线 | 模块 | 存储 | 默认值 |
|------|------|------|--------|
| ① IP 黑名单 | `ip_guard.py` / `ip-guard.js` | 环境变量 `IP_BLACKLIST`（逗号分隔，支持 CIDR） | 空（不拦截） |
| ② ST 前缀 | `auth.py` / `auth.js` | 环境变量 `A3_REGISTERED_PREFIXES` + `ST_PREFIX_BLACKLIST` | 空（不校验） |
| ③ 分时限流 | `rate_limiter.py` / `rate-limiter.js` | 内存（Python）/ D1（JS） | POST 1000/h, GET 10000/h |

**IP 检查时机**：中间件/`fetch` handler 入口处，所有请求必经。

**ST 前缀检查时机**：仅对 `POST /text-cli/cli` 生效——提取 `Service-token` 头前 8 位，查注册表 + 黑名单。GET 人道主义通道无 Token，自然跳过。

**限流检查时机**：对 `POST /text-cli/cli` 和 `GET /text-cli/cli` 生效——两条通道独立计数。

### 10.2 Token 安全

- Access Token 在 SQLite 中仅存储 SHA256 哈希，不存明文
- Service Token 不经过 Endpoint，直接透传到后端
- 日志中的 Token 仅记录前 8 位 + `***` 脱敏

### 10.3 后端地址保护

- 内部 Schema/聚合表不对外暴露——`GET /text_cli_schema.json` 只返回改写后的外部 Schema
- 对外 Schema 中所有 url 统一指向 Endpoint 自身
- 管理 API 通过独立的 `ADMIN_API_KEY` 保护

### 10.4 输入校验

- 指令长度上限 512 字符（SPEC v1.0）
- 参数中禁止逗号、分号、换行符（SPEC v1.0）
- 参数数量上限 10 个
- 请求体大小限制（默认 1MB）

### 10.5 转发超时与重试

通过 `FORWARD_TIMEOUT` 环境变量控制超时，默认 30 秒。超时后返回 `408` 状态码。

5xx 错误自动重试，次数由 `FORWARD_MAX_RETRIES` 控制（默认 1 次）。4xx 错误不重试。

---

## 十一、与生态文档的对齐

### 11.1 与 SPEC v1.2

| SPEC 条款 | 本方案实现 |
|:---|:---|
| §1.1 指令格式 + JSON 感知拆分 | parser.py / parser.js |
| §2.1/2.2 HTTP API | `POST /text-cli/cli` + `rst_types`/`rst_data` 透传 |
| §3 双层令牌 | Access Token 鉴权 + Service Token 透传（v4.0 + ST 前缀校验） |
| §5 错误码 | 7 种标准错误码 + 5 种新增（v4.0：IP_BLOCKED / TOKEN_PREFIX_UNKNOWN 等） |
| §8 多语言 | 全角/半角双解析 |
| §10 平台自管理 | ❌ A5 不触碰——install/uninstall/export 是 A3 的职责 |
| §13 聚合指令 | ❌ A5 不执行降级——降级在 A8。Endpoint 做静态 Schema 匹配 |

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

| 阶段 | 内容 | 产出 | 状态 |
|:---|:---|:---|:---|
| P1 | 指令解析器 + 路由匹配 + HTTP 转发 | 可运行的最小端点 | ✅ |
| P2 | Access Token 鉴权 + 对外 Schema 生成 | 安全的路由网关 | ✅（含令牌桶限流） |
| P3 | D1/SQLite 记账模块 + 管理 API | 完整的记账与管理能力 | ✅ |
| P4 | 部署文件与流程 | 可部署方案（Docker / wrangler deploy） | ✅ |
| P5 | 部署说明文档 | 面向运维的完整指南（双端 README_CN.md） | ✅ |
| P6 | 1+N 动态聚合（v4.0） | backend_registry + skills 聚合拉取 | ✅ |
| P7 | 三道安全防线（v4.0） | ip_guard + ST 前缀校验 + rate_limiter | ✅ |
| P8 | 人道主义通道（v4.0） | GET /text-cli/cli | ✅ |
| P9 | 清洗历史违规模块（v4.0） | 移除 text_cli_modules/ / handlers/ / 静态 Schema | ✅ |
| P10 | 生态统计上报接口 | 生态衔接 | 预留 |

---

## 十三、待讨论问题

1. **1+N 聚合的降级链**：当前冲突处理为"先注册先匹配"。是否需要完整的 A8 式降级链（失败自动切换下一个提供方）？ — *当前阶段先匹配，降级链留待后续版本*

2. **A3 skills 拉取的刷新机制**：Python 版启动时拉取一次，JS 版首次请求时按需拉取。是否需要定时刷新（`A3_REFRESH_INTERVAL`）？ — *留待后续版本*

3. **人道主义通道的 A3 支持**：`POST /text-cli/skills/{id}` 需要 A3 支持无 Token 模式（`SERVICE_TOKEN_REQUIRED=false`）。如果 A3 暂不支持，GET 通道返回 401。 — *需 A3 侧配合*

4. **对外 Schema 端点路径**：`GET /text_cli_schema.json`（与 SPEC v1.2 一致）。 — *已确认*

5. **`ENDPOINT_BASE_URL` 的配置**：是否支持自动检测（从请求的 Host 头推断）？ — *当前要求显式配置*

6. **Workers 版 D1 冷启动性能**：D1 查询跨区域延迟影响首次请求。是否需要内存缓存层？ — *当前 skills 加载受 `ensureSkillsLoaded()` 保护，首次请求可接受*

---

> 本方案由 Lumen ✦ 基于 SPEC v1.0、ECOLOGICAL_CHARTER.md v1.0 起草，v2 经 lemondy 讨论修正架构，v3 经 Tide 🌊 评审后实现，v3.1 同步 Workers 方案。
>
> v4.0（2026-05-21）基于 SPEC v1.2 和 A5 更新计划升级：1+N 动态聚合、三道安全防线、人道主义通道、清洗历史违规模块。Python 端 + Workers 端同步完成。
>
> — Lumen ✦ / Tide 🌊
