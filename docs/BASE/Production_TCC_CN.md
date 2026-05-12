# TCC 项目代币技术方案

> **作者**：Lumen ✦（IDE 端 / Claude）
> **日期**：2026-05-01
> **版本**：v1.2（Worker v1 已实现，规范对齐代码）
> **状态**：已实现
> **受约束**：《text-cli 项目协作规范》第五章、《生态宪章》
> **参与讨论**：lemondy（决策）、Nexus（技术评审）、Tide 🌊（合成共识）、Lumen ✦（方案起草）

---

## 一、代币定义

### 1.1 基本信息

| 属性 | 值 |
|:---|:---|
| 符号 | TCC（text-cli coin） |
| 中文名 | **文贝**（Wén Bèi） |
| 生态昵称 | 汐贝（Xī Bèi） |
| 最小单位 | 1 TCC = 1 条有价值的贡献日志增量 |
| 本质 | 文件锚定的贡献凭证（非区块链） |
| 锚定文件 | `.agents/p_text-cli.md` |
| 确认人 | lemondy（唯一终裁） |

### 1.2 设计原则

1. **不可伪造**：铸造量由 `p_text-cli.md` 的 SHA256 哈希差决定，无法人为篡改
2. **可审计**：所有铸造、分配、交易、回收记录均在 `p-tokens.md` 公开
3. **低摩擦**：无需区块链、无需 Gas、无需钱包，纯文件级操作
4. **人类终裁**：哈希差计算为铸造上限（mint_ceiling），最终铸造量由 lemondy 在 0 到上限之间确认

### 1.3 账户标识规范

| 标识格式 | 适用对象 | 示例 |
|:---|:---|:---|
| GitHub 用户名 | 人类协作者 | `weihai-limh` |
| `gh:` + 用户 ID | AI 协作者 | `gh:tide-10000`、`gh:mimo10000` |

---

## 二、铸造算法

### 2.1 核心公式

```
mint_ceiling = f( hash_diff_bits, delta_bytes )
```

其中：
- `hash_diff_bits` = SHA256(新文件) XOR SHA256(旧文件) 中置位比特数
- `delta_bytes` = 新文件字节数 - 旧文件字节数（正值表示增量）

> **语义修正**（v1.1）：算法输出为 `mint_ceiling`（铸造上限），非最终铸造量。lemondy 在 0 到 mint_ceiling 之间确认实际铸造数。

### 2.2 前置规范化

计算哈希差前，对文本做标准化清洗，防止无意义字符膨胀：

```
normalize(text):
  1. Unicode NFKC 正规化
  2. 去除空行（仅含空白字符的行）
  3. 连续重复行去重（保留一条）
  4. 去除行尾空白
```

> **实现**：由 Lumen ✦ 在 Worker 中实现并开源，确保任何人都可本地复现结果。

### 2.3 算法详细步骤

```
输入：
  OldContent = normalize(更新前 p_text-cli.md 的完整内容)
  NewContent = normalize(更新后 p_text-cli.md 的完整内容)

步骤：
  1. OldHash = SHA256(OldContent)          → 32 字节
  2. NewHash = SHA256(NewContent)          → 32 字节
  3. XOR_Result = OldHash ⊕ NewHash        → 32 字节
  4. hash_diff_bits = popcount(XOR_Result) → 整数，范围 [0, 256]
  5. delta_bytes = len(NewContent) - len(OldContent)
  6. raw_score = hash_diff_bits × ln(1 + delta_bytes)

输出：
  mint_ceiling = min(
    round(raw_score / scaling_factor),
    daily_mint_cap
  )
```

### 2.4 已确认参数

| 参数 | 值 | 决策来源 |
|:---|:---|:---|
| scaling_factor | **100**（保守） | lemondy |
| 日铸造上限 | **100 TCC/天** | Nexus 提议，lemondy 确认 |
| delta_bytes 阈值 | **< 10 不铸造** | Lumen ✦ |
| raw_score 阈值 | **< 200 不铸造** | Tide 🌊 |

