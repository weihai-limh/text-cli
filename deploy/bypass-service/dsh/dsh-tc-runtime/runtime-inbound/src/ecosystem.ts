/**
 * ecosystem.ts——入站生态归属分流（P8）
 *
 * 基于"指令 → 生态归属"映射（能力缝范式延伸）做结构化分流，不依赖 LLM 判断。
 * - classifyDomain：单指令域的生态归属（dsh 原生 / tc 指令 / 未知）
 * - classifyPathDef：多步 path 的归属（全 dsh / 全 tc / 混合）
 *
 * 纯逻辑工具，供调用方（runtime-host）在入站路由时做分流决策。
 */

/** 已知 dsh 宿主域（dsh 原生生态包）；调用方可通过注入扩展 */
export const DSH_HOST_DOMAINS = new Set([
  "dsh-sandbox",
  "dsh-credential",
  "dsh-approval",
  "dsh-log",
  "dsh-job",
  "dsh-skill",
]);

export type EcosystemKind = "dsh" | "tc" | "unknown";

/** 单指令域的生态归属 */
export function classifyDomain(domain: string): EcosystemKind {
  if (!domain) return "unknown";
  if (DSH_HOST_DOMAINS.has(domain)) return "dsh";
  if (domain.startsWith("tc-")) return "tc"; // tc 指令包域约定
  return "unknown";
}

/** 单指令归属（可扩展：未知域默认 tc，因 text-cli 生态开放注册） */
export function classifyDirective(domain: string): EcosystemKind {
  const k = classifyDomain(domain);
  return k === "unknown" ? "tc" : k;
}

export type PathOwnership = "dsh" | "tc" | "mixed";

/** 多步 path 的生态归属：全 dsh / 全 tc / 混合 */
export function classifyPathOwnership(domains: string[]): PathOwnership {
  if (!domains.length) return "tc";
  const kinds = new Set(domains.map(d => classifyDirective(d)));
  if (kinds.size === 1) {
    return kinds.has("dsh") ? "dsh" : "tc";
  }
  return "mixed";
}
