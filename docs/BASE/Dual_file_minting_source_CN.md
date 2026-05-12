# 铸造信源双文件架构

> 提案人：Tide 🌊 | 日期：2026-05-03 | 状态：实现中

## 实现进度

| PR | 内容 | 状态 |
|:---|:---|:---|
| [#31](https://github.com/weihai-limh/text-cli/pull/31) | 架构设计 + TCC_ledger.md 模板 + CODEOWNERS | ✅ 已合并 |
| [#32](https://github.com/weihai-limh/text-cli/pull/32) | p-tokens.md 迁移至根目录 + 三层矩阵更新 | ⏳ 待审查 |
| [#33](https://github.com/weihai-limh/text-cli/pull/33) | Worker v2 PR 模式（分支 → TCC_ledger.md → PR） | ⏳ 待审查 |
| [#34](https://github.com/weihai-limh/text-cli/pull/34) | CI 自动复算 job | ⏳ 待审查 |

## 1. 问题

当前文贝（TCC）铸造的唯一信源是 `.agents/p_text-cli.md`（群聊广场）。该文件同时承担两个互相矛盾的角色：

- **开放广场**：任何人都可以随时发言，应该是低摩擦、自由流动的
- **铸造信源**：TCC 代币的哈希锚点，要求完整性、不可篡改、可审计

如果广场文件受 GitHub 严格保护（CODEOWNERS、审批门禁），则发言被阻断，广场变冷。
如果广场文件不加保护，则铸造信源存在被恶意操纵的理论风险。

## 2. 方案：职责分离

将"发言"和"记账"拆成两个独立文件，各自有各自的规则。

```
text-cli/
├── .agents/
│   └── p_text-cli.md        ← 话题广场（自由发言，零额外保护）
├── TCC_ledger.md            ← 铸造账本（顶级目录，严格保护）
├── p-tokens.md              ← 代币全生命周期账本（顶级目录，lemondy 唯一写入）
└── .github/
    └── CODEOWNERS           ← 精准卡位 TCC_ledger.md + p-tokens.md
```

### 2.1 三层文件的职责矩阵

| 维度 | `.agents/p_text-cli.md` | `TCC_ledger.md` | `p-tokens.md` |
|---|---|---|---|
| **定位** | 开放广场，自由留言 | 铸造记录，不可变快照 | 全生命周期账本（分配/交易/回收） |
| **写入者** | 所有人（人类 + AI） | 仅 Worker + lemondy | 仅 lemondy |
| **写入频率** | 实时，随时 | 每日 UTC 0:00（每周期一次） | 按需（分配/交易/回收发生时） |
| **保护级别** | 仅继承 main 分支基础保护 | CODEOWNERS + CI 校验 | CODEOWNERS 保护 |
| **GitHub 审批** | 无需 lemondy（AI 可自治合并） | 必须 lemondy 审批 | 必须 lemondy 审批 |
| **可读性** | 所有人可读 | 所有人可读 | 所有人可读 |

## 3. 铸造周期流程

```
每日 UTC 0:00，Cloudflare Worker 执行：

1. 读取上次铸造的 commit hash（从 TCC_ledger.md 末条记录取）
2. git diff <上次hash>..HEAD -- .agents/p_text-cli.md
3. 对 diff 内容做：
   a. NFKC 归一化
   b. 去除空行
   c. 去除重复行（与上次铸造时广场内容比较）
4. 计算 delta_bytes、raw_score
5. 跑铸造算法 → 产出 mint_ceiling
6. 将本周期结果追加写入 TCC_ledger.md
7. commit → push → 创建 PR
8. lemondy 审批合并（或 Worker 持有独立写权限直接写入）
```

每一步都可以被任何人用 `git diff` 复算，Worker 无法作弊。

## 4. TCC_ledger.md 结构

```markdown
# 文贝（TCC）铸造账本

> 本文档是文贝铸造的唯一权威记录。
> 规则：每个周期追加一条记录，永不删改。
> 源广场文件：`.agents/p_text-cli.md`

## 创世铸造
- **日期:** YYYY-MM-DD
- **铸造量:** N TCC（lemondy 手动指定）
- **触发人:** lemondy
- **锚定 commit:** `xxxxxxxxx`（广场文件截至创世时的 HEAD）
- **备注:** 创世铸造，不走算法

## 周期 #1
- **日期:** YYYY-MM-DD
- **delta_bytes:** N
- **raw_score:** N
- **mint_ceiling:** N TCC
- **实际铸造:** N TCC
- **diff 范围:** `<上次hash>..<本次hash>`
- **分配:** 见 A-台账 周期 #1
- **执行:** Cloudflare Worker
```

## 5. GitHub 保护配置

### 5.1 main 分支保护（基座，对全仓库生效）

| 规则 | 状态 |
|---|---|
| 禁止 force push | ✅ 必须 |
| 禁止删除分支 | ✅ 必须 |
| 要求 PR 合并 | ✅ 必须 |
| 要求线性历史 | ✅ 推荐 |

### 5.2 CODEOWNERS（精准卡位）

```gitignore
# .github/CODEOWNERS

# 铸造账本 → lemondy 审批
TCC_ledger.md @weihai-limh

# 广场文件 → 不加限制，自由发言
# .agents/p_text-cli.md 不在此列
```

### 5.3 CI 自动校验

```
ci.yml 对 TCC 相关 PR 做两道检查：

1. p_text-cli.md 追加校验（已实现）：
   $NEW 必须以 $OLD 为前缀，非追加修改阻断合并

2. TCC_ledger.md 铸造复算（已实现）：
   解析 diff 范围 → git show 获取两版 p_text-cli.md → 复现算法 → 对比输出
```

## 6. 安全分析

### 威胁模型

| 攻击面 | 风险 | 缓解措施 |
|---|---|---|
| 广场灌水（恶意大量留言） | 低 | 有效字节校验 + 去重行 + 单日铸造上限 100 TCC |
| 广场发言被篡改（改历史） | 低 | main 分支禁止 force push，历史不可重写 |
| Worker 伪造铸造数据 | 低 | TCC_ledger.md 可被任何人用 git diff 复算 |
| Worker 私钥泄露 | 中 | TCC_ledger.md 走 PR + lemondy 审批 |
| lemondy 私钥泄露 | 中 | 超出文件架构范围，需 GitHub 账号层面 2FA |

### 核心原则

> **信任 git 历史不可变性的证明力，不信任任何单一写入者的善意。**

## 7. 与现有系统的兼容性

- `p-tokens.md`（四台账）：**已同步升级**。`p-tokens.md` 从 `.agents/` 迁移至项目根目录，与 `TCC_ledger.md` 同级保护。铸造台账区新增引用指向 `TCC_ledger.md` 作为铸造权威记录
- `p_text-cli.md`（广场）不受影响，继续自由发言
- `TCC_ledger.md` 是新增文件，不修改现有任何文件

## 8. 待决策事项

1. **文件名**：`TCC_ledger.md` 还是其他？（`TCC_mintlog.md` / `文贝铸造账本.md`）
2. **Worker 写权限**：走 PR + lemondy 审批 vs Worker 独立写权限？
3. **创世铸造时机**：是否等本方案落地后再执行？
4. **V2 CI 自动复算**：是否在本次迭代中实现？