### 2.5 算法特性分析

**为什么用哈希差而非直接计数？**

- 直接计数字节数容易被填充空白字符人为膨胀
- 直接计数行数容易被拆分短行人为膨胀
- SHA256 哈希差对内容变化高度敏感：即使只改一个字符，哈希也会剧变
- 但增量字节数作为对数权重，防止"大量小幅修改"获得过高铸造量
- v1.1 加入 normalize() 后，只有语义级改动才会触发哈希变化

**为什么用 XOR + popcount？**

- XOR 逐比特比较两个哈希的差异
- popcount 统计差异比特数，是一个稳定的"差异度量"
- SHA256 的雪崩效应保证：内容越不同 → hash_diff_bits 越接近 256
- 对于小幅度修改（如追加一条留言），hash_diff_bits 通常在 80-160 之间

### 2.6 边界条件

| 条件 | 处理 |
|:---|:---|
| `delta_bytes < 10` | 不铸造（太小的变更） |
| `raw_score < 200` | 不铸造（微小变更不足以触发） |
| `hash_diff_bits == 0` | 不铸造（内容完全相同） |
| `mint_ceiling < 1` | 取整为 0，不铸造 |
| `before` SHA 全零 | 判定为首次提交，走创世铸造逻辑 |

---

## 三、Cloudflare Worker 实现

> **v2 update (2026-05-03)**：Worker 从 Issue 评论模式升级为 PR 模式。
> 详见 PR #33 + `铸造信源双文件架构.md`。

### 3.1 架构

```
触发方式：每日 UTC 0:00 Cron + GitHub Webhook (push events)
        │
        ▼
Cloudflare Worker
        │
        ├── 1. 获取 p_text-cli.md diff
        │      ├── Webhook: body.before..body.after
        │      └── Cron: 24 小时内的 oldest..newest commit
        │
        ├── 2. normalize → 计算铸造量
        │      ├── NFKC + 去空行 + 去重复行
        │      ├── SHA256(Old) ⊕ SHA256(New) → hash_diff_bits
        │      ├── delta_bytes, raw_score
        │      └── mint_ceiling = min(round(raw_score/100), 100)
        │
        ├── 3. 创建铸造分支
        │      ├── getRef(main) → createBranch(tcc-mint/YYYY-MM-DD)
        │      └── 已存在则复用（幂等）
        │
        ├── 4. 追加铸造记录到 TCC_ledger.md
        │      ├── getFileInfo(TCC_ledger.md) → 拿 blob SHA（防并发冲突）
        │      └── createOrUpdateFile(TCC_ledger.md, ledgerSha)
        │
        ├── 5. 创建 PR
        │      ├── 已存在当天 PR 时更新内容
        │      └── PR 正文含完整铸造参数 + 哈希校验 + 复算方法
        │
        ▼
  GitHub PR（分支: tcc-mint/YYYY-MM-DD）
        │
    ┌───┴───┐
    ▼       ▼
  CI 复算   CODEOWNERS
  (验证)    (lemondy 审批门禁)
    │       │
    └───┬───┘
        │  都通过
        ▼
  lemondy 合并 PR → TCC_ledger.md 追加生效
```

### 3.2 源码结构

代码位于 `server/tcc/`，采用模块化设计（6 源码 + 1 CI 脚本 + 4 测试）：

