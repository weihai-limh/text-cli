/**
 * aggregate.ts——聚合降级（指令路由层 try-in-order，功能设计 §10.2）
 *
 * - default[] 候选按序遍历 → execute → 信封判定（isError / value.status=="stop"）→ 切换
 * - 末参显式指定 provider（`,provider:<domain>;<action>`）→ 不走降级，只走该候选
 * - 审批合并：整链一次决策（防风暴）
 * - 环检测：agg:<name>（祖先链）
 * - 消费 quota stop：聚合前查 quota，stop → 直接返回 stop 信封（降级信号）
 */
import { CycleDetectedError } from "@dsh-tc/runtime-sandbox";
import type { AggProvider, AggregateDeps } from "./types.js";

function isErrorResult(r: unknown): boolean {
  if (r && typeof r === "object" && "rst_err" in (r as Record<string, unknown>)) {
    const e = (r as Record<string, unknown>).rst_err;
    return typeof e === "string" && e.length > 0;
  }
  return false;
}

function isStop(r: unknown): boolean {
  if (r && typeof r === "object") {
    const data = (r as Record<string, unknown>).rst_data;
    if (data && typeof data === "object" && (data as Record<string, unknown>).status === "stop") {
      return true;
    }
  }
  return false;
}

const PROVIDER_RE = /^provider:(.+)$/;

export async function aggregate(
  name: string,
  candidates: AggProvider[],
  params: string[],
  deps: AggregateDeps,
): Promise<unknown> {
  const key = `agg:${name}` as const;

  // 环检测
  if (deps.ancestorChain.contains(key)) {
    throw new CycleDetectedError(key);
  }

  // 末参显式指定 provider
  let explicit: AggProvider | undefined;
  const last = params[params.length - 1];
  const m = last?.match(PROVIDER_RE);
  if (m) {
    const [d, a] = m[1].split(";");
    if (d && a) explicit = { domain: d, action: a };
    params = params.slice(0, -1); // 去掉末参
  }

  // 消费 quota stop（降级信号）
  if (deps.quota) {
    const q = await deps.quota.check(name);
    if (q.status === "stop") {
      return { rst_err: "", rst_data: { status: "stop", reason: "quota_exhausted" } };
    }
  }

  // 审批合并：整链一次决策
  if (deps.approval) {
    const d = await deps.approval({
      callId: `agg-${name}-${deps.now?.() ?? 0}`,
      toolName: `agg:${name}`,
      reason: "aggregate dispatch",
    });
    if (!d.decided || !d.allowed) {
      return { rst_err: "ERR_EXECUTION", rst_data: { reason: `approval denied: ${d.decidedBy ?? "no-decision"}` } };
    }
  }

  const list = explicit ? candidates.filter((c) => c.domain === explicit!.domain && c.action === explicit!.action) : candidates;
  if (list.length === 0) {
    return { rst_err: "ERR_NOT_FOUND", rst_data: {} };
  }

  deps.ancestorChain.push(key);
  try {
    for (const c of list) {
      let r: unknown;
      try {
        r = await deps.dispatch(c.domain, c.action, params);
      } catch {
        continue; // 抛错 → 降级到下一候选
      }
      if (isErrorResult(r) || isStop(r)) continue;
      return r;
    }
    return { rst_err: "ERR_EXECUTION", rst_data: { reason: "DEGRADE_EXHAUSTED" } };
  } finally {
    deps.ancestorChain.pop(key);
  }
}
