#!/usr/bin/env python3
"""
recalculate.py — TCC 铸造本地复算脚本

基于 p_text-cli.md 的 Git 历史，复现每条留言的 TCC 铸造算法，
输出每日铸造建议 + 创世铸造参考值。

算法: SHA256 XOR → popcount → hash_diff_bits × ln(1 + delta_bytes) / scaling_factor
参数: scaling_factor=100, daily_mint_cap=100
       delta_bytes ≥ 10, raw_score ≥ 200

用法:
    cd text-cli
    python3 scripts/recalculate.py
"""

import hashlib
import math
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

# ─── 配置 ─────────────────────────────────────────
SCALING_FACTOR = 100
DAILY_MINT_CAP = 100
DELTA_BYTES_THRESHOLD = 10
RAW_SCORE_THRESHOLD = 200

ANCHOR_FILE = '.agents/p_text-cli.md'


# ─── 算法核心 ─────────────────────────────────────

def normalize(text: str) -> str:
    """NFKC 正规化 + 去空行 + 去重复行 + 去行尾空格"""
    import unicodedata
    result = unicodedata.normalize('NFKC', text)
    lines = result.split('\n')
    no_blank = [l for l in lines if l.strip() != '']
    deduped = [l for i, l in enumerate(no_blank) if i == 0 or l != no_blank[i - 1]]
    trimmed = [l.rstrip() for l in deduped]
    return '\n'.join(trimmed)


def sha256(content: str) -> bytes:
    return hashlib.sha256(content.encode('utf-8')).digest()


def xor_bytes(a: bytes, b: bytes) -> bytes:
    return bytes(x ^ y for x, y in zip(a, b))


def popcount(byte: int) -> int:
    return bin(byte).count('1')


def calculate_mint(old_text: str, new_text: str) -> dict:
    """复现 Worker 的 calculateMint 逻辑。"""
    old_norm = normalize(old_text)
    new_norm = normalize(new_text)
    delta_bytes = len(new_norm) - len(old_norm)

    if delta_bytes < DELTA_BYTES_THRESHOLD:
        return {
            'mint_ceiling': 0,
            'reason': 'delta_too_small',
            'delta_bytes': delta_bytes,
        }

    old_hash = sha256(old_norm)
    new_hash = sha256(new_norm)
    xor_result = xor_bytes(old_hash, new_hash)

    hash_diff_bits = sum(popcount(b) for b in xor_result)

    if hash_diff_bits == 0:
        return {
            'mint_ceiling': 0,
            'reason': 'content_identical',
            'hash_diff_bits': 0,
            'delta_bytes': delta_bytes,
        }

    raw_score = hash_diff_bits * math.log(1 + delta_bytes)

    if raw_score < RAW_SCORE_THRESHOLD:
        return {
            'mint_ceiling': 0,
            'reason': 'raw_score_below_threshold',
            'hash_diff_bits': hash_diff_bits,
            'delta_bytes': delta_bytes,
            'raw_score': round(raw_score, 2),
        }

    suggested_mint = round(raw_score / SCALING_FACTOR)
    mint_ceiling = min(suggested_mint, DAILY_MINT_CAP)

    return {
        'type': 'daily',
        'mint_ceiling': mint_ceiling,
        'hash_diff_bits': hash_diff_bits,
        'delta_bytes': delta_bytes,
        'raw_score': round(raw_score, 2),
        'scaling_factor': SCALING_FACTOR,
        'daily_cap': DAILY_MINT_CAP,
        'old_hash': old_hash.hex(),
        'new_hash': new_hash.hex(),
    }


# ─── Git 历史提取 ────────────────────────────────