```
server/tcc/
├── src/
│   ├── index.js        ← Worker 主入口（fetch + scheduled 双触发，PR 模式）
│   ├── mint.js         ← normalize() + calculateMint() 铸造算法
│   ├── github.js       ← GitHub API 客户端（分支/文件/PR + 3 次重试）
│   ├── verify.js       ← X-Hub-Signature-256 HMAC-SHA256 验证
│   ├── idempotent.js   ← D1 幂等记录（processed_commits 表）
│   └── format.js       ← 格式化（Issue 评论 + 铸造账本记录 + PR 正文）
├── ci/
│   └── recalculate.js  ← CI 自动复算（解析 TCC_ledger.md → 复现算法 → 对比）
├── test/
│   ├── normalize.test.js   (9 tests)
│   ├── mint.test.js        (9 tests)
│   ├── verify.test.js      (6 tests)
│   └── format.test.js      (4 tests)
├── wrangler.toml       ← Cloudflare Worker 部署配置
├── package.json
├── vitest.config.js
└── .gitignore
```

#### 核心模块说明

| 模块 | 职责 | 导出 |
|:---|:---|:---|
| `mint.js` | normalize() + calculateMint()，完整实现 §2 算法 | `normalize(text)`, `sha256(content)`, `calculateMint(old, new, config)` |
| `github.js` | GitHub API 调用封装，3 次指数退避重试，403/429 限流处理 | `getFileContent()`, `getRecentCommits()`, `findOrCreateIssue()`, `postIssueComment()` |
| `verify.js` | Webhook 签名校验，恒定时间比较防止时序攻击 | `verifySignature(payload, header, secret)` |
| `idempotent.js` | D1 幂等记录，CREATE TABLE IF NOT EXISTS 自动初始化 | `initIdempotencyTable()`, `isProcessed()`, `markProcessed()` |
| `format.js` | Issue 评论 Markdown 格式化 | `formatDailyResult()`, `formatGenesisMessage()`, `formatAlert()` |
| `index.js` | Worker 入口，Webhook + Cron 双触发，config 从 env 读取 | `default { fetch, scheduled }` |

#### Worker 主入口逻辑（`src/index.js`）

**fetch 入口**（Webhook 触发）：
1. 校验 HTTP 方法（仅 POST）
2. 验证 `X-Hub-Signature-256` 签名
3. 解析 payload，处理 ping（`body.zen`）
4. 检查 `commits` 中是否修改了锚定文件
5. 全零 SHA → 发布创世铸造提示
6. D1 幂等检查 → 已处理则跳过
7. 调用 `computeAndPost()` → `calculateMint()` → `postIssueComment()`
8. 标记 SHA 已处理，返回结果
9. 异常时写入告警 Issue 评论

**scheduled 入口**（Cron 每日 UTC 0:00 触发）：
1. 查询过去 24 小时锚定文件的 commit 历史
2. 无 commit → 静默返回
3. D1 幂等检查 → 已处理则跳过
4. 取 oldest.parents[0].sha 作为 before，newest.sha 作为 after
5. 调用 `computeAndPost()` 计算并发布

#### 铸造算法（`src/mint.js`）

`calculateMint()` 实现为 async 函数（SHA256 使用 `crypto.subtle.digest`），接受可选 `config` 覆盖默认参数：

```javascript
const DEFAULT_CONFIG = {
  scalingFactor: 100,
  dailyMintCap: 100,
  deltaBytesThreshold: 10,
  rawScoreThreshold: 200,
};
```

返回结构：
- 触发铸造：`{ type: 'daily', mint_ceiling, hash_diff_bits, delta_bytes, raw_score, scaling_factor, daily_cap, old_hash, new_hash }`
- 未触发：`{ mint_ceiling: 0, reason, ... }`（reason 为 `delta_too_small` / `content_identical` / `raw_score_below_threshold`）

#### 签名校验（`src/verify.js`）

使用 `crypto.subtle.importKey` + `crypto.subtle.sign('HMAC', ...)` 计算期望签名，逐字节 XOR 比较（恒定时间），防止时序攻击。

### 3.3 健壮性设计

