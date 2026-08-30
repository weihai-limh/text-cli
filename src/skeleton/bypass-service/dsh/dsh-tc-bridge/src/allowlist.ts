// tc 指令白名单：基于可配置 allowlist 的 tc 指令暴露控制（仅 tc 源，dsh_tool 不过滤）。
// 对齐 dsh-tc-bridge.md §2.3.5（粒度 domain;action，支持域级/通配；空 = 全暴露，红线④）。
import type { TcDirectiveMeta } from './types.js';

/** 白名单条目：`domain;action`，支持 `domain;*`（域级通配）与 `*`（全通配） */
export interface Allowlist {
  /** 条目列表；空数组 = 全部暴露（向后兼容桥接模式） */
  entries: string[];
}

/** 解析白名单条目 → { domain, action }；`*` = 全通配；action 为 `*` = 域级通配 */
function parseEntry(entry: string): { domain: string | '*'; action: string | '*' } | null {
  const trimmed = entry.trim();
  if (trimmed === '*') return { domain: '*', action: '*' };
  const idx = trimmed.indexOf(';');
  if (idx < 0) return null;
  const domain = trimmed.slice(0, idx).trim();
  const action = trimmed.slice(idx + 1).trim();
  if (!domain) return null;
  return { domain, action: action === '*' ? '*' : action };
}

/** 判断单条指令是否命中白名单 */
function matchOne(d: TcDirectiveMeta, entry: string): boolean {
  const p = parseEntry(entry);
  if (!p) return false;
  if (p.domain === '*') return true; // 全通配
  if (d.domain !== p.domain) return false;
  if (p.action === '*') return true; // 域级通配
  return d.action === p.action;
}

/**
 * 过滤 tc 指令：仅保留白名单内的指令。
 * - 白名单为空 → 返回原数组（全暴露，兼容桥接模式）。
 * - 粒度匹配：先精确 domain;action，再域级通配 domain;*。
 */
export function filterTcDirectives(directives: TcDirectiveMeta[], allowlist: Allowlist): TcDirectiveMeta[] {
  if (allowlist.entries.length === 0) return directives;
  return directives.filter((d) => allowlist.entries.some((entry) => matchOne(d, entry)));
}

/** 便捷：从 string[] 构造 Allowlist */
export function makeAllowlist(entries: string[]): Allowlist {
  return { entries };
}