def get_commits_by_date():
    """获取 p_text-cli.md 的所有 commit，按日期分组。"""
    cmd = [
        'git', 'log', '--reverse', '--format=%H|%ai|%s',
        '--', ANCHOR_FILE
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Git 错误: {result.stderr}")
        sys.exit(1)

    commits = []
    for line in result.stdout.strip().split('\n'):
        if not line:
            continue
        sha, date_str, *subject_parts = line.split('|')
        date = date_str[:10]  # YYYY-MM-DD
        commits.append({
            'sha': sha,
            'date': date,
            'subject': '|'.join(subject_parts),
        })
    return commits


def get_file_content_at(sha: str) -> str:
    """获取指定 commit 时的文件内容。"""
    cmd = ['git', 'show', f'{sha}:{ANCHOR_FILE}']
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return ''
    return result.stdout


# ─── 创世铸造计算 ────────────────────────────────

def calculate_genesis(content: str) -> dict:
    """
    创世铸造：以空字符串为"旧版本"计算首次铸造。
    """
    result = calculate_mint('', content)
    result['type'] = 'genesis'
    result['reason'] = 'genesis_creation'
    return result


# ─── 按日期累计铸造 ──────────────────────────────

def calculate_all():
    commits = get_commits_by_date()
    if not commits:
        print("未找到 p_text-cli.md 的 commit 记录")
        return

    # 创世铸造：首个 commit 之前的内容为空
    genesis_content = get_file_content_at(commits[0]['sha'])
    genesis = calculate_genesis(genesis_content)

    # 按日期分组，计算每个"铸造日"的变化
    # 实际 Worker 行为：每日 UTC 0:00 取 last_minted_sha..HEAD diff
    # 这里模拟：按日期分组，每组最后一个 commit 为当日终态
    daily_groups = defaultdict(list)
    for c in commits:
        daily_groups[c['date']].append(c)

    daily_mints = []
    prev_content = genesis_content
    prev_sha = commits[0]['sha']
    processed_dates = set()

    for date in sorted(daily_groups.keys()):
        group = daily_groups[date]
        last_commit = group[-1]
        curr_content = get_file_content_at(last_commit['sha'])

        if date not in processed_dates:
            result = calculate_mint(prev_content, curr_content)

            # 解析当日留言发送者
            messages = _parse_messages(get_messages_added(prev_content, curr_content))

            daily_mints.append({
                'date': date,
                'commits': len(group),
                'messages': messages,
                'result': result,
                'from_sha': prev_sha[:8],
                'to_sha': last_commit['sha'][:8],
            })

            processed_dates.add(date)
            prev_content = curr_content
            prev_sha = last_commit['sha']

    return genesis, daily_mints


def get_messages_added(old_content: str, new_content: str) -> str:
    """简单 diff：返回 new 中比 old 多出的部分。"""
    if not old_content:
        return new_content
    if old_content in new_content:
        return new_content[len(old_content):]
    return new_content  # 回退：返回全部


def _parse_messages(added: str) -> list[dict]:
    """解析新增内容中的发送者信息。"""
    import re
    messages = []
    pattern = r'### (\d{4}-\d{2}-\d{2} \d{2}:\d{2} UTC\+8) · ([^→\n]+)'
    for m in re.finditer(pattern, added):
        messages.append({
            'time': m.group(1),
            'sender': m.group(2).strip(),
        })
    return messages


# ─── 输出 ────────────────────────────────────────

def print_report(genesis, daily_mints):
    print("=" * 70)
    print("  TCC 铸造复算报告 — p_text-cli.md")
    print("=" * 70)
    print()
    print(f"  参数: scaling_factor={SCALING_FACTOR}, daily_cap={DAILY_MINT_CAP}")
    print(f"        delta_threshold={DELTA_BYTES_THRESHOLD}, raw_score_threshold={RAW_SCORE_THRESHOLD}")
    print()
    print("-" * 70)
    print("  创世铸造 (Genesis)")
    print("-" * 70)
    print_genesis(genesis)
    print()
    print("-" * 70)
    print(f"  逐日铸造 (共 {len(daily_mints)} 日)")
    print("-" * 70)
    total_ceiling = genesis.get('mint_ceiling', 0)
    for dm in daily_mints:
        print_daily(dm)
        total_ceiling += dm['result'].get('mint_ceiling', 0)
    print()
    print("=" * 70)
    print(f"  总计 (创世 + {len(daily_mints)} 日): {total_ceiling} TCC (算法上限)")
    print(f"  实际铸造量由 lemondy 在 [0, {total_ceiling}] 之间确认")
    print("=" * 70)


def print_genesis(g):
    print(f"  类型: {g['type']}")
    print(f"  铸造上限: {g.get('mint_ceiling', 0)} TCC")
    print(f"  hash_diff_bits: {g.get('hash_diff_bits', 'N/A')}")
    print(f"  delta_bytes: {g.get('delta_bytes', 'N/A')}")
    print(f"  raw_score: {g.get('raw_score', 'N/A')}")
    print(f"  old_hash: {'0' * 64} (空字符串)")
    print(f"  new_hash: {g.get('new_hash', 'N/A')}")


def print_daily(dm):
    r = dm['result']
    mc = r.get('mint_ceiling', 0)
    status = '✅' if mc > 0 else '⏭️'
    senders = ', '.join(set(m['sender'] for m in dm['messages'])) if dm['messages'] else '(无新发言)'
    print(f"  {dm['date']}  {status} 上限={mc:>3} TCC  "
          f"delta={r.get('delta_bytes', 0):>5}B  "
          f"bits={r.get('hash_diff_bits', 0):>4}  "
          f"发言者: {senders}")


# ─── 生成创世铸造模板 ────────────────────────────

def generate_genesis_template(genesis, daily_mints):
    """生成 TCC_ledger.md 的创世铸造条目模板。"""
    total_algorithm = genesis.get('mint_ceiling', 0)
    for dm in daily_mints:
        total_algorithm += dm['result'].get('mint_ceiling', 0)

    lines = []
    lines.append("# TCC 创世铸造记录")
    lines.append("")
    lines.append("> 算法上限仅供参考。lemondy 在 0 到算法上限之间确认实际铸造量。")
    lines.append("")
    lines.append("## 算法复算结果")
    lines.append("")
    lines.append(f"- 创世铸造算法上限: **{genesis.get('mint_ceiling', 0)} TCC**")
    lines.append(f"- 逐日铸造算法上限合计: **{total_algorithm - genesis.get('mint_ceiling', 0)} TCC**")
    lines.append(f"- 算法总计上限: **{total_algorithm} TCC**")
    lines.append("")
    lines.append("## 创世铸造确认")
    lines.append("")
    lines.append("| 参数 | 值 |")
    lines.append("|------|----|")
    lines.append(f"| 铸造日期 | 2026-05-04 |")
    lines.append(f"| 算法建议上限 | {total_algorithm} TCC |")
    lines.append(f"| 实际铸造量 | ___ TCC ← lemondy 填写 |")
    lines.append(f"| casting_type | genesis |")
    lines.append("| anchor_sha | (首次 p_text-cli.md commit) |")
    lines.append("")
    lines.append("## 建议分配方案 (方案 D)")
    lines.append("")
    lines.append("方案 D：基础均分 + lemondy ±30% 加权调整。")
    lines.append("")
    lines.append("建议分配比例（基于项目资产清单贡献度）：")
    lines.append("")
    lines.append("| 协作者 | 建议比例 | 建议 TCC | 确认 TCC |")
    lines.append("|--------|---------|---------|---------|")
    # 基于资产清单贡献
    contributors = [
        ('lemondy', 40, '项目发起、架构设计、核心决策'),
        ('Tide 🌊', 25, '协议审计、Agent 工具包、分布式存续、README 架构'),
        ('Lumen ✦', 20, 'Worker v2、CI 复算、人机协作机制、庇护所实现'),
        ('Nexus', 10, '生态宪章、SPEC v1.0、人机协作提案、分布式存续理念'),
        ('Meridian 🌐', 5, 'MCP 集成、多语言文档重构'),
    ]
    total_pct = sum(pct for _, pct, _ in contributors)
    for name, pct, note in contributors:
        tcc_val = round(total_algorithm * pct / total_pct)
        lines.append(f"| {name} | {pct}% ({note}) | {tcc_val} | ___ |")

    lines.append("")
    lines.append("## 复算详情")
    lines.append("")
    lines.append("```")
    lines.append(f"创世: mint_ceiling={genesis.get('mint_ceiling', 0)}, bits={genesis.get('hash_diff_bits', 'N/A')}, delta={genesis.get('delta_bytes', 'N/A')}")
    for dm in daily_mints:
        r = dm['result']
        lines.append(f"{dm['date']}: mint_ceiling={r.get('mint_ceiling', 0)}, bits={r.get('hash_diff_bits', 0)}, delta={r.get('delta_bytes', 0)}")
    lines.append("```")

    return '\n'.join(lines)


# ─── 入口 ────────────────────────────────────────

if __name__ == '__main__':
    # 确保在项目根目录
    repo_root = Path(__file__).parent.parent
    import os
    os.chdir(repo_root)

    genesis, daily_mints = calculate_all()
    print_report(genesis, daily_mints)

    template = generate_genesis_template(genesis, daily_mints)
    print()
    print("-" * 70)
    print("  创世铸造 TCC_ledger.md 模板 (可直接追加)")
    print("-" * 70)
    print()
    print(template)