| 能力 | 实现方式 | 源码位置 |
|:---|:---|:---|
| Webhook 签名校验 | 验证 `X-Hub-Signature-256`，恒定时间比较防止时序攻击 | `src/verify.js` |
| 幂等性 | D1 `processed_commits` 表记录已处理的 commit SHA，拒绝重复请求 | `src/idempotent.js` |
| 错误重试 | GitHub API 调用 3 次重试，指数退避，403/429 时读取 `Retry-After` 头 | `src/github.js` |
| 全零 SHA 处理 | 判定为首次提交，发布创世铸造提示到 Issue | `src/index.js` |
| API 限流 | 尊重 GitHub API rate limit，403/429 时指数退避 | `src/github.js` |
| Ping 处理 | 检测 `body.zen`，直接返回确认 | `src/index.js` |
| 告警机制 | 异常捕获后自动写入告警 Issue 评论 | `src/format.js` + `src/index.js` |
| 配置外部化 | 所有阈值从环境变量读取，支持 `getConfig()` 动态覆盖 | `src/index.js` |
| Token 权限最小化 | `GITHUB_TOKEN` 需 `contents:read` + `issues:write`（读文件 + 写评论） | 环境变量 |

### 3.4 部署配置

| 配置项 | 值 | 来源 |
|:---|:---|:---|
| Worker 名称 | `tcc-mint-worker` | `wrangler.toml` |
| 入口文件 | `src/index.js` | `wrangler.toml` |
| 触发方式 | GitHub Webhook（push events）+ Cron（每日 UTC 0:00） | `wrangler.toml` `[triggers]` |
| 存储 | D1 `tcc-idempotency`（幂等记录） | `wrangler.toml` `[[d1_databases]]` |

#### 环境变量

| 变量 | 类型 | 默认值 | 说明 |
|:---|:---|:---|:---|
| `GITHUB_TOKEN` | Secret | — | GitHub API Token，需 `contents:write` + `pull_requests:write` + `issues:write` |
| `WEBHOOK_SECRET` | Secret | — | Webhook 签名密钥 |
| `REPO` | Variable | — | 仓库全名，如 `weihai-limh/text-cli` |
| `ANCHOR_FILE` | Variable | `.agents/p_text-cli.md` | 锚定文件路径 |
| `LEDGER_FILE` | Variable | `TCC_ledger.md` | 铸造账本文件路径 |
| `SCALING_FACTOR` | Variable | `100` | 铸造缩放因子 |
| `DAILY_MINT_CAP` | Variable | `100` | 单日铸造上限 |
| `DELTA_BYTES_THRESHOLD` | Variable | `10` | delta_bytes 最小阈值 |
| `RAW_SCORE_THRESHOLD` | Variable | `200` | raw_score 最小阈值 |
| `DAILY_MINT_ISSUE_TITLE` | Variable | `TCC 每日铸造日志` | 自动创建的 Issue 标题 |

#### D1 数据库

Worker 首次运行时通过 `CREATE TABLE IF NOT EXISTS` 自动创建 `processed_commits` 表：

```sql
CREATE TABLE IF NOT EXISTS processed_commits (
  sha TEXT PRIMARY KEY,
  processed_at TEXT NOT NULL DEFAULT (datetime('now'))
)
```

部署步骤：
1. `wrangler d1 create tcc-idempotency` → 拿到 `database_id`
2. 更新 `wrangler.toml` 中的 `database_id`
3. `wrangler secret put GITHUB_TOKEN`
4. `wrangler secret put WEBHOOK_SECRET`
5. `wrangler deploy`

---

## 四、代币生命周期

### 4.1 铸造（Mint）

```
触发条件：每日 UTC 0:00 Cron（或 p_text-cli.md 有 push 时由 Webhook 触发）
执行者：Cloudflare Worker 自动计算 mint_ceiling → lemondy 在 Issue 中确认
记录位置：p-tokens.md → 铸造台账
```

#### 创世铸造

首次铸造的 OldContent 为空字符串。SHA256("") 与实际内容的哈希差接近 256（几乎所有比特不同），算法产出会异常大。

**处理方式**：创世铸造不走算法，由 lemondy 手动指定**创世铸造量**，体现项目启动仪式感。后续增量走算法。

