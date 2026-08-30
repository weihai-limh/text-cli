/**
 * executor.ts——path 声明层解释器（功能设计 §9）
 *
 * - _dispatch_step 统一派发（call/sequence/parallel/map/if/http_dispatch/delegated）
 * - 嵌套深度 ≤ maxDepth（默认 2），超限 NESTING_EXCEEDED
 * - 变量插值两层（{var} / {stepId.field}），未定义 → 空串 + WARNING
 * - if 四形式
 * - 降级递补：call 的 fallback 候选按序，全失败 → DEGRADE_EXHAUSTED
 * - parallel：first_ok / all
 * - map：默认关（enabled），硬上限 MAP_HARD_CAP，on_error stop/skip
 * - http_dispatch：跨节点（extract_rst_data）
 * - delegated：无匹配指令非 error
 * - get_final_output：反向找最后非空
 */
import { interpolateParams } from "./interpolate.js";
import { evalCondition } from "./conditions.js";
import type {
  CallStep,
  Condition,
  HttpDispatchStep,
  IfStep,
  MapStep,
  ParallelStep,
  PathDef,
  PathDeps,
  PathResult,
  PathStep,
  SequenceStep,
  DelegatedStep,
} from "./types.js";

const DEFAULT_MAX_DEPTH = 2;
const DEFAULT_MAP_CAP = 1000;

class PathError extends Error {
  constructor(
    public readonly code: string,
    public readonly step?: PathStep,
  ) {
    super(code);
    this.name = "PathError";
  }
}

/** 错误信封判定（rst_err 非空字符串） */
function isErrorResult(r: unknown): boolean {
  if (r && typeof r === "object" && "rst_err" in (r as Record<string, unknown>)) {
    const e = (r as Record<string, unknown>).rst_err;
    return typeof e === "string" && e.length > 0;
  }
  return false;
}

/** 从信封抽出 rst_data（new/old 格式统一） */
function extractRstData(r: unknown): unknown {
  if (r && typeof r === "object" && "rst_data" in (r as Record<string, unknown>)) {
    return (r as Record<string, unknown>).rst_data;
  }
  return r;
}

interface ExecCtx {
  vars: Record<string, unknown>;
  steps: Record<string, unknown>;
  warnings: string[];
}

async function callOne(
  domain: string,
  action: string,
  params: string[] | undefined,
  deps: PathDeps,
  ctx: ExecCtx,
): Promise<unknown> {
  const ip = interpolateParams(params, ctx, ctx.warnings);
  return deps.dispatch(domain, action, ip);
}

/** 单一调用 + 降级递补 */
async function executeCall(
  step: CallStep,
  deps: PathDeps,
  ctx: ExecCtx,
): Promise<unknown> {
  const candidates = [
    { domain: step.domain, action: step.action },
    ...(step.fallback ?? []),
  ];
  let lastErr: unknown = null;
  for (const c of candidates) {
    let r: unknown;
    try {
      r = await callOne(c.domain, c.action, step.params, deps, ctx);
    } catch (e) {
      lastErr = e;
      ctx.warnings.push(`call ${c.domain};${c.action} threw: ${e instanceof Error ? e.message : String(e)}`);
      continue;
    }
    if (!isErrorResult(r)) return r;
    lastErr = r;
  }
  throw new PathError("DEGRADE_EXHAUSTED", step);
}

