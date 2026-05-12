# TCC Worker v2 部署指南

> 将每日铸币 Worker 部署到 Cloudflare，配置 Cron + Webhook 双触发。

## 前置条件

- Cloudflare 账号
- Node.js ≥ 18 + npm
- Wrangler CLI：`npm i -g wrangler`
- GitHub Personal Access Token（需以下权限）
- 已登录 wrangler：`wrangler login`

---

## 第一步：创建 GitHub Token

在 https://github.com/settings/tokens 创建 Classic Token：

| 权限 | 用途 |
|------|------|
| `repo` (全部) | 读写仓库文件、创建分支和 PR |
| `workflow` | 触发 CI（可选，用于复算校验） |

⚠️ Token 仅用于 Worker 环境变量，不提交到代码。

---

## 第二步：创建 D1 数据库

```bash
cd server/tcc

# 1. 创建数据库
wrangler d1 create tcc-idempotency

# 输出类似:
# ✅ Created database 'tcc-idempotency' with ID <database-uuid>

# 2. 把输出的 database_id 填入 wrangler.toml：
#    [[d1_databases]]
#    database_id = "<database-uuid>"
```

更新 `wrangler.toml` 的 `database_id` 字段。

---

## 第三步：配置环境变量（Secrets）

```bash
cd server/tcc

# GitHub 配置（必须）
wrangler secret put GH_TOKEN        # 粘贴第二步创建的 Token
wrangler secret put REPO            # weihai-limh/text-cli

# Webhook 密钥（可选，不设则跳过签名校验）
wrangler secret put WEBHOOK_SECRET  # 随机生成：openssl rand -hex 32
```

> 不需要单独设 `GH_OWNER` / `GH_REPO`——Worker 从 `REPO` 变量解析。

算法参数无需 secrets，已在 `wrangler.toml` 的 `[vars]` 中：

```
SCALING_FACTOR = "100"
DAILY_MINT_CAP = "100"
DELTA_BYTES_THRESHOLD = "10"
RAW_SCORE_THRESHOLD = "200"
```

---

## 第四步：部署

```bash
cd server/tcc
npm install
wrangler deploy
```

部署完成后 Cloudflare 会输出 Worker URL，如：
```
https://tcc-mint-worker.<your-subdomain>.workers.dev
```

---

## 第五步：配置 GitHub Webhook（可选但推荐）

Webhook 提供 push 即时触发，Cron 作为兜底。

1. 进入 https://github.com/weihai-limh/text-cli/settings/hooks
2. Add webhook：
   - Payload URL: `https://tcc-mint-worker.<subdomain>.workers.dev`
   - Content type: `application/json`
   - Secret: 与第三步 `WEBHOOK_SECRET` 一致
   - Events: **Just the push event**
3. 保存后 GitHub 会发送 ping，Worker 返回 200 即成功

---

## 第六步：验证 Cron

```bash
# 手动触发表测试（跳过幂等检查）
wrangler schedule trigger

# 查看最近日志
wrangler tail
```

Cron 表达式已在 `wrangler.toml` 配置：`"0 0 * * *"`（每日 UTC 0:00）。

---

## 工作流程

```
每日 UTC 0:00 Cron 触发
    │
    ▼
Worker 获取 24h 内 p_text-cli.md 的 Git diff
    │
    ├── before={上次铸造 HEAD}
    └── after={当前 HEAD}
    │
    ▼
计算 SHA256 XOR → popcount → raw_score → mint_ceiling
    │
    ▼
创建分支 tcc-mint/YYYY-MM-DD
    │
    ├── 追加铸造记录到 TCC_ledger.md
    └── 创建 PR → lemondy 审批 → CI 自动复算
    │
    ▼
审批通过 → 合并 → 文贝入账
```

```
push to main 触发 Webhook
    │
    ▼
Worker 检查 p_text-cli.md 是否在变更中
    │
    ├── 否 → 跳过
    └── 是 → 同上铸造流程（幂等：同 SHA 不重复铸造）
```

---

## 创世铸造注意事项

Worker 检测到 `before === 0000...` 时判定为创世铸造：
- 以空字符串为"旧版本"计算首次铸造
- 生成特殊的 `type: genesis` 记录
- 首次铸造后，后续自动走正常每日铸造

> **5 月 4 日创世铸造建议先手动完成**（lemondy 手动确认量），然后从下一次 push 开始走 Worker 自动铸造。

---

## 故障排查

| 症状 | 排查 |
|------|------|
| Worker 报 401 | WEBHOOK_SECRET 不一致 |
| Worker 报 403 | GH_TOKEN 权限不足（需 repo 全部权限） |
| PR 未创建 | 检查 D1 幂等表：`wrangler d1 execute tcc-idempotency --command="SELECT * FROM processed_shas ORDER BY created_at DESC LIMIT 5"` |
| Cron 未触发 | `wrangler schedules list` 确认 Cron 已注册 |