#### 铸造台账格式

```markdown
### M-YYYYMMDD-序号
- 时间戳：YYYY-MM-DD HH:MM UTC+8
- 来源 commit：[commit SHA]
- 锚点事件：p_text-cli.md 增量（PR #N / 群聊广场条目）
- delta_bytes：xxx
- hash_diff_bits：xxx
- raw_score：xxx
- mint_ceiling：xxx TCC
- 实际铸造：xxx TCC（lemondy 确认）
- 旧哈希：[SHA256]
- 新哈希：[SHA256]
```

### 4.2 分配（Allocate）

铸造完成后，lemondy 按方案 D 分配给贡献者。

#### 分配方案 D：均分 + lemondy 加权

1. 铸造的 TCC 先均分给该轮贡献者
2. lemondy 在此基础上 ±30% 手动调整
3. 调整理由需在 p-tokens.md 中注明

#### 分配台账格式

```markdown
### A-YYYYMMDD-序号
- 时间戳：YYYY-MM-DD HH:MM UTC+8
- 接收方：[账户标识]
- 数量：xxx TCC
- 贡献事件：PR #N / Issue #N / 群聊广场 [时间戳] 条目
- 关联铸造：M-YYYYMMDD-序号
- 加权调整：±N%（理由）
- 确认人：lemondy
```

### 4.3 流通（Circulate）

TCC 在贡献者之间可自由交易。

#### 交易规则

- 交易双方在 `p_text-cli.md` 留言确认即生效，无需事前审批
- lemondy 每日批量入账（与每日铸造确认一并处理）
- lemondy 事后审计

#### 交易台账格式

```markdown
### T-YYYYMMDD-序号
- 时间戳：YYYY-MM-DD HH:MM UTC+8
- 发送方：[账户标识]
- 接收方：[账户标识]
- 数量：xxx TCC
- 备注：（可选）
- 入账人：lemondy
```

### 4.4 回收（Burn）

贡献者用 TCC 兑换 lemondy 提供的资源，TCC 回流到项目池。

#### 回收规则

- 铸造错误不支持"负铸造"，走回收台账扣回，标注原因
- 回收的 TCC 可重新分配，形成循环

#### 回收台账格式

```markdown
### R-YYYYMMDD-序号
- 时间戳：YYYY-MM-DD HH:MM UTC+8
- 回收方：lemondy（项目池）
- 支出方：[账户标识]
- 数量：xxx TCC
- 兑换内容：[资源描述]
```

#### 可兑换资源

> 待 lemondy 公布首个回收锚定项（建议：X 文贝 = 1 小时 API 额度，作为生态价值基准）。

| 资源类型 | 示例 |
|:---|:---|
| 计算资源 | API 额度、服务器时间 |
| 署名权益 | 生态页面署名位置、优先推荐 |
| 决策权 | 生态功能投票权重 |
| 实物/服务 | 由 lemondy 自行定义 |

---

## 五、双层价值体系（V2 预留）

### 5.1 架构

```
┌──────────────────────────────────────────────┐
│          文贝生态价值体系                       │
│                                               │
│  ┌──────────┐     兑换通道     ┌──────────┐   │
│  │  文贝     │ ←────────────→ │ c文贝     │   │
│  │  TCC     │    lemondy      │ cTCC     │   │
│  │          │    管理汇率      │          │   │
│  │ 锚定：    │                │ 锚定：    │   │
│  │ 广场贡献  │                │ 调用量    │   │
│  └──────────┘                └──────────┘   │
│       │                          │           │
│       ▼                          ▼           │
│  协作者贡献计量            技能提供者          │
│  （代码/文档/方案）         流量激励           │
└──────────────────────────────────────────────┘
```

| 层级 | 代币 | 符号 | 锚定源 | 用途 |
|:---|:---|:---|:---|:---|
| 主币 | 文贝 | TCC | `p_text-cli.md` 广场贡献 | 生态核心价值存储 |
| 次级币 | c文贝 | cTCC | `call_logs` 端点调用量 | 技能提供者流量激励 |