/** 统一派发入口 */
async function dispatchStep(
  step: PathStep,
  deps: PathDeps,
  ctx: ExecCtx,
  depth: number,
  maxDepth: number,
  outputs: unknown[],
): Promise<unknown> {
  const childDepth = depth + 1;
  if (childDepth > maxDepth) throw new PathError("NESTING_EXCEEDED", step);

  // 归一化 call（type 缺省为 call；有 type 且非 "call" 视为复合步骤）
  const stepType = (step as { type?: string }).type;
  if (!stepType || stepType === "call") {
    const s = step as CallStep;
    if (s.domain === undefined) throw new PathError("INVALID_STEP", step);
    const r = await executeCall(s, deps, ctx);
    if (s.name) {
      ctx.steps[s.name] = r;
      ctx.vars[s.name] = r;
    }
    if (s.out) ctx.vars[s.out] = r;
    return r;
  }

  switch ((step as { type: string }).type) {
    case "sequence": {
      const s = step as SequenceStep;
      let last: unknown;
      for (const sub of s.steps) {
        last = await dispatchStep(sub, deps, ctx, childDepth, maxDepth, outputs);
      }
      return last;
    }

    case "parallel": {
      const s = step as ParallelStep;
      if (s.strategy === "all") {
        const rs = await Promise.all(
          s.branches.map((b) => dispatchStep(b, deps, ctx, childDepth, maxDepth, outputs)),
        );
        return rs;
      }
      // first_ok
      const errors: unknown[] = [];
      for (const b of s.branches) {
        try {
          return await dispatchStep(b, deps, ctx, childDepth, maxDepth, outputs);
        } catch (e) {
          errors.push(e);
        }
      }
      throw new PathError("DEGRADE_EXHAUSTED", step);
    }

    case "map": {
      const s = step as MapStep;
      if (!s.enabled) {
        ctx.warnings.push(`map "${s.as}" skipped (disabled)`);
        return [];
      }
      const arr = ctx.vars[s.over];
      if (!Array.isArray(arr)) {
        ctx.warnings.push(`map over non-array var "${s.over}"`);
        return [];
      }
      const cap = deps.mapHardCap ?? DEFAULT_MAP_CAP;
      const items = arr.slice(0, cap);
      if (arr.length > cap) ctx.warnings.push(`map truncated to ${cap}`);
      const results: unknown[] = [];
      const concurrency = s.concurrency && s.concurrency > 1 ? s.concurrency : 1;
      for (let i = 0; i < items.length; i += concurrency) {
        const chunk = items.slice(i, i + concurrency);
        const rs = await Promise.all(
          chunk.map(async (item) => {
            const saved = ctx.vars[s.as];
            ctx.vars[s.as] = item;
            try {
              return await dispatchStep(s.step, deps, ctx, childDepth, maxDepth, outputs);
            } finally {
              if (saved === undefined) delete ctx.vars[s.as];
              else ctx.vars[s.as] = saved;
            }
          }),
        );
        for (const r of rs) {
          if (s.on_error === "stop" && r instanceof PathError) throw r;
          results.push(r);
        }
      }
      return results;
    }

    case "if": {
      const s = step as IfStep;
      const cond: Condition = s.cond;
      const branch = evalCondition(cond, ctx) ? s.then : s.else;
      if (!branch) return undefined;
      return dispatchStep(branch, deps, ctx, childDepth, maxDepth, outputs);
    }

    case "http_dispatch": {
      const s = step as HttpDispatchStep;
      const ip = interpolateParams(s.params, ctx, ctx.warnings);
      let r: unknown;
      if (deps.httpDispatch) {
        r = await deps.httpDispatch(s.node, s.domain, s.action, ip);
      } else {
        r = await deps.dispatch(s.domain, s.action, ip);
      }
      return extractRstData(r);
    }

    case "delegated": {
      const s = step as DelegatedStep;
      const ip = interpolateParams(s.params, ctx, ctx.warnings);
      let r: unknown;
      try {
        r = await deps.dispatch(s.domain, s.action, ip);
      } catch {
        // 无匹配指令非 error
        ctx.warnings.push(`delegated no-match ${s.domain};${s.action}`);
        return { delegated: false, reason: "no-matching-directive" };
      }
      if (isErrorResult(r)) {
        ctx.warnings.push(`delegated no-match ${s.domain};${s.action}`);
        return { delegated: false, reason: "no-matching-directive" };
      }
      return { delegated: true, data: extractRstData(r) };
    }

    default:
      throw new PathError("UNKNOWN_STEP_TYPE", step);
  }
}

function lastNonEmpty(outputs: unknown[]): unknown {
  for (let i = outputs.length - 1; i >= 0; i--) {
    const o = outputs[i];
    if (o === undefined || o === null) continue;
    if (typeof o === "string" && o.length === 0) continue;
    if (Array.isArray(o) && o.length === 0) continue;
    if (typeof o === "object" && Object.keys(o as object).length === 0) continue;
    return o;
  }
  return undefined;
}

export async function runPath(def: PathDef, deps: PathDeps): Promise<PathResult> {
  const result: PathResult = {
    ok: false,
    vars: { ...(deps.initialVars ?? {}) },
    steps: {},
    warnings: [],
  };
  const ctx: ExecCtx = { vars: result.vars, steps: result.steps, warnings: result.warnings };
  const maxDepth = deps.maxDepth ?? DEFAULT_MAX_DEPTH;
  const outputs: unknown[] = [];

  try {
    for (const step of def.steps) {
      const r = await dispatchStep(step, deps, ctx, 0, maxDepth, outputs);
      if (r !== undefined) outputs.push(r);
    }
    result.ok = true;
    result.output = lastNonEmpty(outputs);
  } catch (e) {
    result.ok = false;
    result.error = e instanceof PathError ? e.code : e instanceof Error ? e.message : String(e);
  }
  return result;
}

export { PathError };
