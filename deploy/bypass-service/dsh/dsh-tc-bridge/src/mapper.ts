// 前缀双射映射：AI:d;a ↔ tc__<domain>__<action>（混合模式）。
// 对齐 dsh-tc-bridge.md §2.3.5（mapper 双射约束：命名含 __ 拒绝，红线③）。
import type { BridgeMode } from './types.js';

/** tc 工具名的双下划线分隔符 */
const SEP = '__';

/**
 * AI:d;a → runtime 工具名 tc__<domain>__<action>。
 * domain/action 含 `__` 时拒绝（避免双射歧义，红线③）。
 */
export function toolName(domain: string, action: string): string {
  if (domain.includes(SEP) || action.includes(SEP)) {
    throw new Error(`domain/action must not contain "${SEP}": ${domain};${action}`);
  }
  return `tc__${domain}__${action}`;
}

/** 拆分 tc__<d>__<a> → { domain, action }；格式不符返回 null */
export function fromToolName(name: string): { domain: string; action: string } | null {
  if (!name.startsWith('tc__')) return null;
  const body = name.slice('tc__'.length);
  const parts = body.split(SEP);
  if (parts.length !== 2) return null; // 必须是恰好两个段，防歧义
  const [domain, action] = parts;
  if (!domain || !action) return null;
  return { domain, action };
}

/** 判断某工具名是否为 tc 运行时注册的 tc__ 前缀工具（模态检测用） */
export function isTcTool(name: string): boolean {
  return name.startsWith('tc__');
}

/**
 * 归一化工具名（对齐 runtime-mapper normalizeName）：
 * 若名字已是 tc__ 形式，返回原样；否则包一层（供 find_tc 的 tc_local 源）。
 */
export function normalizeToolName(domainOrName: string, action?: string): string {
  if (action === undefined) return domainOrName; // 已是完整名
  return toolName(domainOrName, action);
}

/** 便捷：模态感知下取调用目标（桥接模式不经 mapper，直接返回原 prompt 域/动作） */
export function targetToolName(domain: string, action: string, mode: BridgeMode): string {
  return mode === 'hybrid' ? toolName(domain, action) : `${domain};${action}`;
}