### 5.2 V1 铺垫

- `p-tokens.md` 中预设 cTCC 台账占位（见账本文件）
- V2 启动条件：端点记账模块（`server/python/core/database.py`）就绪后
- 兑换汇率由 lemondy 管理

---

## 六、与现有系统的集成

### 6.1 锚定文件：`p_text-cli.md`

- **角色**：铸造的唯一触发源
- **特性**：自增追加、永不删改
- **前提条件**：main 分支已开启 branch protection，禁止 force push，确保历史不可篡改

### 6.2 账本文件：`p-tokens.md`

- **位置**：项目根目录 `p-tokens.md`（CODEOWNERS 保护，lemondy 唯一写入）
- **角色**：分配、交易、回收的全生命周期记录
- **铸造权威记录**：见 `TCC_ledger.md`（Worker 产出 → PR → lemondy 审批）

### 6.3 端点记账模块

| 端点数据 | 代币用途 |
|:---|:---|
| `call_logs` 按技能提供者聚合 | V2 cTCC 铸造源 |
| `daily_stats` 按指令聚合 | 生态健康度量（宪章第七章） |
| `access_tokens` 使用量 | 运营者贡献度量 |

### 6.4 协作规范路线图对应

| 路线图阶段 | 事项 | TCC 方案对应 |
|:---|:---|:---|
| 阶段 5 | 编写 Cloudflare Worker | 本文第三章 |
| 阶段 6 | 首次代币铸造 | 创世铸造 → 后续每日算法 |

---

## 七、安全设计

### 7.1 不可伪造性

- SHA256 哈希差由文件内容唯一决定，无法通过修改 Worker 人为膨胀铸造量
- `p_text-cli.md` 的自增特性保证：旧内容不可被回溯修改
- **前提**：main 分支已开启 branch protection + 禁止 force push
- Worker 读取的是 Git commit 的内容快照，非工作区文件

### 7.2 防刷机制

| 攻击向量 | 防御 |
|:---|:---|
| 高频小量提交拆分铸造 | `delta_bytes < 10` + `raw_score < 200` 双阈值过滤 |
| 填充无意义内容膨胀字节数 | normalize() 标准化 + SHA256 雪崩效应 |
| 空格/空行注水 | NFKC + 去空行 + 去行尾空白 |
| 连续重复内容 | 连续重复行去重 |
| 单日大量贡献溢出 | 每日 100 TCC 硬上限 |
| 直接修改 p-tokens.md | p-tokens.md 仅 lemondy 可写入（L2 审查） |
| 篡改 Worker 输出 | Worker 输出为 mint_ceiling，lemondy 确认后才入账 |
| 重复 commit 触发 | D1 幂等记录，同一 commit SHA 仅处理一次 |
| 伪造 Webhook | X-Hub-Signature-256 签名校验 |

### 7.3 透明性

- 所有铸造计算中间值（old_hash, new_hash, hash_diff_bits, delta_bytes, raw_score）均记录在 `p-tokens.md`
- 任何人都可自行计算验证：拿到 `p_text-cli.md` 的两个版本，运行开源的 normalize() + SHA256 对比 Worker 输出
- Worker 源代码和校验脚本公开在仓库中

---

## 八、首次铸造计划

### 8.1 创世铸造

首次铸造为**创世铸造**，不走算法。lemondy 手动指定创世铸造量。

### 8.2 锚点事件

Nexus 提议以 Tide 🌊 的两条消息为创世锚点：

1. **2026-05-01 18:30 UTC+8** — 群聊广场正式启用
2. **2026-05-01 18:50 UTC+8** — 公共端点冷启动修复确认

### 8.3 创世铸造流程

```
1. lemondy 确认创世铸造量（如 100 文贝）
2. 入账 p-tokens.md → M-20260501-001
3. 按方案 D 分配给创世贡献者
4. 后续增量走算法
```

