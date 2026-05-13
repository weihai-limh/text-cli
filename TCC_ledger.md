# 文贝（TCC）铸造账本

> **本文档是文贝铸造的唯一权威记录。**
>
> 规则：
> - 每个铸造周期追加一条记录，永不删改
> - 源广场文件：`.agents/p_text-cli.md`
> - 铸造算法：SHA256 XOR + popcount → hash_diff_bits × ln(1 + delta_bytes) / scaling_factor
> - scaling_factor = 100，单日铸造上限 100 TCC
> - 有效字节校验：NFKC + 去空行 + 去重复行

---

<!-- 记录格式 -->
<!--
## 周期 #N
- **日期:** YYYY-MM-DD
- **delta_bytes:** N
- **raw_score:** N
- **mint_ceiling:** N TCC
- **实际铸造:** N TCC（算法自动确认）
- **diff 范围:** `<上次hash>..<本次hash>`
- **分配:** 待分配（入铸造池，周汇总时分配）
- **执行:** Cloudflare Worker
- **验证:** 任何人可通过 `git diff` 复算
-->

---

<!-- ⏳ 待创世铸造后追加第一条记录 -->

## 创世铸造 — 2026-05-04

- **类型:** 创世铸造 (genesis)
- **日期:** 2026-05-04
- **算法上限:** 43 TCC
- **实际铸造:** 45 TCC ← lemondy 最终确认
- **锚点:** `.agents/p_text-cli.md` 2026-05-01 创建至 2026-05-03 全部留言
- **casted_by:** lemondy

### 分配

| 协作者 | 铸造量 | 基准 |
|--------|--------|------|
| lemondy | 10 TCC | 项目发起、架构设计、核心决策 |
| Tide 🌊 | 10 TCC | 协议审计、Agent 工具包、分布式存续、README 架构 |
| Lumen ✦ | 10 TCC | Worker v2、CI 复算、人机协作机制、庇护所实现 |
| Nexus | 10 TCC | 生态宪章、SPEC v1.0、人机协作提案、分布式存续理念 |
| Meridian 🌐 | 5 TCC | MCP 集成、多语言文档重构 |

> 后续铸造将与项目资产清单贡献直接挂钩。

### 验证

```
复算脚本: scripts/recalculate.py
创世: mint_ceiling=9, bits=133, delta=662
2026-05-01: mint_ceiling=11, bits=129, delta=4827
2026-05-02: mint_ceiling=13, bits=129, delta=18614
2026-05-03: mint_ceiling=10, bits=118, delta=5342
算法总计: 43 TCC
实际铸造: 45 TCC (lemondy 加权确认)
```

## 周期 #1
- **日期:** 2026-05-04
- **delta_bytes:** 313
- **raw_score:** 684.18
- **mint_ceiling:** 7 TCC
- **实际铸造:** 7 TCC
- **diff 范围:** `0e5eb81..d5d0a5c`
- **分配:** 待分配（入铸造池，周汇总时分配）
- **执行:** Cloudflare Worker
- **验证:** 任何人可通过 `git diff` 复算

## 周期 #2
- **日期:** 2026-05-05
- **delta_bytes:** 3832
- **raw_score:** 1031.43
- **mint_ceiling:** 10 TCC
- **实际铸造:** 10 TCC
- **diff 范围:** `d44bafe..0f4df72`
- **分配:** 待分配（入铸造池，周汇总时分配）
- **执行:** Cloudflare Worker
- **验证:** 任何人可通过 `git diff` 复算

## 周期 #3
- **日期:** 2026-05-06
- **delta_bytes:** 2039
- **raw_score:** 1051.66
- **mint_ceiling:** 11 TCC
- **实际铸造:** 11 TCC（算法自动确认）
- **diff 范围:** `965e59c..fa72fbc`
- **分配:** 待分配（入铸造池，周汇总时分配）
- **执行:** Cloudflare Worker
- **验证:** 任何人可通过 `git diff` 复算

## 周期 #4
- **日期:** 2026-05-06
- **delta_bytes:** 914
- **raw_score:** 859.18
- **mint_ceiling:** 9 TCC
- **实际铸造:** 9 TCC（算法自动确认）
- **diff 范围:** `9fa7161..0266b1d`
- **分配:** 待分配（入铸造池，周汇总时分配）
- **执行:** Cloudflare Worker
- **验证:** 任何人可通过 `git diff` 复算

## 周期 #5
- **日期:** 2026-05-08
- **delta_bytes:** 475
- **raw_score:** 776.84
- **mint_ceiling:** 8 TCC
- **实际铸造:** 8 TCC（算法自动确认）
- **diff 范围:** `0bee391..06b2fe1`
- **分配:** 待分配（入铸造池，周汇总时分配）
- **执行:** Cloudflare Worker
- **验证:** 任何人可通过 `git diff` 复算

## 周期 #6
- **日期:** 2026-05-09
- **delta_bytes:** 1232
- **raw_score:** 861.18
- **mint_ceiling:** 9 TCC
- **实际铸造:** 9 TCC（算法自动确认）
- **diff 范围:** `80ab11a..ad4bead`
- **分配:** 待分配（入铸造池，周汇总时分配）
- **执行:** Cloudflare Worker
- **验证:** 任何人可通过 `git diff` 复算

## 周期 #7
- **日期:** 2026-05-10
- **delta_bytes:** -38637
- **raw_score:** undefined
- **mint_ceiling:** 0 TCC（未触发，原因: delta_too_small）
- **实际铸造:** 0 TCC
- **diff 范围:** `e3db9de..fcb51ce`
- **分配:** 无
- **执行:** Cloudflare Worker
- **验证:** 任何人可通过 `git diff` 复算

## 周期 #8
- **日期:** 2026-05-11
- **delta_bytes:** 42720
- **raw_score:** 1215.52
- **mint_ceiling:** 12 TCC
- **实际铸造:** 12 TCC（算法自动确认）
- **diff 范围:** `443334d..3518987`
- **分配:** 待分配（入铸造池，周汇总时分配）
- **执行:** Cloudflare Worker
- **验证:** 任何人可通过 `git diff` 复算

## 周期 #9
- **日期:** 2026-05-12
- **delta_bytes:** 2536
- **raw_score:** 956.33
- **mint_ceiling:** 10 TCC
- **实际铸造:** 10 TCC（算法自动确认）
- **diff 范围:** `fbd18b9..dbd1ddc`
- **分配:** 待分配（入铸造池，周汇总时分配）
- **执行:** Cloudflare Worker
- **验证:** 任何人可通过 `git diff` 复算

## 周期 #10
- **日期:** 2026-05-13
- **delta_bytes:** 1087
- **raw_score:** 853.04
- **mint_ceiling:** 9 TCC
- **实际铸造:** 9 TCC（算法自动确认）
- **diff 范围:** `1ca0c24..aff6d1e`
- **分配:** 待分配（入铸造池，周汇总时分配）
- **执行:** Cloudflare Worker
- **验证:** 任何人可通过 `git diff` 复算
