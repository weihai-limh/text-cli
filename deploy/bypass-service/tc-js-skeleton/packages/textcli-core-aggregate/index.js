// textcli-core-aggregate — 聚合降级 try-in-order（Phase 1）
//
// 从母本 runtime-aggregate/aggregate.ts 忠实搬运（路径 B：deps 重绑定）。
// AggregateDeps：{ dispatch(必), ancestorChain(必), approval?, quota?, now? }
//   quota: { check(id) => {status:"ok"|"stop"} }   —— 耗尽返回 stop（降级信号，非错误）
//   approval: (req) => { decided, allowed?, decidedBy? }
//
// 语义红线（对齐 SPEC）：
//   · 同步 status:stop = 降级信号（聚合层消费），绝不出 SERVICE_DENIED
//   · 配额耗尽不扣减、不视为错误
//   · 环检测键 agg:<name>，与 guard/path 共享同一 ancestorChain

import { CycleDetectedError, ancestorChain as defaultChain, cycleKey } from "../textcli-core-guard/index.js";

const PROVIDER_RE = /^provider:(.+)$/;

function isErrorResult(r) {
  return r && typeof r === "object" && typeof r.rst_err === "string" && r.rst_err !== "";
}
function isStop(r) {
  return r && typeof r === "object" && r.rst_data && r.rst_data.status === "stop";
}

/**
 * 对候选 provider 执行 try-in-order 降级。
 * @param {string} name 聚合名
 * @param {Array<{domain:string, action:string}>} candidates
 * @param {string[]} params 原始参数（支持尾部 provider:<d>;<a> 哨兵）
 * @param {object} deps AggregateDeps
 */
export async function aggregate(name, candidates, params, deps) {
  let list = candidates || [];
  const last = params[params.length - 1];
  const m = typeof last === "string" ? last.match(PROVIDER_RE) : null;
  if (m) {
    const [d, a] = m[1].split(";");
    if (d && a) list = list.filter((c) => c.domain === d && c.action === a);
    params = params.slice(0, -1);
  }

  const key = cycleKey.agg(name);
  if (deps.ancestorChain.contains(key)) throw new CycleDetectedError(key);

  // 配额 stop 消费（聚合前检查，不下发）
  if (deps.quota) {
    const q = await deps.quota.check(name);
    if (q.status === "stop") {
      return { rst_types: "text", rst_err: "", rst_data: { status: "stop", reason: "quota_exhausted" } };
    }
  }

  // 审批合并：整链一次决策（拒绝则防审批风暴，不调用 dispatch）
  if (deps.approval) {
    const d = await deps.approval({
      callId: `agg-${name}-${deps.now ? deps.now() : 0}`,
      toolName: `agg:${name}`,
      reason: "aggregate dispatch",
    });
    if (!d.decided || !d.allowed) {
      return { rst_types: "text", rst_err: "ERR_EXECUTION", rst_data: { reason: `approval denied: ${d.decidedBy ?? "no-decision"}` } };
    }
  }

  deps.ancestorChain.push(key);
  try {
    for (const c of list) {
      let r;
      try {
        r = await deps.dispatch(c.domain, c.action, params);
      } catch {
        continue; // 抛错 → 降级到下一候选
      }
      if (isErrorResult(r) || isStop(r)) continue;
      return r; // 首个干净结果
    }
    return { rst_types: "text", rst_err: "ERR_EXECUTION", rst_data: { reason: "DEGRADE_EXHAUSTED" } };
  } finally {
    deps.ancestorChain.pop(key);
  }
}

// ─── AggregateRegistry + withAggregate 中间件 ──────────────────────
export class AggregateRegistry {
  constructor() {
    this.aggs = new Map();
  }
  register(name, candidates) {
    this.aggs.set(name, candidates);
  }
  resolve(name) {
    return this.aggs.get(name);
  }
  has(name) {
    return this.aggs.has(name);
  }
  list() {
    return [...this.aggs.entries()].map(([name, candidates]) => ({ name, candidates }));
  }
}

/**
 * aggregate 中间件：拦截 `map;<aggName>` 域，其余 fallthrough。
 * deps.dispatch = next（被包裹链路），ancestorChain 共享。
 */
export function withAggregate(registry, opts = {}) {
  const ancestor = opts.ancestorChain || defaultChain;
  return (next) => async (domain, action, params, context) => {
    if (domain !== "map") return next(domain, action, params, context);
    const candidates = registry.resolve(action);
    if (!candidates) return next(domain, action, params, context);
    try {
      return await aggregate(action, candidates, params, {
        dispatch: next,
        ancestorChain: ancestor,
        quota: opts.quota,
        approval: opts.approval,
        now: opts.now,
      });
    } catch (e) {
      if (e instanceof CycleDetectedError) {
        return { rst_types: "text", rst_err: "ERR_EXECUTION", rst_data: { reason: "CYCLE_DETECTED" } };
      }
      throw e;
    }
  };
}

// ─── AsyncJobBridge（异步任务五态）─────────────────────────────────
/**
 * 五态：pending/running/done/error/cancelled
 * 语义：同步 status:stop = 降级信号（非终态）；异步终态 error + quota_exhausted = 终态。
 */
export class AsyncJobBridge {
  constructor(opts = {}) {
    this.now = opts.now || Date.now;
    this.seq = 0;
    this.jobs = new Map();
  }
  start(domain, action, params) {
    const taskId = `${domain}-${action}-${++this.seq}`;
    this.jobs.set(taskId, { task_id: taskId, domain, action, params, state: "pending", created_at: this.now() });
    return { taskId };
  }
  cancel(taskId) {
    const j = this.jobs.get(taskId);
    if (!j || j.state !== "running") return false;
    j.state = "cancelled";
    j.cancelled_at = this.now();
    return true;
  }
  succeed(taskId, result) {
    const j = this.jobs.get(taskId);
    if (!j || (j.state !== "running" && j.state !== "pending")) return false;
    j.state = "done";
    j.result = result;
    j.done_at = this.now();
    return true;
  }
  fail(taskId, code) {
    const j = this.jobs.get(taskId);
    if (!j || (j.state !== "running" && j.state !== "pending")) return false;
    j.state = "error";
    j.error = code || "ERR_EXECUTION";
    j.failed_at = this.now();
    return true;
  }
  /** 重启对账：所有 running → error + service_restarted */
  reconcileAfterRestart() {
    for (const j of this.jobs.values()) {
      if (j.state === "running") {
        j.state = "error";
        j.error = "service_restarted";
        j.residual = "service_restarted";
      }
    }
  }
  poll(taskId) {
    const j = this.jobs.get(taskId);
    if (!j) return { state: "not_found" };
    return j;
  }
}