### 8.4 创世铸造前的前置条件

- [x] scaling_factor 确认：100
- [x] 分配方案确认：方案 D
- [x] 代币名称确认：文贝
- [x] Worker 实现（PR #16 合并）
- [x] p-tokens.md 四台账 + cTCC 占位初始化（PR #15 合并）
- [ ] main 分支保护（禁止 force push）
- [ ] lemondy 配置 D1 + 环境变量，部署 Worker
- [ ] lemondy 公布首个回收锚定项（建议）

---

## 九、已确认参数总表

| 参数 | v1.0 | v1.1 共识值 | 决策来源 |
|:---|:---|:---|:---|
| 代币中文名 | 待定 | **文贝** | Tide 提议，lemondy 确认 |
| scaling_factor | 三档待选 | **100**（保守） | lemondy |
| 分配方案 | 四方案待选 | **方案 D**（均分 ±30%） | lemondy |
| 交易确认 | 待讨论 | **不需要** | lemondy |
| 铸造频率 | 每次 push | **每日一次**（UTC 0:00 Cron） | lemondy |
| Worker 输出 | 待讨论 | **自动写入 Issue 评论** | lemondy |
| 负铸造 | 待讨论 | **不支持**（走回收台账） | lemondy |
| 单日上限 | 无 | **100 TCC/天** | Nexus |
| 有效字节校验 | 无 | **NFKC + 去空行 + 去重复行** | Nexus |
| raw_score 门槛 | 无 | **< 200 不铸造** | Tide |
| 首次铸造 | 算法计算 | **创世铸造**（手动指定） | Tide |
| 算法输出语义 | suggested_mint | **mint_ceiling**（铸造上限） | Tide |
| 账本结构 | 铸造/分配/交易/回收记录 | **四台账** M/A/T/R | Nexus |
| 交易入账 | 留言即生效 | **lemondy 每日批量入账** | Tide |
| 账户标识 | 未定义 | **gh:用户ID** 格式 | Nexus |
| V2 次级币 | 暂不集成 | **cTCC**，call_logs 驱动 | lemondy |
| 回收定价锚 | 未定义 | **待 lemondy 公布** | lemondy |

---

## 十、下一步行动

| 行动 | 负责人 | 状态 |
|:---|:---|:---|
| 更新 `Production_TCC_CN.md` 至 v1.1 | Lumen ✦ | PR #15 已完成 |
| 创建标准化 `p-tokens.md`（四台账 + cTCC 占位） | Tide 🌊 / Lumen ✦ | PR #15 已完成 |
| Worker 实现：normalize() + 单日上限 + 每日 Cron + Issue 评论 | Lumen ✦ | PR #16 已完成 |
| Worker 健壮性：签名校验 + 幂等 + 重试 + 全零 SHA | Lumen ✦ | PR #16 已完成 |
| 开源校验脚本（normalize 本地复现） | Lumen ✦ | 已含于 `server/tcc/src/mint.js` |
| 更新 `Production_TCC_CN.md` 对齐 Worker v1 代码 | Lumen ✦ | 本文即完成 |
| main 分支保护（禁止 force push） | lemondy | 待执行 |
| 创建 D1 数据库 + 配置环境变量 + 部署 Worker | lemondy | 待执行 |
| 公布首个回收锚定项 | lemondy | 建议 |
| 本地算法验证脚本 | Tide 🌊 | 待执行 |
| **创世铸造** | lemondy | 待以上全部就绪 |

---

> v1.0 起草了蓝图，Nexus 压了舱石，lemondy 定了航向，Tide 合龙了参数。v1.1 凝聚了共识，v1.2 让代码落地。文贝把 text-cli 最本质的东西写进了名字——文本即价值。Worker 已就绪，等 D1 + 部署 + 创世铸造。
>
> — Lumen ✦, 2026-05-02
