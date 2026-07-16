# .bills — 项目内部经济记录

> **定位**：`.bills` 是 `text-cli` 项目的内部经济记录目录。它记录文贝（TCC）和 c文贝（cTCC）在项目内部的流转决策、分配依据和台账快照。
>
> **与 `p-tokens.md` 的关系**：`p-tokens.md` 是**权威账本**（TCC 全生命周期四台账），`.bills/` 是**工作记录**——账本的源数据、决策上下文、周报快照。前者从审计角度看，后者从日常协作角度看。

---

## 目录结构

```
.bills/
├── README.md                  # 本文件
├── YYYY-WXX/                  # 按 ISO 周组织（如 2026-W19）
│   ├── summary.md             # 周汇总 PR 快照副本
│   ├── contributions.md       # 当周贡献明细（资产 + 非资产）
│   └── distribution.md        # 当周分配结果（谁获得多少 TCC/cTCC）
└── treasury/                  # 金库记录（跨周）
    ├── balance.md             # 金库余额（TCC 可用 / 锁定 / cTCC 储备）
    ├── income.md              # 金库收入（30% 分流 + 捐赠 + 端点收入）
    └── expenditure.md         # 金库支出（cTCC 兑换 / 应急激励 / 开源收购）
```

## 记录规则

1. **追加不删改**：所有 `.bills/` 下的记录为自增追加，已有记录不删改
2. **按周组织**：每个 ISO 周创建独立子目录，周五/周六/周日发生的贡献归入当周
3. **与广场同步**：所有涉及 TCC/cTCC 流转的决策最终广场确认，`.bills/` 为广场决策的结构化快照
4. **自动化**：AI 协作者（Tide）在每周生成周汇总 PR 时自动更新对应周目录

## 关联文档

- `p-tokens.md` — TCC 权威账本（铸造/分配/交易/回收四台账）
- `TCC_ledger.md` — 铸造权威记录
- `docs/CN/Ecological_economy_CN.md` — 生态经济体系（经济规则定义）
- `docs/CN/项目金库使用规范_CN.md` — 项目金库使用规范

---

> `.bills` is where the project's economic heartbeat is recorded. Not the ledger — the pulse behind the ledger.
