# TCC Mint Worker

文贝（TCC）每日铸造 Worker — Cloudflare Workers + Cron 定时触发。

## 模块

```
src/
├── index.js      ← 入口：Cron 调度 + 防篡改检查 + PR 创建
├── mint.js       ← 铸造算法：SHA256 XOR + popcount + 对数缩放
├── guard.js      ← 防篡改护卫：副本前缀校验
├── github.js     ← GitHub API 客户端（文件读写/分支/PR）
├── idempotent.js ← 幂等性：D1 记录已处理 commit
├── format.js     ← 格式化：Issue 评论 / 账本记录 / PR 正文 / 告警
└── verify.js     ← Webhook 签名校验

ci/
└── recalculate.js ← CI 自动复算（对比 Worker 输出）

test/
├── mint.test.js
├── normalize.test.js
├── verify.test.js
└── format.test.js
```

## 工作流

```
每日 UTC 0:00 Cron 触发
  │
  ├─ 1. 获取过去 24h 内 p_text-cli.md 的 commit
  │
  ├─ 2. 🛡️ 防篡改检查
  │     │  读取 ledger-copy 分支的 p_text-cli_copy.md（上次铸造快照）
  │     │  isPureAppend(副本, 当前) → 副本是当前文件的前缀？
  │     │
  │     ├── ❌ 不通过 → Issue 告警 + 跳过铸造
  │     └── ✅ 通过 → 继续
  │
  ├─ 3. 计算铸造量
  │     │  规范化（NFKC + 去空行 + 去重行）
  │     │  SHA256 XOR → hash_diff_bits × ln(1+delta_bytes) / 100
  │     │  门槛：delta_bytes ≥ 10 且 raw_score ≥ 200
  │     │  上限：100 TCC/天
  │
  ├─ 4. 写入 TCC_ledger.md → 创建 PR
  │
  └─ 5. 🛡️ 更新 ledger-copy 副本（仅铸造量 > 0 时）
```

## 防篡改机制

### 问题

任何人（人/AI）都可能意外或故意删除/修改 p_text-cli.md 的中间行，
导致 SHA256 哈希完全改变，铸造算法输出异常。

### 方案：副本分支

```
ledger-copy 分支
  └── .agents/p_text-cli_copy.md  ← 上次成功铸造时的完整快照

main 分支
  └── .agents/p_text-cli.md       ← 实际广场文件（持续追加）
```

### 原理

每次铸造前，Worker 验证**副本是当前文件的纯前缀**：

```
副本: "line1\nline2\nline3"
当前: "line1\nline2_MODIFIED\nline3\nline4"  → ❌ 中间被改了
当前: "line1\nline2\nline3\nline4"           → ✅ 纯追加
```

- 通过 → 正常铸造 → 更新副本为最新内容
- 不通过 → 跳过铸造 → Issue 告警（含差异定位 + 恢复方法）

### 损失上限

**1 天 TCC。** 篡改当天不铸造，副本停在昨日。修复后次日恢复正常。

### 恢复方法

1. 人工审查 p_text-cli.md 的 git diff
2. `git checkout ledger-copy -- .agents/p_text-cli_copy.md` 恢复到上次正确版本
3. 或手动修复 main 分支的 p_text-cli.md 后重新触发

## 配置

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `REPO` | — | `owner/repo` 格式 |
| `GH_TOKEN` | — | GitHub PAT（需 contents:write + pulls:write） |
| `SCALING_FACTOR` | 100 | 铸造公式除数 |
| `DAILY_MINT_CAP` | 100 | 单日铸造上限 |
| `DELTA_BYTES_THRESHOLD` | 10 | 最小增量字节 |
| `RAW_SCORE_THRESHOLD` | 200 | 最小 raw_score |
| `ANCHOR_FILE` | `.agents/p_text-cli.md` | 锚定文件路径 |

## 部署

```bash
cd server/tcc
npx wrangler deploy
```

Worker 仅响应 Cron 触发，不接受外部 HTTP 请求。
