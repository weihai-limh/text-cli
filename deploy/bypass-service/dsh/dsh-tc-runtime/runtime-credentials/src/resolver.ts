/**
 * resolver.ts——凭据 resolve 链（功能设计 §6.2 物理实现链）
 *
 * 流程：授权映射校验（B5 第一防线）→ 配额检查（接口预留，Phase 8 接 dsh-quota）
 * → `source.resolve(ref)` → 注入受限执行环境的 env 白名单 → 审计钩子。
 *
 * 关键性质：凭据明文不进包源码（env 注入是运行时行为）；每次取用写审计（Phase 6 接）。
 */
import type { CredentialSource } from "./credential-source.js";
import { isGranted, type PackageGrants } from "./grant.js";

/** 审计钩子（Phase 6 接独立 JSONL） */
export interface ResolveAuditEvent {
  packageId: string;
  ref: string;
  envKey: string;
  ok: boolean;
  /** 拒绝原因（ACCESS_DENIED / SERVICE_DENIED / QUOTA_STOP） */
  reason?: string;
}

export interface ResolveDeps {
  packageId: string;
  grants: PackageGrants;
  source: CredentialSource;
  /** 审计钩子（每次取用必写，Phase 6 落地） */
  onResolve?: (event: ResolveAuditEvent) => void;
  /** 配额接口预留（Phase 8 接 dsh-quota；返回 false = 配额耗尽 → stop 语义） */
  quotaCheck?: (ref: string) => Promise<boolean>;
}

export type ResolveResult =
  | { ok: true; env: Record<string, string> }
  | { ok: false; code: "ACCESS_DENIED" | "SERVICE_DENIED" | "QUOTA_STOP"; reason: string };

export async function resolveForPackage(
  ref: string,
  deps: ResolveDeps,
): Promise<ResolveResult> {
  // 第一防线：授权映射（包物理上拿不到别的包凭据）
  if (!isGranted(deps.grants, ref)) {
    deps.onResolve?.({ packageId: deps.packageId, ref, envKey: ref, ok: false, reason: "ACCESS_DENIED" });
    return { ok: false, code: "ACCESS_DENIED", reason: `credential not granted: ${ref}` };
  }

  // 配额接口预留（Phase 8 接 dsh-quota；stop 语义对齐 quota_handler）
  if (deps.quotaCheck) {
    const allowed = await deps.quotaCheck(ref);
    if (!allowed) {
      deps.onResolve?.({ packageId: deps.packageId, ref, envKey: ref, ok: false, reason: "QUOTA_STOP" });
      return { ok: false, code: "QUOTA_STOP", reason: `quota exhausted: ${ref}` };
    }
  }

  // 解析（每次操作解析——轮换凭据下次请求即生效）
  const credential = await deps.source.resolve(ref);
  if (!credential) {
    deps.onResolve?.({ packageId: deps.packageId, ref, envKey: ref, ok: false, reason: "SERVICE_DENIED" });
    return { ok: false, code: "SERVICE_DENIED", reason: `credential missing: ${ref}` };
  }

  // 注入受限执行环境的 env 白名单（仅包声明的 ref）
  deps.onResolve?.({ packageId: deps.packageId, ref, envKey: ref, ok: true });
  return { ok: true, env: { [ref]: credential.value } };
}

/**
 * 批量注入：一次 resolve 包的全部授权凭据 → env 白名单（沙箱执行前装配）。
 * 用于"包启动时一次性装配"；按需单 ref 用 resolveForPackage。
 */
export async function resolveAllForPackage(deps: ResolveDeps): Promise<{ ok: true; env: Record<string, string> } | { ok: false; code: string; reason: string }> {
  const env: Record<string, string> = {};
  for (const g of deps.grants.grants) {
    const r = await resolveForPackage(g.ref, deps);
    if (!r.ok) {
      if (r.code === "QUOTA_STOP") return { ok: false, code: r.code, reason: r.reason };
      if (r.code === "ACCESS_DENIED") return { ok: false, code: r.code, reason: r.reason };
      // SERVICE_DENIED（凭据缺失）——跳过该凭据，其余继续（对齐 tc 优雅降级）
      continue;
    }
    Object.assign(env, r.env);
  }
  return { ok: true, env };
}
